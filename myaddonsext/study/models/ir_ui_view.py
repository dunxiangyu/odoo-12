from odoo import models, fields


class View(models.Model):
    _inherit = 'ir.ui.view'

    type = fields.Selection(selection_add=[('myview', 'My View')])
