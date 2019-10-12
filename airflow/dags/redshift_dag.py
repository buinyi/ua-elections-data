from airflow import DAG
from airflow.operators.dummy_operator import DummyOperator
from airflow.hooks.postgres_hook import PostgresHook
from airflow.hooks.S3_hook import S3Hook
from airflow.operators.s3_to_redshift_operator import S3ToRedshiftTransfer
from airflow.operators.create_drop_insert_plugin import (
    CreateTableOperator, DropTableOperator, InsertOperator
)
from airflow.operators.data_quality_plugin import (DataQualityOperator)
import configparser
import os
from parsing_dag import default_args
from helpers.queries import SqlQueries

sql_queries = SqlQueries

config = configparser.ConfigParser()
assert(os.path.isfile('config/config'))
config.read('config/config')


# To use standard S3ToRedshiftTransfer operator with our key structure
# we need to remove '{table}' from the end of the s3_key
def execute_copy(self, context):
    self.hook = PostgresHook(postgres_conn_id=self.redshift_conn_id)
    self.s3 = S3Hook(aws_conn_id=self.aws_conn_id, verify=self.verify)
    credentials = self.s3.get_credentials()
    copy_options = '\n\t\t\t'.join(self.copy_options)

    copy_query = """
        COPY {schema}.{table}
        FROM 's3://{s3_bucket}/{s3_key}'
        with credentials
        'aws_access_key_id={access_key};aws_secret_access_key={secret_key}'
        {copy_options};
    """.format(schema=self.schema,
               table=self.table,
               s3_bucket=self.s3_bucket,
               s3_key=self.s3_key,
               access_key=credentials.access_key,
               secret_key=credentials.secret_key,
               copy_options=copy_options)

    self.log.info('Executing COPY command...')
    self.hook.run(copy_query, self.autocommit)
    self.log.info("COPY command complete...")

S3ToRedshiftTransfer.execute = execute_copy


with DAG('2.redshift.upload_polling_stations',
         default_args=default_args,
         description='Upload polling station data',
         schedule_interval='@once'
         ) as dag_ps:

    code = 'ps'
    start_task = DummyOperator(task_id=f'{code}.begin_execution')

    drop_stations_staging_table = DropTableOperator(
        task_id=f'{code}.drop_polling_stations_staging',
        sql_stmnt=sql_queries.stations_table['staging']['drop'],
    )

    drop_stations_prod_table = DropTableOperator(
        task_id=f'{code}.drop_polling_stations',
        sql_stmnt=sql_queries.stations_table['prod']['drop'],
    )

    create_stations_staging_task = CreateTableOperator(
        task_id=f'{code}.create_stations_staging_table',
        sql_stmnt=sql_queries.stations_table['staging']['create'],
    )

    create_stations_prod_task = CreateTableOperator(
        task_id=f'{code}.create_stations_table',
        sql_stmnt=sql_queries.stations_table['prod']['create'],
    )

    copy_stations_staging = S3ToRedshiftTransfer(
        task_id=f'{code}.copy_polling_stations_data_from_s3_to_redshift',
        table='polling_stations_staging',
        s3_bucket=config.get('S3', 'BUCKET_NAME'),
        s3_key='stations_from_register/station',
        copy_options=('COMPUPDATE OFF', 'STATUPDATE OFF', "JSON 'auto'")
    )

    fix_stations_staging = InsertOperator(
        task_id=f'{code}.fix_polling_stations_staging',
        sql_stmnt=sql_queries.stations_table['staging']['fix1'],
    )

    stations_insert_task = InsertOperator(
        task_id=f'{code}.stations_insert',
        sql_stmnt=sql_queries.stations_table['prod']['insert'],
    )

    data_quality_check1 = DataQualityOperator(
        task_id=f'{code}.data_quality_check1',
        table='polling_stations',
        sql_stmnt=sql_queries.stations_table['prod']['check1'],
        trigger_rule='all_done',
    )

    data_quality_check2 = DataQualityOperator(
        task_id=f'{code}.data_quality_check2',
        table='polling_stations',
        sql_stmnt=sql_queries.stations_table['prod']['check2'],
        trigger_rule='all_done',
    )

    drop_stations_staging_table2 = DropTableOperator(
        task_id=f'{code}.drop_polling_stations_staging2',
        sql_stmnt=sql_queries.stations_table['staging']['drop'],
        trigger_rule='all_done',
    )

    end_task = DummyOperator(
        task_id=f'{code}.stop_execution',
        trigger_rule='all_done',
    )

    start_task >> [drop_stations_staging_table, drop_stations_prod_table] >> \
        create_stations_staging_task >> create_stations_prod_task >> \
        copy_stations_staging >> fix_stations_staging >> \
        stations_insert_task >> [data_quality_check1, data_quality_check2] >> \
        drop_stations_staging_table2 >> end_task


