# Implements parsing elections results from the website of
# the Central Election Commission of Ukraine
import shutil
import os
import requests
from bs4 import BeautifulSoup
import logging
import time
import random
import pandas as pd
import re
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import configparser

config = configparser.ConfigParser()
assert(os.path.isfile('config/config'))
config.read('config/config')

LOCAL_DATA_FOLDER = config.get('LOCAL', 'LOCAL_ROOT_FOLDER')

# set delay after http request to limit the website load
parse_delay_range = {
    'success': (0.5, 1.0),
    'failure': (0.2, 0.2),
}


class UrlMapper:
    """
    Implements class that generate url to the page
    with the requested elections results
    """
    implemented_campaigns = {'vnd2019', 'vnd2014', 'vnd2012'}

    # for templated campaigns the url is generated from template
    # (no initial parsing is needed)
    templated_campaigns = {'vnd2019', 'vnd2014'}
    start_urls = {
        'vnd2012': {
            'prefix': 'https://www.cvk.gov.ua/pls/vnd2012/',
            'party': 'wp005ad94.html?PT001F01=900',
            'individual': 'wp039ad94.html?PT001F01=900',
        }
    }

    def __init__(self):
        self.implemented_campaigns = UrlMapper.implemented_campaigns
        self.templated_campaigns = UrlMapper.templated_campaigns
        self.start_urls = UrlMapper.start_urls
        self.mapper = dict()

    @staticmethod
    def _get_url(campaign, ballot, district):
        """Generates url from template"""
        template = None
        if campaign == 'vnd2019':
            if ballot == 'party':
                template = 'https://www.cvk.gov.ua/pls/vnd2019/' \
                           'wp336pt001f01=919pf7331={}.html'
            elif ballot == 'individual':
                template = 'https://www.cvk.gov.ua/pls/vnd2019/' \
                           'wp338pt001f01=919pf7331={}.html'
        if campaign == 'vnd2014':
            if ballot == 'party':
                template = 'https://www.cvk.gov.ua/pls/vnd2014/' \
                           'wp336pt001f01=910pf7331={}.html'
            elif ballot == 'individual':
                template = 'https://www.cvk.gov.ua/pls/vnd2014/' \
                           'wp338pt001f01=910pf7331={}.html'
        if template:
            return template.format(district)

    def get_url(self, campaign, ballot, district):
        assert campaign in self.implemented_campaigns
        assert ballot in {'individual', 'party'}
        if campaign not in self.templated_campaigns:
            if campaign in self.start_urls \
                    and ballot in self.start_urls[campaign] \
                    and not (campaign in self.mapper and
                             ballot in self.mapper[campaign]):
                # initialize mapper
                logging.info(f'Inititalizing url mapper for campaign'
                             f'={campaign} and ballot_type={ballot}')
                url = self.start_urls[campaign]['prefix'] + \
                    self.start_urls[campaign][ballot]
                page = requests_retry_session().get(url, timeout=10)
                soup = BeautifulSoup(page.content, 'lxml')
                tables = soup.find_all('table')
                tables = [table for table in tables
                          if safe_len(table.find_all('a')) > 10]
                table = tables[-1]

                if campaign not in self.mapper:
                    self.mapper[campaign] = dict()
                self.mapper[campaign][ballot] = dict()
                for row in table.find_all('tr'):
                    values = row.find_all('td')
                    if values and values[0].find('a'):
                        d = int(values[0].text.split('№')[1])
                        url2 = self.start_urls[campaign]['prefix'] + \
                            values[0].find('a')['href']
                        page2 = requests_retry_session().get(url2, timeout=10)
                        soup2 = BeautifulSoup(page2.content, 'lxml')
                        a = soup2.find(
                            'a',
                            string='Результати голосування на виборчих '
                                   'дільницях округу'
                        )
                        self.mapper[campaign][ballot][d] = \
                            self.start_urls[campaign]['prefix'] + a['href']
                        time.sleep(
                            random.uniform(*parse_delay_range['success'])
                        )
                logging.info(f'Mapper for campaign={campaign} and ballot_type'
                             f'={ballot} has been initialized')
            # retrieve the link
            return self.mapper[campaign][ballot].get(district, None)
        else:
            return self._get_url(campaign, ballot, district)


urlmapper = UrlMapper()


def requests_retry_session(
        retries=3,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 503, 504),
        session=None,
):
    """
    Make sure that request retries on failure.
    Source:
    https://www.peterbe.com/plog/best-practice-with-retries-with-requests
    """
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def safe_len(text):
    """
    Calculates the length of some html block
    :param text: text
    :return: Length of the text block. Returns 0 in case of error.
    """
    try:
        l = len(text)
    except:
        l = 0
    return l


