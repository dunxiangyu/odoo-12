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
        if self._context.get('tracking_disable'):
            return super(MailThread, self).write(values)

        # Track initial values of tracked fields
        if 'lang' not in self._context:
            track_self = self.with_context(lang=self.env.user.lang)
        else:
            track_self = self

        tracked_fields = None
        if not self._context.get('mail_notrack'):
            tracked_fields = track_self._get_tracked_fields(list(values))
        if tracked_fields:
            initial_values = dict((record.id, dict((key, getattr(record, key)) for key in tracked_fields))
                                  for record in track_self)

        # Perform write
        result = super(MailThread, self).write(values)

        # Update followers
        self._message_auto_subscribe(values)

        # Perform the tracking
        if tracked_fields:
            track_self.with_context(clean_context(self._context)).message_track(tracked_fields, initial_values)

        return result

    @api.multi
    def unlink(self):
        if not self:
            return True
        self.env['mail.message'].search([('model', '=', self._name), ('res_id', 'in', self.ids)]).unlink()
        res = super(MailThread, self).unlink()
        self.env['mail.followers'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids)
        ]).unlink()
        return res

    @api.multi
    def copy_data(self, default=None):
        return super(MailThread, self.with_context(mail_notrack=True)).copy_data(default=default)

    @api.model
    def get_empty_list_help(self, help):
        model = self._context.get('empty_list_help_model')
        res_id = self._context.get('empty_list_help_id')
        catchall_domain = self.env['ir.config.parameter'].sudo().get_param('mail.catchall.domain')
        document_name = self._context.get('empty_list_help_document_name', 'document')
        nothing_here = not help
        alias = None

        if catchall_domain and model and res_id:
            record = self.env[model].sudo().browse(res_id)
            if record.alias_id and record.alias_id.alias_name and \
                    record.alias_id.alias_model_id and \
                    record.alias_id.alias_model_id.model == self._name and \
                    record.alias_id.alias_force_thread_id == 0:
                alias = record.alias_id
        if not alias and catchall_domain and model:
            Alias = self.env['mail.alias']
            aliases = Alias.search([
                ('alias_parent_model_id.model', '=', model),
                ('alias_name', '!=', False),
                ('alias_force_thread_id', '=', False),
                ('alias_parent_thread_id', '=', False)
            ], order='id ASC')
            if aliases and len(aliases) == 1:
                alias = aliases[0]

        if alias:
            email_link = ''
            if nothing_here:
                return ""
            if 'oe_view_nocontent_alias' not in help:
                return ''
        if nothing_here:
            return ''

        return help

    @api.model
    def check_mail_message_access(self, res_ids, operation, model_name=None):
        if model_name:
            DocModel = self.env[model_name]
        else:
            DocModel = self
        if hasattr((DocModel, '_mail_post_access')):
            create_allow = DocModel._mail_post_access
        else:
            create_allow = 'write'

        if operation in ['write', 'unlink']:
            check_operation = 'write'
        elif operation == 'create' and create_allow in ['create', 'read', 'write', 'unlink']:
            check_operation = create_allow
        elif operation == 'create':
            check_operation = 'write'
        else:
            check_operation = operation

        DocModel.check_access_rights(check_operation)
        DocModel.browse(res_ids).check_access_rule(check_operation)

    @api.multi
    def message_change_thread(self, new_thread):
        self.ensure_one()
        subtype_comment = self.env['ir.model.data'].xml_to_res_id('mail.mt_comment')
        MailMessage = self.env['mail.message']
        msg_comment = MailMessage.search([
            ('model', '=', self._name),
            ('res_id', '=', self.id),
            ('subtype_id', '=', subtype_comment)
        ])
        msg_not_comment = MailMessage.search([
            ('model', '=', self._name),
            ('res_id', '=', self.id),
            ('subtype_id', '!=', subtype_comment)
        ])
        msg_comment.write({'res_id': new_thread.id, 'model': new_thread._name})
        msg_not_comment.write({'res_id': new_thread.id, 'model': new_thread._name})
        return True

    @api.model
    def _get_tracked_fields(self, updated_fields):
        tracked_fields = []
        for name, field in self._fields.items():
            if getattr(field, 'track_visibility', False):
                tracked_fields.append(name)

        if tracked_fields:
            return self.fields_get(tracked_fields)
        return {}

    @api.multi
    def _track_subtype(self, init_values):
        return False

    @api.multi
    def _track_template(self, tracking):
        return dict()

    @api.multi
    def _message_track_post_template(self, tracking):
        if not any(change for rec_id, (change, tracking_value_ids) in tracking.items()):
            return True
        templates = self._track_template(tracking)
        for field_name, (template, post_kwargs) in templates.items():
            if not template:
                continue
            if isinstance(template, pycompat.string_types):
                self.message_post_with_view(template, **post_kwargs)
            else:
                self.message_post_with_template(template.id, **post_kwargs)
        return True

    @api.multi
    def _message_track_get_changes(self, tracked_fields, initail_values):
        result = dict()
        for record in self:
            result[record.id] = record._message_track(tracked_fields, initail_values[record.id])
        return result

    @api.multi
    def _message_track(self, tracked_fields, initial):
        self.ensure_one()
        changes = set()
        tracking_value_ids = []

        for col_name, col_info in tracked_fields.items():
            initial_value = initial[col_name]
            new_value = getattr(self, col_name)

            if new_value != initial_value and (new_value or initial_value):
                track_sequence = getattr(self._fields[col_name], 'track_sequence')
                tracking = self.env['mail.tracking.value'].create_tracking_values(initial_value, new_value, col_name,
                                                                                  col_info, track_sequence)
                if tracking:
                    tracking_value_ids.append([0, 0, tracking])

                if col_name in tracked_fields:
                    changes.add(col_name)

        return changes, tracking_value_ids

    @api.multi
    def message_track(self, tracked_fields, initial_values):
        if not tracked_fields:
            return True

        tracking = self._message_track_get_changes(tracked_fields, initial_values)
        for record in self:
            changes, tracking_value_ids = tracking[record.id]
            if not changes:
                continue

            subtype_xmlid = False
            if not self._context.get('mail_track_log_only'):
                subtype_xmlid = record._track_subtype(
                    dict((col_name, initial_values[record.id][col_name]) for col_name in changes))

            if subtype_xmlid:
                subtype_rec = self.env.ref(subtype_xmlid)
                if not (subtype_rec and subtype_rec.exists()):
                    continue
                record.message_post(subtype=subtype_xmlid, tracking_value_ids=tracking_value_ids)
            elif tracking_value_ids:
                record._message_log(tracking_value_ids=tracking_value_ids)

        self._message_track_post_template(tracking)

        return True

    @api.model
    def _notify_encode_link(self, base_link, params):
        secret = self.env['ir.config_parameter'].sudo().get_param('database.secret')
        token = '%s?%s' % (base_link, ' '.join('%s=%s' % (key, params[key]) for key in sorted(params)))
        hm = hmac.new(secret.encode('utf-8'), token.encode('utf-8'), hashlib.sha1).hexdigest()
        return hm

    @api.multi
    def _notify_get_action_link(self, link_type, **kwargs):
        local_kwargs = dict(kwargs)
        base_params = {
            'model': kwargs.get('model', self._name),
            'res_id': kwargs.get('res_id', self.ids and self.ids[0] or False),
        }

        local_kwargs.pop('message_id', None)
        local_kwargs.pop('model', None)
        local_kwargs.pop('res_id', None)

        if link_type in ['view', 'assign', 'follow', 'unfollow']:
            params = dict(base_params, **local_kwargs)
            base_link = '/mail/%s' % link_type
        elif link_type == 'controller':
            controller = local_kwargs.pop('controller')
            params = dict(base_params, **local_kwargs)
            params.pop('model')
            base_link = '%s' % controller
        else:
            return ''

        if link_type not in ['view']:
            token = self._notify_encode_link(base_link, params)
            params['token'] = token

        link = '%s?%s' % (base_link, url_encode(params))

        if self and hasattr(self, 'get_base_url'):
            link = self[0].get_base_url() + link

        return link

    @api.multi
    def _notify_get_groups(self, message, groups):
        return groups

    @api.multi
    def _notify_classify_recipients(self, message, recipient_data):
        result = {}

        access_link = self._notify_get_action_link('view')

        if message.model:
            model = self.env['ir.model'].with_context(
                lang=self.env.context.get('lang', self.env.user.lang)
            )
            model_name = model._get(message.model).display_name
            view_title = 'View %s' % model_name
        else:
            view_title = 'View'

        default_groups = [
            ('user', lambda pdata: pdata['type'] == 'user', {}),
            ('portal', lambda pdata: pdata['type'] == 'portal', {
                'has_button_access': False
            }),
            ('customer', lambda pdata: True, {
                'has_button_access': False
            })
        ]

        groups = self._notify_get_groups(message, default_groups)

        for group_name, group_func, group_data in groups:
            group_data.setdefault('has_button_access', True)
            group_data.setdefault('button_access', {
                'url': access_link,
                'title': view_title
            })
            group_data.setdefault('actions', list())
            group_data.setdefault('recipients', list())

        for recipient in recipient_data:
            for group_name, group_func, group_data in groups:
                if group_func(recipient):
                    group_data['recipients'].append(recipient['id'])
                    break

        for group_name, group_method, group_data in groups:
            result[group_name] = group_data

        return result

    def _notify_classify_recipients_on_records(self, message, recipient_data, records=None):
        if records and hasattr(records, '_notify_classify_recipients'):
            return records._notify_classify_recipients(message, recipient_data)
        return self._notify_classify_recipients(message, recipient_data)

    @api.multi
    def _notify_get_reply_to(self, default=None, records=None, company=None, doc_names=None):
        _records = self if self and self._name != 'mail.thread' else records
        model = _records._name if _records and _records._name != 'mail.thread' else False
        res_ids = _records.ids if _records and model else []
        _res_ids = res_ids or [False]

        alias_domain = self.env['ir.config_parameter'].sudo().get_param('mail.catchall.domain')
        result = dict.fromkeys(_res_ids, False)
        result_email = dict()
        doc_names = doc_names if doc_names else dict()

        if alias_domain:
            if model and res_ids:
                if not doc_names:
                    doc_names = dict((rec.id, rec.display_name) for rec in _records)

                mail_aliases = self.env['mail.alias'].sudo().search([
                    ('alias_parent_model_id.model', '=', model),
                    ('alias_parent_thread_id', 'in', res_ids),
                    ('alias_name', '!=', False)
                ])
                for alias in mail_aliases:
                    result_email.setdefault(alias.alais_parent_thread_id, '%s@%s' % (alias.alias_name, alias_domain))

            left_ids = set(_res_ids) - set(result_email)
            if left_ids:
                catchall = self.env['ir.config_parameter'].sudo().get_param('mail.catchall.alias')
                if catchall:
                    result_email.update(dict((rid, '%s@%s' % (catchall, alias_domain)) for rid in left_ids))

            company_name = company.name if company else self.env.user.company_id.name
            for res_id in result_email.keys():
                name = '%s%s%s' % (company_name, ' ' if doc_names.get(res_id) else '', doc_names.get(res_id, ''))
                result[res_id] = formataddr((name, result_email[res_id]))

        left_ids = set(_res_ids) - set(result_email)
        if left_ids:
            result.update(dict((res_id, default) for res_id in left_ids))

        return result

    @api.model
    def _notify_get_reply_to_on_records(self, default=None, records=None, company=None, doc_names=None):
        if records and hasattr(records, '_notify_get_reply_to'):
            return records._notify_get_reply_to(default=default, company=company, doc_names=doc_names)
        return self._notify_get_reply_to(default, records, company, doc_names)

    @api.multi
    def _notify_specific_email_values(self, message):
        if not self:
            return {}
        self.ensure_one()
        return {'headers': repr({
            'X-Odoo-Objects': '%s-%s' % (self._name, self.id)
        })}

    @api.model
    def _notify_specific_email_values_on_records(self, message, records=None):
        if records and hasattr(records, '_notify_specific_email_values'):
            return records._notify_specific_email_values(message)
        return self._notify_specific_email_values(message)

    @api.multi
    def _notify_email_recipients(self, message, recipient_ids):
        return {
            'recipient_ids': [(4, pid) for pid in recipient_ids]
        }

    @api.model
    def _notify_email_recipients_on_records(self, message, recipient_ids, records=None):
        if records and hasattr(records, '_notify_email_recipients'):
            return records._notify_email_recipients(message, recipient_ids)
        return self._notify_email_recipients(message, recipient_ids)

    def _message_find_partners(self, message, header_fields=['form']):
        s = ', '.join([tools.decod_smtp_header(message.get(h)) for h in header_fields if message.get(h)])
        return [x for x in self._find_partner_from_emails(tools.email_splits(s)) if x]

    def _routing_warn(self, error_message, warn_suffix, message_id, route, raise_exception):
        short_message = 'Mailbox unavailable - %s' % error_message
        full_message = ('Routing mail with Message-Id %s: route %s: %s' %
                        (message_id, route, error_message))
        if raise_exception:
            raise ValueError(short_message)

    def _routing_create_bounce_email(self, email_from, body_html, message, **mail_values):
        bounce_to = tools.decode_message_header(message, 'Return-Path') or email_from
        bounce_mail_values = {
            'body_html': body_html,
            'subject': 'Re: %s' % message.get('subject'),
            'email_to': bounce_to,
            'auto_delete': True,
        }
        bounce_from = self.env['ir.mail.server']._get_default_bounce_address()
        if bounce_from:
            bounce_mail_values['email_from'] = 'MAILER_DAEMON <%s>' % bounce_from
        bounce_mail_values.update(mail_values)
        self.env['mail.mail'].create(bounce_mail_values).send()

    @api.model
    def message_route_verify(self, message, message_dict, route,
                             update_author=True, assert_model=True,
                             create_fallback=True, allow_private=False,
                             drop_alias=False):
        assert isinstance(route, (list, tuple))
        assert len(route) == 5

        message_id = message.get('Message-Id')
        email_from = tools.decode_message_header(message, 'From')
        author_id = message_dict.get('author_id')
        model, thread_id, alias = route[0], route[1], route[4]
        record_set = None

        _generic_bounce_body_html = """
        
        """

        if model and model not in self.env:
            self._routing_warn('unknown target model %s' % model, '', message_id, route, assert_model)
            return ()

        if not model:
            if thread_id:
                self._routing_warn(
                    'posting a message without model should be with a null res id (private message), received %s' % thread_id,
                    'resetting thread_id', message_id, route, assert_model)
                thread_id = 0
            if not message_dict.get('parent_id'):
                return False

        if model and thread_id:
            record_set = self.env[model].browse(thread_id)
        elif model:
            record_set = self.env[model]

        if thread_id:
            if not record_set.exists() and create_fallback:
                thread_id = None
            elif not hasattr(record_set, 'message_update') and create_fallback:
                thread_id = None

            if not record_set.exists():
                return False
            elif not hasattr(record_set, 'message_update'):
                return False

        if not thread_id and model and not hasattr(record_set, 'message_new'):
            return False

        if not author_id and update_author:
            author_ids = self.env['mail.thread']._find_partner_from_emails([email_from], res_model=model,
                                                                           res_id=thread_id)
            if author_ids:
                message_dict['author_id'] = author_ids[0]

        if alias:
            obj = None
            if thread_id:
                obj = record_set[0]
            elif alias.alias_parent_model_id and alias.alias_parent_thread_id:
                obj = self.env[alias.alias_parent_model_id.model].browse(alias.alias_parent_thread_id)
            elif model:
                obj = self.env[model]
            if hasattr(obj, '_alias_check_contact'):
                check_result = obj._alias_check_contact(message, message_dict, alias)
            else:
                check_result = self.env['mail.alias.mixin']._alias_check_contact(obj, message, message_dict, alias)
