from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # netfetchs = fields.One2many('netfetch.config', string='Netfetch Config')
