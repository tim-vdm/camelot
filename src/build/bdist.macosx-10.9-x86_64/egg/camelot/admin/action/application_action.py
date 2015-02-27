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
import time

import six

from ...core.conf import settings
from ...core.qt import Qt, QtCore, QtGui, QtWebKit
from camelot.admin.action.base import Action, GuiContext, Mode, ModelContext
from camelot.core.exception import CancelRequest
from camelot.core.orm import Session
from camelot.core.utils import ugettext, ugettext_lazy as _
from camelot.core.backup import BackupMechanism
from camelot.view.art import Icon

"""ModelContext, GuiContext and Actions that run in the context of an 
application.
"""

LOGGER = logging.getLogger( 'camelot.admin.action.application_action' )

class ApplicationActionModelContext( ModelContext ):
    """The Model context for an :class:`camelot.admin.action.Action`.  On top 
    of the attributes of the :class:`camelot.admin.action.base.ModelContext`, 
    this context contains :
        
    .. attribute:: admin
   
        the application admin.

    .. attribute:: session

        the active session
    """
    
    def __init__( self ):
        super( ApplicationActionModelContext, self ).__init__()
        self.admin = None

    # Cannot set session in constructor because constructor is called
    # inside the GUI thread
    @property
    def session( self ):
        return Session()
        
class ApplicationActionGuiContext( GuiContext ):
    """The GUI context for an :class:`camelot.admin.action.Action`.  On top of 
    the attributes of the :class:`camelot.admin.action.base.GuiContext`, this 
    context contains :
    
    .. attribute:: workspace
    
        the :class:`camelot.view.workspace.DesktopWorkspace` of the 
        application in which views can be opened or adapted.
        
    .. attribute:: admin
    
        the application admin.
    """
    
    model_context = ApplicationActionModelContext
    
    def __init__( self ):
        super( ApplicationActionGuiContext, self ).__init__()
        self.workspace = None
        self.admin = None
    
    def get_window(self):
        if self.workspace is not None:
            return self.workspace.window()

    def create_model_context( self ):
        context = super( ApplicationActionGuiContext, self ).create_model_context()
        context.admin = self.admin
        return context
        
    def copy( self, base_class=None ):
        new_context = super( ApplicationActionGuiContext, self ).copy( base_class )
        new_context.workspace = self.workspace
        new_context.admin = self.admin
        return new_context
        
