# -*- coding: utf-8 -*-

from myfly import models_ext
from odoo import fields, api, models


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

    @api.multi
    def write(self, vals):
        return super(Xtgldxlx, self).write(vals)

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        return super(Xtgldxlx, self).read(fields, load)

class Xmjjmx(models.Model):
    _name = 'cwgk.xmjjmx'
    _description = '项目奖金明细'
    # _ext_system = 'system2'

    number = fields.Integer('工号')
    name = fields.Char('姓名')
    department_name = fields.Char('部门')
    sub_department_name = fields.Char('二级部门')
    post = fields.Char('岗位')
    rz_date = fields.Date('入职日期')
    zz_date = fields.Date('转正日期')
    current_pay = fields.Float('当前月薪')
    jj_month = fields.Char('月份')
    js_jj = fields.Float('奖金基数')
    jj = fields.Float('奖金')

class Department(models_ext.ExtModel):
    _name = 'cwgk.department'
    _description = '部门'
    _ext_system = 'system2'

    name = fields.Char('名称')
    parent_id = fields.Many2one('cwgk.department')
    parent_name = fields.Char('上级部门', related='parent_id.name')
    child_ids = fields.One2many('cwgk.department', 'parent_id')


class Employee(models_ext.ExtModel):
    _name = 'cwgk.employee'
    _description = '员工'
    _ext_system = 'system2'

    number = fields.Integer('工号')
    name = fields.Char('姓名')
    department_id = fields.Many2one('cwgk.department', string='部门')
    department_name = fields.Char('部门', related='department_id.name')
    parent_department_name = fields.Char('上级部门', related='department_id.parent_id.name')
    post = fields.Char('岗位')
    rz_date = fields.Date('入职日期')
    zz_date = fields.Date('转正日期')
    current_pay = fields.Float('当前月薪')


class XmjjMaster(models_ext.ExtModel):
    _name = 'cwgk.xmjj.master'
    _description = '项目奖金'
    _ext_system = 'system2'

    jj_month = fields.Integer('奖金月份')
    department_id = fields.Many2one('cwgk.department', string='部门')
    detail_ids = fields.One2many('cwgk.xmjj.detail', 'master_id', string='明细', copy=True)


class XmjjDetail(models_ext.ExtModel):
    _name = 'cwgk.xmjj.detail'
    _description = '项目奖金明细'
    _ext_system = 'system2'

    master_id = fields.Many2one('cwgk.xmjj.master')
    employee_id = fields.Many2one('cwgk.employee', '员工')
    employee_name = fields.Char('姓名', related='employee_id.name', store=False)
    department_name = fields.Char('部门', related='employee_id.department_id.name', store=False)
    post = fields.Char('岗位', related='employee_id.post', store=False)
    current_pay = fields.Float('当前月薪', related='employee_id.current_pay', store=False)
    jj = fields.Float('奖金')



