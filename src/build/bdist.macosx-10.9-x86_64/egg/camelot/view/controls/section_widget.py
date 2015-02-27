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

"""left navigation pane"""

import logging
logger = logging.getLogger('camelot.view.controls.section_widget')

import six

from ...core.qt import variant_to_py, QtCore, QtGui, Qt
from camelot.admin.action.application_action import ApplicationActionGuiContext
from camelot.admin.section import Section, SectionItem
from camelot.view.model_thread import post
from camelot.view.controls.modeltree import ModelItem
from camelot.view.controls.modeltree import ModelTree

class PaneSection(QtGui.QWidget):

    def __init__(self, parent, section, workspace):
        super(PaneSection, self).__init__(parent)
        self._items = []
        self._workspace = workspace
        self._section = section
        layout = QtGui.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        section_tree = ModelTree(parent=self)
        # i hate the sunken frame style
        section_tree.setFrameShape(QtGui.QFrame.NoFrame)
        section_tree.setFrameShadow(QtGui.QFrame.Plain)
        section_tree.contextmenu = QtGui.QMenu(self)
        section_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        section_tree.customContextMenuRequested.connect(self.create_context_menu)
        section_tree.setObjectName( 'SectionTree' )
        section_tree.itemClicked.connect( self._item_clicked )
        section_tree.setWordWrap( False )
        layout.addWidget( section_tree )
        self.setLayout(layout)
        post( section.get_items, self.set_items )

    @QtCore.qt_slot(object)
    def set_items(self, items, parent = None):
        logger.debug('setting items for current navpane section')
        section_tree = self.findChild(QtGui.QWidget, 'SectionTree')
        if section_tree:
            if parent == None:
                # take a copy, so the copy can be extended
                self._items = list(i for i in items)
                section_tree.clear()
                section_tree.clear_model_items()
                parent = section_tree
    
            if not items: return
    
            for item in items:
                label = item.get_verbose_name()
                icon = item.get_icon()
                model_item = ModelItem( parent, 
                                        [six.text_type(label)],
                                        item )
                if icon:
                    model_item.set_icon(icon.getQIcon())
                section_tree.modelitems.append( model_item )
                if isinstance( item, Section ):
                    child_items = item.get_items()
                    self.set_items( child_items, parent = model_item )
                    self._items.extend( child_items )
                    
            section_tree.resizeColumnToContents( 0 )

    def create_context_menu(self, point):
        logger.debug('creating context menu')
        section_tree = self.findChild(QtGui.QWidget, 'SectionTree')
        if section_tree:
            item = section_tree.itemAt(point)
            if item:
                section_tree.contextmenu.clear()
                for mode in item.section_item.get_modes():
                    action = mode.render( self )
                    action.triggered.connect( self._action_triggered )
                    section_tree.contextmenu.addAction( action )
                section_tree.setCurrentItem(item)
                section_tree.contextmenu.popup(section_tree.mapToGlobal(point))

    @QtCore.qt_slot(bool)
    def _action_triggered( self, _checked ):
        action = self.sender()
        mode_name = variant_to_py( action.data() )
        self._run_current_action( mode_name )
        
    @QtCore.qt_slot(QtGui.QTreeWidgetItem, int)
    def _item_clicked(self, _item, _column):
        self._run_current_action()

    def _run_current_action( self, mode_name=None ):
        section_tree = self.findChild(QtGui.QWidget, 'SectionTree')
        if section_tree:
            item = section_tree.currentItem()
            index = section_tree.indexFromItem(item)
            parent = index.parent()
            if parent.row() >= 0:
                section = self._items[parent.row()]
                section_item = section.items[index.row()]
            else:
                section_item = self._items[index.row()]
            if not isinstance( section_item, SectionItem ):
                return
            gui_context = ApplicationActionGuiContext()
            gui_context.mode_name = mode_name
            gui_context.workspace = self._workspace
            gui_context.admin = self._section.admin
            section_item.get_action().gui_run( gui_context )
                        
class NavigationPane(QtGui.QDockWidget):

    def __init__(self, workspace, parent):
        super(NavigationPane, self).__init__(parent)
        self._workspace = workspace
        tb = QtGui.QToolBox()
        tb.setMinimumWidth(220)
        tb.setFrameShape(QtGui.QFrame.NoFrame)
        tb.layout().setContentsMargins(0,0,0,0)
        tb.layout().setSpacing(1)
        tb.setObjectName('toolbox')
        tb.setMouseTracking(True)
        
        # hack for removing the dock title bar
        self.setTitleBarWidget(QtGui.QWidget())
        self.setWidget(tb)
        self.setFeatures(QtGui.QDockWidget.NoDockWidgetFeatures)

    def wheelEvent(self, wheel_event):
        steps = -1 * wheel_event.delta() / (8 * 15)
        toolbox = self.findChild(QtGui.QWidget, 'toolbox')
        if steps and toolbox:
            current_index = toolbox.currentIndex()
            toolbox.setCurrentIndex( max( 0, min( current_index + steps, toolbox.count() ) ) )

    @QtCore.qt_slot(object)
    def set_sections(self, sections):
        logger.debug('setting navpane sections')
        if not sections:
            self.setMaximumWidth(0)
            return
        toolbox = self.findChild(QtGui.QWidget, 'toolbox')

        # performs QToolBox clean up
        # QToolbox won't delete items we have to do it explicitly
        count = toolbox.count()
        while count:
            item = toolbox.widget(count-1)
            toolbox.removeItem(count-1)
            item.deleteLater()
            count -= 1
            
        for section in sections:
            # TODO: old navpane used translation here
            name = six.text_type( section.get_verbose_name() )
            icon = section.get_icon().getQIcon()
            pwdg = PaneSection(toolbox, section, self._workspace)
            toolbox.addItem(pwdg, icon, name)

        toolbox.setCurrentIndex(0)
        # WARNING: hardcoded width
        #self._toolbox.setMinimumWidth(220)