class SelectProfile( Action ):
    """Select the application profile to use
    
    :param profile_store: an object of type
        :class:`camelot.core.profile.ProfileStore`
    :param edit_dialog_class: a :class:`QtGui.QDialog` to display the needed
        fields to store in a profile
    This action is also useable as an action step, which will return the
    selected profile.
    """
    
    new_icon = Icon('tango/16x16/actions/document-new.png')
    save_icon = Icon('tango/16x16/actions/document-save.png')
    load_icon = Icon('tango/16x16/actions/document-open.png')
    file_name_filter = _('Profiles file (*.ini)')
    
    def __init__( self, profile_store, edit_dialog_class=None):
        from camelot.core.profile import ProfileStore
        if profile_store==None:
            profile_store=ProfileStore()
        self.profile_store = profile_store
        self.edit_dialog_class = edit_dialog_class
        self.selected_profile = None
    
    def gui_run(self, gui_context):
        super(SelectProfile, self).gui_run(gui_context)
        return self.selected_profile
        
    def model_run( self, model_context ):
        from camelot.view import action_steps
        from camelot.view.action_steps.profile import EditProfiles

        # dummy profiles
        new_profile, save_profiles, load_profiles = object(), object(), object()
        selected_profile = new_profile
        try:
            while selected_profile in (None, new_profile, 
                                       save_profiles, load_profiles):
                profiles = self.profile_store.read_profiles()
                profiles.sort()
                items = [(None,'')] + [(p,p.name) for p in profiles]
                font = QtGui.QFont()
                font.setItalic(True)
                items.append({Qt.UserRole: new_profile, Qt.FontRole: font,
                              Qt.DisplayRole: ugettext('new/edit profile'),
                              Qt.DecorationRole: self.new_icon
                              })
                if len(profiles):
                    items.append({Qt.UserRole: save_profiles, Qt.FontRole: font,
                                  Qt.DisplayRole: ugettext('save profiles'),
                                  Qt.DecorationRole: self.save_icon
                                  })
                items.append({Qt.UserRole: load_profiles, Qt.FontRole: font,
                              Qt.DisplayRole: ugettext('load profiles'),
                              Qt.DecorationRole: self.load_icon
                              })
                select_profile = action_steps.SelectItem( items )
                last_profile = self.profile_store.get_last_profile()
                select_profile.title = ugettext('Profile Selection')
                if len(profiles):
                    subtitle = ugettext('Select a stored profile:')
                else:
                    subtitle = ugettext('''Load profiles from file or'''
                                        ''' create a new profile''')
                select_profile.subtitle = subtitle
                if last_profile in profiles:
                    select_profile.value = last_profile
                elif len(profiles):
                    select_profile.value = None
                else:
                    select_profile.value = load_profiles
                selected_profile = yield select_profile
                if selected_profile is new_profile:
                    edit_profile_name = ''
                    while selected_profile is new_profile:
                        profile_info = yield EditProfiles(profiles, current_profile=edit_profile_name, dialog_class=self.edit_dialog_class)
                        profile = self.profile_store.read_profile(profile_info['name'])
                        if profile is None:
                            profile = self.profile_store.profile_class(**profile_info)
                        else:
                            profile.__dict__.update(profile_info)
                        yield action_steps.UpdateProgress(text=ugettext('Verifying database settings'))
                        engine = profile.create_engine()
                        try:
                            connection = engine.raw_connection()
                            cursor = connection.cursor()
                            cursor.close()
                            connection.close()
                        except Exception as e:
                            exception_box = action_steps.MessageBox( title = ugettext('Could not connect to database, please check host and port'),
                                                                     text = _('Verify driver, host and port or contact your system administrator'),
                                                                     standard_buttons = QtGui.QMessageBox.Ok )
                            exception_box.informative_text = six.text_type(e)
                            yield exception_box
                            edit_profile_name = profile.name
                            if profile in profiles:
                                profiles.remove(profile)
                            profiles.append(profile)
                            profiles.sort()
                            continue
                        self.profile_store.write_profile(profile)
                        selected_profile = profile
                elif selected_profile is save_profiles:
                    file_name = yield action_steps.SaveFile(file_name_filter=self.file_name_filter)
                    self.profile_store.write_to_file(file_name)
                elif selected_profile is load_profiles:
                    file_names =  yield action_steps.SelectFile(file_name_filter=self.file_name_filter)
                    for file_name in file_names:
                        self.profile_store.read_from_file(file_name)
        except CancelRequest:
            # explicit handling of exit when cancel button is pressed,
            # to avoid the use of subgenerators in the main action
            yield Exit()
        message = ugettext(u'Use {} profile'.format(selected_profile.name))
        yield action_steps.UpdateProgress(text=message)
        self.profile_store.set_last_profile( selected_profile )
        self.selected_profile = selected_profile


class EntityAction( Action ):
    """Generic ApplicationAction that acts upon an Entity class"""

    def __init__( self, 
                  entity_admin ):
        """
        :param entity_admin: an instance of 
            :class:`camelot.admin.entity_admin.EntityAdmin` to be used to
            visualize the entities
        """
        from camelot.admin.entity_admin import EntityAdmin
        assert isinstance( entity_admin, EntityAdmin )
        self._entity_admin = entity_admin
        
class OpenTableView( EntityAction ):
    """An application action that opens a TableView of an Entity

    :param entity_admin: an instance of 
        :class:`camelot.admin.entity_admin.EntityAdmin` to be used to
        visualize the entities
    
    """

    modes = [ Mode( 'new_tab', _('Open in New Tab') ) ]
        
    def get_state( self, model_context ):
        state = super( OpenTableView, self ).get_state( model_context )
        state.verbose_name = self.verbose_name or self._entity_admin.get_verbose_name_plural()
        return state

    def model_run( self, model_context ):
        from camelot.view import action_steps
        yield action_steps.UpdateProgress(text=_('Open table'))
        step = action_steps.OpenTableView(self._entity_admin,
                                          self._entity_admin.get_query())
        step.new_tab = (model_context.mode_name == 'new_tab')
        yield step

