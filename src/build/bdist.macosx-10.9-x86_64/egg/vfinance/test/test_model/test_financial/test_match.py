import datetime
import unittest
import logging
import mock

logger = logging.getLogger('vfinance.test.test_match')

from vfinance.model.financial.match import match_premiums_and_entries, get_code
from vfinance.model.financial.premium import PremiumScheduleMixin

from .mock_objects import EntryMock, product_1

class PremiumMock( mock.Mock, PremiumScheduleMixin ):
    
    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'product', product_1 )
        kwargs.setdefault( 'valid_from_date', datetime.date( 2010, 1, 1 ) )
        kwargs.setdefault( 'valid_thru_date', datetime.date( 2100, 1, 1 ) )
        kwargs.setdefault( 'payment_thru_date', datetime.date( 2100, 1, 1 ) )
        kwargs.setdefault( 'period_type', 'single' )
        kwargs.setdefault( 'roles', [] )
        kwargs.setdefault( 'coverages', [] )
        kwargs.setdefault( 'get_coverages_at', mock.Mock( return_value = [] ) )
        kwargs.setdefault( 'premiums_attributed_to_customer', 0 )
        kwargs.setdefault( 'features', {} )
        kwargs.setdefault( 'financial_account', mock.Mock( direct_debit_mandates = [] ) )
        super( PremiumMock, self ).__init__( *args, **kwargs )

    def get_all_features_switch_dates( self, *args, **kwargs ):
        return set( [self.valid_from_date, self.valid_thru_date] )
    
    def get_role_switch_dates( self, *args, **kwargs ):
        return set( [self.valid_from_date, self.valid_thru_date] )    
    
    def get_coverage_switch_dates( self, *args, **kwargs ):
        return set( [self.valid_from_date, self.valid_thru_date] )
    
    def get_applied_feature_at( self,
                                application_date, 
                                attribution_date,
                                premium_amount,
                                feature_description, 
                                default = None ):
        return mock.Mock( value = self.features.get( feature_description, default ) )

