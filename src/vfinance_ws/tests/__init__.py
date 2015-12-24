import os
import sys

from PyQt4 import QtGui

from camelot.core.templates import environment, loader
from vfinance.admin.jinja2_filters import filters
from vfinance.model.financial.notification.environment import PackageExtensionLoader

if os.environ.get('DEBUGGER') == 'wingdb':
    import wingdbstub
    assert wingdbstub

qapplications = []

loader.loaders.insert(0, PackageExtensionLoader(
    package_name='vfinance', package_path='art/templates'))
loader.loaders.insert(0, PackageExtensionLoader(
    package_name='vfinance_ws', package_path='art/templates'))
environment.autoescape = True
environment.finalize = lambda x: '' if x is None else x
#environment.newline_sequence = '\r\n'
environment.add_extension('jinja2.ext.i18n')
environment.add_extension('jinja2.ext.do')
environment.filters.update(filters)
qapplications.append(QtGui.QApplication(([a for a in sys.argv[2:] if a])))