class OpenNewView( EntityAction ):
    """An application action that opens a new view of an Entity
    
    :param entity_admin: an instance of 
        :class:`camelot.admin.entity_admin.EntityAdmin` to be used to
        visualize the entities
    
    """

    verbose_name = _('New')
    shortcut = QtGui.QKeySequence.New
    icon = Icon('tango/16x16/actions/document-new.png')
    tooltip = _('New')
            
    def get_state( self, model_context ):
        state = super( OpenNewView, self ).get_state( model_context )
        state.verbose_name = self.verbose_name or ugettext('New %s')%(self._entity_admin.get_verbose_name())
        state.tooltip = ugettext('Create a new %s')%(self._entity_admin.get_verbose_name())
        return state

    def model_run( self, model_context ):
        from camelot.view import action_steps
        admin = yield action_steps.SelectSubclass(self._entity_admin)
        new_object = admin.entity()
        # Give the default fields their value
        admin.add(new_object)
        admin.set_defaults(new_object)
        yield action_steps.OpenFormView([new_object], admin)

class ShowHelp( Action ):
    """Open the help"""
    
    shortcut = QtGui.QKeySequence.HelpContents
    icon = Icon('tango/16x16/apps/help-browser.png')
    tooltip = _('Help content')
    verbose_name = _('Help')
    
    def gui_run( self, gui_context ):
        self.view = QtWebKit.QWebView( None )
        self.view.load( gui_context.admin.get_application_admin().get_help_url() )
        self.view.setWindowTitle( ugettext('Help Browser') )
        self.view.setWindowIcon( self.icon.getQIcon() )
        self.view.show()
     
class ShowAbout( Action ):
    """Show the about dialog with the content returned by the
    :meth:`ApplicationAdmin.get_about` method
    """
    
    verbose_name = _('&About')
    icon = Icon('tango/16x16/mimetypes/application-certificate.png')
    tooltip = _("Show the application's About box")
    
    def gui_run( self, gui_context ):
        abtmsg = gui_context.admin.get_application_admin().get_about()
        QtGui.QMessageBox.about( gui_context.workspace, 
                                 ugettext('About'), 
                                 six.text_type( abtmsg ) )
        
class Backup( Action ):
    """
Backup the database to disk

.. attribute:: backup_mechanism

    A subclass of :class:`camelot.core.backup.BackupMechanism` that enables 
    the application to perform backups an restores.
    """
    
    verbose_name = _('&Backup')
    tooltip = _('Backup the database')
    icon = Icon('tango/16x16/actions/document-save.png')
    backup_mechanism = BackupMechanism

    def model_run( self, model_context ):
        from camelot.view.action_steps import UpdateProgress, SelectBackup
        label, storage = yield SelectBackup( self.backup_mechanism )
        yield UpdateProgress( text = _('Backup in progress') )
        backup_mechanism = self.backup_mechanism(label, storage)
        backup_iterator = backup_mechanism.backup(settings.ENGINE())
        for completed, total, description in backup_iterator:
            yield UpdateProgress(completed,
                                 total,
                                 text = description)

class Refresh( Action ):
    """Reload all objects from the database and update all views in the
    application."""
    
    verbose_name = _('Refresh')
    shortcut = QtGui.QKeySequence( Qt.Key_F9 )
    icon = Icon('tango/16x16/actions/view-refresh.png')
    
    def model_run( self, model_context ):
        import sqlalchemy.exc as sa_exc
        from camelot.core.orm import Session
        from camelot.view import action_steps
        from camelot.view.remote_signals import get_signal_handler
        LOGGER.debug('session refresh requested')
        progress_db_message = ugettext('Reload data from database')
        progress_view_message = ugettext('Update screens')
        session = Session()
        signal_handler = get_signal_handler()
        refreshed_objects = []
        expunged_objects = []
        #
        # Loop over the objects one by one to be able to detect the deleted
        # objects
        #
        session_items = len( session.identity_map )
        for i, (_key, obj) in enumerate( six.iteritems(session.identity_map) ):
            try:
                session.refresh( obj )
                refreshed_objects.append( obj )
            except sa_exc.InvalidRequestError:
                #
                # this object could not be refreshed, it was probably deleted
                # outside the scope of this session, so assume it is deleted
                # from the application its point of view
                #
                session.expunge( obj )
                expunged_objects.append( obj )
            if i%10 == 0:
                yield action_steps.UpdateProgress( i, 
                                                   session_items, 
                                                   progress_db_message )
        yield action_steps.UpdateProgress( text = progress_view_message )
        for obj in refreshed_objects:
            signal_handler.sendEntityUpdate( self, obj )
        for obj in expunged_objects:
            signal_handler.sendEntityDelete( self, obj )
        yield action_steps.Refresh()

