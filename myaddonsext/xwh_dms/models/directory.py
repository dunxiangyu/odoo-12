from odoo import models, fields, api
import os


class Directory(models.Model):
    _name = 'xwh_dms.directory'
    _description = 'Document Directory'

    name = fields.Char('Name')
    parent_id = fields.Many2one('xwh_dms.directory', string='Parent Directory',
                                ondelete='restrict', auto_join=True, index=True)
    complete_name = fields.Char('Full Path', compute='_compute_complete_name', index=True)
    tag_ids = fields.Many2many('xwh_dms.tag', 'xwh_dms_directory_tag_rel', auto_join=False,
                               column1='did', column2='tid', string='Tags')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.user.company_id)
    attachment_ids = fields.One2many('ir.attachment', 'directory_id', string='Attachments', auto_join=False,
                                     readonly=True)
    child_directory_ids = fields.One2many('xwh_dms.directory', 'parent_id', string='SubDirectories', auto_join=False,
                                          readonly=True)

    count_tags = fields.Integer(string='Count Tags', compute='_compute_count_tags')
    count_subdirectories = fields.Integer(string='Count Sub Directories', compute='_compute_count_subdirectories')
    count_attachments = fields.Integer(string='Count Attachments', compute='_compute_count_attachments')

    _sql_constraints = [
        ('complete_name', 'unique(complete_name)', 'Directory name already exists!')
    ]

    @api.depends('tag_ids')
    def _compute_count_tags(self):
        for record in self:
            record.count_tags = len(record.tag_ids)

    @api.depends('attachment_ids')
    def _compute_count_attachments(self):
        for record in self:
            record.count_attachments = len(record.attachment_ids)

    @api.depends('child_directory_ids')
    def _compute_count_subdirectories(self):
        for record in self:
            record.count_subdirectories = len(record.child_directory_ids)

    @api.onchange('name', 'parent_id')
    def _compute_complete_name(self):
        for record in self:
            record.complete_name = self._get_full_name(record)

    def _get_full_name(self, record):
        if record.parent_id and record.name:
            parent_name = record.parent_id.complete_name if record.parent_id.complete_name else ''
            return parent_name + '/' + record.name
        else:
            return record.name

    @api.multi
    def name_get(self):
        return [(item.id, item.complete_name) for item in self]

    @api.multi
    def attachment_tree_view(self):
        self.ensure_one()
        domain = [('directory_id', '=', self.id)]
        return {
            'name': 'Attachments',
            'type': 'ir.actions.act_window',
            'domain': domain,
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,form',
            'view_type': 'form',
        }

    @api.multi
    def sub_directory_tree_view(self):
        self.ensure_one()
        return {
            'name': 'Sub Directory',
            'type': 'ir.actions.act_window',
            'domain': [('parent_id', '=', self.id)],
            'res_model': 'xwh_dms.directory',
            'view_mode': 'tree',
            # 'view_type': 'form',
        }

    def get_or_create_directory(self, parent_id, name):
        rs = self.search([('parent_id', '=', parent_id), ('name', '=', name)])
        if len(rs) == 1:
            return rs.id
        else:
            rec = self.create({
                'name': name,
                'parent_id': parent_id,
                'company_id': self.env.user.company_id.id,
            })
            return rec.id

    def get_or_create_directories(self, parent_id, path):
        for name in path.split('/'):
            if len(name) > 0:
                parent_id = self.get_or_create_directory(parent_id, name)
        return parent_id
