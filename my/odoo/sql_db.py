import psycopg2.pool
from werkzeug import urls
from .tools import config

class Cursor(object):
    def __init__(self, pool, dbname, dsn, serialized=True):
        pass

class Connection(object):
    def __init__(self, pool, dbname, dsn):
        self.dbname = dbname
        self.dsn = dsn
        self.__pool = pool

    def cursor(self, serialized=True):
        pass


class ConnectionPool(object):
    def brrow(self, connection_info):
        pass

    def close_all(self, dsn=None):
        pass


def connection_info_for(db_or_uri):
    if db_or_uri.startswith(('postgresql://', 'postgres://')):
        us = urls.url_parse(db_or_uri)
        if len(us.path) > 1:
            db_name = us.path[1:]
        elif us.username:
            db_name = us.username
        else:
            db_name = us.hostname
        return db_name, {'dsn': db_or_uri}

    connection_info = {'database': db_or_uri}
    for p in ('host', 'port', 'user', 'password', 'sslmode'):
        cfg = config['db_' + p]
        if cfg:
            connection_info[p] = cfg

    return db_or_uri, connection_info

_Pool = None


def db_connect(to, allow_uri=False):
    global _Pool
    if _Pool is None:
        _Pool = ConnectionPool(50)

    db, info = connection_info_for(to)
    return Connection(_Pool, db, info)


def close_db(db_name):
    global _Pool
    if _Pool:
        _Pool.close_all(connection_info_for(db_name)[1])

def close_all():
    global _Pool
    if _Pool:
        _Pool.close_all()