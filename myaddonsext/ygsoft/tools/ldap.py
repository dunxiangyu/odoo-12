import ldap


class Ldap():
    def __init__(self, server, port, tls):
        self.server = server
        self.port = port
        self.tls = tls

    def _get_connection(self):
        uri = 'ldap://%s:%d' % (self.server, self.port)

        connection = ldap.initialize(uri)
        if self.tls:
            connection.start_tls_s()
        return connection

    def to_map(self, entry):
        result = {
            #'CN': entry[0]
        }
        for attr in entry[1]:
            try:
                result[attr] = str(entry[1][attr][0], 'utf-8')
            except:
                pass
        return result

    def auth(self, user, passwd):
        conn = self._get_connection()
        result = conn.simple_bind_s(user, passwd)
        conn.unbind()
        return result[0] == 97

    def search(self, admin, admin_passwd, base, filter='(objectclass=*)', retrieve_attributes=[]):
        conn = self._get_connection()
        conn.simple_bind_s(admin, admin_passwd)
        result = conn.search_st(base, ldap.SCOPE_SUBTREE, filter, retrieve_attributes)
        list = []
        for item in result:
            list.append(self.to_map(item))
        conn.unbind()
        return list
