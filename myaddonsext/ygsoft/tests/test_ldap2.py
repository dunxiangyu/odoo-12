import unittest
from ..tools.ldap import Ldap

conf = {
    'ldap_server': 'ad.ygsoft.com',
    'ldap_server_port': 389,
    'ldap_tls': False,
    'ldap_password': 'mKGIQywIDJYR7Qzv',
    'ldap_binddn': 'sync_ldap@ygsoft.com',
    'ldap_base': 'ou=corpusers,dc=ygsoft,dc=com',
    'ldap_filter': '(objectclass=*)'
}


class TestLdap(unittest.TestCase):
    ldap = Ldap(conf['ldap_server'], conf['ldap_server_port'], conf['ldap_tls'])

    def test_auth(self):
        self.ldap.auth('xiangwanhong@ygsoft.com', 'XwhSoft0')

    def test_search(self):
        attrs = ['sn', 'name', 'company', 'department', 'employeeID', 'mobile', 'mail', 'title',
                 'physicalDeliveryOfficeName']
        result = self.ldap.search(conf['ldap_binddn'], conf['ldap_password'], conf['ldap_base'],
                                  retrieve_attributes=attrs)
        for item in [item for item in result if item.get('company') and item.get('mail')]:
            print(item)

    def test_search_xiangwanhong(self):
        attrs = ['sn', 'name', 'company', 'department', 'employeeID', 'mobile', 'mail', 'title',
                 'physicalDeliveryOfficeName']
        result = self.ldap.search(conf['ldap_binddn'], conf['ldap_password'], conf['ldap_base'],
                                  '(mail=xiangwanhong@ygsoft.com)', retrieve_attributes=[])
        print(result)
