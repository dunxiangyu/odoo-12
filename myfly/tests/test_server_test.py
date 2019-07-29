from .. import server_test


class TestServerTest(server_test.ModelTest):
    # def test_server_start(self):
    #     server_test.start_server()

    def test_init(self):
        rs = self.env['res.users'].search([])
        for row in rs:
            print(row)
