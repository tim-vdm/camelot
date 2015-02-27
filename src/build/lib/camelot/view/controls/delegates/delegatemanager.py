#  ============================================================================
#
#  Copyright (C) 2007-2013 Conceptive Engineering bvba. All rights reserved.
#  www.conceptive.be / info@conceptive.be
#
#  This file is part of the Camelot Library.
#
#  This file may be used under the terms of the GNU General Public
#  License version 2.0 as published by the Free Software Foundation
#  and appearing in the file license.txt included in the packaging of
#  this file.  Please review this information to ensure GNU
#  General Public Licensing requirements will be met.
#
#  If you are unsure which license is appropriate for your use, please
#  visit www.python-camelot.com or contact info@conceptive.be
#
#  This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
#  WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#
#  For use of this library in commercial applications, please contact
#  info@conceptive.be
#
#  ============================================================================

import logging
logger = logging.getLogger('camelot.view.controls.delegates.delegatemanager')

import six

from ....core.qt import QtGui, QtCore, Qt, variant_to_py, is_deleted
from .plaintextdelegate import PlainTextDelegate

class DelegateManager(QtGui.QItemDelegate):
    """Manages custom delegates, should not be used by the application
  developer
  """

    def __init__(self, columns, parent=None):
        QtGui.QItemDelegate.__init__(self, parent)
        # set a delegate for the vertical header
        self.insert_column_delegate(-1, PlainTextDelegate(parent=self))
        self._columns = columns

    def get_column_delegate(self, column):
        delegate = self.findChild(QtGui.QAbstractItemDelegate, str(column))
        if delegate is None:
            field_name, field_attributes = self._columns[column]
            delegate = field_attributes['delegate'](parent=self, **field_attributes)
            self.insert_column_delegate(column, delegate)
        return delegate

    def insert_column_delegate(self, column, delegate):
        """Inserts a custom column delegate"""
        assert delegate != None
        delegate.setObjectName(str(column))
        delegate.commitData.connect(self._commit_data)
        delegate.closeEditor.connect(self._close_editor)

    def _commit_data(self, editor):
        self.commitData.emit(editor)

    @QtCore.qt_slot( QtGui.QWidget, QtGui.QAbstractItemDelegate.EndEditHint )
    def _close_editor(self, editor, hint):
        self.closeEditor.emit(editor, hint )

    def paint(self, painter, option, index):
        """Use a custom delegate paint method if it exists"""
        delegate = self.get_column_delegate(index.column())
        delegate.paint(painter, option, index)

    def createEditor(self, parent, option, index):
        """Use a custom delegate createEditor method if it exists"""
        try:
            delegate = self.get_column_delegate(index.column())
            editor = delegate.createEditor(parent, option, index)
        except Exception as e:
            logger.error('Programming Error : could not createEditor editor data for editor at column %s'%(index.column()), exc_info=e)
            return QtGui.QWidget( parent = parent ) 
        return editor

    def setEditorData(self, editor, index):
        """Use a custom delegate setEditorData method if it exists"""
        logger.debug('setting editor data for column %s' % index.column())
        # the datawidgetmapper has no mechanism to remove a deleted
        # editor from its list of editors for which the data is set
        if not is_deleted(editor):
            try:
                delegate = self.get_column_delegate(index.column())
                delegate.setEditorData(editor, index)
            except Exception as e:
                logger.error('Programming Error : could not set editor data for editor at column %s'%(index.column()), exc_info=e)
                logger.error('value that could not be set : %s'%six.text_type(variant_to_py(index.model().data(index, Qt.EditRole))))
                logger.error('editor that failed %s %s'%(type(editor).__name__, editor.objectName()))

    def setModelData(self, editor, model, index):
        """Use a custom delegate setModelData method if it exists"""
        logger.debug('setting model data for column %s' % index.column())
        delegate = self.get_column_delegate(index.column())
        delegate.setModelData(editor, model, index)

    def sizeHint(self, option, index):
        option = QtGui.QStyleOptionViewItem()
        delegate = self.get_column_delegate(index.column())
        return delegate.sizeHint(option, index)

    #def eventFilter(self, *args):
        #"""The datawidgetmapper installs the delegate as an event filter
        #on each editor.
        
        #TODO : investigate if this is a reliable alternative to implement
               #commitData instead of the editingFinished signal.
        #"""
        #return False

