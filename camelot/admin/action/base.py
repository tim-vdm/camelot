#  ============================================================================
#
#  Copyright (C) 2007-2016 Conceptive Engineering bvba.
#  www.conceptive.be / info@conceptive.be
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#      * Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#      * Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#      * Neither the name of Conceptive Engineering nor the
#        names of its contributors may be used to endorse or promote products
#        derived from this software without specific prior written permission.
#  
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
#  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
#  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#  ============================================================================
from __future__ import annotations

import logging
import typing

from enum import Enum
from dataclasses import dataclass, field
from typing import Any

from ...admin.icon import Icon
from ...core.qt import QtWidgets, QtGui
from ...core.serializable import DataclassSerializable
from ...core.utils import ugettext_lazy

LOGGER = logging.getLogger( 'camelot.admin.action' )

class ModelContext( object ):
    """
The Model context in which an action is running.  The model context can contain
reference to database sessions or other model related data. 
    """

    def __init__( self ):
        pass


@dataclass
class Mode(DataclassSerializable):
    """A mode is a way in which an action can be triggered, a print action could
be triggered as 'Export to PDF' or 'Export to Word'.  None always represents
the default mode.
    
.. attribute:: value

    a value representing the mode to the developer
    
.. attribute:: verbose_name

    The name shown to the user
    
.. attribute:: icon

    The icon of the mode
    
.. attribute:: modes: 

    Optionally, a list of sub modes.
    
.. attribute:: enabled:

    Flag indicating whether mode should be enabled or not.
    """

    value: Any
    verbose_name: typing.Union[str, ugettext_lazy]
    icon: typing.Union[Icon, None] = None
    modes: typing.List[Mode] = field(default_factory=list)
    enabled: bool = True

    def __post_init__(self):
        for mode in self.modes:
            assert isinstance(mode, type(self))

    def render( self, parent ):
        """
        In case this mode is a leaf (no containing sub modes), a :class:`QtWidgets.QAction`
        will be created (or `QtWidgets.QMenu` in case this modes has sub modes defined)
        that can be used to enable the widget to trigger the action in a specific mode.
        The data attribute of the action will contain the value of the mode.
        In case has underlying sub modes, a `QtWidgets.QMenu` will be created to which
        the rendered sub modes can be attached.
        :return: a :class:`QtWidgets.QAction` or :class:`QtWidgets.QMenu` to use this mode
        """
        if self.modes:
            menu = QtWidgets.QMenu(str(self.verbose_name), parent=parent)
            parent.addMenu(menu)
            return menu
        else:
            action = QtGui.QAction( parent )
            action.setData( self.value )
            action.setText( str(self.verbose_name) )
            action.setEnabled(self.enabled)
            action.setIconVisibleInMenu(False)
            return action

@dataclass
class State(DataclassSerializable):
    """A state represents the appearance and behavior of the widget that
triggers the action.  When the objects in the model change, the 
:meth:`Action.get_state` method will be called, which should return the
updated state for the widget.

.. attribute:: verbose_name

    The name of the action as it will appear in the button, this defaults to
    the verbose_name of the action.
    
.. attribute:: icon

    The icon that represents the action, of type 
    :class:`camelot.admin.icon.Icon`, this defaults to the icon of the action.

.. attribute:: tooltip

    The tooltip as displayed to the user, this should be of type 
    :class:`camelot.core.utils.ugettext_lazy`, this defaults to the tooltip
    op the action.

.. attribute:: enabled

    :const:`True` if the widget should be enabled (the default), 
    :const:`False` otherwise
    
.. attribute:: visible

    :const:`True` if the widget should be visible (the default), 
    :const:`False` otherwise

.. attribute:: notification

    :const:`True` if the buttons should attract the attention of the user, 
    defaults to :const:`False`.

.. attribute:: modes

    The modes in which an action can be triggered, a list of :class:`Mode`
    objects.

.. attribute:: shortcut

    The shortcut key sequence to trigger the action.

.. attribute:: color

    A color used to indicate something regarding the action's state. This color
    can be used as button text color, background or outline for example.
    """

    verbose_name: typing.Union[str, ugettext_lazy, None] = None
    icon: typing.Union[Icon, None] = None
    tooltip: typing.Union[str, ugettext_lazy, None] = None
    enabled: bool = True
    visible: bool = True
    notification: bool = False
    modes: typing.List[Mode] = field(default_factory=list)
    shortcut: typing.Optional[str] = None
    color: typing.Optional[str] = None

# TODO: When all action step have been refactored to be serializable, ActionStep can be implemented as NamedDataclassSerializable,
#       which NamedDataclassSerializableMeta metaclass replaces the need for MetaActionStep.
class MetaActionStep(type):

    action_steps = dict()

    def __new__(cls, clsname, bases, attrs):
        newclass = super().__new__(cls, clsname, bases, attrs)
        cls.action_steps[clsname] = newclass
        return newclass

