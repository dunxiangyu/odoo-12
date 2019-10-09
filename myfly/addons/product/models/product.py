from odoo.osv import expression

from odoo.exceptions import ValidationError

from odoo import api, models, fields, _, tools
from odoo.tools import pycompat, re, float_compare


class ProductCategory(models.Model):
    _name = 'product.category'
    _description = 'Product Category'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'complete_name'

    name = fields.Char('Name', index=True, required=True, translate=True)
    complete_name = fields.Char('Complete Name', compute='_compute_complete_name', store=True)
    parent_id = fields.Many2one('product.category', 'Parent Category', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True)
    child_id = fields.One2many('product.category', 'parent_id', 'Child Categories')
    product_count = fields.Integer('# Products', compute='_compute_product_count')

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = "%s / %s" % (category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name

    def _compute_product_count(self):
        read_group_res = self.env['product.template'].read_group([('categ_id', 'child_of', self.ids)], ['categ_id'],
                                                                 ['categ_id'])
        group_data = dict((data['categ_id'][0], data['categ_id_count']) for data in read_group_res)
        for categ in self:
            product_count = 0
            for sub_categ_id in categ.search([('id', 'child_of', categ.id)]).ids:
                product_count += group_data.get(sub_categ_id, 0)
            categ.product_count = product_count

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_(''))
        return True

    @api.model
    def name_create(self, name):
        return self.create({'name': name}).name_get()[0]


class ProductPriceHistory(models.Model):
    _name = 'product.price.history'
    _rec_name = 'datetime'
    _order = 'datetime desc'
    _description = 'Product Price List History'

    def _get_default_company_id(self):
        return self._context.get('force_company', self.env.user.company_id.id)

    company_id = fields.Many2one('res.company', string='Company', default=_get_default_company_id, required=True)
    product_id = fields.Many2one('product.product', 'Product', ondelete='cascade', required=True)
    datetime = fields.Datetime('Date', default=fields.Datetime.now)
    cost = fields.Float('Cost')


