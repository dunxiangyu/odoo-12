import datetime

import pytz

from odoo import api, fields, models, tools
from odoo.exceptions import UserError, ValidationError


def _create_sequence(cr, seq_name, number_increment, number_next):
    if number_increment == 0:
        raise UserError(_('Step must not be zero'))
    sql = 'CREATE SEQUENCE %s INCREMENT BY %%s START WITH %%s' % seq_name
    cr.execute(sql, (number_increment, number_next))


def _drop_sequence(cr, seq_names):
    names = ','.join(seq_names)
    cr.execute('DROP SEQUENCE IF EXISTS %s RESITRICT' % names)


def _alter_sequence(cr, seq_name, number_increment=None, number_next=None):
    if number_increment == 0:
        raise UserError(_('Step must not be zero.'))
    cr.execute('SELECT relname FROM pg_class WHERE relkind=%s AND relname=%s', ('S', seq_name))
    if not cr.fetchone():
        return
    statement = 'ALTER SEQUENCE %s' % (seq_name,)
    if number_increment is not None:
        statement += ' INCREMENT BY %d' % (number_increment,)
    if number_next is not None:
        statement += ' RESTART WITH %d' % (number_next,)
    cr.execute(statement)


def _select_nextval(cr, seq_name):
    cr.execute("SELECT nextval('%s')" % seq_name)
    return cr.fetchone()


def _update_nogap(self, number_increment):
    number_next = self.number_next
    self._cr.execute('SELECT number_next FROM %s WHERE id=%s FOR UPDATE NOWAIT' % (self._table, self.id))
    self._cr.execute('UPDATE %s SET number_next=number_next+%s WHERE id=%s' % (self._table, number_increment, self.id))
    self.invalidate_cache(['number_next'], [self.id])
    return number_next


def _predict_nextval(self, seq_id):
    query = """SELECT last_value,
        (SELECT increment_by FROM pg_sequences WHERE sequencename='ir_sequence_%(seq_id)s'), is_called FROM ir_sequence_%(seq_id)s
    """
    if self.env.cr._cnx.server_version < 100000:
        query = """SELECT last_value, increment_by, is_called FROM ir_sequence_%(seq_id)s"""
    self.env.cr.execute(query % {'seq_id': seq_id})
    (last_value, increment_by, is_called) = self.env.cr.fetchone()
    if is_called:
        return last_value + increment_by
    return last_value


