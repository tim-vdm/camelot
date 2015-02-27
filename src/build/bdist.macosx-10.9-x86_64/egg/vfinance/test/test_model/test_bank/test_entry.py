import copy
import datetime
import logging
import unittest

logger = logging.getLogger('vfinance.test.test_bank.test_entry')

from sqlalchemy import exc
from vfinance.model.bank.entry import Entry, EntryPresence, TickSession
from vfinance.test import setup_model

from camelot.core.orm import Session

from integration.venice.mock import mock_venice_dossier_class
from integration.venice.venice import DossierWrapper, constants

# data for test entries
entry_1_1 = dict(
    pBookTypeOrg = None,
    pBookType = constants.btSales,
    pBookDateOrg = None,
    pBookDate = datetime.datetime( 2007, 1, 1 ),
    pBookOrg = None,
    pBook = 'A',
    pDocNumOrg = None,
    pDocNum = 1,
    pLineNumOrg = None,
    vLineNum = 1, 
    pAccount = '111',
    pAmountDosC = 100,
    pOpenDosC = 100,
    pQuantity = 0,
    pTickStatus = 2,
    pRemark = 'entry_1_1',
)

entry_1_2 = copy.copy( entry_1_1 )
entry_1_2['pRemark'] = 'entry_1_2'

entry_2_1 = copy.copy( entry_1_1 )
entry_2_1.update( dict(
    pBookTypeOrg = constants.btSales,
    pBookType = constants.btSales,
    pBookDateOrg = datetime.datetime( 2007, 1, 1 ),
    pBookDate = datetime.datetime( 2008, 1, 1 ),
    pBookOrg = 'A',
    pBook = 'O',
    pDocNumOrg = 1,
    pDocNum = 2,
    pLineNumOrg = 1,
    vLineNum = 5, 
    pAccount = '111',
    pAmountDosC = 100,
    pOpenDosC = 100,
    pQuantity = 0,
    pTickStatus = 2,
    pRemark = 'entry_2_1',    
) )

entry_3_2 = dict(
    pBookTypeOrg = constants.btSales,
    pBookType = constants.btSales,
    pBookDateOrg = datetime.datetime( 2006, 1, 1),
    pBookDate = datetime.datetime( 2007, 1, 1 ),
    pBookOrg = 'B',
    pBook = 'O',
    pDocNumOrg = 2,
    pDocNum = 7,
    pLineNumOrg = 1,
    vLineNum = 33, 
    pAccount = '111',
    pAmountDosC = 100,
    pOpenDosC = 100,
    pQuantity = 0,
    pTickStatus = 2,
    pRemark = 'entry_3_2',
)

entry_3_3 = copy.copy( entry_1_1 )
entry_3_3['pRemark'] = 'entry_3_3'

entry_4_1 = copy.copy( entry_1_1 )
entry_4_1.update( dict( pRemark = 'entry_4_1',
                        pBookDate = datetime.datetime( 2007, 5, 5 ),
                        pBook = None,
                        pDocNum = 5 ) )
entry_4_2 = copy.copy( entry_4_1 )
entry_4_2.update( dict( pRemark = 'entry_4_2',
                        pBookTypeOrg = constants.btSales,
                        pBookDateOrg = datetime.datetime( 2007, 5, 5 ),
                        pBookOrg = None,
                        pDocNumOrg = 5,
                        pLineNumOrg = 1,
                        pBookDate = datetime.datetime( 2008, 1, 1 ),
                        pBook = 'O',
                        pDocNum = 2,
                        vLineNum = 6,                         
                        ) )
                        

