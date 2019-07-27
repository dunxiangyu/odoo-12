import unittest
from ..sql_db import *


class TestSQLDB(unittest.TestCase):
    def test_cursor(self):
        con = db_connect('odoo-12')
        cursor = con.cursor()
        res = cursor.execute('show all')
        self.assertIsNotNone(res)
        cursor.close()
