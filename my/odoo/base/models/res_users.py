from collections import defaultdict
from odoo import models, fields


class Group(models.Model):
    _name = 'res.groups'
    _description = 'Access Groups'
    _rec_name = 'full_name'
    _order = 'name'

    name = fields.Char(required=True)
    users = fields.Many2many('res.users', 'res_group_users_rel', 'gid', 'uid')
    model_access = fields.One2many('ir.model.access', 'group_id')
    rule_groups = fields.Many2many('ir.rule', 'rule_group_rel', 'group_id',
                                   'rule_group_id', domain=[('global', '=', False)])
    menu_access = fields.Many2many('ir.ui.menu', 'ir_ui_menu_group_rel', 'gid', 'menu_id')
    view_access = fields.Many2many('ir.ui.view', 'ir_ui_view_group_rel', 'group_id', 'view_id')
    comment = fields.Text()
    category_id = fields.Many2one('ir.module.category')
    color = fields.Integer()
    full_name = fields.Char(compute='_compute_full_name')
    share = fields.Boolean()

    def _check_one_user_type(self):
        pass

    def _compute_full_name(self):
        pass

    def _search_full_name(self, operator, operand):
        lst = True
        if isinstance(operand, bool):
            domains = [[('name', operator, operand)], [('category_id.name', operator, operand)]]

    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        pass

    def copy(self, default=None):
        pass

    def write(self, vals):
        pass


class ResUserLog(models.Model):
    _name = 'res.users.log'
    _order = 'id desc'
    _description = 'Users Log'


class Users(models.Model):
    _name = 'res.users'
    _description = 'Users'
    _inherits = {'res.partner': 'partner_id'}
    _order = 'name, login'
    __uid_cache = defaultdict(dict)

    partner_id = fields.Many2one('res.partner')
    login = fields.Char()
    password = fields.Char(compute='_compute_password', inverse='_set_password',
                           copy=False, invisible=True)
    new_password = fields.Char(compute='_compute_password', inverse='_set_new_password')
    signature = fields.Html()
    active = fields.Boolean()
    active_partner = fields.Boolean(related='partner_id.active', readonly=True)
    action_id = fields.Many2one('ir.action.actions')
    groups_id = fields.Many2many('res.groups', 'res_groups_users_rel', 'uid', 'gid')
    log_ids = fields.One2many('res.users_log', 'create_uid')
    login_date = fields.Datetime(related='log_ids.create_date')
    share = fields.Boolean()
    companies_count = fields.Integer()
    tz_offset = fields.Char()

    company_id = fields.Many2one('res.company')
    company_ids = fields.Many2many('res.company', 'res_company_users_rel', 'user_id', 'cid')

    name = fields.Char(related='partner_id.name', inherited=True)
    email = fields.Char(related='partner_id.email', inherited=True)

    def _compute_password(self):
        for user in self:
            user.password = ''
            user.new_password = ''

    def _set_new_password(self):
        for user in self:
            if not user.new_password:
                continue
            if user == self.env.user:
                raise
            else:
                user.password = user.new_password

    def _compute_share(self):
        for user in self:
            user.share = not user.has_group('base.group_user')

    def _compute_companies_count(self):
        pass

    def on_change_login(self):
        pass

    def onchange_parent_id(self):
        pass


class ChangePasswordWizard(models.TransientModel):
    _name = 'change.password.wizard'
    _description = 'Change Password Wizard'

    user_ids = fields.One2many('change.password.user', 'wizard_id')

    def _default_user_ids(self):
        user_ids = self._context.get('active_model') == 'res.users' and \
                   self._context.get('active_ids') or []
        return [
            (0, 0, {'user_id': user.id, 'user_login': user.login})
            for user in self.env['res.users'].browse(user_ids)
        ]

    def change_password_button(self):
        self.ensure_one()
        self.user_ids.change_password_button()
        if self.env.user in self.mapped('user_ids.user_id'):
            return {'type': 'ir.action.client', 'tag': 'reload'}
        return {'type': 'ir.action.act_window_close'}


class ChangePasswordUsers(models.TransientModel):
    _name = 'change.password.user'
    _description = 'User, Change Password Wizards'

    wizard_id = fields.Many2one('change.password.wizard')
    user_id = fields.Many2one('res.users')
    user_login = fields.Char()
    new_passwd = fields.Char()

    def change_password_button(self):
        for line in self:
            if not line.new_passwd:
                raise
            line.user_id.write({'password': line.new_passwd})
        self.write({'new_passwd': False})
