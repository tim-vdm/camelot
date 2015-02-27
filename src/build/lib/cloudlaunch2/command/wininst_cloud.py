# -*- coding: utf-8 -*-
"""
Created on Thu Dec 30 10:02:35 2010

@author: tw55413
"""
import logging
import base64
import sys
import os
import zipfile
import string

from distutils.errors import DistutilsOptionError
from distutils.sysconfig import get_python_version
from pkg_resources import resource_filename

LOGGER = logging.getLogger('wininst_cloud')

from .. import art
from ..record import CloudRecord
from ..functions import images_folder, get_appdata_folder
from download_cloud import download_cloud

inno_setup_template = string.Template("""
[Setup]
AppName=$name
AppVersion=$version
AppVerName=$name $version
DefaultDirName={pf}\\$name
DefaultGroupName=$name
OutputDir=.
; LicenseFile=..\\eula.txt
SetupIconFile=$setup_icon
AppPublisher=$author
AppId={{$uuid}

[Icons] 
Name: "{group}\\$name"; Filename: "{app}\\pythonw.exe"; Parameters: " -m cloudlaunch.main --cld-name ""$name"" --cld-author ""$author"" --cld-branch ""$branch"" "; WorkingDir: "{app}"
; Name: "{group}\\Update"; Filename: "{app}\\pythonw.exe"; Parameters: " -m cloudlaunch.main --cld-name ""$name"" --cld-author ""$author"" --cld-branch ""$branch"" " --cld-update"; WorkingDir: "{app}" 
Name: "{group}\\Uninstall"; Filename: "{uninstallexe}" 

[Files]
; python dist
Source: "$runtime_folder\\*"; DestDir: "{app}"; Flags: recursesubdirs; Excludes: "$excludes"
; egg and cld
Source: "$records_file"; DestDir: "{app}"; DestName: "default.cld"
; exe
Source: "$runtime_folder\\pythonw.exe"; DestDir: "{app}"; DestName: "pythonw.exe"
""")

class wininst_cloud( download_cloud ):
  
    user_options = [
        ('certificate', 'b',
            "The cloud certificate"),
        ('download-runtime', None, 
            "Download a runtime instead of using the python distribution that runs the script"),
        ('excludes', None,
            "The name of a file containing expressions of files and directories that dont need to be included with the binary distribution"),
    ]
    
    def initialize_options(self):
        self.certificate = None
        self.download_runtime = False
        self.excludes = None
        self.uuid = None

    def finalize_options(self):
        if self.certificate:
            certificate = eval( base64.b64decode(''.join(self.certificate.split('\n'))) )
            self.private_access_key = certificate['private_access_key']
            self.private_secret_key = certificate['private_secret_key']
            self.bucket = certificate['bucket']
            self.author = certificate['author']
            self.name = certificate['name']
                        
    def get_images_directory(self):
        """Return the base local CloudLaunch images directory"""
        if ('win' in sys.platform) and ('darwin' not in sys.platform):
            import winpaths
            ground_directory = os.path.join(winpaths.get_local_appdata(), 'cloudlaunch', 'images')
        else:
            ground_directory = os.path.join( os.path.expanduser('~'), '.cloudlaunch', 'images')
        if not os.path.exists( ground_directory ):
            os.makedirs( ground_directory )
        return ground_directory

    def get_runtime_folder(self, runtime_name):
        runtime_folder = os.path.join( get_appdata_folder(), 'runtime', runtime_name )
        if not os.path.exists( runtime_folder ):
            os.makedirs( runtime_folder )
        return runtime_folder
    
    def run(self):
        
        runtime_name = 'python-sdk-win32-2011-8-30'
        
        # 
        # download a runtime to start with 
        #
        if self.download_runtime:
            images_directory = self.get_images_directory()
            LOGGER.info('look for images in bucket')
            s3_bucket = self.get_bucket()
            runtime_found = False
            for key in s3_bucket.list( images_folder() ):
                if key.name.endswith( runtime_name + '.zip' ):
                    LOGGER.info( 'found runtime %s'%key.name )
                    self.download_key( key, images_directory )
                    runtime_found = True
            if not runtime_found:
                raise Exception( 'Unable to download runtime' )
            #
            # extract the runtime to disk
            #
            runtime_folder = self.get_runtime_folder( runtime_name )
            if not len( os.listdir( runtime_folder ) ):
                LOGGER.info('extracting runtime, do not interupt')
                runtime_zip = zipfile.ZipFile( os.path.join(images_directory, runtime_name+'.zip') )
                runtime_zip.extractall( runtime_folder )
        else:
            runtime_folder = os.path.dirname( sys.executable )
        #
        # Create the inno installer file
        #
        if not self.distribution.dist_files:
            raise DistutilsOptionError("No dist file created in earlier command")
        for command, pyversion, filename in self.distribution.dist_files:
            if command in ['bdist_cloud']:
                self.create_installer( runtime_folder, filename )                    
                    
    def create_installer( self, runtime_folder, records_file ):
        records = list( CloudRecord.read_records_from_file(records_file) )
        if not len( records ):
            raise Exception( 'no records found in %s'%records_file )
        record = records[0]
        exclude_lines = []
        #
        # Add the default excludes
        #
        excludes_filename = resource_filename( art.__name__, 'excludes.txt' )
        exclude_lines.extend( open(excludes_filename).readlines() )
        #
        # Add specific excludes
        #
        if self.excludes:
            exclude_lines.extend( open(self.excludes).readlines() )
        excludes = ",".join(filter(lambda l: len(l), map(lambda l: l.strip(" \t\r\n"), exclude_lines)))
        installer_filename = os.path.splitext( records_file )[0] + '.iss'
        installer_file = open( installer_filename, "w")
        LOGGER.info('write installer file to %s'%installer_filename)
        context = dict(
            uuid = self.uuid,
            name = record.name,
            revision = record.revision,
            author = record.author,
            branch = record.branch,
            version = self.distribution.metadata.version,
            setup_icon = resource_filename( art.__name__, 'setup.ico'),
            runtime_folder = runtime_folder,
            excludes = excludes,
            records_file = os.path.abspath( records_file ), 
        )
        installer_file.write( inno_setup_template.substitute( context ) )
        for egg, _checksum in record.eggs:
            installer_file.write( 'Source: "%s"; DestDir: "{app}"; DestName: "%s"'%( os.path.abspath( os.path.join( record.dirname, egg) ), egg ) )
        installer_file.close()
        getattr(self.distribution,'dist_files',[]).append(
            ('wininst_cloud',get_python_version(),installer_filename))
