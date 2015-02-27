# coding=UTF-8
import warnings
from sqlalchemy.exc import SADeprecationWarning
warnings.filterwarnings('ignore', category=SADeprecationWarning)

import datetime

from decimal import Decimal as D

from sqlalchemy import sql

from camelot.core.templates import environment
from camelot.model.authentication import end_of_times
from camelot.test.action import MockModelContext
from camelot.view.action_steps import ChangeObject, ChangeObjects, PrintJinjaTemplate, UpdateProgress, open_file

from vfinance.model.bank.product import ProductFeatureApplicability
from vfinance.model.financial.notification.account_document import FinancialAccountDocument
from vfinance.model.financial.notification.transaction_document import TransactionDocument
from vfinance.model.financial.security import AssignAccountNumber, FinancialFund, FinancialSecurityQuotation
from vfinance.model.financial.fund import (FinancialAccountFundDistribution,
                                           FinancialTransactionFundDistribution)
from vfinance.model.financial.admin import (RunTransactionSimulation,
                                            RunBackTransaction)
from vfinance.model.financial.visitor.abstract import FinancialBookingAccount, ProductBookingAccount
from vfinance.model.financial.visitor.joined import JoinedVisitor
from vfinance.model.financial.visitor.security_orders import SecurityOrdersVisitor
from vfinance.model.financial.security_order import FinancialSecurityOrderLine
from vfinance.model.financial.transaction import (
    FinancialTransaction,FinancialTransactionPremiumSchedule,
    FinancialTransactionCreditDistribution, TransactionStatusVerified,
    RemoveFutureOrderLines)
from vfinance.model.financial.visitor.security_order_lines import SecurityOrderLinesVisitor
from vfinance.model.financial.work_effort import FinancialAccountNotificationAcceptance
from vfinance.model.financial.visitor.customer_attribution import CustomerAttributionVisitor
from vfinance.model.financial.product import FinancialProduct, ProductFundAvailability
from vfinance.model.financial.package import ( FinancialPackage, 
                                               FinancialNotificationApplicability, 
                                               FinancialBrokerAvailability,
                                               FinancialProductAvailability,
                                               FunctionalSettingApplicability )
from vfinance.model.financial.security import (FinancialSecurityQuotationPeriodType,
                                               FinancialSecurityFeature,
                                               FinancialSecurityRiskAssessment)
from vfinance.model.financial.document import FinancialDocumentType
from vfinance.admin.jinja2_filters import currency as currency_jinja_filter
from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.model.financial.agreement import FinancialAgreementRole, FinancialAgreementFunctionalSettingAgreement
from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
from vfinance.model.financial.document import FinancialDocument
from vfinance.model.financial.commission import FinancialAgreementCommissionDistribution
from vfinance.model.financial.summary.agreement_summary import FinancialAgreementSummary
from vfinance.model.financial.notification.premium_schedule_document import PremiumScheduleDocument
from vfinance.model.financial.visitor.fund_attribution import FundAttributionVisitor
from vfinance.model.financial.visitor.abstract import AbstractVisitor
from vfinance.model.financial.visitor.security_quotation import SecurityQuotationVisitor
from vfinance.model.financial.feature import FinancialTransactionPremiumScheduleFeature
from vfinance.model.financial.visitor.transaction_completion import (
    TransactionCompletionVisitor, TransactionInitiationVisitor)
from vfinance.model.financial.visitor.financed_commission import FinancedCommissionVisitor
from vfinance.model.financial.security import AbstractQuotation
from vfinance.model.financial.visitor.security_orders import security_order
from integration.tinyerp.convenience import add_months_to_date

from test_financial import AbstractFinancialCase
import logging

logger = logging.getLogger('vfinance.test.test_branch_23')

run_back = RunBackTransaction()
transaction_simulate = RunTransactionSimulation()
        
