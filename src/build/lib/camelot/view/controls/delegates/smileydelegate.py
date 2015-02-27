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

from ....core.qt import QtGui, QtCore, Qt, variant_to_py

import six

from .customdelegate import CustomDelegate, DocumentationMetaclass
from ..editors.smileyeditor import SmileyEditor, default_icons

class SmileyDelegate( six.with_metaclass( DocumentationMetaclass,
                                          CustomDelegate ) ):
    """Delegate for Smiley's
  """
    
    editor = SmileyEditor
  
    def __init__(self, parent, editable=True,  icons=default_icons, **kwargs):
        CustomDelegate.__init__(self,
                                parent=parent,
                                editable=editable,
                                icons=icons,
                                **kwargs)
        self.icons_by_name = dict(icons)
        
    def paint(self, painter, option, index):
        painter.save()
        icon_name = six.text_type(variant_to_py(index.model().data(index, Qt.DisplayRole)))
        
        background_color = QtGui.QColor(index.model().data(index, Qt.BackgroundRole))
        
        self.drawBackground(painter, option, index)
        rect = option.rect
        rect = QtCore.QRect(rect.left()+3, rect.top()+6, rect.width()-5, rect.height())
        
        if( option.state & QtGui.QStyle.State_Selected ):
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            if not self.editable:
                painter.fillRect(option.rect, option.palette.window())
            else:
                painter.fillRect(option.rect, background_color)
                
        if icon_name:
            pixmap = self.icons_by_name[icon_name].getQPixmap()
            QtGui.QApplication.style().drawItemPixmap(painter, rect, 1, pixmap)

        painter.restore()




