import datetime
from decimal import Decimal as D

from .test_premium import AbstractFinancialAccountPremiumScheduleCase

from vfinance.model.bank.visitor import CustomerBookingAccount
from vfinance.model.financial.transaction import (
    FinancialTransaction,
    FinancialTransactionPremiumSchedule)
from vfinance.model.financial.fund import FinancialAccountFundDistribution
from vfinance.model.financial.visitor import (
    SecurityOrderLinesVisitor,
    TransactionInitiationVisitor,
    TransactionCompletionVisitor,
    FundAttributionVisitor,
)
from vfinance.model.financial.security import FinancialSecurityQuotation

from .test_transaction import MixinTransactionCase

class TestTransactionVisitorCase(AbstractFinancialAccountPremiumScheduleCase,
                                 MixinTransactionCase):

    security_order_lines_visitor = SecurityOrderLinesVisitor()
    transaction_initiation_visitor = TransactionInitiationVisitor()
    transaction_completion_visitor = TransactionCompletionVisitor()
    fund_attribution_visitor = FundAttributionVisitor()

    def test_partial_redemption_monthly_schedule(self):
        transaction = FinancialTransaction(
            from_date = self.t21,
            agreement_date = self.t20,
            transaction_type = 'partial_redemption',
            code = self.code,
        )
        FinancialTransactionPremiumSchedule(
            within = transaction,
            premium_schedule = self.monthly_schedule,
            described_by = 'percentage',
            quantity = D('-50')
        )
        fund_distribution = FinancialAccountFundDistribution(
            distribution_of = self.monthly_schedule,
            fund = self.fund,
            target_percentage = D('100'),
            from_date = self.agreement.from_date,
        )
        quot = FinancialSecurityQuotation(
            financial_security = self.fund,
            sales_date = self.t23_1,
            purchase_date = self.tp,
            from_datetime = datetime.datetime(*self.t23_1.timetuple()[:3]),
            value = D(1)
        )
        quot.change_status('verified')
        self.session.flush()
        self.button(transaction, self.status_complete)
        self.button(transaction, self.transaction_status_verified)
        self.assertEqual(transaction.completion_date, self.t23_1)
        #
        # put some initial units on the fund
        #
        initial_unit_date = self.t20 - datetime.timedelta(days=10)
        self.insert_entry(self.monthly_schedule, initial_unit_date,
                          initial_unit_date,
                          fund_distribution.full_account_number,
                          -100,
                          quantity=100)
        #
        # add unattributed amounts
        #
        ## before the transaction from date
        self.insert_entry(self.monthly_schedule,
                          self.t21 - datetime.timedelta(days=2),
                          self.t21 - datetime.timedelta(days=2),
                          self.monthly_schedule.full_account_number,
                          -60,
                          'depot_movement')
        ## at the transaction from date
        #self.insert_entry(self.monthly_schedule,
                          #self.t21,
                          #self.t21,
                          #self.monthly_schedule.full_account_number,
                          #-70,
                          #'depot_movement')
        # after the transaction from date, before the transaction
        # completion date
        self.insert_entry(self.monthly_schedule,
                          self.t23_1 - datetime.timedelta(days=2),
                          self.t23_1 - datetime.timedelta(days=2),
                          self.monthly_schedule.full_account_number,
                          -80,
                          'depot_movement')
        # after the transaction completion date
        self.insert_entry(self.monthly_schedule,
                          self.t23_1 + datetime.timedelta(days=2),
                          self.t23_1 + datetime.timedelta(days=2),
                          self.monthly_schedule.full_account_number,
                          -90,
                          'depot_movement')
        #
        # validate the security orders before the transaction
        #
        orders_upto_transaction_date = list(
            self.security_order_lines_visitor.get_premium_security_orders(
                premium_schedule=self.monthly_schedule,
                order_date=self.t21,
                from_document_date=self.tp
            ))
        self.assertEqual(len(orders_upto_transaction_date), 2)
        self.assertEqual(sum(o.quantity for o in orders_upto_transaction_date), -50 + 60)
        #
        # test fund attribution
        #
        list(self.visitor.visit_premium_schedule(self.monthly_schedule, self.t23_1))
        customer_amount = self.visitor.get_total_amount_until(self.monthly_schedule, self.t26, account=CustomerBookingAccount())[0]
        self.assertEqual(customer_amount, -1*(100+60)/2 )
        #self.visit_premium_schedule(self.visitor, self.monthly_schedule, self.t26)
        #
        # validate the security orders after the transaction
        #
        orders_after_transaction_date = list(
            self.security_order_lines_visitor.get_premium_security_orders(
                premium_schedule=self.monthly_schedule,
                order_date=self.t26 + datetime.timedelta(days=5),
                from_document_date=self.tp
            ))
        self.assertEqual(len(orders_after_transaction_date), 4)
        self.assertEqual(sum(o.quantity for o in orders_after_transaction_date), -50+80+90+60/2)