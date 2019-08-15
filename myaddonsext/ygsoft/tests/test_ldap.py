import unittest
import ldap

conf = {
    'ldap_server': 'ad.ygsoft.com',
    'ldap_server_port': 389,
    'ldap_tls': False,
    'ldap_password': 'mKGIQywIDJYR7Qzv',
    'ldap_binddn': 'sync_ldap@ygsoft.com',
    'ldap_base': 'ou=corpusers,dc=ygsoft,dc=com',
    'ldap_filter': '(objectclass=*)'
}


def to_str(value):
    return str(value, 'utf-8')


def to_map(ldap_entry):
    attrs = ldap_entry[1]
    return {
        'mail': to_str(attrs['mail'][0]),
        'displayName': to_str(attrs['displayName'][0]),
        'sAMAccountName': to_str(attrs['sAMAccountName'][0]),
    }


class TestLdap(unittest.TestCase):
    def get_connection(self):
        uri = 'ldap://%s:%d' % (conf['ldap_server'], conf['ldap_server_port'])

        connection = ldap.initialize(uri)
        if conf['ldap_tls']:
            connection.start_tls_s()
        return connection

    def bind(self, user, passwd):
        conn = self.get_connection()
        result = conn.simple_bind_s(user, passwd)
        self.assertEqual(97, result[0])

    def search(self, filter):
        conn = self.get_connection()
        ldap_password = conf['ldap_password'] or ''
        ldap_binddn = conf['ldap_binddn'] or ''
        conn.simple_bind_s(ldap_binddn, ldap_password)
        retrieve_attributes = ['cn', 'mail', 'displayName', 'sAMAccountName']
        results = conn.search_st(conf['ldap_base'], ldap.SCOPE_SUBTREE, filter, retrieve_attributes)
        return results

    def test_bind_ok(self):
        self.bind('xiangwanhong@ygsoft.com', 'XwhSoft0')

    def test_bind_pass_error(self):
        self.bind('xiangwanhong@ygsoft.com', 'error')

    def test_bind_user_error(self):
        self.bind('xiangwanhong', 'error')

    def test_search(self):
        conn = self.get_connection()
        ldap_password = conf['ldap_password'] or ''
        ldap_binddn = conf['ldap_binddn'] or ''
        conn.simple_bind_s(ldap_binddn, ldap_password)
        retrieve_attributes = ['cn', 'mail', 'displayName', 'sAMAccountName']
        results = conn.search_st(conf['ldap_base'], ldap.SCOPE_SUBTREE, conf['ldap_filter'], retrieve_attributes,
                                 timeout=60)
        for item in results:
            print(item)
        conn.unbind()

    def test_search_xiangwanhong(self):
        results = self.search('(sAMAccountName=xiangwanhong)')
        self.assertTrue(len(results))
        for item in results:
            print(to_map(item))

    def test_search_xiangwanhong_mail(self):
        results = self.search('(mail=xiangwanhong@ygsoft.com)')
        self.assertTrue(len(results))
        for item in results:
            print(to_map(item))
