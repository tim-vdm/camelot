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
logger = logging.getLogger('camelot.view.controls.delegates.comboboxdelegate')

from .customdelegate import CustomDelegate, DocumentationMetaclass

import six

from ....core.qt import Qt, variant_to_py
from camelot.view.controls import editors
from camelot.view.proxy import ValueLoading

class ComboBoxDelegate( six.with_metaclass( DocumentationMetaclass,
                                            CustomDelegate ) ):
    
    editor = editors.ChoicesEditor

    def setEditorData(self, editor, index):
        value = variant_to_py(index.data(Qt.EditRole))
        field_attributes = variant_to_py(index.data(Qt.UserRole))
        editor.set_field_attributes(**(field_attributes or {}))
        editor.set_value(value)

    def paint(self, painter, option, index):
        painter.save()
        self.drawBackground(painter, option, index)
        value = variant_to_py(index.data(Qt.DisplayRole))
        if value in (None, ValueLoading):
            value = ''
        self.paint_text(painter, option, index, six.text_type(value) )
        painter.restore()

