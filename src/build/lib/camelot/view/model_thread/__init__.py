#  ============================================================================
#
#  Copyright (C) 2007-2013 Conceptive Engineering bvba. All rights reserved.
#  www.conceptive.be / info@conceptive.be
#
#  This file is part of the Camelot Library.
#
#  This file may be used under the terms of the GNU General Public
#  License version 2.0 as published by the Free Software Foundation
#  and appearing in the file license.txt included in the packaging of
#  this file.  Please review this information to ensure GNU
#  General Public Licensing requirements will be met.
#
#  If you are unsure which license is appropriate for your use, please
#  visit www.python-camelot.com or contact info@conceptive.be
#
#  This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
#  WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#
#  For use of this library in commercial applications, please contact
#  info@conceptive.be
#
#  ============================================================================

import logging

from ...core.qt import QtCore

logger = logging.getLogger('camelot.view.model_thread')

_model_thread_ = []

# this might be set to False, for unittesting purpose
verify_threads = True

class ModelThreadException(Exception):
    pass

def object_thread( self ):
    """Funtion to verify if a call to an object is made in the thread of this
    object, to be used in assert statements.  Example ::
    
        class FooObject( QtCore.QObject ):
        
            def do_something( self ):
                assert object_thread( self )
                print 'safe method call'
    
    :param self: a :class:`QtCore.QObject` instance.
    :return True: if the thread of self is the current thread 
    
    The approach with assert statements is prefered over decorators,
    since decorators hide part of the method signature from the sphinx
    documentation.
    """
    return self.thread() == QtCore.QThread.currentThread()

class AbstractModelThread(QtCore.QThread):
    """Abstract implementation of a model thread class
    Thread in which the model runs, all requests to the model should be
    posted to the the model thread.

    This class ensures the gui thread doesn't block when the model needs
    time to complete tasks by providing asynchronous communication between
    the model thread and the gui thread
    
    The Model thread class provides a number of signals :
    
    *thread_busy_signal*
    
    indicates if the model thread is working in the background
    
    *setup_exception_signal*
    
    this signal is emitted when there was an exception setting up the model
    thread, eg no connection to the database could be made.  this exception
    is mostly fatal for the application.
    """

    thread_busy_signal = QtCore.qt_signal(bool)
    setup_exception_signal = QtCore.qt_signal(object)

    def __init__(self):
        super(AbstractModelThread, self).__init__()
        self.logger = logging.getLogger(logger.name + '.%s' % id(self))
        self._exit = False
        self._traceback = ''
        self.logger.debug('model thread constructed')

    def run(self):
        pass

    def traceback(self):
        """The formatted traceback of the last exception in the model thread"""
        return self._traceback

    def wait_on_work(self):
        """Wait for all work to be finished, this function should only be used
    to do unit testing and such, since it will block the calling thread until
    all work is done"""
        pass

    def post(self, request, response=None, exception=None, args=()):
        """Post a request to the model thread, request should be a function
        that takes no arguments. The request function will be called within the
        model thread. When the request is finished, on first occasion, the
        response function will be called within the gui thread. The response
        function takes as arguments, the results of the request function.

        :param request: function to be called within the model thread
        :param response: a slot that will be called with the result of the
        request function
        :param exception: a slot that will be called in case request throws an
        exception
        :param args: arguments with which the request function will be called        
        """
        raise NotImplemented

    def busy(self):
        """Return True or False indicating wether either the model or the gui
        thread is doing something"""
        return False
    
    def stop(self):
        """Stop the model thread from accepting any further posts.
        """
        return True

def has_model_thread():
    return len(_model_thread_) > 0

def get_model_thread():
    try:
        return _model_thread_[0]
    except IndexError:
        from .signal_slot_model_thread import SignalSlotModelThread
        _model_thread_.insert(0, SignalSlotModelThread())
        _model_thread_[0].start()
        return _model_thread_[0]

def post(request, response=None, exception=None, args=()):
    """Post a request and a response to the default model thread"""
    mt = get_model_thread()
    mt.post(request, response, exception, args)


