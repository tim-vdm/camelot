import datetime
from decimal import Decimal as D
from sqlalchemy import orm

from camelot.core.exception import UserException
from camelot.test.action import MockModelContext

from vfinance.connector.accounting import AccountingRequest
from vfinance.model.bank import entry, invoice
from vfinance.model.bank.product import ProductFeatureApplicability
from vfinance.model.bank.visitor import ProductBookingAccount
from vfinance.model.financial import admin as financial_admin
from vfinance.model.financial import (premium, agreement, visitor, feature,
                                      commission, account, fund)
from vfinance.model.insurance import account as insurance_account
from vfinance.model.financial.visitor.abstract import AbstractVisitor

from . import test_package


class AbstractFinancialAgreementPremiumScheduleCase(test_package.AbstractFinancialPackageCase):

    @classmethod
    def setUpClass(cls):
        test_package.AbstractFinancialPackageCase.setUpClass()
        cls.agreement = agreement.FinancialAgreement(
            agreement_date = cls.t0,
            from_date = cls.t1,
            code = cls.next_agreement_code(),
            package = cls.package,
        )
        cls.agreed_yearly_schedule = premium.FinancialAgreementPremiumSchedule(
            product = cls.product,
            duration = 5*12,
            payment_duration = None,
            period_type = 'yearly',
            amount = 1500,
            financial_agreement = cls.agreement,
        )
        cls.agreed_monthly_schedule = premium.FinancialAgreementPremiumSchedule(
            product = cls.product,
            duration = 200*12,
            payment_duration = None,
            period_type = 'monthly',
            amount = 50,
            financial_agreement = cls.agreement,
        )
        cls.session.flush()

    def setUp(self):
        super(AbstractFinancialAgreementPremiumScheduleCase, self).setUp()
        self.session.add(self.agreement)

class AbstractFinancialAccountPremiumScheduleCase(AbstractFinancialAgreementPremiumScheduleCase):

    @classmethod
    def setUpClass(cls):
        AbstractFinancialAgreementPremiumScheduleCase.setUpClass()
        cls.setup_accounting_period()
        cls.account = account.FinancialAccount(package=cls.package)
        cls.account.change_status('active')
        cls.session.flush()
        from_date = cls.agreement.from_date
        cls.yearly_schedule = premium.FinancialAccountPremiumSchedule(
            agreed_schedule = cls.agreed_yearly_schedule,
            period_type = cls.agreed_yearly_schedule.period_type,
            financial_account = cls.account,
            product = cls.product,
            premium_amount = cls.agreed_yearly_schedule.amount,
            account_number = premium.FinancialAccountPremiumSchedule.new_account_number(cls.product, cls.account),
            valid_from_date = from_date,
        )
        cls.monthly_schedule = premium.FinancialAccountPremiumSchedule(
            agreed_schedule = cls.agreed_monthly_schedule,
            period_type = cls.agreed_monthly_schedule.period_type,
            financial_account = cls.account,
            product = cls.product,
            premium_amount = cls.agreed_monthly_schedule.amount,
            account_number = premium.FinancialAccountPremiumSchedule.new_account_number(cls.product, cls.account),
            valid_from_date = from_date,
        )
        fund.FinancialAccountFundDistribution(
            distribution_of = cls.yearly_schedule,
            from_date = from_date,
            fund = cls.fund,
            target_percentage = 100,
        )
        feature.FinancialAccountPremiumScheduleFeature(
            applied_on = cls.yearly_schedule,
            described_by = 'maximum_legal_exit_rate',
        )
        # percentages 60/40 are chose to result in worst case rounding
        commission.FinancialAccountCommissionDistribution(
            premium_schedule = cls.yearly_schedule,
            described_by = 'funded_premium_rate_1',
            recipient = 'master_broker',
            distribution = D(60),
        )
        commission.FinancialAccountCommissionDistribution(
            premium_schedule = cls.yearly_schedule,
            described_by = 'funded_premium_rate_1',
            recipient = 'broker',
            distribution = D(40),
        )
        invoice.InvoiceItem(premium_schedule = cls.yearly_schedule,
                            amount=cls.agreed_yearly_schedule.amount,
                            item_description='monthly premium')
        insurance_account.InsuranceAccountCoverage(
            premium = cls.yearly_schedule,
            coverage_for = cls.coverage_level,
        )
        account.FinancialAccountRole(
            financial_account = cls.account,
            from_date = cls.tp,
            natuurlijke_persoon = cls.get_or_create_natuurlijke_persoon(),
        )
        account.FinancialAccountRole(
            financial_account = cls.account,
            from_date = cls.tp,
            natuurlijke_persoon = cls.get_or_create_natuurlijke_persoon(),
            described_by = 'insured_party'
        )
        account.FinancialAccountBroker(
            financial_account = cls.account,
            from_date = cls.tp,
            broker_relation = cls.commercial_relation,
        )
        cls.premium_schedule_model_context = MockModelContext()
        cls.premium_schedule_model_context.obj = cls.yearly_schedule
        cls.premium_schedule_model_context.admin = cls.app_admin.get_related_admin(premium.FinancialAccountPremiumSchedule)
        cls.session.flush()

    def setUp(self):
        super(AbstractFinancialAccountPremiumScheduleCase, self).setUp()
        self.session.add(self.account)
        self.session.add(self.yearly_schedule)
        self.session.add(self.monthly_schedule)
        self.session.add(self.base_product)
        self.session.add(self.product)

