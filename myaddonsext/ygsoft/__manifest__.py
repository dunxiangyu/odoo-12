# -*- coding: utf-8 -*-
{
    'name': "ygsoft",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'contacts', 'hr', 'hr_org_chart'],

    # always loaded
    'data': [
        'views/views.xml',
        'views/templates.xml',
        'security/ygsoft_security.xml',
        'data/ir_mail_server_data.xml',
        'data/res_partner_data.xml',
        'data/res_company_data.xml',
        'data/res_users_data.xml',
        'data/hr_employee_data.xml',
        'data/hr_department_data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
