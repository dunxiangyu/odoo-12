from collections import defaultdict
from odoo import models, fields, api
from odoo.osv import expression


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
        for group, group1 in pycompat.izip(self, self.sudo()):
            if group1.category_id:
                group.full_name = '%s / %s' % (group1.category_id.name, group1.name)
            else:
                group.full_name = group1.name

    def _search_full_name(self, operator, operand):
        lst = True
        if isinstance(operand, bool):
            domains = [[('name', operator, operand)], [('category_id.name', operator, operand)]]
            if operator in expression.NEGATIVE_TERM_OPERATORS == (not operand):
                return expression.AND(domains)
            else:
                return expression.OR(domains)
        if isinstance(operand, pycompat.string_types):
            lst = False
            operand = [operand]
        where = []
        for group in operand:
            values = [v for v in group.split('/') if v]
            group_name = values.pop().strip()
            category_name = values and '/'.join(values).strip() or group_name
            group_domain = [('name', operator, lst and [group_name] or group_name)]
            category_domain = [('category_id.name', operator, lst and [category_name] or category_name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS and not values:
                category_domain = expression.OR([category_domain, [('category_id', '=', False)]])
            if (operator in expression.NEGATIVE_TERM_OPERATORS) == (not values):
                sub_where = expression.AND([group_domain, category_domain])
            else:
                sub_where = expression.OR([group_domain, category_domain])
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                where = expression.AND([where, sub_where])
            else:
                where = expression.OR([where, sub_where])
        return where

    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if order and order.startswith('full_name'):
            groups = super(Group, self).search(args)
            groups = groups.sorted('full_name', reverse=order.endswith('DESC'))
            groups = groups[offset:offset + limit] if limit else groups[offset:]
            return len(groups) if count else groups.ids
        return super(Group, self)._search(args, offset=offset, limit=limit, order=order,
                                          count=count, access_rights_uid=access_rights_uid)

    @api.multi
    def copy(self, default=None):
        self.ensure_one()
        chosen_name = default.get('name') if default else ''
        default_name = chosen_name or '%s (coopy)' % self.name
        default = dict(default or {}, name=default_name)
        return super(Group, self).copy(default)

    @api.multi
    def write(self, vals):
        if 'name' in vals:
            if vals['name'].startswith('-'):
                raise
        self.env['ir.model.access'].call_cache_clearing_methods()
        self.env['res.users'].has_group.clear_cache(self.env['res.users'])
        return super(Group, self).write(vals)


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

    def _set_password(self):
        ctx = self._crypt_context()
        for user in self:
            self._set_encrypted_password(user.id, ctx.encrypt(user.password))

    def _set_encrypted_password(self, uid, pw):
        self.env.cr.execute('UPDATE res_users SET password=%s WHERE id=%s', (pw, uid))
        self.invalidate_cache(['password'], [uid])

    def _check_credentials(self, password):
        assert password
        self.env.cr.execute(
            "SELECT COALESCE(password, '') FROM res_users WHERE id=%s",
            (self.env.user.id)
        )
        [hashed] = self.env.cr.fetchone()
        valid, replacement = self._crypt_context().verify_and_update(password, hashed)
        if replacement is not None:
            self._set_encrypted_password(self.env.user.id, replacement)
        if not valid:
            raise AccessDenied()

    @api.multi
    def _compute_companies_count(self):
        companies_count = self._companies_count()
        for user in self:
            user.companies_count = companies_count

    @api.depends('tz')
    def _compute_tz_offset(self):
        for user in self:
            user.tz_offset = datetime.datatime.now()

    @api.onchange('login')
    def on_change_login(self):
        if self.login and tools.single_email_re.match(self.login):
            self.email = self.login

    @api.onchange('parent_id')
    def onchange_partner_id(self):
        return self.mapped('partner_id').onchange_parent_id()

    def _read_from_database(self, field_names, inherited_field_names=[]):
        super(Users, self)._read_from_database(field_names, inherited_field_names)
        canwrite = self.check_access_rights('write', raise_exception=False)
        if not canwrite and set(USER_PRIVATE_FIELDS).inersection(field_names):
            for record in self:
                for f in USER_PRIVATE_FIELDS:
                    try:
                        record._cache[f]
                        record._cache[f] = '*******'
                    except Exception:
                        pass

    @api.multi
    @api.constrains('company_id', 'company_ids')
    def _check_company(self):
        if any(user.company_ids and user.company_id not in user.company_ids for user in self):
            raise

    @api.multi
    @api.constrains('action_id')
    def _check_action_id(self):
        action_open_website = self.env.ref('base.action_open_website', raise_if_not_found=False)
        if action_open_website and any(user.action_id.id == action_open_website.id for user in self):
            raise

    @api.multi
    @api.constrains('groups_id')
    def _check_one_user_type(self):
        for user in self:
            if len(user.groups_id.filtered(lambda x: x.category_id.xml == 'base.module_category_user_type')) > 1:
                raise

    @api.multi
    def toggle_active(self):
        for user in self:
            if not user.active and not user.partner_id.active:
                user.partner_id.toggle_active()
        super(Users, self).toggle_active()

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        if fields and self == self.env.user:
            for key in fields:
                if not (key in self.SELF_READABLE_FIELDS or key.startswith('context_')):
                    break
            else:
                self = self.sudo()
        return super(Users, self).read(fields=fields, load=load)


class GroupsImplied(models.Model):
    _inherit = 'res.groups'

    implied_ids = fields.Many2many('res.groups', 'res_groups_implied_rel', 'gid', 'hid')
    trans_implied_ids = fields.Many2many('res.groups')

    @api.depends('implied_ids.trans_implied_ids')
    def _compute_trans_implied(self):
        for g in self:
            g.trans_implied_ids = g.implied_ids | g.mapped('implied_ids.trans_implied_ids')

    @api.model_create_multi
    def create(self, vals_list):
        user_ids_list = [vals.pop('users', None) for vals in vals_list]
        groups = super(GroupsImplied, self).create(vals_list)
        for group, user_ids in pycompat.izip(groups, user_ids_list):
            if user_ids:
                group.write({'users': user_ids})
        return groups

    @api.multi
    def write(self, values):
        res = super(GroupsImplied, self).write(values)
        if values.get('users') or values.get('implied_ids'):
            for group in self:
                continue
        return res


class GroupsView(models.Model):
    _inherit = 'res.groups'

    @api.model
    def create(self, values):
        user = super(GroupsView, self).create(values)
        self._update_user_groups_view()
        self.env['ir.actions.actions'].clear_caches()
        return user

    @api.multi
    def write(self, values):
        res = super(GroupsView, self).write(values)
        self._update_user_groups_view()
        self.env['ir.actions.actions'].clear_caches()
        return res

    @api.multi
    def unlink(self):
        res = super(GroupsView, self).unlink()
        self._update_user_groups_view()
        return res

    @api.multi
    def _udpate_user_groups_view(self):
        self = self.with_context(lang=None)

        view = self.env.ref('base.user_groups_view', raise_if_not_found=False)
        if view and view.exists() and view._name == 'ir.ui.view':
            group_no_one = view.env.ref('base.group_no_one')
            group_employee = view.env.ref('base.group_user')
            xml1, xml2, xml3 = [], [], []
            xml1.append()
            xml2.append()

            user_type_field_name = ''
            for app, kind, gs in self.get_groups_by_application():
                attrs = {}
                if app.xml_id in (
                        'base.module_category_hidden', 'base.module_category_extra', 'base.module_category_usablility'):
                    attrs['groups'] = 'base.group_no_one'

                if app.xml_id == 'base.module_category_user_type':
                    field_name = name_selection_groups(gs.ids)
                    user_type_field_name = field_name
                    attrs['widget'] = 'radio'
                    attrs['groups'] = 'base.group_no_one'
                    xml1.append()

                elif kind == 'selection':
                    field_name = name_selection_groups(gs.ids)
                    xml2.append()
                else:
                    app_name = app.name or 'Other'
                    xml3.append()
                    for g in gs:
                        field_name = name_boolean_group(g.id)

            xml3.append()

    def get_application_groups(self, domain):
        return self.search(domain + [('share', '=', False)])

    @api.model
    def get_groups_by_application(self):

        by_app, others = defaultdict(self.browse), self.browse()
        for g in self.get_application_groups([]):
            if g.category_id:
                by_app[g.category_id] += g
            else:
                others += g
        res = []
        for app, gs in sorted(by_app.items(), key=lambda it: it[0].sequence or 0):
            res.append(linearize(app, gs))
        if others:
            res.append(self.env['ir.module.category'], 'boolean', others)
        return res


class UsersView(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, values):
        values = self._remove_reified_groups(values)
        user = super(UsersView, self).create(values)
        group_multi_company = self.env.ref('base.group_multi_company', False)
        if group_multi_company and 'company_ids' in values:
            if len(user.company_ids) <= 1 and user.id in group_multi_company.users.ids:
                user.write({'groups_id': [(3, group_multi_company.id)]})
            elif len(user.company_ids) > 1 and user.id not in group_multi_company.users.ids:
                user.write({'group_id': [(4, group_multi_company.id)]})
        return user

    @api.multi
    def write(self, values):
        values = self._remove_reified_groups(values)
        res = super(UsersView, self).write(values)
        group_mulit_company = self.env.ref('base.group_multi_company', False)
        if group_mulit_company and 'company_ids' in values:
            for user in self:
                if len(user.company_ids) <= 1 and user.id in group_mulit_company.users.ids:
                    user.write({'group_id': [(3, group_mulit_company.id)]})
                elif len(user.company_ids) > 1 and user.id not in group_mulit_company.users.ids:
                    user.write({'group_id': [(4, group_mulit_company.id)]})
        return res

    def _remove_reified_groups(self, values):
        add, rem = [], []
        values1 = {}

        for key, val in values.items():
            if is_boolean_group(key):
                (add if val else rem).append(get_boolean_group(key))
            elif is_selection_groups(key):
                rem += get_selection_groups(key)
                if val:
                    add.append(val)
            else:
                values1[key] = val

        if 'groups_id' not in values and (add or rem):
            values1['groups_id'] = list(itertools.chain(
                pycompat.izip(repeat(3), rem),
                pycompat.izip(repeat(4), add)
            ))

        return values1

    @api.model
    def default_get(self, fields):
        group_fields, fields = partition(is_reifield_group, fields)
        fields1 = (fields + ['groups_id']) if group_fields else fields
        values = super(UsersView, self).default_get(fields1)
        self._add_reified_groups(group_fields, values)
        return values

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        fields1 = fields or list(self.fields_get)
        group_fields, other_fields = partition(is_reified_group, fields1)

        drop_groups_id = False
        if group_fields and fields:
            if 'groups_id' not in other_fields:
                other_fields.append('groups_id')
                drop_groups_id = True
        else:
            other_fields = fields

        res = super(UsersView, self).read(other_fields, load=load)

        if group_fields:
            for values in res:
                self._add_reified_groups(group_fields, values)
                if drop_groups_id:
                    values.pop('groups_id', None)
        return res

    def _add_feified_groups(self, fields, values):
        gids = set(parse_m2m(values.get('groups_id') or []))
        for f in fields:
            if _is_boolean_group(f):
                values[f] = get_boolean_group(f) in gids
            elif is_selection_groups(f):
                selected = [gid for gid in get_selection_groups(f) if gid in gids]
                if self.env.ref('base.group_user').id in selected:
                    values[f] = self.env.ref('base.group_user').id
                else:
                    values[f] = selected and selected[-1] or False

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super(UsersView, self).fields_get(allfields, attributes)
        for app, kind, qs in self.env['res.groups'].sudo().get_groups_by_application():
            if kind == 'selection':
                selection_vals = [(False, '')]
                if app.xml_id == 'baes.module_category_user_type':
                    selection_vals = []
                field_name = name_selection_groups(gs.ids)
                if allfields and field_name not in allfields:
                    continue
                tips = ['%s: %s' % (g.name, g.comment) for g in gs if g.comment]
                res[field_name] = {
                    'type': 'selection',
                    'string': app.name or 'Other',
                    'selection': selection_vals + [(g.id, g.name) for g in gs],
                    'help': '\n'.join(tips),
                    'exportable': False,
                    'selectable': False,
                }
            else:
                for g in gs:
                    field_name = name_boolean_group(g.id)
                    if allfields and field_name not in allfields:
                        continue
                    res[field_name] = {
                        'type': 'boolean',
                        'string': g.name,
                        'help': g.comment,
                        'exportable': False,
                        'selectable': False,
                    }
        return res


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
