import unittest
import mysql.connector
from myfly.sql_db import connection_info_for, close_db


class TestMysql(unittest.TestCase):
    def get_connection(self):
        url = 'mysql://odoo:odoo@localhost:3326/odoo-12'
        db_name, connection_info = connection_info_for(url)
        conn = mysql.connector.connect(**connection_info)
        self.assertIsNotNone(conn)
        return conn

    def test_connect(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        self.assertIsNotNone(cursor)
        cursor.execute('show all')
        rs = cursor.fetchall()
        self.assertIsNotNone(rs)
        for row in rs:
            print(row)
        rs.close()
        conn.close()
