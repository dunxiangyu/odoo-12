from myfly import server_test


class TestXtgldxlx(server_test.ModelTest):
    def setUp(self):
        super(TestXtgldxlx, self).setUp()
        self.Model = self.env['cwgk.xtgldxlx']

    def test_default_get(self):
        value = self.Model.default_get(['id', 'dxlxid', 'name', 'value'])
        self.assertIsNotNone(value)

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

    def test_create(self):
        rec = self.Model.create({
            'id': 3,
            'dxlxid': '2001',
            'name': 'test lx',
            'value': '12'
        })
        self.assertIsNotNone(rec)

    def test_write(self):
        self.Model.browse([2]).write({
            'id': 2,
            'value': 123
        })
