import unittest
from ..models import utils


class TestUtils(unittest.TestCase):
    def test_get_file_info(self):
        fullpath = '/etc/odoo.conf'
        fileinfo = utils.get_file_info('/etc', fullpath)
        print(fileinfo)
        self.assertEqual(fullpath, fileinfo['fullpath'])
        self.assertEqual('.conf', fileinfo['file_ext'])
        self.assertEqual('odoo.conf', fileinfo['file_name'])
        self.assertEqual('odoo', fileinfo['name'])
        self.assertTrue(fileinfo['file_size'] > 0)

    def test_get_file_info_code(self):
        rootpath = '/xwh.work/git/odoo-12/myaddonsext'
        fileinfo = utils.get_file_info(rootpath,
                                       rootpath + '/xwh_dms_fetch/tests/test_utils.py')
        print(fileinfo)
        self.assertEqual('test_utils', fileinfo['name'])
        self.assertEqual('test_utils.py', fileinfo['file_name'])
        self.assertEqual('xwh_dms_fetch/tests', fileinfo['file_path'])
        self.assertEqual('.py', fileinfo['file_ext'])
        self.assertEqual(rootpath + '/xwh_dms_fetch/tests/test_utils.py', fileinfo['fullpath'])
        self.assertTrue(fileinfo['file_size'] > 0)

    def test_getPdfContent(self):
        file = 'xwh_dms_fetch/tests/docs/国家电网智能化规划总报告-4-4.pdf'
        content = utils.getPdfContent(file)
        print(content)

    def test_copydict(self):
        vals1 = {
            'name': 'name',
            'code': 'code'
        }
        name_map = {
            'name': 'name_new',
        }
        vals2 = dict(
            (name if not name_map.get(name) else name_map.get(name), vals1[name]) for name in ['name', 'code'] if
            vals1.get(name))
        print(vals2)
        vals3 = dict((name_map.get(name) or name, vals1[name]) for name in ['name', 'code'])
        print(vals3)
