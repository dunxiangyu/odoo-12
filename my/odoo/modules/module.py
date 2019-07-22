import unittest
import threading
import time
import logging
import os
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
    pass


def get_modules_with_version():
    pass


def adapt_version(version):
    pass


def get_test_modules(module):
    pass


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
