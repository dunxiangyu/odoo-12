import threading
from collections import Mapping


class Registry(Mapping):
    registries = {}
    _lock = threading.RLock()
    _saved_lock = None

    def __new__(cls, db_name):
        with cls._lock:
            try:
                return cls.registries[db_name]
            except KeyError:
                return cls.new(db_name)
            finally:
                threading.current_thread().db_name = db_name

    @classmethod
    def new(cls, db_name, force_demo=False, status=None, update_module=False):
        with cls._lock:
            registry = object.__new__(cls)
            registry.init(db_name)
            cls.registries[db_name] = registry
            registry = cls.registries[db_name]
            registry._init = False
            registry.ready = True
        return registry

    def init(self, db_name):
        self.models = {}
        self._sql_error = {}
        self._init = True

        self.db_name = db_name

        self.loaded = False
        self.ready = False

    @classmethod
    def delete(cls, db_name):
        pass

    @classmethod
    def delete_all(cls):
        pass

    def __iter__(self):
        return iter(self.models)

    def __len__(self):
        return len(self.models)

    def __getitem__(self, model_name):
        return self.models[model_name]

    def __setitem__(self, model_name, model):
        self.models[model_name] = model

    def __call__(self, model_name):
        return self.models[model_name]

    def load(self, cr, module):
        pass

    def setup_models(self, cr):
        pass
