# -*- coding: utf-8 -*-
"""
Created on Thu Dec 30 10:02:35 2010

@author: tw55413
"""
import logging
import os.path
import base64

from setuptools import Command

from ..record import CloudRecord
from ..functions import update_folder, egg_key

LOGGER = logging.getLogger('download_cloud')

class download_cloud(Command):
  
    user_options = [
        ('certificate', 'b',
            "The cloud certificate"),
    ]
    
    def initialize_options(self):
        self.certificate = None

    def finalize_options(self):
        if self.certificate:
            certificate = eval( base64.b64decode(''.join(self.certificate.split('\n'))) )
            self.private_access_key = certificate['private_access_key']
            self.private_secret_key = certificate['private_secret_key']
            self.bucket = certificate['bucket']
            self.author = certificate['author']
            self.name = certificate['name']
                        
    def get_bucket(self):
        from boto.s3 import connection
        from boto.s3 import bucket
        s3_connection = connection.S3Connection(self.private_access_key, 
                                                self.private_secret_key)
        s3_bucket = bucket.Bucket(s3_connection, self.bucket )
        return s3_bucket

    def run(self):
        LOGGER.info('look for cloud records in bucket')
        s3_bucket = self.get_bucket()
        download_folder = os.path.join( 'dist', 'cloud' )
        for key in s3_bucket.list( update_folder( self.author, self.name ) ):
            if key.name.endswith('.cld'):
                LOGGER.info( 'found key %s'%key.name )
                self.download_key( key, download_folder )
                remote_json_records = key.get_contents_as_string()
                remote_records = list( CloudRecord.read_records_from_string( remote_json_records ) )
                for record in remote_records:
                    for egg_name, md5 in record.eggs:
                        self.download_key( egg_key(s3_bucket, self.author, self.name, egg_name ), download_folder )

    def download_key(self, key, download_folder):
        LOGGER.info('download key %s'%(key.name))
        if not os.path.exists( download_folder ):
            os.makedirs( download_folder )
        filename = os.path.join( download_folder, key.name.split('/')[-1])
        if os.path.exists( filename ) and CloudRecord.checksum(filename) == key.etag.strip('"'):
            LOGGER.info('key is already downloaded')
        else:
            key.get_contents_to_filename( filename )