class EntryCase( unittest.TestCase ):
    
    def setUp( self ):
        setup_model()
        self.session = Session()
        self.session.query(TickSession).delete()
        self.session.query(EntryPresence).delete()
        self.session.query(Entry).delete()
        self.venice = DossierWrapper( mock_venice_dossier_class( 'Test', 'EntrySync' ),
                                      constants )
        self.entry_3_1 = self.create_entry_entry_3_1()
        self.entry_presence_3_1 = EntryPresence( entry = self.entry_3_1, venice_active_year = '2006', venice_id = 12 )
        
        self.session.flush()
        
    def tearDown( self ):
        session = Session()
        session.rollback()
        for entry_presence in EntryPresence.query.filter_by( entry = self.entry_3_1 ).all():
            session.delete( entry_presence )
        session.flush() 
        session.delete( self.entry_3_1 )
        session.flush()
        
    def get_entry( self, entry_data ):
        """Get the VF entry corresponding to Venice entry data"""
        entry = Entry.get_by( venice_doc = entry_data['pDocNumOrg'] or entry_data['pDocNum'],
                              book_date = (entry_data['pBookDateOrg'] or entry_data['pBookDate']).date(),
                              line_number = entry_data['pLineNumOrg'] or entry_data['vLineNum'],
                              venice_book = entry_data['pBookOrg'] or entry_data['pBook'] or '', )
        if entry != None:
            Session().expire( entry )
        return entry
        
    def create_entry_entry_3_1( self ):
        #
        # Inserting the same entry twice should fail
        #
        entry = Entry( venice_doc = 2,
                       book_date = datetime.date( 2006, 1, 1), 
                       line_number = 1,
                       venice_book = 'B',
                       remark = 'entry_3_1',
                       amount = 100,
                       open_amount = 0,
                       ticked = False,
                       account = '111',
                       )
        return entry
    
    def sync_entries( self, account ):
        from vfinance.model.bank.entry import SyncEntries
        from camelot.test.action import MockModelContext
        model_context = MockModelContext()
        sync_action = SyncEntries()
        for i, step in enumerate( sync_action.model_run( model_context ) ):
            if i == 0:
                options = step.get_object()
                options.accounts = account
                options.dossier = self.venice
                options.constants = constants
        
    def test_unique_entry( self ):
        with self.assertRaises( exc.IntegrityError ):
            session = Session()
            with session.begin():
                self.create_entry_entry_3_1()

    def test_sync_frozen_entry( self ):
        self.venice.CreateYearContext( '2007' ).CreateEntry( False )._dossier._entries = [ entry_1_1 ]
        self.sync_entries( '111' )
        entry = self.get_entry( entry_1_1 )
        self.assertTrue( entry )
        self.assertEqual( entry.open_amount, 100 )
        #
        # adapt and freeze the entry
        #
        entry.accounting_state = 'frozen'
        modified_entry_1_1 = copy.copy( entry_1_1 )
        modified_entry_1_1['pOpenDosC'] = 0
        self.venice.CreateYearContext( '2007' ).CreateEntry( False )._dossier._entries = [ modified_entry_1_1 ]
        self.sync_entries( '111' )
        entry = self.get_entry( entry_1_1 )
        self.assertEqual( entry.open_amount, 100 )
        #
        # remove the frozen entry from the accounting system
        #
        self.venice.CreateYearContext( '2007' ).CreateEntry( False )._dossier._entries = []
        self.sync_entries( '111' )
        entry = self.get_entry( entry_1_1 )
        self.assertTrue( entry )

    def test_sync_venice( self ):
        #
        # Simply sync a single entry
        #
        self.venice.CreateYearContext( '2007' ).CreateEntry( False )._dossier._entries = [ entry_1_1 ]
        # verify if the mock objects have been setup correctly
        self.assertTrue( self.venice.CreateYearContext( '2007' ).CreateEntry(False).SetFilter( 'Account ^^  "123"', True ) )
        self.sync_entries( '111' )
        entry = self.get_entry( entry_1_1 )
        self.assertTrue( entry )
        self.assertEqual( entry.remark, 'entry_1_1' )
        #
        # The entry has changed in Venice, see if the change comes through after the sync
        #
        self.venice.CreateYearContext( '2007' ).CreateEntry( False )._dossier._entries = [ entry_1_2 ]
        self.sync_entries( '111' )
        entry = self.get_entry( entry_1_1 )
        self.assertEqual( entry.remark, 'entry_1_2' )
        #
        # We have the same entry in 2 book years, the last one should come through
        #
        self.venice.CreateYearContext( '2007' ).CreateEntry( False )._dossier._entries = [ entry_1_1 ]
        self.venice.CreateYearContext( '2008' ).CreateEntry( False )._dossier._entries = [ entry_2_1 ]
        self.sync_entries( '111' )
        entry = self.get_entry( entry_1_1 )
        self.assertEqual( entry.remark, 'entry_2_1' )
        #
        # We have the same entry in 2 book years, the last one should come through
        # The first entry has no book associated with it
        #
        self.venice.CreateYearContext( '2007' ).CreateEntry( False )._dossier._entries = [ entry_4_1 ]
        self.venice.CreateYearContext( '2008' ).CreateEntry( False )._dossier._entries = [ entry_4_2 ]
        self.sync_entries( '111' )
        entry = self.get_entry( entry_4_1 )
        self.assertEqual( entry.remark, 'entry_4_2' )
        #
        # Entries in a year that is not synced should be left alone
        #
        entry = self.get_entry( entry_3_2 )
        self.assertEqual( entry.remark, 'entry_3_1' )
        self.sync_entries( '111' )
        entry = self.get_entry( entry_3_2 )
        self.assertEqual( entry.remark, 'entry_3_1' )
        #
        # Update an entry that has its origins in a year that was not synced
        #        
        self.venice.CreateYearContext( '2007' ).CreateEntry( False )._dossier._entries = [ entry_3_2 ]
        self.sync_entries( '111' )
        entry = self.get_entry( entry_3_2 )
        self.assertEqual( entry.remark, 'entry_3_2' )
        #
        # Test if failure during sync rollsback any changes
        self.venice.CreateYearContext( '2007' ).CreateEntry( False )._dossier._entries = [ entry_3_3 ] 
        
        def raiser( *args, **kwargs ):
            raise Exception()
        
        self.venice.CreateYearContext( '2008' ).CreateEntry( False )._dossier.GetNext = raiser
        with self.assertRaises( Exception ):
            self.sync_entries( '111' )
        entry = self.get_entry( entry_3_2 )
        self.assertEqual( entry.remark, 'entry_3_2' )
