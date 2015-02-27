"""Cloud Launch - Cloud Deployed Python Applications

Launches a python application that has been published with a
cld file.

All arguments that start with '--cld' are processed by the
cloud launcher, other arguments are left for the application
itself.

If the --cld-file argument is given, that specific cld file
will be loaded, otherwise the file 'default.cld' in sys.exec_prefix
will be attempted.

The cld launcher will look in the cld file for the record
with the closest match to the requested branch and revsion and
launch that.
"""

import sys
from multiprocessing import freeze_support

win = sys.platform.startswith('win')
        
def popup_message(message):
    """Use windows script host to popup a message"""
    import win32com.client
    import traceback, cStringIO
    shell = win32com.client.Dispatch("WScript.Shell")
    sio = cStringIO.StringIO()
    traceback.print_exc(file=sio)
    traceback_print = sio.getvalue()
    sio.close()
    if traceback_print:
        message = '%s\n%s' % (message, traceback_print)
    shell.Popup(unicode(message), 0, "Cloud Launch Message")
    
def main():
    import argparse
    import logging
    import os
    from .functions import has_fast_internet
    from . import __version__ as version
    
    
    default_cloudlaunch = os.path.join( sys.exec_prefix, 'default.cld' )
    LOGGER = logging.getLogger('cloud_launch.main')
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cld-author", action="store", dest="author", default=None)
    parser.add_argument("--cld-name", action="store", dest="name", default=None)
    parser.add_argument("--cld-branch", action="store", dest="branch", default=None)
    parser.add_argument("--cld-revision", action="store", dest="revision", default=None)    
    parser.add_argument("--cld-update", action="store_true", dest="update", default=False)
    parser.add_argument("--cld-no-process", action="store_false", dest="process", default=True)
    parser.add_argument("--cld-file", action="store", dest="cld", default=default_cloudlaunch)
    parser.add_argument("--cld-entry-point", action="store", dest="entry_point", default=None,
                        help='Specify the entry point, use / as path separator')
    parser.add_argument("--cld-list", action="store_true", 
                        dest="list", default=False, help='Display a list of all available records')
    parser.add_argument("--cld-purge", action="store_true", 
                        dest="purge", default=False, help='Remove old downloads from the repository')    
    parser.add_argument(dest="application", nargs="*")

    options = parser.parse_args()
    LOGGER.info( u'launched with options %s'%unicode(options) )
    LOGGER.info( u'this is Cloud Launch version %s'%version )
    sys.argv = [a for a in sys.argv if not a.startswith('--cld-')]

    from repository import get_repository
    from application import PublishedApplication
    
    repository = get_repository()
    repository.add_records_from_file( options.cld )
    if options.list:
        for record in repository.get_records():
            print unicode( record )
        return
    if options.purge:
        records = list( repository.get_records() )
        for record in records:
            repository.purge( record )
        return
    else:
        exitcode = 10
        while exitcode==10:
            exitcode = 0
            counter = 0
            updated = True
            # add counter to prevent infinite loops in case of server error,
            # every fast internet check can take a second, so this counter
            # determines how long it can take to check for updates in case
            # of bad internet
            while updated and counter<3:
                updated = False
                counter = counter + 1
                record = repository.get_matching_record(options.author,
                                                        options.name,
                                                        options.branch,
                                                        options.revision)
                if options.update==True or record.update_before_launch:
                    try:
                        #
                        # First verify fast if there is an internet connection
                        #
                        if has_fast_internet():
                            updated, reason = repository.update( record )
                            LOGGER.info( reason )
                        else:
                            LOGGER.info( 'unable to update, because no fast connection' )
                    except Exception, e:
                        LOGGER.warn('could not update application', exc_info=e)
            published_application = PublishedApplication( record )
            if options.entry_point:
                entry_point = options.entry_point.split('/')
            else:
                entry_point = None
            exitcode = published_application.launch(options.branch, options.revision, entry_point)
        sys.exit( exitcode )

if __name__ == '__main__':
    freeze_support()
    try:
        main()
    except Exception,e:
        if win:
            popup_message(unicode(e))
        else:
            import traceback
            traceback.print_exc()
            
    sys.exit(0)