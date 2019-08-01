from myfly import server_test


class TestResUsers(server_test.HttpCase):
    def test_execute(self):
        ids = self.execute('res.users', 'search_read', [True, True, False],
                           {'domain': [('name', '=', 'admin')], 'fields': ['name'], 'limit': 80, 'offset': 0})
        self.assertTrue(len(ids) > 0)
        ids = self.execute('res.users', 'search_read')
        self.assertTrue(len(ids) == 3)
