# -*- coding: utf-8 -*-
import os
from odoo import models, fields, api
from . import utils


class FetchConfig(models.Model):
    _name = 'xwh_dms.fetch.config'
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
    root_directory_id = fields.Many2one('xwh_dms.directory', 'Root Directory', required=True)
    dir_tags = fields.Boolean('按目录建立标签', default=True)

    @api.multi
    def fetch(self):
        for conf in self:
            if conf['type'] == 'local':
                self.fetch_local(conf['path'], conf)

    def fetch_local(self, rootpath, conf):
        model = self.env['ir.attachment']
        directories = dict()
        for parent, dirnames, filenames in os.walk(rootpath):
            for filename in filenames:
                fullpath = os.path.join(parent, filename)
                fileinfo = utils.get_file_info(rootpath, fullpath)
                directory_id = directories.get(fileinfo['file_path'])
                if not directory_id:
                    directory_id = self.env['xwh_dms.directory'].get_or_create_directories(conf['root_directory_id'].id,
                                                                                           fileinfo['file_path'])
                    directories.setdefault(fileinfo['file_path'], directory_id)
                print('process %s, %s' % (fullpath, fileinfo))
                self.get_or_create_attachment(model, fileinfo, conf, directory_id)

    def get_or_create_attachment(self, model, fileinfo, conf, directory_id):
        rs = model.search([('datas_fname', '=', fileinfo['file_name']), ('directory_id', '=', directory_id)])
        if len(rs) == 0:
            # file not exists
            rec = model.create({
                'name': fileinfo['name'],
                'datas_fname': fileinfo['file_name'],
                'directory_id': directory_id,
                'datas': utils.get_file_content(fileinfo['fullpath']),
                'company_id': conf['company_id'].id
            })
        elif len(rs) == 1:
            # file exists
            if rs[0].file_size != fileinfo['file_size']:
                # file changed, need reupdate
                rec = model.write({
                    'datas': utils.get_file_content(fileinfo['fullpath']),
                })
        return rec
