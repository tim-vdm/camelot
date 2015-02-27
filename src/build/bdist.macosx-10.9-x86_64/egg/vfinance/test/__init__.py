# -*- coding: utf-8 -*-
"""

=============================
Unit Test suite for V-Finance
=============================

Class naming conventions
========================

- Test...Case : An actual test case that is a subclass of 
    unittest.TestCase, that has test methods.

- Abstract...Case : a subclass of unittest.TestCase to be subclassed by
  Test...Case.  This class has no test methods, as such it can be subclassed
  without expanding the number of test methods ran.  This class can provide
  initial data for tests to run.

- Mixin...Case : an class providing helper methods, to be subclassed
    by Test...Case or Abstract...Case.  This class has no test methods and
    is not a subclass of unittest.TestCase

To run pdb:

from PyQt4.QtCore import pyqtRemoveInputHook
from pdb import set_trace
pyqtRemoveInputHook()
set_trace()
    
"""

#
# initiate profiles and fixtures
#
import faulthandler
import sys
import tempfile
import os
# import locale
import logging

from camelot.core.qt import QtGui

from vfinance import logging_format
import sip

if os.environ.get('DEBUGGER') == 'wingdb':
    import wingdbstub
    assert wingdbstub
LOGGER = logging.getLogger('vfinance.test')
# ensure stack trace when there is a segfault
faulthandler.enable()

#logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
engine_logger = logging.getLogger('sqlalchemy.engine')
engine_handler = logging.FileHandler('sql_logs.txt')
engine_handler.setFormatter(logging.Formatter(logging_format))
engine_handler.setLevel(logging.DEBUG)
engine_logger.addHandler(engine_handler)

try:
    import cdecimal
    sys.modules["decimal"] = cdecimal
    LOGGER.info('using cdecimal instead of decimale')
except:
    LOGGER.info('using decimal, cdecimal import failed')

sip.setdestroyonexit(False)

# import settings
from vfinance.application_admin import FinanceApplicationAdmin

# to store the profile, a qapplication is needed
if not QtGui.QApplication.instance():
    #
    # set up a test application
    #
    app_admin = FinanceApplicationAdmin()
    _application_ = QtGui.QApplication([a for a in sys.argv if a])
    QtGui.QApplication.setApplicationName(app_admin.get_name())
    QtGui.QApplication.setOrganizationName(app_admin.get_organization_name())
    # setattr(settings, 'THREADING', False)

from camelot.core.profile import Profile, ProfileStore
store = ProfileStore()

media_location = tempfile.mkdtemp('-vf-media')
if sys.platform.startswith('win'):
    media_location = 'C:\\Windows\\Temp'

default_unittest_profile = {
    'dialect':'postgresql',
    'host':'127.0.0.1',
    'port':'5432',
    'database':'vfinance_test',
    'user':'postgres',
    'pass':'postgres',
    'media_location': media_location,
    'locale_language':'nl',
    'proxy_host':'',
    'proxy_port':'',
    'proxy_username':'',
    'proxy_password':'',
    'stylesheet':'black',
}

original_profile = store.read_profile('unittest')
if original_profile==None:
    original_profile = Profile('unittest')

for key, value in default_unittest_profile.items():
    var_name = 'UNIT_TEST_%s'%(key.upper())
    setattr( original_profile, key, os.environ.get( var_name, value ) )

store.write_profile(original_profile)
store.set_last_profile(original_profile)

from camelot.core.conf import settings
from vfinance.model.bank.settings import SettingsProxy
settings.append( SettingsProxy(original_profile) )

#
# Settings specific to the unittests
#

class TestSettings(object):
    
    def __init__(self):
        self.TEST_FOLDER = os.environ.get('UNIT_TEST_TEST_FOLDER', None)
        self.UNIT_TEST_TEMPLATE_FOLDERS = os.environ.get('UNIT_TEST_TEMPLATE_FOLDERS', None)
        if not self.TEST_FOLDER:
            self.TEST_FOLDER = tempfile.mkdtemp('-vf-test')

settings.append(TestSettings())

#
# bind the metadata
#
from camelot.core.sql import metadata
engine =  settings.ENGINE()
metadata.bind = engine

#
# Set Python and Qt locale
#
from camelot.core.qt import QtCore
# Normally not needed anymore, since all formatting is now done through Qt
# locale.setlocale( locale.LC_ALL, '' )
QtCore.QLocale.setDefault( QtCore.QLocale('nl_BE') )

from vfinance.utils import setup_model
from vfinance.model.financial.notification.environment import setup_templates

# uncomment the next lines to profile the startup process
#import cProfile
#command = 'setup_model(False, templates=False)'
#cProfile.runctx( command, globals(), locals(), filename='setup_model.profile' )

