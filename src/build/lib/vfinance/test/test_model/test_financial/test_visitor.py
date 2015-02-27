"""
Visitors tests without a complete workflow
"""
from decimal import Decimal as D
import logging

import datetime
import operator

from sqlalchemy import orm

from vfinance.model.financial.visitor import (AccountAttributionVisitor,
                                              abstract as abstract_visitor)
from vfinance.model.financial.visitor.security_orders import SecurityOrdersVisitor
from vfinance.model.bank.visitor import ProductBookingAccount, CustomerBookingAccount
from vfinance.model.financial.fund import FinancialAccountFundDistribution
from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment as FAPF
from vfinance.model.financial import product, premium
from vfinance.sql import explain

logger = logging.getLogger('vfinance.test.test_visitor')

from camelot.core.exception import UserException

last_doc_date = datetime.date( 2012, 1, 1 )

from .test_premium import AbstractFinancialAccountPremiumScheduleCase
from .test_security import MixinFinancialSecurityCase


class AccountAttributionCase(AbstractFinancialAccountPremiumScheduleCase):

    def setUp(self):
        self.account_attribution = AccountAttributionVisitor()

    def test_distribute_feature_amount(self):
        # amount chosen to have a remainder when split in 60 and 40 %
        distributed_amount = D('100.99')
        distribution = list(self.account_attribution.distribute_feature_amount(
            self.yearly_schedule,
            last_doc_date,
            'funded_premium_rate_1',
            'funded_premium',
            D('1000'),
            distributed_amount,
            'funded_premium_activation',
            'test'))
        self.assertEqual(len(distribution), 2)
        self.assertEqual(sum((line.amount for line in distribution), D(0)), distributed_amount)
        

class SecurityOrdersCase(AbstractFinancialAccountPremiumScheduleCase, MixinFinancialSecurityCase):

    @classmethod
    def setUpClass(cls):
        AbstractFinancialAccountPremiumScheduleCase.setUpClass()
        MixinFinancialSecurityCase.set_up_funds()

    def setUp( self ):
        AbstractFinancialAccountPremiumScheduleCase.setUp(self)
        self.security_orders = SecurityOrdersVisitor()
        
    def distribute( self, distribution, attributed_amount = D('100') ):
        return list( self.security_orders.get_amounts_to_invest(
            premium_schedule = self.yearly_schedule,
            attributed_amount = attributed_amount,
            distribution_date = None,
            fund_distributions = distribution 
        ) )

    def test_amounts_to_invest( self ):
        unbalanced_distribution = [FinancialAccountFundDistribution(fund = self.fund_1, target_percentage = D(50), distribution_of=self.monthly_schedule),
                                  FinancialAccountFundDistribution(fund = self.fund_2, target_percentage = D('0.00001'), distribution_of=self.monthly_schedule) ]
                                    
        with self.assertRaises( UserException ):
            self.distribute( unbalanced_distribution )
            
        # distribution and percentage as such that there is a rounding off on the
        # last fund
        zero_distribution = [ FinancialAccountFundDistribution(fund = self.fund_1, target_percentage = D('29.353979'), distribution_of=self.monthly_schedule),
                              FinancialAccountFundDistribution(fund = self.fund_2, target_percentage = D('70.646021'), distribution_of=self.monthly_schedule),
                              FinancialAccountFundDistribution(fund = self.fund_3, target_percentage = D(0), distribution_of=self.monthly_schedule),]
        
        amounts = self.distribute( zero_distribution, D('81.60') )
        
        self.assertEqual( sum( a[1] for a in amounts if a[0].fund == self.fund_3 ), 0 )
        self.assertEqual( sum( a[1] for a in amounts ), D('81.60') )
        
        # distribution of a single fund with no target_percentage specified
        single_distribution = [ FinancialAccountFundDistribution(fund = self.fund_1, target_percentage = D(0), distribution_of=self.monthly_schedule) ]
        amounts = self.distribute( single_distribution, D(200) )
        self.assertEqual( sum( a[1] for a in amounts ), D(200) )


