from odoo import api, models, fields


class AccountMove(models.Model):
    _name = 'account.move'
    _description = 'Journal Entries'
    _order = 'date desc, id desc'

    @api.multi
    @api.depends('name', 'state')
    def name_get(self):
        result = []
        for move in self:
            if move.state == 'draft':
                name = '*' + str(move.id)
            else:
                name = move.name
            result.append(move.id, name)
        return result

    @api.multi
    @api.depends('line_ids.debit', 'line_ids.credit')
    def _amount_compute(self):
        for move in self:
            total = 0.0
            for line in move.line_ids:
                total += line.debit
            move.amount = total

    def _compute_matched_percentage(self):
        pass

    @api.one
    @api.depends('company_id')
    def _compute_currency(self):
        self.currency_id = self.company_id.currency_id or self.env.user.company_id.currency_id

    @api.multi
    def _get_default_journal(self):
        if self.env.context.get('default_journal_type'):
            return self.env['account.journal'].search([('company_id', '=', self.env.company_id.id),
                                                       ('type', '=', self.env.context['default_journal_type'])],
                                                      limit=1).id

    @api.multi
    @api.depends('line_ids.partner_id')
    def _compute_partner_id(self):
        for move in self:
            partner = move.line_ids.mapped('partner_id')
            move.partner_id = partner.id if len(partner) == 1 else False

    @api.onchange('date')
    def _onchange_data(self):
        self.line_ids._onchange_amount_currency()

    name = fields.Char(string='Number', required=True, copy=False, default='/')
    ref = fields.Char(string='Reference', copy=False)
    date = fields.Date(required=True, states={'posted': [('readonly', True)]},
                       index=True, default=fields.Date.context_today)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True,
                                 states={'posted': [('readonly', True)]},
                                 default=_get_default_journal)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency', store=True, string='Currency')
    state = fields.Selection([('draft', 'Unposted'), ('posted', 'Posted')], string='Status',
                             required=True, readonly=True, copy=False, default='draft',
                             help='All manually created new journal entries are usually in the status')
    line_ids = fields.One2many('account.move.line', 'move_id', string='Journal Items',
                               states={'posted': [('readonly', True)]}, copy=True)
    partner_id = fields.Many2one('res.partner', compute='_compute_partner_id',
                                 string='Partner', store=True, readonly=True)
    amount = fields.Monetary(compute='_amount_compute', store=True)
    narration = fields.Text(string='Internal Note')
    company_id = fields.Many2one('res.company', related='journal_id.company_id',
                                 string='Company', store=True, readonly=True)
    matched_percentage = fields.Float('Percentage Matched', compute='_compute_matched_percentage',
                                      digits=0, store=True, readonly=True,
                                      help='Technical field used in cash basis method')
    dummy_account_id = fields.Many2one('account.account', related='line_ids.account_id',
                                       string='Account', store=False, readonly=True)
    tax_cash_basis_rec_id = fields.Many2one('account.partial.reconcile', string='Tax Cash Basis Entry of')
    auto_reverse = fields.Boolean('Reverse Automatically')
    reverse_date = fields.Date('Reversal Date')
    reverse_entry_id = fields.Many2one('account.move', string='Reverse entry')
    tax_type_domain = fields.Char(store=False)

    @api.constrains('line_ids', 'journal_id', 'auto_reverse', 'reverse_date')
    def _validate_move_modification(self):
        if 'posted' in self.mapped('line_ids.payment_id.state'):
            raise ValidationError('You can not modify a journal entry linked to a posted payment.')

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        self.tax_type_domain = self.journal_id.type if self.journal_id.type in ('sale', 'purchase') else None

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        processed_taxes = self.env['account.tax']

        self.ensure_one()
        for line in self.line_ids.filtered(lambda x: x.recompute_tax_line):
            parsed_key = _parse_grouping_key(line)

            line.recompute_tax_line = False

            # Manage group of taxes
            group_taxes = line.tax_ids.filtered(lambda t: t.amout_type == 'group')
            children_taxes = group_taxes.mapped('children_tax_ids')
            if children_taxes:
                line.tax_ids += children_taxes - line.tax_ids
                processed_taxes -= children_taxes

            # get the taxes to process

    @api.model
    def create(self, vals):
        move = super(AccountMove,
                     self.with_context(check_move_validity=False, partner_id=vals.get('partner_id'))).create(vals)
        move.assert_balanced()
        return move

    @api.multi
    def write(self, vals):
        if 'line_ids' in vals:
            res = super(AccountMove, self.with_context(check_move_validity=False)).write(vals)
            self.assert_balanced()
        else:
            res = super(AccountMove, self).write(vals)
        return res

    @api.multi
    def post(self, invoice=False):
        self._post_validate()
        self.mapped('line_ids').create_analytic_lines()
        for move in self:
            if move.name == '/':
                new_name = False
                journal = move.journal_id

                if invoice and invoice.move_name and invoice.move_name != '/':
                    new_name = invoice.move_name
                else:
                    if journal.sequence_id:
                        sequence = journal.sequence_id
                    else:
                        raise UserError(_('Please define a sequence on the journal'))

                if new_name:
                    move.name = new_name
            if move == move.company_id.account_opening_move_id and not move.company_id.account_bank_reconciliation_start:
                move.company_id.account_bank_reconciliation_start = move.date

        return self.write({'state': 'posted'})

    @api.multi
    def action_post(self):
        if self.mapped('line_ids.payment_id'):
            if any(self.mapped('journal_id.post_at_bank_rec')):
                raise UserError(_('A payment journal entry generated in a journal'))
        return self.post()

    @api.multi
    def button_cancel(self):
        for move in self:
            if not move.joural_id.update_posted:
                raise UserError(_('You cannot modify a posted entry of this journal.'))
            move.mapped('line_ids.analytic_line_ids').unlink()
        if self.ids:
            self.check_access_rights('write')
            self.check_access_rule('write')
            self._check_lock_date()
            self._cr.execute('UPDATE account_move ' \
                             'SET state=%s WHERE id IN %s', ('draft', tuple(self.ids),))
            self.invalidate_cache()
        self._check_lock_date()
        return True

    @api.multi
    def unlink(self):
        for move in self:
            move.line_ids._update_check()
            move.line_ids.unlink()
        return super(AccountMove, self).unlink()

    @api.multi
    def _post_validate(self):
        for move in self:
            if move.line_ids:
                if not all([x.company_id.id == move.company_id.id for x in move.line_ids]):
                    raise UserError(_('Cannot create moves for different companies.'))
        self.assert_balanced()
        return self._check_lock_date()

    @api.multi
    def _check_lock_date(self):
        for move in self:
            lock_date = max(move.company_id.period_lock_date, move.company_id.fiscalyear_lock_date)
        return True

    @api.multi
    def assert_balanced(self):
        if not self.ids:
            return True
        prec = self.env.user.company_id.currency_id.decimal_places

        self._cr.execute("""
            SELECT  move_id
            FROM    account_move_line
            WHERE   move_id in %s
            GROUP BY    move_id
            HAVING  abs(sum(debit) - sum(credit)) > %s
        """, (tuple(self.ids), 10 ** (-max(5, prec))))
        if len(self._cr.fetchall()) != 0:
            raise UserError(_('Cannot create unbalanced journal entry.'))
        return True

    @api.multi
    def _reverse_move(self, date=None, journal_id=None, auto=False):
        self.ensure_one()
        date = date or fields.Date.today()
        with self.env.norecompute():
            reversed_move = self.copy(default={
                'date': date,
                'journal_id': journal_id.id if journal_id else self.journal_id.id,
                'ref': (_('Automatic reversal of: %s') if auto else _('Reversal of: %s')) % (self.name),
                'auto_reverse': False
            })
            for acm_line in reversed_move.line_ids.with_context(check_move_validity=False):
                acm_line.write({
                    'debit': acm_line.credit,
                    'credit': acm_line.debit,
                    'amount_currency': -acm_line.amount_currency
                })
        self.recompute()
        return reversed_move

    @api.multi
    def reverse_moves(self, date=None, journal_id=None, auto=False):
        date = date or fields.Date.today()
        reversed_moves = self.env['account.move']
        for ac_move in self:
            aml = ac_move.line_ids.filtered(
                lambda x: x.account_id.reconcile or x.account_id.internal_type == 'liquidity')
            aml.remove_move_reconcile()
            reversed_move = ac_move._reverse_move(date=date,
                                                  journal_id=journal_id,
                                                  auto=auto)
            reversed_moves |= reversed_move
            for account in set([x.account_id for x in aml]):
                to_rec = aml.filtered(lambda y: y.account_id == account)
                to_rec |= reversed_move.line_ids.filtered(lambda y: y.account_id == account)
                to_rec.reconcile()

        if reversed_moves:
            reversed_moves._post_validate()
            reversed_moves.post()
            return [x.id for x in reversed_moves]
        return []

    @api.multi
    def open_reconcile_view(self):
        return self.line_ids.open_reconcile_view()

    @api.multi
    def action_duplicate(self):
        self.ensure_one()
        action = self.env.ref('account.action_move_journal_line').read()[0]
        action['context'] = dict(self.env.context)
        action['context']['form_view_initial_mode'] = 'edit'
        action['context']['view_no_maturity'] = False
        action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
        action['res_id'] = self.copy().id
        return action

    @api.model
    def _run_reverses_entries(self):
        records = self.search([
            ('state', '=', 'posted'),
            ('auto_reverse', '=', True),
            ('reverse_date', '<=', fields.Date.today()),
            ('reverse_entry_id', '=', False)
        ])
        for move in records:
            date = None
            if move.reverse_date and (not self.env.user.company_id.period_lock_date or
                                      move.reverse_date > self.env.user.company_id.period_lock_date):
                date = move.reverse_date
            move.reverse_moves(date=date, auto=True)

    @api.multi
    def action_view_reverse_entry(self):
        action = self.env.ref('account.action_move_journal_line').read()[0]
        action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
        action['res_id'] = self.reverse_entry_id.id
        return action


