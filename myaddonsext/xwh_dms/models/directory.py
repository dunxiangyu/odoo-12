from odoo import models, fields, api


class Directory(models.Model):
    _name = 'xwh_dms.directory'
    _description = 'Document Directory'

    name = fields.Char('Name')
    parent_id = fields.Many2one('xwh_dms.directory', string='Parent Directory',
                                ondelete='restrict', auto_join=True, index=True)
    tag_ids = fields.Many2many('xwh_dms.tag', 'xwh_dms_directory_tag_rel', auto_join=False,
                               column1='did', column2='tid', string='Tags')
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.user.company_id)
    attachment_ids = fields.One2many('ir.attachment', 'directory_id', string='Attachments', auto_join=False)
    child_directory_ids = fields.One2many('xwh_dms.directory', 'parent_id', string='SubDirectories', auto_join=False)

    count_tags = fields.Integer(string='Count Tags', compute='_compute_count_tags')
    count_subdirectories = fields.Integer(string='Count Sub Directories', compute='_compute_count_subdirectories')
    count_attachments = fields.Integer(string='Count Attachments', compute='_compute_count_attachments')

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
