from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class account_payment_method(models.Model):
    _name = 'account.payment.method'
    _description = 'Payment Methods'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    payment_type = fields.Selection([('inbound', 'Inbound'), ('outbound', 'Outbound')], required=True)


class account_abstract_payment(models.AbstractModel):
    _name = 'account.abstract.payment'
    _description = 'Contains the logic shared between models which allows to register payments'

    invoice_ids = fields.Many2many('account.invoice', string='Invoices', copy=False)
    multi = fields.Booelan(string='Multi',
                           help='Technical field indication if the user selected invoices from multiple partners or from different types.')
    payment_type = fields.Selection([('outbound', 'Send Money'), ('inbound', 'Receive Money')], string='Payment Type',
                                    required=True)
    payment_method_id = fields.Many2one('account.payment.method', string='Payment Method Type', required=True,
                                        oldname='payment_method')
    payment_method_code = fields.Char(related='payment_method_id.code', readonly=True)
    partner_type = fields.Selection([('customer', 'Customer'), ('supplier', 'Vendor')])
    partner_id = fields.Many2one('res.partner', string='Partner')

    amount = fields.Monetary(string='Payment Amount', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.user.company_id.currency_id)
    payment_date = fields.Date(string='Payment Date', default=fields.Date.context_today, required=True, copy=False)
    communication = fields.Char(string='Memo')
    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True,
                                 domain=[('type', 'in', ('bank', 'cash'))])
    hide_payment_method = fields.Boolean(compute='_compute_hide_payment_method')
    payment_difference = fields.Monetary(compute='_compute_payment_difference', readonly=True)
    payment_difference_handling = fields.Selection([('open', 'Keep open'), ('reconcile', 'Mark invoice as fully paid')],
                                                   default='open', string='Payment Difference Handling')
    writeoff_account_id = fields.Many2one('account.account', string='Difference Account',
                                          domain=[('deprecated', '=', False)], copy=False)
    writeoff_label = fields.Char(string='Journal Item Label', default='Write-Off')
    partner_bank_account_id = fields.Many2one('res.partner.bank', string='Recipient Bank Account')
    show_partner_bank_account = fields.Boolean(compute='_compute_show_partner_bank')

    @api.model
    def default_get(self, fields):
        rec = super(account_abstract_payment, self).default_get(fields)
        active_ids = self._context.get('active_ids')
        active_model = self._context.get('active_model')

        # Check for selected invoices ids
        if not active_ids or active_model != 'account.invoice':
            return rec

        invoices = self.env['account.invoice'].browse(active_ids)

        # Check all invoices are open
        if any(invoice.state != 'open' for invoice in invoices):
            raise UserError(_('You can only register payments for open invoices'))
        # Check all invoices have the same currency
        if any(inv.currency_id != invoices[0].currency_id for inv in invoices):
            raise UserError(_('In order to pay multiple invoices at once, they must use the same currency.'))
        # Check if, in batch payments, there are not negative invoices and positive invoices
        dtype = invoices[0].type
        for inv in invoices[1:]:
            if inv.type != dtype:
                if ((dtype == 'in_refund' and inv.type == 'in_invoice') or
                        (dtype == 'in_invoice' and inv.type == 'in_refund')):
                    raise UserError(
                        _('You cannot register payments for vendor bills and supplier refunds at the same time.'))
                if ((dtype == 'out_refund' and inv.type == 'out_invoice') or
                        (dtype == 'out_invoice' and inv.type == 'out_refund')):
                    raise UserError(
                        _('You cannot register payments for customer invoices and credit notes at the same time.'))

        # Look if we are mixin multiple commercical_partner or customer invoices with vendor bills
        multi = any(inv.commercial_partner_id != invoices[0].commercial_partner_id
                    or MAP_INVOICE_TYPE_PARTNER_TYPE[inv.type] != MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type]
                    or inv.account_id != invoices[0].account_id
                    or inv.partner_bank_id != invoices[0].partner_bank_id
                    for inv in invoices)

        currency = invoices[0].currency_id

        total_amount = self._compute_payment_amount(invoices=invoices, currency=currency)

        rec.update({
            'amount': abs(total_amount),
            'currency_id': currency.id,
            'payment_type': total_amount > 0 and 'inbound' or 'outbound',
            'partner_id': False if multi else invoices[0].commercial_partner_id.id,
            'partner_type': False if multi else MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type],
            'communication': ' '.join([ref for ref in invoices.mapped('reference') if ref])[:2000],
            'invoice_ids': [(6, 0, invoices.ids)],
            'multi': multi,
        })
        return rec

    @api.one
    @api.constrains('amount')
    def _check_amount(self):
        if self.amount < 0:
            raise ValidationError(_('The payment amount check be negative.'))

    @api.model
    def _get_method_codes_using_bank_account(self):
        return []

    @api.multi
    @api.depends('payment_type', 'journal_id')
    def _compute_hide_payment_method(self):
        for payment in self:
            if not payment.journal_id or payment.journal_id.type not in ['bank', 'cash']:
                payment.hide_payment_method = True
                continue
            journal_payment_methods = payment.payment_type == 'inbound' \
                                      and payment.journal_id.inbound_payment_method_ids \
                                      or payment.journal_id.outbound_payment_method_ids
            payment.hide_payment_method = len(journal_payment_methods) == 1 and journal_payment_methods[
                0].code == 'manual'

    @api.depends('invoice_ids', 'amount', 'payment_date', 'currency_id')
    def _compute_payment_difference(self):
        for pay in self.filtered(lambda p: p.invoice_ids):
            payment_amount = -pay.amount if pay.payment_type == 'outbound' else pay.amount
            pay.payment_difference = pay._compute_payment_amount() - payment_amount

    @api.depends('payment_method_code')
    def _compute_show_partner_bank(self):
        for payment in self:
            payment.show_partner_bank_account = payment.payment_method_code in self._get_method_codes_using_bank_account() and not self.multi

    @api.onchange('journal_id')
    def _onchange_journal(self):
        if self.journal_id:
            # Set default payment method (we consider the first to be the default one)
            payment_methods = self.payment_type == 'outbound' and self.journal_id.inbound_payment_method_ids or self.journal_id.outbound_payment_method_ids
            payment_method_list = payment_methods.ids

            default_payment_method_id = self.env.context.get('default_payment_method_id')
            if default_payment_method_id:
                payment_method_list.append(default_payment_method_id)
            else:
                self.payment_method_id = payment_methods and payment_methods[0] or False

            payment_type = self.payment_type in ('outbound', 'transfer') and 'outbound' or 'inbound'
            return {
                'domain': {
                    'payment_method_id': [('payment_type', '=', payment_type), ('id', 'in', payment_method_list)]
                }
            }
        return {}

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if not self.multi and self.invoice_ids and self.invoice_ids[0].partner_bank_id:
            self.partner_bank_account_id = self.invoice_ids[0].partner_bank_id
        elif self.partner_id != self.partner_bank_account_id.partner_id:
            if self.partner_id and len(self.partner_id.bank_ids) > 0:
                self.partner_bank_account_id = self.partner_id.bank_ids[0]
            elif self.partner_id and len(self.partner_id.commercial_partner_id.bank_ids) > 0:
                self.partner_bank_account_id = self.partner_id.commercial_partner_id.bank_ids[0]
            else:
                self.partner_bank_account_id = False
        return {'domain': {
            'partner_bank_account_id': [
                ('partner_id', 'in', [self.partner_id.id, self.partner_id.commercial_partner_id.id])]
        }}

    def _compute_journal_domain_and_types(self):
        journal_type = ['bank', 'cash']
        domain = []
        if self.currency_id.is_zero(self.amount) and self.has_invoices:
            journal_type = ['general']
            self.payment_difference_handling = 'reconcile'
        else:
            if self.payment_type == 'inbound':
                domain.append(('at_least_one_inbound', '=', True))
            else:
                domain.append(('at_least_one_outbound', '=', True))
        return {'domain': domain, 'journal_types': set(journal_type)}

    @api.onchange('amount', 'currency_id')
    def _onchange_amount(self):
        jrnl_filters = self._compute_journal_domain_and_types()
        journal_types = jrnl_filters['journal_types']
        domain_on_types = [('type', 'in', list(journal_types))]
        if self.journal_id.type not in journal_types:
            self.journal_id = self.env['account_journal'].search(domain_on_types, limit=1)
        return {'domain': {'journal_id': jrnl_filters['domain'] + domain_on_types}}

    @api.onchange('currency_id')
    def _onchange_currency(self):
        self.amount = abs(self._compute_payment_amount())

        if self.journal_id:
            return
        journal = self.env['account.journal'].search(
            [('type', 'in', ('bank', 'cash')), ('currency_id', '=', self.currency_id.id)], limit=1)
        if journal:
            return {'value': {'journal_id': journal.id}}

    @api.multi
    def _compute_payment_amount(self, invoices=None, currency=None):
        if not invoices:
            invoices = self.invoice_ids

        if not currency:
            currency = self.currency_id or self.journal_id.currency_id or self.journal_id.company_id.currency_id or invoices and \
                       invoices[0].currency_id

        invoice_datas = invoices.read_group([('id', 'in', invoices.ids)], ['currency_id', 'type', 'residual_signed'],
                                            ['currency_id', 'type'], lazy=False)
        total = 0.0
        for invoice_data in invoice_datas:
            amount_total = MAP_INVOICE_TYPE_PAYMENT_SIGN[invoice_data['type']] * invoice_data['residual_signed']
            payment_currency = self.env['res.currency'].browse(invoice_data['currency_id'][0])
            if payment_currency == currency:
                total += amount_total
            else:
                total += payment_currency._convert(amount_total, currency, self.env.user.company_id,
                                                   self.payment_date or fields.Date.today())
        return total


