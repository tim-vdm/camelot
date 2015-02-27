# -*- coding: utf-8 -*-
"""
Created on Thu Dec 30 10:02:35 2010

@author: tw55413
"""
import logging
import os.path
import base64

from setuptools import Command
from distutils.errors import DistutilsOptionError

from ..record import CloudRecord
from ..functions import update_folder

LOGGER = logging.getLogger('upload_cloud')

class upload_cloud(Command):
  
    user_options = [
        ('certificate', 'b',
            "The cloud certificate"),
        ('private-access-key', 'b',
            "access key for write access to the bucket"),
        ('private-secret-key', 'b',
            "secret key for write access to the bucket"),
    ]
    
    def initialize_options(self):
        self.certificate = None
        self.private_access_key = None
        self.private_secret_key = None

    def finalize_options(self):
        if self.certificate:
            certificate = eval( base64.b64decode(''.join(self.certificate.split('\n'))) )
            self.private_access_key = certificate['private_access_key']
            self.private_secret_key = certificate['private_secret_key']
            self.author = certificate['author']
            self.name = certificate['name']
        if not self.private_access_key:
            raise Exception('A private access key or a certificate should be specified')
        if not self.private_secret_key:
            raise Exception('A private secret key or a certificate should be specified')
            
    def run(self):
        if not self.distribution.dist_files:
            raise DistutilsOptionError("No dist file created in earlier command")
        for command, pyversion, filename in self.distribution.dist_files:
            if command in ['bdist_cloud']:
                records = CloudRecord.read_records_from_file(filename)
                for record in records:
                    bucket_name = record.bucket
                    self.upload_file(bucket_name, filename, os.path.basename(filename) )
                    for egg, checksum in record.eggs:
                        self.upload_file(bucket_name,
                                         os.path.join(record.dirname, egg),
                                         egg)

    def upload_file(self, bucket_name, filename, key_name):
        LOGGER.info('upload %s to key %s'%(filename, key_name))
        from boto.s3 import connection
        from boto.s3 import bucket
        from boto.s3 import key
        full_key_name = '%s%s'%(update_folder(self.author, self.name), key_name )
        s3_connection = connection.S3Connection(self.private_access_key, 
                                                self.private_secret_key)
        s3_bucket = bucket.Bucket(s3_connection, bucket_name)
        s3_key = s3_bucket.get_key( full_key_name )
        if s3_key:
            if CloudRecord.checksum(filename) == s3_key.etag.strip('"'):
                LOGGER.info('key is allready up to data')
                return
        else:
            s3_key = key.Key(s3_bucket)
        s3_key.key = full_key_name
        s3_key.set_contents_from_filename( filename )
        LOGGER.info('key updated')
