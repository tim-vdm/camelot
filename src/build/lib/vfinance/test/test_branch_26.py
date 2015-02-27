import datetime
from xml.etree import ElementTree

from camelot.admin.action import ApplicationActionModelContext
from camelot.core.exception import UserException
from camelot.test.action import MockModelContext
from camelot.view.action_steps import ChangeObject
from camelot.view import action_steps

from vfinance.model.bank.product import ProductFeatureApplicability
from vfinance.model.financial.notification.transaction_document import TransactionDocument
from vfinance.model.financial.transaction import TransactionStatusVerified
from vfinance.model.financial.visitor.abstract import FinancialBookingAccount, ProductBookingAccount
from vfinance.facade.redemption import CompleteRedemption

from test_financial import AbstractFinancialCase

import logging

logger = logging.getLogger('vfinance.test.test_branch_26')

from decimal import Decimal as D

class Branch26Case(AbstractFinancialCase):
    
    code = u'000/0000/00101'
    t9 = AbstractFinancialCase.t4
    
    def setUp( self ):
        AbstractFinancialCase.setUp( self )
        from vfinance.model.bank.entry import Entry
        from vfinance.model.financial.package import (FinancialPackage, FinancialNotificationApplicability, FinancialProductAvailability, FinancialBrokerAvailability,
                                                      FunctionalSettingApplicability)
        from vfinance.model.financial.product import FinancialProduct
        for e in Entry.query.filter( Entry.remark.like( u'%' + self.code + u'%' ) ):
            e.delete()
        self.tp = datetime.date( 2008, 1, 1 )
        self._package = FinancialPackage(name='Fork Rekening',
                                         from_customer = 400000,
                                         thru_customer = 499999,
                                         from_supplier = 8000,
                                         thru_supplier = 9000,
                                         )
        account_number_prefix = self.next_account_number_prefix()
        self._base_product = FinancialProduct(name='Branch 26',
                                              account_number_prefix = account_number_prefix,
                                              account_number_digits = 6
                                              )
        self._product = FinancialProduct(name='Fork Rekening',
                                         specialization_of=self._base_product,
                                         from_date=self.tp,
                                         account_number_prefix = account_number_prefix,
                                         account_number_digits = 6,
                                         premium_sales_book = 'VPrem',
                                         premium_attribution_book = u'DOMTV',
                                         depot_movement_book = u'RESBE',
                                         interest_book = u'INT',
                                         redemption_book = 'REDEM',
                                         supplier_distribution_book = u'COM',
                                         )
        FinancialProductAvailability( available_for = self._package,
                                      product = self._product,
                                      from_date = self.tp )
        self.create_accounts_for_product( self._product )
        
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='interest_rate', value=D('2.1'),
                                    overrule_required = True)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='effective_interest_tax_rate', value=D('15'))
        
        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = datetime.date(2000,1,1),
                                           notification_type = 'certificate',
                                           template = 'time_deposit/certificate_branch26_nl_BE.xml',
                                           language = 'nl',
                                           premium_period_type = None)
        
        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = datetime.date(2000,1,1),
                                           notification_type = 'certificate',
                                           template = 'time_deposit/certificate_rentdeposit_addendum_nl_BE.xml',
                                           language = 'nl',
                                           premium_period_type = None)
        
        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = self.tp,
                                           notification_type = 'transaction-completion',
                                           template = 'time_deposit/transaction_nl_BE.xml',
                                           language = None,)
        FinancialBrokerAvailability( available_for = self._package,
                                     broker_relation = self.rechtspersoon_case.broker_relation,
                                     from_date = self.tp )
        FunctionalSettingApplicability(available_for = self._package,
                                       described_by = 'exit_at_first_decease',
                                       availability = 'standard',
                                       from_date = self.tp)
                
        Entry.query.session.flush()
            
    def complete_agreement(self, agreement):
        from vfinance.model.financial.agreement import FinancialAgreementRole
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        person = self.natuurlijke_persoon_case.create_natuurlijke_persoon()
        role = FinancialAgreementRole(natuurlijke_persoon=person)
        agreement.roles.append(role)
        renter_person = self.natuurlijke_persoon_case.get_natuurlijke_personen()[-1]
        renter_role = FinancialAgreementRole(natuurlijke_persoon=renter_person,
                                             described_by='renter')
        agreement.roles.append(renter_role)
        premium_schedule = FinancialAgreementPremiumSchedule(product=self._product,
                                                             amount=100000,
                                                             duration=24)
        agreement.invested_amounts.append( premium_schedule )
        premium_schedule.use_default_features()
        agreement.broker_relation = agreement.get_available_broker_relations()[-1]
        FinancialAgreementRole.query.session.flush()
        
    def test_venice_synchronisation(self):
        agreement = self.create_agreement()
        self.complete_agreement(agreement)
        self.button_complete(agreement)
        self.button_verified(agreement)
        self.fulfill_agreement(agreement)
        # we cannot test the creation of accounts with synchronize all, since synchronizing
        # the entries will unfulfill the agreement
        for step in self.synchronizer.create_premium_schedules():
            self.assertTrue( isinstance(step, basestring) )
        self.assertTrue( agreement.account )
        premium_schedules = agreement.account.premium_schedules
        self.assertTrue( len(premium_schedules) > 0 )
        
        for step in self.synchronizer.attribute_pending_premiums():
            logger.debug(unicode(step))
            self.assertTrue( isinstance(step, basestring) )
        for premium_schedule in premium_schedules:
            self.assertEqual( premium_schedule.premiums_attributed_to_customer, 1 )
            self.assertEqual( premium_schedule.premiums_attributed_to_account, 0 )
            self.assertEqual( premium_schedule.valid_from_date, self.t4 )
        for progress in self.synchronizer.run_forward():
            # make sure there is some output for the buildbot
            logger.debug( unicode( progress ) )
        for premium_schedule in premium_schedules:
            premium_schedule.expire()
            self.assertEqual( premium_schedule.premiums_attributed_to_customer, 1 )
            self.assertTrue( premium_schedule.premiums_attributed_to_account >= 1 )
            self.assertEqual( premium_schedule.account_status, 'active' )
        for progress in self.synchronizer.all():
            logger.debug( progress._text )
        
    def test_relate_payments_to_agreements(self):
        agreement = self.create_agreement()
        self.complete_agreement(agreement)
        self.assertEqual( agreement.amount_due, 100000 )
        entry = self.fulfill_agreement(agreement)
        self.assertTrue( entry in agreement.related_entries )
        self.assertEqual( agreement.amount_on_hold, 100000 )
        self.assertEqual( agreement.amount_due, 0 )
        
    def test_agreement_state_transitions(self):
        agreement = self.create_agreement()
        self.assertFalse( agreement.is_complete() )
        with self.assertRaises(Exception):
            self.button_complete(agreement)
        self.complete_agreement( agreement )
        self.assertTrue( agreement.is_complete() )
        self.button_complete(agreement)
        with self.assertRaises( UserException ):
            for ps in agreement.invested_amounts:
                ps.use_default_features()
        self.button_draft(agreement)
        self.button_complete(agreement)
        self.button_incomplete(agreement)
        self.button_complete(agreement)
        self.button_verified(agreement)
        
    def test_account_creation(self):
        agreement = self.create_agreement()
        self.complete_agreement( agreement )
        self.fulfill_agreement(agreement)
        self.button_complete(agreement)
        self.button_verified(agreement)
        self.button_agreement_forward(agreement)
        self.assertTrue( agreement.account )
        self.assertEqual( agreement.account.current_status, 'draft' )
        agreement.account.change_status('active')
        self.assertEqual( agreement.account.current_status, 'active' )
        
    def test_invested_amount_to_premium(self):
        agreement = self.create_agreement()
        self.complete_agreement( agreement )
        self.fulfill_agreement( agreement )
        self.button_complete(agreement)
        self.button_verified(agreement)
        self.button_agreement_forward(agreement)
        agreement.account.change_status('active')
        for invested_amount in agreement.invested_amounts:
            self.assertTrue( invested_amount.fulfilled )
            self.assertEqual( invested_amount.current_status_sql, 'verified' )
        premium_schedules = list(invested_amount.fulfilled_by)
        self.assertTrue( len(premium_schedules) > 0)
        self.assertTrue( invested_amount.fulfilled )
        return premium_schedules
    
    def test_create_entries_for_premium(self):
        from vfinance.model.bank.customer import CustomerAccount
        from vfinance.model.financial.visitor.account_attribution import AccountAttributionVisitor
        account_attribution_visitor = AccountAttributionVisitor()
        premium_schedules = self.test_invested_amount_to_premium()
        list(self.synchronizer.attribute_pending_premiums())
        for premium in premium_schedules:
            self.visit_premium_schedule(account_attribution_visitor, premium, datetime.date.today())
        account = premium_schedules[0].financial_account
        package = account.package
        #
        # verify if the customer account has been created
        #
        dual_persons = [role for role in premium.financial_account.roles if role.described_by=='subscriber']
        self.assertTrue( len( dual_persons ) )        
        customer_account = CustomerAccount.find_by_dual_persons(dual_persons, package.from_customer, package.thru_customer)
        self.assertTrue( customer_account )
        self.assertEqual( customer_account.state, 'aangemaakt' )
        return account

    def test_create_notifications( self ):
        #
        # Generate notifications
        #
        account = self.test_create_entries_for_premium()
        self.assertTrue( len(account.notifications) > 0 )
        work_effort = account.notifications[0].generated_by
        self.assertEqual( work_effort.current_status, 'open' )
        return work_effort

    def test_create_documents( self ):
        from vfinance.model.financial.work_effort import Complete
        #
        # Generate documents for notifications
        #
        account = self.test_create_entries_for_premium()
        work_effort = self.test_create_notifications()
        work_effort.button_close()
        complete_action = Complete()
        model_context = MockModelContext()
        model_context.obj = work_effort
        for step in complete_action.model_run( model_context ):
            self.assertNotEqual( type( step ), action_steps.MessageBox )
        for notification in account.notifications:
            message = notification.message
            self.assertTrue( message )
            xml_stream = message.storage.checkout_stream( message )
            ElementTree.parse( xml_stream )

    def test_performance( self ):
        """
        
        easy_install SquareMap RunSnakeRun
        apt-get install python-profiler python-wxgtk2.8
        
        export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games
        export PYTHONHOME=/usr
        
        python -m runsnakerun.runsnake branch_26.profile
        """
        from vfinance.model.financial.visitor.joined import JoinedVisitor
        
        thru_date = datetime.date(year=2011, month=12, day=1)
        joined = JoinedVisitor()
        premium_schedules = self.test_create_entries_for_premium().premium_schedules
        
        #
        # visit the premium schedule a couple of times to measure
        # the amount of time taken
        #
        def run():
            for i in range(5):
                for premium_schedule in premium_schedules:
                    #logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
                    list(joined.visit_premium_schedule( premium_schedule, thru_date ))
            
        import cProfile
        command = 'run()'
        cProfile.runctx( command, globals(), locals(), filename='branch_26.profile' )
        
    def test_redemption_before_thru_date(self):
        from vfinance.model.financial.admin import CloseAccount
        from vfinance.facade.redemption import RedemptionAction
        from vfinance.model.financial.visitor.joined import JoinedVisitor
        from vfinance.model.financial.transaction import FinancialTransaction
        from vfinance.model.financial.interest import leap_days
        joined = JoinedVisitor()
        account = self.test_create_entries_for_premium()
        redemption_date = datetime.date( self.t3.year + 1, self.t3.month + 1, self.t3.day + 1 )
        book_thru_date = datetime.date( self.t3.year + 3, self.t3.month, self.t3.day )
        for premium_schedule in account.premium_schedules:
            list(joined.visit_premium_schedule( premium_schedule, redemption_date ))
        value_before_redemption = joined.get_total_amount_until( premium_schedule, account=FinancialBookingAccount() )[0] * -1
        self.assertTrue( value_before_redemption > D('100000') * D('1.021') )
        self.assertTrue( value_before_redemption < D('100000') * D('1.021') * D('1.021') )

        self.session.flush()
        self.session.expire_all()

        count_before_wizard = self.session.query(FinancialTransaction).count()

        model_context = MockModelContext(self.session)
        model_context.admin = self.app_admin
        model_context.obj = account
        initiate_transaction = RedemptionAction()
        g = initiate_transaction.model_run( model_context )
        wizard_open_formview_step = g.next()
        redemption_facade = wizard_open_formview_step.objects[0]
        model_context.admin= self.app_admin.get_related_admin(redemption_facade.__class__)
        model_context.obj = redemption_facade
        incomplete_action = wizard_open_formview_step.actions[0]
        complete_action = wizard_open_formview_step.actions[1]
        self.assertFalse(incomplete_action.get_state(model_context).enabled)
        self.assertFalse(complete_action.get_state(model_context).enabled)
        redemption_facade.agreement_date = redemption_date
        redemption_facade.from_date = redemption_date
        redemption_facade.code = u'000/0000/00000'
        self.assertTrue(redemption_facade.note)
        redemption_facade.credit_distribution_iban = 'NL91ABNA0417164300'
        self.assertFalse(redemption_facade.terminate_premium_payments_checked)
        redemption_facade.terminate_premium_payments_checked = True
        self.assertTrue(redemption_facade.terminate_premium_payments_checked)
        self.assertFalse(redemption_facade.note)
        redemption_facade.compliance_checked = False
        self.assertTrue(incomplete_action.get_state(model_context).enabled)
        self.assertFalse(complete_action.get_state(model_context).enabled)
        redemption_facade.compliance_checked = True
        self.assertTrue(incomplete_action.get_state(model_context).enabled)
        self.assertTrue(complete_action.get_state(model_context).enabled)
        list(g)

        self.assertFalse(redemption_facade.note)

        # Test completion of redemption
        complete_redemption = CompleteRedemption()
        self.button(redemption_facade, complete_redemption, model_context)
        count_after_wizard = self.session.query(FinancialTransaction).count()
        self.assertEqual(count_before_wizard + 1, count_after_wizard)
        self.assertEqual(redemption_facade.current_status, 'complete')

        # Test verification of transaction.  Verification is done on the
        # transaction, not on the facade
        transaction = self.session.query(FinancialTransaction).get(redemption_facade.id)
        self.assertTrue(transaction)
        transaction_status_verified = TransactionStatusVerified()
        self.button(transaction, transaction_status_verified, model_context)
        self.assertEqual(transaction.current_status, 'verified')
        model_context.obj = account

        list(joined.visit_premium_schedule( premium_schedule, book_thru_date ))
        value_after_redemption = joined.get_total_amount_until( premium_schedule, account=FinancialBookingAccount() )[0] * -1
        redeemed = joined.get_total_amount_until( premium_schedule, 
                                                  account = ProductBookingAccount( 'redemption_revenue' ), 
                                                  fulfillment_type = 'redemption_attribution' )[0]
        leaps = leap_days( self.t4, redemption_date)
        days_on_account = ( redemption_date - self.t4 ).days + 1
        self.assertEqual( leaps, 0 )
        self.assertEqual( days_on_account, 365 + 28 + 1 + 1 )
        value_at_redemption_date = D(100000) * D('1.021') ** ( D(days_on_account) / 365 )
        self.assertAlmostEqual( value_at_redemption_date, redeemed, 2 )
        self.assertEqual( value_after_redemption, 0 )
        #
        # make sure bookings don't happen twice
        #
        list(joined.visit_premium_schedule( premium_schedule, book_thru_date ))
        value_after_redemption = joined.get_total_amount_until( premium_schedule, account=FinancialBookingAccount() )[0] * -1
        self.assertEqual( value_after_redemption, 0 )
        #
        # Transaction completion document - FULL REDEMPTION
        #
        document = TransactionDocument()
        options = TransactionDocument.Options()
        model_context = MockModelContext()
        model_context.obj = transaction
        for step in document.model_run(model_context):
            if isinstance( step, ChangeObject ):
                step.get_object().notification_type = 'transaction-completion'
        # numbers already verified above
        # this is to test field injection and template logic
        strings_present = [
            'Dehaen',
            'uw verzoek tot volledige afkoop van ',
            '101.933,37',
        #    'Het afgekochte bedrag zal na aftrek van eventuele kosten en/of nog verschuldigde bedragen binnen een periode van 30 dagen'
        ]
        self.assert_generated_transaction_document(step.path, strings_present)
        context = document.get_context(transaction, None, options)
        transaction_revenue_by_type = dict((r.revenue_type, r.amount) for r in context['transaction_revenues'])
        self.assertAlmostEqual( transaction_revenue_by_type['effective_interest_tax'], -15 * (value_at_redemption_date - 100000) / 100, 2 )

        context = document.get_context(transaction, None, options)
        transaction_revenue_by_type = dict((r.revenue_type, r.amount) for r in context['transaction_revenues'])
        self.assertAlmostEqual( transaction_revenue_by_type['effective_interest_tax'], -15 * (value_at_redemption_date - 100000) / 100, 2 )
        #
        # This account should show up when running the close account wizard
        #
        account_evaluated = False
        close_account_wizard = CloseAccount()
        model_context = ApplicationActionModelContext()
        for step in close_account_wizard.model_run( model_context ):
            if 'account {0}'.format( account.id ) in unicode( step ):
                account_evaluated = True
        self.assertTrue( account_evaluated )
        self.assertEqual( account.current_status, 'closed' )
        return transaction
        
    def test_interest_before_attribution(self):
        from vfinance.model.financial.visitor.joined import JoinedVisitor
        from vfinance.model.financial.feature import FinancialAccountPremiumScheduleFeature
        joined = JoinedVisitor()
        account = self.test_create_entries_for_premium()
        redemption_date = datetime.date( self.t3.year + 3, self.t3.month, self.t3.day )
        for premium_schedule in account.premium_schedules:
            FinancialAccountPremiumScheduleFeature( applied_on = premium_schedule,
                                                    described_by = 'interest_before_attribution',
                                                    premium_from_date = self.t3,
                                                    apply_from_date = self.t3,
                                                    value = 365 )
            FinancialAccountPremiumScheduleFeature.query.session.flush()
            list(joined.visit_premium_schedule( premium_schedule, redemption_date ))
        value_before_redemption = joined.get_total_amount_until( premium_schedule, account=FinancialBookingAccount() )[0] * -1
        self.assertAlmostEqual( value_before_redemption, D('100000') * D('1.021') * D('1.021') * D('1.021'), 2 )
        
    def test_redemption_after_thru_date(self):
        from vfinance.model.financial.visitor.joined import JoinedVisitor
        from vfinance.model.financial.transaction import ( FinancialTransaction, 
                                                           FinancialTransactionPremiumSchedule,
                                                           FinancialTransactionCreditDistribution )
        joined = JoinedVisitor()
        account = self.test_create_entries_for_premium()
        redemption_date = datetime.date( self.t3.year + 3, self.t3.month, self.t3.day )
        for premium_schedule in account.premium_schedules:
            list(joined.visit_premium_schedule( premium_schedule, redemption_date ))
        value_before_redemption = joined.get_total_amount_until( premium_schedule, account=FinancialBookingAccount() )[0] * -1
        self.assertAlmostEqual( value_before_redemption, D('100000') * D('1.021') * D('1.021'), 2 )
        
        transaction = FinancialTransaction( agreement_date = redemption_date, 
                                            from_date = redemption_date, 
                                            transaction_type = 'full_redemption', 
                                            code=u'000/0000/00000')
        self.assertTrue( transaction.note )
        
        for premium_schedule in account.premium_schedules:
            FinancialTransactionPremiumSchedule( within = transaction, 
                                                 premium_schedule = premium_schedule, 
                                                 described_by = 'percentage', quantity = -100 )
        FinancialTransactionCreditDistribution(financial_transaction = transaction,
                                               iban = 'NL91ABNA0417164300',
                                               described_by = 'percentage',
                                               quantity = 100)       
        self.assertFalse( transaction.note )
        
        FinancialTransaction.query.session.flush()
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())
            
        list(joined.visit_premium_schedule( premium_schedule, redemption_date ))
        value_after_redemption = joined.get_total_amount_until( premium_schedule, account=FinancialBookingAccount() )[0] * -1
        self.assertEqual( value_after_redemption, 0 )
        #
        # redeemed value
        #
        
        #
        # make sure bookings don't happen twice
        #
        list(joined.visit_premium_schedule( premium_schedule, redemption_date ))
        value_after_redemption = joined.get_total_amount_until( premium_schedule, account=FinancialBookingAccount() )[0] * -1
        self.assertEqual( value_after_redemption, 0 )
        #
        # Transaction completion document - FULL REDEMPTION
        #
        document = TransactionDocument()
        model_context = MockModelContext()
        model_context.obj = transaction
        for step in document.model_run(model_context):
            if isinstance( step, ChangeObject ):
                step.get_object().notification_type = 'transaction-completion'
        # numbers already verified above
        # this is to test field injection and template logic
        strings_present = [
            'Dehaen',
            'Graag melden wij de goede ontvangst van uw verzoek tot volledige afkoop van uw Contract',
            'Roerende voorheffing', # tak 26 heeft altijd roerende voorheffing, geen premietaks
            # tijdelijk verwijderd, tot account-movements in voege is
            # 'Het afgekochte bedrag zal na aftrek van eventuele kosten en/of nog verschuldigde bedragen binnen een periode van 30 dagen'
        ]
        self.assert_generated_transaction_document(step.path, strings_present)

        return account, transaction
        
    def tearDown(self):
        pass