class account_register_payments(models.TransientModel):
    _name = 'account.register.payments'
    _inherit = 'account.abstract.payment'
    _description = 'Register Payments'

    group_invoices = fields.Boolean(string='Group Invoices')
    show_communication_field = fields.Boolean(compute='_compute_show_communication_field')

    @api.depends('invoice_ids.partner_id', 'group_invoices')
    def _compute_show_communication_field(self):
        for record in self:
            record.show_communication_field = len(record.invoice_ids) == 1 \
                                              or record.group_invoices and len(
                record.mapped('invoice_ids.partner_id.commercial_partner_id')) == 1

    @api.onchange('journal_id')
    def _onchange_journal(self):
        res = super(account_register_payments, self)._onchange_journal()
        active_ids = self._context.get('active_ids')
        invoices = self.env['account.invoice'].browse(active_ids)
        self.amount = abs(self._compute_payment_amount(invoices))
        return res

    @api.model
    def default_get(self, fields):
        rec = super(account_register_payments, self).default_get(fields)
        active_ids = self._context.get('active_ids')

        if not active_ids:
            raise UserError(_('Programing error: wizard action executed without active_ids in context.'))

        return rec

    @api.multi
    def _groupby_invoices(self):
        if not self.group_invoices:
            return {inv.id: inv for inv in self.invoice_ids}

        results = {}
        for inv in self.invoice_ids:
            partner_id = inv.commercial_partner_id.id
            account_id = inv.account_id.id
            invoice_type = MAP_INVOICE_TYPE_PARTNER_TYPE[inv.type]
            recipient_account = inv.partner_bank_id
            key = (partner_id, account_id, invoice_type, recipient_account)
            if not key in results:
                results[key] = self.env['account.invoice']
            results[key] += inv
        return results

    @api.multi
    def _prepare_payment_vals(self, invoices):
        amount = self._compute_payment_amount(invoices=invoices) if self.multi else self.amount
        payment_type = ('inbound' if amount > 0 else 'outbound') if self.multi else self.payment_type
        bank_account = self.multi and invoices[0].partner_bank_id or self.partner_bank_account_id
        pmt_communication = self.show_communication_field and self.communication \
                            or self.group_invoices and ' '.join([inv.reference or inv.number for inv in invoices]) \
                            or invoices[0].reference
        values = {
            'journal_id': self.journal_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_date': self.payment_date,
            'communication': pmt_communication,
            'invoice_ids': [(6, 0, invoices.ids)],
            'payment_type': payment_type,
            'amount': abs(amount),
            'currency_id': self.currency_id.id,
            'partner_id': invoices[0].commercial_partner_id.id,
            'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type],
            'partner_bank_account_id': bank_account.id,
            'multi': False,
            'payment_difference_handling': self.payment_difference_handling,
            'writeoff_account_id': self.writeoff_account_id.id,
            'writeoff_label': self.writeoff_label,
        }
        return values

    @api.multi
    def get_payments_vals(self):
        if self.multi:
            groups = self._groupby_invoices()
            return [self._prepare_payment_vals(invoices) for invoices in groups.values()]
        return [self._prepare_payment_vals(self.invoices_ids)]

    @api.multi
    def create_payments(self):
        Payment = self.env['account.payment']
        payments = Payment
        for payment_vals in self.get_payments_vals():
            payments += Payment.create(payment_vals)
        payments.post()

        action_vals = {
            'name': _('Payments'),
            'domain': [('id', 'in', payments.ids), ('state', '=', 'posted')],
            'view_type': 'form',
            'res_model': 'account.payment',
            'view_id': False,
            'type': 'ir.actions.act_window',
        }
        if len(payments) == 1:
            action_vals.update({'res_id': payments[0].id, 'view_mode': 'form'})
        else:
            action_vals['view_form'] = 'tree,form'
        return action_vals


