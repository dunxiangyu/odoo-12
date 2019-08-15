# -*- coding: utf-8 -*-
import os
import base64
from odoo import models, fields, api


class Slide(models.Model):
    _inherit = 'slide.slide'

    path = fields.Char('Path')


class NetfetchConfig(models.Model):
    _name = 'netfetch.config'
    _description = 'net fetch config'

    company_id = fields.Many2one('res.company', 'Company', required=True)
    name = fields.Char('Name')
    type = fields.Selection([
        ('local', 'Local'),
        ('smb', 'SMB'),
        ('ftp', 'FTP'),
        ('http', 'HTTP')
    ], 'Type', required=True)
    host = fields.Char('Host')
    port = fields.Integer('Port')
    path = fields.Char('Path')
    user = fields.Char('User')
    password = fields.Char('Password')
    channel_id = fields.Many2one('slide.channel', string="Channel", required=True)

    @api.multi
    def fetch(self):
        for conf in self:
            if conf['type'] == 'local':
                self.fetch_local(conf['path'])

    def to_fileinfo(self, rootpath, fullpath):
        return {
            'name': '',
            'path': ''
        }

    def fetch_local(self, rootpath):
        for parent, dirnames, filenames in os.walk(rootpath):
            for filename in filenames:  # 输出文件信息
                fullpath = os.path.join(parent, filename)
                fileinfo = self.to_fileinfo(rootpath, fullpath)

                fileinfo = os.stat(fullpath)
                print('process %s, %s' % (fullpath, fileinfo))
                file = open(fullpath, mode='rb')
                datas = base64.encodestring(file.read())
                file.close()
                self.save_file(fileinfo, datas)

    def save_file(self, fileinfo, datas):
        pass
