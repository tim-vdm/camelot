#-*- coding: utf-8 -*-
"""
Created on Thu Dec 23 21:08:56 2010

@author: tw55413
"""

import os
import logging
import datetime

LOGGER = logging.getLogger('cloudlaunch.record')

from functions import update_folder, get_connection_kwargs

class CloudRecord(object):
    """A cloud record
    
    Describes an application and the instructions to run and
    update the application.
    
    A record can be serialized and deserialized to and from JSON.
    
    Records can be read from the file system or from urls.
    """
    	
    @classmethod
    def write_records_to_file(cls, records, fp):
        """:param records: a list of CloudRecord
           :param fp: a file pointer
        """
        import json
        json_records = []
        for record in records:
            json_records.append( dict(
                cld_format = 1,
                public_access_key = record.public_access_key,
                public_secret_key = record.public_secret_key,
                bucket = record.bucket,
                author = record.author,
                name = record.name,
                update_before_launch = record.update_before_launch,
                branch = record.branch,
                revision = record.revision,
                update = record.update,             
                force_update = record.force_update,
                default_entry_point = record.default_entry_point,
                entry_points = record.entry_points,
                timestamp = tuple(getattr(record.timestamp, attr) for attr in ['year', 
                                                                               'month', 
                                                                               'day', 
                                                                               'hour', 
                                                                               'minute',
                                                                               'second']),

                eggs = record.eggs,
                configuration = record.configuration,
            ) )
        json.dump( json_records, fp, indent=1)

    @classmethod
    def read_records_from_string(cls, cloudlaunch_string, dirname = None):
        """
        :param cloudlaunch_string: a string containing json cloud records
        :param dirname: the local directory where to look for the eggs defined in the record,
        None if those eggs are not stored local
        :return: a generator of Record objects
        """
        import json
        json_records = json.loads( cloudlaunch_string )
        for json_record in json_records:
            cloudlaunch_record = cls()
            for key,value in json_record.items():
                if key=='timestamp':
                    cloudlaunch_record.timestamp = datetime.datetime(*value)
                elif hasattr(cloudlaunch_record, key):
                    setattr(cloudlaunch_record, key, value)
            cloudlaunch_record.dirname = dirname
            yield cloudlaunch_record
                
    @classmethod
    def read_records_from_file(cls, cloudlaunch_file):
        """
        :param cloudlaunch_file: a filename containing cloud records
        :return: a generator of Record objects
        """
        try:
            dirname = os.path.dirname( cloudlaunch_file.encode('utf-8') )
        except Exception, e:
            dirname = os.path.dirname( cloudlaunch_file )
            LOGGER.debug('Could not encode file name: {0}'.format(e))
        for record in cls.read_records_from_string( open(cloudlaunch_file).read(), dirname):
            yield record
        
    @staticmethod
    def checksum(filename):
        """:param filename: the full path of the file to be checksummed
        """
        import hashlib
        return hashlib.md5(file(filename, 'rb').read()).hexdigest()
    
    @staticmethod
    def sort_records(record_list):
        """Sort records so that the most recent record comes first
        :param record_list: a list of records
        """
        zero = datetime.datetime(1970,1,1)
        record_list.sort( key = lambda record:record.timestamp or zero, reverse=True )
        
    def __init__(self):
        self.public_access_key = None,
        self.public_secret_key = None,
        self.update_before_launch = True,
        self.force_update = False
        self.author = None
        self.name = None
        self.branch = None
        self.revision = 0
        self.update = None # the name of the key containing updated records
        self.eggs = []        
        self.modules = []
        self.bucket = None
        self.default_entry_point = None
        self.entry_points = []
        self.dirname = None
        self.description = None
        self.changes = []
        self.timestamp = None
        self.configuration = {}

    def __unicode__(self):
        return '%15s %15s %15s %15s %15s'%(self.author, self.name, self.branch, self.revision, self.timestamp)
        
    def get_connection(self):
        """
        :return: an S3 connection with the credentials of this record
        """
        from boto.s3 import connection
        kwargs = get_connection_kwargs()
        s3_connection = connection.S3Connection(self.public_access_key, 
                                                self.public_secret_key,
                                                **kwargs)
        return s3_connection
        
    def get_bucket(self):
        """
        :return: the S3 bucket of this record
        """
        from boto.s3 import bucket
        return bucket.Bucket(self.get_connection(), self.bucket)    
 
    def matches(self, 
                author=None,
                name=None, 
                branch=None,
                revision=None):
        """:return: True if record matches criteria, False otherwise"""
        if author and self.author!=author:
            return False
        if name and self.name!=name:
            return False
        if branch and self.branch!=branch:
            return False
        if revision and self.revision!=revision:
            return False
        return True       
               
    def has_update( self ):
        """Verify if updates are available for this record
        :return: a cloudlaunch record that points to the updated record
        if available, None otherwise
        """
        LOGGER.info('check for update of %s'%unicode(self))
        if self.update and self.bucket:
            bucket = self.get_bucket()
            update_key_name = '%s%s'%(update_folder(self.author, self.name), self.update)
            LOGGER.info('look for updated record %s'%update_key_name)
            update_key = bucket.get_key( update_key_name )
            if update_key:
                LOGGER.info('update key available')
                remote_json_records = update_key.get_contents_as_string()
                remote_records = list( self.read_records_from_string( remote_json_records ) )
                LOGGER.info('read %i remote records'%len(remote_records))
                matching_records = [r for r in remote_records if r.matches(self.author,
                                                                           self.name,
                                                                           self.branch)]
                LOGGER.info('%i records match'%len(matching_records))
                matching_records.append( self )
                self.sort_records( matching_records )
                LOGGER.info('most recent record %s'%matching_records[0].timestamp)
                if matching_records[0] != self and matching_records[0].timestamp != self.timestamp:
                    return matching_records[0]
            
    def verify_integrity(self):
        """Verify the integrity of the cloudlaunch record.  That is, the eggs it points to
        are available and their checksum is correct.
        
        :return: (boolean, string)
        the returned boolean indicates wether the record is valid or not,
        the string indicates the reason for the record not being valid
        """
        import time
        for filename, checksum in self.eggs:
            # dont know what the encoding of dirname is, filename is read from the
            # json
            egg_path = os.path.join(self.dirname, filename)
            if not os.path.exists( egg_path ):
                return False, u'%s does not exist'%egg_path
            if not checksum:
                return True
            #
            # validate the checksum multiple times, since the first time we
            # open the file, the file might not yet be ready
            #
            i = 5
            valid = False
            while i > 0:
                if checksum == self.checksum( egg_path ):
                    valid = True
                    break
                else:
                    time.sleep(.2)
                i = i - 1
            if not valid:
                return False, u'The checksum of %s is invalid : %s expected, got %s'%(egg_path, 
                                                                                      checksum,
                                                                                      self.checksum( egg_path ))
        return True, u''
