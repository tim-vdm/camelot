"""
Helper classes to implement parts of the logic as processes that can be
executed in parallel.

The functions of the standard library (Pool, ProcessPoolExecutor) are not used
because, atm, they have no way of dealing with an expensive initialization process
on a node.  In this case, this includes, setting up connection with the DB, setting
up the ORM and the caching that takes place in a visitor.
"""

import itertools
import logging
import multiprocessing
import os
import sys
import tblib
import pickle

from camelot.core.sql import metadata
from camelot.core.conf import settings

from ..model.bank.settings import SettingsProxy
from ..connector.accounting import AccountingSingleton, DocumentNumbers

LOGGER = logging.getLogger('vfinance.process')

class StopWorking(object):
    """Signal a worker that it should stop working"""
    pass

class WorkerPool(object):
    """
    Create a pool of workers to submit work.
    
    :param worker_factory: callable that creates a new subclass of
    :class:`WorkerProcess`
    
    :param args: arguments to be used to call the `worker_factory`
    
    :param kwargs: keyword arguments to be used to call the `worker_factory`
    """

    def __init__(self, worker_factory, *args, **kwargs):
        max_workers = int(settings.get('VFINANCE_MAX_WORKERS', '2'))
        max_workers = min(max_workers, multiprocessing.cpu_count())
        self.manager = multiprocessing.Manager()
        last_document_numbers = self.manager.dict()
        document_numbers_lock = self.manager.RLock()
        self.document_numbers = DocumentNumbers(last_document_numbers, document_numbers_lock)
        self.workers = []
        for _i in range(max_workers):
            self.workers.append(worker_factory(*args, document_numbers = self.document_numbers, **kwargs))

    def submit(self, work_iterator):
        """
        An iterator over all the work that needs to be submitted to
        the workers.
        
        :result: an interator over all the results
        """
        worker_keys = itertools.cycle(range(len(self.workers)))
        result_iterators = []
        for work, worker_key in itertools.izip(work_iterator,
                                               worker_keys):
            # iterate over the results each time all workers have received work
            if worker_key == 0:
                for result in itertools.chain.from_iterable(result_iterators):
                    yield result
                result_iterators = []
            worker = self.workers[worker_key]
            result_iterators.append(worker.send_work(work))
        # iterate over the remaining results
        for result in itertools.chain.from_iterable(result_iterators):
            yield result

    def __len__(self):
        return len(self.workers)

    def __enter__(self):
        #
        # Dispose the existing database connections before spawning new
        # processes.  Since they might no longer work after the spawning
        #
        # http://www.postgresql.org/docs/current/static/libpq-connect.html#LIBPQ-CONNECT
        #
        # This is not perfect though, since connections that are not in the pool
        # are not disposed by this call
        #
        metadata.bind.dispose()
        for worker in self.workers:
            worker.start()
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        for worker in self.workers:
            worker.stop()
        for worker in self.workers:
            worker.join()

class WorkerProcess(multiprocessing.Process):
    """
    A process that configures its connection to the database and sets up its
    ORM before executing the business logic.

    To connect to the database, the profile of the parent process is send to the
    child process.

    Next the :meth:`send_work` generator can be called to send work to the process.
    """

    def __init__(self, profile=None, document_numbers=None):
        super(WorkerProcess, self).__init__()
        self.profile = profile or settings.profile
        self._stopped = True
        self._parent_end, self._worker_end = multiprocessing.Pipe()
        self._result_queue = multiprocessing.Queue(100)
        self.parent_pid = os.getpid()
        self._document_numbers = pickle.dumps(document_numbers)

    def configure(self):
        """
        Configures the database and the ORM
        """
        # recycle the database connection every minute, in case something
        # goes wrong
        settings.append(SettingsProxy(self.profile))
        metadata.bind = settings.ENGINE(pool_recycle=60)
        settings.setup_model()
        settings.load()
        document_numbers = pickle.loads(self._document_numbers)
        AccountingSingleton.set_document_numbers(document_numbers)

    def dispose(self):
        """
        Close checked in database connections
        """
        LOGGER.debug('dispose connections from %s'%(self.pid))
        metadata.bind.dispose()

    def run(self):
        """
        Call the configure method, then the initialize method and and start
        handling the work
        """
        self.configure()
        self.initialize()
        while True:
            try:
                work = self._receive_work()
            # EOFError will be raised if the pipe has been closed by the parent
            except EOFError:
                break
            if isinstance(work, StopWorking):
                break
            try:
                for result in self.handle_work(work):
                    self._send_result(result)
                self._send_result(StopIteration())
            except Exception, e:
                LOGGER.error('Unhandled exception in worker process', exc_info=e)
                self._send_result(Exception("Unhandled {0} in worker process".format(type(e).__name__)))
                import traceback
                traceback.print_exc()
            except:
                self._send_result(Exception("Unhandled event in worker process"))
        self.dispose()

    def initialize(self):
        """
        Overwrite this method to acquire long term resources needed to perform the
        work
        """
        pass

    def handle_work(self, work):
        """
        This generator is called in the worker process when work has been send to the
        worker.  Implement this generator to make a worker do something usefull.
        
        The default implementation yields the work
        """
        yield work

    def _validate_parent(self):
        if not self.is_alive():
            raise Exception('Worker is not alive an cannot communicate')
        if self.parent_pid != os.getpid():
            raise Exception('Only the parent can communicate with the worker')

    def send_work(self, work):
        """
        Send an object to the worker process
        """
        if not self._stopped:
            raise Exception('Cannot send work to worker while worker still busy')
        self._validate_parent()
        LOGGER.debug('waiting to send work to %s'%(self.pid))
        self._parent_end.send(work)
        self._stopped = False
        LOGGER.debug('work send to %s'%(self.pid))
        return self

    def __iter__(self):
        return self

    def next(self):
        if self._stopped:
            raise StopIteration
        LOGGER.debug('waiting for result from {0.pid}'.format(self))
        result = self._receive_result()
        if isinstance(result, StopIteration):
            self._stopped = True
            raise StopIteration
        elif isinstance(result, Exception):
            raise result
        return result

    def stop(self):
        """
        Request the worker to finish its ongoing work and stop
        """
        self._parent_end.send(StopWorking())
        self._parent_end.close()

    def _receive_work(self):
        """
        Receive work to be done by the worker
        """
        if self.pid != os.getpid():
            raise Exception('only the worker can receive work')
        if not self.is_alive():
            raise Exception('Worker is not alive, and cannot send results')
        return self._worker_end.recv()

    def _send_result(self, result):
        """
        Send result of work back to the parent
        """
        if self.pid != os.getpid():
            raise Exception('only the worker can send results')
        try:
            self._result_queue.put(result)
        except pickle.PickleError:
            rtype = type(result)
            LOGGER.fatal('Could not send result of type {0} to parent'.format(rtype))
            LOGGER.error('Result value : {0}'.format(unicode(result)))
            raise

    def _receive_result(self):
        self._validate_parent()
        return self._result_queue.get()

class WorkerProcessException(object):
    """To be yielded when an exception takes place during a workerprocess.
    This object stores information of the exception for reuse"""

    def __init__( self, message ):
        self.message = message
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        self.exc_info = (exc_type, exc_value, tblib.Traceback(exc_traceback))

class Progress(unicode):
    pass