class ProductProduct(models.Model):
    _name = 'product.template'
    _description = 'Product'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'product.template': 'product_tmpl_id'}
    _order = 'default_code, name, id'

    price = fields.Float('Price', compute='_compute_prodcut_price', inverse='_set_product_price')
    price_extra = fields.Float('Variant Price Extra', compute='_compute_product_price_extra')
    lst_price = fields.Float('Sale Price', compute='_compute_product_lst_price', inverse='_set_product_lst_price')

    default_code = fields.Char('Internal Reference', index=True)
    code = fields.Char('Reference', compute='_compute_product_code')
    partner_ref = fields.Char('Customer Ref', compute='_compute_partner_ref')

    active = fields.Boolean('Active', default=True)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', auto_join=True, index=True,
                                      ondelete="cascade", required=True)
    image_variant = fields.Binary('Variant Image', attachment=True)
    image = fields.Binary('Big-sized image', compute='_compute_images', inverse='_set_image')
    image_small = fields.Binary('Small-sized image', compute='_compute_images', inverse='_set_image_small')
    image_medium = fields.Binary('Medium-sized image', compute='_compute_images', inverse='_set_image_medium')
    is_product_variant = fields.Boolean(compute='_compute_is_product_variant')

    standard_price = fields.Float('Cost', company_dependent=True, groups='base.group_user')
    volume = fields.Float('Volume')
    weight = fields.Float('Weight')

    pricelist_item_ids = fields.Many2many('product.pricelist.item', 'Pricelist Items', compute='_get_pricelist_items')

    packaging_ids = fields.One2many('product.packaging', 'product_id', 'Product Packages')

    _sql_constraints = [
        ('barcode_uniq', 'unqiue(barcode)', '')
    ]

    def _get_invoice_policy(self):
        return False

    def _compute_prodcut_price(self):
        prices = {}
        pricelist_id_or_name = self._context.get('pricelist')
        if pricelist_id_or_name:
            pricelist = None
            partner = self.env.context.get('partner', False)
            quantity = self.env.context.get('quantity', 1.0)

            if isinstance(pricelist_id_or_name, pycompat.string_types):
                pricelist_name_search = self.env['product.pricelist'].name_search(pricelist_id_or_name, operator='=',
                                                                                  limit=1)
                if pricelist_name_search:
                    pricelist = self.env['product.pricelist'].browse([pricelist_name_search[0][0]])
            elif isinstance(pricelist_id_or_name, pycompat.integer_types):
                pricelist = self.env['product.pricelist'].browse(pricelist_id_or_name)

            if pricelist:
                quantities = [quantity] * len(self)
                partners = [partner] * len(self)
                prices = pricelist.get_products_price(self, quantities, partners)

        for product in self:
            product.price = prices.get(product.id, 0.0)

    def _set_product_price(self):
        for product in self:
            if self._context.get('uom'):
                value = self.env['uom.uom'].browse(self._context['uom'])._compute_price(product.price, product.uom_id)
            else:
                value = product.price
            product.write({'list_price': value})

    @api.depends('product_template_attribute_value_ids.price_extra')
    def _compute_product_price_extra(self):
        for product in self:
            product.price_extra = sum(product.mapped('product_template_attribute_value_ids.price_extra'))

    @api.depends('list_price', 'price_extra')
    def _compute_product_lst_price(self):
        to_uom = None
        if 'uom' in self._context:
            to_uom = self.env['uom.uom'].browse([self._context['uom']])

        for product in self:
            if to_uom:
                list_price = product.uom_id._compute_price(product.list_price, to_uom)
            else:
                list_price = product.list_price
            product.lst_price = list_price + product.price_extra

    def _set_product_lst_price(self):
        for product in self:
            if self._context.get('uom'):
                value = self.env['uom.uom'].browse(self._context['uom'])._compute_price(product.lst_price,
                                                                                        product.uom_id)
            else:
                value = product.lst_price
            value -= product.price_extra
            product.write({'list_price': value})

    @api.one
    def _compute_product_code(self):
        for supplier_info in self.seller_ids:
            if supplier_info.name.id == self._context.get('partner_id'):
                self.code = supplier_info.product_code or self.default_code
                break
        else:
            self.code = self.default_code

    @api.one
    def _compute_partner_ref(self):
        for supplier_info in self.seller_ids:
            if supplier_info.name.id == self._context.get('partner_id'):
                product_name = supplier_info.product_name or self.default_code or self.name_get
                self.partner_ref = "%s%s" % (self.code and '[%s] ' % self.code or '', product_name)
                break
        else:
            self.partner_ref = self.name_get()[0][1]

    @api.one
    @api.depends('image_variant', 'product_tmpl_id.image')
    def _compute_images(self):
        if self._context.get('bin_size'):
            self.image_medium = self.image_variant
            self.image_small = self.image_variant
            self.image = self.image_variant
        else:
            resized_images = tools.image_get_resized_images(self.image_variant, return_big=True,
                                                            avoid_resize_medium=True)
            self.image_medium = resized_images['image_medium']
            self.iamge_small = resized_images['image_small']
            self.image = resized_images['image']
        if not self.image_medium:
            self.image_medium = self.product_tmpl_id.image_medium
        if not self.image_small:
            self.image_small = self.product_tmpl_id.image_small
        if not self.image:
            self.image = self.product_tmpl_id.image

    @api.one
    def _set_image(self):
        self._set_image_value(self.image)

    def _set_image_small(self):
        self._set_image_small(self.image_small)

    def _set_image_medium(self):
        self._set_image_medium(self.image_medium)

    @api.one
    def _set_image_value(self, value):
        if isinstance(value, pycompat.text_type):
            value = value.encode('ascii')
        image = tools.image_resize_image_big(value)

        if self.product_tmpl_id.image and self.product_variant_count > 1:
            self.image_variant = image
        else:
            self.image_variant = False
            self.product_tmpl_id.image = image

    def _compute_is_product_variant(self):
        for product in self:
            product.is_product_variant = True

    @api.depends('product_tmpl_id', 'attribute_value_ids')
    def _compute_product_template_attribute_value_ids(self):
        values = self.env['product.template.attribute.value'].search([
            ('product_tmpl_id', 'in', self.mapped('product_tmpl_id').ids),
            ('product_attribute_value_id', 'in', self.mapped('attribute_value_ids').ids),
        ])

        values_per_template = {}
        for ptav in values:
            pt_id = ptav.product_tmpl_id.id
            if pt_id not in values_per_template:
                values_per_template[pt_id] = {}
            values_per_template[pt_id][ptav.product_attribute_value_id.id] = ptav

        for product in self:
            product.product_template_attribute_value_ids = self.env['product.template.attribute.value']
            for pav in product.attribute_value_ids:
                if product.product_tmpl_id.id not in values_per_template or pav.id not in values_per_template[
                    product.product_tmpl_id.id]:
                    continue
                else:
                    product.product_template_attribute_value_ids += values_per_template[product.product_tmpl_id.id][
                        pav.id]

    @api.one
    def _get_pricelist_items(self):
        self.pricelist_item_ids = self.env['product.pricelist.item'].search([
            '|',
            ('product_id', '=', self.id),
            ('product_tmpl_id', '=', self.product_tmpl_id.id)
        ]).ids

    @api.constrains('attribute_value_ids')
    def _check_attribute_value_ids(self):
        for product in self:
            attributes = self.env['product.attribute']
            for value in product.attribute_value_ids:
                if value.attribute_id in attributes:
                    raise ValidationError(_(''))
                if value.attribute_id.create_variant == 'always':
                    attributes |= value.attribute_id
        return True

    @api.onchange('uom_id', 'uom_po_id')
    def _onchange_uom(self):
        if self.uom_id and self.uom_po_id and self.uom_id.category_id != self.uom_po_id.category_id:
            self.uom_po_id = self.uom_id

    @api.model_create_multi
    def create(self, vals_list):
        products = super(ProductProduct, self.with_context(create_product_product=True)).create(vals_list)
        for product, vals in pycompat.izip(products, vals_list):
            if not (self.env.context.get('create_from_tmpl') and len(product.product_tmpl_id.product_variant_ids) == 1):
                product._set_standard_price(vals.get('standard_price') or 0.0)
        self.clear_caches()
        self.env['product.template'].invalidate_cache(
            fnames=[
                'valid_archived_variant_ids',
                'valid_existing_variant_ids',
                'product_variant_ids',
                'product_variant_id',
                'product_variant_count',
            ],
            ids=products.mapped('product_tmpl_id').ids
        )
        return products

    @api.multi
    def write(self, values):
        res = super(ProductProduct, self).write(values)
        if 'standard_price' in values:
            self._set_standard_price(values['standard_price'])
        if 'attribute_value_ids' in values:
            self.clear_caches()
        if 'active' in values:
            self.invalidate_cache()
            self.clear_caches()
        return res

    @api.multi
    def unlink(self):
        unlink_products = self.env['product.product']
        unlink_templates = self.env['product.template']
        for product in self:
            if not product.exists():
                continue
            other_products = self.search(
                [('product_tmpl_id', '=', product.product_tmpl_id.id), ('id', '!=', product.id)])
            if not other_products and not product.product_tmpl_id.has_dynamic_attributes():
                unlink_templates |= product.product_tmpl_id
            unlink_products |= product
        res = super(ProductProduct, unlink_products).unlink()
        unlink_templates.unlink()
        self.clear_caches()
        return res

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        if default is None:
            default = {}
        if self._context.get('variant'):
            default['product_tmpl_id'] = self.product_tmpl_id
        elif 'name' not in default:
            default['name'] = self.name

        return super(ProductProduct, self).copy(default=default)

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if self._context.get('search_default_categ_id'):
            args.append((('categ_id', 'child_of', self._context['search_default_categ_id'])))
        return super(ProductProduct, self)._search(args, offset, limit, order, count, access_rights_uid)

    @api.multi
    def name_get(self):
        def _name_get(d):
            name = d.get('name', '')
            code = self._context.get('display_default_code', True) and d.get('default_code', False) or False
            if code:
                name = '[%s] %s' % (code, name)
            return (d['id'], name)

        partner_id = self._context.get('partner_id')
        if partner_id:
            partner_ids = [partner_id, self.env['res.partner'].browse(partner_id).commercial_partner_id.id]
        else:
            partner_ids = []

        self.check_access_rights('read')
        self.check_access_rule('read')

        result = []

        self.sudo().read(['name', 'default_code', 'product_tmpl_id', 'attribute_value_ids', 'attribute_line_ids'],
                         load=False)

        product_template_ids = self.sudo().mapped('product_tmpl_id').ids

        if partner_ids:
            supplier_info = self.env['product.supplierinfo'].sudo().search([
                ('product_tmpl_id', 'in', product_template_ids),
                ('name', 'in', partner_ids),
            ])
            supplier_info.sudo().read(['product_tmpl_id', 'product_id', 'product_name', 'product_code'], load=False)
            supplier_info_by_template = {}
            for r in supplier_info:
                supplier_info_by_template.setdefault(r.product_tmpl_id, []).append(r)
        for product in self.sudo():
            variable_attributes = product.attribute_line_ids.filtered(lambda l: len(l.value_ids) > 1).mapped(
                'attribute_id')
            variant = product.attribute_value_ids._variant_name(variable_attributes)

            name = variant and "%s (%s)" % (product.name, variant) or product.name
            sellers = []
            if partner_ids:
                product_supplier_info = supplier_info_by_template.get(product.product_tmpl_id, [])
                sellers = [x for x in product_supplier_info if x.product_id and x.product_id == product]
                if not sellers:
                    sellers = [x for x in product_supplier_info if not x.product_id]
            if sellers:
                for s in sellers:
                    seller_variant = s.product_name and (
                            variant and "%s (%s)" % (s.product_name, variant) or s.product_name) or False
                    mydict = {
                        'id': product.id,
                        'name': seller_variant or name,
                        'default_code': s.product_code or product.default_code,
                    }
                    temp = _name_get(mydict)
                    if temp not in result:
                        result.append(temp)
            else:
                mydict = {
                    'id': product.id,
                    'name': name,
                    'default_code': product.default_code,
                }
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if not args:
            args = []
        if name:
            positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
            product_ids = []
            if operator in positive_operators:
                product_ids = self._search([('default_code', '=', name)] + args, limit=limit,
                                           access_rights_uid=name_get_uid)
                if not product_ids:
                    product_ids = self._search([('barcode', '=', name)] + args, limit=limit,
                                               access_rights_uid=name_get_uid)
            if not product_ids and operator not in expression.NEGATIVE_TERM_OPERATORS:
                product_ids = self._search(args + [('default_code', operator, name)], limit=limit)
                if not limit or len(product_ids) < limit:
                    limit2 = (limit - len(product_ids)) if limit else False
                    product2_ids = self._search(args + [('name', operator, name), ('id', 'not in', product_ids)],
                                                limit=limit2, access_rights_uid=name_get_uid)
                    product_ids.extend(product2_ids)
            elif not product_ids and operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = expression.OR([
                    ['&', ('default_code', operator, name), ('name', operator, name)],
                    ['&', ('default_code', '=', False), ('name', operator, name)],
                ])
                domain = expression.AND([args, domain])
                product_ids = self._search(domain, limit=limit, access_rights_uid=name_get_uid)
            if not product_ids and operator in positive_operators:
                ptrn = re.compile('(\[(.*?)\])')
                res = ptrn.search(name)
                if res:
                    product_ids = self._search([('default_code', '=', res.group(2))] + args, limit=limit,
                                               access_rights_uid=name_get_uid)
            if not product_ids and self._context.get('partner_id'):
                supplier_ids = self.env['product.supplierinfo']._search([
                    ('name', '=', self._context.get('partner_id')),
                    '|',
                    ('product_code', operator, name),
                    ('product_name', operator, name)
                ], access_rights_uid=name_get_uid)
                if supplier_ids:
                    product_ids = self._search([('product_tmpl_id.seller_ids', 'in', supplier_ids)], limit=limit,
                                               access_rights_uid=name_get_uid)
        else:
            product_ids = self._search(args, limit=limit, access_rights_uid=name_get_uid)
        return self.browse(product_ids).name_get()

    @api.model
    def view_header_get(self, view_id=None, view_type='form'):
        res = super(ProductProduct, self).view_header_get(view_id, view_type)
        if self._context.get('categ_id'):
            return _('Products: ') + self.env['product.category'].browse(self._context['categ_id']).name
        return res

    @api.multi
    def open_product_template(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'form',
            'res_id': self.product_tmpl_id.id,
            'target': 'new',
        }

    def _prepare_sellers(self, params):
        return self.seller_ids

    @api.multi
    def _select_seller(self, partner_id=False, quantity=0.0, date=None, uom_id=False, params=False):
        self.ensure_one()
        if date in None:
            date = fields.Date.context_today(self)
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        res = self.env['product.supplierinfo']
        sellers = self._prepare_sellers(params)
        if self.env.context.get('force_company'):
            sellers = sellers.filtered(
                lambda s: not s.company_id or s.company_id.id == self.env.context['force_company'])
        for seller in sellers:
            quantity_uom_seller = quantity
            if quantity_uom_seller and uom_id and uom_id != seller.product_uom:
                quantity_uom_seller = uom_id._compute_quantity(quantity_uom_seller, seller.product_uom)

            if seller.date_start and seller.date_start > date:
                continue
            if seller.date_end and seller.date_end < date:
                continue
            if partner_id and seller.name not in [partner_id, partner_id.parent_id]:
                continue
            if float_compare(quantity_uom_seller, seller.min_qty, precision_digits=precision) == -1:
                continue
            if seller.product_id and seller.product_id != self:
                continue

            res |= seller
            break
        return res

    @api.multi
    def price_compute(self, price_type, uom=False, currency=False, company=False):
        if not uom and self._context.get('uom'):
            uom = self.env['uom.uom'].get('uom')
        if not currency and self._context.get('currency'):
            currency = self.env['res.currency'].browse(self._context['currency'])

        products = self
        if price_type == 'standard_price':
            products = self.with_context(force_company=company and company.id or self._context.get('force_company',
                                                                                                   self.env.user.company_id.id)).sudo()

        prices = dict.fromkeys(self.ids, 0.0)
        for product in products:
            prices[product.id] = product[price_type] or 0.0
            if price_type == 'list_price':
                prices[product.id] += product.price_extra
                if self._context.get('no_variant_attriubtes_price_extra'):
                    prices[product.id] += sum(self._context.get('no_variant_attriubtes_price_extra'))

            if uom:
                prices[product.id] = product.uom_id.compute_price(prices[product.id], uom)

            if currency:
                prices[product.id] = product.currency_id._convert(prices[product.id], currency, product.company_id,
                                                                  fields.Date.today())

        return prices

    @api.multi
    def price_get(self, ptype='list_price'):
        return self.price_compute(ptype)

    @api.multi
    def _set_standard_price(self, value):
        PriceHistory = self.env['product.price.history']
        for product in self:
            PriceHistory.create({
                'product_id': product.id,
                'cost': value,
                'company_id': self._context.get('force_company', self.env.user.company_id.id),
            })

    @api.multi
    def get_history_price(self, company_id, date=None):
        history = self.env['product.price.history'].search([
            ('company_id', '=', company_id),
            ('product_id', 'in', self.ids),
            ('datetime', '<=', date or fields.Datetime.now())
        ], order='datetime desc, id desc', limit=1)
        return history.cost or 0.0

    @api.model
    def get_empty_list_help(self, help):
        self = self.with_context(
            empty_list_help_document_name=_('product')
        )
        return super(ProductProduct, self).get_empty_list_help(help)

    def get_product_multiline_description_sale(self):
        name = self._compute_display_name
        if self.description_sale:
            name += '\n' + self.description_sale
        return name

    def _has_valid_attributes(self, valid_attributes, valid_values):
        self.ensure_one()
        values = self.attribute_value_ids
        attributes = values.mapped('attribute_id')
        if attributes != valid_attributes:
            return False
        for value in values:
            if value not in valid_values:
                return False
        return True

    @api.multi
    def _is_variant_possible(self, parent_combination=None):
        self.ensure_one()
        return self.product_tmpl_id._is_combination_possible(self.product_template_attribute_value_ids,
                                                             parent_combination=parent_combination)