class ActionStep(metaclass=MetaActionStep):
    """A reusable part of an action.  Action step object can be yielded inside
the :meth:`model_run`.  When this happens, their :meth:`gui_run` method will
be called inside the *GUI thread*.  The :meth:`gui_run` can pop up a dialog
box or perform other GUI related tasks.

When the ActionStep is blocking, it will return control after the 
:meth:`gui_run` is finished, and the return value of :meth:`gui_run` will
be the result of the :keyword:`yield` statement.

When the ActionStep is not blocking, the :keyword:`yield` statement will
return immediately and the :meth:`model_run` will not be blocked.

.. attribute:: blocking

    a :keyword:`boolean` indicating if the ActionStep is blocking, defaults
    to :const:`True`
    
.. attribute:: cancelable

    a :keyword:`boolean` indicating if the ActionStep is allowed to raise
    a `CancelRequest` exception when yielded, defaults to :const:`True`

    """

    blocking = True
    cancelable = True

    def model_run( self, model_context, mode ):
        raise Exception('This should not happen')

    @classmethod
    def deserialize_result(cls, model_context: ModelContext, serialized_result):
        """
        :param model_context:  An object of type
            :class:`camelot.admin.action.ModelContext`, which is the context
            on which the action was started.

        :param serialized_result: The serialized result coming from the client.

        :return: The deserialized result. The default implementation returns the
            serialized result as is. This function can be reimplemented to change
            this behavior.
        """
        return serialized_result


class RenderHint(Enum):
    """
    How an action wants to be rendered in the ui
    """

    PUSH_BUTTON = 'push_button'
    TOOL_BUTTON = 'tool_button'
    CLOSE_BUTTON = 'close_button'
    SEARCH_BUTTON = 'search_button'
    EXCLUSIVE_GROUP_BOX = 'exclusive_group_box'
    NON_EXCLUSIVE_GROUP_BOX = 'non_exclusive_group_box'
    COMBO_BOX = 'combo_box'
    LABEL = 'label'
    STRETCH = 'stretch'
    STATUS_BUTTON = 'status_button'
    DROP = 'drop'


class Action( ActionStep ):
    """An action has a set of attributes that define its appearance in the
GUI.  
    
.. attribute:: name

    The internal name of the action, this can be used to store preferences
    concerning the action in the settings

.. attribute:: render_hint

    a :class:`RenderHint` instance indicating the preffered way to render
    this action in the user interface

These attributes are used at the default values for the creation of a
:class:`camelot.admin.action.base.State` object that defines the appearance
of the action button.  Subclasses of :class:`Action` that require dynamic
values for these attributes can reimplement the :class:`Action.get_state`
method.

.. attribute:: verbose_name

    The name as displayed to the user, this should be of type 
    :class:`camelot.core.utils.ugettext_lazy`
    
.. attribute:: icon

    The icon that represents the action, of type 
    :class:`camelot.admin.icon.Icon`

.. attribute:: tooltip

    The tooltip as displayed to the user, this should be of type 
    :class:`camelot.core.utils.ugettext_lazy` or :class:`QtGui.QKeySequence`

.. attribute:: modes

    The modes in which an action can be triggered, a list of :class:`Mode`
    objects.
    
For each of these attributes there is a corresponding getter method
which is used by the view.  Subclasses of :class:`Action` that require dynamic
values for these attributes can reimplement the getter methods.

.. attribute:: shortcut

    The shortcut that can be used to trigger the action, this should be of 
    type :class:`camelot.core.utils.ugettext_lazy`
    
.. attribute:: drop_mime_types

    A list of strings with the mime types that can be used to trigger this
    action by dropping objects on the related widget.  Example ::
    
        drop_mime_types = ['text/plain']
    
An action has two important methods that can be reimplemented.  These are 
:meth:`model_run` for manipulations of the model and :meth:`gui_run` for
direct manipulations of the user interface without a need to access the model.

To prevent an action object from being garbage collected, it can be registered
with a view.

        """

    name = u'action'
    render_hint = RenderHint.PUSH_BUTTON
    verbose_name = None
    icon = None
    tooltip = None
    shortcut = None 
    modes = []
    drop_mime_types = []
    
    def get_name( self ):
        """
        :return: a string, by default the :attr:`name` attribute
        """
        return self.name
    
    def get_shortcut( self ):
        """
        :return: a :class:`camelot.core.utils.ugettext_lazy`, by default the 
        :attr:`shortcut` attribute
        """
        return self.shortcut

    def get_tooltip( self ):
        """
        :return: a `str` with the tooltip to display, by default this is
            a combination of the :attr:`tooltip` and the :attr:`shortcut`
            attribute
        """
        tooltip = None

        if self.tooltip is not None:
            tooltip = str(self.tooltip)

        if isinstance(self.shortcut, QtGui.QKeySequence):
            tooltip = (tooltip or u'') + '\n' + self.shortcut.toString(QtGui.QKeySequence.SequenceFormat.NativeText)
        elif isinstance(self.shortcut, QtGui.QKeySequence.StandardKey):
            for shortcut in QtGui.QKeySequence.keyBindings(self.shortcut):
                tooltip = (tooltip or u'') + '\n' + shortcut.toString(QtGui.QKeySequence.SequenceFormat.NativeText)
                break
        elif self.shortcut is not None:
            tooltip = (tooltip or u'') + '\n' + str(self.shortcut)

        return tooltip

    def model_run( self, model_context, mode ):
        """A generator that yields :class:`camelot.admin.action.ActionStep`
        objects.  This generator can be called in the *model thread*.
        
        :param context:  An object of type
            :class:`camelot.admin.action.ModelContext`.
            What is in the  context depends on how the action was called.
        """
        yield

    def get_state( self, model_context ):
        """
        This method is called inside the Model thread to verify if
        the state of the action widget visible to the current user.
        
        :param model_context: the context available in the *Model thread*
        :return: an instance of :class:`camelot.admin.action.base.State`
        """
        state = State()
        state.verbose_name = self.verbose_name
        state.icon = self.icon
        state.tooltip = self.get_tooltip()
        state.modes = self.modes
        state.shortcut = self.shortcut
        return state



