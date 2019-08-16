# -*- coding: utf-8 -*-
import os
import base64
from odoo import models, fields, api
import os.path


def get_slide_type(file_ext):
    if file_ext in ['jpg', 'gif', 'bmp']:
        return 'infographic'
    elif file_ext in ['pdf', 'word', 'xls', 'ppt']:
        return 'document'
    else:
        return 'document'


def get_file_info(rootpath, fullpath):
    stat = os.stat(fullpath)
    file_path = fullpath[len(rootpath)]
    file_ext = os.path.splitext(file_path)[1]
    return {
        'fullpath': fullpath,
        'file_create_date': stat.st_ctime,
        'file_update_date': stat.st_mtime,
        'file_ext': file_ext[1] if len(file_ext) > 0 else '',
        'file_name': file_path[:-len(file_ext)],
        'name': os.path.split(file_path)[1][:-len(file_ext)]
    }


class Slide(models.Model):
    _inherit = 'slide.slide'

    path = fields.Char('Path')
    file_create_date = fields.Date('File Create Date')
    file_update_date = fields.Date('File Last Update Date')
    file_size = fields.Integer('File Size')


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
    top_category = fields.Boolean('按一级目录建立分类', defaul=True)
    dir_tags = fields.Boolean('按目录建立标签', default=True)

    @api.multi
    def fetch(self):
        for conf in self:
            if conf['type'] == 'local':
                self.fetch_local(conf['path'], conf['channel_id'].id)

    def fetch_local(self, rootpath, channel_id):
        for parent, dirnames, filenames in os.walk(rootpath):
            for filename in filenames:  # 输出文件信息
                fullpath = os.path.join(parent, filename)
                fileinfo = get_file_info(rootpath, fullpath)
                print('process %s, %s' % (fullpath, fileinfo))
                file = open(fullpath, mode='rb')
                datas = base64.encodestring(file.read())
                file.close()
                # self.save_file(parent, filename, datas, channel_id)

    def get_or_create_slide(self, model, fileinfo, conf):
        rs = model.search([('name', '=', fileinfo['file_name']), ('channel_id', '=', fileinfo['channel_id'])])
        vals = {
            'name': fileinfo['file_name'],
            'path': fileinfo['fullpath'],
            'file_create_date': fileinfo['file_create_date'],
            'file_update_date': fileinfo['file_update_date'],
            'slide_type': get_slide_type(fileinfo['file_ext']),
            'mime_type': 'application/' + fileinfo['file_ext'],
        }
        if len(rs) == 0:
            rec = model.create(vals)
        elif len(rs) == 1:
            rec = rs.write(vals)
        else:
            raise
        return rec


    def save_file(self, parent, filename, datas, channel_id):
        file_ext = os.path.splitext(filename)[1][1:]
        vals = {
            'name': filename,
            'path': parent,
            'channel_id': channel_id,
            'slide_type': self.get_slide_type(file_ext),
            'mime_type': 'application/' + file_ext,
            'datas': datas
        }
        model = self.env['slide.slide']
        rs = model.search([('name', '=', vals['name']), ('channel_id', '=', vals['channel_id'])])
        if len(rs) == 0:
            rec = model.create(vals)
        else:
            rec = model.browse(rs.id).write(vals)
        return rec