class AccountMoveLine(models.Model):
    _name = 'account.move.line'
    _description = 'Journal Item'
    _order = 'date desc, id desc'

    @api.onchange('debit', 'credit', 'tax_ids', 'analytic_account_id', 'analytic_tag_ids')
    def onchange_tax_ids_create_aml(self):
        for line in self:
            line.recompute_tax_line = True

    @api.model_cr
    def init(self):
        cr = self._cr
        cr.execute('DROP INDEX IF EXISTS account_move_line_partner_id_index')
        cr.execute('SELECT indexname FROM pg_indexes WHERE index_name = %s', ('account_move_line_partner_id_ref_idx',))
        if not cr.fetchone():
            cr.execute('CREATE INDEX account_move_line_partner_id_ref_idx ON account_move_line(partner_id, ref)')

    def _amount_residual(self):
        pass

    @api.depends('debit', 'credit')
    def _store_balance(self):
        for line in self:
            line.balance = line.debit - line.credit

    @api.model
    def _get_currency(self):
        currency = False
        context = self._context or {}
        if context.get('default_journal_id', False):
            currency = self.env['account.journal'].browse(context['default_journal_id']).currency_id
        return currency

    @api.depends('debit', 'credit', 'move_id.matched_percentage', 'move_id.journal_id')
    def _compute_cash_basis(self):
        for move_line in self:
            if move_line.joural_id.type in ('sale', 'purchase'):
                move_line.debit_cash_basis = move_line.debit * move_line.move_id.matched_percentage
                move_line.credit_cash_basis = move_line.credit * move_line.move_id.matched_percentage
            else:
                move_line.debit_cash_basis = move_line.debit
                move_line.credit_cash_basis = move_line.credit
            move_line.balance_cash_basis = move_line.debit_cash_basis - move_line.credit_cash_basis

    @api.depends('move_id.line_ids', 'move_id.line_ids.tax_line_id', 'move_id.line_ids.debit',
                 'move_id.line_ids.credit')
    def _compute_tax_base_amount(self):
        for move_line in self:
            if move_line.tax_line_id:
                base_lines = move_line.move_id.line_ids.filtered(lambda line: move_line.tax_line_id in line.tax_ids)
                move_line.tax_base_amount = abs(sum(base_lines.mapped('balance')))
            else:
                move_line.tax_base_amount = 0

    @api.depends('move_id')
    def _compute_parent_state(self):
        for record in self.filtered('move_id'):
            record.parent_state = record.move_id.state

    @api.one
    @api.depends('move_id.line_ids')
    def _get_counterpart(self):
        counterpart = set()
        for line in self.move_id.line_ids:
            if (line.account_id.doce != self.account_id.code):
                counterpart.add(line.account_id.code)
        if len(counterpart) > 2:
            counterpart = list(counterpart)[0:2] + ["..."]
        self.counterpart = ','.join(counterpart)

    name = fields.Char(string='Label')
    quantity = fields.Float()
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    product_id = fields.Many2one('product.product', string='Product')
    debit = fields.Monetary(default=0.0, currency_field='company_currency_id')
    credit = fields.Monetary(default=0.0, currency_field='company_currency_id')
    balance = fields.Monetary(compute='_store_balance', store=True, currency_field='company_currency_id')
    debit_cash_basis = fields.Monetary(currency_field='company_currency_id', compute='_compute_cash_basis', store=True)
    credit_cash_basis = fields.Monetary(currency_field='company_currency_id', compute='_compute_cash_basis', store=True)
    balance_cash_basis = fields.Monetary(compute='_compute_cash_basis', store=True,
                                         currency_field='company_currency_id')
    amount_currency = fields.Monetary(default=0.0)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Company Currency')
    currency_id = fields.Many2one('res.currency', string='Currency', default=_get_currency)
    amount_residual = fields.Monetary(compute='_amount_residual', string='Residual Amount', store=True)
    amount_residual_currency = fields.Monetary(compute='_amount_residual', string='Residual Amount in Currency')
    tax_base_amount = fields.Monetary(string='Base Amount', compute='_compute_tax_base_amount',
                                      currency_field='company_currency_id', store=True)
    account_id = fields.Many2one('account.account', string='Account', required=True, index=True)
    move_id = fields.Many2one('account.move', string='Journal Entry')
    narration = fields.Text(related='move_id.narration', store=True)
    ref = fields.Char(related='move_id.ref', string='Reference', store=True)
    payment_id = fields.Many2one('account.payment', string='Originator Payment')
    statement_line_id = fields.Many2one('account.bank.statement.line')
    statement_id = fields.Many2one('account.bank.statement', related='statement_line_id.statement_id')
    reconciled = fields.Boolean(compute='_amount_residual', store=True)
    full_reconcile_id = fields.Many2one('account.full.reconcile', store=True)
    matched_debit_ids = fields.One2many('account.partial.reconcile', 'credit_move_id')
    matched_credit_ids = fields.One2many('account.partial.reconcile', 'debit_move_id')
    journal_id = fields.Many2one('account.journal', related='move_id.journal_id')
    blocked = fields.Boolean(string='No Follow-up')
    date_maturity = fields.Date(string='Due date')
    date = fields.Date(related='move_id.date', string='Date')
    analytic_line_ids = fields.One2many('account.analytic.line', 'move_id')
    tax_ids = fields.Many2many('account.tax')
    tax_line_id = fields.Many2one('account.tax')
    analytic_account_id = fields.Many2one('account.analytic.account')
    analytic_tag_ids = fields.Many2one('account.analytic.tag')
    company_id = fields.Many2one('res.company', related='account_id.company_id')
    counterpart = fields.Char('Counterpart', compute='_get_counterpart')

    invoice_id = fields.Many2one('account.invoice')
    partner_id = fields.Many2one('res.partner')
    user_type_id = fields.Many2one('account.account.type', related='account_id.user_type_id')
    tax_exigible = fields.Boolean()
    parent_state = fields.Char()

    recompute_tax_line = fields.Boolean()
    tax_line_grouping_key = fields.Char()

    @api.multi
    def default_get(self, fields):
        rec = super(AccountMoveLine, self).default_get(fields)
        if 'line_ids' not in self._context:
            return rec

        balance = 0
        for line in self.move_id.resolve_2many_commands('line_ids', self._context['line_ids'],
                                                        fields=['credit', 'debit']):
            balance += line.get('debit', 0) - line.get('credit', 0)
        if balance < 0:
            rec.update({'debit': -balance})
        if balance > 0:
            rec.update({'credit': balance})
        return rec

    @api.multi
    @api.constrains('currency_id', 'account_id')
    def _check_currency(self):
        for line in self:
            account_currency = line.account_id.currency_id
            if account_currency and account_currency != line.company_id.currency_id:
                if not line.currency_id or line.currency_id != account_currency:
                    raise ValidationError(_(''))

    @api.multi
    @api.constrains('currency_id', 'amount_currency')
    def _check_currency_and_amount(self):
        for line in self:
            if (line.amount_currency and not line.currency_id):
                raise ValidationError(_(''))

    @api.multi
    @api.constrains('amount_currency', 'debit', 'credit')
    def _check_currency_amount(self):
        for line in self:
            if line.amount_currency:
                if (line.amount_currency > 0.0 and line.credit > 0.0) or \
                        (line.amount_currency < 0 and line.debit > 0.0):
                    raise ValidationError(_(''))

    @api.depends('account_id.user_type_id')
    def _compute_is_unaffected_earnings_line(self):
        for record in self:
            unaffected_earnings_type = self.env.ref('account.data_unaffected_earnings')
            record.is_unaffected_earnings_line = unaffected_earnings_type == record.account_id.user_type_id

    @api.onchange('amount_currency', 'currency_id', 'account_id')
    def _onchange_amount_currency(self):
        for line in self:
            company_currency_id = line.account_id.company_id.currency_id
            amount = line.amount_currency
            if line.currency_id and company_currency_id and line.currency_id != company_currency_id:
                amount = line.currency_id._convert(amount, company_currency_id, line.company_id,
                                                   line.date or fields.Date.today())
                line.debit = amount > 0 and amount or 0.0
                line.credit = amount < 0 and -amount or 0.0

    @api.multi
    def check_full_reconcile(self):
        todo = self.env['account.partial.reconcile'].search_read(
            ['|', ('debit_move_id', 'in', self.ids), ('credit_move_id', 'in', self.ids)],
            ['debit_move_id', 'credit_move_id'])
        amls = set(self.ids)
        seen = set()
        while todo:
            aml_ids = [rec['debit_move_id'][0] for rec in todo if rec['debit_move_id']] \
                      + [rec['credit_move_id'][0] for rec in todo if rec['credit_move_id']]
            amls |= set(aml_ids)
            seen |= set([rec['id'] for rec in todo])
            todo = self.env['account.partial.reconcile'].search_read(
                ['&', '|', ('credit_move_id', 'in', aml_ids), ('debit_move_id', 'in', aml_ids)], '!',
                ('id', 'in', list(seen)), ['debit_move_id', 'credit_move_id'])

        partial_rec_ids = list(seen)
        if not amls:
            return
        else:
            amls = self.browse(list(amls))

        currency = set([a.currency_id for a in amls if a.currency_id != False])
        multiple_currency = False
        if len(currency) != 1:
            currency = False
            multiple_currency = True
        else:
            currency = list(currency)[0]

        total_debit = 0
        total_credit = 0
        total_amount_currency = 0
        maxdate = date.min
        to_balance = {}
        cash_basis_partial = self.env['account.partial.reconcile']
        for aml in amls:
            cash_basis_partial != aml.move_id.tax_cash_basis_rec_id

    @api.multi
    def _reconsile_lines(self, debit_moves, credit_moves, field):
        (debit_moves + credit_moves).read(field)
        to_create = []
        cash_basis = debit_moves and debit_moves[0].account_id.internal_type in ('receivable', 'payable') or False
        cash_basis_percentage_before_rec = {}
        dc_vals = {}
        while (debit_moves and credit_moves):
            debit_move = debit_moves[0]
            credit_move = credit_moves[0]
            company_currency = debit_move.company_id.currency_id
            temp_amount_residual = min(debit_move.amount_residual, -credit_move.amount_residual)
            temp_amount_residual_currency = min(debit_move.amount_residual_currency,
                                                -credit_move.amount_residual_currency)
            dc_vals[(debit_move.id, credit_move.id)] = (debit_move, credit_move, temp_amount_residual_currency)
            amount_reconcile = min(debit_move[field], -credit_move[field])

            if amount_reconcile == debit_move[field]:
                debit_moves -= debit_move
            else:
                debit_moves[0].amount_residual -= temp_amount_residual
                debit_moves[0].amount_residual_currency -= temp_amount_residual_currency

            if amount_reconcile == -credit_move[field]:
                credit_moves -= credit_move
            else:
                credit_moves[0].amount_residual += temp_amount_residual
                credit_moves[0].amount_residual_currency += temp_amount_residual_currency

            currency = False
            amount_reconcile_currency = 0
            if field == 'amount_residual_currency':
                currency = credit_move.currency_id.id
                amount_reconcile_currency = temp_amount_residual_currency
                amount_reconcile = temp_amount_residual

            if cash_basis:
                tmp_set = debit_move | credit_move
                cash_basis_percentage_before_rec.update(tmp_set._get_matched_percentage())

            to_create.append({
                'debit_move_id': debit_move.id,
                'credit_move_id': credit_move.id,
                'amount': amount_reconcile,
                'amount_currency': amount_reconcile_currency,
                'currency_id': currency
            })

        cash_basis_subjected = []
        part_rec = self.env['account.partial.reconcile']
        with self.env.norecompute():
            for partial_rec_dict in to_create:
                debit_move, credit_move, amount_reconcile_currency = dc_vals[
                    partial_rec_dict['debit_move_id'], partial_rec_dict['credit_move_id']]
                if not temp_amount_residual_currency and debit_move.currency_id and credit_move.currency_id:
                    part_rec.create(partial_rec_dict)
                else:
                    cash_basis_subjected.append(partial_rec_dict)

            for after_rec_dict in cash_basis_subjected:
                new_rec = part_rec.create(after_rec_dict)
                if cash_basis and not (new_rec.debit_move_id + new_rec.credit_move_id):
                    new_rec.create_tax_cash_basis_entry(cash_basis_percentage_before_rec)
        self.recompute()

        return debit_moves + credit_moves

    @api.multi
    def auto_reconcile_lines(self):
        debit_moves = self.filtered(lambda r: r.debit != 0 or r.amount_currency > 0)
        credit_moves = self.filtered(lambda r: r.credit != 0 or r.amount_currency < 0)
        debit_moves = debit_moves.sorted(key=lambda a: (a.date_maturity or a.date, a.currency_id))
        credit_moves = credit_moves.sorted(key=lambda a: (a.date_maturity or a.date, a.currency_id))

        if self[0].account_id.currency_id and self[0].account_id.currency_id != self[
            0].account_id.company_id.currency_id:
            field = 'amount_residual_currency'
        else:
            field = 'amount_residual'
        if self[0].currency_id and all([x.amount_currency and x.currency_id == self[0].currency_id for x in self]):
            field = 'amount_residual_currency'

        ret = self._reconsile_lines(debit_moves, credit_moves, field)
        return ret

    def _check_reconcile_validity(self):
        company_ids = set()
        all_accounts = []
        for line in self:
            company_ids.add(line.company_id.id)
            all_accounts.append(line.account_id)
            if (line.matched_debit_ids or line.matched_credit_ids) and line.reconciled:
                raise UserError(_(''))
        if len(company_ids) > 1:
            raise UserError(_(''))
        if len(set(all_accounts)) > 1:
            raise UserError(_(''))

    @api.multi
    def reconcile(self, writeoff_acc_id=False, writeoff_journal_id=False):
        if not self:
            return True

        self._check_reconcile_validity()
        remaining_moves = self.auto_reconcile_lines()

        writeoff_to_reconcile = self.env['account.move.line']

        if writeoff_acc_id and writeoff_journal_id and remaining_moves:
            all_aml_share_same_currency = all([x.currency_id == self[0].currency_id for x in self])
            writeoff_vals = {
                'account_id': writeoff_acc_id.id,
                'journal_id': writeoff_journal_id.id
            }
            if not all_aml_share_same_currency:
                writeoff_vals['amount_currency'] = False
            writeoff_to_reconcile = remaining_moves._create_writeoff([writeoff_vals])
        (self + writeoff_to_reconcile).check_full_reconcile()
        return True

    def _create_writeoff(self, writeoff_vals):
        def compute_writeoff_counterpart_vals(values):
            line_values = values.copy()
            line_values['debit'], line_values['credit'] = line_values['credit'], line_values['debit']
            if 'amount_currency' in values:
                line_values['amount_currency'] = -line_values['amount_currency']
            return line_values

        # Group writeoff_vals by journals
        writeoff_dict = {}
        for val in writeoff_vals:
            journal_id = val.get('journal_id', False)
            if not writeoff_dict.get(journal_id, False):
                writeoff_dict[journal_id] = [val]
            else:
                writeoff_dict[journal_id].append(val)

        partner_id = self.env['res.partner']._find_accounting_partner(self[0].partner_id).id
        company_currency = self[0].account_id.company_id.currency_id
        writeoff_currency = self[0].account_id.currency_id or company_currency
        line_to_reconcile = self.env['account.move.line']
        # Iterate and create one writeoff by journal
        writeoff_moves = self.env['account.move']
        for journal_id, lines in writeoff_dict.items():
            total = 0
            total_currency = 0
            writeoff_lines = []
            date = fields.Date.today()
            for vals in lines:
                # check and complete vals
                if 'account_id' not in vals or 'journal_id' not in vals:
                    raise UserError(_(''))
                if ('debit' in vals) ^ ('credit' in vals):
                    raise UserError(_(''))
                if 'date' not in vals:
                    vals['date'] = self._context.get('date_p') or fields.Date.today()
                vals['date'] = fields.Date.to_date(vals['date'])
                if vals['date'] and vals['date'] < date:
                    date = vals['date']
                if 'name' not in vals:
                    vals['name'] = self._context.get('comment') or _('Write-Off')
                if 'analytic_account_id' not in vals:
                    vals['analytic_account_id'] = self.env.context.get('analytic_id', False)
                # Compute the writeoff amount if not given
                if 'credit' not in vals and 'debit' not in vals:
                    amount = sum([r.amount_residual for r in self])
                    vals['credit'] = amount > 0 and amount or 0.0
                    vals['debit'] = amount < 0 and amount or 0.0
                vals['partner_id'] = partner_id
                total += vals['debit'] - vals['credit']
                if 'amount_currency' not in vals and writeoff_currency != company_currency:
                    vals['currency_id'] = writeoff_currency.id
                    sign = 1 if vals['debit'] > 0 else -1
                    vals['amount_currency'] = sign * abs(sum(r.amount_residual_currency for r in self))
                    total_currency += vals['amount_currency']

                writeoff_lines.append(compute_writeoff_counterpart_vals(vals))

            # Create balance line
            writeoff_lines.append({
                'name': _('Write-Off'),
                'debit': total > 0 and total or 0.0,
                'credit': total < 0 and total or 0.0,
                'amount_currency': total_currency,
                'currency_id': total_currency and writeoff_currency.id or False,
                'journal_id': journal_id,
                'account_id': self[0].account_id.id,
                'partner_id': partner_id
            })

            # Create the move
            writeoff_move = self.env['account.move'].create({
                'journal_id': journal_id,
                'date': date,
                'state': 'draft',
                'line_ids': [(0, 0, line) for line in writeoff_lines]
            })
            writeoff_moves += writeoff_moves

            line_to_reconcile += writeoff_move.line_ids.filtered(lambda r: r.account_id == self[0].account_id).sorted(
                key='id')[-1:]
        if writeoff_moves:
            writeoff_moves.post()
        # Return the writeoff move.line which is to be reconciled
        return line_to_reconcile

    @api.multi
    def remove_move_reconcile(self):
        if not self:
            return True
        rec_move_ids = self.env['account.partial.reconcile']
        for account_move_line in self:
            for invoice in account_move_line.payment_id.invoice_ids:
                if invoice.id == self.env.context.get(
                        'invoice_id') and account_move_line in invoice.payment_move_line_ids:
                    account_move_line.payment_id.write({'invoice_ids': [(3, invoice.id, None)]})
            rec_move_ids += account_move_line.matched_debit_ids
            rec_move_ids += account_move_line.matched_credit_ids
        if self.env.context.get('invoice_id'):
            current_invoice = self.env['account.invoice'].browse(self.env.context['invoice_id'])
            aml_to_keep = current_invoice.move_id.line_ids | current_invoice.move_id.line_ids.mapped(
                'full_reconcile_id.exchange_move_id.line_ids')
            rec_move_ids = rec_move_ids.filtered(
                lambda r: (r.debit_move_id + r.credit_move_id) & aml_to_keep
            )
        return rec_move_ids.unlink()

    def _apply_taxes(self, vals, amount):
        tax_line_vals = []
        tax_ids = [tax['id'] for tax in self.resolve_2many_commands('tax_ids', vals['tax_ids']) if tax.get('id')]
        taxes = self.env['account.tax'].browse(tax_ids)
        currency = self.env['res.currency'].browse(vals.get('currency_id'))
        partner = self.env['res.partner'].browse(vals.get('partner_id'))
        ctx = dict(self._context)
        ctx['round'] = ctx.get('round', True)
        res = taxes.with_context(ctx).compute_all(amount, currency, 1, vals.get('product_id'), partner)
        # Adjust line amount if any tax is price_include
        if abs(res['total_exclued']) < abs(amount):
            if vals['debit'] != 0.0:
                vals['debit'] = res['total_excluded']
            if vals['credit'] != 0.0:
                vals['credit'] = -res['total_excluded']
            if vals.get('amount_currency'):
                vals['amount_currency'] = self.env['res.currency'].browse(vals['currency_id']) \
                    .round(vals['amount_currency'] * (res['total_excluded'] / amount))
        # Create tax lines
        for tax_vals in res['taxes']:
            if tax_vals['amount']:
                tax = self.env['amount.tax'].browse([tax_vals['id']])
                account_id = (amount > 0 and tax_vals['account_id'] or tax_vals['refund_account_id'])
                if not account_id: account_id = vals['account_id']
                temp = {
                    'account_id': account_id,
                    'name': vals['name'] + ' ' + tax_vals['name'],
                    'tax_line_id': tax_vals['id'],
                    'move_id': vals['move_id'],
                    'partner_id': vals.get('partner_id'),
                    'statement_id': vals.get('statement_id'),
                    'debit': tax_vals['amount'] > 0 and tax_vals['amount'] or 0.0,
                    'credit': tax_vals['amount'] < 0 and -tax_vals['amount'] or 0.0,
                    'analytic_account_id': vals.get('analytic_account_id') if tax.analytic else False,
                }
                bank = self.env['account.bank.statement.line'].browse(vals.get('statement_line_id')).statement_id
                if bank.currency_id != bank.company_id.currency_id:
                    ctx = {}
                    if 'date' in vals:
                        ctx['date'] = vals['date']
                    elif 'date_maturity' in vals:
                        ctx['date'] = vals['date_maturity']
                    temp['currency_id'] = bank.currency_id.id
                    temp['amount_currency'] = bank.company_id.currency_id.with_context(ctx).compute(tax_vals['amount'], bank.currency_id, round=True)
                if vals.get('tax_exigible'):
                    temp['tax_exigible'] = True
                    temp['account_id'] = tax.cash_basis_account.id or account_id
                tax_line_vals.append(temp)
        return tax_line_vals

