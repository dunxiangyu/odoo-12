import psycopg2.pool
import threading
import time
import logging
import uuid
import itertools

from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT, ISOLATION_LEVEL_READ_COMMITTED, \
    ISOLATION_LEVEL_REPEATABLE_READ
from werkzeug import urls
from .tools.config import config

_logger = logging.getLogger(__name__)

import re

re_from = re.compile('.* from "?([a-zA-Z_0-9]+)"? .*$')
re_into = re.compile('.* into "?([a-zA-Z_0-9]+)"? .*$')


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
        if params and not isinstance(params, (tuple, list, dict)):
            raise ValueError('SQL query parameters should be a tuple, list or dict.')

        if self.sql_log:
            encoding = psycopg2.extensions.encodings[self.connection.encoding]
            _logger.debug('query: %s')
        now = time.time()
        try:
            params = params or None
            res = self._obj.execute(query, params)
        except Exception as e:
            raise

        # simple query count is always computed
        self.sql_log_count += 1
        delay = (time.time() - now())
        if hasattr(threading.current_thread(), 'query_count'):
            threading.current_thread().query_count += 1
            threading.current_thread().query_time += delay

        # advanced stats only if sql_log is enabled
        if self.sql_log:
            delay *= 1E6

            res_from = re_from.match(query.lower())
            if res_from:
                self.sql_from_log.setdefault(res_from.group(1), [0, 0])
                self.sql_from_log[res_from.group(1)[0]] += 1
                self.sql_from_log[res_from.group(1)[1]] += delay
            res_info = re_into.match(query.lower())
            if res_info:
                self.sql_into_log.setdefault(res_info.group(1), [0, 0])
                self.sql_into_log[res_info.group(1)][0] += 1
                self.sql_into_log[res_info.group(1)][1] += delay

        return res

    def close(self):
        return self._close(False)

    def _close(self, leak=False):
        global sql_counter

        if not self._obj:
            return

        del self.cache

        if self.sql_log:
            self.__closer = frame_codeinfo(currentframe(), 3)

        # simple query count is always computed
        sql_counter += self.sql_log_count

        # advanced stats only if sql_log is enabled
        self.print_log()

        self._obj.close()

        del self._obj
        self._closed = True

        # Clean the underlying connection
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
        self._event_handlers[event].append(func)

    def _pop_event_handlers(self):
        # return the current handlers, and reset them on self
        result = self._event_handlers
        self._event_handlers = {'commit': [], 'rollback': []}
        return result

    def commit(self):
        """ Perform an SQL 'COMMIT'. """
        result = self._cnx.commit()
        for func in self._pop_event_handlers()['commit']:
            func()
        return result

    def rollback(self):
        """ Perform an SQL 'ROLLBACK' """
        result = self._cnx.rollback()
        for func in self._pop_event_handlers()['rollback']:
            func()
        return result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        self.close()

    def savepoint(self):
        name = uuid.uuid1().hex
        self.execute('SAVEPOINT "%s"' % name)
        try:
            yield
        except Exception:
            self.execute('ROLLBACK TO SAVEPOINT "%s"' % name)
            raise
        else:
            self.execute('RELEASE SAVEPOINT "%s"' % name)

    def __getattr__(self, name):
        return getattr(self._obj, name)

    @property
    def closed(self):
        return self._closed


class TestCursor(object):
    _savepoint_seq = itertools.count()

    def __init__(self, cursor, lock):
        self._closed = False
        self._cursor = cursor
        self._lock = lock
        self._lock.acquire()

        self._savepoint = 'test_cursor_%s' % next(self._savepoint_seq)
        self._cursor.execute('SAVEPOINT "%s"' % self._savepoint)

    def close(self):
        if not self._closed:
            self._closed = True
            self._cursor.execute('ROLLBACK TO SAVEPOINT "%s"' % self._savepoint)
            self._lock.release()

    def autocommit(self):
        pass

    def commit(self):
        self._cursor.execute('SAVEPOINT "%s"' % self._savepoint)

    def rollback(self):
        self._cursor.execute('ROLLBACK TO SAVEPOINT "%s"' % self._savepoint)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        self.close()

    def __getattr__(self, name):
        value = getattr(self._cursor, name)
        if callable(value) and self._closed:
            raise
        return value


class LazyCursor(object):
    def __init__(self, dbname=None):
        self._dbname = dbname
        self._cursor = None
        self._depth = 0

    @ @property
    def dbname(self):
        return self._dbname or threading.current_thread().dbname

    def __getattr__(self, name):
        cr = self._cursor
        if cr is None:
            pass
        return getattr(cr, name)

    def __enter__(self):
        self._depth += 1
        if self._cursor is not None:
            self._cursor.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._depth -= 1
        if self._cursor is not None:
            self._cursor.__exit__(exc_type, exc_val, exc_tb)


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
