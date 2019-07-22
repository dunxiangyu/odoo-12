from collections import defaultdict

from . import api


class MetaModel(api.Meta):
    module_to_models = defaultdict(list)

    def __init__(cls, name, bases, attrs):
        if not cls._register:
            cls._register = True
            super(MetaModel, cls).__init__(name, bases, attrs)
            return

        if not hasattr(cls, '_module'):
            cls._module = cls._get_addon_name(cls.__module__)

        if not cls._custom:
            cls.module_to_models[cls._module].append(cls)

        for key, val in attrs.items():
            continue

    def _get_addon_name(self, full_name):
        pass


class BaseModel(MetaModel('DummyModel', (object,), {'_register': False})):
    _auto = False
    _register = False
    _abstract = True
    _transient = False

    _name = None
    _description = None
    _custom = False

    _inherit = None
    _inherits = {}
    _constraints = []

    _table = None
    _sequence = None
    _sql_constraints = []

    _rec_name = None
    _order = 'id'
    _parent_name = 'parent_id'
    _parent_store = False
    _date_name = 'date'
    _fold_name = 'fold'

    _needaction = False
    _transient = True

    _depends = {}

    def _prepare_setup(self):
        cls = type(self)
        cls._setup_done = False
        cls._model_cache_key = tuple(c for c in cls.mro() if getattr(c, 'pool', None) is None)

    def _setup_base(self):
        cls = type(self)
        if cls._setup_done:
            return

        cls0 = cls.pool.model_cache.get(cls._model_cache_key)
        if cls0 and cls0._model_cache_key == cls._model_cache_key:
            print("")
        else:
            for name in cls._fields:
                delattr(cls, name)
        cls.pool.model_cache[cls._model_cache_key] = cls

        # 2. add manual fields

        cls._setup_done = True

    def _setup_fields(self):
        cls = type(self)

        bad_fields = []
        for name, field in cls._fields.items():
            pass

        for name in bad_fields:
            del cls._fields[name]
            delattr(cls, name)

    def _setup_complete(self):
        cls = type(self)

        if isinstance(self, Model):
            for field in cls._fields.values():
                pass

        if cls._rec_name:
            assert cls._rec_name in cls._fields
        elif 'name' in cls._fields:
            cls._rec_name = 'name'
        elif 'x_name' in cls._fields:
            cls._rec_name = 'x_name'

    @classmethod
    def _build_model(cls, pool, cr):
        cls._local_constraints = cls.__dict__.get('_constraints', [])
        cls._local_sql_constraints = cls.__dict__.get('_sql_constraints', [])

    @classmethod
    def _build_model_attributes(cls, pool):
        cls._description = cls._name
        cls._table = cls._name.replace('.', '_')
        cls._sequence = None

        for base in reversed(cls.__bases__):
            continue


AbstractModel = BaseModel


class Model(AbstractModel):
    _auto = True
    _register = False
    _abstract = False
    _transient = False


class TransientModel(Model):
    _auto = True
    _register = False
    _abstract = False
    _transient = True
