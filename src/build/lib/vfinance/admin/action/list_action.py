import logging

from camelot.core.qt import QtGui

from camelot.core.utils import ugettext as _
from camelot.admin.action import Action
from camelot.admin.action.list_action import DeleteSelection

LOGGER = logging.getLogger( 'vfinance.admin.action' )

class VFDeleteSelection( DeleteSelection ):
    
    def gui_run( self, gui_context):
        if hasattr(gui_context.admin, 'disallow_delete') and gui_context.admin.disallow_delete:
            message = 'Deleting record(s) is not allowed.'
            dialog = QtGui.QMessageBox(QtGui.QMessageBox.Information, 'Delete action not allowed', message)
            dialog.exec_()
        else:
            number_of_rows = len( gui_context.item_view.selectionModel().selectedRows() )
            plural_name = gui_context.admin.get_verbose_name_plural()
            answer = QtGui.QMessageBox.question( gui_context.item_view, 
                                                 _('Remove %s %s ?')%( number_of_rows, plural_name ), 
                                                 _('If you continue, they will no longer be accessible.'), 
                                                 QtGui.QMessageBox.Yes,
                                                 QtGui.QMessageBox.No )
            if answer == QtGui.QMessageBox.Yes:
                super( VFDeleteSelection, self ).gui_run( gui_context )
                
class RemoteDebugger( Action ):
    
    verbose_name = _('Remote debugger')
    
    def model_run( self, model_context ):
        import wingdbstub
        LOGGER.warn( 'started remote debugger {0.__name__}'.format( wingdbstub ) )
        
