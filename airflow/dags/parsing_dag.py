from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.dummy_operator import DummyOperator
from airflow.contrib.hooks.aws_hook import AwsHook
from airflow.operators.python_operator import PythonOperator
import logging
import boto3
import configparser
import os
from helpers.parse_election_data import (
    prepare_local_folder, remove_local_folder, parse_results,
    parse_candidates, parse_parties
)
from helpers.load_stations import load_stations_from_register

config = configparser.ConfigParser()
assert(os.path.isfile('config/config'))
config.read('config/config')

default_args = {
    'owner': 'udacity',
    'depends_on_past': False,
    'start_date': datetime(2019, 9, 1),
    'retries': 3,
    'retry_delay': timedelta(minutes=1),  # 1 minute for debugging purposes
    'catchup': False,
    'email_on_retry': False,
    'redshift_conn_id': 'redshift',
    'aws_conn_id': 'aws_credentials',
    'schema': 'public',
    'weight_rule': 'upstream',
}


def boto3_upload_to_s3(local_root_folder, folder):
    """
    Uploads .csv or .json files from a specified folder and its all subfolders
    :param local_root_folder:
    :param folder:
    :return:
    """
    aws_hook = AwsHook(aws_conn_id='aws_credentials')
    aws_access_key_id, aws_secret_access_key, _ = aws_hook.get_credentials()

    s3 = boto3.client('s3',
                      aws_access_key_id=aws_access_key_id,
                      aws_secret_access_key=aws_secret_access_key)
    bucket = config.get('S3', 'BUCKET_NAME')

    logging.info(f'Uploading folder {os.path.join(local_root_folder, folder)}')

    for root, dirs, files in os.walk(os.path.join(local_root_folder, folder),
                                     topdown=False):
        prefix_len = len(local_root_folder) + 1
        for name in files:
            if name.lower().endswith('.csv') or name.lower().endswith('.json'):
                path_local = os.path.join(root, name)
                s3_key = path_local[prefix_len:]
                logging.info(f'Uploading file {s3_key}')
                s3.upload_file(path_local, bucket, s3_key)


def create_folders(local_data_folder, subfolder):
    if not os.path.isdir(local_data_folder):
        prepare_local_folder(local_data_folder)
    if subfolder:
        prepare_local_folder(os.path.join(local_data_folder, subfolder))


def create_campaign_dag(campaign):
    """
    The same code returns multiple DAGs as suggested in
    https://www.astronomer.io/guides/dynamically-generating-dags/
    :param campaign: identifier of election campaign
    :return: DAG
    """
    with DAG(f'1.parse_and_upload_to_s3.{campaign}',
             default_args=default_args,
             description=f'Parse data for campaign {campaign} from '
             f'https://www.cvk.gov.ua/pls/{campaign}/ '
             f'and load to s3',
             schedule_interval='@once'
             ) as campaign_dag:

        local_data_folder = os.path.join(
            config.get('LOCAL', 'LOCAL_ROOT_FOLDER'), campaign
        )

        start_task = DummyOperator(task_id=f'parse.{campaign}.begin_execution')

        create_folders_task = PythonOperator(
            task_id=f'parse.{campaign}.create_folders',
            python_callable=prepare_local_folder,
            op_kwargs={'local_folder': local_data_folder}
        )

        parse_results_individual_task = PythonOperator(
            task_id=f'parse.{campaign}.parse_results_individual',
            python_callable=parse_results,
            op_kwargs={'campaign': campaign,
                       'ballot': 'individual',
                       'local_data_folder': local_data_folder
                       }
        )

        parse_results_party_task = PythonOperator(
            task_id=f'parse.{campaign}.parse_results_party',
            python_callable=parse_results,
            op_kwargs={'campaign': campaign,
                       'ballot': 'party',
                       'local_data_folder': local_data_folder
                       }
        )

        parse_candidates_task = PythonOperator(
            task_id=f'parse.{campaign}.parse_candidates',
            python_callable=parse_candidates,
            op_kwargs={'campaign': campaign,
                       'local_data_folder': local_data_folder
                       }
        )

        parse_parties_task = PythonOperator(
            task_id=f'parse.{campaign}.parse_parties',
            python_callable=parse_parties,
            op_kwargs={'campaign': campaign,
                       'local_data_folder': local_data_folder
                       }
        )

        upload_folders_to_s3_task = PythonOperator(
            task_id=f'parse.{campaign}.upload_folders_to_s3',
            python_callable=boto3_upload_to_s3,
            op_kwargs={
                'local_root_folder': config.get('LOCAL', 'LOCAL_ROOT_FOLDER'),
                'folder': campaign}
        )

        '''
        remove_folders_task = PythonOperator(
            task_id=f'parse.{campaign}.remove_folders',
            python_callable=remove_local_folder,
            op_kwargs={'local_folder': local_data_folder}
        )
        '''

        end_task = DummyOperator(task_id=f'parse.{campaign}.stop_execution')

        start_task >> create_folders_task >> parse_results_individual_task >> \
            parse_results_party_task >> parse_candidates_task >> \
            parse_parties_task >> upload_folders_to_s3_task >> end_task

    return campaign_dag


for campaign in ['vnd2019', 'vnd2014', 'vnd2012']:
    globals()[f'1.parse_and_upload_to_s3.{campaign}'] = \
        create_campaign_dag(campaign)


with DAG('1.load_polling_stations_from_register', default_args=default_args,
         description='Parse stations from the State Voters Register '
                     'https://www.drv.gov.ua',
         schedule_interval='@once'
         ) as load_stations_dag:
    folder_name = 'stations_from_register'
    local_data_folder = os.path.join(
        config.get('LOCAL', 'LOCAL_ROOT_FOLDER'), folder_name
    )

    start_task = DummyOperator(task_id=f'ps.begin_execution')

    create_folders_task = PythonOperator(
        task_id=f'ps.create_folders',
        python_callable=prepare_local_folder,
        op_kwargs={'local_folder': local_data_folder}
    )

    parse_stations_task = PythonOperator(
        task_id=f'ps.load_stations_from_register',
        python_callable=load_stations_from_register,
        op_kwargs={'local_data_folder': local_data_folder}
    )

    upload_folders_to_s3_task = PythonOperator(
        task_id=f'ps.upload_folders_to_s3',
        python_callable=boto3_upload_to_s3,
        op_kwargs={
            'local_root_folder': config.get('LOCAL', 'LOCAL_ROOT_FOLDER'),
            'folder': folder_name
        }
    )

    '''
    remove_folders_task = PythonOperator(
        task_id=f'ps.remove_folders',
        python_callable=remove_local_folder,
        op_kwargs={'local_folder': local_data_folder}
    )
    '''

    end_task = DummyOperator(task_id=f'ps.stop_execution')

    start_task >> create_folders_task >> parse_stations_task >> \
        upload_folders_to_s3_task >> end_task
