import unittest
import threading
import time
import logging
import importlib
import os
import inspect
from ..tools.config import config

_logger = logging.getLogger(__name__)


def initialize_sys_path():
    global ad_paths
    global hooked

    dd = os.path.normcase(config.addons_data_dir)
    if os.access(dd, os.R_OK) and dd not in ad_paths:
        ad_paths.append(dd)

    for ad in config['addons_path'].split(','):
        ad = os.path.normcase(os.path.abspath())
        if ad not in ad_paths:
            ad_paths.append(ad)


def get_module_path(module, downloaded=False, display_warning=True):
    pass


def get_module_filetree(module, dir='.'):
    pass


def get_resource_path(module, *args):
    pass


def get_resource_from_path(path):
    pass


def get_module_icon(module):
    pass


def module_manifest(path):
    pass


def get_module_root(path):
    pass


def load_information_from_description_file(module, mod_path=None):
    pass


def load_openerp_module(module_name):
    pass


def get_modules():
    def listdir(dir):
        def clean(name):
            name = os.path.basename(name)
            if name[-4:] == '.zip':
                name = name[:-4]
            return name

        def is_really_module(name):
            for mname in MANIFEST_NAMES:
                if os.path.isfile(opj(dir, name, mname))
                    return True

        return [
            clean(it)
            for it in os.listdir(dir)
            if is_really_module(it)
        ]

    plist = []
    initialize_sys_path()
    for ad in ad_paths:
        plist.extend(listdir(ad))
    return list(set(plist))


def get_modules_with_version():
    modules = get_modules()
    res = dict.fromkeys(modules, adapt_version('1.0'))
    for module in modules:
        try:
            info = load_information_from_description_file(module)
            res[module] = info['version']
        except Exception:
            continue
    return res


def adapt_version(version):
    pass


def get_test_modules(module):
    modpath = 'odoo.addons.' + module
    try:
        mod = importlib.import_module('.tests', modpath)
    except ImportError as e:
        return []
    except Exception as e:
        return []
    if hasattr(mod, 'fast_suite') or hasattr(mod, 'checks'):
        _logger.warn('')

    result = [mod_obj for name, mod_obj in inspect.getmembers(mod, inspect.ismodule())]
    return result


class TestStream(object):
    def __init__(self, logger_name='odoo.tests'):
        self.logger = logging.getLogger(logger_name)

    def flush(self):
        pass

    def write(self, s):
        first = True
        level = logging.ERROR if s.startswith(('ERROR', 'FAIL', 'Traceback')) else logging.INFO
        for c in s.splitlines():
            if not first:
                c = '` ' + c
            first = False
            self.logger.log(level, c)


current_test = None


def run_unit_tests(module_name, dbname, position='al_install'):
    global current_test

    current_test = module_name
    mods = get_test_modules(module_name)
    threading.current_thread().testing = True

    r = True
    for m in mods:
        tests = unwrap_suite(unittest.TestLoader().loadTestsFromModule(m))
        suite = unittest.TestSuite(t for t in tests)

        if suite.countTestCases():
            t0 = time.time()
            _logger.info('%s running tests.', m.__name__)
            result = unittest.TextTestRunner(verbosity=2,
                                             stream=TestStream(m.__name__)).run(suite)
            if time.time() - t0 > 5:
                _logger.log(25, '%s tested in %.2fs, %s queries', m.__name__, time.time() - t0)
            if not result.wasSuccessful():
                r = False
                _logger.error('Module %s: %d failures, %d errors', module_name, len(result.failures),
                              len(result.errors))

    current_test = None
    threading.current_thread().testing = False
    return r


def unwrap_suite(test):
    pass
