'''
Created on Aug 24, 2010

@author: tw55413
'''
import datetime
from decimal import Decimal as D
import unittest

from integration.tinyerp.convenience import add_months_to_date

from vfinance.model.hypo.mortgage_table import mortgage_table, capital_due

class MortgageTableCase(unittest.TestCase):

    def assertRepaymentsMatchCapitalDue(self, repayments, schema_definition):
        schema_definition.pop('mortgage_date', None)
        thru_date = datetime.date(2400,12,31)
        for p in repayments:
            capital_due_on_repayment_date = capital_due(p.date, thru_date=thru_date, **schema_definition)
            self.assertAlmostEqual(max(p.capital_due, 0), capital_due_on_repayment_date, delta=2)
            capital_due_after_repayment_date =  capital_due(p.date + datetime.timedelta(days=7), thru_date=thru_date, **schema_definition)
            self.assertAlmostEqual(max(p.capital_due, 0), capital_due_after_repayment_date, delta=2)
            end_of_period = add_months_to_date(p.date, schema_definition['interval']) - datetime.timedelta(days=1)
            capital_at_end_of_period = capital_due(end_of_period, thru_date=thru_date, **schema_definition)
            self.assertAlmostEqual(max(p.capital_due, 0), capital_at_end_of_period, delta=2)

    def test_cummulative_payments(self):
        # patronale dossier 3835
        schema_definition = dict(periodic_interest_rate = D('0.85'),
                                 payment_type = 'cummulative',
                                 amount = D('170000'),
                                 number_of_capital_payments = 24,
                                 interval = 1,
                                 from_date = datetime.date(2014, 4, 18))
        payments = dict((p.number,p) for p in  mortgage_table(**schema_definition))
        p6 = payments[6]
        self.assertEqual( p6.number,             6 )
        self.assertEqual( p6.date,               datetime.date(2014, 10, 17) )
        self.assertEqual( p6.rent,         D('1507.47') )
        self.assertEqual( p6.capital,      D('-1507.47') )
        self.assertEqual( p6.amount,       D('0') )
        self.assertEqual( p6.capital_due,  D('178856.34') )
        self.assertRepaymentsMatchCapitalDue(payments.values(), schema_definition)

    def test_three_months_payments_fixed_payment(self):
        # patronale dossier 3132
        schema_definition = dict(periodic_interest_rate = D('1.765'),
                                 payment_type = 'fixed_payment',
                                 amount = D('74368.06'),
                                 number_of_capital_payments = 180/3, 
                                 interval = 3,
                                 from_date = datetime.date(2001, 10, 24))
        payments = dict((p.number,p) for p in  mortgage_table(**schema_definition))
        
        p6 = payments[6]
        self.assertEqual( p6.number,             6 )
        self.assertEqual( p6.date,               datetime.date(2003, 4, 23) )
        self.assertAlmostEqual( p6.rent,         D('1247.99'), 1 )
        self.assertAlmostEqual( p6.capital,      D('771.47'),  1)
        self.assertAlmostEqual( p6.amount,       D('2019.46'), 1 )
        self.assertAlmostEqual( p6.capital_due,  D('70706.84') - D('771.47'), 1)
        self.assertRepaymentsMatchCapitalDue(payments.values(), schema_definition)

    def test_fixed_capital_payment(self):
        # patronale dossier 3421
        schema_definition = dict(periodic_interest_rate = D('0.41'),
                                 payment_type = 'fixed_capital_payment',
                                 amount = D('51000'),
                                 number_of_capital_payments = 51, 
                                 interval = 1,
                                 from_date = datetime.date(2011, 10, 31))
        payments = dict((p.number,p) for p in  mortgage_table(**schema_definition))
        
        p6 = payments[6]
        self.assertEqual( p6.number,             6 )
        self.assertEqual( p6.date,               datetime.date(2012, 4, 30) )
        self.assertEqual( p6.rent,         D('188.60'), 1 )
        self.assertEqual( p6.capital,      D('1000'),  1)
        self.assertEqual( p6.amount,       D('1188.60'), 1 )
        self.assertEqual( p6.capital_due,  D('45000'), 1)
        self.assertRepaymentsMatchCapitalDue(payments.values(), schema_definition)

    def test_monthly_payments_only_interest(self):
        schema_definition = dict(periodic_interest_rate = D('0.73'),
                                 payment_type = 'bullet',
                                 amount = D('99250.00'),
                                 number_of_capital_payments = 12, 
                                 interval = 1,
                                 from_date = datetime.date(2011, 12, 12) )
        payments = dict((p.number,p) for p in  mortgage_table(**schema_definition))
        self.assertEqual( len(payments), 12 )
        p1 = payments[1]
        self.assertEqual( p1.capital,           0 )
        self.assertEqual( p1.rent,              D('724.52') )
        p_12 = payments[12]
        self.assertEqual( p_12.capital,         D('99250.00') )
        self.assertEqual( p_12.rent,            D('724.52') )
        self.assertRepaymentsMatchCapitalDue(payments.values(), schema_definition)

    def test_annual_intrest_1(self):
        schema_definition = dict(annual_interest_rate = D('5.0'),
                                 periodic_interest_rate = D('0.0'),
                                 payment_type = 'fixed_payment',
                                 amount =  D('11320.13'),
                                 number_of_capital_payments = 147, 
                                 interval = 1,
                                 from_date = datetime.date(1998, 12, 2))
        payments = dict((p.number,p) for p in  mortgage_table(**schema_definition))
        self.assertEqual( len(payments), 147 )
        p6 = payments[6]
        self.assertEqual( p6.number,             6 )
        self.assertEqual( p6.date,               datetime.date(1999, 6, 1) )
        self.assertAlmostEqual( p6.rent,         D('47.16'), 1 )
        self.assertAlmostEqual( p6.capital,      D('57.67'),  1)
        self.assertRepaymentsMatchCapitalDue(payments.values(), schema_definition)
        
    def test_annual_intrest_2(self):
        schema_definition = dict(annual_interest_rate = D('0.0'),
                                 periodic_interest_rate = D('5.0'),
                                 payment_type = 'fixed_annuity',
                                 amount =  D('11320.13'),
                                 number_of_capital_payments = 147, 
                                 interval = 1,
                                 from_date = datetime.date(1998, 12, 2))
        payments = dict((p.number,p) for p in  mortgage_table(**schema_definition))
        self.assertEqual( len(payments), 147 )
        p6 = payments[6]
        self.assertEqual( p6.number,             6 )
        self.assertEqual( p6.date,               datetime.date(1999, 6, 1) )
        self.assertAlmostEqual( p6.rent,         D('47.16'), 1 )
        self.assertAlmostEqual( p6.capital,      D('57.67'),  1)
        self.assertRepaymentsMatchCapitalDue(payments.values(), schema_definition)
        #
        # take the original mortgage table starting in 1992
        #
        payments = list( p for p in  mortgage_table( annual_interest_rate = D('0.0'),
                                                     periodic_interest_rate = D('9'),
                                                     payment_type = 'fixed_annuity',
                                                     amount =  D('51867.08'),
                                                     number_of_capital_payments = 20 * 12,
                                                     interval = 1,
                                                     from_date = datetime.date(1992, 10, 2) ) )
        
        #
        # now try to continue this table in 2011
        #
        payments = list( p for p in  mortgage_table( annual_interest_rate = D('0.0'),
                                                     periodic_interest_rate = D('9'),
                                                     payment_type = 'fixed_annuity',
                                                     amount =  D('8798.37'),
                                                     number_of_capital_payments = 21,
                                                     interval = 1,
                                                     from_date = datetime.date(2011, 1, 2) ) )
    
    def test_first_of_month_payment_start_before_notary_settlement(self):
        #
        # This is SRCL dossier 43750
        #
        schema_definition = dict(periodic_interest_rate=D('0.554'),
                                 payment_type='fixed_payment',
                                 amount = D('59494.45'),
                                 number_of_capital_payments=240,
                                 interval = 1,
                                 from_date = datetime.date(1997,10,2),
                                 mortgage_date = datetime.date(1997,10,17))
        repayments = list(mortgage_table(**schema_definition))
        first_repayment = repayments[0]
        self.assertEqual( first_repayment.number,     2 )
        self.assertEqual( first_repayment.date,       datetime.date(1997, 12, 1) )
        self.assertEqual( first_repayment.rent,       D('482.75') )
        self.assertEqual( first_repayment.capital,    D('239') )
        last_repayment = repayments[-1]
        self.assertEqual( last_repayment.number ,     240 )
        self.assertEqual( last_repayment.date,        datetime.date(2017, 10, 1) )
        self.assertEqual( last_repayment.rent,        D(  '2.48') )
        self.assertEqual( last_repayment.capital,     D('446.29') )
        self.assertRepaymentsMatchCapitalDue(repayments, schema_definition)

    def test_first_of_month_payment_start_at_notary_settlement(self):
        #
        # This is SRCL dossier 35160
        #
        schema_definition = dict(periodic_interest_rate=D('0.6625'),
                                 payment_type='fixed_payment',
                                 amount = D('31482.35'),
                                 number_of_capital_payments=180,
                                 interval = 1,
                                 from_date = datetime.date(1993,7,2),
                                 mortgage_date = datetime.date(1993,7,2))
        repayments = list(mortgage_table(**schema_definition))
        first_repayment = repayments[0]
        self.assertEqual( first_repayment.number,     1 )
        self.assertEqual( first_repayment.date,       datetime.date(1993, 8, 1) )
        self.assertEqual( first_repayment.rent,       D('208.57') )
        self.assertEqual( first_repayment.capital,     D('91.38') )
        last_repayment = repayments[-1]
        self.assertEqual( last_repayment.number ,     180 )
        self.assertEqual( last_repayment.date,        datetime.date(2008, 7, 1) )
        self.assertEqual( last_repayment.rent,        D(  '1.98') )
        self.assertEqual( last_repayment.capital,     D('297.97') )
        self.assertRepaymentsMatchCapitalDue(repayments, schema_definition)

    def test_first_of_month_payment_start_after_notary_settlement(self):
        #
        # This is Eigen Heerd dossier 234-01-05171
        #
        schema_definition = dict(periodic_interest_rate=D('0.29'),
                                 payment_type='fixed_payment',
                                 amount = D('32884.31'),
                                 number_of_capital_payments=120,
                                 interval = 1,
                                 from_date = datetime.date(2011,11,2),
                                 mortgage_date = datetime.date(2011,10,27))
        repayments = list(mortgage_table(**schema_definition))
        first_repayment = repayments[0]
        self.assertEqual( first_repayment.number,      1 )
        self.assertEqual( first_repayment.date,        datetime.date(2011, 12, 1) )
        self.assertEqual( first_repayment.rent,        D('95.36') )
        self.assertEqual( first_repayment.capital,     D('229.51') )
        second_last_repayment = repayments[-2]
        self.assertEqual( second_last_repayment.number ,     119 )
        self.assertEqual( second_last_repayment.rent,        D(  '1.88') )
        self.assertEqual( second_last_repayment.capital,     D('322.99') )
        self.assertRepaymentsMatchCapitalDue(repayments, schema_definition)