class Restore(Refresh):
    """
Restore the database to disk

.. attribute:: backup_mechanism

    A subclass of :class:`camelot.core.backup.BackupMechanism` that enables 
    the application to perform backups an restores.
"""
    
    verbose_name = _('&Restore')
    tooltip = _('Restore the database from a backup')
    icon = Icon('tango/16x16/devices/drive-harddisk.png')
    backup_mechanism = BackupMechanism
    shortcut = None
            
    def model_run( self, model_context ):
        from camelot.view.action_steps import UpdateProgress, SelectRestore
        label, storage = yield SelectRestore( self.backup_mechanism )
        yield UpdateProgress( text = _('Restore in progress') )
        backup_mechanism = self.backup_mechanism(label, storage)
        restore_iterator = backup_mechanism.restore(settings.ENGINE())
        for completed, total, description in restore_iterator:
            yield UpdateProgress(completed,
                                 total,
                                 text = description)
        for step in super(Restore, self).model_run(model_context):
            yield step

class Profiler( Action ):
    """Start/Stop the runtime profiler.  This action exists for debugging
    purposes, to evaluate where an application spends its time.
    """
    
    verbose_name = _('Profiler start/stop')
    
    def __init__(self):
        self.profile = None
    
    def model_run(self, model_context):
        from ...view import action_steps
        from six import StringIO
        import cProfile
        import pstats
        if self.profile is None:
            yield action_steps.MessageBox('Start profiler')
            self.profile = cProfile.Profile()
            self.profile.enable()
        else:
            yield action_steps.UpdateProgress(text='Creating statistics')
            self.profile.disable()
            stream = StringIO()
            stats = pstats.Stats(self.profile, stream=stream)
            self.profile = None
            stats.sort_stats('cumulative')
            yield action_steps.UpdateProgress(text='Create report')
            stats.print_stats()
            stream.seek(0)
            yield action_steps.OpenStream(stream)
            filename = action_steps.OpenFile.create_temporary_file('.prof')
            stats.dump_stats(filename)
            yield action_steps.MessageBox(
                'Profile stored in {0}'.format(filename))
            
class Exit( Action ):
    """Exit the application"""
    
    verbose_name = _('E&xit')
    shortcut = QtGui.QKeySequence.Quit
    icon = Icon('tango/16x16/actions/system-shutdown.png')
    tooltip = _('Exit the application')
    
    def gui_run( self, gui_context ):
        from camelot.view.model_thread import get_model_thread
        model_thread = get_model_thread()
        # we might exit the application when the workspace is not even there
        if gui_context.workspace != None:
            gui_context.workspace.close_all_views()
        if model_thread != None:
            model_thread.stop()
        QtCore.QCoreApplication.exit(0)
        
#
# Some actions to assist the debugging process
#

