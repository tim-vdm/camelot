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

import datetime

import six

from ....core.qt import QtGui, QtCore, Qt
from .customeditor import CustomEditor, set_background_color_palette
from .dateeditor import DateEditor
from camelot.view.proxy import ValueLoading

class TimeValidator(QtGui.QValidator):
    
    def __init__(self, parent=None):
        QtGui.QValidator.__init__(self, parent)
    
    def validate(self, input, pos):
        accept, input, pos = self._validate(input, pos)
        if six.PY3:
            return accept, input, pos
        else:
            return accept, pos

    def _validate(self, input, pos):
        input = six.text_type(input).strip()
        # allow None
        if len(input)==0:
            return (QtGui.QValidator.Acceptable, input, pos)
        parts = input.split(':')
        if len(parts)>2:
            return (QtGui.QValidator.Invalid, input, pos)
        # validate individual parts
        for i, part in enumerate(parts):
            if len(part)==0:
                return (QtGui.QValidator.Intermediate, input, pos)
            if len(part)<1:
                return (QtGui.QValidator.Intermediate, input, pos)
            if len(part)>2:
                return (QtGui.QValidator.Invalid, input, pos)
            if not part.isdigit():
                return (QtGui.QValidator.Invalid, input, pos)
            if i==1 or (i==0 and len(parts)==1):
                if int(part) > 59:
                    return (QtGui.QValidator.Invalid, input, pos)
            elif int(part) > 23:
                return (QtGui.QValidator.Invalid, input, pos)
        # validate the number of parts
        if len(parts)<2:
            return (QtGui.QValidator.Intermediate, input, pos)
        return (QtGui.QValidator.Acceptable, input, pos)
    
class DateTimeEditor(CustomEditor):
    """Widget for editing date and time separated and with popups"""
  
    def __init__(self,
                 parent,
                 editable=True,
                 nullable=True,
                 field_name = 'datetime',
                 **kwargs):
        CustomEditor.__init__(self, parent)
        self.setSizePolicy( QtGui.QSizePolicy.Preferred,
                            QtGui.QSizePolicy.Fixed )        
        self.setObjectName( field_name )
        import itertools
        self.nullable = nullable

        layout = QtGui.QHBoxLayout()
        self.dateedit = DateEditor(self, editable=editable, nullable=nullable, **kwargs)
        self.dateedit.editingFinished.connect( self.editing_finished )
        layout.addWidget(self.dateedit, 1)

        self.timeedit = QtGui.QComboBox(self)
        self.timeedit.setEditable(True)
        if not editable:
            self.timeedit.setEnabled(False)
        
        time_entries = [entry
                        for entry in itertools.chain(*(('%02i:00'%i, '%02i:30'%i)
                        for i in range(0,24)))]
        self.timeedit.addItems(time_entries)
        self.timeedit.setValidator(TimeValidator(self))
        self.timeedit.activated.connect( self.editing_finished )
        self.timeedit.lineEdit().editingFinished.connect( self.editing_finished )
        self.timeedit.lineEdit().setPlaceholderText('--:--')
        self.timeedit.setFocusPolicy( Qt.StrongFocus )

        layout.addWidget(self.timeedit, 1)
        # focus proxy is needed to activate the editor with a single click
        self.setFocusProxy(self.dateedit)
        self.setLayout(layout)
        layout.setContentsMargins( 0, 0, 0, 0)
        layout.setSpacing(0)

    @QtCore.qt_slot(six.text_type)
    @QtCore.qt_slot(int)
    @QtCore.qt_slot()
    def editing_finished(self, _arg=None):
        if self.time() and self.date():
            self.editingFinished.emit()
        
    def get_value(self):
        time_value = self.time()
        date_value = self.date()
        if time_value not in (None, ValueLoading) and date_value not in (None, ValueLoading):
            value = datetime.datetime(hour=time_value.hour(),
                                      minute=time_value.minute(),
                                      second=time_value.second(),
                                      year=date_value.year,
                                      month=date_value.month,
                                      day=date_value.day)
        else:
            value = None
        return CustomEditor.get_value(self) or value
    
    def set_value(self, value):
        value = CustomEditor.set_value(self, value)
        if value:
            self.dateedit.set_value(value.date())
            self.timeedit.lineEdit().setText('%02i:%02i'%(value.hour, value.minute))
        else:
            self.dateedit.set_value(None)
            self.timeedit.lineEdit().setText('')
      
    def date(self):
        return self.dateedit.get_value()
    
    def time(self):
        text = str(self.timeedit.currentText())
        if not len(text):
            return None
        parts = text.split(':')
        return QtCore.QTime(int(parts[0]), int(parts[1]))
      
    def set_enabled(self, editable=True):
        self.timeedit.setEnabled(editable)
        self.dateedit.setEnabled(editable)

    def set_field_attributes(self, **kwargs):
        super(DateTimeEditor, self).set_field_attributes(**kwargs)
        line_edit = self.findChild(QtGui.QWidget, 'date_line_edit')
        if line_edit is not None:
            self.set_enabled(kwargs.get('editable', False))
            line_edit.setToolTip(six.text_type(kwargs.get('tooltip') or ''))

    def set_background_color(self, background_color):
        self.dateedit.set_background_color( background_color )
        set_background_color_palette( self.timeedit.lineEdit(), background_color )



