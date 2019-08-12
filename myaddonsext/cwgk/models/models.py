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


class Xmjjmx(models_ext.ExtModel):
    _name = 'cwgk.xmjjmx'
    _description = '项目奖金明细'
    _ext_system = 'system2'

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
    currency_id = fields.Many2one('res.currency', 'Currency',
                                  default=lambda self: self.env.user.company_id.currency_id.id)
    current_pay = fields.Monetary('当前月薪')


class XmjjMaster(models_ext.ExtModel):
    _name = 'cwgk.xmjj.master'
    _description = '项目奖金单'
    _ext_system = 'system2'

    name = fields.Char('Name', default='New', copy=False)
    jj_month = fields.Integer('奖金月份', default=201906)
    department_id = fields.Many2one('cwgk.department', string='部门')
    detail_ids = fields.One2many('cwgk.xmjj.detail', 'master_id', string='明细', copy=True)
    state = fields.Selection([('draft', '草稿'), ('to approve', 'To Approve'), ('done', '完成'), ('cancel', 'Cancelled')],
                             string='状态', default='draft')
    currency_id = fields.Many2one('res.currency', 'Currency',
                                  default=lambda self: self.env.user.company_id.currency_id.id)
    total_pay = fields.Monetary(string='月薪总额', store=True, readonly=True, compute='_compute_total_pay')
    total_jj = fields.Monetary(string='奖金总额', store=True, readonly=True, compute='_compute_total_jj')

    @api.depends('detail_ids.current_pay')
    def _compute_total_pay(self):
        for master in self:
            total_pay = 0.0
            for detail in master.detail_ids:
                total_pay += detail.current_pay
            master.write({'total_pay': total_pay})

    @api.depends('detail_ids.jj')
    def _compute_total_jj(self):
        for master in self:
            total_jj = 0.0
            for detail in master.detail_ids:
                total_jj += detail.jj
            master.write({'total_jj': total_jj})

    @api.multi
    def button_cancel(self):
        self.write({'state': 'cancel'})

    @api.multi
    def button_done(self):
        self.write({'state': 'done'})

    @api.multi
    def button_draft(self):
        self.write({'state': 'draft'})

    @api.multi
    def button_submit(self):
        self.write({'state': 'to approve'})

    @api.multi
    def button_approve(self):
        self.write({'state', 'to approve'})

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('cwgk.xmjjd') or '/'
        return super(XmjjMaster, self).create(vals)

    @api.onchange('department_id')
    def onchange_department_id(self):
        result = {}
        if not self.department_id:
            return result
        # result['domain'] = {
        #     'detail_ids': [
        #         ('department_id', '=', self.department_id.id)
        #     ]
        # }
        rs = self.env['cwgk.employee'].search([('department_id', '=', self.department_id.id)])
        self.detail_ids = [{'employee_id': id} for id in rs.ids]
        return result


class XmjjDetail(models_ext.ExtModel):
    _name = 'cwgk.xmjj.detail'
    _description = '项目奖金明细'
    _ext_system = 'system2'

    master_id = fields.Many2one('cwgk.xmjj.master')
    employee_id = fields.Many2one('cwgk.employee', '员工')
    employee_name = fields.Char('姓名', related='employee_id.name', store=False)
    department_name = fields.Char('部门', related='employee_id.department_id.name', store=False)
    post = fields.Char('岗位', related='employee_id.post', store=False)
    currency_id = fields.Many2one('res.currency', string='Currency', related='employee_id.currency_id')
    current_pay = fields.Monetary('当前月薪', related='employee_id.current_pay', store=False)
    jj = fields.Monetary('奖金')

    @api.onchange('employee_id')
    def onchange_employee_id(self):
        result = {}
        if not self.employee_id:
            return result
        # else:
        #     result['warning'] = {
        #         'title': 'warning',
        #         'message': 'this is a warning.'
        #     }
        self.employee_name = self.employee_id.name
        self.department_name = self.employee_id.department_id.name
        self.post = self.employee_id.post
        self.current_pay = self.employee_id.current_pay
        self.currency_id = self.employee_id.currency_id
        return result
