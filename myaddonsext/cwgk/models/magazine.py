from odoo import fields, models, api
from myfly import models_ext


class Magazine(models.Model):
    _name = 'cwgk.magazine'
    _description = 'Magazine'
    #_ext_system = 'system2'

    # 年度	报刊代号	报刊名称	是否主办	刊期种类	出版日期	发报刊局	级别	收订种类
    # 订阅参考单价	月价	季价	半年价	全年价	报刊种类	直封份数	凭证订阅方式	报刊简介	产品分类	整捆规格	发行限制
    year = fields.Integer('年度')
    code = fields.Char('报刊代号')
    name = fields.Char('报刊名称')
    is_master = fields.Char('是否主办')
    category = fields.Char('刊期种类')
    pub_date = fields.Char('出版日期')
    pub_post = fields.Char('发报刊局')
    level = fields.Char('级别')
    sdzl = fields.Char('收订种类')
    price = fields.Float('订阅参考单价')
    month_price = fields.Float('月价')
    quautor_price = fields.Float('季价')
    halfyear_price = fields.Float('半年价')
    year_price = fields.Float('全年价')
    zl = fields.Char('报刊种类')
    zffs = fields.Char('直封份数')
    pzdyfs = fields.Char('凭证订阅方式')
    bkjj = fields.Char('报刊简介')
    product_class = fields.Char('产品分类')
    gg = fields.Char('整捆规格')
    fxxz = fields.Char('发行限制')
