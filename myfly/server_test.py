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
        super(ModelTest, cls).setUpClass()


class HttpCase(common.HttpCase):
    @classmethod
    def setUpClass(cls):
        super(HttpCase, cls).setUpClass()

    def setUp(self):
        super(HttpCase, self).setUp()
        self.db = common.get_db_name()
        self.uid = self.env.ref('base.user_admin').id
        self.password = 'admin'

    def execute(self, model, method, params, kwargs):
        return self.xmlrpc_object.execute(self.db, self.uid, self.password,
                                          model, method, params, kwargs)
