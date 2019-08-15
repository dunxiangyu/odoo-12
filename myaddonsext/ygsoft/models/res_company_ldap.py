from odoo import api, fields, models
from ..tools.ldap import Ldap


class LdapSync(models.Model):
    _inherit = 'res.company.ldap'

    def _get_ldap_users(self, conf):
        attrs = ['sn', 'name', 'company', 'department', 'employeeID', 'mobile', 'mail', 'title',
                 'physicalDeliveryOfficeName']
        ldap = Ldap(conf['ldap_server'], conf['ldap_server_port'], conf['ldap_tls'])
        list = ldap.search(conf['ldap_binddn'], conf['ldap_password'], conf['ldap_base'], retrieve_attributes=attrs)
        return [item for item in list if item.get('company')]

    @api.multi
    def sync_employees(self):
        employeeModel = self.sudo().env['hr.employee']
        for conf in self:
            company_id = conf['company'].id
            list = self._get_ldap_users(conf)
            for item in list:
                self.get_or_create_employee(employeeModel, item, company_id)

    def get_or_create_employee(self, model, value, company_id):
        user = {
            'name': value.get('name', False),
            'work_email': value.get('mail', False),
            'mobile_phone': value.get('mobile', False),
            'work_location': value.get('physicalDeliveryOfficeName', False),
            'job_title': value.get('title', False)
        }
        rs = model.search_read([('company_id', '=', company_id), ('work_email', '=', user['work_email'])],
                               user.keys())
        if len(rs) == 0:
            user['company_id'] = company_id
            rec = model.create(user)
            print('%s %s' % (rec.id, user))
        else:
            user2 = rs[0]
            del user2['id']
            if user2 != user:
                rs.write(user)
                print('%s %s' % (rs[0].id, user))

    @api.multi
    def sync_users(self):
        pass
