from odoo import models, fields, api


class Tag(models.Model):
    _name = 'xwh_dms.tag'
    _description = 'Document Tag'

    name = fields.Char('Name', required=True)

    color = fields.Integer('Color Index')

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.user.company_id)

    directory_ids = fields.Many2many('xwh_dms.directory', 'xwh_dms_directory_tag_rel', string='Directories',
                                     column1='tid', column2='did', readonly=True)

    count_directories = fields.Integer(compute='_compute_count_directories',
                                       string='Count Directories')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Tag name already exists!')
    ]

    @api.depends('directory_ids')
    def _compute_count_directories(self):
        for record in self:
            record.count_directories = len(record.directory_ids)
