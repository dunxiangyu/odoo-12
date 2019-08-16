from odoo.tests import common


class TestNetFetchConfig(common.TransactionCase):
    def setUp(self):
        super(TestNetFetchConfig, self).setUp()
        self.model = self.env['netfetch.config']

    def test_fetch_local(self):
        self.model.search([('type', '=', 'local')]).fetch()