class TestAbstractVisitorCase(AbstractFinancialAccountPremiumScheduleCase,
                              MixinFinancialSecurityCase):
    #
    # All tests should act on different dates to avoid interference
    #

    @classmethod
    def setUpClass(cls):
        AbstractFinancialAccountPremiumScheduleCase.setUpClass()
        cls.second_product = product.FinancialProduct(name='Branch 21 Account',
                                                      specialization_of=cls.base_product,
                                                      from_date=cls.tp,
                                                      account_number_prefix=124,
                                                      account_number_digits=6)
        cls.session.flush()
        cls.second_monthly_schedule = premium.FinancialAccountPremiumSchedule(
            agreed_schedule = cls.agreed_monthly_schedule,
            period_type = cls.agreed_monthly_schedule.period_type,
            financial_account = cls.account,
            product = cls.second_product,
            premium_amount = cls.agreed_monthly_schedule.amount,
            account_number = premium.FinancialAccountPremiumSchedule.new_account_number(cls.second_product, cls.account)
        )
        MixinFinancialSecurityCase.set_up_funds()
        cls.session.flush()

    def setUp(self):
        super(TestAbstractVisitorCase, self).setUp()
        self.setup_accounting_period()
        self.product_booking_account_1 = ProductBookingAccount('premium_rate_1_revenue', alternative_account_type='premium_rate_2_revenue')
        self.product_booking_account_2 = ProductBookingAccount('premium_rate_1_revenue')
        self.product_booking_account_3 = ProductBookingAccount('capital_cost')
        self.financial_booking_account_1 = abstract_visitor.FinancialBookingAccount('uninvested')
        self.financial_booking_account_2 = abstract_visitor.FinancialBookingAccount('financed_commissions')
        self.customer_booking_account = CustomerBookingAccount()

    def test_query_schedule(self):
        #
        # issue a query to measure the amount of time taken by the query
        #
        conditions = [ ('of_id', operator.eq, self.yearly_schedule.id) ]
        connection = self.session.connection(mapper=orm.class_mapper(FAPF))
        query, params = self.visitor._get_entry_query(self.yearly_schedule, conditions, None)
        full_query = str(query)%params
        print full_query
        for row in connection.execute( explain( full_query ) ):
            print row 

    def test_product_booking_account( self ):
        self.assertEqual( self.product_booking_account_1,
                          self.product_booking_account_2 )
        self.assertNotEqual( self.product_booking_account_1,
                             self.product_booking_account_3 )
        book_date_1 = datetime.date(2011,1,1)
        self.assertEqual(self.product_booking_account_1.booking_account_number_at(self.yearly_schedule, book_date_1), self.second_premium_rate_1_account)
        # test the alternative account
        book_date_2 = datetime.date(2000,1,1)
        self.assertEqual(self.product_booking_account_1.booking_account_number_at(self.yearly_schedule, book_date_2), self.first_premium_rate_1_account)

    def test_security_booking_account( self ):
        security_booking_account_1 = abstract_visitor.SecurityBookingAccount( 'security', self.fund_1 )
        security_booking_account_2 = abstract_visitor.SecurityBookingAccount( 'transfer_revenue', self.fund_1 )
        security_booking_account_3 = abstract_visitor.SecurityBookingAccount( 'transfer_revenue', self.fund_2 )
        security_booking_account_4 = abstract_visitor.SecurityBookingAccount( 'transfer_revenue', self.fund_3 )
        self.assertNotEqual( security_booking_account_1, security_booking_account_2 )
        self.assertNotEqual( self.fund_1, self.fund_2 )
        self.assertNotEqual( self.fund_1.transfer_revenue_account, self.fund_2.transfer_revenue_account )
        self.assertNotEqual( security_booking_account_2, security_booking_account_3 )
        self.assertNotEqual( self.fund_1, self.fund_3 )
        # multiple funds can have the same revenue account, so those should
        # evaluate to being equal
        self.assertEqual( self.fund_1.transfer_revenue_account, self.fund_3.transfer_revenue_account )
        self.assertEqual( security_booking_account_2, security_booking_account_4 )
        
    def test_key_and_params( self ):
        #
        # different products should result in a different key
        #
        key_1, params_ = self.visitor._key_and_params( self.monthly_schedule, [], [] )
        key_2, params_ = self.visitor._key_and_params( self.second_monthly_schedule, [], [] )
        self.assertNotEqual( key_1, key_2 )
        #
        # same product should result in same key
        #
        key_1, params_ = self.visitor._key_and_params( self.yearly_schedule, [], [] )
        key_2, params_ = self.visitor._key_and_params( self.yearly_schedule, [], [] )
        self.assertEqual( key_1, key_2 )
        #
        # same product, same account but different object should result in same key
        #
        key_1, params_ = self.visitor._key_and_params( self.yearly_schedule, [('account', operator.eq, self.product_booking_account_1)], [] )
        key_2, params_ = self.visitor._key_and_params( self.yearly_schedule, [('account', operator.eq, self.product_booking_account_2)], [] )
        self.assertEqual( key_1, key_2 )
        #
        # same product, different product account should result in different key
        #
        key_1, params_ = self.visitor._key_and_params( self.yearly_schedule, [('account', operator.eq, self.product_booking_account_1)], [] )
        key_2, params_ = self.visitor._key_and_params( self.yearly_schedule, [('account', operator.eq, self.product_booking_account_3)], [] )
        self.assertNotEqual( key_1, key_2 )
        #
        # same product, different booking account type
        #   
        key_1, params_ = self.visitor._key_and_params( self.yearly_schedule, [('account', operator.eq, self.financial_booking_account_1)], [] )
        key_2, params_ = self.visitor._key_and_params( self.yearly_schedule, [('account', operator.eq, self.customer_booking_account)], [] )
        self.assertNotEqual( key_1, key_2 )        
        
        
    def test_total_amount_at_query( self ):
        #
        # two unconditional queries should result in the same object, due to
        # query cache
        #
        query_1, params_1 = self.visitor._get_total_amount_at_query( self.yearly_schedule, [] )
        query_2, params_2 = self.visitor._get_total_amount_at_query( self.yearly_schedule, [] )
        self.assertEqual( id( query_1 ), id( query_2 ) )
        #
        # two unconditional queries should result in a different object if they
        # are for a different product
        #
        query_1, params_1 = self.visitor._get_total_amount_at_query( self.yearly_schedule, [] )
        query_2, params_2 = self.visitor._get_total_amount_at_query( self.second_monthly_schedule, [] )
        self.assertNotEqual( id( query_1 ), id( query_2 ) )
        
    def test_get_total_amount_at( self ):
        date_1 = datetime.date( 2010, 1, 3 )
        date_2 = datetime.date( 2011, 6, 6 )
        self.insert_entry( self.yearly_schedule, date_1, date_1, self.first_premium_rate_1_account, 30  )
        self.insert_entry( self.yearly_schedule, date_1, date_1, self.second_premium_rate_1_account, 300 )
        self.insert_entry( self.yearly_schedule, date_2, date_2, self.second_premium_rate_1_account, 40  )
        self.insert_entry( self.yearly_schedule, date_2, date_2, self.first_premium_rate_1_account, 400 )   
        self.insert_entry( self.yearly_schedule, date_1, date_1, self.yearly_schedule.full_account_number, 10  )
        self.insert_entry( self.monthly_schedule, date_1, date_1, self.monthly_schedule.full_account_number, 15  )
        self.assertEqual( self.visitor.get_total_amount_at( self.yearly_schedule, date_1 )[0], 0 )
        self.assertEqual( self.visitor.get_total_amount_at( self.yearly_schedule, date_1, account = ProductBookingAccount('premium_rate_3_revenue') )[0], 0 )
        self.assertEqual( self.visitor.get_total_amount_at( self.yearly_schedule, date_1, account = ProductBookingAccount('premium_rate_1_revenue') )[0], 30 )
        self.assertEqual( self.visitor.get_total_amount_at( self.yearly_schedule, date_2, account = ProductBookingAccount('premium_rate_1_revenue') )[0], 40 )
        self.assertEqual( self.visitor.get_total_amount_at( self.yearly_schedule, date_1, account = abstract_visitor.FinancialBookingAccount() )[0], 10 )
        self.assertEqual( self.visitor.get_total_amount_at( self.monthly_schedule, date_1, account = abstract_visitor.FinancialBookingAccount() )[0], 15 )

    def test_related_fulfillment_type(self):
        date_1 = datetime.date(2010, 1, 8)
        date_2 = datetime.date(2010, 1, 9)
        premium_entry_id = self.insert_entry(self.yearly_schedule,
                                             date_1,
                                             date_1,
                                             self.yearly_schedule.full_account_number,
                                             20,
                                             'premium_attribution')
        self.insert_entry(self.yearly_schedule, 
                          date_2, 
                          date_2, 
                          self.yearly_schedule.full_account_number,
                          15,
                          'fund_attribution',
                          premium_entry_id,
                          )
        self.assertEqual(self.visitor.get_total_amount_until(self.yearly_schedule, account=abstract_visitor.FinancialBookingAccount(), fulfillment_type='fund_attribution')[0], 15)
        self.assertEqual(self.visitor.get_total_amount_until(self.yearly_schedule, account=abstract_visitor.FinancialBookingAccount(), conditions=[('associated_to_fulfillment_type', operator.eq, 'risk_deduction')])[0], 0)
        self.assertEqual(self.visitor.get_total_amount_until(self.yearly_schedule, account=abstract_visitor.FinancialBookingAccount(), conditions=[('associated_to_fulfillment_type', operator.eq, 'premium_attribution')])[0], 15)

    def remove_entries(self, premium_schedule, entries):
        """
        :return: a list of executed remove requests
        """
        remove_requests = []
        with self.accounting.begin(self.session):
            for request in self.visitor.create_remove_request(premium_schedule, entries):
                self.accounting.register_request(request)
                remove_requests.append(request)
        return remove_requests

    def test_create_remove_request(self):
        remove_date = datetime.date( 2010, 1, 2 )
        self.insert_entry(self.yearly_schedule, remove_date, remove_date, self.premium_fee_1_revenue_account, 30)
        entries = list(self.visitor.get_entries(self.yearly_schedule, from_book_date=remove_date, thru_book_date=remove_date))
        self.assertTrue(len(entries) >= 2)
        # remove should not work outside a transaction within the accounting system
        with self.assertRaises(UserException):
            list(self.visitor.create_remove_request(self.yearly_schedule, entries))
        remove_requests = self.remove_entries(self.yearly_schedule, entries)
        self.assertTrue(len(remove_requests) >= 1)

    def test_remove_associated_entry(self):
        #
        # associated entries should be removed as well, but not those not
        # associated
        #
        remove_date = datetime.date( 2010, 1, 10 )
        entry_1_id = self.insert_entry(self.yearly_schedule, remove_date, remove_date, self.first_premium_rate_1_account, 30)
        self.insert_entry(self.yearly_schedule, remove_date, remove_date, self.premium_fee_1_revenue_account, 40)
        self.insert_entry(self.yearly_schedule, remove_date, remove_date, self.premium_fee_1_revenue_account, 50, associated_to_id=entry_1_id)
        entries = list(self.visitor.get_entries(self.yearly_schedule, account=ProductBookingAccount('premium_rate_1_revenue'), from_book_date=remove_date, thru_book_date=remove_date))
        self.assertEqual(len(entries), 1)
        remove_requests = self.remove_entries(self.yearly_schedule, entries)
        self.assertEqual(len(remove_requests), 2)

    def test_remove_same_document_association(self):
        #
        # entries associated to the same document as the removed entry
        #
        remove_date = datetime.date( 2010, 1, 11 )
        ft = 'premium_attribution'
        self.insert_entry(self.yearly_schedule, remove_date, remove_date,  self.first_premium_rate_1_account, 30, fulfillment_type=ft)
        entries = list(self.visitor.get_entries(self.yearly_schedule, fulfillment_type=ft, from_book_date=remove_date, thru_book_date=remove_date))
        self.assertEqual(len(entries), 2)
        entry_1, entry_2 = entries[0], entries[1]
        self.insert_entry(self.yearly_schedule, remove_date, remove_date,  self.premium_fee_1_revenue_account, 50, associated_to_id=entry_1.fulfillment_id)
        remove_requests = self.remove_entries(self.yearly_schedule, [entry_2])
        self.assertEqual(len(remove_requests), 2)

    def test_fail_on_mixed_schedules(self):
        mixed_schedule_date = datetime.date(2010, 1, 5)
        entry_1_id = self.insert_entry(self.yearly_schedule, mixed_schedule_date, mixed_schedule_date, self.first_premium_rate_1_account, 30)
        self.insert_entry(self.monthly_schedule, mixed_schedule_date, mixed_schedule_date, self.premium_fee_1_revenue_account, 50, associated_to_id=entry_1_id)
        entries = list(self.visitor.get_entries(self.yearly_schedule, from_book_date=mixed_schedule_date, thru_book_date=mixed_schedule_date))
        self.assertEqual(len(entries), 2)
        with self.assertRaises(UserException):
            self.remove_entries(self.yearly_schedule, entries)