class account_payment(models.Model):
    _name = 'account.payment'
    _inherit = ['mail.thread', 'account.abstract.payment']
    _description = 'Payments'
    _order = 'payment_date desc, name desc'

    @api.multi
    @api.depends('move_line_ids.reconciled')
    def _get_move_reconciled(self):
        for payment in self:
            rec = True
            for aml in payment.move_line_ids.filtered(lambda x: x.account_id.reconcile):
                if not aml.reconciled:
                    rec = False
            payment.move_reconciled = rec

    company_id = fields.Many2one('res.company', related='journal_id.company_id', string='Company', readonly=True)
    name = fields.Char(readonly=True, copy=False)
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Posted'), ('sent', 'Sent'), ('reconciled', 'Reconciled'),
                              ('cancelled', 'Cancelled')], readonly=True, default='draft')
    payment_type = fields.Selection(selection_add=[('transfer', 'Internal Transfer')])
    payment_reference = fields.Char(copy=False, readonly=True)
    move_name = fields.Char(string='Journal Entry Name', readonly=True, default=False, copy=False)
    destination_account_id = fields.Many2one('account.account', compute='_compute_destination_account_id',
                                             readonly=True)
    destination_journal_id = fields.Many2one('account.journal', string='Transfer To',
                                             domain=[('type', 'in', ('bank', 'cash'))])
    invoice_ids = fields.Many2many('account.invoice', 'account_invoice_payment_rel', 'payment_id', 'invoice_id',
                                   string='Invoices', copy=False, readonly=True)
    reconciled_invoice_ids = fields.Many2many('account.invoice', string='Reconciled Invoices',
                                              compute='_compute_reconciled_invoice_ids')
    has_invoices = fields.Boolean(compute='_compute_reconciled_invoice_ids')
    move_line_ids = fields.One2many('account.move.line', 'payment_id', readonly=True, copy=False, ondelete='restrict')
    move_reconciled = fields.Boolean(compute='_get_move_reconciled', readonly=False)

    def open_payment_matching_screen(self):
        move_line_id = False
        for move_line in self.move_line_ids:
            if move_line.account_id.reconcile:
                move_line_id = move_line.id
                break
        if not self.partner_id:
            raise UserError(_('Payments without a customer can\'t be matched'))
        action_context = {'company_ids': [self.company_id.id],
                          'partner_ids': [self.partner_id.commercial_partner_id.id]}
        if self.partner_type == 'customer':
            action_context.update({'mode': 'customers'})
        elif self.partner_type == 'supplier':
            action_context.update({'mode': 'suppliers'})
        if move_line_id:
            action_context.update({'move_line_id': move_line_id})
        return {
            'type': 'ir.actions.client',
            'tag': 'manual_reconcileiation_view',
            'context': action_context
        }

    @api.one
    @api.depends('invoice_ids', 'payment_type', 'partner_type', 'partner_id')
    def _compute_destination_account_id(self):
        if self.invoice_ids:
            self.destination_account_id = self.invoice_ids[0].account_id.id
        elif self.payment_type == 'transfer':
            if not self.company_id.transfer_account_id.id:
                raise UserError(_('There is no Transfer Account defined in the accounting settings.'))
            self.destination_account_id = self.company_id.transfer_account_id.id
        elif self.partner_id:
            if self.partner_type == 'customer':
                self.destination_account_id = self.partner_id.property_account_receivable_id.id
            else:
                self.destination_account_id = self.partner_id.property_account_payable_id.id
        elif self.partner_type == 'customer':
            default_account = self.env['ir.property'].get('property_account_receivable_id', 'res.partner')
            self.destination_account_id = default_account.id
        elif self.partner_type == 'supplier':
            default_account = self.env['ir.property'].get('property_account_payable_id', 'res.partner')
            self.destination_account_id = default_account.id

    @api.depends('move_line_ids.matched_debit_ids', 'move_line_ids.matched_credit_ids')
    def _compute_reconciled_invoice_ids(self):
        for record in self:
            record.reconciled_invoice_ids = (record.move_line_ids.mapped('matched_debit_ids.debit_move_id.invoice_id') |
                                             record.move_line_ids.mapped(
                                                 'matched_credit_ids.credit_move_id.invoice_id'))
            record.has_invoices = bool(record.reconciled_invoice_ids)

    @api.onchange('partner_type')
    def _onchange_partner_type(self):
        self.ensure_one()
        if self.partner_type:
            return {'domain': {'partner_id': [(self.partner_type, '=', True)]}}

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        if not self.invoice_ids:
            if self.payment_type == 'inbound':
                self.partner_type = 'customer'
            elif self.payment_type == 'outbound':
                self.partner_type = 'supplier'
            else:
                self.partner_type = False

        res = self._onchange_journal()
        if not res.get('domain', {}):
            res['domain'] = {}
        jrnl_filters = self._compute_journal_domain_and_types()
        journal_types = jrnl_filters['journal_types']
        journal_types.update(['bank', 'cash'])
        res['domain']['journal_id'] = jrnl_filters['domain'] + [('type', 'in', list(journal_types))]
        return res

    @api.model
    def default_get(self, fields):
        rec = super(account_payment, self).default_get(fields)
        invoice_defaults = self.resolve_2many_commands('invoice_ids', rec.get('invoice_ids'))
        if invoice_defaults and len(invoice_defaults) == 1:
            invoice = invoice_defaults[0]
            rec['communication'] = invoice['reference'] or invoice['name'] or invoice['number']
            rec['currency_id'] = invoice['currency_id'][0]
            rec['payment_type'] = invoice['type'] in ('out_invoice', 'in_refund') and 'inbound' or 'outbound'
            rec['partner_type'] = MAP_INVOICE_TYPE_PARTNER_TYPE[invoice['type']]
            rec['partner_id'] = invoice['partner_id'][0]
            rec['amount'] = invoice['residual']
        return rec

    @api.model
    def create(self, vals):
        rslt = super(account_payment, self).create(vals)
        if not rslt.partner_bank_account_id and rslt.show_partner_bank_account and rslt.partner_id.bank_ids:
            rslt.partner_bank_account_id = rslt.partner_id.bank_ids[0]
        return rslt

    @api.multi
    def button_journal_entries(self):
        return {
            'name': _('Journal Items'),
            'view_type': 'form',
            'view_mode': 'tree, form',
            'res_model': 'account.move.line',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('payment_id', 'in', self.ids)],
        }

    @api.multi
    def button_invoices(self):
        if self.partner_type == 'supplier':
            views = [(self.env.ref('account.invoice_supplier_tree').id, 'tree'),
                     (self.env.ref('account.invoice_supplier_form').id, 'form')]
        else:
            views = [(self.env.ref('account.invoice_tree').id, 'tree'),
                     (self.env.ref('account.invoice_form').id, 'form')]
        return {
            'name': _('Paid Invoices'),
            'view_type': 'form',
            'view_mode': 'tree, form',
            'res_model': 'account.invoice',
            'view_id': False,
            'views': views,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', [x.id for x in self.reconciled_invoice_ids])]
        }

    @api.multi
    def button_dummy(self):
        return True

    @api.multi
    def unreconcile(self):
        for payment in self:
            if payment.payment_reference:
                payment.write({'state': 'sent'})
            else:
                payment.write({'state': 'posted'})

    @api.multi
    def cancel(self):
        for rec in self:
            for move in rec.move_line_ids.mapped('move_id'):
                if rec.invoice_ids:
                    move.line_ids.remove_move_reconcile()
                move.button_cancel()
                move.unlink()
            rec.state = 'cancelled'

    @api.multi
    def unlink(self):
        if any(bool(rec.move_line_ids) for rec in self):
            raise UserError(_('You cannot delete a payment that is already posted.'))
        if any(rec.move_name for rec in self):
            raise UserError(_('It is not allowed to delete a payment that already created a journal entry.'))
        return super(account_payment, self).unlink()

    @api.multi
    def post(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only a draft payment can be posted.'))

            if any(inv.state != 'open' for inv in rec.invoice_ids):
                raise ValidationError(_('The payment cannot be processed because the invoice is not open!'))

            if not rec.name:
                if rec.payment_type == 'transfer':
                    sequence_code = 'account.payment.transfer'
                else:
                    if rec.partner_type == 'customer':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.customer.invoice'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.customer.refund'
                    if rec.partner_type == 'supplier':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.supplier.refund'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.supplier.invoice'
                rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(
                    sequence_code)
                if not rec.name and rec.payment_type != 'transfer':
                    raise UserError(_('You have to define a sequence for %s in your company.') % (sequence_code,))

            amount = rec.amount * (rec.payment_type in ('outbound', 'inbound') and 1 or -1)
            move = rec._create_payment_entry(amount)

            if rec.payment_type == 'transfer':
                transfer_credit_aml = move.line_ids.filtered(
                    lambda r: r.account_id == rec.company_id.transfer_account_id)
                transfer_debit_aml = rec._create_transfer_entry(amount)
                (transfer_credit_aml + transfer_debit_aml).reconcile()

            rec.write({'state': 'posted', 'move_name': move.name})
        return True

    @api.multi
    def account_draft(self):
        return self.write({'state': 'draft'})

    def action_validate_invoice_payment(self):
        if any(len(record.invoice_ids) != 1 for record in self):
            raise UserError(_('This method should only be called to process a single invoice\'s payment.'))
        return self.post()

    def _create_payment_entry(self, amount):
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        debit, credit, amount_currency, currency_id = aml_obj.with_context(
            date=self.payment_date)._compute_amount_fields(amount, self.currency_id, self.company_id.currency_id)

        move = self.env['acount.move'].create(self._get_move_vals())

        counterpart_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, move.id, False)
        counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
        counterpart_aml_dict.update({'currency_id': currency_id})
        counterpart_aml = aml_obj.create(counterpart_aml_dict)

        if self.payment_difference_handling == 'reconcile' and self.payment_difference:
            writeoff_line = self._get_shared_move_line_vals(0, 0, 0, move.id, False)
            debit_wo, credit_wo, amount_currency_wo, currency_id = aml_obj.with_context(
                date=self.payment_date)._compute_amount_fields(self.payment_difference, self.currency_id,
                                                               self.company_id.currency_id)
            writeoff_line['name'] = self.writeoff_label
            writeoff_line['account_id'] = self.writeoff_account_id.id
            writeoff_line['debit'] = debit_wo
            writeoff_line['credit'] = credit_wo
            writeoff_line['amount_currency'] = amount_currency_wo
            writeoff_line['currency_id'] = currency_id
            writeoff_line = aml_obj.create(writeoff_line)
            if counterpart_aml['debit'] or (writeoff_line['credit'] and not counterpart_aml['credit']):
                counterpart_aml['debit'] += credit_wo - debit_wo
            if counterpart_aml['credit'] or (writeoff_line['debit'] and not counterpart_aml['debit']):
                counterpart_aml['credit'] += debit_wo - credit_wo
            counterpart_aml['amount_currency'] -= amount_currency_wo

        if not self.currency_id.is_zero(self.amount):
            if not self.currency_id != self.company_id.currency_id:
                amount_currency = 0
            liquidity_aml_dict = self._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, False)
            liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
            aml_obj.create(liquidity_aml_dict)

        if not self.journal_id.post_at_bank_rec:
            move.post()

        if self.invoice_ids:
            self.invoice_ids.register_payment(counterpart_aml)

        return move

    def _create_transfer_entry(self, amount):
        aml_obj = self.env['account.move.line'].with_context(check_move_valdity=False)
        debit, credit, amount_currency, dummy = aml_obj.with_context(date=self.payment_date)._compute_amount_fields(
            amount, self.currency_id, self.company_id.currency_id)
        amount_currency = self.destination_journal_id.currency_id and self.currency_id._convert(amount,
                                                                                                self.destination_journal_id.currency_id,
                                                                                                self.company_id,
                                                                                                self.payment_date or fields.Date.today()) or 0

        dst_move = self.env['account.move'].create(self._get_move_vals(self.destination_journal_id))

        dst_liquidity_aml_dict = self._get_shared_move_line_vals(debit, credit, amount_currency, dst_move.id)
        dst_liquidity_aml_dict.update({
            'name': _('Transfer from %s') % self.journal_id.name,
            'account_id': self.destination_journal_id.default_credit_account_id.id,
            'currency_id': self.destination_journal_id.currency_id.id,
            'journal_id': self.destination_journal_id.id
        })
        aml_obj.create(dst_liquidity_aml_dict)

        transfer_debit_aml_dict = self._get_shared_move_line_vals(credit, debit, 0, dst_move.id)
        transfer_debit_aml_dict.update({
            'name': self.name,
            'account_id': self.company_id.transfer_account_id.id,
            'journal_id': self.destination_journal_id
        })
        if self.currency_id != self.company_id.currency_id:
            transfer_debit_aml_dict.update({
                'currency_id': self.currency_id.id,
                'amount_currency': -self.amount,
            })
        transfer_debit_aml = aml_obj.create(transfer_debit_aml_dict)
        if not self.destination_journal_id.post_at_bank_rec:
            dst_move.post()
        return transfer_debit_aml

    def _get_move_vals(self, journal=None):
        journal = journal or self.journal_id
        move_vals = {
            'date': self.payment_date,
            'ref': self.communication or '',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
        }
        if self.move_name:
            move_vals['name'] = self.move_name
        return move_vals

    def _get_shared_move_line_vals(self, debit, credit, amount_currency, move_id, invoice_id=False):
        return {
            'partner_id': self.payment_type in ('inbound', 'outbound') and self.env[
                'res.partner']._find_accounting_partner(self.partner_id).id or False,
            'invoice_id': invoice_id and invoice_id.id or False,
            'move_id': move_id,
            'debit': debit,
            'credit': credit,
            'amount_currency': amount_currency or False,
            'payment_id': self.id,
            'journal_id': self.journal_id.id,
        }

    def _get_counterpart_move_line_vals(self, invoice=False):
        if self.payment_type == 'transfer':
            name = self.name
        else:
            name = ''
            if self.partner_type == 'customer':
                if self.payment_type == 'inbound':
                    name += _('Customer Payment')
                elif self.payment_type == 'outbound':
                    name += _('Customer Credit Note')
            elif self.partner_type == 'supplier':
                if self.payment_type == 'inbound':
                    name += _('Vendor Credit Note')
                elif self.payment_type == 'outbound':
                    name += _('Vendor Payment')
            if invoice:
                name += ': '
                for inv in invoice:
                    if inv.move_id:
                        name += inv.number + ', '
                name = name[:len(name) - 2]
        return {
            'name': name,
            'account_id': self.destination_account_id.id,
            'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
        }

    def _get_liquidity_move_line_vals(self, amount):
        name = self.name
        if self.payment_type == 'transfer':
            name = _('Transfer to %s') % self.destination_journal_id.name
        vals = {
            'name': name,
            'account_id': self.payment_type in ('outbound', 'transfer') and self.journal_id.default_debit_account_id.id \
                          or self.journal_id.default_credit_account_id.id,
            'journal_id': self.journal_id.id,
            'currency_id': self.currency_id != self.company_id.currency_id and self.currency_id.id or False,
        }

        if self.journal_id.currency_id and self.currency_id != self.journal_id.currency_id:
            amount = self.currency_id._convert(amount, self.journal_currency_id, self.company_id,
                                               self.payment_date or fields.Date.today())
            debit, credit, amount_currency, dummy = self.env['account.move.line'].with_context(
                date=self.payment_date)._compute_amount_fields(amount, self.journal_id.currency_id,
                                                               self.company_id.currency_id)
            vals.update({
                'amount_currency': amount_currency,
                'currency_id': self.journal_id.currency_id.id,
            })
        return vals

    def _get_invoice_payment_amount(self, inv):
        self.ensure_one()
        return sum([
            data['amount'] for data in inv._get_payments_vals() if data['account_payment_id'] == self.id
        ])
