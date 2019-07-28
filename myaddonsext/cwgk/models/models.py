# -*- coding: utf-8 -*-

from myfly import models_ext
from odoo import fields, api


class Xtgldxlx(models_ext.ExtModel):
    _name = 'cwgk.xtgldxlx'
    _description = '管理对象类型'
    _ext_system = 'system2'
    _table = 'xtgldxlx'

    dxlxid = fields.Char('对象类型ID')
    name = fields.Char('对象类型名称')
    value = fields.Integer()
    value2 = fields.Float(compute="_value_pc", store=True)

    @api.depends('value')
    def _value_pc(self):
        self.value2 = float(self.value) / 100
