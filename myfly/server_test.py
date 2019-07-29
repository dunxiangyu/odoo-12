from odoo.tools import config
from odoo.service import server
from odoo.tests import common

_server_started = False


def start_server():
    global _server_started
    if not _server_started:
        config.parse_config(['--log-sql'])
        server.load_server_wide_modules()
        preload = [config.get('db_name')]
        server.preload_registries(preload)
        _server_started = True


class ModelTest(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        start_server()
        super(ModelTest, cls).setUpClass()
