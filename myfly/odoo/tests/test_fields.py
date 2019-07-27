import logging
import unittest
from ..fields import *

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)


class TestFields(unittest.TestCase):
    def test_MetaField_types(self):
        _logger.info(MetaField.by_type)
        self.assertIn('boolean', MetaField.by_type)
        self.assertIn('integer', MetaField.by_type)

    def test_boolean(self):
        bf = Boolean(string='name')
        self.assertEqual('boolean', bf.type)
        bf.setup_base()
        self.assertEqual('name', bf.string)
        assert dir(bf)

    def test_integer(self):
        if1 = Integer(string='age')
        self.assertEqual('integer', if1.type)
        if1.setup_base()
        self.assertEqual('age', if1.string)
        self.assertTrue(hasattr(if1, 'group_operator'))
        self.assertEqual('sum', if1.group_operator)

    def test_integer_compute(self):
        def compute():
            pass

        if2 = Integer(string='cost', compute=compute)
        if2.setup_base()
        self.assertTrue(hasattr(if2, 'copy'))

    def test_float(self):
        ff = Float(string='weight', digits=3)
        ff.setup_base()
        self.assertEqual(3, ff._digits)
        dir(ff)

    def test_monetary(self):
        field = Monetary(string='currency')
        field.setup_base()

    def test_char(self):
        field = Char(string='sex')
        field.setup_base()

    def test_text(self):
        field = Text(string='memo')
        field.setup_base()

    def test_html(self):
        field = Html(string='site')
        field.setup_base()

    def test_date(self):
        field = Date(string='birthday')
        field.setup_base()

    def test_datetime(self):
        field = Datetime(string='create_date')
        field.setup_base()

    def test_binary(self):
        field = Binary(string='file')
        field.setup_base()

    def test_selection(self):
        field = Selection(string='fenlei')
        field.setup_base()

    def test_reference(self):
        field = Reference(string='ref')
        field.setup_base()

    def test_many2one(self):
        field = Many2one(string='user_id')
        field.setup_base()

    def test_one2many(self):
        field = One2Many(string="users")
        field.setup_base()

    def test_many2many(self):
        field = Many2Many(string="rels")
        field.setup_base()

    def test_id(self):
        field = Id()
        field.setup_base()
