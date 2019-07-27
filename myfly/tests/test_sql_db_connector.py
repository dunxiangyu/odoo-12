from myfly.sql_db_connector import db_connect, connection_info_for
import unittest


class TestSqlDbConnector(unittest.TestCase):
    db_system1 = 'postgresql://odoo:odoo@localhost:5432/odoo-12'
    db_system2 = 'mysql://odoo:odoo@localhost:3306/odoo-12'
    db_system3 = 'oracle://odoo:odoo@localhost:1521/odoo-12'

    def test_connection_info_for_postgresql(self):
        uri = 'postgresql://odoo:odoo@localhost:5432/odoo-12'
        type, connection_info = connection_info_for(uri)
        self.assertEqual('postgresql', type)
        self.assertEqual('localhost', connection_info['host'])
        self.assertEqual(5432, connection_info['port'])
        self.assertEqual('odoo', connection_info['user'])
        self.assertEqual('odoo', connection_info['password'])
        self.assertEqual('odoo-12', connection_info['database'])

    def test_connection_info_for_mysql(self):
        uri = 'mysql://odoo:odoo@localhost:3306/odoo-12'
        type, connection_info = connection_info_for(uri)
        self.assertEqual('mysql', type)
        self.assertEqual('localhost', connection_info['host'])
        self.assertEqual(3306, connection_info['port'])
        self.assertEqual('odoo', connection_info['user'])
        self.assertEqual('odoo', connection_info['password'])
        self.assertEqual('odoo-12', connection_info['database'])

    def test_connection_info_for_oracle(self):
        uri = 'oracle://odoo:odoo@localhost:1521/odoo-12'
        type, connection_info = connection_info_for(uri)
        self.assertEqual('oracle', type)
        self.assertEqual('localhost', connection_info['host'])
        self.assertEqual(1521, connection_info['port'])
        self.assertEqual('odoo', connection_info['user'])
        self.assertEqual('odoo', connection_info['password'])
        self.assertEqual('odoo-12', connection_info['database'])

    def test_postgresql(self):
        conn = db_connect(self.db_system1)
        cursor = conn.cursor()
        cursor.execute('show all')
        rs = cursor.fetchall()
        for row in rs:
            print(row)
        cursor.close()
        conn.close()

    def test_mysql(self):
        conn = db_connect(self.db_system2)
        cursor = conn.cursor()
        cursor.execute('show all')
        rs = cursor.fetchall()
        for row in rs:
            print(row)
        cursor.close()
        conn.close()