class ChangeLogging( Action ):
    """Allow the user to change the logging configuration"""
    
    verbose_name = _('Change logging')
    icon = Icon('tango/16x16/emblems/emblem-photos.png')
    tooltip = _('Change the logging configuration of the application')

    @classmethod
    def before_cursor_execute(cls, conn, cursor, statement, parameters, context,
                              executemany):
        context._query_start_time = time.time()
        LOGGER.info("start query:\n\t%s" % statement.replace("\n", "\n\t"))
        LOGGER.info("parameters: %r" % (parameters,))

    @classmethod
    def after_cursor_execute(cls, conn, cursor, statement, parameters, context,
                             executemany):
        total = time.time() - context._query_start_time
        LOGGER.info("query Complete in %.02fms" % (total*1000))

    @classmethod
    def begin_transaction(cls, conn):
        LOGGER.info("begin transaction")

    @classmethod
    def commit_transaction(cls, conn):
        LOGGER.info("commit transaction")

    @classmethod
    def rollback_transaction(cls, conn):
        LOGGER.info("rollback transaction")

    @classmethod
    def connection_checkout(cls, dbapi_connection, connection_record, 
                            connection_proxy):
        LOGGER.info('checkout connection {0}'.format(id(dbapi_connection)))

    @classmethod
    def connection_checkin(cls, dbapi_connection, connection_record):
        LOGGER.info('checkin connection {0}'.format(id(dbapi_connection)))

    def model_run( self, model_context ):
        from camelot.view.controls import delegates
        from camelot.view import action_steps
        from camelot.admin.object_admin import ObjectAdmin
        
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        from sqlalchemy.pool import Pool
        
        class Options( object ):
            
            def __init__( self ):
                self.level = logging.INFO
                self.queries = False
                self.pool = False
                
            class Admin( ObjectAdmin ):
                list_display = ['level', 'queries', 'pool']
                field_attributes = { 'level':{ 'delegate':delegates.ComboBoxDelegate,
                                               'editable':True,
                                               'choices':[(l,logging.getLevelName(l)) for l in [logging.DEBUG, 
                                                                                                logging.INFO, 
                                                                                                logging.WARNING,
                                                                                                logging.ERROR,
                                                                                                logging.CRITICAL]]},
                                     'queries':{ 'delegate': delegates.BoolDelegate,
                                                 'tooltip': _('Log and time queries send to the database'),
                                                 'editable': True},
                                     'pool':{ 'delegate': delegates.BoolDelegate,
                                              'tooltip': _('Log database connection checkin/checkout'),
                                              'editable': True},
                                     }
                
        options = Options()
        yield action_steps.ChangeObject( options )
        logging.getLogger().setLevel( options.level )
        if options.queries == True:
            event.listen(Engine, 'before_cursor_execute',
                         self.before_cursor_execute)
            event.listen(Engine, 'after_cursor_execute',
                         self.after_cursor_execute)
            event.listen(Engine, 'begin',
                         self.begin_transaction)
            event.listen(Engine, 'commit',
                         self.commit_transaction)
            event.listen(Engine, 'rollback',
                         self.rollback_transaction)
        if options.pool == True:
            event.listen(Pool, 'checkout',
                         self.connection_checkout)
            event.listen(Pool, 'checkin',
                         self.connection_checkin)
            
class DumpState( Action ):
    """Dump the state of the application to the output, this method is
    triggered by pressing :kbd:`Ctrl-Alt-D` in the GUI"""
    
    verbose_name = _('Dump state')
    shortcut = QtGui.QKeySequence( QtCore.Qt.CTRL+QtCore.Qt.ALT+QtCore.Qt.Key_D )
    
    def model_run( self, model_context ):
        import collections
        import gc
        from camelot.core.orm import Session
        from camelot.view import action_steps
        from camelot.view.register import dump_register
        from camelot.view.proxy.collection_proxy import CollectionProxy

        dump_logger = LOGGER.getChild('dump_state')
        session = Session()
        type_counter = collections.defaultdict(int)

        yield action_steps.UpdateProgress( text = _('Dumping session state') )
        gc.collect()
        
        dump_logger.warn( '======= begin register dump =============' )
        dump_register( dump_logger )
        dump_logger.warn( '======= end register dump ===============' )

        for o in session:
            type_counter[type(o).__name__] += 1
        dump_logger.warn( '======= begin session dump ==============' )
        for k,v in six.iteritems(type_counter):
            dump_logger.warn( '%s : %s'%(k,v) )
        dump_logger.warn( '======= end session dump ==============' )

        yield action_steps.UpdateProgress( text = _('Dumping item model state') )
        dump_logger.warn( '======= begin item model dump =========' )
        for o in gc.get_objects():
            if isinstance(o, CollectionProxy):
                dump_logger.warn( '%s is used by :'%(six.text_type( o )) )
                for r in gc.get_referrers(o):
                    dump_logger.warn( ' ' + type(r).__name__ )
                    for rr in gc.get_referrers(r):
                        dump_logger.warn( '  ' + type(rr).__name__ )
        dump_logger.warn( '======= end item model dump ===========' )

