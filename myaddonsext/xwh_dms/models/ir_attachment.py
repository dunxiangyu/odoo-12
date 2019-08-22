from odoo import models, fields, api


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    directory_id = fields.Many2one('xwh_dms.directory', 'Directory')
    tag_ids = fields.Many2many('xwh_dms.tag', 'xwh_dms_file_tag_rel', string='Tags',
                               column1='fid', column2='tid')
    count_tags = fields.Integer('Count Tags', compute='_compute_count_tags')

    likes = fields.Integer('Likes')
    dislikes = fields.Integer('Dislikes')
    slide_views = fields.Integer('# of Website Views')
    embed_views = fields.Integer('# of Embedded Views')
    total_views = fields.Integer("Total # Views", default="0", compute='_compute_total', store=True)

    @api.depends('tag_ids')
    def _compute_count_tags(self):
        for record in self:
            record.count_tags = len(record.tag_ids)

    @api.depends('slide_views', 'embed_views')
    def _compute_total(self):
        for record in self:
            record.total_views = record.slide_views + record.embed_views
