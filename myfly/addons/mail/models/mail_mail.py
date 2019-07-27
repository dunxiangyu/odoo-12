import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

class MailMail(models.Model):
    _name = 'mail.mail'
    _description = 'Outgoing Mails'
    _inherits = {'mail.message': 'mail_message_id'}
    _order = 'id desc'
    _rec_name = 'subject'

    