def prepare_local_folder(local_folder):
    """Creates local folder"""
    try:
        shutil.rmtree(local_folder)
    except FileNotFoundError:
        pass
    os.makedirs(local_folder)


def remove_local_folder(local_folder):
    """Removes local folder"""
    try:
        shutil.rmtree(local_folder)
    except FileNotFoundError:
        pass


def enrich_df(df, columns):
    """
    Adds columns with constant values to dataframe.
    :param df: dataframe
    :param columns: list of tuples with (colname, colvalue)
    :return:
    """
    for col, v in columns[::-1]:
        df.insert(0, col, v)
    return df


def drop_unused_columns(df):
    """Removes stop_columns from dataframe"""
    stop_columns = {
        'Наявність (відсутність) заборгованості зі сплати '
        'аліментів на утримання дитини',
        'Передвиборна програма',
        'Декларація'
    }
    return df.drop(columns=[c for c in df.columns if c in stop_columns])


def split_results(df, num_columns_station=15, dim_col='Кандидат чи партія',
                  truncated2012=False):
    """
    Splits election results into station part and competitor part.
    :param df: dataframe with results
    :param num_columns_station: how many columns at the left side
    belong to the station part.
    :param dim_col: name of the created 'competitor' column.
    :param truncated2012: True if a special logic for 2012 Parliamentary
    elections to be applied.
    :return: two dataframes, station results and competitor results.
    """
    station_cols = list(df.columns[:num_columns_station]) + [df.columns[-1]]
    competitor_cols = [df.columns[0]] + \
        list(df.columns[num_columns_station:-1])
    df_station = df[station_cols]
    if truncated2012:
        cols = [df.columns[0]] + [f'dummy_{n}' for n in range(1, 16)]
        cols[3] = df_station.columns[1]
        cols[14] = df_station.columns[2]
        for col in cols:
            if col not in df_station.columns:
                df_station[col] = ''
        df_station = df_station[cols]

    df_competitor = df[competitor_cols]
    comp2i = {c: i for i, c in enumerate(df_competitor.columns[1:])}
    i2comp = {i: c for c, i in comp2i.items()}
    df_competitor.columns = [competitor_cols[0]] + \
        [f'votes_{i}' for i, c in enumerate(competitor_cols[1:])]
    df_competitor = pd.wide_to_long(
        df_competitor, stubnames='votes', i=competitor_cols[:1],
        j=dim_col, sep='_', suffix='\w+'
    )
    df_competitor.reset_index(inplace=True)
    df_competitor[dim_col] = df_competitor[dim_col].map(i2comp)
    return df_station, df_competitor


def get_bs_table_from_url(url):
    """
    Loads html and returns tables from it.
    This is a repeated block in a few parsing scenarios.
    """
    page = requests_retry_session().get(url, timeout=10)
    soup = BeautifulSoup(page.content, 'lxml')
    tables = soup.find_all('table')
    time.sleep(random.uniform(*parse_delay_range['success']))
    return tables


def parse_results(campaign, ballot, local_data_folder=LOCAL_DATA_FOLDER):
    """
    Parses election results at polling stations.
    :param campaign: identifier of election campaign
    :param ballot: ballot type
    :param local_data_folder: local folder to save the data
    """
    assert campaign in {'vnd2019', 'vnd2014', 'vnd2012'}
    assert ballot in {'individual', 'party', }

    folders = [
        os.path.join(local_data_folder, f'results_{ballot}_raw'),
        os.path.join(local_data_folder, f'results_{ballot}_station'),
        os.path.join(local_data_folder, f'results_{ballot}_competitor')
    ]
    for folder in folders:
        prepare_local_folder(folder)

    for district in range(1, 227):
        url = urlmapper.get_url(campaign, ballot, district)
        if url:
            page = requests_retry_session().get(url, timeout=10)
            if page.status_code == 200:
                dfs = pd.read_html(
                    page.content.decode('cp1251').replace('<br>', ' '),
                    converters={0: str}
                )
                dfs = [df for df in dfs if df.shape[1] >= 5]
                df = dfs[-1]

                if df.columns[0] == 0:
                    df.columns = df.iloc[0]
                    df = df.iloc[1:]

                df.to_csv(
                    os.path.join(local_data_folder, f'results_{ballot}_raw',
                                 f'{campaign}_{district}_{ballot}.csv'),
                    encoding='utf-8-sig',
                    index=False
                )

                # For some rows additional info like 'Not valid'
                # is present with the station id. It will be cleaned in redshift.
                # df[df.columns[0]] = df[df.columns[0]].map(
                #    lambda x: ''.join([c for c in x if c.isdigit()])
                # )

                if campaign == 'vnd2012' and ballot == 'party':
                    df_station, df_competitor = split_results(
                        df, num_columns_station=3, truncated2012=True
                    )
                else:
                    df_station, df_competitor = split_results(df)

                df_station = enrich_df(
                    df_station,
                    (('Виборча кампанія', campaign), ('Тип округу', ballot),
                     ('Виборчий округ', district),)
                )
                df_competitor = enrich_df(
                    df_competitor,
                    (('Виборча кампанія', campaign), ('Тип округу', ballot),
                     ('Виборчий округ', district),)
                )

                df_station.to_csv(
                    os.path.join(local_data_folder, f'results_{ballot}_station',
                                 f'{campaign}_{district}_{ballot}.csv'),
                    encoding='utf-8-sig',
                    index=False
                )
                df_competitor.to_csv(
                    os.path.join(local_data_folder, f'results_{ballot}_competitor',
                                 f'{campaign}_{district}_{ballot}.csv'),
                    encoding='utf-8-sig',
                    index=False
                )

                logging.info(f'Loaded {ballot} results for district {district}')
                time.sleep(random.uniform(*parse_delay_range['success']))
            else:
                logging.info(f'No info available for district {district}')
                time.sleep(random.uniform(*parse_delay_range['failure']))


