import datetime

from .mock_objects import ( FinancialTransactionMock,
                            FinancialTransactionPremiumScheduleMock,
                            FinancialTransactionFundDistributionMock,
                            FinancialTransactionCreditDistributionMock,
                            FundDistributionMock,
                            PremiumScheduleMock,
                            fund_1, fund_2, fund_3 )

from camelot.core.exception import UserException

from vfinance.model.bank.invoice import InvoiceItem
from vfinance.model.financial.transaction import (
    FinancialTransaction,
    FinancialTransactionPremiumSchedule,
    FinancialTransactionCreditDistribution,
    TransactionStatusVerified,
    TransactionStatusUndoVerified,
    RemoveFutureOrderLines,
    )
from vfinance.model.financial.premium import (
    FinancialAccountPremiumScheduleHistory
)
from vfinance.model.financial.transaction_task import FinancialTransactionPremiumScheduleTask
from vfinance.model.financial.fund import FinancialTransactionFundDistribution
from vfinance.model.financial.security_order import FinancialSecurityOrderLine

from .test_premium import AbstractFinancialAccountPremiumScheduleCase

class MixinTransactionCase(object):

    transaction_status_verified = TransactionStatusVerified()
    transaction_status_undo_verified = TransactionStatusUndoVerified()
    remove_future_order_lines = RemoveFutureOrderLines()

