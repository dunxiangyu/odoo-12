import dp as dp
from odoo.osv import expression

from odoo.exceptions import UserError, ValidationError

from odoo import api, fields, models, _


class ProductAttribute(models.Model):
    _name = 'product.attribute'
    _description = 'Product Attribute'
    _order = 'sequence, id'

    name = fields.Char('Attribute', required=True, translate=True)
    value_ids = fields.One2many('product.attribute.value', 'attribute_id', 'Values', copy=True)
    sequence = fields.Integer('Sequence', index=True)
    attribute_line_ids = fields.One2many('product.template.attribute.line', 'attribute_id', 'Lines')
    create_variant = fields.Selection([
        ('no_variant', 'Never'),
        ('always', 'Always'),
        ('dynamic', 'Only when the product is added to a sales order'),
    ], default='always', string='Create Variants', required=True)

    @api.multi
    def _without_no_variant_attributes(self):
        return self.filtered(lambda pa: pa.create_variant != 'no_variant')

    @api.multi
    def write(self, vals):
        if 'create_variant' in vals:
            products = self._get_related_product_templates()
            if products:
                message = ', '.join(products.mapped('name'))
                raise UserError(_(''))
        invalidate_cache = 'sequence' in vals and any(record.sequence != vals['sequence'] for record in self)
        res = super(ProductAttribute, self).write(vals)
        if invalidate_cache:
            self.invalidate_cache()
        return res

    @api.multi
    def _get_related_product_templates(self):
        return self.env['product.template'].with_context(active_test=False).search([
            ('attribute_line_ids.attribute_id', 'in', self.ids)
        ])


