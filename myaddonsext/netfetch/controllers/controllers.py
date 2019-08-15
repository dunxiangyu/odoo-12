# -*- coding: utf-8 -*-
from odoo import http

# class Netfetch(http.Controller):
#     @http.route('/netfetch/netfetch/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/netfetch/netfetch/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('netfetch.listing', {
#             'root': '/netfetch/netfetch',
#             'objects': http.request.env['netfetch.netfetch'].search([]),
#         })

#     @http.route('/netfetch/netfetch/objects/<model("netfetch.netfetch"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('netfetch.object', {
#             'object': obj
#         })