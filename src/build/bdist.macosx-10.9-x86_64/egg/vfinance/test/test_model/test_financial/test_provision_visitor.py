import datetime
from decimal import Decimal as D
import mock

from vfinance.model.financial.visitor.provision import ProvisionVisitor, premium_data
from vfinance.model.insurance.agreement import InsuranceAgreementAccountCoverageMixin

from .test_match import PremiumMock
from .test_premium import AbstractFinancialAccountPremiumScheduleCase

class CoverageLevelMock( mock.Mock ):
    
    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'type', 'percentage_of_account' )
        kwargs.setdefault( 'coverage_limit_from', D(0) )
        kwargs.setdefault( 'coverage_limit_thru', D(10000000) )
        super( CoverageLevelMock, self ).__init__(  *args, **kwargs )
        
coverage_level_fixed_amount = CoverageLevelMock( type = 'fixed_amount' )

class CoverageMock( mock.Mock, InsuranceAgreementAccountCoverageMixin ):
    
    @property
    def coverage_from_date( self ):
        return self.from_date
    
class ProvisionCase(AbstractFinancialAccountPremiumScheduleCase):

    @classmethod
    def setUpClass(cls):
        AbstractFinancialAccountPremiumScheduleCase.setUpClass()
        cls.visitor = ProvisionVisitor()
        
    def test_insured_capital( self ):
        fixed_amount = CoverageMock( coverage_for = coverage_level_fixed_amount,
                                     coverage_limit = D(100000),
                                     from_date = datetime.date( 2007,  1,  1 ),
                                     thru_date = datetime.date( 2007, 12, 31 ),
                                     )
        self.assertEqual( self.visitor.insured_capital_at( datetime.date( 2006, 12, 31 ), fixed_amount, 1000.0 ),
                          0.0 )
        self.assertEqual( self.visitor.insured_capital_at( datetime.date( 2008,  1,  1 ), fixed_amount, 1000.0 ),
                          0.0 )  
        self.assertEqual( self.visitor.insured_capital_at( datetime.date( 2007,  1,  1 ), fixed_amount, 1000.0 ),
                          99000.0 )
        
    def test_get_provision( self ):
        visitor = ProvisionVisitor()
        premium_schedule = PremiumMock( product = self.product,
                                        premium_amount = 100000,
                                        features = { 'interest_rate':1,
                                                     'additional_interest_rate':1 } )
        
        premium_1 = premium_data( date = premium_schedule.valid_from_date, 
                                  amount = 100000, 
                                  gross_amount = 100000, 
                                  associated_surrenderings = [] )
        leap_day = datetime.date( 2012, 2, 29 )
        thru_date_1 = datetime.date( 2010, 12, 31 )
        new_provisions = list( visitor.get_provision( premium_schedule, 
                                                      premium_schedule.valid_from_date, 
                                                      [ thru_date_1 ], 
                                                      None, 
                                                      [ premium_1 ] ) )
        
        expected_provision = D(100000) * ( 1 + D(2)/100 )
        
        self.assertAlmostEqual( new_provisions[0][0].provision, expected_provision, 2 )
        self.assertEqual( len( list( visitor.get_document_dates( premium_schedule, premium_schedule.valid_from_date, thru_date_1 ) ) ), 12 )
        
        # 2012 has a leap day
        premium_2 = premium_data( date = datetime.date( 2012, 1, 1 ), 
                                  amount = 100000, 
                                  gross_amount = 100000, 
                                  associated_surrenderings = [] )
        new_provisions = list( visitor.get_provision( premium_schedule, 
                                                      premium_schedule.valid_from_date, 
                                                      [ datetime.date( 2012, 12, 31 ) ], 
                                                      None, 
                                                      [ premium_2 ] ) )
        self.assertAlmostEqual( new_provisions[-1][0].provision, expected_provision, 2 )
        
        # payment can start on a leap day
        premium_3 = premium_data( date = leap_day, 
                                  amount = 100000, 
                                  gross_amount = 100000, 
                                  associated_surrenderings = [] )
        new_provisions = list( visitor.get_provision( premium_schedule, 
                                                      premium_schedule.valid_from_date, 
                                                      [ datetime.date( 2013, 2, 28 ) ], 
                                                      None, 
                                                      [ premium_3 ] ) )
        self.assertAlmostEqual( new_provisions[-1][0].provision, expected_provision, 2 )
        
        # premium schedule can start on a leap day
        premium_schedule_2 = PremiumMock( product = self.product,
                                          from_date = leap_day,
                                          premium_amount = 100000,
                                          features = { 'interest_rate':1,
                                                       'additional_interest_rate':1 } )
        thru_date_3 = datetime.date( 2013, 2, 28 )
        new_provisions = list( visitor.get_provision( premium_schedule_2, 
                                                      premium_schedule_2.from_date, 
                                                      [ thru_date_3 ], 
                                                      None, 
                                                      [ premium_3 ] ) )
        self.assertAlmostEqual( new_provisions[-1][0].provision, expected_provision, 2 )
        self.assertEqual( len( list( visitor.get_document_dates( premium_schedule_2, premium_schedule_2.from_date, thru_date_3 ) ) ), 13 )            
