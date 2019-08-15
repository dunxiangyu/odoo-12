import unittest
from smb.SMBConnection import SMBConnection
from nmb.NetBIOS import NetBIOS

def getBIOSName(remote_smb_ip, timeout=30):
    try:
        bios = NetBIOS()
        srv_name = bios.queryIPForName(remote_smb_ip, timeout=timeout)
    except:
        print("Looking up timeout, check remote_smb_ip again!!")
    finally:
        bios.close()
        return srv_name


class TestSMB(unittest.TestCase):
    def download_file(self, conn, remote_file, local_file):
        file_obj = open(local_file, 'wb')  # 保存到本地的路径和文件名
        conn.retrieveFile('root', remote_file, file_obj)  # 获取smb服务器上的文件名字
        file_obj.close()

    def test_get_bios(self):
        result = getBIOSName('192.168.3.10')
        print(result)

    def test_connect_ygsoft(self):
        conn = SMBConnection('anonymous', '', 'my_name', 'remote_name', use_ntlm_v2=True, is_direct_tcp=False)
        conn.connect('192.168.0.88', 445)
        sharelist = conn.listShares()
        for item in sharelist:
            print(item)

    def test_connect_local(self):
        conn = SMBConnection('xiangwanhong', 'xyc20171113', '', '', use_ntlm_v2=True,
                             is_direct_tcp=False, sign_options=SMBConnection.SIGN_NEVER)
        conn.connect('127.0.0.1', 445, timeout=600)
        sharelist = conn.listShares()
        for item in sharelist:
            print(item)
