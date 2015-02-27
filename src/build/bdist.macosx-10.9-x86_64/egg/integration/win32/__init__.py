#
# Don't import anything here, since an import might generate output, and this
# file get's imported before output is redirected
#


#
# store all files in a temporary folder
#
_temp_folders_ = dict()

def popup_message(message):
    """Use windows script host to popup a message"""
    import win32com.client
    shell = win32com.client.Dispatch("WScript.Shell")
    shell.Popup(unicode(message))
      
def popup_exception(exception):
    """Show a popup message with exception information"""
    import traceback, cStringIO
    sio = cStringIO.StringIO()
    traceback.print_exc(file=sio)
    traceback_print = sio.getvalue()
    sio.close()
    popup_message(unicode(exception) + '\n' + traceback_print)

def get_app_folder(name):
    """Get a folder with guaranteed write permissions"""
    import sys
    import os
    if sys.platform.startswith('win'):
        import winpaths
        apps_folder = winpaths.get_local_appdata()
    else:
        from PyQt4.QtGui import QDesktopServices
        apps_folder = unicode(QDesktopServices.storageLocation(QDesktopServices.DataLocation), errors='ignore')
    return os.path.join(apps_folder, name)
    
def get_temp_folder(prefix):
    """Get a temporary folder with a certain prefix, multiple calls
    to this method, with the same prefix will return the same temp
    folder.
    :return: the name of the temporary folder, or None if no writeable
    temporary folder could be made."""
    import tempfile
    import datetime
    
    global _temp_folders_
    
    if prefix not in _temp_folders_:
        now = datetime.datetime.now()
        try:
            _temp_folders_[prefix] = tempfile.mkdtemp(u'%s_%s'%(prefix, now.strftime('%Y_%m_%d_%H_%M')))
        except Exception, e:
            #
            # As a last resort, try to use win32 com that there will be no logging,
            # and then continue
            #
            popup_exception(e)
            _temp_folders_[prefix] = None
        
    return _temp_folders_.get(prefix, None)
    
    
def setup_secure_output(prefix):
    """Write all output to a black hole, to prevent windows popups"""
    import sys
    import os

    temp_folder = get_temp_folder(prefix)

    class Blackhole(object):
        softspace = 0
        def write(self, text):
            pass
        def flush(self):
            pass
            
    if temp_folder:
        sys.stdout = open( os.path.join(temp_folder, u'stdout.txt'), 'wb' )
        sys.stderr = open( os.path.join(temp_folder, u'stderr.txt'), 'wb' )
    else:         
        sys.stdout = Blackhole()
        sys.stderr = Blackhole()    
    
def setup_secure_logging(prefix):
    """Setup logging to write logs into a temp directory.  This function
    well generate no output and won't throw exceptions when if fails, instead
    it will popup a dialog
    """
    #
    # Initialization of logging might fail big time on Vista like systems
    #
    import logging
    import logging.handlers
    import getpass
    import os
    import sys
    
    temp_folder = get_temp_folder(prefix)
    if temp_folder:
        try:
            
            level = logging.INFO
            for arg in sys.argv:
                if '--debug' in arg:
                    level = logging.DEBUG
                    popup_message('Running in debug mode')
                
            user = getpass.getuser()
            handler = logging.handlers.TimedRotatingFileHandler(os.path.join(get_temp_folder(prefix), 
                                                                u'logs-%s.txt'%unicode(user, errors='ignore')), 
                                                                when='D',
                                                                encoding='UTF-8' )
            formatter = logging.Formatter('[%(asctime)s] [%(levelname)-5s] [%(name)-35s] - %(message)s')
            handler.setFormatter(formatter)
            logging.root.addHandler(handler)
            logging.root.setLevel(level)
            logger = logging.getLogger('integration.win32.setup_secure_logging')
            logger.info('secure logging has been set up')
        except Exception, e:
            popup_exception(e)
    
def setup_gencache():
    """ make sure gencache can be used, even in a py2exe environment
    after http://www.py2exe.org/index.cgi/UsingEnsureDispatch"""
    return
    import sys
    import os
    if not 'win' in sys.platform:
        return
    import logging
    logger = logging.getLogger('integration.win32.setup_gencache')
    import win32com
    import win32com.client
    gen_path = win32com.__gen_path__
    logger.info(u'gencache is stored in %s'%unicode(gen_path))
    if gen_path:
        #
        # let's try to remove the cached dictionary, since the user might have
        # upgraded its applications and constants may not be constants any more
        #
        dicts_path = os.path.join(gen_path, 'dicts.dat')
        if os.path.exists(dicts_path):
            try:
                os.remove(dicts_path)
                logger.info('removed existing dicts.dat')
            except Exception, e:
                logger.error('could not remove dicts.dat', exc_info=e)
            except:
                logger.error('unhandled exception while removing dicts')
        else:
            logger.info('no dicts file found, maybe this is a first run')
    if win32com.client.gencache.is_readonly == True:
        logger.info('gencache is readonly')
        #allow gencache to create the cached wrapper objects
        win32com.client.gencache.is_readonly = False
        
        # under p2exe the call in gencache to __init__() does not happen
        # so we use Rebuild() to force the creation of the gen_py folder
        win32com.client.gencache.Rebuild()
        
        # NB You must ensure that the python...\win32com.client.gen_py dir does not exist
        # to allow creation of the cache in %temp%

def clear_matplotlib_fontcache(app_folder):
    import os
    import sys
    import hashlib
    import shutil
    md5 = hashlib.md5()
    md5.update(os.path.dirname(__file__))
    
    cache_path = os.path.join(app_folder, md5.hexdigest()[:16])
    if os.path.isdir(cache_path):
        shutil.rmtree(cache_path)
    os.makedirs(cache_path)
    os.environ['MPLCONFIGDIR'] = cache_path.encode(sys.getfilesystemencoding())
