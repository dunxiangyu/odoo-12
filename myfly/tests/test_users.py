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

    def test_write(self):
        self.Model.browse([2]).write({
            'id': 2,
            'value': 123
        })
