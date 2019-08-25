from odoo.tests import common


class TestDirectory(common.TransactionCase):
    def test_get_or_create_directory(self):
        model = self.env['xwh_dms.directory']
        directory_id = model.get_or_create_directory(None, '需求')
        self.assertTrue(directory_id > 0)

    def test_get_or_create_directories(self):
        model = self.env['xwh_dms.directory']
        directory_id = model.get_or_create_directories(None, 'tests')
        self.assertTrue(directory_id > 0)

    def test_get_or_create_directories_2(self):
        model = self.env['xwh_dms.directory']
        directory_id = model.get_or_create_directories(None, 'tests/a')
        self.assertTrue(directory_id > 0)

    def test_get_or_create_directories_3(self):
        model = self.env['xwh_dms.directory']
        directory_id = model.get_or_create_directories(None, 'tests/a/b')
        self.assertTrue(directory_id > 0)
