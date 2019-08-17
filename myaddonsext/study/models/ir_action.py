from odoo import models, fields


class ActionModel(models.Model):
    _inherit = 'ir.actions.act_window.view'

    view_mode = fields.Selection(selection_add=[('myview', 'My View')])
