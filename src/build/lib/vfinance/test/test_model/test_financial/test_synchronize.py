import pickle
import unittest

from camelot.core.orm import Session

from vfinance.model.financial.synchronize import ( FinancialSynchronizer,
                                                   SynchronizationException,
                                                   SynchronizerOptions,
                                                   ordered_options )

class RaisingSynchronizer( FinancialSynchronizer ):
    
    def read_account_entries(self):
        try:
            raise Exception()
        except:
            pass
        yield SynchronizationException( 'could not read entries' )

class SynchronizeCase( unittest.TestCase ):
    
    def setUp( self ):
        session = Session()
        session.expunge_all()
        self.options = SynchronizerOptions()
        for option in ordered_options:
            setattr( self.options, option, False )
        self.options.read_account_entries = True
        self.previous_job = self.get_last_batch_job()

    def get_last_batch_job( self ):
        from camelot.model.batch_job import BatchJob
        session = Session()
        session.expire_all()
        return session.query( BatchJob ).order_by( BatchJob.id.desc() ).first()

    def test_pickle_synchronization_exception(self):
        # Sync exception should be pickable, to be able to send if from
        # one process to another.
        synchronizer = RaisingSynchronizer()
        sync_except = list(synchronizer.read_account_entries())[-1]
        self.assertIsInstance(sync_except, SynchronizationException)
        pickle.dumps(sync_except)

    def test_synchronization_exception( self ):
        synchronizer = RaisingSynchronizer()
        list( synchronizer.all( self.options ) )
        last_batch_job = self.get_last_batch_job()
        self.assertNotEqual( self.previous_job, last_batch_job )
        self.assertEqual( last_batch_job.current_status, 'warnings' )
        self.assertTrue( 'could not read entries' in last_batch_job.message )

    def test_exception( self ):
        
        class RaisingSynchronizer( FinancialSynchronizer ):
            
            def read_account_entries(self):
                yield 'about to raise'
                raise Exception()
            
        synchronizer = RaisingSynchronizer()
        list( synchronizer.all( self.options ) )
        last_batch_job = self.get_last_batch_job()
        self.assertNotEqual( self.previous_job, last_batch_job )
        self.assertEqual( last_batch_job.current_status, 'errors' )
        
    def test_generator_exit( self ):
        # see if it works for non Exceptions as well
        
        class RaisingSynchronizer( FinancialSynchronizer ):
            
            def read_account_entries(self):
                yield 'about to raise'
                raise GeneratorExit()
            
        synchronizer = RaisingSynchronizer()
        list( synchronizer.all( self.options ) )
        last_batch_job = self.get_last_batch_job()
        self.assertNotEqual( self.previous_job, last_batch_job )
        self.assertEqual( last_batch_job.current_status, 'errors' )
