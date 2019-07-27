import unittest
from myfly.sql_db import db_connect, close_db, Connection


class TestSqlDB(unittest.TestCase):
    def test_db_connect_pgsql(self):
        url = 'postgresql://odoo:odoo@localhost:5432/odoo-12?sslmode=prefer'
        conn = db_connect(url, allow_uri=True)
        self.assertIsNotNone(conn)
        cursor = conn.cursor()
        self.assertIsNotNone(cursor)
        cursor.execute('show all')
        result = cursor.fetchone()
        self.assertIsNotNone(result)
        cursor.close()

    def test_a(self):
        url = 'postgresql://odoo:odoo@localhost:5432/odoo-12?sslmode=prefer'
        conn = db_connect(url, True)
        self.assertIsNotNone(conn)
        cursor = conn.cursor()
        self.assertIsNotNone(cursor)
        cursor.execute('show all')
        rs = cursor.dictfetchone()
        self.assertIsNotNone(rs)
        for row in rs:
            print(row)
        rs = cursor.dictfetchall()
        self.assertIsNotNone(rs)
        for row in rs:
            print(row)
        cursor.close()
        close_db(url)