class TestFinancialAgreementPremiumScheduleCase(AbstractFinancialAgreementPremiumScheduleCase):

    def test_planned_premiums_yearly( self ):
        self.agreement.from_date = datetime.date(2010,1,1)
        self.assertEqual( self.agreed_yearly_schedule.planned_premiums, 5 )
        self.assertEqual( self.agreed_yearly_schedule.valid_thru_date, datetime.date( 2015, 1, 1 ) )
        self.assertEqual( self.agreed_yearly_schedule.payment_thru_date, datetime.date( 2015, 1, 1 ) )
        self.assertEqual( self.agreed_yearly_schedule.get_premiums_due_at( datetime.date( 2010, 1, 1 ) ), 1 )
        self.assertEqual( self.agreed_yearly_schedule.get_premiums_due_at( datetime.date( 2015, 1, 1 ) ), 5 )
        self.agreement.from_date = datetime.date( 2012, 9, 7 )
        self.assertEqual( self.agreed_yearly_schedule.valid_thru_date, datetime.date( 2017, 9, 7 ) )
        self.assertEqual( self.agreed_yearly_schedule.payment_thru_date, datetime.date( 2017, 9, 7 ) )
        self.assertEqual( self.agreed_yearly_schedule.planned_premiums, 5 )
        
    def test_planned_premiums_monthly( self ):
        self.agreement.from_date = datetime.date( 2010, 12, 30 )
        self.assertEqual( self.agreed_monthly_schedule.valid_thru_date, datetime.date( 2210, 12, 30 ) )
        self.assertEqual( self.agreed_monthly_schedule.valid_thru_date, datetime.date( 2210, 12, 30 ) )
        self.assertEqual( self.agreed_monthly_schedule.get_premiums_due_at( datetime.date( 2011, 1,  1 ) ), 1 )
        self.assertEqual( self.agreed_monthly_schedule.get_premiums_due_at( datetime.date( 2011, 2,  1 ) ), 2 )
        self.assertEqual( self.agreed_monthly_schedule.get_premiums_due_at( datetime.date( 2011, 5,  1 ) ), 5 )
        self.assertEqual( self.agreed_monthly_schedule.get_premiums_due_at( datetime.date( 2011, 5, 30 ) ), 6 )

