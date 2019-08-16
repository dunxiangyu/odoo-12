import unittest
from ..models import utils


class TestUtils(unittest.TestCase):
    def test_get_file_info(self):
        fullpath = '/etc/odoo.conf'
        fileinfo = utils.get_file_info('/etc', fullpath)
        print(fileinfo)
        self.assertEqual(fullpath, fileinfo['fullpath'])
        self.assertEqual('conf', fileinfo['file_ext'])
        self.assertEqual('/odoo', fileinfo['file_name'])
        self.assertEqual('odoo', fileinfo['name'])

    def test_get_file_info_code(self):
        rootpath = '/xwh.work/git/odoo-12/myaddonsext'
        fileinfo = utils.get_file_info(rootpath,
                                       rootpath + '/netfetch/tests/test_utils.py')
        print(fileinfo)
