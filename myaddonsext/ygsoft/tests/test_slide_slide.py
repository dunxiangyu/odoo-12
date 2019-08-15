from odoo.tests import common


class TestSlide(common.TransactionCase):
    def setUp(self):
        super(TestSlide, self).setUp()
        self.model = self.env['slide.slide']

    def test_list(self):
        rs = self.model.search_read([], ['name'])
        for row in rs:
            print(row)
