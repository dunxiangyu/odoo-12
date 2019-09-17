from odoo import api, models, fields
from odoo.exceptions import UserError, ValidationError

TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale',
    'in_refund': 'purchase',
}

TYPE2REFUND = {
    'out_inovice': 'out_refund',  # Customer Inovice
    'in_invoice': 'in_refund',  # Vendor Bill
    'out_refund': 'out_invoice',  # Customer Credit Note
    'in_refund': 'in_invoice',  # Vender Credit Note
}

MAGIC_COLUMNS = ('id', 'create_uid', 'create_date', 'write_uid', 'write_date')


class AccountInovice(models.Model):
    _name = 'account.invoice'
    _inherit = ['protal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Invoice'
    _order = 'date_invoice desc, number desc, id desc'

    def _get_default_incoterm(self):
        return self.env.user.company_id.incoterm_id

    def _compute_amount(self):
        round_curr = self.currency_id.round
        self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        self.amount_tax = sum(round_curr(line.amount_total) for line in self.tax_line_ids)
        self.amount_total = self.amount_untaxed + self.amount_tax
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id
            amount_total_company_signed = currency_id._convert(self.amount_total, self.company_id.currency_id,
                                                               self.company_id,
                                                               self.date_invoice or fields.Date.today())
            amount_untaxed_signed = currency_id._convert(self.amount_untaxed, self.company_id.currency_id,
                                                         self.company_id, self.date_invoice or fields.Date.today())
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign

    def _compute_sign_taxes(self):
        for invoice in self:
            sign = invoice.type in ['in_refund', 'out_refund'] and -1 or 1
            invoice.amount_untaxed_invoice_signed = invoice.amount_untaxed * sign
            invoice.amount_tax_signed = invoice.amount_tax * sign

    @api.conchange('amount_total')
    def _onchange_amount_total(self):
        for inv in self:
            if float_compare(inv.amount_total, 0.0, precision_rounding=inv.currency_id.rounding) == -1:
                raise Warning(_(
                    'You cannot validate an inovice with a negative total amount. You should create a credit note instead.'))

    @api.model
    def _default_journal(self):
        if self._context.get('default_journal_id', False):
            return self.env['account_journal'].browse(self._context.get('default_journal_id'))
        inv_type = self._context.get('type', 'out_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', [TYPE2JOURNAL[ty] for ty in inv_types if ty in TYPE2JOURNAL]),
            ('company_id', '=', company_id)
        ]
        company_currency_id = self.env['res.company'].browse(company_id).currency_id.id
        currency_id = self._context.get('default_currency_id') or company_currency_id
        currency_clause = [('currency_id', '=', currency_id)]
        if currency_id == company_currency_id:
            currency_clause = ['|', ('currency_id', '=', False)] + currency_clause
        return (
                self.env['account.journal'].search(domain + currency_clause, limit=1)
                or self.env['account.journal'].search(domain, limit=1)
        )

    def _default_currency(self):
        journal = self._default_journal()
        return journal.currency_id or journal.company_id.currency_id or self.env.user.company_id.currency_id

    def _get_aml_for_amount_residual(self):
        self.ensure_one()
        return self.undo().move_id.line_ids.filtered(lambda l: l.account_id == self.account_id)