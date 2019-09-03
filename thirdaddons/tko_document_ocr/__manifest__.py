# © 2016 Therp BV <http://therp.nl>
# © 2018 TKOpen <https://tkopen.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    'name': 'OCR for Documents (image and PDF)',
    'category': 'Knowledge Management',
    'author': 'Therp BV,'
              'Odoo Community Association (OCA),'
              'TKOpen',
    'license': 'AGPL-3',
    'website': 'https://tkopen.com',
    'version': '11.0.1.0.0',
    'sequence': 1,
    'summary': 'OCR for text, image and PDF documents',
    'depends': [
        'document',
    ],
    'data': [
        'data/ir_cron.xml',
        'data/ir_config_parameter.xml',
        'views/ir_attachment_view.xml',
    ],
    'external_dependencies': {
        'bin': [
            'tesseract',
            'convert',
            'pdftotext',
            'pdfimages',
        ],
    },
}