class ProductPakcaging(models.Model):
    _name = 'product.packaging'
    _description = 'Product Packaging'
    _order = 'sequence'

    name = fields.Char('Packaging Type', required=True)
    sequence = fields.Integer('Sequence', default=1)
    product_id = fields.Many2one('product.product', string='Product')
    qty = fields.Float('Contained Quantity')
    barcode = fields.Char('Barcode', copy=False)
    product_uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', readonly=True)


class SupplierInfo(models.Model):
    _name = 'product.supplierinfo'
    _description = 'Supplier Pricelist'
    _order = 'sequence, min_qty desc, price'

    name = fields.Many2one('res.partner', 'Vendor', domain=[('supplier', '=', True)], ondelete='cascade', required=True)
    product_name = fields.Char('Vendor Product Name')
    product_code = fields.Char('Vendor Product Code')
    sequence = fields.Integer('Sequence', default=1)
    product_uom = fields.Many2one('uom.uom', 'Unit of Measure', related='product_tmpl_id.uom_po_id')
    min_qty = fields.Float('Minimal Quantity', default=0.0, required=True)
    price = fields.Float('Price', default=0.0, required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id.id, index=1)
    currency_id = fields.Many2one('res.currency', 'Currency',
                                  default=lambda self: self.env.user.company_id.currency_id.id, required=True)
    date_start = fields.Date('Start Date')
    date_end = fields.Date('End Date')
    product_id = fields.Many2one('product.product', 'Product Variant')
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', index=True, ondelete='cascade',
                                      oldname='product_id')
    product_variant_count = fields.Integer('Variant Count', related='product_tmpl_id.product_variant_count',
                                           readonly=True)
    delay = fields.Integer('Delivery Lead Time', default=1, required=True)

    @api.model
    def get_import_templates(self):
        return [{
            'label': _('Import Template for Vendor Pricelists'),
            'template': '/product/static/xls/product_supplierinfo.xls',
        }]
