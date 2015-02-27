import logging
import threading
import time

LOGGER = logging.getLogger('cloudlaunch.resources')

def get_cloud_record(module_name):
    """Get the Cloud Record that provides a module on the
    current sys.path
    
    :param module_name: the name of the module, egg 'camelot'
    :return: None of the record could not be identified, a CloudRecord
    otherwise
    
    The CloudRecord will be stored inside the egg, when the egg is
    constructed with the bdist_cloud command, and restored with this
    function.
    
    As this record is stored inside the egg, it's eggs list will have
    no checksum, since the checksum depends on the egg itself
    """
    from pkg_resources import get_provider
    from .record import CloudRecord
    provider = get_provider(module_name)
    if provider:
        record_json = provider.get_metadata('cloudlaunch.cld')
        if record_json:
            for record in CloudRecord.read_records_from_string(record_json):
                return record

def purge_records(module_name, delay=2*60):
    """
    Purge older records that provide a module on the current sys.path
    
    :param module_name: the name of the module, egg 'camelot'
    :param delay: how long to wait before the purging starts, defaults to 2
        minutes
    :return: None
    
    A new thread will be started to complete the purging process, so this 
    function returns immediately.
    """
    
    class PurgeThread( threading.Thread ):
        
        def run( self ):
            try:
                from .repository import get_repository
                record = get_cloud_record(module_name)
                repository = get_repository()
                if record and repository:
                    LOGGER.debug( 'wait before purging starts' )
                    time.sleep( delay )
                    LOGGER.info( 'start purging repository' )
                    repository.purge( record )
            except Exception, e:
                LOGGER.warn('could not purge repository', exc_info=e)
                
    t = PurgeThread()
    t.start()
