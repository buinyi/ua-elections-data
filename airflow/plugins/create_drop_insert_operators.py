from airflow.hooks.postgres_hook import PostgresHook
from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from airflow.plugins_manager import AirflowPlugin

stopwords = {'create', 'temporary', 'table', 'if', 'not', 'exists'}


class GeneralSqlOperatorTemplate(BaseOperator):
    """
    Implements a template for creating SQL operator classes.

    Parameters:
        sql_stmnt: sql that generates the data to be uploaded into table
        redshift_conn_id: redshift connection id
        stopwords: possible first words of the sql statement before
        the table name
        messages: dictionary with messages logged during the execution
        of the operator
    """

    @apply_defaults
    def __init__(self,
                 sql_stmnt='',
                 redshift_conn_id='',
                 stopwords={},
                 messages=dict(),
                 *args, **kwargs):

        super(GeneralSqlOperatorTemplate, self).__init__(*args, **kwargs)
        self.sql_stmnt = sql_stmnt
        self.redshift_conn_id = redshift_conn_id
        self.messages = messages
        if not stopwords:
            self.table = ''
        else:
            words = self.sql_stmnt.lower().split()
            for w in words:
                if w not in stopwords:
                    self.table = w
                    break
            else:
                self.table = ''

    def execute(self, context):
        self.log.info(f'{self.messages["start"]} {self.table}')

        hook = PostgresHook(postgres_conn_id=self.redshift_conn_id)
        conn = hook.get_conn()
        cursor = conn.cursor()

        self.log.info(
            "Connected with connection '{}'".format(self.redshift_conn_id)
        )

        self.log.info(f'Running query:\n{self.sql_stmnt}')

        cursor.execute(self.sql_stmnt)
        cursor.close()
        conn.commit()
        self.log.info(f'{self.messages["end"]}')


class CreateTableOperator(GeneralSqlOperatorTemplate):
    """
    Implements CreateTableOperator class.

    Parameters:
        sql_stmnt: sql that generates the data to be uploaded into table
        redshift_conn_id: redshift connection id
        stopwords: possible first words of the sql statement before
        the table name
        messages: dictionary with messages logged during the execution
        of the operator
    """
    ui_color = '#F98866'

    @apply_defaults
    def __init__(self,
                 sql_stmnt='',
                 redshift_conn_id='',
                 stopwords={
                     'create', 'temporary', 'table', 'if', 'not', 'exists'
                 },
                 messages={
                     'start': 'Creating table',
                     'end': 'CREATE command has run succesfully'
                 },
                 *args, **kwargs):
        super(CreateTableOperator, self).__init__(
            sql_stmnt=sql_stmnt, stopwords=stopwords,
            messages=messages, *args, **kwargs
        )


class DropTableOperator(GeneralSqlOperatorTemplate):
    """
    Implements DropTableOperator class.

    Parameters:
        sql_stmnt: sql that generates the data to be uploaded into table
        redshift_conn_id: redshift connection id
        stopwords: possible first words of the sql statement before
        the table name
        messages: dictionary with messages logged during the execution
        of the operator
    """
    ui_color = '#94CC12'

    @apply_defaults
    def __init__(self,
                 sql_stmnt='',
                 redshift_conn_id='',
                 stopwords={'drop', 'table', 'if', 'exists'},
                 messages={'start': 'Dropping table',
                           'end': 'DROP command has run succesfully'},
                 *args, **kwargs):
        super(DropTableOperator, self).__init__(
            sql_stmnt=sql_stmnt, stopwords=stopwords,
            messages=messages, *args, **kwargs
        )


class InsertOperator(GeneralSqlOperatorTemplate):
    """
    Implements InsertOperator class.

    Parameters:
        sql_stmnt: sql that generates the data to be uploaded into table
        redshift_conn_id: redshift connection id
        stopwords: possible first words of the sql statement before
        the table name
        messages: dictionary with messages logged during the execution
        of the operator
    """
    ui_color = '#2453ED'

    @apply_defaults
    def __init__(self,
                 sql_stmnt='',
                 redshift_conn_id='',
                 stopwords={'insert', 'into'},
                 messages={'start': 'Inserting into table',
                           'end': 'INSERT command has run succesfully'},
                 *args, **kwargs):
        super(InsertOperator, self).__init__(
            sql_stmnt=sql_stmnt, stopwords=stopwords,
            messages=messages, *args, **kwargs
        )


class ElectionsPlugin(AirflowPlugin):
    name = "create_drop_insert_plugin"
    operators = [CreateTableOperator, DropTableOperator, InsertOperator]
