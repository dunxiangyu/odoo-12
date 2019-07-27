import logging
from email.utils import formataddr
from odoo import models, fields, api
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class Message(models.Model):
    _name = 'mail.message'
    _description = 'Message'
    _order = 'id desc'
    _rec_name = 'record_name'

    _message_read_limit = 30

    @api.model
    def _get_default_from(self):
        if self.evn.user.email:
            return formataddr(self.env.user.name, self.env.user.email)

    @api.model
    def _get_default_author(self):
        return self.env.user.partner_id

    # content
    subject = fields.Char('Subject')
    date = fields.Datetime('Date', default=fields.Datetime.now)
    body = fields.Html('Contents', default='', sanitize_style=True)
    attachment_ids = fields.Many2many('ir.attachment', 'message_attachment_rel',
                                      'message_id', 'attachment_id',
                                      string='Attachments')
    parent_id = fields.Many2one('mail.message', 'Parent Message',
                                ondelete='set null')
    child_ids = fields.One2many('mail.message', 'parent_id', 'Child Messages')
    # related document
    model = fields.Char('Related Document Model')
    res_id = fields.Integer('Related Document ID')
    record_name = fields.Char('Message Record Name')
    #
    message_type = fields.Selection([
        ('email', 'Email'),
        ('comment', 'Comment'),
        ('notification', 'System notification')], 'Type', default='email')
    subtype_id = fields.Many2one('mail.message.subtype', 'Subtype')
    mail_activity_type_id = fields.Many2one('mail.activity.type', 'Mail Activity Type')
    # orign
    email_from = fields.Char('From', default=_get_default_from)
    author_id = fields.Many2one('res.partner', 'Author', default=_get_default_author)
    author_avatar = fields.Binary("Author's avatar", related='author_id.image_small')
    partner_ids = fields.Many2many('res.partner', string='Recipients')
    needaction_partner_ids = fields.Many2many('res.partner', 'mail_message_res_partner_needaction_rel',
                                              string='Partners with Need Action')
    needaction = fields.Boolean('Need Action', compute='_get_needaction')
    has_error = fields.Boolean('Has error', compute='_compute_has_error')
    channel_ids = fields.Many2many('mail.channel', 'mail_message_mail_channel_rel', 'Channels')
    # notifications
    notification_ids = fields.One2many('res.partner', 'mail_message_res_partner_starred_rel')
    startred = fields.Boolean('Startred', compute='_get_startred')
    # tracking
    tracking_value_ids = fields.One2many('mail.tracking.value', 'mail_message_id')
    # mail gateway
    no_auto_thread = fields.Boolean('No threading for answers')
    message_id = fields.Char('Message-Id')
    reply_to = fields.Char('Reply-To')
    mail_server_id = fields.Many2one('ir.mail.server')
    # moderation
    moderation_status = fields.Selection([
        ('pending_moderation', 'Pending Moderation'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected')])
    moderator_id = fields.Many2one('res.users')
    need_moderation = fields.Boolean('Need moderation')
    layout = fields.Char('Layout')
    add_sign = fields.Boolean(default=True)

    @api.multi
    def _get_needaction(self):
        my_myssages = self.env['mail.notification'].sudo().search([
            ('mail_message_id', 'in', self.ids),
            ('res_partner_id', '=', self.env.user.partner_id.id),
            ('is_read', '=', False)]).mapped('mail_message_id')
        for message in self:
            message.needaction = message in my_myssages

    @api.model
    def _search_needaction(self, operator, operand):
        if operator == '=' and operand:
            return ['&', ('notification_ids.res_partner_id', '=', self.env.user.partner_id.id),
                    ('notification_ids.is_red', '=', False)]
        return ['&', ('notification_ids.res_partner_id', '=', self.env.user.partner_id.id),
                ('notification_ids.is_read', '=', True)]

    @api.multi
    def _compute_has_error(self):
        error_from_notification = self.env['mail.notification'].sudo().search([
            ('mail_message_id', 'in', self.ids),
            ('email_status', 'in', ('bounce', 'exception'))]).mapped('mail_message_id')
        for message in self:
            message.has_error = message in error_from_notification

    @api.multi
    def _search_has_error(self, operator, operand):
        if operator == '=' and operand:
            return [('notification_ids.email_status', 'in', ('bounce', 'exception'))]
        return ['!', ('notification_ids.email_status', 'in', ('bounce', 'exception'))]

    @api.depends('starred_partner_ids')
    def _get_starred(self):
        starred = self.sudo().filtered(lambda msg: self.env.user.partner_id in msg.starred_partner_ids)
        for message in self:
            message.starred = message in starred

    @api.model
    def _search_starred(self, operator, operand):
        if operator == '=' and operand:
            return [('starred_partner_ids', 'in', [self.evn.partner_id.id])]
        return [('starred_partner_ids', 'not in', [self.env.user.partner_id.id])]

    @api.multi
    def _compute_need_moderation(self):
        for message in self:
            message.need_moderation = False

    @api.model
    def _search_need_moderation(self, operator, operand):
        if operator == '=' and operand is True:
            return ['&', '&',
                    ('moderation_status', '=', 'pending_moderation'),
                    ('model', '=', 'mail.channel'),
                    ('res_id', 'in', self.env.user.moderation_channel_ids.ids)]
        return ValueError()

    @api.model
    def mark_all_as_read(self, channel_ids=None, domain=None):
        partner_id = self.env.user.partner_id.id
        delete_mode = not self.env.user.share
        if not domain and delete_mode:
            query = "DELETE FROM mail_message_res_partner_needaction_rel WHERE res_partner_id IN %s"
            args = [(partner_id,)]
            if channel_ids:
                query += """
                    AND mail.message_id in 
                        (SELECT mail_message_id
                        FROM mail_message_mail_channel_rel
                        WHERE mail_channel_id in %s)
                """
                args += [tuple(channel_ids)]
            query += " RETURNING mail_message_id as id"
            self._cr.execute(query, args)
            self.invalidate_cache()

            ids = [m['id'] for m in self._cr.dictfetchall()]
        else:
            msg_domain = [('needaction_partner_ids', 'in', partner_id)]
            if channel_ids:
                msg_domain += [('channel_ids', 'in', channel_ids)]
            unred_messages = self.search(expression.AND([msg_domain, domain]))
            notifications = self.env['mail.notification'].sudo().search([
                ('mail_message_id', 'in', unred_messages.ids),
                ('res_partner_id', '=', self.env.user.partner_id.id),
                ('is_read', '=', False)])
            if delete_mode:
                notifications.unlink()
            else:
                notifications.write({'is_read': True})
            ids = unred_messages.mapped('id')

        notification = {'type': 'mark_as_read', 'message_ids': ids, 'channel_ids': channel_ids}
        self.env['bus.bus'].sendone((self._cr.dbname, 'res.partner', self.env.partner_id.id), notification)
        return ids

    @api.multi
    def set_message_done(self):
        partner_id = self.env.user.partner_id
        delete_mode = not self.env.user.share

        notifications = self.env['mail.notification'].sudo().search([
            ('mail_message_id', 'in', self.ids),
            ('res_partner_id', '=', partner_id.id),
            ('is_read', '=', False)])
        if not notifications:
            return

        groups = []
        messages = notifications.mapped('mail_message_id')
        current_channel_ids = messages[0].channel_ids
        current_group = []
        for record in messages:
            if record.channel_ids == current_channel_ids:
                current_group.append(record.id)
            else:
                groups.append((current_group, current_channel_ids))
                current_group = [record.id]
                current_channel_ids = record.channel_ids

        groups.append((current_group, current_channel_ids))
        current_group = [record.id]
        current_channel_ids = record.channel_ids

        if delete_mode:
            notifications.unlink()
        else:
            notifications.write({'is_read': True})

        for (msg_ids, channel_ids) in groups:
            notification = {'type': 'mark_as_read', 'message_ids': msg_ids,
                            'channel_ids': [c.id for c in channel_ids]}
            self.env['bus.bus'].sendone((self._cr.dbname, 'res.partner', partner_id.id), notification)

    @api.model
    def unstar_all(self):
        partner_id = self.env.user.partner_id.id

        starred_messages = self.search([('starred_partner_ids', 'in', partner_id)])
        starred_messages.write({'starred_partner_ids': [(3, partner_id)]})

        ids = [m.id for m in starred_messages]
        notification = {'type': 'toggle_star', 'message_ids': ids, 'starred': False}
        self.env['bus.bus'].sendone((self._cr_dbname, 'res.partner', partner_id), notification)

    @api.multi
    def toggle_message_starred(self):
        self.check_access_rule('read')
        partner_id = self.env.user.partner_id.id
        starred = not self.starred
        if starred:
            self.sudo().write({'starred_partner_ids': [(4, partner_id)]})
        else:
            self.sudo().write({'starred_partner_ids': [(3, partner_id)]})

        notification = {'type': 'toggle_star', 'message_ids': [self.id], 'starred': starred}
        self.env['bus.bus'].sendone((self._cr.dbname, 'res.partner', partner_id), notification)

    # -----------------------------------------
    # Message loading for web interface
    # -----------------------------------------

    @api.model
    def _message_read_dict_postprocess(self, messages, message_tree):
        # 1. Aggregate partners
        partners = self.env['res.partner'].sudo()
        attachments = self.env['ir.attachment']
        message_ids = list(message_tree.keys())
        for message in message_tree.values():
            if message.author_id:
                partners |= message.author_id
            if message.subtype_id and message.partner_ids:
                partners |= message.partner_ids
            elif not message.subtype_id and message.partner_ids:
                partners |= message.partner_ids
            if message.needaction_partner_ids:
                partners |= message.needaction_partner_ids
            if message.attachment_ids:
                attachments |= message.attachment_ids
        # Read partner as superuser
        partners_names = partners.name_get()
        partner_tree = dict((partner[0], partner) for partner in partners_names)

        # 2. attachments as superuser
        attachments_data = attachments.sudo().read(['id', 'datas_fname', 'name', 'mimetype'])
        safari = request and request.httprequest.user_agent.browser == 'safari'
        attachments_tree = dict((attachment['id'], {
            'id': attachment['id'],
            'filename': attachment['datas_fname'],
            'name': attachment['name'],
            'mimetype': ''
        }) for attachment in attachments_data)

        # 3. Tracking values
        tracking_values = self.env['mail.tracking.value'].sudo().search([('mail_message_id', 'in', message_ids)])
        message_to_tracking = dict()
        tracking_tree = dict.fromkeys(tracking_values.ids, False)
        for tracking in tracking_values:
            message_to_tracking.setdefault(tracking.mail_message_id.id, list()).append(tracking.id)
            tracking_tree[tracking.id] = {
                'id': tracking.id,
                'change_field': tracking.field_desc,
                'old_value': tracking.get_old_display_value()[0],
                'new value': tracking.get_new_display_value()[0],
                'field_type': tracking.field_type,
            }

        # 4. update message dictionaries
        for message_dict in messages:
            message_id = message_dict.get('id')
            message = message_tree[message_id]
            if message.author_id:
                author = partner_tree[message.author_id.id]
            else:
                author = (0, message.email_from)
            partner_ids = []
            if message.subtype_id:
                partner_ids = [partner_tree[partner.id] for partner in message.partner_ids
                               if partner.id in partner_tree]
            else:
                partner_ids = [partner_tree[partner.id] for partner in message.partner_ids
                               if partner.id in partner_tree]
            customer_email_status = (
                    (all(n.email_status == 'sent' for n in message.notification_ids) and 'sent') or
                    (any(n.email_status == 'exception' for n in message.notification_ids) and 'exception') or
                    (any(n.email_status == 'bounce' for n in message.notification_ids) and 'bounce') or
                    'ready'
            )
            customer_email_data = []

            def filter_notification(notif):
                return (
                        (notif.email_status in (
                            'bounce', 'exception', 'canceled') or notif.res_partner_id.partner_share) and
                        notif.res_partner_id.active
                )

            for notification in message.notification_ids.filtered(filter_notification):
                customer_email_data.append((partner_tree[notification.res_partner_id][0],
                                            partner_tree[notification.res_partner_id.id][1],
                                            notification.email_status))

            has_access_to_model = message.model and self.env[message.model].check_access_rights('read',
                                                                                                raise_exception=False)
            main_attachment = has_access_to_model and message.res_id and self.env[message.model].search(
                [('id', '=', message.res_id)])
            and getattr(self.env[message.model].browse(message.res_id), 'message_main_attachment_id')
            attachment_ids = []
            for attachment in message.attachment_ids:
                if attachment.id in attachments_tree:
                    attachments_tree[attachment.id]['is_main'] = main_attachment == attachment
                    attachment_ids.append(attachments_tree[attachment.id])
            tracking_value_ids = []
            for tracking_value_id in message_to_tracking.get(message_id, list()):
                if tracking_value_id in tracking_tree:
                    tracking_value_ids.append(tracking_tree[tracking_value_id])

            message_dict.update({
                'author_id': author,
                'partner_ids': partner_ids,
                'customer_email_status': customer_email_status,
                'customer_email_data': customer_email_data,
                'attachment_ids': attachment_ids,

            })

        return True

    @api.multi
    def message_fetch_failed(self):
        messages = self.search([('has_error', '=', True),
                                ('author_id.id', '=', self.env.user.partner_id.id),
                                ('res_id', '!=', 0),
                                ('model', '!=', False)])
        return messages._format_mail_failures()

    @api.model
    def message_fetch(self, domain, limit=20, moderated_channel_ids=None):
        messages = self.search(domain, limit=limit)
        if moderated_channel_ids:
            moderated_message_dom = [('model', '=', 'mail.channel'),
                                     ('res_id', 'in', moderated_channel_ids),
                                     '|',
                                     ('author_id', '=', self.env.user.partner_id.id),
                                     ('need_moderation', '=', True)]
            messages |= self.search(moderated_message_dom, limit=limit)
            messages = messages.sorted(key='id', reverse=True)[:limit]
        return messages.message_format()

    @api.multi
    def message_format(self):
        message_values = self.read([
            'id', 'body', 'date', 'author_id', 'email_from',
            'message_type', 'subtype_id', 'subject',
            'model', 'res_id', 'record_name',
            'channel_ids', 'partner_ids',
            'starred_partner_ids', 'moderation_status'
        ])
        message_tree = dict((m.id, m) for m in self.sudo())
        self._message_read_dict_postprocess(message_values, message_tree)

        subtype_ids = [msg['subtype_id'][0] for msg in message_values if msg['subtype_id']]
        subtypes = self.env['mail.message.subtype'].sudo().browse(subtype_ids).read(['internal', 'description', 'id'])
        subtypes_dict = dict((subtype['id'], subtype) for subtype in subtypes)

        com_id = self.env['ir.model.data'].xmlid_to_res_id('mail.mt_comment')
        note_id = self.env['ir.model.data'].xmlid_to_res_id('mail.mt_note')

        notif_dict = {}
        notifs = self.env['mail.notification'].sudo().search(
            [('mail_message_id', 'in', list(mid for mid in message_tree)), ('is_read', '=', False)])
        for notif in notifs:
            mid = notif.mail_message_id.id
            if not notif_dict.get(mid):
                notif_dict[mid] = {'partner_id': list()}
            notif_dict[mid]['partner_id'].append(notif.res_partner_id.id)

        for message in message_values:
            message['needaction_partner_ids'] = notif_dict.get(message['id'], dict()).get('partner_id', [])
            message['is_note'] = message['subtype_id'] and subtypes_dict[message['subtype_id'][0]]['id'] == note_id
            message['is_discussion'] = message['subtype_id'] and subtypes_dict[message['subtype_id'][0]]['id'] == com_id
            message['is_notification'] = message['is_note'] and not message['model'] and not message['res_id']
            message['subtype_description'] = message['subtype_id'] and subtypes_dict[message['subtype_id'][0]][
                'description']
            if message['model'] and self.env[message['model']]._original_module:
                message['module_icon'] = modules.module.get_module_icon(self.env[message['model']]._original_module)
        return message_values

    @api.multi
    def _format_mail_failure(self):
        failure_infos = []
        for message in self:
            if message.model and message.res_id:
                record = self.env[message.model].browse(message.res_id)
                try:
                    record.check_access_rights('read')
                    record.check_access_rule('read')
                except AccessError:
                    continue
            info = {
                'message_id': message.id,
                'record_name': message.record_name,
                'model_name': self.env['ir.model']._get(message.model).display_name,
                'uuid': message.message_id,
                'res_id': message.res_id,
                'model': message.model,
                'last_message_date': message.date,
                'module_icon': '/mail.static/src/img/smiley/mailfailure.jpg',
                'notifications': dict(
                    (notif.res_partner_id.id, (notif.email_status, notif.res_partner_id.name)) for notif in
                    message.notification_ids.sudo())
            }
            failure_infos.append(info)
        return failure_infos

    @api.multi
    def _notify_failure_update(self):
        authors = {}
        for author, author_messages in groupby(self, itemgetter('author_id')):
            self.env['bus.bus'].sendone(
                (self._cr.dbname, 'res.partner', author.id),
                {'type': 'mail_failure',
                 'elements': self.env['mail.message'].concat(*author_messages)._format_mail_failuers()}
            )

    @api.model_cr
    def init(self):
        self._cr.execute('SELECT indexname FROM pg_indexes WHERE indexname="mail_message_model_res_id_idx"')
        if not self._cr.fetchone():
            self._cr.execute("CREATE INDEX mail_message_model_res_id_idx ON mail_message(model, res_id")

    @api.model
    def _find_allowed_model_wise(self, doc_model, doc_dict):
        doc_ids = list(doc_dict)
        allowed_doc_ids = self.env[doc_model].with_context(active_test=False).search([('id', 'in', doc_ids)]).ids
        return set([message_id for allowed_doc_id in allowed_doc_ids for message_id in doc_dict[allowed_doc_id]])
