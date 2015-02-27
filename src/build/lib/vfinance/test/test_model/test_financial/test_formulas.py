import datetime
from decimal import Decimal as D

from . import test_product

from .test_match import PremiumMock

from vfinance.model.bank.index import IndexHistory
from vfinance.model.financial.formulas import get_amount_at

class FormulaCase(test_product.FinancialProductCase):

    def setUp(self):
        super(FormulaCase, self).setUp()
        for duration in range(13):
            IndexHistory(from_date=self.tp,
                         duration=duration,
                         value = (9-duration/12),
                         described_by = self.index_type,
                         )
        self.session.flush()

    def test_market_fluctuation( self ):
        reserve = D(100000)
        features = { 'interest_rate':D(4),
                     'additional_interest_rate':D(0),
                     'market_fluctuation_exit_rate':D(100),
                     'market_fluctuation_reference_duration':D(8*12),
                     'market_fluctuation_index_difference':D(0) }
        
        premium_schedule = PremiumMock( product = self.product )
        ftps = PremiumMock( features = features,
                            premium_schedule = premium_schedule )
        # in case Index rate is higher than interest rate
        market_fluctuation = get_amount_at(  ftps, 
                                             None, 
                                             datetime.date(2012,1,1),
                                             datetime.date(2012 - 7, 1, 1), 
                                             'market_fluctuation', 
                                             applied_amount = reserve )
        expected_market_fluctuation = reserve * ( 1 - ( 1 + D(4)/100 ) / ( 1 + D(8)/100 ) )
        self.assertAlmostEqual( market_fluctuation, expected_market_fluctuation, 1 )
        # in case Index rate lower than interest rate
        features['additional_interest_rate'] = D(6)
        premium_schedule = PremiumMock( product = self.product )
        ftps = PremiumMock( features = features,
                            premium_schedule = premium_schedule )
        market_fluctuation = get_amount_at(  ftps, 
                                             None, 
                                             datetime.date(2012,1,1),
                                             datetime.date(2012 - 7, 1, 1), 
                                             'market_fluctuation', 
                                             applied_amount = reserve )
        self.assertEqual( market_fluctuation, 0 )
        
        
        