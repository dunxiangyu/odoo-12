import psycopg2.pool
import threading
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT, ISOLATION_LEVEL_READ_COMMITTED, \
    ISOLATION_LEVEL_REPEATABLE_READ
from werkzeug import urls
from .tools.config import config


class Cursor(object):
    def __init__(self, pool, dbname, dsn, serialized=True):
        self.sql_from_log = {}
        self.sql_into_log = {}

        self.sql_log = None
        self.sql_log_count = 0

        self._closed = True

        self.__pool = pool
        self.dbname = dbname

        self._serialized = serialized

        self._cnx = pool.borrow(dsn)
        self._obj = self._cnx.cursor()
        self._closed = False
        self.autocommit(False)
        self.__cursor = False

        self._default_log_exceptions = True

        self.cache = {}

        self._event_handlers = {'commit': [], 'rollback': {}}

    def execute(self, query, params=None, log_exceptions=None):
        try:
            params = params or None
            res = self._obj.execute(query, params)
        except Exception as e:
            raise

        return res

    def close(self):
        return self._close(False)

    def _close(self, leak=False):
        if not self._obj:
            return
        self._obj.close()
        self._closed = True
        self._cnx.rollback()
        if leak:
            self._cnx.leadked = True
        else:
            keep_in_pool = self.dbname
            self.__pool.give_back(self._cnx, keep_in_pool=keep_in_pool)

    def autocommit(self, on):
        if on:
            isolation_level = ISOLATION_LEVEL_AUTOCOMMIT
        else:
            isolation_level = ISOLATION_LEVEL_REPEATABLE_READ \
                if self._serialized else ISOLATION_LEVEL_READ_COMMITTED
        self._cnx.set_isolation_level(isolation_level)

    def after(self, event, func):
        pass

    def commit(self):
        result = self._cnx.commit()
        return result

    def rollback(self):
        result = self._cnx.rollback()
        return result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        self.close()


class Connection(object):
    def __init__(self, pool, dbname, dsn):
        self.dbname = dbname
        self.dsn = dsn
        self.__pool = pool

    def cursor(self, serialized=True):
        cursor_type = serialized and 'serialized' or ''
        return Cursor(self.__pool, self.dbname, self.dsn, serialized=serialized)


class ConnectionPool(object):
    def __init__(self, maxconn=64):
        self._connections = []
        self._maxconn = max(maxconn, 1)
        self._lock = threading.Lock()

    def borrow(self, connection_info):
        try:
            result = psycopg2.connect(**connection_info)
        except psycopg2.Error:
            raise
        self._connections.append(result)
        return result

    def give_back(self, connection, keep_in_pool=True):
        for i, (cnx, used) in enumerate(self._connections):
            if cnx is connection:
                self._connections.pop(i)
                if keep_in_pool:
                    self._connections.append((cnx, False))
                else:
                    cnx.close()
                break

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
        try:
            cfg = config['db_' + p]
            if cfg:
                connection_info[p] = cfg
        except KeyError:
            continue

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
