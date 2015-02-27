from camelot.view.main import Application

import datetime
import logging
import os

LOGGER = logging.getLogger( 'cloudlaunch.integration.camelot_application' )

class CloudlaunchApplication( Application ):
    """A Camelot application that features cloudlaunch
    integration.
    """
    
    def __init__(self, application_admin):
        super( CloudlaunchApplication, self ).__init__( application_admin )
        # keep reference to stack trace file, to prevent garbage collection
        self.stacktrace_file = None
        
    def pre_initialization(self):
        super( CloudlaunchApplication, self ).pre_initialization()
        try:
            import faulthandler
        except:
            LOGGER.info( 'could not import faulthandler library' )
            return
        try:
            from cloudlaunch2.functions import get_appdata_folder
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
