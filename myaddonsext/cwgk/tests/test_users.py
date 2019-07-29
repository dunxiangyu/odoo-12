from myfly import server_test


class TestUsers(server_test.ModelTest):
    def test_users(self):
        self.Model = self.env['res.users']
        self.Model.search([])
