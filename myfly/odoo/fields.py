import logging
from datetime import date, datetime, time

_logger = logging.getLogger(__name__)

Default = object()


class MetaField(type):
    by_type = {}

    def __new__(cls, name, bases, attrs):
        # _logger.info('MetaField new: %s', cls)
        base_slots = {}
        for base in reversed(bases):
            base_slots.update(getattr(base, '_slots', ()))
        slots = dict(base_slots)
        slots.update(attrs.get('_slots', ()))

        attrs['__slots__'] = set(slots) - set(base_slots)
        attrs['_slots'] = slots
        return type.__new__(cls, name, bases, attrs)

    def __init__(cls, name, bases, attrs):
        # _logger.info('MetaField init: ')
        super(MetaField, cls).__init__(name, bases, attrs)
        if not hasattr(cls, 'type'):
            return

        if cls.type and cls.type not in MetaField.by_type:
            MetaField.by_type[cls.type] = cls


class Field(MetaField('DummyField', (object,), {})):
    type = None
    relational = False
    translate = False

    column_type = None
    column_format = '%s'

    _slots = {
        'args': dict(),
        '_attrs': dict(),
        '_setup_done': None,

        'name': None,
        'model_name': None,
        'inhertied': False,
        'inhertied_field': None,

        'compute': None,

        'store': True,
        'copy': True,
        'readonly': False,
        'index': False,
        'default': None,
        'context_dependent': None,

        'string': None,
        'help': None
    }

    def __init__(self, string=Default, **kwargs):
        # _logger.info('Field init: ')
        kwargs['string'] = string
        args = {key: val for key, val in kwargs.items() if val is not Default}
        self.args = args or dict()
        self._setup_done = None

    def __getattr__(self, name):
        try:
            return self._attrs[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        try:
            object.__setattr__(self, name, value)
        except AttributeError:
            if self._attrs:
                self._attrs[name] = value
            else:
                self._attrs = {name: value}

    def set_all_attrs(self, attrs):
        assign = object.__setattr__
        for key, val in self._slots.items():
            assign(self, key, attrs.pop(key, val))
        if attrs:
            assign(self, '_attrs', attrs)

    def _get_attrs(self, model, name):
        modules = set()
        attrs = {}
        if not (self.args.get('automatic') or self.args.get('manual')):
            pass
        attrs.update(self.args)

        attrs['args'] = self.args
        attrs['name'] = name
        attrs['_modules'] = modules

        if attrs.get('compute'):
            attrs['store'] = attrs.get('store', False)
            attrs['copy'] = attrs.get('copy', False)
            attrs['readonly'] = attrs.get('readonly', False)
            attrs['context_dependent'] = attrs.get('context_dependent', True)

        return attrs

    def _setup_attrs(self, model, name):
        attrs = self._get_attrs(model, name)
        self.set_all_attrs(attrs)

        # self.default must be a callable
        if self.default is not None:
            value = self.default
            self.default = value if callable(value) else lambda model: value

    def setup_base(self):
        if self._setup_done:
            self._setup_done = 'base'
        else:
            self._setup_attrs(None, None)
            self._setup_done = 'base'


class Boolean(Field):
    type = 'boolean'


class Integer(Field):
    type = 'integer'
    _slots = {
        'group_operator': 'sum'
    }


class Float(Field):
    type = 'float'
    _slots = {
        '_digits': None,
        'group_operator': 'sum',
    }

    def __init__(self, string=Default, digits=Default, **kwargs):
        super(Float, self).__init__(string=string, _digits=digits, **kwargs)


class Monetary(Field):
    type = 'monetary'
    _slots = {
        'currency_field': None,
        'gruop_operator': 'sum',
    }

    def __init__(self, string=Default, currency_field=Default, **kwargs):
        super(Monetary, self).__init__(string=string, currency_field=currency_field, **kwargs)


class _String(Field):
    _slots = {
        'translate': False,
    }

    def __init__(self, string=Default, **kwargs):
        if 'translate' in kwargs and not callable(kwargs['translate']):
            kwargs['translate'] = bool(kwargs['translate'])
        super(_String, self).__init__(string, **kwargs)


class Char(_String):
    type = 'char'
    _slots = {
        'size': None,
        'trim': True,
    }


class Text(_String):
    type = 'text'


class Html(_String):
    type = 'html'
    _slots = {
        'sanitize': True,
        'sanitize_tags': True,
    }


class Date(Field):
    type = 'date'

    @staticmethod
    def today():
        return date.today()

    @staticmethod
    def to_date(value):
        pass

    @classmethod
    def to_string(value):
        pass


class Datetime(Field):
    type = 'datetime'

    @staticmethod
    def now():
        return datetime.now().replace(microsecond=0)

    @staticmethod
    def today():
        return Datetime.now().replace(hour=0, minute=0, second=0)

    @staticmethod
    def to_datetime(value):
        pass

    @staticmethod
    def to_string(value):
        pass


class Binary(Field):
    type = 'binary'
    _slots = {
        'prefetch': False,
        'context_dependent': True,
        'attachment': False,
    }


class Selection(Field):
    type = 'selection'
    _slots = {
        'selection': None,
        'validate': True,
    }

    def __init__(self, string=Default, selection=Default, **kwargs):
        super(Selection, self).__init__(string=string, selection=selection, **kwargs)


class Reference(Selection):
    type = 'reference'


class _Relational(Field):
    relational = True
    _slots = {
        'domain': [],
        'context': {}
    }


class Many2one(_Relational):
    type = 'many2one'
    _slots = {
        'ondelete': 'set null',
        'auto_join': False,
        'delegate': False,
    }


class _RelationalMulti(_Relational):
    _slots = {
        'context_dependent': True
    }


class One2Many(_RelationalMulti):
    type = 'one2many'
    _slots = {
        'inverse_name': None,
        'auto_join': False,
        'limit': None,
        'copy': False
    }


class Many2Many(_RelationalMulti):
    type = 'many2many'
    _slots = {
        'relation': None,
        'column1': None,
        'column2': None,
        'auto_join': False,
        'limit': None,
    }


class Id(Field):
    type = 'integer'
    _slots = {
        'string': 'ID',
        'store': True,
        'readonly': True,
        'prefetch': False,
    }
