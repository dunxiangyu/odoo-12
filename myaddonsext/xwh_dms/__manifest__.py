# -*- coding: utf-8 -*-
{
    'name': "xwh_dms",

    'summary': """
        Document Managements""",

    'description': """
        ir_attachment add directory, tag
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Document Management',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'document'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/tag_views.xml',
        'views/directory_views.xml',
        'views/ir_attachment_views.xml',
        'views/menus.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
}