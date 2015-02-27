# -*- coding: utf-8 -*-
"""
Created on Fri Dec 24 10:42:55 2010

@author: tw55413
"""

import logging
import os
import sys
import shutil

from record import CloudRecord
from functions import update_folder

_repository_ = None

LOGGER = logging.getLogger('cloudlaunch.repository')

def get_repository():
    """Get access to the singleton ground repository
    :return: a GroundRepository    
    """
    global _repository_
    if not _repository_:
        _repository_ = GroundRepository()
    return _repository_

class GroundRepository(object):
    """Represents a collection of cloud records and their associated
    eggs that are available to the launcher on the ground.

    These records are either stored as application data, or pointed
    to by the user.
    """
    
    def __init__(self):
        self._record_files = []
        
    def get_ground_directory(self):
        """Return the base local CloudLaunch repository directory"""
        if ('win' in sys.platform) and ('darwin' not in sys.platform):
            import winpaths
            ground_directory = os.path.join( winpaths.get_local_appdata(), 'cloudlaunch', 'repository' )
        else:
            ground_directory = os.path.join( os.path.expanduser('~'), '.cloudlaunch', 'repository' )
        if not os.path.exists( ground_directory ):
            os.makedirs( ground_directory )
        return ground_directory
        
    def add_records_from_file(self, filename):
        """Add cloudlaunch records from a filename
        :param filename: the full path of the file        
        """
        self._record_files.append( filename )
        
    def get_record_files(self):
        import re
        expression = re.compile(".*.cld$", re.DOTALL) 
        for record_file in self._record_files:
            yield record_file
        for path, _dirs, files in os.walk( self.get_ground_directory() ):
            for file in files:
                if expression.match(file):
                    yield os.path.join( path, file )
                
    def get_records(self):
        """
        :return: a generator over all available cloudlaunch records
        """
        #
        # Yield the records of the files that were specified
        #
        for record_file in self.get_record_files():
            try:
                for record in CloudRecord.read_records_from_file(record_file):
                    yield record
            except Exception, exc:
                LOGGER.warn( 'Could not read cloudlaunch records from %s'%record_file, exc_info=exc )
                
    def get_remote_key( self, s3_bucket, key_name ):
        """Return the contens of a remote key, None if no such key exists"""
        from boto.s3 import key
        s3_key = key.Key(s3_bucket)
        s3_key.key = key_name
        if s3_key.exists():
            return s3_key.get_contents_as_string()
        
    def purge( self, record ):
        """Look for older versions of this record and remove them from the
        repository, to free disk space. Always keep 1 older version for backup
        purposes.
        
        :param record: the cloudlaunch record for which to purge
        """
        ground_directory = self.get_ground_directory()
        
        def filter_record( r ):
            if not r.matches( record.author, record.name, record.branch ):
                return False            
            # don't remove records that have no timestamp
            if not r.timestamp:
                return False
            # don't remove records that are in the cloud
            if not r.dirname:
                return False
            # don't remove records that are not in this repository
            if not r.dirname.startswith( ground_directory ):
                return False
            return r.timestamp < record.timestamp
        
        matching_records = [r for r in self.get_records() if filter_record( r )]
        CloudRecord.sort_records( matching_records )
        LOGGER.info( '%s records match purge criteria'%len( matching_records ) )
        for r in matching_records[1:]:
            if os.path.exists( r.dirname ):
                LOGGER.info( 'remove %s'%r.dirname )
                shutil.rmtree( r.dirname )
        
    def update( self, record ):
        """Download available updates for the record.
        :param record: the cloudlaunch record for which to download updates
        :return: (success, reason) a tuple where success indicates if the download
        succeeded, and reason is text string specifying what happened
        """
        import tempfile
        remote_record = record.has_update()
        if remote_record:
            LOGGER.info('update available')
            dirname = []
            
            def get_dirname():
                """create a directory to store the new record, only if 
                really needed, to avoid clutter on the filesystem"""
                if not dirname:
                    #
                    # We should not take dirnames that are too long, or they might
                    # fail on XP boxes
                    #
                    dirname.append( tempfile.mkdtemp(dir=self.get_ground_directory()) )
                return dirname[0]
            
            LOGGER.info('storing update in %s'%dirname)
            #
            # first write the eggs, only if that was successfull, write the record itself, to
            # avoid unnecessary checks
            #
            bucket = remote_record.get_bucket()
            for egg, checksum in remote_record.eggs:
                egg_key = bucket.get_key('%s%s'%(update_folder(remote_record.author, remote_record.name), egg))
                if not egg_key:
                    return False, 'repository has no such key %s, cancel update'%egg_key
                remote_checksum = egg_key.etag.strip('"')
                if remote_checksum != checksum:
                    return False, 'bucket contains invalid egg : %s expected, got %s, cancel update'%(checksum, remote_checksum)
                egg_key.get_contents_to_filename( os.path.join(get_dirname(), egg) )
            CloudRecord.write_records_to_file([remote_record], open(os.path.join(get_dirname(), remote_record.update), 'w' ))
            return True, 'update succeeded'
        return False, 'No update available'

    def get_matching_record(self,
                            author=None,
                            name=None, 
                            branch=None,
                            revision=None):
        matching_records = []
        for record in self.get_records():
            if record.matches(author, name, branch, revision):
                matching_records.append( record )
        CloudRecord.sort_records( matching_records )
        
        for record in matching_records:
            integrity, reason = record.verify_integrity()
            if integrity:
                return record
            else:
                LOGGER.warn(u'invalid record : %s'%reason)
                        
        raise Exception('No record found matching branch %s and revision %s'%(branch, revision))
