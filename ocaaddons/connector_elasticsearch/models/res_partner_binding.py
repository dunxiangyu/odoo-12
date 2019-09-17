from odoo import api, models, fields


class ResPartnerBinding(models.Model):
    _name = 'res.partner.binding'
    _inherit = 'se.binding'