class ProductAttributeValue(models.Model):
    _name = 'product.attribute.value'
    _order = 'attribute_id, sequence, id'
    _description = 'Attribute Value'

    name = fields.Char(string='Value', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', index=True)
    attribute_id = fields.Many2one('product.attribute', string='Attribute', ondelete='cascade', required=True,
                                   index=True)

    _sql_constraints = [
        ('value_company_uniq', 'unique(name, attribute_id)', 'This attribute value already exists !')
    ]

    @api.multi
    def name_get(self):
        if not self._context.get('show_attribute', True):
            return super(ProductAttributeValue, self).name_get()
        return [(value.id, "%s: %s" % (value.attribute_id.name, value.name)) for value in self]

    @api.multi
    def _variant_name(self, variable_attributes):
        return ", ".join([v.name for v in self if v.attribute_id in variable_attributes])

    @api.multi
    def write(self, values):
        invalidate_cache = 'sequence' in values and any(record.sequence != values['sequence'] for record in self)
        res = super(ProductAttributeValue, self).write(values)
        if invalidate_cache:
            self.invalidate_cache()
        return res

    @api.multi
    def unlink(self):
        linked_products = self._get_related_product_templates()
        if linked_products:
            raise UserError(_(''))
        return super(ProductAttributeValue, self).unlink()

    @api.multi
    def _without_no_variant_attributes(self):
        return self.filtered(lambda v: v.attribute_id.create_variant != 'no_variant')

    @api.multi
    def _get_related_product_templates(self):
        return self.env['product.template'].with_context(active_test=False).search({
            ('attribute_line_ids.value_ids', 'in', self.ids)
        })


class ProductTemplateAttributeLine(models.Model):
    _name = 'product.template.attribute.line'
    _rec_name = 'attribute_id'
    _description = 'Product Template Attribute Line'
    _order = 'attribute_id, id'

    product_tmpl_id = fields.Many2one('product.template', string='Product Template', ondelete='cascade', required=True,
                                      index=True)
    attribute_id = fields.Many2one('product.attribute', string='Attribute', ondelete='restrict', required=True,
                                   index=True)
    value_ids = fields.Many2many('product.attribute.value', string='Attribute Values')
    product_template_value_ids = fields.Many2many('product.template.attribute.value', string='Product Attribute Values',
                                                  compute='_set_product_template_value_ids', store=False)

    @api.constrains('value_ids', 'attribute_id')
    def _check_valid_attribute(self):
        if any(not line.value_ids or line.value_ids > line.attriubte_id.value_ids for line in self):
            raise ValidationError(_(''))
        return True

    @api.model
    def create(self, values):
        res = super(ProductTemplateAttributeLine, self).create(values)
        res._update_product_template_attribute_values()
        return res

    def write(self, values):
        res = super(ProductTemplateAttributeLine, self).write(values)
        self._update_product_template_attribute_values()
        return res

    @api.depends('value_ids')
    def _set_product_template_value_ids(self):
        for product_template_attribute_line in self:
            product_template_attribute_line.product_template_value_ids = self.env[
                'product.template.attribute.value'].search([
                ('product_tmpl_id', 'in', product_template_attribute_line.product_tmpl_id.ids),
                ('product_attribute_value_id', 'in', product_template_attribute_line.value_ids.ids)
            ])

    @api.multi
    def unlink(self):
        for product_template_attribute_line in self:
            self.env['product.template.attribute.value'].search([
                ('product_tmpl_id', 'in', product_template_attribute_line.product_tmpl_id.ids),
                ('product_attribute_value_id', 'in', product_template_attribute_line.value_ids.ids)
            ])

    def _update_product_template_attribute_values(self):
        for attribute_line in self:
            product_template_attribute_values_to_remove = self.env['product.template.attribute.value'].search([
                ('product_tmpl_id', '=', attribute_line.product_tmpl_id.id),
                ('product_attribute_value_id.attribute_id', 'in', attribute_line.value_ids.mapped('attribute_id').ids)
            ])
            existing_product_attribute_values = product_template_attribute_values_to_remove.mapped(
                'product_attribute_value_id')
            for product_attribute_value in attribute_line.value_ids:
                if product_attribute_value in existing_product_attribute_values:
                    product_template_attribute_values_to_remove = product_template_attribute_values_to_remove.filtered(
                        lambda value: product_attribute_value not in value.mapped('product_attribute_value_id')
                    )
                else:
                    self.env['product.template.attribute.value'].create({
                        'product_attriubte_value_id': product_attribute_value.id,
                        'product_tmpl_id': attribute_line.product_tmpl_id.id
                    })
            if product_template_attribute_values_to_remove:
                product_template_attribute_values_to_remove.unlink()

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
            args = args or []
            domain = ['|', ('attribute_id', operator, name), ('value_ids', operator, name)]
            attribute_ids = self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
            return self.browse(attribute_ids).name_get()
        return super(ProductTemplateAttributeLine, self)._name_search(name, args, operator, limit, name_get_uid)

    @api.multi
    def _without_no_variant_attributes(self):
        return self.filtered(lambda v: v.attribute_id.create_variant != 'no_variant')


class ProductTemplateAttributeValue(models.Model):
    _name = 'product.template.attribute.value'
    _order = 'product_attribute_value_id, id'
    _description = 'Product Attribute Value'

    product_attribute_value_id = fields.Many2one('product.attribute.value', string='Attribute Value', required=True,
                                                 ondelete='cascade', index=True)
    name = fields.Char('Value', related='product_attribute_value_id.name')
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', required=True, ondelete='cascade',
                                      index=True)
    attribute_id = fields.Many2one('product.attribute', string='Attribute',
                                   related='product_attribute_value_id.attribute_id')
    sequence = fields.Integer('Sequence', related='product_attribute_value_id.sequence')
    price_extra = fields.Float(string='Attribute Price Extra', default=0.0, digits=dp.get_precision('Product Price'))
    exclude_for = fields.One2many('product.template.attribute.exclusion', 'product_template_attribute_value_id',
                                  string='Exclude for', relation='product_template_attribute_exclusion')

    @api.multi
    def name_get(self):
        if not self._context.get('show_attribute', True):
            return super(ProductTemplateAttributeValue, self).name_get()
        return [(value.id, "%s: %s" % (value.attribute_id.name, value.name)) for value in self]

    @api.multi
    def _without_no_variant_attributes(self):
        return self.filtered(lambda v: v.attribute_id.create_variant != 'no_variant')


class ProductTemplateAttributeExclusion(models.Model):
    _name = 'product.template.attribute.exclusion'
    _description = 'Product Template Attribute Exclusion'

    product_template_attribute_value_id = fields.Many2one('product.template.attribute.value', string='Attribute Value',
                                                          ondelete='cascade', index=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', ondelete='cascade', required=True,
                                      index=True)
    value_ids = fields.Many2many('product.template.attribute.value', relation='product_attr_exclusion_value_ids_rel',
                                 string='Attriubte Values', domain="[('product_tmpl_id','=',product_tmpl_id)]")
