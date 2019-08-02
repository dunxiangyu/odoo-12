from myfly import server_test


class TestUsers(server_test.ModelTest):
    def setUp(self):
        super(TestUsers, self).setUp()
        self.Model = self.env['res.users']

    def test_browse(self):
        rs = self.Model.browse([1]).read()
        self.assertIsNotNone(rs)

    def test_exists(self):
        self.Model.browse([1]).exists()

    def test_search(self):
        ids = self.Model.search([])
        self.assertIsNotNone(ids)

    def test_read(self):
        ids = self.Model.search([])
        rs = ids.read()
        self.assertIsNotNone(rs)
        rs = self.Model.search_read([])
        self.assertEqual(len(ids), len(rs))
        count = self.Model.search_count([])
        self.assertEqual(len(ids), count)

    def test_write(self):
        self.Model.browse([2]).write({
            'id': 2,
            'value': 123
        })

    def test_fields(self):
        names = self.Model._fields.keys()
        self.assertTrue(len(names))
        rs = self.Model.search_read(fields=names)
        self.assertTrue(len(rs))

    def test_export(self):
        rs = self.Model.search([]).export_data(self.Model._fields.keys())
        self.assertIsNotNone(rs)

    def test_read_group(self):
        rs = self.Model.read_group(domain=[], fields=['name'], groupby=['company_id'])
        self.assertIsNotNone(rs)