class Branch23Case(AbstractFinancialCase):

    remove_future_order_lines = RemoveFutureOrderLines()

    def setUp(self):
        AbstractFinancialCase.setUp(self)
        self.fund_1 = FinancialFund(name='Carmignac Patrimoine %s'%datetime.datetime.now(),
                                    isin = 'CARMI',
                                    order_lines_from = datetime.date(2000, 1, 1),
                                    purchase_delay = 1,
                                    transfer_revenue_account = '771',
                                    sales_delay = 1)
        
        FinancialSecurityFeature( financial_security = self.fund_1, 
                                  apply_from_date = datetime.date(2000, 1, 1),
                                  described_by = 'exit_rate',
                                  value = 5,
                                  )
        # TODO use dates defined in test_financial.AbstractFinancialCase
        #      this can be done once the template tests use these dates as well
        #      currently the template tests use their own defined dates
        FinancialSecurityRiskAssessment(financial_security=self.fund_1,
                                        from_date=datetime.date(2000, 1, 1),
                                        risk_type='class 2')
        FinancialSecurityRiskAssessment(financial_security=self.fund_1,
                                        from_date=datetime.date(2009, 8, 2),
                                        risk_type='class 4')
        FinancialSecurityRiskAssessment(financial_security=self.fund_1,
                                        from_date=datetime.date(2010, 8, 2),
                                        risk_type='class 6')
        
        self.fund_1.quotation_period_types.append( FinancialSecurityQuotationPeriodType( 
                                                   from_date=datetime.date(year=2010, month=1, day=1) ) )
        for i in range(1,13):
            quotation = FinancialSecurityQuotation(financial_security=self.fund_1, from_datetime=datetime.datetime(year=2010, month=i, day=15), value=100 + 10*i)
            quotation.set_default_dates()
            quotation.change_status('verified')

        self.fund_2 = FinancialFund(name='Allegro %s'%datetime.datetime.now(), 
                                    isin='ALLG',
                                    order_lines_from = datetime.date(2000, 1, 1),
                                    transfer_revenue_account = '771',
                                    purchase_delay = 1,
                                    sales_delay = 1)
        self.fund_2.quotation_period_types.append( FinancialSecurityQuotationPeriodType(
                                                   from_date=datetime.date(year=2010, month=1, day=1) ) )
        for i in range(1,13):
            quotation = FinancialSecurityQuotation(financial_security=self.fund_2, from_datetime=datetime.datetime(year=2010, month=i, day=15), value=100 - 5*i)
            quotation.set_default_dates()
            
        self.fund_3 = FinancialFund(name='Moneytron %s'%datetime.datetime.now(),
                                    isin = 'MTRON',
                                    order_lines_from = datetime.date(2000, 1, 1),
                                    transfer_revenue_account = '771',
                                    purchase_delay = 1,
                                    sales_delay = 1)
        self.fund_3.quotation_period_types.append( FinancialSecurityQuotationPeriodType( 
                                                   from_date=datetime.date(year=2010, month=1, day=1) ) )
        for i in range(1,13):
            quotation = FinancialSecurityQuotation(financial_security=self.fund_3, from_datetime=datetime.datetime(year=2010, month=i, day=17), value=100 + 1*i)
            quotation.set_default_dates()
            quotation.change_status('verified')
            
        self._document_type = FinancialDocumentType(description=u'Proof')
        self._base_product = FinancialProduct(name='Branch 23',
                                              account_number_prefix = 152,
                                              account_number_digits = 6)
        self._product = FinancialProduct(name='Puerto Azul',
                                         specialization_of=self._base_product,
                                         from_date=self.tp,
                                         account_number_prefix = 152,
                                         account_number_digits = 6,
                                         quotation_book = 'Qout',
                                         premium_sales_book = 'VPrem',
                                         premium_attribution_book = u'DOMTV',
                                         depot_movement_book = u'RESBE',
                                         supplier_distribution_book = u'COM',
                                         unit_linked=True,
                                         fund_number_digits=3,
                                         numbering_scheme='global',
                                         financed_commissions_prefix='22352',
                                         financed_commissions_sales_book='GIT',
                                         redemption_book = 'REDEM',
                                         switch_book = 'SWITCH',
                                         )
        self._package = FinancialPackage( name='Puerto Azul',
                                          from_customer = 400000,
                                          thru_customer = 499999,
                                          from_supplier = 8000,
                                          thru_supplier = 9000,
                                          )

        FunctionalSettingApplicability( available_for = self._package,
                                        from_date = self.tp,
                                        described_by = 'mail_to_first_subscriber',
                                        availability = 'standard' )
        
        FinancialProductAvailability( available_for = self._package,
                                      product = self._product,
                                      from_date = self.tp )
        
        self.create_accounts_for_product( self._product )
     
        FinancialBrokerAvailability( available_for = self._package, 
                                     broker_relation = self.rechtspersoon_case.broker_relation,
                                     from_date = self.tp )
        
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_taxation_physical_person', value=D('1.1'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='financed_commissions_rate', value=6)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='financed_commissions_periodicity', value=D('1'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='cooling_off_period', value=30)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='investment_delay', value=7)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='financed_commissions_interest_rate', value=D('0.55'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='switch_out_fee', value=D('5'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='switch_out_rate', value=D('2'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='switch_in_fee', value=D('2'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='switch_in_rate', value=D('1'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='redemption_fee', value=D('15'))
        # set the redemption rate here to 2, to verify if setting the redemption rate to 1 on the transaction itself overrules this value
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='redemption_rate', value=D('2'))
        
        for from_duration,  thru_duration,  value in [(0,    11,  D('2.5') ),
                                                      (12,   23,  D('2.08') ),
                                                      (24,   35,  D('1.67') ),
                                                      (36,   47,  D('1.25') ),
                                                      (48,   59,  D('0.83') ),
                                                      (60,   71,  D('0.42') ),
                                                      (72,   83,  D('0.33') ),
                                                      (84,   95,  D('0.25') ),
                                                      (96,  107,  D('0.17') ),
                                                      (108, 119,  D('0.08') ),
                                                    ]:
            ProductFeatureApplicability(apply_from_date = self.tp,
                                        premium_from_date = self.tp, 
                                        available_for=self._product,
                                        described_by='financed_commissions_deduction_rate', 
                                        from_attributed_duration = from_duration, 
                                        thru_attributed_duration = thru_duration, 
                                        value=value)
        
        self.fr_pre_certificate = FinancialNotificationApplicability(available_for = self._package,
                                                                     from_date = self.tp,
                                                                     notification_type = 'pre-certificate',
                                                                     template = 'time_deposit/certificate_cooling_off_italy_single.xml',
                                                                     language = 'fr',
                                                                     premium_period_type = 'single')
        self.it_pre_certificate = FinancialNotificationApplicability(available_for = self._package,
                                                                     from_date = self.tp,
                                                                     notification_type = 'pre-certificate',
                                                                     template = 'time_deposit/certificate_cooling_off_italy_single.xml',
                                                                     language = 'nl',
                                                                     premium_period_type = 'single')
        
        #
        # Only test 1 notification per step, otherwise the order is random and difficult to test
        #
        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = self.tp,
                                           notification_type = 'certificate',
                                           template = 'time_deposit/certificate_branch23_nl_BE.xml',
                                           language = 'nl',
                                           premium_period_type = 'single')
        
        self.fr_investment_confirmation = FinancialNotificationApplicability(available_for = self._package,
                                                                             from_date = self.tp,
                                                                             notification_type = 'investment-confirmation',
                                                                             template = 'time_deposit/investment_confirmation_it_IT.xml',
                                                                             language = 'fr',)
        
        self.it_investment_confirmation = FinancialNotificationApplicability(available_for = self._package,
                                                                             from_date = self.tp,
                                                                             notification_type = 'investment-confirmation',
                                                                             template = 'time_deposit/investment_confirmation_it_IT.xml',
                                                                             language = 'it',)

        self.account_state = FinancialNotificationApplicability(available_for = self._package,
                                                                from_date = self.tp,
                                                                notification_type = 'account-state',
                                                                template = 'time_deposit/account_state_23_nl_BE.xml',
                                                                language = None,)
        
        self.account_movements = FinancialNotificationApplicability(available_for = self._package,
                                                                    from_date = self.tp,
                                                                    notification_type = 'account-movements',
                                                                    template = 'time_deposit/account_movements_23_nl_BE.xml',
                                                                    language = None,)
        
        self.be_investment_confirmation =  FinancialNotificationApplicability(available_for = self._package,
                                                                              from_date = self.tp,
                                                                              notification_type = 'investment-confirmation',
                                                                              template = 'time_deposit/certificate_branch23_nl_BE.xml',
                                                                              language = None,)
                                                                                  
        self.transaction_document = FinancialNotificationApplicability(available_for = self._package,
                                                                       from_date = self.tp,
                                                                       notification_type = 'transaction-completion',
                                                                       template = 'time_deposit/transaction_nl_BE.xml',
                                                                       language = None,)
 
        self._fund_availability = ProductFundAvailability(available_for=self._product,
                                                          fund=self.fund_1,
                                                          default_target_percentage=60)
        self._fund_availability = ProductFundAvailability(available_for=self._product,
                                                          fund=self.fund_2,
                                                          default_target_percentage=40)
        FinancialFund.query.session.flush()
        self.fund_1.change_quotation_statuses('verified')
        self.fund_2.change_quotation_statuses('verified')
        self.fund_3.change_quotation_statuses('verified')

    def complete_funds(self):
        for security in [self.fund_1, self.fund_2, self.fund_3]:
            if security.current_status == 'draft':
                self.button(security, AssignAccountNumber())
                self.button_complete(security)
            if security.current_status == 'complete':
                self.button_verified(security)
            if security.current_status != 'verified':
                raise Exception('could not verify security')

    def complete_agreement(self, agreement):
        person = self.natuurlijke_persoon_case.create_natuurlijke_persoon(self.natuurlijke_persoon_case.natuurlijke_personen_data[4])
        role = FinancialAgreementRole(natuurlijke_persoon=person)
        agreement.roles.append(role)
        insured_role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='insured_party')
        agreement.roles.append(insured_role)
        
        single_premium_schedule = FinancialAgreementPremiumSchedule(product=self._product, amount=2500, duration=200*12, period_type='single')
        single_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='financed_commissions_rate', recipient='broker', distribution=D('6') ) )
        agreement.invested_amounts.append( single_premium_schedule )

        yearly_premium_schedule = FinancialAgreementPremiumSchedule(product=self._product, amount=1000, duration=12*10, period_type='yearly')
        yearly_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='financed_commissions_rate', recipient='broker', distribution=D('6') ) )
        agreement.invested_amounts.append( yearly_premium_schedule )
        
        agreement.use_default_funds()
        agreement.documents.append( FinancialDocument( description='proof of payment', type=self._document_type) )
        
        agreement.broker_relation = self.rechtspersoon_case.broker_relation
        agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='exit_at_first_decease' ) )
        
        FinancialAgreementRole.query.session.flush()
        
    def test_fund(self):
        self.complete_funds()
        self.assertTrue( self.fund_1.account_number > 0 )
        self.assertTrue( self.fund_2.account_number > 0 )
        self.assertNotEqual( self.fund_1.account_number, self.fund_2.account_number )
        
        self.assertEqual( self.fund_1.value_at( datetime.date(year=2010, month=1, day=15) ),  110  )
        self.assertEqual( self.fund_1.value_at( datetime.date(year=2010, month=2, day=16) ),  120  )
        self.assertEqual( self.fund_1.value_at( datetime.date(year=2011, month=2, day=16) ),  None )
        
    def test_venice_synchronisation(self):
        agreement = self.create_agreement()
        self.complete_agreement(agreement)
        self.button_complete(agreement)
        self.button_verified(agreement)
        self.button(self.fund_1, AssignAccountNumber())
        self.button(self.fund_2, AssignAccountNumber())
        self.fulfill_agreement(agreement)
        self.button_complete(self.fund_1)
        self.button_complete(self.fund_2)
        self.button_verified(self.fund_1)
        self.button_verified(self.fund_2)
        self.assertTrue( self.fund_1.account_number > 0 )
        self.assertTrue( self.fund_2.account_number > 0 )
        # other tests might have left some incomplete funds
        self.complete_funds()
        self.assertTrue( list( self.synchronizer.create_premium_schedules() ) )
        self.assertTrue( agreement.account )
        for premium in agreement.account.premium_schedules:
            self.assertTrue( len(premium.fund_distribution) > 1 )
        
    def test_agreement_state_transitions(self):
        agreement = self.create_agreement()
        self.assertFalse( agreement.is_complete() )
        self.complete_agreement(agreement)
        self.assertTrue( agreement.is_complete() )
        self.button_complete(agreement)
        self.button_verified(agreement)
        summary_action = FinancialAgreementSummary()
        model_context = MockModelContext()
        model_context.obj = agreement
        list( summary_action.model_run( model_context ) )
        
    def test_account_creation(self):
        agreement = self.create_agreement()
        self.complete_funds()
        self.account_from_agreement(agreement)
        self.assertTrue( agreement.account )
        self.assertEqual( agreement.account.current_status, 'draft' )
        agreement.account.change_status('active')
        self.assertEqual( agreement.account.current_status, 'active' )
        #
        # Have a look the account contains all the agreed data
        #
        account = agreement.account
        for premium in account.premium_schedules:
            self.assertTrue( len(premium.fund_distribution) )
        self.assertTrue( len(account.documents) )
        account_number = premium.full_account_number
        self.assertEqual( len(account_number), 12 )
        self.assertEqual( int(account_number[-5:]), account.id )
        
    def test_agreed_to_applied_premium_schedule(self):
        agreement = self.create_agreement()
        self.complete_funds()
        self.account_from_agreement(agreement)
        agreement.account.change_status('active')
        premium_schedules = []
        for invested_amount in agreement.invested_amounts:
            self.assertTrue( invested_amount.fulfilled )
            self.assertEqual( invested_amount.current_status_sql, 'verified' )
            premium_schedules.extend( list(invested_amount.fulfilled_by) )
        #premium_schedules.sort(key=lambda ps:ps.rank)
        self.assertEqual( len(premium_schedules), 2 )
        self.assertTrue( invested_amount.fulfilled )
        first_premium_schedule = premium_schedules[0]
        self.assertEqual( first_premium_schedule.end_of_cooling_off, end_of_times() )
        return premium_schedules
    
    def accept_notification(self, premium_schedule):
        notification = premium_schedule.get_receipt_notification()
        self.assertTrue( notification )
        acceptance = FinancialAccountNotificationAcceptance(acceptance_of = notification,
                                                            reception_date = self.t7,
                                                            post_date = self.t6)
        acceptance.change_status('accepted')
        acceptance.flush()
        premium_schedule.expire()
        
    def test_create_entries_for_single_premium(self):
        customer_attribution = CustomerAttributionVisitor()
        premium_schedules = self.test_agreed_to_applied_premium_schedule()
        single_premium_schedule = [premium for premium in premium_schedules if premium.period_type=='single'][0]
        list(self.synchronizer.attribute_pending_premiums())
        self.visit_premium_schedule(customer_attribution, single_premium_schedule, self.t4)
        #
        # The investment receipt should be made
        #
        strings_present = [
            u'Giovanni',
            u'2.500,00',
            u'01-02-2010',
            u'Carmignac',
        ]
        notification = self.verify_last_notification_from_account (
            single_premium_schedule.financial_account, 
            expected_type = 'pre-certificate',
            strings_present=strings_present
        )
        self.assertEqual( notification.application_of, self.it_pre_certificate)
        self.assertEqual( notification.date, self.t3 )
        #
        # Customer signs off the investment receipt
        #
        acceptance = FinancialAccountNotificationAcceptance(acceptance_of = notification,
                                                            reception_date = self.t7,
                                                            post_date = self.t6)
        acceptance.change_status('draft')
        acceptance.flush()
        single_premium_schedule.expire()
        self.assertTrue( single_premium_schedule.acceptance, 'draft' )
        acceptance.change_status('accepted')
        acceptance.flush()
        single_premium_schedule.expire()
        self.assertTrue( single_premium_schedule.acceptance, 'accepted' )
        self.assertEqual( single_premium_schedule.end_of_cooling_off, self.t8 )
        #
        # premium is attributed to account
        #
        #self.account_attribution_visitor.visit_premium_schedule( single_premium_schedule, self.t8 )
        with self.accounting.begin(self.session):
            for step in self.account_attribution_visitor.visit_premium_schedule( single_premium_schedule, datetime.date.today() ):
                self.accounting.register_request(step)
        #
        # The certificate should be made
        # 
        strings_present = []
        notification = self.verify_last_notification_from_account(
            single_premium_schedule.financial_account, 
            expected_type = 'certificate',
            strings_present=strings_present
        )
        self.assertAlmostEqual( 2472.80*1.1/100, 27.20, 1 )
        self.assertAlmostEqual( 2472.80 + 27.20, 2500, 1 )
        self.assertAlmostEqual( 2472.80 * 6 / 100, 148.37, 1)
        #
        # The investment should be made
        #
        self.assertEqual( single_premium_schedule.earliest_investment_date, self.t9 )
        amount_to_order = 0
        visitor = SecurityOrdersVisitor()
        for premium_schedule in premium_schedules:
            for order in visitor.get_premium_security_orders( premium_schedule,
                                                               single_premium_schedule.earliest_investment_date,
                                                               premium_schedule.valid_from_date):
                (_document_date, _fulfillment_type, _fund_id, order_type, amount, _ara, _fulf, _ftps) = order
                amount_to_order += amount
        self.assertEqual( order_type, 'amount' )
        self.assertEqual( amount_to_order, single_premium_schedule.get_amount_at( single_premium_schedule.premium_amount, 
                                                                                  single_premium_schedule.valid_from_date,
                                                                                  single_premium_schedule.valid_from_date,
                                                                                  'net_premium' ) )
        #
        # Check if the premium commissions have been distributed
        #
        financed_commissions = self.visitor.get_total_amount_until(single_premium_schedule,
                                                                   account=ProductBookingAccount('financed_commissions_revenue_broker'))
        self.assertEqual(financed_commissions, (D('-148.37'), 0, 0))
        # Run the supplier attribution visitor twice to make sure the supplier is not payed twice
        for i in range(2):
            self.visit_premium_schedule(self.supplier_attribution_visitor, single_premium_schedule, datetime.date.today())
        #
        # Check if the premium commissions have been booked
        #
        financed_commissions = self.visitor.get_total_amount_until(single_premium_schedule,
                                                                   account=ProductBookingAccount('financed_commissions_cost_broker'))
        self.assertEqual(financed_commissions, (D('148.37'), 0, 0))
        return premium_schedules
        
    def test_security_order(self):
        visitor = SecurityOrderLinesVisitor()
        premium_schedules = self.test_create_entries_for_single_premium()
        single_premium_schedule = [ps for ps in premium_schedules if ps.period_type=='single'][0]
        investment_date = single_premium_schedule.earliest_investment_date
        list(visitor.visit_premium_schedule_at( single_premium_schedule, investment_date, investment_date, datetime.date(2000,1,1) ))
        lines = list( FinancialSecurityOrderLine.query.filter( FinancialSecurityOrderLine.premium_schedule_id == single_premium_schedule.id ).all() )
        self.assertTrue( len( lines ) )
        self.assertTrue( lines )
        return premium_schedules
            
    def test_fund_distribution(self):
        visitor = FundAttributionVisitor()
        premium_schedules = self.test_security_order()
        #
        # the ordered premiums can be booked
        #
        with self.accounting.begin(self.session):
            for premium_schedule in premium_schedules:
                for document_date in visitor.get_document_dates(premium_schedule, self.t0, self.t12):
                    for step in visitor.visit_premium_schedule_at(premium_schedule, document_date, self.t12, datetime.date(2000,1,1) ):
                        self.accounting.register_request(step)
        single_premium_schedule = [ps for ps in premium_schedules if ps.period_type=='single'][0]
        strings_present = []
        self.verify_last_notification_from_account(
            single_premium_schedule.financial_account, 
            expected_type = 'investment-confirmation',
            strings_present = strings_present
        )
        #
        # see if we can generate an investment confirmation
        #
        document_action = PremiumScheduleDocument()
        model_context = MockModelContext()
        model_context.obj = single_premium_schedule
        for step in document_action.model_run(model_context):
            if isinstance( step, ChangeObject ):
                options = step.get_object()
                options.from_document_date = self.t0
                options.notification_type = 'investment-confirmation'
        return premium_schedules
    
    def test_net_asset_value_transitions(self):
        security_quotation_visitor = SecurityQuotationVisitor()
        visitor = AbstractVisitor()
        #
        # Some verifications of the value and the number of units at certain points in time
        #  
        premium_schedules = self.test_fund_distribution()
        single_premium_schedule = [ps for ps in premium_schedules if ps.period_type=='single'][0]
        
        def value_at(at_date):
            """:return: a dict with key=fund id and value is (value, number of units)"""
            return dict((fund_distribution.fund.id, 
                         visitor.get_total_amount_until(single_premium_schedule, 
                                                        at_date, 
                                                        account= FinancialBookingAccount( 'fund', fund_distribution.fund ) )) for fund_distribution in single_premium_schedule.fund_distribution)
            
        # at t11
        value_for_fund = value_at( self.t11 - datetime.timedelta(days=1) )
        self.assertEqual( value_for_fund[self.fund_1.id][0], 0 )
        self.assertEqual( value_for_fund[self.fund_2.id][0], 0 )
        self.assertAlmostEqual( value_for_fund[self.fund_1.id][1], 0, 5 )
        self.assertAlmostEqual( value_for_fund[self.fund_2.id][1], 0, 5 )
        # at t12
        value_for_fund = value_at( self.t12 )
        expected_value_for_fund_1 = D('2472.80') * D(60)/D(100) # 1483.68
        expected_value_for_fund_2 = D('2472.80') * D(40)/D(100) # 989.12
        self.assertAlmostEqual( value_for_fund[self.fund_1.id][0] * -1, expected_value_for_fund_1, 2 )
        self.assertAlmostEqual( value_for_fund[self.fund_2.id][0] * -1, expected_value_for_fund_2, 2 )
        expected_quantity_for_fund_1 = D(expected_value_for_fund_1) / 140
        expected_quantity_for_fund_2 = D(expected_value_for_fund_2) / 80
        self.assertAlmostEqual( value_for_fund[self.fund_1.id][1], expected_quantity_for_fund_1, 2 )
        self.assertAlmostEqual( value_for_fund[self.fund_2.id][1], expected_quantity_for_fund_2, 2 )
        #
        # Change the value of the funds and see if the account value follows
        #    
        sync_date = datetime.datetime(year=2010, month=7, day=15)
        with self.accounting.begin(self.session):
            for premium_schedule in premium_schedules:
                for step in security_quotation_visitor.visit_premium_schedule_at(premium_schedule, sync_date.date(), sync_date.date(), datetime.date(2000,1,1) ):
                    self.accounting.register_request(step)
        value_for_fund = value_at( sync_date )
        self.assertAlmostEqual( value_for_fund[self.fund_1.id][0] * -1,  expected_value_for_fund_1 * D(170) / D(140) , 1 ) # 1801.61 = +317
        self.assertAlmostEqual( value_for_fund[self.fund_2.id][0] * -1,  expected_value_for_fund_2 * D(65) / D(80)   , 1 ) # 803.66 = -185.46
        
        
        # Test contents of account state document(s)
        # 
        
        options = FinancialAccountDocument.Options()
        options.from_document_date = self.t0
        options.notification_type = 'account-state'

        for notification in single_premium_schedule.financial_account.package.applicable_notifications:
            if notification.notification_type == 'account-state':
                
                account_state = FinancialAccountDocument()

                with TemplateLanguage( 'nl' ):
                    context = account_state.get_context(single_premium_schedule.financial_account, options)
                    doc = account_state._create_document(environment,
                                                         context,
                                                         notification.template)
                
                doc_content = unicode(open(doc, 'r').read(), 'utf-8')
                
                strings_present = [currency_jinja_filter(unicode(value_for_fund[self.fund_1.id][0] * -1)),
                                   currency_jinja_filter(unicode(value_for_fund[self.fund_2.id][0] * -1)),]
                for string_present in strings_present:
                    self.assertTrue(string_present in doc_content)
        
        # 
        # Test contents of account movements document(s)
        # 
        
        options = FinancialAccountDocument.Options()
        options.from_document_date = self.t0
        options.notification_type = 'account-movements'
        
        for notification in single_premium_schedule.financial_account.package.applicable_notifications:
            if notification.notification_type == 'account-movements':
                for recipient, _broker in single_premium_schedule.financial_account.get_notification_recipients( single_premium_schedule.valid_from_date ):
                    account_state = FinancialAccountDocument()
                    with TemplateLanguage( 'nl' ):
                        doc = account_state._create_document(environment,
                                                             account_state.get_context(single_premium_schedule.financial_account, recipient),
                                                             notification.template)
                    doc_content = unicode(open(doc, 'r').read(), 'utf-8')
                
                    # TODO add expected strings
                    strings_present = []
                    for string_present in strings_present:
                        self.assertTrue(string_present in doc_content)
        
        return premium_schedules, (expected_quantity_for_fund_1, expected_quantity_for_fund_2)
    
    def test_revert_sales( self ):
        premium_schedules, (expected_quantity_for_fund_1, expected_quantity_for_fund_2) = self.test_net_asset_value_transitions()
        for premium_schedule in premium_schedules:
            entries = list( self.visitor.get_entries( premium_schedule ) )
            with self.accounting.begin(self.session):
                for step in self.visitor.create_revert_request( premium_schedule, entries ):
                    self.accounting.register_request(step)
            self.assertEqual( len( list( self.visitor.get_entries( premium_schedule ) ) ), 0 )
                
    def test_performance( self ):
        """
        
        easy_install SquareMap RunSnakeRun
        apt-get install python-profiler python-wxgtk2.8
        
        python -m runsnakerun.runsnake branch_23.profile
        """
        
        thru_date = datetime.date(year=2011, month=12, day=1)
        joined = JoinedVisitor()
        premium_schedules, (expected_quantity_for_fund_1, expected_quantity_for_fund_2) = self.test_net_asset_value_transitions()
        
        for premium_schedule in premium_schedules:
            if premium_schedule.period_type == 'single':
                single_premium_schedule = premium_schedule
            
        def run():
            for i in range(5):
                list(joined.visit_premium_schedule( single_premium_schedule, thru_date ))
            
        import cProfile
        command = 'run()'
        profile_report = cProfile.runctx( command, globals(), locals(), filename='branch_23.profile' )
        print profile_report
        
    def test_financed_switch(self):
        joined = JoinedVisitor()
        document = TransactionDocument()
        run_back = RunBackTransaction()
        premium_schedules, (expected_quantity_for_fund_1, expected_quantity_for_fund_2) = self.test_net_asset_value_transitions()

        transaction = FinancialTransaction( agreement_date = self.t20, from_date = self.t21, transaction_type = 'financed_switch', code=u'000/0000/00000')
        for premium_schedule in premium_schedules:
            if premium_schedule.period_type == 'single':
                single_premium_schedule = premium_schedule
                ftps_switch_out = FinancialTransactionPremiumSchedule( within = transaction, premium_schedule = single_premium_schedule, described_by = 'amount', quantity = -200 )
                FinancialTransactionFundDistribution( distribution_of = ftps_switch_out, fund = self.fund_1, target_percentage = 100 )
                ftps_switch_in = FinancialTransactionPremiumSchedule( within = transaction, premium_schedule = single_premium_schedule, described_by = 'amount', quantity = 191 )
                FinancialTransactionFundDistribution( distribution_of = ftps_switch_in, fund = self.fund_2 )
                
        FinancialTransactionCreditDistribution( iban='NL91ABNA0417164300', described_by = 'percentage', quantity = 100, financial_transaction = transaction )
        FinancialTransaction.query.session.flush()

        model_context = MockModelContext()
        model_context.obj = transaction
        
        self.button(transaction, self.remove_future_order_lines)
        list( run_back.model_run( model_context ) )
        
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())

        #
        # switch out
        #
        switch_date = max(self.t23_1, self.t23_2)
        list(joined.visit_premium_schedule( single_premium_schedule, switch_date))
        #
        # switch in
        #
        for premium_schedule in premium_schedules:
            list(joined.visit_premium_schedule( premium_schedule, datetime.date(year=2010, month=12, day=1) ))
        self.assertEqual(joined.get_total_amount_until(single_premium_schedule,
                                                       thru_document_date = switch_date,
                                                       account=FinancialBookingAccount('fund', fund=self.fund_2))[0], D('-989.29'))
        #
        # Transaction completion document
        #
        options = TransactionDocument.Options()
        options.from_document_date = self.t0
        options.notification_type = 'transaction-completion'
        context = document.get_context( transaction, None, options )
        self.assert_valid_transaction_document_context( context )
        model_context = MockModelContext()
        model_context.obj = transaction
        for step in document.model_run(model_context):
            if isinstance( step, ChangeObject ):
                step.get_object().from_document_date = self.t0
                step.get_object().notification_type = 'transaction-completion'
        # numbers already verified above
        # this is to test field injection and template logic
        strings_present = [
            'Giovanni',
            'uw verzoek tot switch van ',
            #'In bijlage vindt u een gedetailleerde afrekeningstaat met bijhorende waardestand van uw contract na uitvoering van deze operatie.'
        ]
        self.assert_generated_transaction_document(step.path, strings_present)
        #
        # Account Movements (transaction details) document
        #
        document = FinancialAccountDocument()
        options = FinancialAccountDocument.Options()
        options.from_document_date = self.t0
        options.notification_type = 'account-movements'
        context = document.get_context( single_premium_schedule.financial_account, options )
        self.assert_valid_account_movements_document_context( context )
        document.model_run(context)

        # test get_roles_at method
        self.assertEqual(len(transaction.get_roles_at(self.tp, 'subscriber')), 0)
        self.assertEqual(len(transaction.get_roles_at(self.t3, 'subscriber')), 1)
        self.assertEqual(len(transaction.get_roles_at(self.t7, 'subscriber')), 1)
        self.assertEqual(len(transaction.get_roles_at(self.t8, 'subscriber')), 1)
        self.assertEqual(len(transaction.get_roles_at(self.t9, 'subscriber')), 1)

        return transaction

    def test_switch(self):
        document = TransactionDocument()
        joined = JoinedVisitor()
        premium_schedules, (expected_quantity_for_fund_1, expected_quantity_for_fund_2) = self.test_net_asset_value_transitions()

        transaction = FinancialTransaction( agreement_date = self.t20, from_date = self.t21, transaction_type = 'switch', code=u'000/0000/00000')
        for premium_schedule in premium_schedules:
            if premium_schedule.period_type == 'single':
                single_premium_schedule = premium_schedule
                ftps_switch_out = FinancialTransactionPremiumSchedule( within = transaction, premium_schedule = single_premium_schedule, described_by = 'amount', quantity = -200 )
                FinancialTransactionFundDistribution( distribution_of = ftps_switch_out, fund = self.fund_1, target_percentage = 100 )
                ftps_switch_in = FinancialTransactionPremiumSchedule( within = transaction, premium_schedule = single_premium_schedule, described_by = 'percentage', quantity = 100 )
                FinancialTransactionFundDistribution( distribution_of = ftps_switch_in, fund = self.fund_3 )
                FinancialAccountFundDistribution(distribution_of=single_premium_schedule, from_date=self.t21+datetime.timedelta(days=1), fund=self.fund_3)
                
        FinancialTransactionCreditDistribution( iban='NL91ABNA0417164300', described_by = 'percentage', quantity = 100, financial_transaction = transaction )
        FinancialTransaction.query.session.flush()
        
        model_context = MockModelContext()
        model_context.obj = transaction
        
        self.button(transaction, self.remove_future_order_lines)
        list( run_back.model_run( model_context ) )
        #list(transaction_simulate.model_run(model_context))
        
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())

        #
        # switch out
        #
        switch_date = max(self.t23_1, self.t23_2)
        list(joined.visit_premium_schedule( single_premium_schedule, switch_date))
        #
        # switch in
        #
        list(joined.visit_premium_schedule( single_premium_schedule, datetime.date(year=2010, month=12, day=1) ))
        #
        # Transaction completion document
        #
        options = TransactionDocument.Options()
        options.from_document_date = self.t0
        options.notification_type = 'transaction-completion'
        context = document.get_context( transaction, None, options )
        transaction_revenue_by_type = dict((r.revenue_type, r.amount) for r in context['transaction_revenues'])
        self.assertEqual( transaction_revenue_by_type['switch_revenue'], -1 * (5 + 2*200/100))
        self.assert_valid_transaction_document_context( context )
        model_context = MockModelContext()
        model_context.obj = transaction
        for step in document.model_run(model_context):
            if isinstance( step, ChangeObject ):
                step.get_object().from_document_date = self.t0
                step.get_object().notification_type = 'transaction-completion'
        # numbers already verified above
        # this is to test field injection and template logic
        strings_present = [
            'Giovanni',
            'Graag melden wij de goede ontvangst van uw verzoek tot switch van uw Contract',
            # 'In bijlage vindt u een gedetailleerde afrekeningstaat met bijhorende waardestand van uw contract na uitvoering van deze operatie.'
        ]
        self.assert_generated_transaction_document(step.path, strings_present)
        #
        # Account Movements (transaction details) document
        #
        document = FinancialAccountDocument()
        options = FinancialAccountDocument.Options()
        options.notification_type = 'account-movements'
        options.from_document_date = self.t0
        options.from_date = self.t20
        options.thru_date = datetime.date(year=2010, month=12, day=1)
        context = document.get_context( single_premium_schedule.financial_account, options )
        self.assert_valid_account_movements_document_context( context )
        model_context = MockModelContext()
        model_context.obj = single_premium_schedule.financial_account
        for step in document.model_run(model_context):
            if isinstance( step, ChangeObject ):
                step.get_object().from_document_date = self.t0
                step.get_object().notification_type = 'account-movements'
            if isinstance(step, open_file.WordJinjaTemplate):
                # numbers already verified above
                # this is to test field injection and template logic
                strings_present = [
                    'Vanhove Giovanni',
                    'Betreft: Overzicht verrichtingen contract',
                    'Hierbij vindt u de details van de verrichtingen die gebeurd zijn binnen uw verzekeringscontract',
                    'Investering',
                    'Switch kost'
                ]
                self.assert_generated_account_movements_document(step.path, strings_present)
        
        
    def test_redemption(self):
        document = TransactionDocument()
        visitor = AbstractVisitor()
        fund_attribution = FundAttributionVisitor()
        transaction_completion = TransactionCompletionVisitor()
        security_orders = SecurityOrdersVisitor()
        financed_commission = FinancedCommissionVisitor()
        security_order_lines = SecurityOrderLinesVisitor()
        transaction_initiation = TransactionInitiationVisitor()
        joined = JoinedVisitor()
        
        premium_schedules, (expected_quantity_for_fund_1, expected_quantity_for_fund_2) = self.test_net_asset_value_transitions()
        #
        # at t20, a redemption is received
        #
        transaction = FinancialTransaction( agreement_date = self.t20, from_date = self.t21, transaction_type = 'partial_redemption', code=u'000/0000/00000')
        
        for premium_schedule in premium_schedules:
            if premium_schedule.period_type == 'single':
                single_premium_schedule = premium_schedule
                ftps = FinancialTransactionPremiumSchedule( within = transaction, premium_schedule = single_premium_schedule, described_by = 'percentage', quantity = -20 )
                FinancialTransactionPremiumScheduleFeature( applied_on = ftps, 
                                                            described_by = 'financed_commissions_min_redemption_rate', 
                                                            value=100,
                                                            premium_from_date = self.t21,
                                                            apply_from_date = self.t21,)
                FinancialTransactionPremiumScheduleFeature( applied_on = ftps, 
                                                            described_by = 'redemption_rate', 
                                                            value=1,
                                                            premium_from_date = self.t21,
                                                            apply_from_date = self.t21,)
            elif premium_schedule.period_type == 'yearly':
                yearly_premium_schedule = premium_schedule
                transaction_schedule = FinancialTransactionPremiumSchedule( within = transaction, premium_schedule = yearly_premium_schedule, described_by = 'amount', quantity = -1000 )
                FinancialTransactionFundDistribution( distribution_of = transaction_schedule, fund = self.fund_2, target_percentage = 100 )
        FinancialTransactionCreditDistribution( iban='NL91ABNA0417164300', described_by = 'percentage', quantity = 100, financial_transaction = transaction )
        FinancialTransaction.query.session.flush()
        #
        # Create some financed commission security orders beyond the redemption
        # date.
        #
        redemption_date = max(self.t23_1, self.t23_2)
        self.visit_premium_schedule(financed_commission, single_premium_schedule, redemption_date)
        list(security_order_lines.visit_premium_schedule(single_premium_schedule, redemption_date))
        #
        # Completion of the transaction should fail
        #
        with self.assertRaises(Exception):
            self.button_complete(transaction)
        self.button(transaction, self.remove_future_order_lines)
        with self.assertRaises(Exception):
            self.button_complete(transaction)
        model_context = MockModelContext()
        model_context.obj = transaction
        
        self.button(transaction, self.remove_future_order_lines)
        list( run_back.model_run( model_context ) )
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())
        self.assertEqual( transaction.completion_date, self.t26 )
        # attribute financed commissions to fund
        with self.accounting.begin(self.session):
            for step in financed_commission.visit_premium_schedule(single_premium_schedule, self.t22):
                self.accounting.register_request(step)
            for step in fund_attribution.visit_premium_schedule_at(single_premium_schedule, self.t22, self.t22, datetime.date(2000,1,1)):
                self.accounting.register_request(step)
        #
        # the transaction should not be initiated before t22
        #
        initiaton_dates = transaction_initiation.get_document_dates( single_premium_schedule, datetime.date(2000,1,1), self.t22 - datetime.timedelta( days = 1 ) )
        self.assertEqual( len( list( initiaton_dates ) ), 0 )
        #
        # at t22, the transaction should be initiated
        #
        initiaton_dates = transaction_initiation.get_document_dates( single_premium_schedule, datetime.date(2000,1,1), self.t22 )
        self.assertEqual( len( list( initiaton_dates ) ), 1 )
        with self.accounting.begin(self.session):
            for step in transaction_initiation.visit_premium_schedule_at(single_premium_schedule, self.t22, self.t22, datetime.date(2000,1,1)):
                self.accounting.register_request(step)

        def financed_commissions_until(at_date):
            return visitor.get_total_amount_until(single_premium_schedule, 
                                                  thru_document_date = at_date, 
                                                  account=FinancialBookingAccount('financed_commissions') )[0]
        
        def uninvested_until(at_date):
            return visitor.get_total_amount_until(single_premium_schedule, 
                                                  thru_document_date = redemption_date, 
                                                  account=FinancialBookingAccount() )[0]
        
        self.assertEqual( financed_commissions_until(self.t22), 0 )
        
        #
        # at t23, units should be sold
        # 
        # verify if orders are made    
        redemption_orders = dict((distribution.fund_id, amount_to_order) for (document_date, _ft, distribution, _ot, amount_to_order, _ara, _fulf, _ftps) in security_orders.get_premium_security_orders(single_premium_schedule, self.t22, self.t22))
        financed_commission_units_fund_1 = D('3.71') * D('0.6') * (1/D('140') + 1/D('150') + 1/D('160') ) * D('1.05')
        financed_commission_units_fund_2 = D('3.71') * D('0.4') * (1/D('80') + 1/D('75') + 1/D('70') )
        redemption_units_fund_1 = -1 * ( (expected_quantity_for_fund_1 - financed_commission_units_fund_1) * 20) / 100 
        redemption_units_fund_2 = -1 * ( (expected_quantity_for_fund_2 - financed_commission_units_fund_2) * 20) / 100 
        self.assertAlmostEqual( redemption_orders[ self.fund_1.id ], redemption_units_fund_1, 4 )
        self.assertAlmostEqual( redemption_orders[ self.fund_2.id ], redemption_units_fund_2, 4 )
        # verify if fund attributions are made once and only once
        for i in range(2):
            with self.accounting.begin(self.session):
                for step in fund_attribution.visit_premium_schedule_at(single_premium_schedule, redemption_date, redemption_date, datetime.date(2000,1,1)):
                    self.accounting.register_request(step)
        
        def redemption_at(at_date):
            """:return: a dict with key=fund id and value is (value, number of units)"""
            return visitor.get_total_amount_at(single_premium_schedule, 
                                                document_date = at_date, 
                                                fulfillment_type = 'redemption',
                                                account=FinancialBookingAccount() )[0]
          
        redemption_amount_fund_1 = redemption_units_fund_1 * 170  * D('0.95') # 360.32 - 5% exit rate
        redemption_amount_fund_2 = redemption_units_fund_2 * 65  # 160.73
        self.assertAlmostEqual( redemption_at(redemption_date), redemption_amount_fund_1 + redemption_amount_fund_2, 1 ) # 521.05
        # transfer amount to customer
        with self.accounting.begin(self.session):
            for document_date in transaction_completion.get_document_dates(single_premium_schedule, premium_schedule.valid_from_date, end_of_times() ):
                for step in transaction_completion.visit_premium_schedule_at(single_premium_schedule, redemption_date, redemption_date, datetime.date(2000,1,1)):
                    self.accounting.register_request(step)
        # account should be empty
        self.assertEqual( uninvested_until(redemption_date), 0 )
        #
        # Let all visitors run to see if everything ends well
        #
        list(joined.visit_premium_schedule( single_premium_schedule, redemption_date))
        # financed commission stays 0
        self.assertEqual( financed_commissions_until(redemption_date), 0 )
        self.assertEqual( uninvested_until(redemption_date), 0 )
        # no more units are sold to cover the financed commissions after t22
        for entry in visitor.get_entries( single_premium_schedule, 
                                          from_document_date=self.t20,
                                          fulfillment_type='financed_commissions_deduction', 
                                          account=FinancialBookingAccount()):
            units_sold = visitor.get_total_amount_until( single_premium_schedule,
                                                         fulfillment_type='fund_attribution', 
                                                         account=FinancialBookingAccount(),
                                                         associated_to_id = entry.fulfillment_id )[0]
            self.assertEqual( units_sold, 0 )
        #
        # redemptions fees should be booked
        #
        redemption_fees = visitor.get_total_amount_until(single_premium_schedule,
                                                         fulfillment_type='redemption_attribution', 
                                                         account=ProductBookingAccount('redemption_fee_revenue') )[0]
        self.assertEqual( redemption_fees, -15 )
        #
        # Transaction completion document
        #
        options = TransactionDocument.Options()
        options.from_document_date = self.t0
        options.notification_type = 'transaction-completion'
        context = document.get_context( transaction, None, options )
        transaction_revenue_by_type = dict((r.revenue_type, r.amount) for r in context['transaction_revenues'])
        self.assertEqual( transaction_revenue_by_type['redemption_fee_revenue'], -15)
        self.assertEqual( transaction_revenue_by_type['redemption_rate_revenue'], D('-3.6') )
        self.assertEqual( len( context['security_out_entries'] ), 2 )
        security_out_amount = sum( security_out_entry.amount for security_out_entry in context['security_out_entries'] )
        security_out_quantity = sum( security_out_entry.quantity for security_out_entry in context['security_out_entries'] )
        self.assertAlmostEqual( security_out_quantity, ( redemption_units_fund_1 + redemption_units_fund_2 ), 4 )
        self.assertAlmostEqual( security_out_amount, ( redemption_units_fund_1 * 170 + redemption_units_fund_2 * 65 ), 1 )
        self.assert_valid_transaction_document_context( context )
        #
        # The order lines should be made on the from date of the transaction
        #
        
        def ordered_at( document_date ):
            query = sql.select( [ sql.func.sum( FinancialSecurityOrderLine.quantity ) ] )
            query = query.where( FinancialSecurityOrderLine.document_date == document_date )
            query = query.where( FinancialSecurityOrderLine.fulfillment_type == 'redemption' )
            query = query.where( FinancialSecurityOrderLine.financial_security == self.fund_1 )
            query = query.where( FinancialSecurityOrderLine.premium_schedule == single_premium_schedule )
            total = FinancialSecurityOrderLine.query.session.execute( query ).first()[0]
            return total or 0
        
        self.assertAlmostEqual( ordered_at( self.t21 ), redemption_units_fund_1, 4 )
        
        #
        # Change the date of the transaction, the order lines should move
        # to the new date
        #
        new_from_date = self.t21 + datetime.timedelta( days = -1 )
        transaction.from_date = new_from_date
        FinancialSecurityOrderLine.query.session.flush()
        list(joined.visit_premium_schedule( single_premium_schedule, max( redemption_date,
                                                                          new_from_date ) ))
        
        self.assertAlmostEqual( ordered_at( new_from_date ), redemption_units_fund_1, 4 )
        self.assertAlmostEqual( ordered_at( self.t21 ), 0, 4 )
        
        #
        # Transaction completion document - PARTIAL REDEMPTION
        #
        model_context = MockModelContext()
        model_context.obj = transaction
        for step in document.model_run(model_context):
            if isinstance( step, ChangeObject ):
                step.get_object().from_document_date = self.t0
                step.get_object().notification_type = 'transaction-completion'
        # numbers already verified above
        # this is to test field injection and template logic
        strings_present = [
            'Giovanni',
            'Bruggestraat 73',
            'Torhout',
            'Afkoop Contract',
            'Geachte,',
            'verzoek tot gedeeltelijke afkoop van',
            '518,68', # sum of fund values
            #'Het afgekochte bedrag zal na aftrek van eventuele kosten en/of nog verschuldigde bedragen binnen een periode van 30 dagen'
        ]
        self.assert_generated_transaction_document(step.path, strings_present)
        return transaction
        
    def test_two_redemptions( self ):
        """
        Multiple scenario's can happen where too many unit orders will be created
        
        2) 2 redemptions with the same from date

           1) before any transaction is processed
              - Units on account 100
           2) after first transaction has created order lines
              - Units on account 100
              - Unexecuted order line -100 units
           3) after second transaction has created order lines
              - Order line of -1 * max( 100, 100 - 100 )
           
        1) A redemption is entered with a from date 1 day before a premium
           attribution.
           
           1) before any transaction is processed
              - Units on account 0
           2) premium has created order lines
              - Unexecuted order line of 2000 euro
           3) after transaction has created order lines
              - Order line of -1 * max( 0, 0 + 0 )
        
        """
        joined = JoinedVisitor()
        
        premium_schedules, (expected_quantity_for_fund_1, expected_quantity_for_fund_2) = self.test_net_asset_value_transitions()
        #
        # at t20, a redemption is received
        #
        transaction_1 = FinancialTransaction( agreement_date = self.t20, from_date = self.t21, transaction_type = 'full_redemption', code=u'000/0000/00000')
        transaction_2 = FinancialTransaction( agreement_date = self.t20, from_date = self.t21, transaction_type = 'full_redemption', code=u'000/0000/00000')

        # first update the premium schedule, to set the version_id
        for premium_schedule in premium_schedules:
            if premium_schedule.period_type == 'single':
                single_premium_schedule = premium_schedule
                single_premium_schedule.payment_thru_date = self.t20
        self.session.flush()
                
        for premium_schedule in premium_schedules:
            if premium_schedule.period_type == 'single':
                FinancialTransactionPremiumSchedule( within = transaction_1, premium_schedule = single_premium_schedule, described_by = 'percentage', quantity = -100 )
                FinancialTransactionPremiumSchedule( within = transaction_2, premium_schedule = single_premium_schedule, described_by = 'percentage', quantity = -100 )
        FinancialTransactionCreditDistribution( iban='NL91ABNA0417164300', described_by = 'percentage', quantity = 100, financial_transaction = transaction_1 )
        FinancialTransactionCreditDistribution( iban='NL91ABNA0417164300', described_by = 'percentage', quantity = 100, financial_transaction = transaction_2 )
        self.session.flush()
        
        model_context = MockModelContext()
        model_context.obj = transaction_1
        
        self.button(transaction_1, self.remove_future_order_lines)
        list( run_back.model_run( model_context ) )
        
        self.button_complete(transaction_1)
        self.button(transaction_1, TransactionStatusVerified())
        
        self.button_complete(transaction_2)
        self.button(transaction_2, TransactionStatusVerified())
        
        redemption_date = max(self.t23_1, self.t23_2)
        list(joined.visit_premium_schedule( single_premium_schedule, redemption_date))
        #
        # The sum of all order lines should be 0
        #
        order_lines = list( FinancialSecurityOrderLine.query.filter( FinancialSecurityOrderLine.premium_schedule == single_premium_schedule ).all() )
        units = sum( order_line.number_of_units for order_line in order_lines )
        self.assertEqual( units, 0 )
        #
        # The result should remain consistent after multiple runs
        #
        list(joined.visit_premium_schedule( single_premium_schedule, redemption_date))

        return premium_schedules

    def test_fund_attribution( self ):
        #
        # The number of units deduced from the fund should not be higher than
        # the number of units in the fund
        #
        
        class PremiumScheduleMock( object ):
            full_account_number = '1500003000'
        
        premium_schedule = PremiumScheduleMock()
        
        class EntryMock( object ):
            fulfillment_id = 1
        
        entry = EntryMock()
        
        class FundMock( object ):
            id = 1
            name = 'Global Trend Performance'
            
        fund = FundMock()
            
        class FundDistributionMock( object ):
            id = 1
            fund = FundMock()
            full_account_number = '1500003001'
            
        class QuotationMock( AbstractQuotation ):
            financial_security = fund
            purchase_date = datetime.date( 2011, 5, 3 )
            sales_date = datetime.date( 2011, 5, 3 )
            from_datetime = datetime.datetime( 2011, 5, 4 )
            value = D('142.68')
            
            @property
            def from_date( self ):
                return self.from_datetime.date()
    
        fund_distribution = FundDistributionMock()
        early_date = datetime.date( 2000, 1, 1 )
        
        #
        # security orders are requested that when the amount is converted
        # to units and rounded results in more units then available on the
        # account
        #
        class FundAttributionMock( FundAttributionVisitor ):
            
            attributions = []
            
            def get_earliest_investment_date( self, premium_schedule ):
                return early_date
            
            def get_valid_quotation_at_date( self, fund, document_date, quantity_to_invest ):
                return QuotationMock()
            
            def get_premium_security_orders( self, premium_schedule, document_date, last_visited_document_date):
                yield security_order( doc_date = datetime.date( 2011, 5, 2 ), 
                                       fulfillment_type = 'financed_switch', 
                                       fund_distribution = fund_distribution, 
                                       order_type = 'amount', 
                                       quantity = D('-2381.41'), 
                                       attribution_rate_quantity = 0, 
                                       associated_to = entry,
                                       within_id = None )
                
            def get_total_amount_until( self,
                                        premium_schedule, 
                                        thru_document_date , 
                                        thru_book_date, 
                                        fulfillment_type = None,
                                        **kwargs ):
                if fulfillment_type == 'fund_attribution':
                    return 0,0
                else:
                    return -1*D('2371.40'), D('16620.36')/1000, 0
                
            def attribute_premium_to_fund( self, 
                                           premium_schedule,
                                           fund_distribution, 
                                           book_date, 
                                           attribution_amount, 
                                           attribution_rate_amount, 
                                           number_of_units, 
                                           *args ):
                attribution = (book_date, attribution_amount, attribution_rate_amount, number_of_units )
                self.attributions.append( attribution )
                yield attribution
                
        document_date = datetime.date( 2011, 5, 4 )
        visitor = FundAttributionMock()
        list(visitor.visit_premium_schedule_at(premium_schedule, 
                                               document_date, 
                                               document_date, 
                                               early_date))
        
        self.assertEqual( -1*D('16620.36')/1000, visitor.attributions[0][3] )
    
    def test_monthly_deductions(self):
        financed_commission_visitor = FinancedCommissionVisitor()
        joined = JoinedVisitor()
        premium_schedules = self.test_create_entries_for_single_premium()
        for premium_schedule in premium_schedules:
            if premium_schedule.period_type != 'single':
                continue
            #
            # nothing should be booked yet
            #
            activations = list( financed_commission_visitor.get_entries( premium_schedule,
                                                                         account = FinancialBookingAccount('financed_commissions'),
                                                                         fulfillment_type='financed_commissions_activation' ) )
            activation_entry = activations[0]
            for _date, interest, principal, movements in financed_commission_visitor.get_total_amounts_at_end_of_months( premium_schedule,
                                                                                                                         activation_entry, 
                                                                                                                         self.t9,
                                                                                                                         self.t17,
                                                                                                                         'financed_commissions_write_off'):
                self.assertEqual( interest,  0 )
                self.assertEqual( principal,  0 )
            #
            # verify the amounts that should be booked
            #
            for year, amount in [(0,  D('3.71') ), 
                                 (1,  D('3.09') ),
                                 (2,  D('2.48') ), 
                                 (3,  D('1.85') ), 
                                 (4,  D('1.23') ), 
                                 (5,  D('0.62') ),
                                 (6,  D('0.49') ), 
                                 (7,  D('0.37') ), 
                                 (8,  D('0.25') ), 
                                 (9,  D('0.12') ),
                                 ]:
                month = year * 12
                total_amount, interest, capital, remaining_capital = financed_commission_visitor.get_amount_to_deduce_at( premium_schedule, 
                                                                                                                          add_months_to_date(self.t9, month),
                                                                                                                          self.t9,
                                                                                                                          D('148.37'),
                                                                                                                          100 )
                self.assertEqual( total_amount, amount )
                self.assertEqual( interest, D('0.55') )
                self.assertEqual( capital, amount - D('0.55') )
                self.assertEqual( remaining_capital, 100 - (amount - D('0.55')) )
            # 
            # visit the premium schedule twice, to detect duplicate bookings
            #
            for i in range(2):
                list(joined.visit_premium_schedule( premium_schedule, self.t17 ))
            #
            # Now we should have booking upto t17 for the deduction as well as for the write off
            #
            for date, interest, principal, movements in financed_commission_visitor.get_total_amounts_at_end_of_months( premium_schedule, 
                                                                                                                        activation_entry,
                                                                                                                        self.t9,
                                                                                                                        self.t17,
                                                                                                                        'financed_commissions_write_off'):
                if date == self.t17:
                    self.assertEqual( interest + principal,  -1 * D('3.09') )
                else:
                    self.assertEqual( interest + principal,  -1 * D('3.71') )

    def test_get_risk_assessment_at(self):
        security = self.fund_1
        self.assertEqual(security.get_risk_assessment_at(datetime.date(1900, 1, 1)), None)
        self.assertEqual(unicode(security.get_risk_assessment_at(datetime.date(2000, 1, 1))), u'class 2')
        self.assertEqual(unicode(security.get_risk_assessment_at(datetime.date(2000, 1, 2))), u'class 2')
        self.assertEqual(unicode(security.get_risk_assessment_at(datetime.date(2009, 8, 1))), u'class 2')
        self.assertEqual(unicode(security.get_risk_assessment_at(datetime.date(2009, 8, 2))), u'class 4')
        self.assertEqual(unicode(security.get_risk_assessment_at(datetime.date(2010, 8, 1))), u'class 4')
        self.assertEqual(unicode(security.get_risk_assessment_at(datetime.date(2010, 8, 2))), u'class 6')
        self.assertEqual(unicode(security.get_risk_assessment_at(datetime.date(2400, 12, 31))), u'class 6')

    def test_run_simulation(self):
        premium_schedules, (expected_quantity_for_fund_1, expected_quantity_for_fund_2) = self.test_net_asset_value_transitions()

        transaction = FinancialTransaction(agreement_date=self.t20, from_date=self.t21, transaction_type='switch', code=u'000/0000/00000')
        for premium_schedule in premium_schedules:
            if premium_schedule.period_type == 'single':
                single_premium_schedule = premium_schedule
                ftps_switch_out = FinancialTransactionPremiumSchedule(within=transaction, premium_schedule=single_premium_schedule, described_by='amount', quantity=-200)
                FinancialTransactionFundDistribution(distribution_of=ftps_switch_out, fund=self.fund_1, target_percentage=100)
                ftps_switch_in = FinancialTransactionPremiumSchedule(within=transaction, premium_schedule=single_premium_schedule, described_by='percentage', quantity=100)
                FinancialTransactionFundDistribution(distribution_of=ftps_switch_in, fund=self.fund_3)
                FinancialAccountFundDistribution(distribution_of=single_premium_schedule, from_date=self.t21+datetime.timedelta(days=1), fund=self.fund_3)

        FinancialTransactionCreditDistribution(iban='NL91ABNA0417164300', described_by='percentage', quantity=100, financial_transaction=transaction)
        self.session.flush()
        self.assertFalse(transaction.note)

        model_context = MockModelContext()
        model_context.obj = transaction
        model_context.admin = self.app_admin

        quotations_to_remove = [quot for quot in self.fund_1.quotations if quot.from_date > self.t21]
        for quot in quotations_to_remove:
            self.fund_1.quotations.remove(quot)
        self.session.flush()

        # Get status before simulation
        max_quotation_id_before = FinancialSecurityQuotation.table.select().order_by('id desc').execute().first().id
        status_pre = transaction.__dict__

        quotations = []

        for step in transaction_simulate.model_run(model_context):
            if isinstance(step, ChangeObjects):
                self.assertFalse(self.session.is_active)
                quotations = step.get_objects()
                generated_quotation_value = quotations[0].value
                self.assertTrue(quotations)
            if isinstance(step, UpdateProgress) and step._text == 'Opkuisen tijdelijke gegevens':
                self.assertEqual(quotations[1].value, self.fund_3.get_quotation_value_at(self.t21))
            if isinstance(step, PrintJinjaTemplate):
                self.assertFalse(self.session.is_active)
                self.assertEqual(generated_quotation_value, self.fund_1.last_quotation_value)
                html = step.html
                # Check for a red notification
                notification = u'<span style="color:#f00; font-weight:bold"> - Simulation</span>'
                # Check for a transaction total amount
                transaction_total = u'Transaction total : 0,00'
                self._assert_generated_string(html, [notification, transaction_total])

        # check if database has not been changed by simulation
        max_quotation_id_after = FinancialSecurityQuotation.table.select().order_by('id desc').execute().first().id
        self.assertEqual(max_quotation_id_after, max_quotation_id_before)
        self.assertEqual(transaction.__dict__, status_pre)
