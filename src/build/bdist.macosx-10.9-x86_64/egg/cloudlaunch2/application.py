# -*- coding: utf-8 -*-
"""
Created on Thu Dec 23 12:29:57 2010

@author: tw55413
"""

import logging
import os
import sys
import tempfile
import copy
import shutil

LOGGER = logging.getLogger('cloudlaunch.application')

def _run_application(eggs, entry_point):
    """Run the application.
    :param eggs: a list of absolute paths to eggs that need to be put in the pythonpath
    :param entry_point: the entry point of the application, of type pkg_resources.EntryPoint
    :param egg_cache: the location in which to expand eggs
    """
    LOGGER.info('entered new process, loading entry point')
    sys.path = eggs + copy.copy(sys.path)
    method = entry_point.load(require=False)
    method()
                
class PublishedApplication(object):
    """An application that has been published as a .cloudlaunch file
    somewhere"""
    
    def __init__(self, cloudlaunch_record):
        """Construct a published application object from a .cloudlaunch file.
        
        :param cloudlaunch_record: the cloudlaunch_record that describes the applications,
        """
        self._cloudlaunch_record = cloudlaunch_record
                
    @property
    def author(self):
        return self._cloudlaunch_record.author
        
    @property
    def name(self):
        return self._cloudlaunch_record.name
        
    def launch(self, branch=None, revision=None, entry_point=None):
        """Launch a revision of the application.
        if None is specified, launch the latest revision available.
        :return: the exitcode of the application
        """
        LOGGER.info('launching %s %s'%(self.author, self.name))
        from pkg_resources import EntryPoint
        #
        # take a copy of sys.path before the launcher or the
        # launched program did any manipulation
        #
        reference_sys_path = copy.copy( sys.path )
        #
        # do all the needed imports before manipulating the path
        #
        from multiprocessing import Process

        if not entry_point:
            entry_point = entry_point or self._cloudlaunch_record.default_entry_point
        application_eggs = [os.path.abspath(os.path.join(self._cloudlaunch_record.dirname,egg[0].encode('utf-8'))) for egg in self._cloudlaunch_record.eggs]
            
        LOGGER.info('add to sys.path : %s'%(unicode(application_eggs)))
        LOGGER.info('entry point : %s'%entry_point)
        
        #
        # create a temporary directory to store expanded eggs, to prevent
        # the application from trying to expand files in a non writeable or locked
        # directory
        #
        egg_cache = tempfile.mkdtemp(prefix=u'egg-cache-')
        os.environ['PYTHON_EGG_CACHE'] = egg_cache
        LOGGER.info(u'expand eggs in %s'%egg_cache)
        
        found_entry_point = None
        for entry_point_description in self._cloudlaunch_record.entry_points[entry_point[0]]:
            parsed_entry_point = EntryPoint.parse( entry_point_description )
            if parsed_entry_point.name == entry_point[1]:
                found_entry_point = parsed_entry_point
        
        LOGGER.info('found entry point : %s'%unicode(found_entry_point))
        LOGGER.info('launching %s'%self.name)
        #
        # if console script, dont launch in separate process, to preserve standard
        # input
        #
        if entry_point[0] == 'console_scripts':
            LOGGER.info('run console script')
            exitcode = 0
            _run_application(application_eggs, found_entry_point)
        else:
            p = Process(target=_run_application, args=(application_eggs,
                                                       found_entry_point))
            p.start()
            p.join()
            #
            # restore the sys path
            #
            sys.path = reference_sys_path
            exitcode = p.exitcode
            LOGGER.info('exitcode: %s' % exitcode)
            # 
            # remove the egg cache
            #
            try:
                shutil.rmtree(egg_cache)
            except Exception, e:
                LOGGER.error('Could not remove egg cache', exc_info=e)
        return exitcode
