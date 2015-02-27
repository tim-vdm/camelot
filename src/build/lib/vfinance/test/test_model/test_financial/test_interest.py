import datetime
from decimal import Decimal as D
import decimal
import unittest

from ...test_financial import AbstractFinancialCase
import logging

from vfinance.model.financial import interest

logger = logging.getLogger('vfinance.test.test_interest')

class InterestCase(AbstractFinancialCase, unittest.TestCase):

    def test_leap_days(self):
        self.assertEqual( interest.leap_days( datetime.date(2010, 9,  1), datetime.date(2010, 9, 30) ),  0 )
        self.assertEqual( interest.leap_days( datetime.date(2010, 9,  1), datetime.date(2011, 3,  1) ),  0 )
        self.assertEqual( interest.leap_days( datetime.date(2010, 9,  1), datetime.date(2012, 2, 28) ),  0 )
        self.assertEqual( interest.leap_days( datetime.date(2010, 9,  1), datetime.date(2012, 2, 29) ),  1 )
        self.assertEqual( interest.leap_days( datetime.date(2010, 9,  1), datetime.date(2012, 3,  1) ),  1 )
        self.assertEqual( interest.leap_days( datetime.date(2010, 9,  1), datetime.date(2016, 2, 28) ),  1 )
        self.assertEqual( interest.leap_days( datetime.date(2010, 9,  1), datetime.date(2016, 2, 29) ),  2 )
        self.assertEqual( interest.leap_days( datetime.date(2010, 9,  1), datetime.date(2104, 2, 28) ), 22 )
        self.assertEqual( interest.leap_days( datetime.date(2010, 9,  1), datetime.date(2104, 2, 29) ), 23 )
        self.assertEqual( interest.leap_days( datetime.date(2012, 2, 28), datetime.date(2012, 2, 29) ),  1 )
        self.assertEqual( interest.leap_days( datetime.date(2012, 2, 29), datetime.date(2012, 3,  1) ),  0 )
        
    def test_single_period_future_value(self):
        pa = D(100000)
        apr = D('2.39')
        
        self.assertEqual( interest.single_period_future_value(pa, self.t3 + datetime.timedelta(days=1), self.t3, apr, 365), pa )
        
        #
        # Typical closure dates
        #
        after_one_year = datetime.date( self.t3.year + 1, self.t3.month, self.t3.day )
        end_of_first_month = datetime.date( self.t3.year, self.t3.month, 28 )
        end_of_first_year = datetime.date( self.t3.year, 12, 31 )
        after_9_years = datetime.date( self.t3.year + 9, self.t3.month, self.t3.day )
        
        expected_future_values = [
          (self.t3,                     pa),
          (end_of_first_month,          D('100161.90') ),
          (end_of_first_year,           D('102164.97') ),
          (after_one_year,              D('102390.00') ),
          (datetime.date(2012, 2, 28),  D('105006.85') ),
          (datetime.date(2012, 2, 29),  D('105006.85') ),
          (datetime.date(2012, 3,  1),  D('105013.65') ),
          (datetime.date(2012, 3,  2),  D('105020.44') ),
          (after_9_years,               (pa*(1+apr/100)**9).quantize(D('.01'), rounding=decimal.ROUND_DOWN) )
        ]
        
        #
        # printout for external verification
        #
        #for thru_date, _future_value in expected_future_values:
        #    future_value = interest.single_period_future_value( pa, self.t3, thru_date, apr, 365 )
        #    print '%02i-%02i-%04i     %-10s'%(thru_date.day, thru_date.month, thru_date.year, future_value.quantize(D('.01'), rounding=decimal.ROUND_DOWN) )
              
        for thru_date, future_value in expected_future_values:
            self.assertEqual( interest.single_period_future_value(pa, self.t3 + datetime.timedelta(days=1), thru_date, apr, 365).quantize(D('.01'), rounding=decimal.ROUND_DOWN), future_value )
            
    def test_multiple_periods_future_value(self):
        pa = D(100000)
        
        periods = [ ( datetime.date(2010,1,1), 2),
                    ( datetime.date(2011,1,1), 1),]
        
        self.assertEqual( interest.multiple_periods_future_value(pa, periods, datetime.date(2009,12,31), 365), pa )
        self.assertEqual( interest.multiple_periods_future_value(pa, periods, datetime.date(2010,12,31), 365), pa * D('1.02') )
        self.assertEqual( interest.multiple_periods_future_value(pa, periods, datetime.date(2011,12,31), 365), pa * D('1.02') * D('1.01') )
        self.assertEqual( interest.multiple_periods_future_value(pa, periods, datetime.date(2012,12,31), 365), pa * D('1.02') * D('1.01') * D('1.01') )
        
    def test_multiple_amounts_multiple_periods_future_value(self):
        
        pa = D(100000)
        
        periods = [ ( datetime.date(2010,1,1), 2),
                    ( datetime.date(2011,1,1), 1),]
        
        principal_amounts =  [ ( datetime.date(2009,6,1), pa ),
                               ( datetime.date(2011,1,1), pa ),]
        
        self.assertEqual( interest.multiple_amounts_multiple_periods_future_value(principal_amounts, periods, datetime.date(2009,12,31), 365), pa )
        self.assertEqual( interest.multiple_amounts_multiple_periods_future_value(principal_amounts, periods, datetime.date(2010,12,31), 365), pa * D('1.02') )
        self.assertEqual( interest.multiple_amounts_multiple_periods_future_value(principal_amounts, periods, datetime.date(2011,12,31), 365), (pa * D('1.02') + pa ) * D('1.01') )
        self.assertEqual( interest.multiple_amounts_multiple_periods_future_value(principal_amounts, periods, datetime.date(2012,12,31), 365), (pa * D('1.02') + pa ) * D('1.01') * D('1.01'))