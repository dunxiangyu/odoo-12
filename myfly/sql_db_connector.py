import psycopg2
import mysql.connector
from werkzeug import urls

def connection_info_for(uri):
    """

    :param uri:
    :return:
    """
    us = urls.url_parse(uri)
    if len(us.path) > 1:
        db_name = us.path[1:]
    elif us.username:
        db_name = us.username
    else:
        db_name = us.hostname
    if uri.startswith('mysql'):
        type = 'mysql'
    elif uri.startswith('oracle'):
        type = 'oracle'
    else:
        type = 'postgresql'
    connection_info = {}
    connection_info['database'] = db_name
    connection_info['host'] = us.host
    connection_info['port'] = us.port
    connection_info['user'] = us.username
    connection_info['password'] = us.password
    return type, connection_info


def db_connect(uri):
    """

    :param uri:
    :return:
    """
    type, connection_info = connection_info_for(uri)

    if type == 'mysql':
        conn = mysql.connector.connect(**connection_info)
    elif type == 'oracle':
        conn = None
    else:
        conn = psycopg2.connect(**connection_info)
    return conn





