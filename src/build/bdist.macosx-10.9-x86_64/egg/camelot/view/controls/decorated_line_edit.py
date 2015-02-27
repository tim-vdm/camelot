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

from ...core.qt import QtCore, QtGui
from ..art import ColorScheme
from .editors.customeditor import draw_tooltip_visualization


class DecoratedLineEdit(QtGui.QLineEdit):
    """
    A QLineEdit with additional decorations :
    
     * a validity, which will trigger the background color

    """
      
    arrow_down_key_pressed = QtCore.qt_signal()
    
    _font_metrics = None
    _background_color = None
      
    def __init__(self, parent = None):
        super( DecoratedLineEdit, self ).__init__( parent = parent )
        if self._font_metrics is None:
            self._font_metrics = QtGui.QFontMetrics(QtGui.QApplication.font())
            self._background_color = self.palette().color(self.backgroundRole())
        self.textChanged.connect(self.text_changed)

    def set_minimum_width(self, width):
        """Set the minimum width of the line edit, measured in number of 
        characters.  Use a number of characters the content of the editor
        is unknown, but a sample string can be used if the input pattern
        is known (such as a formatted date or a code) for greater accuracy.
        
        :param width: the number of characters that should be visible in the
            editor or a string that should fit in the editor
        """
        if isinstance( width, six.string_types ):
            self.setMinimumWidth( self._font_metrics.width( width ) )
        else:
            self.setMinimumWidth( self._font_metrics.averageCharWidth() )

    @QtCore.qt_slot(six.text_type)
    def text_changed(self, text):
        self._update_background_color()

    def setValidator(self, validator):
        if self.validator() != validator:
            super(DecoratedLineEdit, self).setValidator(validator)
        # updating the bg color should only be needed when the validat did
        # actually change, however this seems to break the virtualaddresseditor
        # when the existing input is invalid
        self._update_background_color()

    def _update_background_color(self):
        palette = self.palette()
        if self.hasAcceptableInput():
            palette.setColor(self.backgroundRole(), self._background_color)
        else:
            palette.setColor(self.backgroundRole(), ColorScheme.orange_2)
        self.setPalette(palette)
        
    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Down:
            self.arrow_down_key_pressed.emit()
        
        QtGui.QLineEdit.keyPressEvent(self, e)

    def paintEvent(self, event):
        super(DecoratedLineEdit, self).paintEvent(event)
        
        if self.toolTip():
            draw_tooltip_visualization(self)


