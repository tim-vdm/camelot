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

from ....core.qt import variant_to_py, Qt, QtCore
from .customdelegate import CustomDelegate, DocumentationMetaclass
from camelot.view.controls import editors
from camelot.core.utils import create_constant_function
from camelot.view.proxy import ValueLoading

class TimeDelegate( six.with_metaclass( DocumentationMetaclass,
                                        CustomDelegate ) ):
   
    editor = editors.TimeEditor
      
    def __init__(self, parent=None, editable=True, **kwargs):
        CustomDelegate.__init__(self, parent, editable)
        locale = QtCore.QLocale()
        self.time_format = locale.timeFormat(locale.ShortFormat)
        
    def paint(self, painter, option, index):
        painter.save()
        self.drawBackground(painter, option, index)
        value = variant_to_py( index.model().data( index, Qt.EditRole ) )
        
        value_str = u''
        if value not in (None, ValueLoading):
            time = QtCore.QTime(value.hour, value.minute, value.second)
            value_str = time.toString(self.time_format)

        self.paint_text(painter, option, index, value_str)
        painter.restore()
      
    def setModelData(self, editor, model, index):
        value = editor.time()
        t = datetime.time(hour=value.hour(),
                          minute=value.minute(),
                          second=value.second())
        model.setData(index, create_constant_function(t))




