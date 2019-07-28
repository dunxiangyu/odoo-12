from odoo import models, sql_db


class ExtModel(models.AbstractModel):
    _auto = False  # automatically create database backend
    _register = False  # not visible in ORM registry, meant to be python-inherited only
    _abstract = True  # not abstract
    _transient = False  # not transient

    _ext_system = None

    _is_ext = False

    _ext_cr = None

    def _get_cursor(self):
        if self._is_ext:
            if not self._ext_cr:
                conn = sql_db.db_connect('ext_' + self._ext_system)
                self._ext_cr = conn.cursor()
            return self._ext_cr
        else:
            return super(ExtModel, self)._get_cursor()

    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        self._is_ext = True
        result = super(ExtModel, self)._search(args, offset, limit, order, count, access_rights_uid)
        self._is_ext = False
        return result
