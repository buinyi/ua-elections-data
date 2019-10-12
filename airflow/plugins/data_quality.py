from airflow.hooks.postgres_hook import PostgresHook
from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from airflow.plugins_manager import AirflowPlugin


class DataQualityOperator(BaseOperator):
    """
    Implements DataQualityOperator class.

    Parameters:
        table: table name
        select_stmnt: sql that generates the data to be
        uploaded into table
        redshift_conn_id: redshift connection id
    """

    ui_color = '#8F11A6'

    @apply_defaults
    def __init__(self,
                 table='',
                 sql_stmnt='',
                 redshift_conn_id='',
                 *args, **kwargs):

        super(DataQualityOperator, self).__init__(*args, **kwargs)
        self.table = table
        self.sql_stmnt = sql_stmnt
        self.redshift_conn_id = redshift_conn_id
        q_lowercase = ' '.join(self.sql_stmnt.lower().split())
        self.boolean = 'select exists' in q_lowercase or \
                       'select not exists' in q_lowercase

    def execute(self, context):
        self.log.info(f'Running check on table {self.table}')

        hook = PostgresHook(postgres_conn_id=self.redshift_conn_id)
        conn = hook.get_conn()
        cursor = conn.cursor()

        self.log.info(
            "Connected with connection '{}'".format(self.redshift_conn_id)
        )

        self.log.info(f'Running query:\n{self.sql_stmnt}')

        records = hook.get_records(self.sql_stmnt)
        if len(records) < 1 or len(records[0]) < 1:
            self.log.info(
                f'Data quality check failed. {self.table} returned no results'
            )
            raise ValueError(
                f'Data quality check failed. {self.table} returned no results'
            )
        output = records[0][0]
        if self.boolean:
            if output == 0:
                self.log.info(
                    f'Data quality check failed. {self.table} returned '
                    f'incorrect results'
                )
                raise ValueError(
                    f'Data quality check failed. {self.table} contained '
                    f'incorrect results'
                )
            self.log.info(
                f'Data quality check on table {self.table} passed.'
            )
        else:
            if output == 0:
                self.log.info(
                    f'Data quality check failed. {self.table} returned 0 rows'
                )
                raise ValueError(
                    f'Data quality check failed. {self.table} returned 0 rows'
                )
            self.log.info(
                f'Data quality check on table {self.table} passed '
                f'with {output} rows.'
            )

        cursor.close()


class DataQualityPlugin(AirflowPlugin):
    name = "data_quality_plugin"
    operators = [DataQualityOperator, ]
