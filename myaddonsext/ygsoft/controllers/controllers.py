# -*- coding: utf-8 -*-
from odoo import http

# class Ygsoft(http.Controller):
#     @http.route('/ygsoft/ygsoft/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ygsoft/ygsoft/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('ygsoft.listing', {
#             'root': '/ygsoft/ygsoft',
#             'objects': http.request.env['ygsoft.ygsoft'].search([]),
#         })

#     @http.route('/ygsoft/ygsoft/objects/<model("ygsoft.ygsoft"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ygsoft.object', {
#             'object': obj
#         })