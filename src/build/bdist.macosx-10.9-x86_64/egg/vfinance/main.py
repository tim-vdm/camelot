import datetime
import logging
import logging.handlers
import multiprocessing
import os
import warnings

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)-5s] [%(name)-35s] - %(message)s')
LOGGER = logging.getLogger('main')

from sqlalchemy import exc as sa_exc

from camelot.admin.action.application import Application
from camelot.admin.action.application_action import SelectProfile
from camelot.core.qt import QtCore
from camelot.core.utils import ugettext
from camelot.view.main import main_action
from camelot.view import action_steps

from application_admin import FinanceApplicationAdmin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('main')
#logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)

class VFinance( Application ):
                
    # keep reference to stack trace file, to prevent garbage collection
    stacktrace_file = None

    def model_run( self, model_context ):
        from camelot.core.conf import settings
        from camelot.core.profile import ProfileStore
        from camelot.core.sql import metadata
        from camelot.core.threaded_logging import CloudLaunchHandler, ThreadedHandler
        from cloudlaunch2.repository import get_repository
        from cloudlaunch2.resources import get_cloud_record
        from cloudlaunch2.functions import ( get_connection_kwargs, 
                                             get_appdata_folder )
        yield action_steps.UpdateProgress(0, 5, ugettext('Configure logging'))
        # remote logging
        record = get_cloud_record('vfinance')
        if record:
            handler = CloudLaunchHandler( record, 
                                          connection_kwargs = get_connection_kwargs() )
            logging.root.addHandler( handler )
        # initiate the application
        yield action_steps.UpdateProgress(0, 5, ugettext('Select profile'))
        from vfinance.model.bank.settings import SettingsProxy
        profile_store = ProfileStore()
        yield SelectProfile(profile_store)
        profile = profile_store.get_last_profile()
        QtCore.QLocale.setDefault(QtCore.QLocale(profile.get_language_code()))
        yield action_steps.UpdateProgress(0, 5, ugettext('Connect to database'))
        QtCore.QLocale.setDefault(QtCore.QLocale(profile.locale_language))
        vfsettings = SettingsProxy(profile)
        settings.append( vfsettings )
        # local emergency logging
        log_folder = settings.LOG_FOLDER
        if log_folder is not None:
            handler = logging.handlers.TimedRotatingFileHandler( os.path.join(settings.LOG_FOLDER, settings.LOG_FILENAME), 
                                                                 when='midnight', 
                                                                 backupCount=62 )
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)-5s] [%(name)-35s] - %(message)s'))
            logging.root.addHandler(ThreadedHandler(handler))
        yield action_steps.UpdateProgress(0, 5, ugettext('Setup database'))
        metadata.bind = settings.ENGINE()
        settings.setup_model()
        yield action_steps.UpdateProgress(0, 5, ugettext('Load settings from database'))
        vfsettings.load()
        for step in super(VFinance, self).model_run( model_context ):
            yield step
        # purge the repository
        try:
            record = get_cloud_record('vfinance')
            repository = get_repository()
            if record and repository:
                LOGGER.info( 'purging repository' )
                repository.purge( record )
        except Exception, e:
            LOGGER.warn('could not purge repository', exc_info=e)  
        # setup faulthandler
        try:
            import faulthandler
        except:
            LOGGER.info( 'could not import faulthandler library' )
            return
        try:
            app_data = get_appdata_folder()
            now = datetime.datetime.now()
            timestamp = '%s_%03d' % (now.strftime('%Y_%m_%d_%H_%M_%S'), now.microsecond / 1000)
            stack_trace_folder = os.path.join( app_data, 'stack_traces', '%d' % now.year, '%02d' % now.month, '%02d' % now.day )
            if not os.path.exists( stack_trace_folder ):
                os.makedirs( stack_trace_folder )
            filename = '%s-pid-%s.txt'%( timestamp, os.getpid() )
            filename = os.path.join( stack_trace_folder, filename )
            self.stacktrace_file = open( filename, 'w' )
            LOGGER.info( 'enable faulthandler : %s'%filename )
            faulthandler.enable( self.stacktrace_file, all_threads=True )
        except Exception, e:
            LOGGER.error( 'could not enable faulthandler', exc_info=e )
        except:
            LOGGER.error( 'unknown exception while enabling faulthandler' )
    
def main():
    try:

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=sa_exc.SAWarning)
            main_action( VFinance( FinanceApplicationAdmin() ) )
    except Exception, e:
        LOGGER.warn('could not launch', exc_info=e)

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