# Currently not used
# Can be used to fill the gaps in the stations data
# from the State Voters Register.
def parse_stations(campaign='vnd2019',
                   local_data_folder=LOCAL_DATA_FOLDER):
    """
    Parses data for polling stations from the election campaign data
    :param campaign: identifier of election campaign
    :param local_data_folder: local folder to save the data
    """
    assert campaign in {'vnd2019', }
    if campaign == 'vnd2019':
        link_prefix = 'https://www.cvk.gov.ua/pls/vnd2019/'
        start_url = 'wp030pt001f01=919.html'

    start_url = link_prefix + start_url
    page = requests_retry_session().get(start_url, timeout=10)
    soup = BeautifulSoup(page.content, 'lxml')
    tables = soup.find_all('table')
    table = tables[-1]
    links = [link for link in table.find_all('a')
             if 'wp024' in link['href'] or 'wp029' in link['href']]

    prepare_local_folder(os.path.join(local_data_folder, 'polling_stations'))
    prepare_local_folder(os.path.join(local_data_folder, 'polling_districts'))

    for a, b in zip(links[::2], links[1::2]):
        district = a.next_element
        url = '{}{}'.format(link_prefix, b['href'])
        url2 = '{}{}'.format(link_prefix, a['href'])
        # print(f'loading district {district}\r', end='')
        page = requests_retry_session().get(url, timeout=10)
        page2 = requests_retry_session().get(url2, timeout=10)
        if page.status_code == 200 and page2.status_code == 200:
            dfs = pd.read_html(
                page.content.decode('cp1251').replace('<br>', ' ')
            )
            df = dfs[-1]
            filename1 = os.path.join(local_data_folder, 'polling_stations',
                                     f'{campaign}_{district}.csv')
            df.to_csv(filename1, encoding='utf-8-sig', index=False)

            dfs = pd.read_html(
                page2.content.decode('cp1251').replace('<br>', ' ')
            )
            df = dfs[-1]
            filename2 = os.path.join(local_data_folder, 'polling_districts',
                                     f'{campaign}_{district}.csv')
            df.to_csv(filename2, encoding='utf-8-sig', index=False)
            logging.info(f'Loaded stations and district info '
                         f'for district {district}')

            time.sleep(random.uniform(*parse_delay_range['success']))
        else:
            logging.info(f'No stations or district info '
                         f'for district {district}')
            time.sleep(random.uniform(*parse_delay_range['failure']))