class IrSequence(models.Model):
    _name = 'ir.sequence'
    _description = 'Sequence'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(string='Sequence Code')
    implementation = fields.Selection([('standard', 'Standard'), ('no_gap', 'No gap')],
                                      string='Implementation', required=True, default='standard')
    active = fields.Boolean(default=True)
    prefix = fields.Char(trim=False)
    suffix = fields.Char(trim=False)
    number_next = fields.Integer(string='Next Number', required=True, default=1)
    number_next_actual = fields.Integer(string='Actual Next Number', compute='_get_number_next_actual',
                                        inverse='_set_number_next_actual')
    number_increment = fields.Integer(string='Step', required=True, default=1)
    padding = fields.Integer(string='Sequence Size', required=True, default=1)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda s: s.env['res.company']._company_default_get('ir.sequence'))
    use_date_range = fields.Boolean(string='Use subsequences per date_range')
    data_range_ids = fields.One2many('ir.sequence.data_range', 'sequence_id', string='Subsequences')

    def _get_number_next_actual(self):
        for seq in self:
            if seq.implementation != 'standard':
                seq.number_next_actual = seq.number_next
            else:
                seq_id = '%03d' % seq.id
                seq.number_next_actual = _predict_nextval(self, seq_id)

    def _set_number_next_actual(self):
        for seq in self:
            seq.write({'number_next': seq.number_next_actual or 1})

    @api.model
    def _get_current_sequence(self):
        if not self.use_date_range:
            return self
        now = fields.Date.today()
        seq_date = self.env['ir.sequence.date_range'].search(
            [('sequence_id', '=', self.id), ('date_from', '<=', now), ('date_to', '>=', now)], limit=1)
        if seq_date:
            return seq_date[0]
        return self._create_date_range_seq(now)

    @api.model
    def create(self, values):
        seq = super(IrSequence, self).create(values)
        if values.get('implementation', 'standard') == 'standard':
            _create_sequence(self._cr, 'ir_sequence_%03d' % seq.id, values.get('number_increment', 1),
                             values.get('number_next', 1))
        return seq

    @api.multi
    def unlink(self):
        _drop_sequence(self._cr, ['ir_sequence_%03d' % x.id for x in self])
        return super(IrSequence, self).unlink()

    @api.multi
    def write(self, values):
        new_implementation = values.get('implementation')
        for seq in self:
            i = values.get('number_increment', seq.number_increment)
            n = values.get('number_next', seq.number_next)
            if seq.implementation == 'standard':
                if new_implementation in ('standard', None):
                    if values.get('number_next'):
                        _alter_sequence(self._cr, 'ir_sequence_%03d' % seq.id, number_next=n)
                    if seq.number_increment != i:
                        _alter_sequence(self._cr, 'ir_sequence_%03d' % seq.id, number_increment=i)
                        seq.date_range_ids._alter_sequence(number_increment=i)
                else:
                    _drop_sequence(self._cr, ['ir_sequence_%03d' % seq.id])
                    for sub_seq in seq.date_range_ids:
                        _drop_sequence(self._cr, ['ir_sequence_%03d_%03d' % (seq.id, sub_seq.id)])
            else:
                if new_implementation in ('no_gap', None):
                    pass
                else:
                    _create_sequence(self._cr, 'ir_sequence_%03d' % seq.id, i, n)
                    for sub_seq in seq.date_range_ids:
                        _create_sequence(self._cr, 'ir_sequence_%03d' % (seq.id, sub_seq.id), i, n)
        return super(IrSequence, self).write(values)

    def _next_do(self):
        if self.implementation == 'standard':
            number_next = _select_nextval(self._cr, 'ir_sequence_%03d' % self.id)
        else:
            number_next = _update_nogap(self, self.number_increment)
        return self.get_next_char(number_next)

    def _get_prefix_suffix(self):
        def _interpolate(s, d):
            return (s % d) if s else ''

        def _interpolation_dict():
            now = range_date = effective_date = datetime.now(pytz.timezone(self._context.get('tz') or 'UTC'))
            if self._context.get('ir_sequence_date'):
                effective_date = fields.Datetime.from_string(self._context.get('ir_sequence_date'))
            if self._context.get('ir_sequence_date_range'):
                range_date = fields.Datetime.from_string(self._context.get('ir_sequence_date_range'))

            sequences = {
                'year': '%Y', 'month': '%m', 'day': '%d', 'y': '%y', 'doy': '%j', 'woy': '%W',
                'weekday': '%w', 'h24': '%H', 'h12': '%I', 'min': '%M', 'sec': '%S'
            }
            res = {}
            for key, format in sequences.items():
                res[key] = effective_date.strftime(format)
                res['range_' + key] = range_date.strftime(format)
                res['current_' + key] = now.strftime(format)
            return res

        d = _interpolation_dict()
        try:
            _interpolated_prefix = _interpolate(self.prefix, d)
            _interpolated_suffix = _interpolate(self.suffix, d)
        except ValueError:
            raise UserError(_('Invalid prefix or suffix for sequence \'%s\'') % (self.get('name')))
        return _interpolated_prefix, _interpolated_suffix

    def get_next_char(self, number_next):
        interpolated_prefix, interpolated_suffix = self._get_prefix_suffix()
        return interpolated_prefix + '%%0%sd' % self.padding % number_next + interpolated_suffix

    def _create_date_range_seq(self, date):
        year = fields.Date.from_string(date).strftime('%Y')
        date_from = '{}-01-01'.format(year)
        date_to = '{}-12-31'.format(year)
        date_range = self.env['ir.sequence.date_range'].search(
            [('sequence_id', '=', self.id), ('date_from', '>=', date),
             ('date_from', '<=', date_to)], order='date_from desc', limit=1)
        if date_range:
            date_to = date_range.date_from + datetime.timedelta(days=-1)
        date_range = self.env['ir.sequence.date_range'].search(
            [('sequence_id', '=', self.id), ('date_to', '>=', date_from),
             ('date_to', '<=', date)], order='date_to desc', limit=1)
        if date_range:
            date_from = date_range.date_to + datetime.timedelta(days=1)
        seq_date_range = self.env['ir.sequence.date_range'].sudo().create({
            'date_from': date_from,
            'date_to': date_to,
            'sequence_id': self.id
        })
        return seq_date_range

    def _next(self):
        if not self.use_date_range:
            return self._next_do()
        dt = fields.Date.today()
        if self._context.get('ir_sequence_date'):
            dt = self._context.get('ir_sequence_date')
        seq_date = self.env['ir.sequence.date_range'].search([('sequence_id', '=', self.id), ('date_from', '<=', dt),
                                                              ('date_to', '>=', dt)], limit=1)
        if not seq_date:
            seq_date = self._create_date_range_seq(dt)
        return seq_date.with_context(ir_sequence_date_range=seq_date.date_from)._next()

    @api.multi
    def next_by_id(self):
        self.check_access_rights('read')
        return self._next()

    @api.model
    def next_by_code(self, sequence_code):
        self.check_access_rights('read')
        force_company = self._context.get('force_company')
        if not force_company:
            force_company = self.env.user.company_id.id
        seq_ids = self.search([('code', '=', sequence_code), ('company_id', 'in', [force_company, False])],
                              order='company_id')
        if not seq_ids:
            return False
        seq_id = seq_ids[0]
        return seq_id._next()

    @api.model
    def get_id(self, sequence_code_or_id, code_or_id='id'):
        if code_or_id == 'id':
            return self.browse(sequence_code_or_id).next_by_id()
        else:
            return self.next_by_code(sequence_code_or_id)

    @api.model
    def get(self, code):
        return self.get_id(code, 'code')


