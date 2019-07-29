from odoo import models, sql_db


class ExtModel(models.AbstractModel):
    _auto = False  # automatically create database backend
    _register = False  # not visible in ORM registry, meant to be python-inherited only
    _abstract = True  # not abstract
    _transient = False  # not transient
