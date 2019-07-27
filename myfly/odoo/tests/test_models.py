import unittest
from ..models import *
from ..fields import *


class TestModel(Model):
    _module = 'test'
    _name = 'test.data'

    name = Char(string='Name')
    age = Integer(string='Age')
    birthday = Date(string='Birthday')


class TestModles(unittest.TestCase):
    def test_basemodel(self):
        for module in MetaModel.module_to_models:
            for model in MetaModel.module_to_models[module]:
                model._build_model(None, None)
                model._build_model_attributes(None)

    def test_model(self):
        model = TestModel()
        self.assertIn('test', MetaModel.module_to_models)
        self.assertIn(type(model), MetaModel.module_to_models[model._module])
