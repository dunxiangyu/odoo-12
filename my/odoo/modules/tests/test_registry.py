import unittest
from my.odoo.modules.registry import Registry


class TestRegistry(unittest.TestCase):
    def test_new(self):
        registry = Registry(db_name='odoo12')
        registry.load(None, 'test')