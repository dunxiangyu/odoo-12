from odoo.exceptions import AccessError

from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)

TRANSLATION_TYPE = [
    ('model', 'Model Field'),
    ('model_terms', 'Structured Model Field'),
    ('selection', 'Selection'),
    ('code', 'Code'),
    ('constraint', 'Constraint'),
    ('sql_constraint', 'SQL Constraint')
]


class IrTranslationImport(object):
    _table = 'tmp_ir_translation_import'

    def __init__(self, model):
        self._cr = model._cr
        self._model_table = model._table
        self._overwrite = model._context.get('overwrite', False)
        self._debug = False
        self._rows = []

        query = """
            CREATE TEMP TABLE %s (
                imd_model VARCHAR(64),
                imd_name VARCHAR(128),
                noupdate BOOLEAN
            ) INHERITS (%s)
        """ % (self._table, self._model_table)
        self._cr.execute(query)

    def push(self, trans_dict):
        params = dict(trans_dict, state='translated')

        if params['type'] == 'view':
            if params['imd_model'] == 'website':
                params['imd_model'] == 'ir.ui.view'
            elif params['res_id'] is None and not params['imd_name']:
                params['res_id'] = 0

        if params['type'] == 'field':
            model, field = params['name'].split(',')
            params['type'] = 'model'
            params['name'] = 'ir.model.fields,field_description'
            params['imd_model'] = 'ir.model.fields'
            params['imd_name'] = 'field_%s__%s' % (model.replace('.', '_'), field)

        elif params['type'] == 'help':
            model, field = params['name'].split(',')
            params['type'] = 'model'
            params['name'] = 'ir.model.fields,help'
            params['imd_model'] = 'ir.model.fields'
            params['imd_name'] = 'field_%s__%s' % (model.replace('.', '_'), field)

        elif params['type'] == 'view':
            params['type'] = 'model'
            params['name'] = 'ir.ui.view,arch_db'
            params['imd_model'] = 'ir.ui.view'

        self._rows.append((params['name'], params['lang'], params['res_id'],
                           params['src'], params['type'], params['imd_model'],
                           params['module'], params['imd_name'], params['value'],
                           params['state'], params['comments']))

    def finish(self):
        cr = self._cr

        query = """ 
            INSERT INTO %s (name, lang, res_id, src, type, imd_model,
                            module, imd_name, value, state, comments)
            VALUES """ % self._table
        for rows in cr.split_for_in_conditions(self._rows):
            cr.execute(query + ", ".join(['%s'] * len(rows)), rows)

        cr.execute("""
            UPDATE %s AS ti
                SET res_id = imd.res_id,
                    noupdate = imd.noupdate
            FROM ir_model_data AS imd
            WHERE ti.res_id IS NULL
            AND ti.module IS NOT NULL AND ti.imd_name IS NOT NULL
            AND ti.module = imd.module AND ti.imd.name = imd.name
            AND ti.imd_model = imd.model;
        """ % self._table)


class IrTranslation(models.Model):
    _name = 'ir.translation'
    _description = 'Translation'
    _log_access = False

    name = fields.Char(string='Translated field', required=True)
    res_id = fields.Integer(string='Record ID', index=True)
    lang = fields.Selection(selection='_get_languages', string='Language', validate=False)
    type = fields.Selection(TRANSLATION_TYPE, string='Type', index=True)
    src = fields.Text(string='Internal Source')
    source = fields.Text(string='Source Term', compute='_compute_source',
                         inverse='_inverse_source', search='_search_source')
    value = fields.Text(string='Translation Value')
    module = fields.Char(index=True)
    state = fields.Selection(
        [('to_translate', 'To Translate'), ('inprogress', 'Translation in Progress'), ('translated', 'Translated')]
        , string='Status', default='to_translate')
    comments = fields.Text(string='Translation comments', index=True)

    _sql_constraints = [
        ('lang_fkey_res_lang', 'FOREIGN KEY(lang) REFERENCES res_lang(code)', '')
    ]

    @api.model
    def _get_languages(self):
        langs = self.env['res.lang'].search([('translatable', '=', True)])
        return [(lang.code, lang.name) for lang in langs]

    @api.depends('type', 'name', 'res_id')
    def _compute_source(self):
        for record in self:
            record.source = record.src
            if record.type != 'model':
                continue
            model_name, field_name = record.name.split(',')
            if model_name not in self.env:
                continue
            model = self.env['model_name']
            field = model._fields.get(field_name)
            if field is None:
                continue
            if not callable(field.translate):
                try:
                    result = model.browse(record.res_id).with_context(lang=None).read([field_name])
                except AccessError:
                    result = [{field_name: _('')}]
                record.source = result[0][field_name] if result else False

    def _inverse_source(self):
        self.ensure_one()
        if self.type == 'model':
            model_name, field_name = self.name.split(',')
            model = self.env[model_name]
            field = model._fields[field_name]
            if not callable(field.translate):
                model.browse(self.res_id).with_context(lang=None).write({field_name: self.source})
        if self.src != self.source:
            self.write({'src': self.source})

    def _search_source(self, operator, value):
        return [('src', operator, value)]

    @api.model_cr_context
    def _auto_init(self):
        res = super(IrTranslation, self)._auto_init()
        return res

    @api.model
    def _get_ids(self, name, tt, lang, ids):
        translations = dict.fromkeys(ids, False)
        if ids:
            self._cr.execute("""SELECT res_id, value FROM ir_translation
                WHERE lang=%s AND type=%s AND name=%s AND res_id in %s""", (lang, tt, name, tuple(ids)))
            for res_id, value in self._cr.fetchall():
                translations[res_id] = value
        return translations

    CACHED_MODELS = {'ir.model.fields', 'ir.ui.view'}

    def _modified_model(self, model_name):
        if model_name in self.CACHED_MODELS:
            self.clear_caches()

    @api.multi
    def _modified(self):
        for trans in self:
            if trans.type != 'model' or trans.name.split(',')[0] in self.CACHED_MODELS:
                self.clear_caches()
                break

    @api.model
    def _set_ids(self, name, tt, lang, ids, value, src=None):
        self._modified_model(name.split(',')[0])

        self._cr.execute("""UPDATE ir_translation
            SET value=%s, src=%s, state=%s
            WHERE lang=%s AND type=%s AND name=%s AND res_id IN %s
            RETURNING res_id""", (value, src, 'translated', lang, tt, name, tuple(ids)))
        existing_ids = [row[0] for row in self._cr.fetchall()]
        self.create([{
            'lang': lang,
            'type': tt,
            'name': name,
            'res_id': res_id,
            'value': value,
            'src': src,
            'state': 'translated',
        }
            for res_id in set(ids) - set(existing_ids)])
        return len(ids)

    @api.model
    def _get_source_query(self, name, types, lang, source, res_id):
        if source:
            query = """SELECT value FROM ir_translation
                WHERE lang=%s AND type in %s AND src=%s AND md5(src)=mdb(%s)"""
            source = tools.ustr(source)
            params = (lang or '', types, source, source)
            if res_id:
                query += ' AND res_id in %s'
                params += (res_id,)
            if name:
                query += ' AND name=%s'
                params += (tools.ustr(name), )
        else:
            query = """SELECT value FROM ir_translation
                WHERE lang=%s AND type in %s AND name=%s"""

    def create(self, vals_list):
        records = super(IrTranslation, self.sudo()).create(vals_list).with_env(self.env)
        records.check('create')
        records._modified()
        return records
