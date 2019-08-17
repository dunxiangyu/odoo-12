# -*- coding: utf-8 -*-
from odoo import http

# class Study(http.Controller):
#     @http.route('/study/study/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/study/study/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('study.listing', {
#             'root': '/study/study',
#             'objects': http.request.env['study.study'].search([]),
#         })

#     @http.route('/study/study/objects/<model("study.study"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('study.object', {
#             'object': obj
#         })