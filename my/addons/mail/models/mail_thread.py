import logging
from collections import namedtuple
from odoo import models, fields, api
import pycompat

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _name = 'mail.thread'
    _description = 'Email Thread'
    _mail_flat_thread = True
    _mail_post_access = 'write'
    _Attachment = namedtuple('Attachment', ('fname', 'content', 'info'))

    message_is_follower = fields.Boolean()
    message_follower_ids = fields.One2many('mail.followers', 'res_id')
    message_parent_ids = fields.Many2many(comodel_name='res.partner')
    message_channel_ids = fields.Many2many(comodel_name='mail.channel')
    message_ids = fields.One2many('mail.message', 'res_id')
    message_unread = fields.Boolean()
    message_unread_counter = fields.Integer()
    message_needaction = fields.Boolean()
    message_needaction_counter = fields.Integer()
    message_has_error = fields.Boolean()
    message_has_error_counter = fields.Integer()
    message_attachment_count = fields.Integer()
    message_main_attachment_id = fields.Many2one()

    @api.one
    @api.depends('message_follower_ids')
    def _get_followers(self):
        self.message_parent_ids = self.message_follower_ids.mapped('partner_id')
        self.message_channel_ids = self.message_follower_ids.mapped('channel_id')

    @api.model
    def _search_follower_partners(self, operator, operand):
        followers = self.env['mail.followers'].sudo().search([
            ('res_model', '=', self._name),
            ('partner_id', operator, operand)
        ])
        return [('id', 'in', [res['res_id'] for res in followers.read(['res_id'])])]

    @api.model
    def _search_follower_channels(self, operator, operand):
        followers = self.env['mail.followers'].sudo().search([
            ('res_model', '=', self._name),
            ('channel_id', operator, operand)
        ])
        return [('id', 'in', [res['res_id'] for res in followers.read('res_id')])]

    @api.multi
    @api.depends('message_follower_ids')
    def _compute_is_follower(self):
        followers = self.env['mail.followers'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids),
            ('partner_id', '=', self.env.user.partner_id.id)
        ])
        following_ids = [res['res_id'] for res in followers.read(['res_id'])]
        for record in self:
            record.message_id_follower = record.id in following_ids

    @api.model
    def _search_is_follower(self, operator, operand):
        followers = self.env['mail.followers'].sudo().search([
            ('res_model', '=', self._name),
            ('partner_id', '=', self.env.user.partner_id.id)
        ])
        if (operator == '=' and operand) or (operator == '!=' and not operand):
            return [('id', 'in', [res['res_id'] for res in followers.read(['res_id'])])]
        else:
            return [('id', 'not in', [res['res_id'] for res in followers.read(['res_id'])])]

    @api.multi
    def _get_message_unread(self):
        res = dict((res_id, 0) for res_id in self.ids)
        partner_id = self.env.user.partner_id.id
        self._cr.execute("")
        for result in self._cr.fetchall():
            res[result[0]] += 1

        for record in self:
            record.message_unread_counter = res.get(record.id, 0)
            record.message_unread = bool(record.message_unread_counter)

    @api.model
    def _search_message_needaction(self, operator, operand):
        return [('message_ids.needaction', operator, operand)]

    @api.multi
    def _compute_message_has_error(self):
        self._cr.execute("")
        res = dict()
        for result in self._cr.fetchall():
            res[result[0]] = result[1]

        for record in self:
            record.message_has_error_counter = res.get(record.id, 0)
            record.message_has_error = bool(record.message_has_error_counter)

    @api.model
    def _search_message_has_error(self, operator, operand):
        return ['&', ('message_ids.has_error', operator, operand)]

    @api.multi
    def _compute_message_attachment_count(self):
        read_group_var = self.env['ir.attachment'].read_group([
            ('res_id', 'in', self.ids),
            ('res_model', '=', self._name)
        ], fields=['res_id'], groupby=['res_id'])
        attachment_count_dict = dict((d['res_id'], d['res_id_count']) for d in read_group_var)
        for record in self:
            record.message_attachment_count = attachment_count_dict.get(record.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        if self._context.get('tracking_disable'):
            return super(MailThread, self).create(vals_list)

        if not self._context.get('mail_create_nosubscribe'):
            for values in vals_list:
                message_follower_ids = values.get('message_follower_ids') or []
                message_follower_ids += [(0, 0, fol_vals) for fol_vals in
                                         self.env['mail.followers']._add_default_followers(self._name, [],
                                                                                           self.env.user.partner_id.ids,
                                                                                           customer_ids=[])[0][0]]
                values['message_follower_ids'] = message_follower_ids

        threads = super(MailThread, self).create(vals_list)

        if not self._context.get('mail_create_nolog'):
            doc_name = self.env['ir.model']._get(self._name).name
            for thread in threads:
                thread._message_log(body='%s created' % doc_name)

        for thread, values in pycompat.izip(threads, vals_list):
            create_values = dict(values)
            for key, val in self._context.items():
                if key.startswith('default_') and key[8:] not in create_values:
                    create_values[key[8:]] = val
            thread._message_auto_subscribe(create_values)

        if not self._context.get('mail_notrack'):
            if 'lang' not in self._context:
                track_threads = threads.with_context(lang=self.env.user.lang)
            else:
                track_threads = threads
            for thread, values in pycompat.izip(track_threads, vals_list):
                tracked_fields = thread._get_tracked_fields(list(values))
                if tracked_fields:
                    initial_values = {thread.id: dict.fromkeys(tracked_fields)}
                    thread.message_track(tracked_fields, initial_values)

        return threads

    @api.multi
    def write(self, values):
        pass
