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

import six

from ....core.qt import QtGui, QtCore, Qt
from camelot.core.utils import ugettext as _
from camelot.view.controls.editors import CustomEditor
from camelot.view.controls.editors.customeditor import ValueLoading
from camelot.view.controls.editors.integereditor import CustomDoubleSpinBox

class MonthsEditor(CustomEditor):
    """MonthsEditor

    composite months and years editor
    """

    def __init__(self, parent=None, editable=True, field_name='months', **kw):
        CustomEditor.__init__(self, parent)
        self.setSizePolicy( QtGui.QSizePolicy.Preferred,
                            QtGui.QSizePolicy.Fixed )        
        self.setObjectName( field_name )
        self.years_spinbox = CustomDoubleSpinBox()
        self.months_spinbox = CustomDoubleSpinBox()
        self.years_spinbox.setRange(-1, 10000)
        self.months_spinbox.setRange(-1, 12)
        self.years_spinbox.setSuffix(_(' years'))
        self.months_spinbox.setSuffix(_(' months'))
        
        self.years_spinbox.setDecimals(0)
        self.years_spinbox.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.years_spinbox.setSingleStep(1)
        
        self.months_spinbox.setDecimals(0)
        self.months_spinbox.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.months_spinbox.setSingleStep(1)

        self.years_spinbox.editingFinished.connect( self._spinbox_editing_finished )
        self.months_spinbox.editingFinished.connect( self._spinbox_editing_finished )
        
        layout = QtGui.QHBoxLayout()
        layout.addWidget(self.years_spinbox)
        layout.addWidget(self.months_spinbox)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    @QtCore.qt_slot()
    def _spinbox_editing_finished(self):
        self.editingFinished.emit()
        
    def set_field_attributes(self, **kwargs):
        super(MonthsEditor, self).set_field_attributes(**kwargs)
        self.set_enabled(kwargs.get('editable', False))
        self.set_background_color(kwargs.get('background_color', None))
        self.years_spinbox.setToolTip(six.text_type(kwargs.get('tooltip') or ''))

    def set_enabled(self, editable=True):
        self.years_spinbox.setReadOnly(not editable)
        self.years_spinbox.setEnabled(editable)
        self.months_spinbox.setReadOnly(not editable)
        self.months_spinbox.setEnabled(editable)
        if not editable:
            self.years_spinbox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
            self.months_spinbox.setButtonSymbols(QtGui.QAbstractSpinBox.NoButtons)
        else:
            self.years_spinbox.setButtonSymbols(QtGui.QAbstractSpinBox.UpDownArrows)
            self.months_spinbox.setButtonSymbols(QtGui.QAbstractSpinBox.UpDownArrows)

    def set_value(self, value):
        # will set privates value_is_none and _value_loading
        value = CustomEditor.set_value(self, value)
        if value is None:
            self.years_spinbox.setValue(self.years_spinbox.minimum())
            self.months_spinbox.setValue(self.months_spinbox.minimum())
        else:
            # value comes as a months total
            years, months = divmod( value, 12 )
            self.years_spinbox.setValue(years)
            self.months_spinbox.setValue(months)

    def get_value(self):
        if CustomEditor.get_value(self) is ValueLoading:
            return ValueLoading
        self.years_spinbox.interpretText()
        years = int(self.years_spinbox.value())
        self.months_spinbox.interpretText()
        months = int(self.months_spinbox.value())
        years_is_none = (years == self.years_spinbox.minimum())
        months_is_none = (months == self.months_spinbox.minimum())
        if years_is_none and months_is_none:
            return None
        if years_is_none:
            years = 0
        if months_is_none:
            months = 0
        return (years * 12) + months
