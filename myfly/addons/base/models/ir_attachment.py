import io
import itertools
import uuid

from PyPDF2 import PdfFileReader, PdfFileWriter

from odoo import api, fields, models, _, tools, SUPERUSER_ID
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import config, human_size, image_resize_image, crop_image
import logging
import os
import re
import base64
import hashlib
import mimetypes
from odoo.tools.mimetypes import guess_mimetype
from collections import defaultdict

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _name = 'ir.attachment'
    _description = 'Attachment'
    _order = 'id desc'

    name = fields.Char('Name', required=True)
    datas_fname = fields.Char('Filename')
    description = fields.Char('Description')
    res_name = fields.Char('Resource Name', compute='_compute_res_name, store=True')
    res_model = fields.Char('Resource Model', readonly=True,
                            help='The database object this attachment will be attached to.')
    res_model_name = fields.Char(compute='_compute_res_model_name', store=True, index=True)
    res_field = fields.Char('Resource Field', readonly=True)
    res_id = fields.Integer('Resource ID', readonly=True, help='The record id this is attached to.')
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
                                 default=lambda self: self.env['res.company']._company_default_get('ir.attachment'))
    type = fields.Selection([('url', 'URL'), ('binary', 'File')], string='Type', required=True, default='binary',
                            change_default=True,
                            help='You can either upload a file from your computer or copy/paste an internet link to your file.')
    url = fields.Char('Url', index=True, size=1024)
    public = fields.Boolean('Is public document')

    # for external access
    access_token = fields.Char('Access Token', groups='base.group_user')

    datas = fields.Binary(string='File Content', compute='_compute_datas', inverse='_inverse_datas')
    db_datas = fields.Binary('Database Data')
    store_fname = fields.Char('Stored Filename')
    file_size = fields.Integer('File Size', readonly=True)
    checksum = fields.Char('Checksum/SHA1', size=40, index=True, readonly=True)
    mimetype = fields.Char('Mime Type', readonly=True)
    index_context = fields.Char('Indexed Content', readonly=True, prefetch=False)
    active = fields.Boolean(default=True, string='Active', oldname='archived')
    thumbnail = fields.Binary(readonly=1, attachment=True)

    @api.depends('res_model', 'res_id')
    def _compute_res_name(self):
        for attachment in self:
            if attachment.res_model and attachment.res_id:
                record = self.env[attachment.res_model].broswe(attachment.res_id)
                attachment.res_name = record.dispaly_name

    @api.depends('res_model')
    def _compute_res_model_name(self):
        for record in self:
            if record.res_model:
                model = self.env['ir.model'].search([('model', '=', record.res_model)], limit=1)
                if model:
                    record.res_model_name = model[0].name

    @api.model
    def _storage(self):
        return self.env['ir.config_parameter'].sudo().get_param('ir_attachment.location', 'file')

    @api.model
    def _filestore(self):
        return config.filestore(self._cr.dbname)

    @api.model
    def force_storage(self):
        """Force all attachments to be stored in the currency configured storage"""
        if not self.env.user._is_admin():
            raise AccessError(_('Only administrator can execute this action.'))

        domain = {
            'db': [('store_fname', '!=', False)],
            'file': [('db_datas', '!=', False)]
        }[self._storage()]

        for attach in self.search(domain):
            attach.write({'datas': attach.datas})
        return True

    @api.model
    def _full_path(self, path):
        path = re.sub('[.]', '', path)
        path = path.strip('/\\')
        return os.path.join(self._filestore(), path)

    @api.model
    def _get_path(self, bin_data, sha):
        fname = sha[:3] + '/' + sha
        full_path = self._full_path(fname)
        if os.path.isfile(full_path):
            return fname, full_path

        fname = sha[:2] + '/' + sha
        full_path = self._full_path(fname)
        dirname = os.path.dirname(full_path)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        return fname, full_path

    @api.model
    def _file_read(self, fname, bin_size=False):
        full_path = self._full_path(fname)
        r = ''
        try:
            if bin_size:
                r = human_size(os.path.getsize(full_path))
            else:
                r = base64.b64encode(open(full_path, 'rb').read())
        except (IOError, OSError):
            _logger.info('_read_file reading %s', full_path, exc_info=True)
        return r

    @api.model
    def _file_write(self, value, checksum):
        bin_value = base64.b64decode(value)
        fname, full_path = self._get_path(bin_value, checksum)
        if not os.path.exists(full_path):
            try:
                with open(full_path, 'wb') as fp:
                    fp.write(bin_value)
                self._mark_for_gc(fname)
            except IOError:
                _logger.info('_file_write writing %s', full_path, exc_info=True)
        return fname

    @api.model
    def _file_delete(self, fname):
        self._mark_for_gc(fname)

    def mark_for_gc(self, fname):
        full_path = os.path.join(self._full_path('checklist'), fname)
        if not os.path.exists(full_path):
            dirname = os.path.dirname(full_path)
            if not os.path.isdir(dirname):
                with tools.ignore(OSError):
                    os.makedirs(dirname)
            open(full_path, 'ab').close()

    @api.model
    def _file_gc(self):
        """Perform the garbage collection of the filestore."""
        if self._storage() != 'file':
            return
        cr = self._cr
        cr.commit()
        cr.execute('LOCK ir_attachment IN SHARE MODE')
        checklist = {}
        for dirpath, _, filenames in os.walk(self._full_path('checklist')):
            dirname = os.path.basename(dirpath)
            for filename in filenames:
                fname = '%s/%s' % (dirname, filename)
                checklist[fname] = os.path.join(dirpath, filename)

        whitelist = set()
        for names in cr.split_for_in_conditions(checklist):
            cr.execute('SELECT store_fname FROM ir_attachment WHERE store_fname IN %s', [names])
            whitelist.update(row[0] for row in cr.fetchall())

        removed = 0
        for fname, filepath in checklist.items():
            if fname not in whitelist:
                try:
                    os.unlink(self._full_path(fname))
                    removed += 1
                except (OSError, IOError):
                    _logger.info('_file_gc could not unlink %s', self._full_path(fname), exc_info=True)
            with tools.ignore(OSError):
                os.unlink(filepath)

        cr.commit()
        _logger.info('filestore gc %d checked, %d removed', len(checklist), removed)

    @api.depends('store_fname', 'db_datas')
    def _compute_datas(self):
        bin_size = self._context.get('bin_size')
        for attach in self:
            if attach.store_fname:
                attach.datas = self._file_read(attach.store_fname, bin_size)
            else:
                attach.datas = attach.db_datas

    def _inverse_datas(self):
        location = self._storage()
        for attach in self:
            # compute the fields that depend on datas
            value = attach.datas
            bin_data = base64.b64decode(value) if value else b''
            vals = {
                'file_size': len(bin_data),
                'checksum': self._compute_checksum(bin_data),
                'index_context': self._index(bin_data, attach.datas_fname, attach.mimetype),
                'store_fname': False,
                'db_datas': value,
            }
            if value and location != 'db':
                # save it to the filestore
                vals['store_fname'] = self._file_write(value, vals['checksum'])
                vals['db_datas'] = False
            # take current location in filestore to poosibly garbage-collect it
            fname = attach.store_fname
            super(IrAttachment, attach.sudo()).write(vals)
            if fname:
                self._file_delete(fname)

    def _compute_checksum(self, bin_data):
        # an empty file has a checksum too (for caching)
        return hashlib.sha1(bin_data or b'').hexdigest()

    def _compute_mimetype(self, values):
        mimetype = None
        if values.get('mimetype'):
            mimetype = values['mimetype']
        if not mimetype and values.get('datas_fname'):
            mimetype = mimetypes.guess_type(values['datas_fname'])[0]
        if not mimetype and values.get('url'):
            mimetype = mimetypes.guess_type(values['url'])[0]
        if values.get('datas') and (not mimetype or mimetype == 'application/octet-stream'):
            mimetype = guess_mimetype(base64.b64decode(values['datas']))
        return mimetype or 'application/octet-stream'

    def _check_contents(self, values):
        mimetype = values['mimetype'] = self._compute_mimetype(values)
        xml_like = 'ht' in mimetype or 'xml' in mimetype
        user = self.env.context.get('binary_field_real_user', self.env.user)
        force_text = (xml_like and (not user._is_system() or
                                    self.env.context.get('attachments_mime_plainxml')))
        if force_text:
            values['mimetype'] = 'text/plain'
        return values

    @api.model
    def _index(self, bin_data, datas_fname, file_type):
        index_content = False
        if file_type:
            index_content = file_type.split('/')[0]
            if index_content == 'text':
                words = re.findall(b"[\x20-\x7E]{4,}", bin_data)
                index_content = b"\n".join(words).decode('ascii')
        return index_content

    @api.model
    def get_serving_groups(self):
        return ['base.group_system']

    @api.model_cr_context
    def _auto_init(self):
        res = super(IrAttachment, self)._auto_init()
        tools.create_index(self._cr, 'ir_attachment_res_idx', self._table, ['res_model', 'res_id'])
        return res

    @api.one
    @api.constrains('type', 'url')
    def _check_serving_attachments(self):
        if self.env.user._is_admin():
            return
        if self.type == 'binary' and self.url:
            has_group = self.env.user.has_group
            if not any([has_group(g) for g in self.get_serving_groups()]):
                raise ValidationError('Sorry, you are not allowed to write on this document')

    @api.model
    def check(self, mode, values=None):
        model_ids = defaultdict(set)
        require_employee = False
        if self:
            self._cr.execute('SELECT res_model, res_id, create_uid, public FROM ir_attachment WHERE id IN %s',
                             [tuple(self.ids)])
            for res_model, res_id, create_uid, public in self._cr.fetchall():
                if public and mode == 'read':
                    continue
                if not (res_model and res_id):
                    if create_uid != self._uid:
                        require_employee = True
                    continue
                model_ids[res_model].add(res_id)
        if values and values.get('res_model') and values.get('res_id'):
            model_ids[values['res_model']].add(values['res_id'])

        for res_model, res_ids in model_ids.items():
            if res_model not in self.env:
                require_employee = True
                continue
            elif res_model == 'res.users' and len(res_ids) == 1 and self._uid == list(res_ids)[0]:
                continue
            records = self.env[res_model].browse(res_ids).exists()
            if len(records) < len(res_ids):
                require_employee = True
            records.check_access_rights('write' if mode in ('create', 'unlink') else mode)
            records.check_access_rule(mode)

        if require_employee:
            if not (self.env.user._is_admin() or self.env.user.has_group('base.group_user')):
                raise AccessError(_('Sorry, you are not allowed to access this document.'))

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if not any(item[0] in ('id', 'res_field') for item in domain):
            domain.insert(0, ('res_field', '=', False))
        return super(IrAttachment, self).read_group(domain, fields, groupby, offset, limit, orderby, lazy)

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if not any(arg[0] in ('id', 'res_field') for arg in args):
            args.insert(0, ('res_field', '=', False))

        ids = super(IrAttachment, self)._search(args, offset, limit, order, count, access_rights_uid)

        if self._uid == SUPERUSER_ID:
            return len(ids) if count else ids

        orig_ids = ids
        ids = set(ids)

        model_attachments = defaultdict(lambda: defaultdict(set))
        self._cr.execute("""SELECT id, res_model, res_id, public FROM ir_attachment WHERE id IN %s""", [tuple(ids)])
        for row in self._cr.dictfetchall():
            if not row['res_model'] or row['public']:
                continue
            model_attachments[row['res_model']][row['res_id']].add(row['id'])

        for res_model, targets in model_attachments.items():
            if res_model not in self.env:
                continue
            if not self.env[res_model].check_access_rights('read', False):
                ids.difference_update(itertools.chain(*targets.values()))
                continue
            target_ids = list(targets)
            allowed = self.env[res_model].with_context(active_test=False).search([('id', 'in', target_ids)])
            for res_id in set(target_ids).difference(allowed.ids):
                ids.difference_update(targets[res_id])

        result = [id for id in orig_ids if id in ids]

        if len(orig_ids) == limit and len(result) < len(orig_ids):
            result.extend(self._search(args, offset + len(orig_ids), limit, order, count, access_rights_uid)[
                          :limit - len(result)])

        return len(result) if count else list(result)

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        self.check('read')
        return super(IrAttachment, self).read(fields, load=load)

    def _make_thumbnail(self, vals):
        if vals.get('datas') and not vals.get('res_field'):
            vals['thumbnail'] = False
            if vals.get('mimetype') and re.match('image.*(git|jepg|jpg|png)', vals['mimetype']):
                try:
                    temp_image = crop_image(vals['datas'], type='center', size=(80, 80), ratio=(1, 1))
                    vals['thumbnail'] = image_resize_image(base64_source=temp_image, size=(80, 80), encoding='base64')
                except Exception:
                    pass
        return vals

    @api.multi
    def write(self, vals):
        self.check('write', values=vals)
        for field in ('file_size', 'check_sum'):
            vals.pop(field, False)
        if 'mimetype' in vals or 'datas' in vals:
            vals = self._check_contents(vals)
            if all([not attachment.res_field for attachment in self]):
                vals = self._make_thumbnail(vals)
        return super(IrAttachment, self).write(vals)

    @api.multi
    def copy(self, default=None):
        self.check('write')
        return super(IrAttachment, self).copy(default)

    @api.multi
    def unlink(self):
        if not self:
            return True
        self.check('unlink')
        to_delete = set(attach.store_fname for attach in self in attach.store_fname)
        res = super(IrAttachment, self).unlink()
        for file_path in to_delete:
            self._file_delete(file_path)

        return res

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            for field in ('file_size', 'checksum'):
                values.pop(field, False)
            values = self._check_contents(values)
            values = self._make_thumbnail(values)
            self.browse().check('write', values=values)
        return super(IrAttachment, self).create(vals_list)

    @api.multi
    def _post_and_create(self):
        pass

    @api.one
    def generate_access_token(self):
        if self.access_token:
            return self.access_token
        access_token = str(uuid.uuid4())
        self.write({'access_token', access_token})
        return access_token

    @api.one
    def action_get(self):
        return self.env['ir.actions.act_windw'].for_xml_id('base', 'action_attachment')

    def _make_pdf(self, output, name_ext):
        self.ensure_one()
        try:
            stream = io.BytesIO()
            output.stream(stream)
            return self.copy({
                'name': self.name + '-' + name_ext,
                'datas_fname': os.path.splittext(self.data_fname or self.name)[0] + '-' + name_ext + '.pdf',
                'datas': base64.b64encode(stream.getvalue()),
            })
        except Exception:
            raise Exception

    def _split_pdf_groups(self, pdf_groups=None, remainder=False):
        self.ensure_one()
        with io.BytesIO(base64.b64decode(self.datas)) as stream:
            try:
                input_pdf = PdfFileReader(stream)
            except Exception:
                raise ValidationError(_('Error: Invalid PDF file.'))
            max_page = input_pdf.getNumPages()
            remainder_set = set(range(0, max_page))
            new_pdf_ids = []
            if not pdf_groups:
                pdf_groups = []
            for pages in pdf_groups:
                pages[1] = min(max_page, pages[1])
                pages[0] = min(max_page, pages[0])
                if pages[0] == pages[1]:
                    name_ext = '%s' % (pages[0])
                else:
                    name_ext = '%s-%s' % (pages[0], pages[1])
                output = PdfFileWriter()
                for i in range(pages[0] - 1, pages[1]):
                    output.addPage(input_pdf.getPage(i))
                new_pdf_id = self._make_pdf(output, name_ext)
                new_pdf_ids.append(new_pdf_id)
                remainder_set = remainder_set.difference(set(range(pages[0] - 1, pages[1])))
            if remainder:
                for i in remainder_set:
                    output_page = PdfFileWriter()
                    name_ext = '%s' % (i + 1,)
                    output_page.addPage(input_pdf.getPage(i))
                    new_pdf_id = self._make_pdf(output_page, name_ext)
                    new_pdf_ids.append(new_pdf_id)
                self.write({'active': False})
            elif not len(remainder_set):
                self.write({'active': False})
            return new_pdf_ids

    def split_pdf(self, indices=None, remainder=False):
        self.ensure_one()
        if 'pdf' not in self.mimetype:
            raise ValidationError(_('ERROR: the file must be a PDF.'))
        if indices:
            try:
                pages = [[int(x) for x in x.split('-')] for x in indices.split(',')]
            except ValueError:
                raise ValidationError(_('ERROR: invalid list of page to split. Example: 1,5-9,10'))
            return self._split_pdf_groups([[min(x), max(x)] for x in pages], remainder=remainder)
        return self._split_pdf_groups(remainder=remainder)

    @api.model
    def get_serve_attachment(self, url, extra_domain=None, extra_fields=None, order=None):
        domain = [('type', '=', 'binary'), ('url', '=', url)] + (extra_domain or [])
        fieldNames = ['_last_update', 'datas', 'mimetype'] + (extra_fields or [])
        return self.search_read(domain, fieldNames, order=order, limit=1)

    @api.model
    def get_attachment_by_key(self, key, extra_domain=None, order=None):
        domain = [('key', '=', key)] + (extra_domain or [])
        return self.search(domain, order=order, limit=1)