# Currently not used
# Can be used to fill the gaps in the stations data
# from the State Voters Register.
def parse_stations_intrntl(campaign='vnd2019',
                           local_data_folder=LOCAL_DATA_FOLDER):
    """
    Parses data for polling stations abroad from
    the election campaign data
    :param campaign: identifier of election campaign
    :param local_data_folder: local folder to save the data
    :return:
    """
    assert campaign in {'vnd2019', }
    if campaign == 'vnd2019':
        link_prefix = 'https://www.cvk.gov.ua/pls/vnd2019/'
        start_url = 'wp045pt001f01=919.html'

    start_url = link_prefix + start_url
    page = requests_retry_session().get(start_url, timeout=10)
    soup = BeautifulSoup(page.content, 'lxml')
    tables = soup.find_all('table')
    table = tables[-1]

    prepare_local_folder(
        os.path.join(local_data_folder, 'polling_stations_abroad')
    )

    parsed_data = []
    for row in table.find_all('tr'):
        values = row.find_all('td')
        if values and values[2].find('a'):
            country = values[0].contents[0]
            link = '{}{}'.format(link_prefix, values[2].contents[0]['href'])
            for i, r in pd.read_html(link)[-1].iterrows():
                r = list(r)
                parsed_data.append([r[0], ', '.join([r[1], r[2]]), country])
        time.sleep(random.uniform(*parse_delay_range['success']))

    df = pd.DataFrame(
        parsed_data,
        columns=[
            '№ дільниці',
            'Місцезнаходження та адреса приміщення для голосування',
            'Назва країни'
        ]
    )
    df.to_csv(
        os.path.join(local_data_folder, 'polling_stations_abroad',
                     f'{campaign}.csv'),
        encoding='utf-8-sig',
        index=False
    )

    logging.info(f'Loaded info for polling stations abroad')


def parse_candidates(
        campaign='vnd2019',
        ballot='individual',
        local_data_folder=LOCAL_DATA_FOLDER
):
    """
    Parses information about campaign candidates.
    :param campaign: identifier of election campaign
    :param ballot: ballot type
    :param local_data_folder: local folder to save results
    """
    assert campaign in {'vnd2019', 'vnd2014', 'vnd2012'}
    assert ballot in {'individual', }

    # There is a summary page with the list of polling districts or parties.
    # Links from the summary page lead to the list of candidates
    # in the polling district of the party list.
    # Links to summary pages are specified below.
    if campaign == 'vnd2019':
        link_prefix = 'https://www.cvk.gov.ua/pls/vnd2019/'
        start_url = 'wp032pt001f01=919.html'
    elif campaign == 'vnd2014':
        link_prefix = 'https://www.cvk.gov.ua/pls/vnd2014/'
        start_url = 'wp032pt001f01=910.html'
    elif campaign == 'vnd2012':
        link_prefix = 'https://www.cvk.gov.ua/pls/vnd2012/'
        start_url = 'wp032ad94.html?PT001F01=900'

    start_url = link_prefix + start_url
    page = requests_retry_session().get(start_url, timeout=10)
    soup = BeautifulSoup(page.content, 'lxml')
    tables = soup.find_all('table')
    tables = [table for table in tables if safe_len(table.find_all('a')) > 10]

    table = tables[-1]
    links = [link for link in table.find_all('a')
             if 'wp024' in link['href'].lower() or
             'wp033' in link['href'].lower()]

    prepare_local_folder(
        os.path.join(local_data_folder, f'candidates_{ballot}')
    )

    for a, b in zip(links[::2], links[1::2]):
        district = re.findall(r'\d+', a.next_element)[-1]
        url = '{}{}'.format(link_prefix, b['href'])
        page = requests_retry_session().get(url, timeout=10)
        if page.status_code == 200:
            dfs = pd.read_html(
                page.content.decode('cp1251').replace('<br>', ' ')
            )
            dfs = [df for df in dfs if df.shape[1] >= 5]
            df = dfs[-1]

            if df.columns[0] == 0:
                df.columns = df.iloc[0]
                df = df.iloc[1:]

            df = drop_unused_columns(df)

            df = enrich_df(
                df, (('Виборча кампанія', campaign), ('Тип округу', ballot),
                     ('Виборчий округ', district), )
            )

            df.to_csv(os.path.join(local_data_folder, f'candidates_{ballot}',
                                   f'{campaign}_{district}.csv'),
                      encoding='utf-8-sig',
                      index=False)

            logging.info(f'Loaded {ballot} candidates info for '
                         f'district {district}')

            time.sleep(random.uniform(*parse_delay_range['success']))
        else:
            logging.info(f'No candidate info for district {district}')
            time.sleep(random.uniform(*parse_delay_range['failure']))


