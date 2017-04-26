import os
import sys
import tempfile

from PyQt4 import QtGui

from camelot.core.templates import environment, loader
from camelot.core.conf import settings
from vfinance.admin.jinja2_filters import filters
from vfinance.admin.jinja2_tests import tests
from vfinance.model.financial.notification.environment import PackageExtensionLoader

if os.environ.get('DEBUGGER') == 'wingdb':
    import wingdbstub
    assert wingdbstub

tempdir = tempfile.mkdtemp()

s = type('settings', (object,), {'CAMELOT_MEDIA_ROOT': tempdir})

settings.append(s)


qapplications = []

loader.loaders.insert(0, PackageExtensionLoader(
    package_name='vfinance', package_path='art/templates'))
loader.loaders.insert(0, PackageExtensionLoader(
    package_name='vfinance_ws', package_path='art/templates'))
loader.loaders.insert(0, PackageExtensionLoader(
    package_name='vfinance_ws', package_path='art/custom_templates'))
environment.autoescape = True
environment.finalize = lambda x: '' if x is None else x
#environment.newline_sequence = '\r\n'
environment.add_extension('jinja2.ext.i18n')
environment.add_extension('jinja2.ext.do')
environment.filters.update(filters)
environment.tests.update(tests)
qapplications.append(QtGui.QApplication(([a for a in sys.argv[2:] if a])))