class PremiumMatchCase( unittest.TestCase ):
    
    def setUp( self ):
        super( PremiumMatchCase, self ).setUp()
        agreement_code = '123/1234/12345'
        first_remark = '***123/1234/12345***'
        second_remark = '***123/1234/12346***'
        self.e1 = EntryMock( name = '1', open_amount = -100, remark = first_remark )
        self.e2 = EntryMock( name = '2', open_amount = -110, remark = first_remark )
        self.e3 = EntryMock( name = '3', open_amount =  -90, remark = first_remark )
        self.e4 = EntryMock( name = '4', open_amount = -190, remark = first_remark )
        self.e5 = EntryMock( name = '5', open_amount = -100, remark = first_remark, account = '789' )
        self.e6 = EntryMock( name = '6', open_amount =  -91, remark = first_remark )
        self.e7 = EntryMock( name = '7', open_amount =  -20, remark = first_remark )
        self.e8 = EntryMock( name = '8', open_amount = -100, remark = first_remark, number_of_fulfillments = 1 )
        self.e9 = EntryMock( name = '9', open_amount = -100, remark = second_remark )
        
        self.p1 = PremiumMock( name = '1', premium_amount = 100, agreement_code = agreement_code )
        self.p2 = PremiumMock( name = '2', premium_amount = 110, agreement_code = agreement_code  )
        self.p3 = PremiumMock( name = '3', premium_amount = 90, 
                               agreement_code = agreement_code, 
                               features = {'maximum_additional_premium_accepted':1} )
        self.p4 = PremiumMock( name = '4',
                               premium_amount = 200, 
                               agreement_code = agreement_code  )
        self.p5 = PremiumMock( name = '5', 
                               agreement_code = agreement_code,
                               premium_amount = 100, 
                               premiums_attributed_to_customer = 1 )
        self.p6 = PremiumMock( name = '6', 
                               agreement_code = agreement_code,
                               premium_amount = 100, 
                               period_type = 'monthly' )
        self.p7 = PremiumMock( name = '7', 
                               premium_amount = 100, 
                               agreement_code = agreement_code,
                               payment_thru_date = datetime.date(2009, 12, 31) )
        
    def test_code(self):
        self.e1.remark = '2097440033/2097407547 210/9833/00065'
        code_type, code = get_code(self.e1)
        self.assertEqual(code_type, 'agreement')
        self.assertEqual(code, u'210/9833/00065')

    def test_perfect_match( self ):
        matches = match_premiums_and_entries( [self.e1], [self.p1] )
        self.assertEqual( matches, [ (self.p1, self.e1, 100) ] )
        matches = match_premiums_and_entries( [self.e1, self.e2, self.e3], [self.p1] )
        self.assertEqual( matches, [ (self.p1, self.e1, 100) ] )
        matches = match_premiums_and_entries( [self.e3, self.e2, self.e1], [self.p1] )
        self.assertEqual( matches, [ (self.p1, self.e1, 100) ] )
        matches = match_premiums_and_entries( [self.e1], [self.p1, self.p2, self.p3] )
        self.assertEqual( matches, [ (self.p1, self.e1, 100) ] )
        matches = match_premiums_and_entries( [self.e1], [self.p3, self.p2, self.p1] )
        self.assertEqual( matches, [ (self.p1, self.e1, 100) ] )
        
    def test_perfect_matches( self ):
        matches = match_premiums_and_entries( [self.e1, self.e2, self.e3], [self.p3, self.p2, self.p1] )
        self.assertEqual( len( matches ), 3 )
        self.assertTrue( (self.p1, self.e1, 100) in matches )
        self.assertTrue( (self.p2, self.e2, 110) in matches )
        self.assertTrue( (self.p3, self.e3,  90) in matches )
        
    def test_distribution_of_entry( self ):
        matches = match_premiums_and_entries( [self.e4], [self.p1, self.p3] )
        self.assertEqual( len( matches ), 2 )
        self.assertTrue( (self.p1, self.e4, 100) in matches )
        self.assertTrue( (self.p3, self.e4,  90) in matches )
        
    def test_distribution_of_multiple_entries( self ):
        matches = match_premiums_and_entries( [self.e4, self.e7], [self.p1, self.p2] )
        self.assertEqual( len( matches ), 3 )
        
    def test_different_amounts( self ):        
        matches = match_premiums_and_entries( [self.e2], [self.p1] )
        self.assertEqual( matches, [] )
        matches = match_premiums_and_entries( [self.e3], [self.p1] )
        self.assertEqual( matches, [] )
        
    def test_pending_premiums_account( self ):
        matches = match_premiums_and_entries( [self.e5], [self.p1] )
        self.assertEqual( matches, [] )        

    def test_multiple_entries( self ):
        matches = match_premiums_and_entries( [self.e1, self.e2, self.e3, self.e4], [self.p4] )
        self.assertEqual( len( matches ), 2 )
        self.assertTrue( (self.p4, self.e2, 110) in matches )
        self.assertTrue( (self.p4, self.e3,  90) in matches )

    def test_maximum_additional_premium( self ):
        matches = match_premiums_and_entries( [self.e1, self.e2, self.e4, self.e5, self.e6], [self.p3] )
        self.assertEqual( matches, [ (self.p3, self.e6, 91) ] )
        
    def test_fulfilled_entries( self ):
        matches = match_premiums_and_entries( [self.e8], [self.p1] )
        self.assertEqual( matches, [] )    

    def test_fulfilled_premiums( self ):
        matches = match_premiums_and_entries( [self.e1], [self.p5] )
        self.assertEqual( matches, [] )

    def test_many_payments( self ):
        # try to match 2 years of premiums at once
        entries = [ EntryMock( name = str(i), 
                               open_amount = -100, 
                               doc_date = datetime.date(2013,1,1),
                               remark = self.e1.remark ) for i in range(24) ]
        matches = match_premiums_and_entries( entries, [self.p6] )
        self.assertEqual( len(matches), 24 )
        
    def test_different_agreement( self ):
        matches = match_premiums_and_entries( [self.e9], [self.p1] )
        self.assertEqual( matches, [] )
        
    def test_passed_payment_thru_date( self ):        
        matches = match_premiums_and_entries( [self.e1], [self.p7] )
        self.assertEqual( matches, [] )
