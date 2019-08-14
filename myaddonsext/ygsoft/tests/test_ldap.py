import unittest
import ldap

conf = {
    'ldap_server': 'ad.ygsoft.com',
    'ldap_server_port': 389,
    'ldap_tls': False,
    'ldap_password': 'mKGIQywIDJYR7Qzv',
    'ldap_binddn': 'cn=xiangwanhong,ou=Senior Manager,ou=ZhuHai,ou=ygsoft,ou=CorpUsers,dc=ygsoft,dc=com',
    'ldap_base': 'ou=corpusers,dc=ygsoft,dc=com',
    'ldap_filter': '(objectclass=*)'
}


class TestLdap(unittest.TestCase):
    def get_connection(self):
        uri = 'ldap://%s:%d' % (conf['ldap_server'], conf['ldap_server_port'])

        connection = ldap.initialize(uri)
        if conf['ldap_tls']:
            connection.start_tls_s()
        return connection

    def test_connect(self):
        conn = self.get_connection()
        ldap_password = conf['ldap_password'] or ''
        ldap_binddn = conf['ldap_binddn'] or ''
        conn.simple_bind_s(ldap_binddn, ldap_password)
        retrieve_attributes = ['cn', 'mail']
        results = conn.search_st(conf['ldap_base'], ldap.SCOPE_SUBTREE, conf['ldap_filter'], retrieve_attributes,
                                 timeout=60)
        conn.unbind()