class TestFinancialAccountPremiumScheduleCase(AbstractFinancialAccountPremiumScheduleCase):

    def test_heal( self ):
        heal_action = financial_admin.Heal()
        list( heal_action.model_run( self.premium_schedule_model_context ) )
        
    def test_related_entries( self ):
        related_entries_action = financial_admin.RelatedEntries(premium.FinancialAccountPremiumFulfillment)
        list( related_entries_action.model_run( self.premium_schedule_model_context ) )
        
    def test_run_forward( self ):
        run_forward_action = financial_admin.RunForward()
        list( run_forward_action.model_run( self.premium_schedule_model_context ) )
              
    def test_run_backward( self ):
        run_backward_action = financial_admin.RunBackward()
        for i, step in enumerate(run_backward_action.model_run(self.premium_schedule_model_context)):
            if i == 0:
                options = step.get_object()
                options.from_document_date = self.yearly_schedule.valid_from_date

    def test_store_restore_version(self):
        FAPSH = premium.FinancialAccountPremiumScheduleHistory
        current_version = self.yearly_schedule.version_id
        #
        # storing and restoring only makes sense within a transaction
        #
        with self.assertRaises(Exception):
            FAPSH.store_version(self.yearly_schedule)
        with self.assertRaises(Exception):
            FAPSH.restore_version(self.yearly_schedule)
        #
        # a previous version should not be available yet
        #
        with self.assertRaises(UserException):
            FAPSH.get_previous_version(self.yearly_schedule)
        #
        # storing or restoring should fail if the current version in the database
        # does not match the current version of the object
        #
        history_table = premium.FinancialAccountPremiumScheduleHistory.__table__
        bump_version = history_table.update().values(version_id=history_table.c.version_id+1,
                                                     from_date=datetime.date.today()-datetime.timedelta(days=3))
        self.session.execute(bump_version.where(history_table.c.id==self.yearly_schedule.id))
        with self.session.begin():
            with self.assertRaises(UserException):
                FAPSH.store_version(self.yearly_schedule)
            with self.assertRaises(UserException):
                FAPSH.restore_version(self.yearly_schedule)
        self.session.expire(self.yearly_schedule)
        current_version = self.yearly_schedule.version_id
        #
        # modifying the premium schedule should bump the version, update the
        # from date of the current schedule, and the previous version should
        # be available as history
        #
        self.assertEqual(self.yearly_schedule.direct_debit, False)
        history = FAPSH.get_current_version(self.yearly_schedule)
        self.assertNotEqual(history.from_date, datetime.date.today())
        with self.session.begin():
            FAPSH.store_version(self.yearly_schedule)
            self.yearly_schedule.direct_debit = True
            new_version = current_version+1
        self.assertEqual(self.yearly_schedule.direct_debit, True)
        self.assertEqual(self.yearly_schedule.version_id, new_version)
        current_history = FAPSH.get_current_version(self.yearly_schedule)
        self.assertEqual(current_history.from_date, datetime.date.today())
        self.assertEqual(current_history.version_id, current_version+1)
        previous_history = FAPSH.get_previous_version(self.yearly_schedule)
        self.assertEqual(previous_history.thru_date, datetime.date.today() - datetime.timedelta(days=1))
        self.assertEqual(previous_history.version_id, current_version)
        self.assertEqual(previous_history.direct_debit, False)

    def test_validity_dates(self):
        #
        # make sure the from and thru date don't show up in the object model by accident
        #
        with self.assertRaises(AttributeError):
            self.yearly_schedule.from_date
        with self.assertRaises(AttributeError):
            self.yearly_schedule.thru_date
        self.assertTrue(self.yearly_schedule.valid_from_date)
        self.assertTrue(self.yearly_schedule.valid_thru_date)
        #
        # test if the from and thru date in the table exist and have values
        #
        premium_schedule_table = self.yearly_schedule.__table__
        self.assertTrue(premium_schedule_table.c.from_date is not None)
        self.assertTrue(premium_schedule_table.c.thru_date is not None)
        premium_schedule_query = premium_schedule_table.select().where(premium_schedule_table.c.id==self.yearly_schedule.id)
        for row in self.session.execute(premium_schedule_query):
            pass
        self.assertEqual(row['from_date'], datetime.date.today())
        self.assertEqual(row['thru_date'], datetime.date(2400, 12, 31))

    def test_premium_to_pending( self ):
        premium_to_pending_action = financial_admin.PremiumToPending()
        # first, make sure there is a fulfillment
        self.fulfill_agreement(self.agreement, amount=self.yearly_schedule.premium_amount)
        list(self.synchronizer.attribute_pending_premiums())
        fulfillment_query = premium.FinancialAccountPremiumFulfillment.query
        fulfillment_query = fulfillment_query.filter_by(of=self.yearly_schedule,
                                                        fulfillment_type='premium_attribution')
        fulfillment_query = fulfillment_query.order_by(premium.FinancialAccountPremiumFulfillment.entry_book_date.desc())
        fulfillment = fulfillment_query.first()
        
        self.assertTrue(fulfillment)
        self.assertEqual(self.yearly_schedule.last_premium_attribution, fulfillment.entry_book_date)
        premium_entry = fulfillment.entry
        original_account = premium_entry.account
        customer_attribution_visitor = visitor.CustomerAttributionVisitor()
        for doc_date in customer_attribution_visitor.get_document_dates( self.yearly_schedule, 
                                                                         self.yearly_schedule.valid_from_date,
                                                                         self.yearly_schedule.valid_thru_date ):
            self.visit_premium_schedule(customer_attribution_visitor, self.yearly_schedule, doc_date)
        self.session.expire(premium_entry)
        self.assertNotEqual( premium_entry.account, original_account )
        model_context = MockModelContext()
        model_context.obj = fulfillment
        list( premium_to_pending_action.model_run( model_context ) )
        self.session.expire(premium_entry)
        self.assertEqual( premium_entry.account, original_account )
        self.session.expire(self.yearly_schedule)
        self.assertEqual(self.yearly_schedule.last_premium_attribution, None)
        
    def test_get_account_type_at( self ):
        self.assertEqual( self.yearly_schedule.get_account_type_at( '1234', datetime.date( 2010,12,31 ) ), 'pending_premiums' )
        self.assertEqual(  self.yearly_schedule.get_account_type_at( self.first_premium_rate_1_account, datetime.date( 2010,1,1 ) ), 'premium_rate_1_revenue' )
        self.assertEqual(  self.yearly_schedule.get_account_type_at( self.second_premium_rate_1_account, datetime.date( 2012,1,1 ) ), 'premium_rate_1_revenue' )
        with self.assertRaises( Exception ):
            self.yearly_schedule.get_account_type_at( self.first_premium_rate_1_account, datetime.date( 2012,1,1 ) )
        with self.assertRaises( Exception ):
            self.yearly_schedule.get_account_type_at( self.second_premium_rate_1_account, datetime.date( 2010,1,1 ) )
            
    def test_create_revert_sales( self ):
        visitor = AbstractVisitor()
        line = visitor.create_line( ProductBookingAccount('risk_revenue'), 
                                    10, 
                                    '', 
                                    fulfillment_type = 'profit_attribution' )
        doc_date = datetime.date( 2011,  3, 30 )
        book_date = datetime.date( 2011,  4, 30 )
        #
        # create a first booking
        #
        session = orm.object_session( self.yearly_schedule )
        with self.accounting.begin(session):
            customer_request = visitor.create_customer_request(self.yearly_schedule, self.yearly_schedule.financial_account.get_roles_at(doc_date, 'subscriber'))
            self.accounting.register_request(customer_request)
        with self.accounting.begin(session):
            for step in visitor.create_sales( self.yearly_schedule, book_date, doc_date, -10, [line], 'TEST', 'capital_redemption_deduction' ):
                self.accounting.register_request(step)
        self.assertEqual( visitor.get_total_amount_at( self.yearly_schedule,
                                                       doc_date,
                                                       fulfillment_type = 'profit_attribution' )[0], 10 )
        self.assertEqual( visitor.get_total_amount_at( self.yearly_schedule,
                                                       doc_date,
                                                       fulfillment_type = 'capital_redemption_deduction' )[0], -10 )
        entries = list ( visitor.get_entries( self.yearly_schedule, doc_date ) )
        self.assertEqual( len(entries), 2 )
        #
        # revert the booking
        #
        with self.accounting.begin(session):
            for step in visitor.create_revert_request(self.yearly_schedule, entries):
                self.accounting.register_request(step)
        self.assertEqual( visitor.get_total_amount_at( self.yearly_schedule,
                                                       doc_date,
                                                       fulfillment_type = 'profit_attribution' )[0], 0 )
        self.assertEqual( visitor.get_total_amount_at( self.yearly_schedule,
                                                       doc_date,
                                                       fulfillment_type = 'capital_redemption_deduction' )[0], 0 ) 
        self.assertEqual( len( list ( visitor.get_entries( self.yearly_schedule,
                                                           doc_date ) ) ), 0 )
        #
        # try to revert the same booking twice
        #
        requests = []
        with self.accounting.begin(session):
            for step in visitor.create_revert_request(self.yearly_schedule, entries):
                requests.append(step)
                self.accounting.register_request(step)
        self.assertEqual(requests, [])
        #
        # now run back the premium schedule, this should not remove the
        # reverted booking
        #
        entry_query = entry.Entry.fulfillment_query(session, premium.FinancialAccountPremiumFulfillment, entry.Entry, premium.FinancialAccountPremiumFulfillment )
        entry_query = entry_query.filter( premium.FinancialAccountPremiumFulfillment.of == self.yearly_schedule )
        entry_count = entry_query.count()
        run_backward_action = financial_admin.RunBackward()
        for i, step in enumerate( run_backward_action.model_run( self.premium_schedule_model_context ) ):
            if i == 0:
                step.get_object().from_document_date = doc_date
                step.get_object().reason = 'unittest'
        new_entry_count = entry_query.count()
        self.assertEqual( entry_count, new_entry_count )

    def test_create_revert_purchase(self):
      visitor = AbstractVisitor()
      cost_account = ProductBookingAccount('premium_rate_1_cost_broker')
      line = visitor.create_line( cost_account, 
                                  10, 
                                  '', 
                                  fulfillment_type = 'sales_distribution' )
      doc_date = datetime.date( 2011,  3, 30 )
      book_date = datetime.date( 2011,  4, 30 )
      #
      # create a first booking
      #
      session = orm.object_session( self.yearly_schedule )
      with self.accounting.begin(session):
          broker_relation = self.yearly_schedule.financial_account.get_broker_at(doc_date)
          supplier_request = visitor.create_supplier_request(self.yearly_schedule, broker_relation, 'broker')
          self.accounting.register_request(supplier_request)
      with self.accounting.begin(session):
          for step in visitor.create_purchase(self.yearly_schedule, book_date, doc_date, [line], 'TEST', 'sales_distribution', 'broker'):
              self.accounting.register_request(step)
      self.assertEqual( visitor.get_total_amount_at( self.yearly_schedule,
                                                     doc_date,
                                                     account = cost_account)[0], 10 )
      #
      # see if the accounts can be retrieved from the entries
      #
      entries = list(visitor.get_entries(self.yearly_schedule, from_document_date=doc_date, thru_document_date=doc_date, fulfillment_type='sales_distribution'))
      self.assertEqual(len(entries), 2)
      for e in entries:
          self.assertTrue(visitor.get_booking_account(self.yearly_schedule, e.account, book_date))
      #
      # revert the booking
      #
      revert_purchase = None
      with self.accounting.begin(session):
          for step in visitor.create_revert_request(self.yearly_schedule, entries):
              revert_purchase = step
              if isinstance(step, AccountingRequest):
                  self.accounting.register_request(revert_purchase)
      self.assertTrue(revert_purchase)
      self.assertEqual( visitor.get_total_amount_at( self.yearly_schedule,
                                                     doc_date,
                                                     account = cost_account)[0], 0 )

    def test_features(self):
        t1 = datetime.date(2012,1,1)
        t2 = datetime.date(2012,6,1)
        self.base_product.available_with.append(
            ProductFeatureApplicability(apply_from_date=t1,
                                        premium_from_date=self.t0,
                                        value=1,
                                        described_by='interest_rate')
        )    
        self.base_product.available_with.append(
            ProductFeatureApplicability(apply_from_date=t1,
                                        premium_from_date=self.t0,
                                        value=7,
                                        described_by='additional_interest_rate')
        )
        self.product.available_with.append(
            ProductFeatureApplicability(apply_from_date=t2,
                                        premium_from_date=self.t0,
                                        value=2,
                                        described_by='interest_rate')
        )
        self.session.flush()
        self.assertEqual( self.yearly_schedule.get_applied_feature_at(t1, t1, 0, 'interest_rate').value, 1 )
        self.assertEqual( self.yearly_schedule.get_applied_feature_at(t2, t2, 0, 'interest_rate').value, 2 )
        switch_dates = self.yearly_schedule.get_all_features_switch_dates(t2)
        self.assertTrue( t2 in switch_dates )
        self.assertTrue( t1 in switch_dates )
        self.assertTrue( self.yearly_schedule.has_feature_between(t1, t2, 'additional_interest_rate') )

    def editability_on_account_status(self, tested_attr_class, tested_attr_name):
        adm = self.app_admin.get_related_admin(tested_attr_class)
        # Set financial account status to 'delayed'
        self.yearly_schedule.financial_account.change_status('delayed')
        attribute = getattr(self.yearly_schedule, tested_attr_name)
        self.assertNotEqual([], attribute)
        # Verify that some of the fields are editable
        for entr in attribute:
            attribs = adm.get_dynamic_field_attributes(entr, adm.list_display)
            self.assertNotEqual([], attribs)
            for attr in attribs:
                if(attr['editable']):
                    break
            else:
                self.fail("No editable fields despite status 'delayed'")
        # Set financial account status to 'active
        self.yearly_schedule.financial_account.change_status('active')
        # Verify that none of the fields are editable
        for entr in getattr(self.yearly_schedule, tested_attr_name):
            attribs = adm.get_dynamic_field_attributes(entr, adm.list_display)
            for attr in attribs:
                self.assertFalse(attr['editable'])

    def test_insurance_editability_on_account_status(self):
        self.editability_on_account_status(insurance_account.InsuranceAccountCoverage,
                                           'applied_coverages')

    def test_commission_distribution_editability_on_account_status(self):
        self.editability_on_account_status(commission.FinancialAccountCommissionDistribution,
                                           'commission_distribution')

    def test_applied_features_editability_on_account_status(self):
        self.editability_on_account_status(feature.FinancialAccountPremiumScheduleFeature,
                                           'applied_features')

    def test_invoice_items_editability_on_account_status(self):
        self.editability_on_account_status(invoice.InvoiceItem,
                                           'invoice_items')