class FinancialTransactionCase(AbstractFinancialAccountPremiumScheduleCase,
                               MixinTransactionCase):

    @classmethod
    def setUpClass(cls):
        AbstractFinancialAccountPremiumScheduleCase.setUpClass()
        cls.setup_bic()

    def setUp(self):
        self.financial_security_order_line = FinancialSecurityOrderLine(financial_security=self.fund,
                                                                        described_by='amount',
                                                                        quantity=123,
                                                                        document_date=datetime.date(2014, 9, 7),
                                                                        fulfillment_type='redemption_attribution',
                                                                        premium_schedule=self.yearly_schedule)
        self.transaction = FinancialTransaction(agreement_date=datetime.date(2014, 9, 5),
                                                from_date=datetime.date(2014, 9, 7),
                                                thru_date=datetime.date(2017, 9, 7),
                                                code=u'000/0000/00202',
                                                transaction_type='full_redemption',
                                                distributed_via=[])
        self.transaction_premium_schedule = FinancialTransactionPremiumSchedule(within=self.transaction,
                                                                                premium_schedule=self.yearly_schedule)
        self.fund_distribution = FinancialTransactionFundDistribution(distribution_of=self.transaction_premium_schedule,
                                                                      fund=self.fund,
                                                                      target_percentage=100,
                                                                      change_target_percentage=False,
                                                                      new_target_percentage=None)
        self.transaction.consisting_of=[self.transaction_premium_schedule]
        self.session.flush()

    def test_partial_redemption_validation( self ):
        ps = PremiumScheduleMock( id = 4,
                                  fund_distribution = [ FundDistributionMock( fund=fund_1 ),
                                                        FundDistributionMock( fund=fund_2 ) ] )
        t = FinancialTransactionMock( transaction_type='partial_redemption' )
        redemption_date = t.from_date
        # transaction has no schedules
        self.assertTrue( t.note )
        ftps = FinancialTransactionPremiumScheduleMock( premium_schedule = ps,
                                                        within = t,
                                                        described_by = 'percentage',
                                                        previous_version_id = ps.version_id,
                                                        quantity = -100 )
        t.consisting_of.append( ftps )
        # cannot do partial redemption of all funds
        self.assertTrue( t.note )
        # when only one fund is redeemed, there should be a redisitribution
        # of the funds for future deductions/attribution
        ftfd = FinancialTransactionFundDistributionMock()
        ftps.fund_distribution.append( ftfd )
        self.assertTrue( 'fund still in fund distribution' in unicode(t.note) )
        # end the distribution of the redeemed fund
        for fund_distribution in ps.fund_distribution:
            if fund_distribution.fund == ftfd.fund:
                fund_distribution.thru_date = redemption_date
        self.assertTrue( 'Incorrect fund distribution' in unicode(t.note) )
        new_ffd = FundDistributionMock( fund = fund_3,
                                        from_date = redemption_date + datetime.timedelta(days=1) )
        ps.fund_distribution.append( new_ffd )
        # no distribution should be valid
        self.assertFalse( t.note )
        credit_distribution = FinancialTransactionCreditDistributionMock()
        t.distributed_via.append( credit_distribution )
        # howevever, when distributed, the distribution should be valid
        self.assertTrue( 'Invalid credit distribution' in unicode(t.note) )
        # iban
        credit_distribution.iban = 'NL91ABNA0417164300'
        self.assertFalse( t.note )
        # local belgian
        credit_distribution.iban = '001-2478378-07'
        self.assertFalse( t.note )
        # sum of percentages should be 100
        credit_distribution.quantity = 50
        self.assertTrue( '100%' in unicode(t.note))
        
    def test_full_redemption_yearly_premium_schedule( self ):
        for fund_distribution in self.yearly_schedule.fund_distribution:
            self.insert_entry(self.yearly_schedule,
                              self.t20,
                              self.t20,
                              fund_distribution.full_account_number,
                              -100,
                              quantity=100)
        credit_distribution = FinancialTransactionCreditDistribution(
            iban = 'NL91ABNA0417164300',
            bank_identifier_code = self.bic_1,
        )
        self.transaction.distributed_via.append( credit_distribution )
        self.session.flush()
        # full redemption only allows -100%
        self.assertTrue(self.transaction.note)
        self.transaction_premium_schedule.described_by = 'percentage'
        self.transaction_premium_schedule.quantity = -99
        self.assertTrue( 'Only complete premium schedules can be redeemed' in unicode(self.transaction.note) )
        self.transaction_premium_schedule.quantity = -100
        # premium schedule should not be modified after appending it to the
        # transaction
        self.yearly_schedule.valid_thru_date = self.transaction.from_date + datetime.timedelta(days=7)
        self.session.flush()
        self.assertTrue( 'Premium schedule has been modified' in unicode(self.transaction.note) )
        original_version_id = self.yearly_schedule.version_id
        self.transaction_premium_schedule.previous_version_id = original_version_id
        # payments should be terminated
        self.assertTrue( 'Payments are planned after redemption' in unicode(self.transaction.note) )
        self.transaction_premium_schedule.created_via.append(FinancialTransactionPremiumScheduleTask(described_by='terminate_payment_thru_date'))
        # there should be no pending invoice item
        invoice_item = InvoiceItem(item_description='test', amount='100')
        self.yearly_schedule.invoice_items.append(invoice_item)
        self.session.flush()
        self.assertTrue( 'Invoices are planned after redemption' in unicode(self.transaction.note) )
        for invoice_item in self.yearly_schedule.invoice_items:
            if invoice_item.doc_date >= self.transaction.from_date:
                self.session.delete(invoice_item)
        self.session.flush()
        self.session.expire_all()
        self.assertFalse( self.transaction.note)
        self.button(self.transaction, self.remove_future_order_lines)
        self.button(self.transaction, self.status_complete)
        self.assertFalse(self.transaction.note)
        self.button(self.transaction, self.transaction_status_verified)
        self.assertFalse(self.transaction.note)
        self.assertEqual(self.yearly_schedule.payment_thru_date, datetime.date(2014, 9, 6))
        self.assertEqual(self.yearly_schedule.version_id, original_version_id+1)
        self.assertEqual(self.transaction_premium_schedule.previous_version_id, original_version_id)
        # a previous version of the premium schedule should be available
        history = FinancialAccountPremiumScheduleHistory.get_previous_version(self.yearly_schedule)
        self.assertEqual(history.version_id, original_version_id)
        self.assertEqual(history.payment_thru_date, datetime.date(2400, 12, 31))
        # run the transaction visitor, which should make it impossible to
        # undo the transaction verification
        list(self.visitor.visit_premium_schedule(self.yearly_schedule, self.transaction.from_date + datetime.timedelta(days=1)))
        with self.assertRaises(UserException):
            self.button(self.transaction, self.transaction_status_undo_verified)
        self.button(self.transaction, self.remove_future_order_lines)
        self.button(self.transaction, self.transaction_status_undo_verified)
        self.assertEqual(self.yearly_schedule.payment_thru_date, datetime.date(2400, 12, 31))
        self.assertTrue(u'modified' in unicode(self.transaction.note))
        with self.assertRaises(UserException):
            self.button(self.transaction, self.transaction_status_verified)

    def test_fund_distribution_editability_on_status(self):
        adm = self.app_admin.get_related_admin(FinancialTransactionFundDistribution)
        self.transaction.change_status('draft')
        current_status = self.transaction.current_status
        self.assertEqual('draft', current_status)
        for schedule in self.transaction.consisting_of:
            for distr in schedule.fund_distribution:
                attribs = adm.get_dynamic_field_attributes(distr, adm.list_display)
                self.assertNotEqual([], attribs)
                for attr in attribs:
                    if(attr['editable']):
                        break
                else:
                    self.fail("No editable fields despite status %r" % current_status)
        self.transaction.change_status('verified')
        current_status = self.transaction.current_status
        self.assertEqual('verified', current_status)
        for schedule in self.transaction.consisting_of:
            for distr in schedule.fund_distribution:
                attribs = adm.get_dynamic_field_attributes(distr, adm.list_display)
                for attr in attribs:
                    self.assertEqual(False, attr['editable'])
