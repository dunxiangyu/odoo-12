# -*- coding: utf-8 -*-
from odoo import http

# class Cwgk(http.Controller):
#     @http.route('/cwgk/cwgk/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/cwgk/cwgk/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('cwgk.listing', {
#             'root': '/cwgk/cwgk',
#             'objects': http.request.env['cwgk.cwgk'].search([]),
#         })

#     @http.route('/cwgk/cwgk/objects/<model("cwgk.cwgk"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('cwgk.object', {
#             'object': obj
#         })