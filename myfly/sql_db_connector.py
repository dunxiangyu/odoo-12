import psycopg2
import mysql.connector
from werkzeug import urls
from odoo.tools import config

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


def get_connection(uri):
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


db_config = {}


def get_db_config(db_name):
    global db_config
    if not hasattr(db_config, db_name):
        if db_name.startswith('ext_'):
            uri = config.get_misc('db_ext', db_name[4:])
            type, connection_info = connection_info_for(uri)
            db_config[db_name] = {
                'type': type,
                'uri': uri,
                'connection_info': connection_info
            }
        else:
            connection_info = {'database': db_name}
            for p in ('host', 'port', 'user', 'password', 'sslmode'):
                cfg = config['db_' + p]
                if cfg:
                    connection_info[p] = cfg
            db_config[db_name] = {
                'type': 'postgresql',
                'connection_info': connection_info
            }
    return db_config[db_name]


def is_postgresql(db_name):
    config = get_db_config(db_name)
    return config['type'] == 'postgresql'


def get_db_connection(db_name):
    db_config = get_db_config(db_name)
    connection_info = db_config['connection_info']
    type = db_config['type']
    if type == 'mysql':
        conn = mysql.connector.connect(**connection_info)
    elif type == 'oracle':
        conn = None
    else:
        from odoo.sql_db import PsycoConnection
        conn = psycopg2.connect(connection_factory=PsycoConnection, **connection_info)
    return conn