class RuntimeInfo( Action ):
    """Pops up a messagebox showing the version of certain
    libraries used.  This is for debugging purposes., this action is
    triggered by pressing :kbd:`Ctrl-Alt-I` in the GUI"""
    
    verbose_name = _('Show runtime info')
    shortcut = QtGui.QKeySequence( QtCore.Qt.CTRL+QtCore.Qt.ALT+QtCore.Qt.Key_I )
    
    def model_run( self, model_context ):
        from camelot.view import action_steps
        import sys
        import sqlalchemy
        import chardet
        import jinja2
        import xlrd
        import xlwt
                
        html = """<em>Python:</em> <b>%s</b><br>
                  <em>Qt:</em> <b>%s</b><br>
                  <em>PyQt:</em> <b>%s</b><br>
                  <em>SQLAlchemy:</em> <b>%s</b><br>
                  <em>Chardet:</em> <b>%s</b><br>
                  <em>Jinja:</em> <b>%s</b><br>
                  <em>xlrd:</em> <b>%s</b><br>
                  <em>xlwt:</em> <b>%s</b><br><br>
                  <em>path:<br></em> %s""" % ('.'.join([str(el) for el in sys.version_info]),
                                              float('.'.join(str(QtCore.QT_VERSION_STR).split('.')[0:2])),
                                              QtCore.PYQT_VERSION_STR,
                                              sqlalchemy.__version__,
                                              chardet.__version__,
                                              jinja2.__version__,
                                              xlrd.__VERSION__,
                                              xlwt.__VERSION__,
                                              six.text_type(sys.path))        
        yield action_steps.PrintHtml( html )
        
class SegmentationFault( Action ):
    """Create a segmentation fault by reading null, this is to test
        the faulthandling functions.  this method is triggered by pressing
        :kbd:`Ctrl-Alt-0` in the GUI"""
    
    verbose_name = _('Segmentation Fault')
    shortcut = QtGui.QKeySequence( QtCore.Qt.CTRL+QtCore.Qt.ALT+QtCore.Qt.Key_0 )
    
    def model_run( self, model_context ):
        from camelot.view import action_steps
        ok = yield action_steps.MessageBox( text =  'Are you sure you want to segfault the application',
                                            standard_buttons = QtGui.QMessageBox.No | QtGui.QMessageBox.Yes )
        if ok == QtGui.QMessageBox.Yes:
            import faulthandler
            faulthandler._read_null()        
        
class Authentication( Action ):
    """This action provides information of the currently active authentication
    mechanism, in other words, it displays the active user and his permissions.
    
    Add this action to a toolbar if you want to show the authentication
    information to the user.
    """
    
    icon = Icon('tango/16x16/emotes/face-smile.png')
    image_size = 32
    
    def render( self, gui_context, parent ):
        from camelot.view.controls.action_widget import AuthenticationWidget
        return AuthenticationWidget(self, gui_context, parent)
    
    def get_state(self, model_context):
        from camelot.model.authentication import get_current_authentication
        from camelot.view import art
        state = super(Authentication, self).get_state(model_context)
        authentication = get_current_authentication()
        state.verbose_name = authentication.username
        state.tooltip = ', '.join([g.name for g in authentication.groups])
        representation = authentication.get_representation()
        if representation is not None:
            state.icon = art.IconFromImage(representation)
        return state
    
    def model_run(self, model_context):
        from camelot.model.authentication import get_current_authentication
        from camelot.view import action_steps
        from camelot.view.controls.editors.imageeditor import ImageEditor
        select_file = action_steps.SelectFile(file_name_filter=ImageEditor.filter)
        filenames = yield select_file
        for filename in filenames:
            yield action_steps.UpdateProgress(text=ugettext('Scale image'))
            image = QtGui.QImage(filename)
            image = image.scaled(self.image_size,
                                 self.image_size,
                                 Qt.KeepAspectRatio)
            authentication = get_current_authentication()
            authentication.set_representation(image)
            yield action_steps.FlushSession(model_context.session)

def structure_to_application_action(structure, application_admin):
    """Convert a python structure to an ApplicationAction

    :param application_admin: the 
        :class:`camelot.admin.application_admin.ApplicationAdmin` to use to
        create other Admin classes.
    """
    if isinstance(structure, Action):
        return structure
    admin = application_admin.get_related_admin( structure )
    return OpenTableView( admin )