def parse_parties(
        campaign='vnd2019',
        ballot='party',
        local_data_folder=LOCAL_DATA_FOLDER
):
    """
    Parses the party list for a campaign
    :param campaign: identifier of elections campaign
    :param ballot: ballot type
    :param local_data_folder: local folder to save results
    :return:
    """
    assert campaign in {'vnd2019', 'vnd2014', 'vnd2012'}
    assert ballot in {'party', }
    if campaign == 'vnd2019':
        link_prefix = 'https://www.cvk.gov.ua/pls/vnd2019/'
        start_url = 'wp400pt001f01=919.html'
    elif campaign == 'vnd2014':
        link_prefix = 'https://www.cvk.gov.ua/pls/vnd2014/'
        start_url = 'wp400pt001f01=910.html'
    elif campaign == 'vnd2012':
        link_prefix = 'https://www.cvk.gov.ua/pls/vnd2012/'
        start_url = 'wp400ad94.html?PT001F01=900'

    start_url = link_prefix + start_url
    page = requests_retry_session().get(start_url, timeout=10)
    soup = BeautifulSoup(page.content, 'lxml')
    tables = soup.find_all('table')
    tables = [table for table in tables if safe_len(table.find_all('a')) > 10]
    table = tables[-1]

    prepare_local_folder(os.path.join(local_data_folder, 'parties'))
    prepare_local_folder(
        os.path.join(local_data_folder, f'candidates_{ballot}')
    )

    content = page.content.decode('cp1251').replace('<br>', ' ')
    try:
        dfs = pd.read_html(content, converters={1: str})
    except:
        dfs = pd.read_html(content)
    dfs = [df for df in dfs if df.shape[1] >= 4]
    df = dfs[-1]
    if df.columns[0] == 0:
        df.columns = df.iloc[0]
        df = df.iloc[1:]

    df = drop_unused_columns(df)

    df = df.iloc[:, :4]

    df = enrich_df(
        df,
        (('Виборча кампанія', campaign),)
    )

    df.to_csv(os.path.join(local_data_folder, f'parties', f'{campaign}.csv'),
              encoding='utf-8-sig',
              index=False,
              # quoting=csv.QUOTE_NONE
              )

    for row in table.find_all('tr'):
        values = row.find_all('td')

        if values and len(re.findall(r'\d+', values[1].contents[0])) > 0 \
                and values[3].find('a'):
            num = re.findall(r'\d+', values[1].contents[0])[0]
            parsed_data = []
            party = values[2].text
            link = '{}{}'.format(link_prefix, values[3].contents[0]['href'])
            page = requests_retry_session().get(link, timeout=10)
            dfs = pd.read_html(
                page.content.decode('cp1251').replace('<br>', ' ')
            )
            dfs = [df for df in dfs if df.shape[1] >= 4]
            for i, r in dfs[-1].iterrows():
                r = list(r)
                try:
                    n = int(r[0])
                except:
                    n = 0
                if n > 0:
                    if campaign in ('vnd2012', ):
                        record = r[:3] + [r[4], party]

                    else:
                        record = r[:4] + [party]
                    record = [' '.join(str(t).split()) for t in record if t]
                    parsed_data.append(record)

            df = pd.DataFrame(
                parsed_data,
                columns=['Номер у списку', 'Прізвище, ім’я, по батькові',
                         'Основні відомості', 'Дата реєстрації/обрання',
                         'Назва партії - суб’єкту виборчого процесу']
            )
            df = enrich_df(
                df, (('Виборча кампанія', campaign), )
            )
            df.to_csv(
                os.path.join(local_data_folder, f'candidates_{ballot}',
                             f'{campaign}_{num}.csv'),
                encoding='utf-8-sig',
                index=False,
                # quoting=csv.QUOTE_MINIMAL,
                # escapechar='\\'
            )
            logging.info(f'Loaded candidates for party {num} {party}')
            time.sleep(random.uniform(*parse_delay_range['success']))


if __name__ == '__main__':
    t0 = time.time()
    t1 = time.time()
    campaign = 'vnd2019'
    subfolder = os.path.join(LOCAL_DATA_FOLDER, campaign)

    prepare_local_folder(subfolder)

    parse_results(campaign=campaign,
                  ballot='individual',
                  local_data_folder=subfolder
                  )
    print(1, time.time()-t0, time.time()-t1)
    t1 = time.time()

    parse_results(campaign=campaign,
                  ballot='party',
                  local_data_folder=subfolder
                  )
    print(2, time.time()-t0, time.time()-t1)
    t1 = time.time()

    parse_stations(local_data_folder=subfolder)
    print(3, time.time() - t0, time.time() - t1)
    t1 = time.time()

    parse_stations_intrntl(local_data_folder=subfolder)
    print(4, time.time() - t0, time.time() - t1)
    t1 = time.time()

    for ballot, start_url in (('individual', 'wp032pt001f01=919.html'), ):
        parse_candidates(ballot=ballot, start_url=start_url,
                         local_data_folder=subfolder)
    print(5, time.time() - t0, time.time() - t1)
    t1 = time.time()

    parse_parties(local_data_folder=subfolder)
    print(6, time.time() - t0, time.time() - t1)
    t1 = time.time()
