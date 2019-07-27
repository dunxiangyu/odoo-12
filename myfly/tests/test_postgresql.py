import psycopg2
from psycopg2.extensions import *
import unittest
from myfly.sql_db import connection_info_for, PsycoConnection


class TestPostgresql(unittest.TestCase):
    def test_connection_info(self):
        url = 'postgresql://odoo:odoo@localhost:5432/odoo-12?sslmode=prefer'
        db_name, connection_info = connection_info_for(url)
        self.assertEqual('odoo', connection_info['user'])
        self.assertEqual('odoo', connection_info['password'])
        self.assertEqual('odoo-12', connection_info['database'])
        self.assertEqual('localhost', connection_info['host'])
        self.assertEqual(5432, connection_info['port'])
        return db_name, connection_info

    def get_connection(self):
        db_name, connection_info = self.test_connection_info()
        return psycopg2.connect(connection_factory=PsycoConnection, **connection_info)

    def test_connect(self):
        result = self.get_connection()
        self.assertIsNotNone(result)
        result.close()

    def test_autocommit(self):
        isolation_level = ISOLATION_LEVEL_REPEATABLE_READ
        result = self.get_connection()
        result.set_isolation_level(isolation_level)
        self.assertEqual(ISOLATION_LEVEL_REPEATABLE_READ, result.isolation_level)
        result.close()
        isolation_level = ISOLATION_LEVEL_READ_COMMITTED
        result = self.get_connection()
        result.set_isolation_level(isolation_level)
        self.assertEqual(ISOLATION_LEVEL_READ_COMMITTED, result.isolation_level)
        result.close()

    def test_cursor_sql(self):
        connection = self.get_connection()
        cursor = connection.cursor()
        self.assertIsNotNone(cursor)
        cursor.execute('show all')
        result = cursor.fetchall()
        for row in result:
            print(row)
        cursor.close()
        connection.close()
