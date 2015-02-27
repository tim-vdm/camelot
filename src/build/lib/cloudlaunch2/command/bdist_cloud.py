# -*- coding: utf-8 -*-
"""
Created on Sun Dec 26 00:09:00 2010

@author: tw55413
"""

import base64
import datetime
import logging
import os

from setuptools.command.bdist_egg import bdist_egg
from distutils.sysconfig import get_python_version

LOGGER = logging.getLogger( 'cloudlaunch.command.bdist_cloud' )

class bdist_cloud(bdist_egg):
    
    user_options = bdist_egg.user_options + [
        ('cld-prefix=', 'p', "Prefix for the generated .cld file, but not for the one"
                             "that will be looked at for updates, this to enable the"
                             "building of different .cld files for the update process"
                             "and for the installer, use with care, as it might break"
                             "the update process"),
        ('eggs=', 'e', 'A list of eggs on which the application depends')
    ]
    
    def initialize_options(self):
        bdist_egg.initialize_options(self)
        self.dist_dir = os.path.join('dist', 'cloud')
        self.exclude_source_files = True
        self.certificate = None
        self.bucket = 'cloudlaunch'
        self.public_access_key = None
        self.public_secret_key = None
        self.default_entry_point = None
        self.branch = 'trunk'
        #
        # prefix for the generated .cld file, don't use this option if you
        # don't know what you're doing, since the update location of the app
        # will always be without the prefix
        #
        self.cld_prefix = ''
        self.revision = 0
        self.update_before_launch = True
        self.description = ''
        self.changes = []
        # list of additional paths to eggs to upload
        self.eggs = []
        self.timestamp = None
        self.configuration = None
        self.author = None
        self.name = None
        self.uuid = None

    def finalize_options(self):
        bdist_egg.finalize_options(self)
        if self.certificate:
            certificate = eval( base64.b64decode(''.join(self.certificate.split('\n'))) )
            self.public_access_key = certificate['public_access_key']
            self.public_secret_key = certificate['public_secret_key']
            self.bucket = certificate['bucket']
            self.author = certificate['author']
            self.name = certificate['name']
        if not self.bucket:
            raise Exception('A bucket or a certificate should be specified')
        if not self.public_access_key:
            LOGGER.warning( 'No public access key found, remote updates will not work')
        if not self.public_secret_key:
            LOGGER.warning( 'No public secret key found, remote updates will not work')
        if not self.default_entry_point:
            raise Exception('A default entry point is required')
        base, ext = os.path.splitext( self.egg_output )
        if not self.timestamp:
            self.timestamp = datetime.datetime.now()
            
    def run(self):
        self.run_command('egg_info')
        egg_info_command = self.get_finalized_command("egg_info")
        if not os.path.exists(self.egg_info):
            os.makedirs(self.egg_info)
        #
        # Analyze entry points
        #
        from pkg_resources import EntryPoint
        entry_point_map = EntryPoint.parse_map(self.distribution.entry_points or '')
        entry_point_group = entry_point_map.get(self.default_entry_point[0], None)
        if not entry_point_group:
            raise Exception('No entry point group %s found for default entry point'%self.default_entry_point[0])
        if not self.default_entry_point[1] in entry_point_group:
            raise Exception('No entry point %s found'%self.default_entry_point[1])
        #
        # Create a cloudrecord without egg checksum
        #
        from ..record import CloudRecord
        cloudlaunch_record = CloudRecord()
        cloudlaunch_record.bucket              = self.bucket
        cloudlaunch_record.public_access_key   = self.public_access_key
        cloudlaunch_record.public_secret_key   = self.public_secret_key
        cloudlaunch_record.author              = self.author or self.distribution.metadata.author
        cloudlaunch_record.name                = self.name or self.distribution.metadata.name
        cloudlaunch_record.author_email        = self.distribution.metadata.author_email
        cloudlaunch_record.url                 = self.distribution.metadata.url
        cloudlaunch_record.description         = self.distribution.metadata.description
        cloudlaunch_record.branch              = self.branch
        cloudlaunch_record.revision            = self.revision or self.distribution.metadata.version
        cloudlaunch_record.changes             = self.changes
        cloudlaunch_record.timestamp           = self.timestamp
        cloudlaunch_record.update              = '%s-%s.cld'%(self.distribution.metadata.name,
                                                       self.branch)
        cloudlaunch_record.default_entry_point = self.default_entry_point
        cloudlaunch_record.entry_points        = self.distribution.entry_points
        cloudlaunch_record.update_before_launch = self.update_before_launch
        cloudlaunch_record.eggs = [(os.path.basename(self.egg_output), None)]
        cloudlaunch_record.configuration       = self.configuration
        #
        # save in the egg info folder
        #
        cloud_egg_info = os.path.join(self.egg_info, 'cloudlaunch.cld')
        CloudRecord.write_records_to_file( [cloudlaunch_record], open( cloud_egg_info,
                                                                       'w' ) )
        
        egg_info_command.filelist.append( cloud_egg_info )
        #
        # create the egg
        #
        bdist_egg.run(self)
        #
        # add the eggs checksums to the record
        #
        cloudlaunch_record.eggs = [(os.path.basename(egg),
                                    CloudRecord.checksum(egg)) for egg in [self.egg_output] + self.eggs]
    
        cld_output = os.path.join( self.dist_dir, self.cld_prefix + cloudlaunch_record.update)
        fp = open( cld_output, 'w')
        CloudRecord.write_records_to_file( [cloudlaunch_record], fp )
        
        # Add to 'Distribution.dist_files' so that the "upload" command works
        getattr(self.distribution,'dist_files',[]).append(
            ('bdist_cloud',get_python_version(),cld_output))
