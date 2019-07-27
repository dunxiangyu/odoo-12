from odoo import models, fields


def _lang_get(self):
    return self.env['res.lang'].get_installed()


def _tz_get(self):
    return []


class FormatAddressMixin(models.AbstractModel):
    _name = "format.address.mixin"
    _description = "Fomat Address"

    def _fields_view_get_address(self, arch):
        pass


class PartnerCategory(models.Model):
    _name = 'res.partner.category'
    _description = 'Partner Tags'
    _order = 'name'
    _parent_store = True

    name = fields.Char(string='Tag Name', required=True, translate=True)
    color = fields.Integer(string='Color Index')
    parent_id = fields.Many2one('res.partner.category', string='Parent Category',
                                index=True, ondelete='cascade')
    child_ids = fields.One2many('res.partner.category', 'parent_id', string='Child Tags')
    active = fields.Boolean(default=True, help='The active field allows you to hide the category without removing it.')
    parent_path = fields.Char(index=True)
    partner_ids = fields.Many2many('res.partner', column1='category_id',
                                   column2='partner_id', string='Partners')

    def name_get(self):
        if self._context.get('partner_category_display') == 'short':
            return super(PartnerCategory, self).name_get()

        res = []
        for category in self:
            names = []
            current = category
            while current:
                names.append(current.name)
                current = current.parent_id
            res.append((category.id, '/ '.join(reversed(names))))
        return res

    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if name:
            name = name.split(' / ')[-1]
            args = [('name', operator, name)] + args
        partner_category_ids = self._search(args, limit=limit, access_rights_uid=name_get_uid)
        return self.browse(partner_category_ids).name_get()


class PartnerTitle(models.Model):
    _name = 'res.partner.title'
    _description = 'Partner Title'
    _order = 'name'

    name = fields.Char(string='Title', required=True, translate=True)
    shortcut = fields.Char(string='Abbreviation', translate=True)


class Partner(models.Model):
    _name = 'res.partner'
    _inherit = ['format.address.mixin']
    _description = 'Contact'
    _order = 'display_name'

    def _default_category(self):
        return self.env['res.partner.category'].browse(self._context.get('category_id'))

    name = fields.Char(index=True)
    display_name = fields.Char(compute='_compute_display_name', store=True, index=True)
    date = fields.Date(index=True)
    title = fields.Many2one('res.partner.title')
    parent_id = fields.Many2one('res.partner', index=True)
    parent_name = fields.Char(related='parent_id.name', readonly=True)
    child_ids = fields.One2many('res.partner', 'parent_id', domain=[('active', '=', True)])
    ref = fields.Char(string='Internal Reference', index=True)
    lang = fields.Selection(_lang_get, string='Language', default=lambda self: self.lang)
    tz = fields.Selection(_tz_get, string='Timezone', default=lambda self: self._context.get('tz'))
    tz_offset = fields.Char(compute='_compute_tz_offset', invisible=True)
    user_id = fields.Many2one('res.users', string='Salesperson')
    vat = fields.Char(string='Tax ID')
    bank_ids = fields.One2many('res.partner.bank', 'partner_id')
    website = fields.Char()
    comment = fields.Text(string='Notes')

    category_id = fields.Many2many('res.partner.category', column1='partner_id',
                                   column2='category_id', default=_default_category)
    credit_limit = fields.Float()
    barcode = fields.Char()
    active = fields.Boolean(default=True)
    customer = fields.Boolean()
    supplier = fields.Boolean()
    employee = fields.Boolean()
    function = fields.Char()
    type = fields.Selection([('contact', 'Contact'),
                             ('invoice', 'Invoice address'),
                             ('delivery', 'Shipping address'),
                             ('other', 'Other address'),
                             ('private', 'Private Address')])
    street = fields.Char()
    street2 = fields.Char()
    zip = fields.Char(change_default=True)
    city = fields.Char()
    state_id = fields.Many2one('res.country.state', ondelete='restrict',
                               domain="[('country_id', '=?', country_id)]")
    country_id = fields.Many2one('res.country', ondelete='restrict')
    email = fields.Char()
    email_formatted = fields.Char(compute='_compute_email_formatted')
    phone = fields.Char()
    mobile = fields.Char()
    is_company = fields.Boolean()
    industry_id = fields.Many2one('res.partner.industry', 'Industry')
    company_type = fields.Selection(selection=[('person', 'Individual'),
                                               ('company', 'Company')],
                                    compute='_compute_company_type',
                                    inverse='_write_company_tree')
    company_id = fields.Many2one('res.company', default=_default_company)
    color = fields.Integer()
    user_ids = fields.One2many('res.users', 'parent_id', auto_join=True)
    partner_share = fields.Boolean(compute='_compute_partner_share')
    contact_address = fields.Char(compute='_compute_contact_address')

    commercial_partner_id = fields.Many2one('res.partner', compute='_compute_commercial_partner')
    commercial_company_name = fields.Char(compute='_compute_commercial_company_name')

    company_name = fields.Char()

    image = fields.Binary(attachment=True)
    image_medium = fields.Binary(attachment=True)
    image_small = fields.Binary(attachment=True)
    self = fields.Many2one(comodel_name=_name, compute='_compute_get_ids')

    def init(self):
        pass

    def _compute_display_name(self):
        pass

    def _compute_get_ids(self):
        return self.self = self.id

    def onchange_parent_id(self):
        if not self.parent_id:
            return
        result = {}
        partner = getattr(self, '_origin', self)
        if partner.parent_id and partner.parent_id != self.parent_id:
            result['warning'] = {}
        if partner.type == 'contact' or self.type == 'contact':
            address_fields = self._address_fields()

        return result

    def _onchange_contry_id(self):
        if self.country_id and self.country_id != self.state_id.country_id:
            self.state_id = False

    def _onchange_state(self):
        if self.state_id.country_id:
            self.country_id = self.state_id.country_id

    def _compute_company_type(self):
        for partner in self:
            partner.is_company = partner.company_type == 'company'

    def onchange_company_type(self):
        self.is_company = (self.company_type == 'company')

    def _update_fields_values(self, fields):
        values = {}
        for fname in fields:
            field = self._fields[fname]
            if field.type == 'many2one':
                values[fname] = self[fname].id
            elif field.type == 'one2many':
                raise
            elif field.type == 'many2many':
                values[fname] = [(6, 0, self[fname].ids)]
            else:
                values[fname] = self[fname]
        return values

    def write(self, vals):
        if vals.get('active') is False:
            for partner in self:
                if partner.active and partner.user_ids:
                    raise

        if vals.get('website'):
            vals['website'] = self._clean_website(vals['website'])
        if vals.get('parent_id'):
            vals['company_name'] = False
        if vals.get('company_id'):
            company = self.env['res.company'].browse(vals['company_id'])

    def get_base_url(self):
        self.ensure_one()
        return self.env['ir.config_parameter'].sudo().get_param('web.base.url')


class ResPartnerIndustry(models.Model):
    _name = 'res.partner.industry'
    _description = 'Industry'
    _order = 'name'

    name = fields.Char(translate=True)
    full_name = fields.Char(translate=True)
    active = fields.Boolean(default=True)