setup_model(False, templates = False)

from camelot.model.fixture import Fixture
from vfinance.model.bank.settings import Settings

#
# set folders to look for templates
#
if hasattr(settings, 'UNIT_TEST_TEMPLATE_FOLDERS') and settings.UNIT_TEST_TEMPLATE_FOLDERS:
    test_templates_folders = settings.UNIT_TEST_TEMPLATE_FOLDERS
else:
    test_templates_folders = os.path.join(os.path.dirname(__file__), 'resources', 'templates')
for t in test_templates_folders.split(os.pathsep):
    if not os.path.exists(t):
        raise Exception( 'No templates folder found' )

LOGGER.info('use templates folders {}'.format(test_templates_folders))
for key, value in [ ('TEMPLATES_FOLDER', test_templates_folders),
                    ('CLIENT_TEMPLATES_FOLDER', test_templates_folders),
                    ('CLIENT_TEMP_FOLDER', '/tmp' ),
                    ('MAX_BOOK_YEAR', '2400'),
                    ('MIN_BOOK_YEAR', '2000'),
                    ('BANK_ACCOUNT_SUPPLIER', '500000000000'),
                    ('CODA_CENTRALISERENDE_INSTELLING', '200'),
                    ('CODA_IDENTIFICATIE_AFGEVER', '1240907'),
                    ('CODA_IDENTIFICATIE_SCHULDEISER', '1240907'),
                    ('CODA_REKENINGNUMMER', '001-3837687-55'),
                    ('CODA_3_REKENINGNUMMER', '002-3837687-55'),
                    ('CODA_NAAM_SCHULDEISER','SOC.PATRONALE HYPOTHECAIR'),
                    ('FINANCIAL_ACCOUNT_PREMIUMS_RECEIVED', '1234'),
                    ('FINANCIAL_SECURITY_ACCOUNT_PREFIX', '23312'),
                    ('FINANCIAL_SECURITY_DIGITS', '3'),
                    ('FINANCIAL_SECURITY_LIABILITY_PREFIX', '152'),
                    ('VENICE_VERSION', 'MOCK'),
                    ('VENICE_FOLDER', '/tmp/venice/'),
                    ('VENICE_DOSSIER', 'patronale'),
                    ('VENICE_INITIALS', 'TS'),
                    ('VENICE_USER', 'TEST'),
                    ('VENICE_PASSWORD', 'TEST'),
                    ('VENICE_SECURE', '0'),
                    ('HYPO_ACCOUNT_KLANT', '411100000000'),
                    ('HYPO_ACCOUNT_VORDERING', '2921000000'),
                    ('HYPO_DOSSIER_STEP', '1' ),
                    ('HYPO_RAPPEL_KOST', '5.3'),
                    ('HYPO_COMPANY_ID', '123'),
                    ('HYPO_FROM_SUPPLIER', '9000000'),
                    ('HYPO_THRU_SUPPLIER', '9999999'),
                    ('STOMP_SERVER_1', '127.0.0.1' ),
                    ('STOMP_PORT_1', '61613'),
                    ('UL3_HTTP_SERVER', '192.168.100.1'),
                    ('UL3_HTTP_PORT', 5500),
                    ('AWS_ACCESS_KEY', 'AKIAIRWSEQARHSLCSSTA' ),
                    ('AWS_SECRET_KEY', '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' ),
                    ('AWS_QUEUE_IN_NAME', 'vfinance_development' ),
                    ('COMPANY_NAME', u'Bank FOD Financiën' ),
                    ('COMPANY_STREET1', 'Koning Albert II-laan 33' ),
                    ('COMPANY_STREET2', '' ),
                    ('COMPANY_CITY_CODE', '1030' ),
                    ('COMPANY_CITY_NAME', 'Brussel' ),
                    ('COMPANY_COUNTRY_CODE', 'BE' ),
                    ('COMPANY_COUNTRY_NAME', 'Belgium' ),
                    ('GOV_BE_COMPANY_NUMBER', '0222222248' ),
                    ('SEPA_CREDITOR_IDENTIFIER', 'BE10ZZZ0403288089' ),
                    ('SEPA_DIRECT_DEBIT_BIC', 'KREDBEBB' ),
                    ('SEPA_DIRECT_DEBIT_IBAN', 'NL91ABNA0417164300' ),
                    ('VFINANCE_DOSSIER_NAME', 'unittest'),

                    ]: # prod = 5500, test=4500
    Fixture.insert_or_update_fixture(Settings, unicode(key), {'key':unicode(key), 'value':unicode(value)})
# reload settings after fixtures have been put into db
settings.load()
# now setup the templates
setup_templates()
