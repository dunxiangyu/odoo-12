from odoo.tests import common


class TestLdapSync(common.TransactionCase):
    def setUp(self):
        super(TestLdapSync, self).setUp()
        self.Model = self.env['res.company.ldap']

    def test_sync_employee(self):
        self.Model.search([]).sync_employees()
