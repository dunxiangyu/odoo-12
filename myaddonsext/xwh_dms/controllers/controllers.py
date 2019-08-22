# -*- coding: utf-8 -*-
from odoo import http

# class XwhDocument(http.Controller):
#     @http.route('/xwh_document/xwh_document/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/xwh_document/xwh_document/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('xwh_document.listing', {
#             'root': '/xwh_document/xwh_document',
#             'objects': http.request.env['xwh_document.xwh_document'].search([]),
#         })

#     @http.route('/xwh_document/xwh_document/objects/<model("xwh_document.xwh_document"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('xwh_document.object', {
#             'object': obj
#         })