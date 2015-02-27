import datetime

from sqlalchemy import sql

from camelot.model.fixture import Fixture
from camelot.model.authentication import end_of_times

from vfinance.connector.accounting import (
    AccountingSingleton,
    AccountingRequest,
    CreateSalesDocumentRequest,
    LineRequest,
)

from vfinance.model.bank import statusmixin
from vfinance.model.bank.accounting import AccountingPeriod
from vfinance.model.bank.direct_debit import BankIdentifierCode
from vfinance.model.bank.entry import Entry, EntryPresence
from vfinance.model.bank.product import ProductAccount
from vfinance.model.financial.synchronize import FinancialSynchronizer
from vfinance.model.financial.agreement import FinancialAgreement
from vfinance.model.financial.package import FinancialPackage
from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment as FAPF
from vfinance.model.financial.visitor.joined import JoinedVisitor

class FinancialMixinCase(object):
    """
    Utility functions to be used in financial model unit tests
    """

    code = u'000/0000/00202'

    tp  = datetime.date(2009, 12, 31) # Time of product definition
    t0  = datetime.date(2010,  1,  1)
    t1  = datetime.date(2010,  2,  1)
    t3  = datetime.date(2010,  2,  3)
    t4  = max( t3, t1 )
    t6  = datetime.date(2010,  2, 20)
    t7  = datetime.date(2010,  3,  2)
    t8  = datetime.date(2010, 3, 22)
    t9  = max(t4, t8, t7 + datetime.timedelta(days=7) )
    t11 = datetime.date(2010, 4, 15)
    t12 = t11 + datetime.timedelta(days=2)
    t15 = datetime.date(2010,  4,  1)
    t13 = datetime.date(2010,  3,  1)
    t14 = datetime.date(2010,  3, 25)
    t17 = datetime.date(2011,  3, 31)
    t20 = datetime.date(2010, 6, 20)
    t21 = datetime.date(2010, 7, 2)
    t22 = max( t20, t21 )
    t23_1 = datetime.date(2010, 7, 15)
    t23_2 = datetime.date(2010, 7, 15)
    t26 = max( t23_1, t23_2 )

    first_premium_rate_1_account = '720111201'
    second_premium_rate_1_account = '730111201'
    premium_fee_1_revenue_account = '72411001'

    accounting = AccountingSingleton()
    synchronizer = FinancialSynchronizer(t17)
    visitor = JoinedVisitor(accounting)
    status_complete = statusmixin.StatusComplete()
    status_verified = statusmixin.StatusVerified()
    status_draft = statusmixin.StatusDraft()
    status_cancel = statusmixin.StatusCancel()
    status_incomplete = statusmixin.StatusIncomplete()

    @classmethod
    def setup_accounting_period(cls):
        if cls.session.query(AccountingPeriod).count() == 0:
            AccountingPeriod(from_date = datetime.date( 2000, 1, 1 ),
                             thru_date = end_of_times(),
                             from_book_date = datetime.date( 2000, 1, 1 ),
                             thru_book_date = end_of_times(),
                             from_doc_date = datetime.date( 2000, 1, 1 ),
                             thru_doc_date = end_of_times() )
            cls.session.flush()

    @classmethod
    def setup_bic(cls):
        cls.bic_1 = Fixture.insert_or_update_fixture(
            BankIdentifierCode, 'bnp', fixture_class='unittests',
            values=dict(country='BE', code='GEBABEBB', name='BNP Paribas'))
        cls.bic_2 = Fixture.insert_or_update_fixture(
            BankIdentifierCode, 'key', fixture_class='unittests',
            values=dict(country='BE', code='KEYTBEBB', name='Keytrade Bank'))

    @classmethod
    def next_agreement_code(cls):
        start = 2600000000
        q = cls.session.query(sql.func.max(FinancialAgreement.id))
        max = q.scalar()
        if max is None:
            max = 0
        max += 1
        str_nummer = str(start + max*1000)
        return '/'.join([str_nummer[0:3], str_nummer[3:7], str_nummer[7:]+'%02i'%((start + max*1000)%97)])

    @classmethod
    def next_from_supplier(cls):
        q = cls.session.query(sql.func.max(FinancialPackage.thru_supplier))
        max = q.scalar()
        if max is None:
            max = 0
        max += 1
        return max

    @classmethod
    def create_accounts_for_product(cls, product ):

        #
        # add an account that changes over time
        #
        ProductAccount(
            available_for = product,
            described_by = 'premium_rate_1_revenue',
            number = cls.first_premium_rate_1_account,
            from_date = datetime.date( 2000, 1, 1 ),
            thru_date = datetime.date( 2010,12,31 ),
        )
        ProductAccount(
            available_for = product,
            described_by = 'premium_rate_1_revenue',
            number = cls.second_premium_rate_1_account,
            from_date = datetime.date( 2011,1,1 ),
        )

        for account_type, account_number in [
            ( 'capital_cost', '6' ),
            ( 'capital_revenue', '7' ),
            ( 'provisions', '1' ),
            ( 'provisions_cost','6' ),
            ( 'taxes', '4251233' ),
            ( 'premium_fee_1_revenue', cls.premium_fee_1_revenue_account ),
            ( 'premium_fee_1_revenue_master_broker', '7241100101' ),
            ( 'premium_fee_1_revenue_broker', '7241100102' ),
            ( 'premium_fee_2_revenue', '72411002' ),
            ( 'premium_fee_3_revenue', '72411003' ),
            ( 'funded_premium_attribution_cost', '65' ),
            ( 'funded_premium_attribution_revenue', '75' ),
            ( 'funded_premium', '4' ),
            ( 'funded_premium_master_broker', '401' ),
            ( 'funded_premium_broker', '402' ),
            ( 'funded_premium_cost', '625' ),
            #( 'premium_rate_1_revenue', '720111201' ),
            ( 'premium_rate_1_revenue_master_broker', '72011120101' ),
            ( 'premium_rate_1_revenue_broker', '72011120102' ),
            ( 'premium_rate_2_revenue', '720111202' ),
            ( 'premium_rate_3_revenue', '720111203' ),
            ( 'premium_rate_4_revenue', '720111204' ),
            ( 'premium_rate_5_revenue', '720111205' ),
            # use the same account for fee 4 as rate 1 to make sure only one amount
            # is booked
            ( 'premium_fee_4_revenue_broker', '72011120102' ),
            ( 'entry_fee_revenue', '72411000' ),
            ( 'pending_premiums', '1234' ),
            ( 'interest_cost', '65' ),
            ( 'additional_interest_cost', '66' ),
            ( 'redemption_rate_revenue', '721' ),
            ( 'redemption_fee_revenue', '722' ),
            ( 'redemption_revenue', '723' ),
            ( 'redemption_cost', '6' ),
            ( 'effective_interest_tax', '421434' ),
            ( 'fictive_interest_tax', '421435' ),
            ( 'switch_revenue', '724' ),
            ( 'switch_deduction_revenue', '7' ),
            ( 'switch_deduction_cost', '6' ),
            ( 'financed_commissions_interest', '71' ),
            ( 'financed_commissions_revenue', '73' ),
            ( 'financed_commissions_cost', '6234' ),
            ( 'risk_revenue', '7' ),
            ( 'risk_deduction_cost', '6' ),
            ( 'risk_deduction_revenue', '7' ),
            ( 'quotation_revenue', '7' ),
            ( 'quotation_cost', '6' ),
            ( 'distributed_medical_fee_revenue', '725' ),
            ( 'profit_attribution_cost', '626' ),
            ( 'profit_attribution_revenue', '726' ),
            ( 'profit_reserve', '144' ),
            ( 'market_fluctuation_revenue', '727' ),
            ( 'premium_rate_1_cost_broker', '623311'),
            ( 'premium_fee_1_cost_broker', '623312'),
            ( 'premium_rate_2_cost_broker', '623321'),
            ( 'premium_fee_2_cost_broker', '623322'),
            ( 'premium_rate_3_cost_broker', '623331'),
            ( 'premium_fee_3_cost_broker', '623332'),
            ( 'premium_rate_4_cost_broker', '623341'),
            ( 'premium_fee_4_cost_broker', '623311'),
            ( 'premium_rate_5_cost_broker', '623351'),
            ( 'premium_fee_5_cost_broker', '623352'),
            ( 'entry_fee_cost_broker', '62336'),
            ( 'financed_commissions_revenue_broker', '7301' ),
            ( 'financed_commissions_cost_broker', '623401' ),
                ]:
            ProductAccount(
                available_for = product,
                described_by = account_type,
                number = account_number,
                from_date = datetime.date( 2000, 1, 1 ))

    @classmethod
    def visit_premium_schedule(cls, visitor, premium_schedule, at):
        """
        Visit a premium schedule at a specific date with a specific visitor
        """
        with cls.accounting.begin(cls.session):
            customer_request = visitor.create_customer_request(premium_schedule, premium_schedule.financial_account.get_roles_at(at, 'subscriber'))
            cls.accounting.register_request(customer_request)
            broker_relation = premium_schedule.financial_account.get_broker_at(at)
            for supplier_type in ['broker', 'master_broker']:
                supplier_request = visitor.create_supplier_request(premium_schedule, broker_relation, supplier_type)
                if supplier_request is not None:
                    cls.accounting.register_request(supplier_request)
        with cls.accounting.begin(cls.session):
            for step in visitor.visit_premium_schedule(premium_schedule, at):
                if isinstance(step, AccountingRequest):
                    cls.accounting.register_request(step)

    @classmethod
    def fulfill_agreement(cls,
                          agreement,
                          fulfillment_date=None,
                          amount=None,
                          remark=None):

        # make sure we use unique document numbers
        q = cls.session.query(sql.func.max(Entry.venice_doc))
        max = q.scalar() or 0

        amount = float( str( (amount or agreement.amount_due) * -1) )
        remark = remark or u'***' + agreement.code + u'***'

        entry = Entry(amount=amount,
                      account=u'1234',
                      open_amount=amount,
                      remark=remark,
                      ticked=False,
                      line_number=1,
                      venice_doc= max + 1,
                      venice_book=u'KBC',
                      venice_book_type=u'F',
                      book_date=fulfillment_date or datetime.date(2010, 2, 5),
                      datum = fulfillment_date or cls.t3 )

        EntryPresence(entry=entry, venice_active_year='2010', venice_id=1)
        cls.session.flush()
        cls.session.expire_all()
        return entry

    @classmethod
    def insert_entry( cls, premium_schedule, book_date, doc_date, account, amount,
                      fulfillment_type = None, associated_to_id = None,
                      quantity = 0):
        cls.accounting.begin(cls.session)
        sales_document = CreateSalesDocumentRequest(
            book_date  =  book_date,
            document_date = doc_date,
            book = 'S',
            lines = [
                LineRequest(account='1111', amount=amount*-1, quantity=0),
                LineRequest(account=account, amount=amount, quantity=quantity * 1000),
                ])
        cls.accounting.register_request(sales_document)
        fapf_insert = FAPF.__table__.insert()
        for line in sales_document.lines:
            result = fapf_insert.execute(
                of_id = premium_schedule.id,
                entry_book_date = book_date,
                entry_document = sales_document.document_number,
                entry_book = 'S',
                entry_line_number = line.line_number,
                fulfillment_type = fulfillment_type,
                associated_to_id = associated_to_id,
                within_id = None,
                from_date = datetime.date(2000,1,1),
                thru_date = datetime.date(2400,1,1),
            )
        cls.accounting.commit()
        return result.inserted_primary_key[0]