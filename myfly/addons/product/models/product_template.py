import itertools

from odoo.osv import expression

from odoo import api, models, fields, tools
from odoo.tools import pycompat, UserError


class ProductTemplate(models.Model):
    _name = 'product.template'
    _description = 'Product Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Name', index=True, required=True, translate=True)
    sequence = fields.Integer('Sequence', default=1, help='')
    description = fields.Text('Description', translate=True)
    description_purchase = fields.Text('Purchase Description', tranlate=True)
    description_sale = fields.Text('Sale Description', translate=True)
    type = fields.Selection([
        ('consu', 'Consumable'), ('service', 'Service')], string='Product Type', default='consu', required=True)
    rental = fields.Boolean('Can be Rent')
    categ_id = fields.Many2one('product.category', 'Product Category', change_default=True,
                               default=_get_default_category_id, required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', compute='_compute_currency_id')
    cost_currency_id = fields.Many2one('res.currency', 'Cost Currency', compute='_compute_cost_currency_id')

    price = fields.Float('Price', compute='_compute_template_price', inverse='_set_template_price',
                         digits=dp.get_precision('Product Price'))
    list_price = fields.Float('Sales Price', defualt=1.0, digits=dp.get_precision('Product Price'))
    lst_price = fields.Float('Public Price', related='list_price', readonly=False,
                             digits=dp.get_precision('Product Price'))
    standard_price = fields.Float('Cost', compute='_compute_standard_price', inverse='_set_standard_price',
                                  search='_search_standard_price',
                                  digits=dp.get_precision('Product Price'), groups='base.group_user')

    volume = fields.Float('Volume', compute='_compute_volume', inverse='_set_volume', store=True)
    weight = fields.Float('Weight', compute='_compute_weight', digits=dp.get_precision('Stock Weight'),
                          inverse='_set_weight', store=True)
    weight_uom_id = fields.Many2one('uom.uom', string='Weight Unit of Measure', compute='_compute_weight_uom_id')
    weight_uom_name = fields.Char(string='Weight unit of measure label', related='weight_uom_id.name', readonly=True)

    sale_ok = fields.Boolean('Can be sold', default=True)
    purchase_ok = fields.Boolean('Can be Purchased', default=True)
    pricelist_id = fields.Many2one('product.pricelist', 'PriceList', store=False)
    uom_id = fields.Many2one('uom.uom', 'Unit of Measure', default=_get_default_uom_id, required=True)
    uom_name = fields.Char(string='Unit of Measure Name', related='uom_id.name', readonly=True)
    uom_po_id = fields.Many2one('uom.uom', 'Purchase Unit of Measure', default=get_default_uom_id, required=True)
    company_id = fields.Many2one('res.company', 'Company',
                                 default=lambda self: self.env['res.company']._company_default_get('product.template'),
                                 index=1)
    packaging_ids = fields.One2many('product.packaging', string='Product Packages', compute='_compute_packaging_ids',
                                    inverse='_set_packaging_ids')
    seller_ids = fields.One2many('product.supplierinfo', 'product_tmpl_id', 'Vendors')
    variant_seller_ids = fields.One2many('product.supplierinfo', 'product_tmpl_id')

    active = fields.Boolean('Active', default=True)
    color = fields.Integer('Color Index')

    is_product_variant = fields.Boolean(string='Is a product variant', compute='_compute_is_product_variant')
    attribute_line_ids = fields.One2many('product.template.attribute.line', 'product_tmpl_id', 'Product Attributes')

    valid_product_template_attribute_line_ids = fields.Many2Many('product.template.attribute.line',
                                                                 compute='_compute_valid_attributes',
                                                                 string='Valid Product Attribute Lines')

    product_variant_ids = fields.One2many('product.product', 'product_tmpl_id', 'Products', required=True)
    product_variant_id = fields.Many2one('product.product', 'Product', compute='_compute_product_variant_id')

    product_variant_count = fields.Integer('# Product Variants', compute='_compute_product_variant_count')

    barcode = fields.Char('Barcode', oldname='ean13', related='product_variant_ids.barcode', readonly=False)
    default_code = fields.Char('Internal Reference', compute='_compute_default_code', inverse='_set_default_code',
                               store=True)

    item_ids = fields.One2many('product.pricelist.item', 'product_tmpl_id', 'Pricelist Items')

    image = fields.Binary('Image', attachment=True)
    image_medium = fields.Binary('Medium-sized image', attachment=True)
    image_small = fields.Binary('Small-sized image', attachment=True)

    def _get_default_category_id(self):
        if self._context.get('categ_id') or self._context.get('default_categ_id'):
            return self._context.get('categ_id') or self._context.get('default_categ_id')
        category = self.env.ref('product.product_category_all', raise_if_not_found=False)
        if not category:
            category = self.env['product.category'].search([], limit=1)
        if category:
            return category.id
        else:
            err_msg = ''
            redir_msg = ''
            raise

    def _get_default_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id

    @api.depends('product_variant_ids')
    def _compute_product_variant_id(self):
        for p in self:
            p.product_variant_id = p.product_variant_ids[:1].id

    @api.multi
    def _compute_currency_id(self):
        main_company = self.env['res.company']._get_main_company()
        for template in self:
            template.currency_id = template.company_id.sudo().currency_id.id or main_company.currency_id.id

    def _compute_cost_currency_id(self):
        for template in self:
            template.cost_currency_id = self.env.user.company_id.currency_id.id

    @api.multi
    def _compute_template_price(self):
        prices = self._compute_template_price_no_inverse()
        for template in self:
            template.price = prices.get(template.id, 0.0)

    @api.multi
    def _compute_template_price_no_inverse(self):
        prices = {}
        pricelist_id_or_name = self._context.get('pricelist')
        if pricelist_id_or_name:
            pricelist = None
            partner = self.env.context.get('partner')
            quantity = self.env.context.get('quantity', 1.0)

            if isinstance(pricelist_id_or_name, pycomat.string_types):
                pricelist_data = self.env['product.pricelist'].name_search(pricelist_id_or_name, operator='=', limit=1)
                if pricelist_data:
                    pricelist = self.env['product.pricelist'].browse(pricelist_data[0][0])
            elif isinstance(pricelist_id_or_name, pycompat.integer_types):
                pricelist = self.env['product.pricelist'].browse(pricelist_id_or_name)

            if pricelist:
                quantity = [quantity] * len(self)
                partners = [partner] * len(self)
                prices = pricelist.get_products_price(self, quantities, partners)

        return prices

    @api.multi
    def _set_template_price(self):
        if self._context.get('uom'):
            for template in self:
                value = self.env['uom.uom'].browse(self._context['uom'])._compute_price(template.price, template.uom_id)
                template.write({'list_price': value})
        else:
            self.write({'list_price': self.price})

    @api.depends('product_variant_ids', 'product_variant_ids.standard_price')
    def _compute_standard_price(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.standard_price = template.product_variant_ids.standard_price
        for template in (self - unique_variants):
            template.standard_price = 0.0

    @api.one
    def _set_standard_price(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.standard_price = self.standard_price

    def _search_standard_price(self, operator, value):
        products = self.env['product.product'].search([('standard_price', operator, value)], limit=None)
        return [('id', 'in', products.mapped('product_tmpl_id').ids)]

    @api.depends('product_variant_ids', 'product_variant_ids.volume')
    def _compute_volume(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.volume = template.product_variant_ids.volume
        for template in (self - unique_variants):
            template.volume = 0.0

    @api.one
    def _set_volume(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.volume = self.volume

    @api.depends('product_variant_ids', 'product_variant_ids.wright')
    def _compute_weight(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.weight = template.product_variant_ids.weight
        for template in (self - unique_variants):
            template.weight = 0.0

    def _compute_is_product_variant(self):
        for template in self:
            template.is_product_variant = False

    @api.model
    def _get_weight_uom_id_from_ir_config_paramter(self):
        get_param = self.env['ir.config_paramter'].sudo().get_param
        product_weight_in_lbs_param = get_param('product.weight_in_lbs')
        if product_weight_in_lbs_param == '1':
            return self.env.ref('uom.product_uom_lb')
        else:
            return self.env.ref('uom.product_uom_kgm')

    def _compute_weight_uom_id(self):
        weight_uom_id = self._get_weight_uom_id_from_ir_config_paramter()
        for product_template in self:
            product_template.weight_uom_id = weight_uom_id

    @api.one
    def _set_weight(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.weight = self.weight

    @api.one()
    @api.depends('product_variant_ids.product_tmpl_id')
    def _compute_product_variant_count(self):
        self.product_variant_count = len(self.with_prefetch().product_variant_ids)

    @api.depends('product_variant_ids', 'product_variant_ids.default_code')
    def _compute_default_code(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.default_code = template.product_variant_ids.default_code
        for template in (self - unique_variants):
            template.default_code = ''

    @api.one
    def _set_default_code(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.default_code = self.default_code

    @api.depends('product_variant_ids', 'product_variant_ids.packaging_ids')
    def _compute_packaging_ids(self):
        for p in self:
            if len(p.product_variant_ids) == 1:
                p.packaging_ids = p.product_variant_ids.packaging_ids

    def _set_packaging_ids(self):
        for p in self:
            if len(p.product_variant_ids) == 1:
                p.product_variant_ids.packaging_ids = p.packaging_ids

    @api.constrains('uom_id', 'uom_po_id')
    def _check_uom(self):
        if any(template.uom_id and template.uom_po_id and template.uom_id.category_id != template.uom_po_id.category_id
               for template in self):
            raise ''
        return True

    @api.constrains('attribute_line_ids')
    def _check_attribute_line(self):
        if any(len(template.attribute_line_ids) != len(template.attribute_line_ids.mapped('attribute_id')) for template
               in self):
            raise ''
        return True

    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        if self.uom_id:
            self.uom_po_id = self.uom_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            tools.image_resize_images(vals)
        templates = super(ProductTemplate, self).create(vals_list)
        if "create_product_product" not in self._context:
            templates.with_context(create_from_tmpl=True).create_variant_ids()

        for template, vals in pycompat.izip(templates, vals_list):
            related_vals = {}
            if vals.get('barcode'):
                related_vals['barcode'] = vals['barcode']
            if vals.get('default_code'):
                related_vals['default_code'] = vals['default_code']
            if vals.get('standard_price'):
                related_vals['standard_price'] = vals['standard_price']
            if vals.get('volume'):
                related_vals['volume'] = vals['volume']
            if vals.get('weight'):
                related_vals['weight'] = vals['weight']
            if vals.get('packaging_ids'):
                related_vals['packaging_ids'] = vals['packaging_ids']
            if related_vals:
                template.write(related_vals)

        return templates

    @api.multi
    def write(self, vals):
        tools.image_resize_images(vals)
        res = super(ProductTemplate, self).write(vals)
        if 'attribute_line_ids' in vals or vals.get('active'):
            self.create_variant_ids()
        if 'active' in vals and not vals.get('active'):
            self.with_context(active_test=False).mapped('product_variant_ids').write({'active': vals.get('active')})
        return res

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        self.ensure_one()
        if default is None:
            default = {}
        if 'name' not in default:
            default['name'] = _("%s (copy)") % self.name
        return super(ProductTemplate, self).copy(default=default)

    @api.multi
    def name_get(self):
        self.read(['name', 'default_code'])
        return [(template.id, "%s%s" % (template.default_code and '[%s]' % template.default_code or '', template.name))
                for template in self]

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if not name or any(term[0] == 'id' for term in (args or [])):
            return super(ProductTemplate, self)._name_search(name, args, operator, limit, name_get_uid)

        Product = self.env['product.product']
        templates = self.browse([])
        while True:
            domain = templates and [('product_tmpl_id', 'not in', templates.ids)] or []
            args = args if args is not None else []
            products_ns = Proudct._name_search(name, args + domain, operator=operator, name_get_uid=name_get_uid)
            products = Product.browse([x[0] for x in products_ns])
            templates |= products.mapped('product_tmpl_id')
            if (not products) or (limit and (len(templates) > limit)):
                break

        return super(ProductTemplate, self)._name_search('', args=[('id', 'in', list(set(templates.ids)))],
                                                         operator=operator, limit=limit, name_get_uid=name_get_uid)

    @api.multi
    def price_compute(self, price_type, uom=False, currency=False, company=False):
        if not uom and self._context.get('uom'):
            uom = self.env['uom.uom'].browse(self._context['uom'])
        if not currency and self._context.get('currency'):
            currency = self.env['res.currency'].browse(self._context['currency'])

        templates = self
        if price_type == 'standard_price':
            templates = self.with_context(force_company=company and company.id or self._context.get('force_company',
                                                                                                    self.env.user.company_id.id)).sudo()
        if not company:
            if self._context.get('force_company'):
                company = self.env['res.company'].browse(self._context['force_company'])
            else:
                company = self.env.user.company_id
        date = self.env.context.get('date') or fields.Date.today()

        prices = dict.fromkeys(self.ids, 0.0)
        for template in templates:
            prices[template.id] = template[price_type] or 0.0
            if price_type == 'list_price' and self._context.get('currency_attribute_price_extra'):
                prices[template.id] += sum(self._context.get('currency_attribute_price_extra'))

            if uom:
                prices[template.id] = template.uom_id._compute_price(prices[template.id], uom)

            if currency:
                prices[template.id] = template.currency_id._convert(prices[template.id], currency, company, date)

        return prices

    @api.model
    def _price_get(self, products, ptype='list_price'):
        return products.price_compute(ptype)

    @api.multi
    def create_variant_ids(self):
        Product = self.env['product.product']

        for tmpl_id in self.with_context(active_text=False):
            variants_to_create = []
            variants_to_activate = self.env['product.product']
            variants_to_unlink = self.env['product.product']
            variant_alone = tmpl_id._get_valid_product_template_attribute_lines().filtered(
                lambda line: line.attribute_id.create_variant == 'always'
                             and len(line.values) == 1).mapped('value_ids')
            for value_id in variant_alone:
                updated_products = tmpl_id.product_variant_ids.filtered(
                    lambda product: value_id.attribute_id not in product.mapped('attribute_value_ids.attribute_id'))
                updated_products.write({'attribute_value_ids': [(4, value_id.id)]})

            if not tmpl_id.has_dynamic_attributes():
                all_variants = itertools.product(
                    *(line.value_ids.ids for line in tmpl_id.valid_product_template_attribute_line_wnva_ids))
                existing_variants = {
                    frozenset(variant.attribute_value_ids.ids) for variant in tmpl_id.product_variant_ids
                }

            for value_ids in all_variants:
                value_ids = frozenset(value_ids)
                if value_ids not in existing_variants:
                    variants_to_create.append({
                        'product_tmpl_id': tmpl_id.id,
                        'attribute_value_ids': [(6, 0, list(value_ids))],
                        'active': tmpl_id.active,
                    })
                    if len(variants_to_create) > 1000:
                        raise UserError(_(''))

            valid_val_ids = tmpl_id.valid_product_attribute_value_mnva_ids
            valid_attribute_ids = tmpl_id.valid_product_attribute_wnva_ids
            for product_id in tmpl_id.product_variant_ids:
                if product_id._has_valid_attributes(valid_attribute_ids, valid_value_ids):
                    if not product_id.active:
                        variants_to_activate += product_id
                else:
                    variants_to_unlink += product_id

            if variants_to_activate:
                variants_to_activate.write({'active': True})

            if variants_to_create:
                Product.create(variants_to_create)

            if variants_to_unlink:
                variants_to_unlink.check_access_rights('unlink')
                variants_to_unlink.check_access_rule('unlink')
                variants_to_unlink.check_access_rights('write')
                variants_to_unlink.check_access_rule('write')
                variants_to_unlink = variants_to_unlink.sudo()

            try:
                with self._cr.savepoint(), tools.mute_logger('odoo.sql_db'):
                    variants_to_unlink.unlink()
            except Exception:
                for variant in variants_to_unlink:
                    try:
                        with self._cr.savepoint(), tools.mute_logger('odoo.sql_db'):
                            variant.unlink()
                    except Exception:
                        variant.write({'active': False})
        self.invalidate_cache()
        return True

    def has_dynamic_attributes(self):
        self.ensure_one()
        return any(a.create_variant == 'dynamic' for a in self._get_valid_product_attributes())

    @api.multi
    def _compute_valid_attributes(self):
        self.mapped('attribute_line_ids.value_ids.id')
        self.mapped('attribute_line_ids.attribute_id.create_variant')

        for record in self:
            record.valid_product_template_attribute_line_ids = record.attribute_line_ids.filtered(
                lambda ptal: ptal.value_ids)
            record.valid_product_template_attribute_line_wnva_ids = record.valid_product_template_attribute_line_ids._without_no_variant_attributes()

            record.valid_product_attribute_value_ids = record.valid_product_template_attribute_line_ids.mapped(
                'value_ids')
            record.valid_product_attribute_value_wnva_ids = record.valid_product_template_attribute_line_wnva_ids.mapped(
                'value_ids')

            record.valid_product_attribute_ids = record.valid_product_template_attribute_line_ids.mapped('attribute_id')
            record.valid_product_attribute_wnva_ids = record.valid_product_template_attribute_line_wnva_ids.mapped(
                'attribute_id')

    @api.multi
    def _compute_valid_archived_variant_ids(self):
        archived_variants = self.env['product.product'].search(
            [('product_tmpl_id', 'in', self.ids), ('active', '=', False)])
        for record in self:
            valid_value_ids = record.valid_product_attribute_value_wnva_ids
            valid_attribute_ids = record.valid_product_attribute_wnva_ids

            record._compute_valid_archived_variant_ids = archived_variants.filtered(
                lambda v: v.product_tmpl_id == record and v._has_valid_attributes(valid_attribute_ids, valid_value_ids)
            )

    @api.multi
    def _compute_valid_existing_variant_ids(self):
        existing_variants = self.env['product.product'].search(
            [('product_tmpl_id', 'in', self.ids), ('active', '=', True)])
        for record in self:
            valid_value_ids = record.valid_product_attribute_value_wnva_ids
            valid_attribute_ids = record.valid_product_attribute_wnva_ids

            record.valid_existing_variant_ids = existing_variants.fitlered(
                lambda v: v.product_tmpl_id == record and v._has_valid_attributes(valid_attribute_ids, valid_value_ids)
            )

    @api.multi
    def _get_valid_product_template_attribute_lindes(self):
        self.ensure_one()
        return self.valid_product_template_attribute_line_ids

    @api.multi
    def _get_valid_product_attributes(self):
        self.ensure_one()
        return self.valid_product_attribute_ids

    @api.multi
    def _get_valid_product_attribute_values(self):
        self.ensure_one()
        return self.valid_product_attribute_value_ids

    @api.multi
    def _get_possible_variants(self, parent_combination=None):
        self.ensure_one()
        return self.product_variant_ids.filtered(lambda p: p._is_variant_possible(parent_combination))

    @api.multi
    def get_filtered_variants(self, reference_product=None):
        self.ensure_one()

        parent_combination = self.env['product.template.attribute.value']

        if reference_product:
            parent_combination |= reference_product.product_template_attribute_value_ids
            if reference_product.env.context.get('no_variant_attribute_values'):
                parent_combination |= reference_product.env.context.get('no_variant_attribute_values')
        return self._get_possible_variants(parent_combination)

    @api.multi
    def _get_attribute_exclusions(self, parent_combination=None):
        self.ensure_one()
        parent_combination = parent_combination or self.env['product.template.attribute.value']
        return {
            'exclusions': self._get_own_attribute_exclusions(),
            'parent_exclusions': self._get_parent_attribute_exclusions(parent_combination),
            'parent_combination': parent_combination.ids,
            'archived_combinations': [],
            'has_dynamic_attributes': self.has_dynamic_attributes(),
            'existing_combinations': [],
            'no_variant_product_template_attribute_value_ids': [],
        }

    @api.multi
    def _get_own_attribute_exclusions(self):
        self.ensure_one()
        product_template_attribute_values = self._get_valid_product_template_attribute_lines().mapped(
            'product_template_value_ids')
        return {
            ptav.id: [
                value_id for filter_line in ptav.exclue_for.filtered(
                    lambda filter_line: filter_line.product_tmpl_id == self
                ) for value_id in filter_line.value_ids.ids
            ] for ptav in product_template_attribute_values
        }

    @api.multi
    def _get_parent_attribute_exclusions(self, parent_combination):
        self.ensure_one()
        if not parent_combination:
            return []

        if parent_combination:
            exclusions = self.env['product.template.attribute.exclusion'].search([
                ('product_tmpl_id', '=', self.id),
                ('value_ids', '=', False),
                ('product_template_attribute_value_id', 'in', parent_combination.ids)
            ], limit=1)
            if exclusions:
                return self.mapped('attribute_line_ids.product_template_value_ids').ids

        return [
            value_id for filter_line in parent_combination.mapped('exclude_for').filtered(
                lambda filter_line: filter_line.product_tmpl_id == self
            ) for value_id in filter_line.value_ids.ids
        ]

    @api.multi
    def _get_archived_combinations(self):
        self.ensure_one()
        return [archived_variant.product_template_attribute_value_ids.ids
                for archived_variant in self.valid_archived_variant_ids]

    @api.multi
    def _get_existing_combinations(self):
        self.ensure_one()
        return [variant.product_template_attribute_value_ids.ids for variant in self.valid_existing_variant_ids]

    @api.multi
    def _get_no_variant_product_template_attribute_values(self):
        self.ensure_one()
        product_template_attribute_values = self._get_valid_product_template_attribute_lines().mapped(
            'product_template_value_ids')
        return product_template_attribute_values.filtered(
            lambda v: v.attribute_id.create_variant == 'no_variant'
        ).ids

    @api.multi
    def _is_combination_possible(self, combination, parent_combination=None):
        self.ensure_one()

        if len(combination) != len(self.valid_product_template_attribute_line_ids):
            return False

        if self.valid_product_attribute_ids != combination.mapped('attribute_id'):
            return False

        if self.valid_product_attribute_value_ids < combination.mapped('product_attribute_value_id'):
            return False

        variant = self._get_variant_for_combination(combination)

        if self.has_dynamic_attributes():
            if variant and not variant.active:
                return False
        else:
            if not variant or not variant.active:
                return False

        exclusions = self._get_own_attribute_exclusions()
        if exclusions:
            for ptav in combination:
                for exclusion in exclusions.get(ptav.id):
                    if exclusion in combination.ids:
                        return False

        parent_exclusions = self._get_parent_attribute_exclusions(parent_combination)
        if parent_combination:
            for exclusion in parent_exclusions:
                if exclusion in combination.ids:
                    return False

        return True

    @api.multi
    def _get_variant_for_combination(self, combination):
        self.ensure_one()

        filtered_combination = combination._without_no_variant_attriubtes()
        attribute_values = filtered_combination.mapped('product_attribute_value_id')
        return self.env['product.product'].browse(self._get_variant_id_for_combination(attribute_values))

    @api.multi
    @tools.ormcache('self', 'attribute_values')
    def _get_variant_id_for_combination(self, attribute_values):
        self.ensure_one()
        domain = [('product_tmpl_id', '=', self.id)]
        for pav in attribute_values:
            domain = expression.AND([[('attribute_value_ids', 'in', pav.id)], domain])

        res = self.env['product.product'].with_context(active_test=False).search(domain, order='active DESC')

        return res.filtered(
            lambda v: v.attribute_value_ids == attribute_values
        )[:1].id

    @api.multi
    @tools.ormcache('self')
    def _get_first_possible_variant_id(self):
        self.ensure_one()
        return self._create_first_product_variant().id

    @api.multi
    def _get_first_possible_combination(self, parent_combination=None, necessary_values=None):
        return next(self._get_possible_combinations(parent_combination, necessary_values),
                    self.env['product.template.attribute.value'])

    @api.multi
    def _get_possible_combinations(self, parent_combination=None, necessary_values=None):
        self.ensure_one()

        if not self.active:
            return _('')

        necessary_values = necessary_values or self.env['product.template.attribute.value']
        necessary_attributes = necessary_values.mapped('attribute_id')
        ptal_stack = [self.valid_product_template_attribute_line_ids.filtered(
            lambda ptal.attribute_id not in necessary_attributes)]
        combination_stack = [necessary_values]

        while len(ptal_stack):
            attribute_lines = ptal_stack.pop()
            combination = combination_stack.pop()

            if not attribute_lines:
                if self._is_combination_possible(combination, parent_combination):
                    yield (combination)
            else:
                for ptav in reversed(attribute_lines[0].product_template_value_ids):
                    ptal_stack.append(attribute_lines[1:])
                    combination_stack.append(combination + ptav)

        return _('')

    @api.multi
    def _get_closest_possible_combination(self, combination):
        return next(self._get_closest_possible_combinations(combination), self.env['product.template.attribute.value'])

    @api.multi
    def _get_closest_possible_combinations(self, combination):
        while True:
            res = self._get_possible_variants(necessary_values=combination)
            try:
                yield (next(res))
                for cur in res:
                    yield (cur)
                return _('')
            except StopIteration:
                if not combination:
                    return _('')
                combination = combination[:-1]

    @api.multi
    def _get_current_company(self, **kwargs):
        self.ensure_one()
        return self.company_id or self._get_current_company_fallback(**kwargs)

    @api.multi
    def _get_current_company_fallback(self, **kwargs):
        self.ensure_one()
        return self.env.user.company_id

    @api.model
    def get_empty_list_help(self, help):
        self = self.with_context(empty_list_help_document_name=_("product"), )
        return super(ProductTemplate, self).get_empty_list_help(help)

    @api.model
    def get_import_template(self):
        return [{
            'label': _('Import Template for Products'),
            'template': '/product/static/xls/product_template.xls'
        }]
