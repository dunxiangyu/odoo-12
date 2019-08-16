# -*- coding: utf-8 -*-
import os
from odoo import models, fields, api
from . import utils


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
                self.fetch_local(conf['path'], conf)

    def fetch_local(self, rootpath, conf):
        model = self.env['slide.slide']
        for parent, dirnames, filenames in os.walk(rootpath):
            for filename in filenames:
                fullpath = os.path.join(parent, filename)
                fileinfo = utils.get_file_info(rootpath, fullpath)
                print('process %s, %s' % (fullpath, fileinfo))
                self.get_or_create_slide(model, fileinfo, conf)

    def get_or_create_category(self, channel_id, category_name):
        model = self.env['slide.category']
        rs = model.search([('channel_id', '=', channel_id), ('name', '=', category_name)])
        if len(rs) == 0:
            rs = model.create({
                'channel_id': channel_id,
                'name': category_name
            })
        return rs.id

    def get_or_create_tags(self, tags):
        model = self.env['slide.tag']
        result = []
        for tag in tags:
            rs = model.search([('name', '=', tag)])
            if len(rs) == 0:
                rs = model.create({'name': tag})
            result.append(rs.id)
        return result

    def get_or_create_slide(self, model, fileinfo, conf):
        channel_id = conf['channel_id'].id
        rs = model.search([('name', '=', fileinfo['file_name']), ('channel_id', '=', channel_id)])
        vals = {
            'name': fileinfo['file_name'],
            'path': fileinfo['fullpath'],
            'file_create_date': fileinfo['file_create_date'],
            'file_update_date': fileinfo['file_update_date'],
            'slide_type': utils.get_slide_type(fileinfo['file_ext']),
            'mime_type': 'application/' + fileinfo['file_ext'],
            'channel_id': channel_id,
            'category_id': None,
            'tag_ids': []
        }
        if len(rs) == 0:
            vals['datas'] = utils.get_file_content(fileinfo['fullpath'])
            if len(fileinfo['dirs']) > 0:
                category_id = self.get_or_create_category(channel_id, fileinfo['dirs'][0])
                tag_ids = self.get_or_create_tags(fileinfo['dirs'])
                vals['category_id'] = category_id
                vals['tag_ids'] = [(6, 0, tag_ids)]
            rec = model.create(vals)
        elif len(rs) == 1:
            if rs[0].file_create_date != vals['file_create_date']:
                vals['datas'] = utils.get_file_content(fileinfo['fullpath'])
                rec = rs.write(vals)
        else:
            raise
        return rec