def create_campaign_dag(campaign):
    """
        The same code returns multiple DAGs as suggested in
        https://www.astronomer.io/guides/dynamically-generating-dags/
        :param campaign: identifier of election campaign
        :return: DAG
        """
    with DAG(f'3.redshift.upload_campaign_{campaign}',
             default_args=default_args,
             description=f'Upload data to Redshift for campaign {campaign}',
             schedule_interval='@once'
             ) as dag_campaign:

        start_task = DummyOperator(
            task_id=f'redshift.{campaign}.begin_execution'
        )

        queries = [
            sql_queries.parties_table,
            sql_queries.candidates_individual_table,
            sql_queries.results_station_table,
            sql_queries.results_competitor_table
        ]

        create_all_prod_tables = [q['prod']['create'] for q in queries]
        create_all_staging_tables = [q['staging']['drop'] for q in queries] + \
                                    [q['staging']['create'] for q in queries]

        create_all_prod_tables = CreateTableOperator(
            task_id=f'redshift.{campaign}.create_if_not_exists_'
            f'all_prod_tables',
            sql_stmnt='\n\t\t\t'.join(create_all_prod_tables),
        )

        create_all_staging_tables = CreateTableOperator(
            task_id=f'redshift.{campaign}.create_all_staging_tables',
            sql_stmnt='\n\t\t\t'.join(create_all_staging_tables),
        )

        copy_tasks = []
        for s3_keys, table in (
            (('parties', ), 'parties_staging'),
            (('candidates_individual', ), 'candidates_individual_staging'),
            (('results_individual_station', 'results_party_station', ),
             'results_station_staging'),
            (('results_individual_competitor', 'results_party_competitor', ),
             'results_competitor_staging'),
        ):
            for s3_key in s3_keys:
                task = S3ToRedshiftTransfer(
                    task_id=f'redshift.{campaign}.copy_{s3_key}_data_'
                    f'from_s3_to_redshift',
                    table=table,
                    s3_bucket=config.get('S3', 'BUCKET_NAME'),
                    s3_key=f'{campaign}/{s3_key}/',
                    copy_options=('IGNOREHEADER 1', 'IGNOREBLANKLINES',
                                  'COMPUPDATE OFF', 'STATUPDATE OFF',
                                  'CSV', 'maxerror as 250')
                )
                copy_tasks.append(task)

        insert_tasks = []
        for table in ('parties', 'candidates_individual', 'results_station',
                      'results_competitor'):
            sql = sql_queries.__dict__[f'{table}_table']['prod']['insert']
            task = InsertOperator(
                task_id=f'redshift.{campaign}.insert_{table}',
                sql_stmnt=sql,
            )
            insert_tasks.append(task)
            if len(insert_tasks) > 1:
                insert_tasks[-2] >> insert_tasks[-1]

        data_quality_check_tasks = []
        for table in ('parties', 'candidates_individual', 'results_station',
                      'results_competitor'):
            for key, sql in \
                    sql_queries.__dict__[f'{table}_table']['prod'].items():
                if key.startswith('check'):
                    task = DataQualityOperator(
                        task_id=f'redshift.{campaign}.{table}.data_'
                        f'quality_check.key',
                        table=table,
                        sql_stmnt=sql.format(campaign),
                        trigger_rule='all_done',
                    )
                    data_quality_check_tasks.append(task)

        end_task = DummyOperator(
            task_id=f'redshift.{campaign}.stop_execution',
            trigger_rule='all_done',
        )

        start_task >> create_all_prod_tables >> create_all_staging_tables >> \
            copy_tasks >> insert_tasks[0]

        insert_tasks[-1] >> data_quality_check_tasks >> end_task
    return dag_campaign

for campaign in ['vnd2019', 'vnd2014', 'vnd2012']:
    globals()[f'3.redshift.upload_campaign_{campaign}'] = \
        create_campaign_dag(campaign)