class IrSequenceDateRange(models.Model):
    _name = 'ir.sequence.date_range'
    _description = 'Sequence Date Range'
    _rec_name = 'sequence_id'

    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    sequence_id = fields.Many2one('ir.sequence', string='Main Sequence', required=True, ondelete='cascade')
    number_next = fields.Integer(string='Next Number', required=True, default=1)
    number_next_actual = fields.Integer(compute='_get_number_next_actual', inverse='_set_number_next_actual',
                                        string='Actual Next Number')

    def _get_number_next_actual(self):
        for seq in self:
            if seq.sequence_id.implementation != 'standard':
                seq.number_next_actual = seq.number_next
            else:
                seq_id = "%03d_%03d" % (seq.sequence_id.id, seq.id)
                seq.number_next_actual = _predict_nextval(self, seq_id)

    def _set_number_next_actual(self):
        for seq in self:
            seq.write({'number_next': seq.number_next_actual or 1})

    @api.model
    def default_get(self, fields):
        result = super(IrSequenceDateRange, self).default_get(fields)
        result['number_next_actual'] = 1
        return result

    def _next(self):
        if self.sequence_id.implementation == 'standard':
            number_next = _select_nextval(self._cr, 'ir_sequence_%03d_%03d' % (self.sequence_id.id, self.id))
        else:
            number_next = _update_nogap(self, self.sequence_id.number_increment)
        return self.sequence_id.get_next_char(number_next)

    @api.multi
    def _alter_sequence(self, number_increment=None, number_next=None):
        for seq in self:
            _alter_sequence(self._cr, 'ir_sequence_%03d_%03d' % (seq.sequence_id, seq.id),
                            number_increment=number_increment, number_next=number_next)

    @api.model
    def create(self, values):
        seq = super(IrSequenceDateRange, self).create(values)
        main_seq = seq.sequence_id
        if main_seq.implementation == 'standard':
            _create_sequence(self._cr, 'ir_sequence_%03d_%03d' % (main_seq.id, seq.id), main_seq.number_increment,
                             values.get('number_next_actual', 1))
        return seq

    @api.multi
    def unlink(self):
        _drop_sequence(self._cr, ['ir_sequence_%03d_%03d' % (x.sequence_id.id, x.id) for x in self])
        return super(IrSequenceDateRange, self).unlink()

    @api.multi
    def write(self, values):
        if values.get('number_next'):
            seq_to_alter = self.filtered(lambda seq: seq.sequence_id.implementation == 'standard')
            seq_to_alter._alter_sequence(number_next=values.get('number_next'))
        return super(IrSequenceDateRange, self).write(values)
