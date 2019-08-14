import unittest
from smb.SMBConnection import SMBConnection
import smbclient


class TestSMB(unittest.TestCase):
    def test_connect(self):
        conn = SMBConnection('anonymous', '', 'my_name', 'remote_name', domain='ygsoft.com')
        conn.connect('192.168.0.88', 445)
        sharelist = conn.listShares()
        for item in sharelist:
            print(item)

        # file_obj = open('F:/samba/123.c', 'wb') #保存到本地的路径和文件名
        # filesize = conn.retrieveFile('root', '/123.c', file_obj) #获取smb服务器上的文件名字
        # file_obj.close()

    def test_smbclient(self):
        smb = smbclient.SambaClient(server='192.168.0.88',share='产品和技术委员会')
        for item in smb.listdir('/'):
            print(item)