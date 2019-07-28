from odoo.tools.config import configmanager
import unittest


class TestConfig(unittest.TestCase):
    def test_config(self):
        config = configmanager('../../odoo.conf')
        system1 = config.get_misc('db_ext', 'system1')
        self.assertIsNotNone(system1)
        system2 = config.get_misc('db_ext', 'system2')
        self.assertIsNotNone(system2)
