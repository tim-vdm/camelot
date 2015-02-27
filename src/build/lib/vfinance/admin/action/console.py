from camelot.admin.action import ActionStep
from camelot.core.utils import ugettext_lazy as _

from IPython.qt.console.rich_ipython_widget import RichIPythonWidget

from camelot.core.qt import QtGui, QtCore

class IPythonView(RichIPythonWidget):
    
    title_changed_signal = QtCore.pyqtSignal(QtCore.QString)
    icon_changed_signal = QtCore.pyqtSignal(QtGui.QIcon)

class IPythonConsole(ActionStep):
    
    verbose_name = _('Interactive Console')
    
    def gui_run(self, gui_context):
        #control.exit_requested.connect(stop)
        #control.kernel_manager = km
        gui_context.workspace.add_view(IPythonView())
