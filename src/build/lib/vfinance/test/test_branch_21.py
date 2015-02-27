import datetime
from decimal import Decimal as D
import logging
import random

from sqlalchemy.orm import object_session

from camelot.test.action import MockModelContext
from camelot.model.authentication import end_of_times
from camelot.core.files.storage import StoredFile
from camelot.core.exception import UserException
from camelot.core.orm import Session
from camelot.view import action_steps
from camelot.view.action_steps import PrintJinjaTemplate

from vfinance.model.bank.product import (ProductFeatureApplicability,
                                         ProductFeatureDistribution,
                                         ProductIndexApplicability)
from vfinance.model.bank.visitor import ProductBookingAccount
from vfinance.model.financial.agreement import (FinancialAgreement,
                                                FinancialAgreementRole,
                                                FinancialAgreementFunctionalSettingAgreement,
                                                FinancialAgreementItem,
                                                FinancialAgreementJsonExport)
from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment
from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature
from vfinance.model.financial.visitor.abstract import FinancialBookingAccount
from vfinance.model.financial.visitor.joined import JoinedVisitor
from vfinance.model.financial.transaction import (FinancialTransaction,
                                                  FinancialTransactionPremiumSchedule,
                                                  TransactionStatusVerified,
                                                  FinancialTransactionCreditDistribution)
from vfinance.model.financial.transaction_task import FinancialTransactionPremiumScheduleTask
from vfinance.model.financial.notification.transaction_document import TransactionDocument
from vfinance.model.financial.notification.account_document import FinancialAccountDocument
from vfinance.model.financial.interest import single_period_future_value

from vfinance.model.financial.admin import RunTransactionSimulation

from test_financial import AbstractFinancialCase, test_data_folder

logger = logging.getLogger('vfinance.test.test_branch_21')

class Branch21Case(AbstractFinancialCase):

    code = '000/0000/00202'

    def setUp(self):
        AbstractFinancialCase.setUp(self)
        from camelot.core.conf import settings
        from vfinance.model.bank.entry import Entry
        from vfinance.model.bank.index import IndexType, IndexHistory
        from vfinance.model.financial.package import ( FinancialPackage,
                                                       FinancialNotificationApplicability,
                                                       FinancialProductAvailability,
                                                       FunctionalSettingApplicability,
                                                       FinancialBrokerAvailability,
                                                       FinancialItemClause )
        from vfinance.model.financial.product import FinancialProduct
        from vfinance.model.insurance.product import InsuranceCoverageAvailability, InsuranceCoverageLevel, InsuranceCoverageAvailabilityMortalityRateTable
        from vfinance.model.insurance.mortality_table import MortalityRateTable
        settings.setup_model()
        for e in Entry.query.filter( Entry.remark.like( u'%' + self.code + u'%' ) ):
            e.delete()
        self.profit_attribution_date = datetime.date(2010,  7,  1)
        self.premium_after_profit_attribution_date = datetime.date(2010,  8,  1)
        self.redemption_after_profit_attribution_date = datetime.date(2010,  9,  1)
        self.full_redemption_date = datetime.date(2010,  10,  1)
        self._package = FinancialPackage( name = 'Branch 21 Package',
                                          from_customer = 400000,
                                          thru_customer = 499999,
                                          from_supplier = 8000,
                                          thru_supplier = 9000,
                                          )
        self._base_product = FinancialProduct(
            name='Branch 21',
            account_number_prefix = 124,
            account_number_digits = 6
        )
        self._product = FinancialProduct(name='Branch 21 Account',
                                         specialization_of=self._base_product,
                                         from_date=self.tp,
                                         account_number_prefix = 124,
                                         account_number_digits = 6,
                                         premium_sales_book = 'VPrem',
                                         premium_attribution_book = u'DOMTV',
                                         depot_movement_book = u'RESBE',
                                         interest_book = u'INT',
                                         funded_premium_book = 'FPREM',
                                         redemption_book = 'REDEM',
                                         profit_attribution_book = 'PROFIT',
                                         supplier_distribution_book = u'COM',
                                         )
        FinancialProductAvailability( available_for = self._package,
                                      product = self._product,
                                      from_date = self.tp )
        self.create_accounts_for_product( self._product )

        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_taxation_physical_person', value=1.1)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_taxation_legal_person', value=4.4)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='entry_fee', value=35)
        premium_fee_1 = ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_fee_1', from_passed_duration=1, value=4)
        ProductFeatureDistribution(of=premium_fee_1, recipient='master_broker', distribution=4)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_rate_1', value=5)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='funded_premium_rate_1', value=1)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='interest_rate', value=D('2.1'), automated_clearing=False)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='interest_rate', value=D('2.2'), automated_clearing=True)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='fictive_interest_rate', value=D('4.75') )
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='fictive_interest_tax_rate', value=D('15'), thru_passed_duration=8*12 - 1 )
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='effective_interest_tax_rate', value=D('15'), from_passed_duration=8*12 )
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='redemption_rate', value=5)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='monthly_contract_exit_rate_decrease', automated_clearing=True, value=D('0.08333') )
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='monthly_premium_exit_rate_decrease', automated_clearing=False, value=D('0.08333') )
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='minimum_exit_fee', value=75)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='direct_debit_delay', value=2)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='invoicing_period', value=30)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='direct_debit_period', value=14)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='direct_debit_investment_delay', value=0)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_reduction_non_smoker', value=D('2.22'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_risk_charge', value=0)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_insured_capital_charge', value=0)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_general_risk_reduction', value=D('2.22'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='market_fluctuation_exit_rate', value=D('100'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='market_fluctuation_reference_duration', value=D(8*12))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='market_fluctuation_index_difference', value=D('0.3'))

        coverage_availability = InsuranceCoverageAvailability(from_date = self.tp, available_for=self._product, of='life_insurance', availability='optional')
        self._coverage_level = InsuranceCoverageLevel(used_in=coverage_availability, type='percentage_of_account', coverage_limit_from=1, coverage_limit_thru=100)

        self._mk = MortalityRateTable(name=u"MK")
        self._mk.generate_male_table()
        self._fk = MortalityRateTable(name=u"FK")
        self._fk.generate_female_table()
        InsuranceCoverageAvailabilityMortalityRateTable(used_in = coverage_availability, type = 'male', mortality_rate_table = self._mk)
        InsuranceCoverageAvailabilityMortalityRateTable(used_in = coverage_availability, type = 'female', mortality_rate_table = self._fk)

        self._clause = FinancialItemClause(available_for=self._package, name='standard beneficiary', clause='Beneficiaries of this contract are in this order : the children, the grand children')

        FunctionalSettingApplicability(from_date = self.tp, available_for=self._package, described_by='exit_at_first_decease', availability='selectable')
        FunctionalSettingApplicability(from_date = self.tp, available_for=self._package, described_by='exit_at_last_decease', availability='selectable')

        FunctionalSettingApplicability(from_date = self.tp, available_for=self._package, described_by='mail_to_first_subscriber', availability='selectable')
        FunctionalSettingApplicability(from_date = self.tp, available_for=self._package, described_by='mail_to_broker', availability='selectable')
        FunctionalSettingApplicability(from_date = self.tp, available_for=self._package, described_by='mail_to_custom_address', availability='selectable')

        FunctionalSettingApplicability(from_date = self.tp, available_for=self._package, described_by='direct_debit_batch_3', availability='standard')
        FunctionalSettingApplicability(from_date = self.tp, available_for=self._package, described_by='broker_relation_required', availability='standard')

        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = self.tp,
                                           notification_type = 'certificate',
                                           template = 'time_deposit/certificate_branch21_nl_BE.xml',
                                           premium_period_type = 'single',
                                           language= 'nl')

        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = self.tp,
                                           notification_type = 'certificate',
                                           template = 'time_deposit/certificate_branch21_fr_BE.xml',
                                           premium_period_type = 'single',
                                           language= 'fr')

        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = self.tp,
                                           notification_type = 'transaction-completion',
                                           template = 'time_deposit/transaction_nl_BE.xml',
                                           language = None,)

        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = self.tp,
                                           notification_type = 'account-movements',
                                           template = 'time_deposit/account_movements_21_nl_BE.xml',
                                           language = None,)

        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = self.tp,
                                           notification_type = 'account-state',
                                           template = 'time_deposit/account_state_21_nl_BE.xml',
                                           language = None,)

        FinancialBrokerAvailability( available_for = self._package,
                                     broker_relation = self.rechtspersoon_case.broker_relation,
                                     from_date = self.tp )

        self._index = IndexType(name='Market Condition')
        # insert index values for 3 years
        for i in range( 0, 3 ):
            for duration in range(1,5):
                IndexHistory( described_by = self._index,
                              value = duration + D('0.2') * i,
                              duration = duration*12,
                              from_date = self.t0 + datetime.timedelta(days=365*i),
                              )
        ProductIndexApplicability(available_for = self._product,
                                  index_type = self._index,
                                  apply_from_date = self.t0)
        self.session.flush()

        # DIRTY HACK - Set to true in test before completing agreement to eliminate insurance coverage
        self._no_insurance_coverage = False

    def complete_agreement(self, agreement):
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        from vfinance.model.insurance.agreement import InsuranceAgreementCoverage
        from vfinance.model.financial.commission import FinancialAgreementCommissionDistribution
        from vfinance.model.bank.direct_debit import DirectDebitMandate
        person = self.natuurlijke_persoon_case.create_natuurlijke_persoon()
        subscriber_role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='subscriber')
        agreement.origin = 'TEST123'
        agreement.automated_clearing = ['000','0000001','01']
        agreement.roles.append(subscriber_role)
        insured_role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='insured_party')
        agreement.roles.append(insured_role)
        single_premium_schedule = FinancialAgreementPremiumSchedule( product=self._product, amount=2500, duration=200*12, period_type='single', direct_debit=False)
        agreement.invested_amounts.append( single_premium_schedule )
        single_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_rate_1', recipient='broker', distribution=D('4') ) )
        single_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='funded_premium_rate_1', recipient='master_broker', distribution=D('1') ) )
        single_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='entry_fee', recipient='company', distribution=D('35') ) )
        monthly_premium_schedule = FinancialAgreementPremiumSchedule( product=self._product, amount=250, duration=5*12, period_type='monthly', direct_debit=True)
        monthly_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_rate_1', recipient='broker', distribution=D('4') ) )
        monthly_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='funded_premium_rate_1', recipient='company', distribution=D('1') ) )
        monthly_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='entry_fee', recipient='company', distribution=D('35') ) )
        agreement.invested_amounts.append( monthly_premium_schedule )
        agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='exit_at_first_decease' ) )
        agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='mail_to_first_subscriber' ) )
        single_premium_schedule.agreed_features.append( FinancialAgreementPremiumScheduleFeature(apply_from_date = self.tp, premium_from_date = self.tp, described_by='premium_rate_1', value=4) )
        # DIRTY HACK!!!
        if not self._no_insurance_coverage:
            single_premium_schedule.agreed_coverages.append( InsuranceAgreementCoverage(coverage_for=self._coverage_level, coverage_limit=30, duration = 200*12) )
        monthly_premium_schedule.agreed_features.append( FinancialAgreementPremiumScheduleFeature(apply_from_date = self.tp, premium_from_date = self.tp, described_by='premium_rate_1', value=4) )
        # DIRTY HACK!!!
        if not self._no_insurance_coverage:
            monthly_premium_schedule.agreed_coverages.append( InsuranceAgreementCoverage(coverage_for=self._coverage_level, coverage_limit=30, duration = 5*12) )
        agreement.agreed_items.append( FinancialAgreementItem(associated_clause=self._clause) )
        mandate = DirectDebitMandate(iban='BE06001349359522',
                                     bank_identifier_code=self._bic,
                                     financial_agreement=agreement,
                                     document=StoredFile(None, 'mandate.pdf'),
                                     from_date = self.t0, 
                                     date = self.t0 )
        mandate.identification = mandate.get_default_identification()
        agreement.broker_relation = agreement.get_available_broker_relations()[-1]
        FinancialAgreementRole.query.session.flush()

    def test_coverage_level_date(self):
      from vfinance.model.insurance.agreement import coverage_for_choices
      self._no_insurance_coverage = False
      agreement = self.create_agreement()
      self.complete_agreement(agreement)
      premium_schedule = agreement.invested_amounts[0]
      # set agreement date outside coverage level date limits
      premium_schedule.financial_agreement.agreement_date = datetime.date(2010, 1, 2)
      insurance_agreement_coverage = premium_schedule.agreed_coverages[0]
      # assert dropdown is as expected
      self.assertEqual(len(coverage_for_choices(insurance_agreement_coverage)), 2)
      # set agreement date inside coverage level date limits
      premium_schedule.financial_agreement.agreement_date = datetime.date(1900, 1, 2)
      insurance_agreement_coverage = premium_schedule.agreed_coverages[0]
      # assert dropdown is as expected
      self.assertEqual(coverage_for_choices(insurance_agreement_coverage), [(None, '')])

    def test_agreement_state_transitions(self):
        agreement = self.create_agreement()
        self.assertFalse( agreement.is_complete() )
        self.complete_agreement(agreement)
        self.assertTrue( len( agreement.get_available_broker_relations() ) > 0 )
        logger.debug('Available broker relations: %s' % agreement.get_available_broker_relations())
        self.assertTrue( agreement.is_complete() )
        self.button_complete(agreement)
        self.button_draft(agreement)
        self.button_complete(agreement)
        self.button_incomplete(agreement)
        self.button_complete(agreement)
        self.button_verified(agreement)
        for premium in agreement.invested_amounts:
            billing_amounts = list(premium.generate_premium_billing_amounts(self.tp, end_of_times()))
            if premium.period_type == 'single':
                self.assertEqual( len(billing_amounts), 1 )

    def test_relate_payments_to_agreements(self):
        agreement = self.create_agreement()
        self.complete_agreement(agreement)
        self.assertEqual( agreement.amount_due, 2500 )
        entry = self.fulfill_agreement(agreement)
        self.assertTrue( entry in agreement.related_entries )
        self.assertEqual( agreement.amount_on_hold, 2500 )
        self.assertEqual( agreement.amount_due, 0 )
        json_export = FinancialAgreementJsonExport()
        context = MockModelContext()
        context.obj = agreement
        list( json_export.model_run( context ) )

    def test_account_creation(self):
        agreement1 = self.create_agreement()
        self.account_from_agreement(agreement1)
        self.assertTrue( agreement1.account )
        self.assertEqual( agreement1.account.current_status, 'draft' )
        agreement1.account.change_status('active')
        self.assertEqual( agreement1.account.current_status, 'active' )
        #
        # Have a look the account contains all the agreed data
        #
        account = agreement1.account
        self.assertTrue( len(account.applied_functional_settings) )
        self.assertTrue( len(account.items) )
        self.assertTrue( len(account.direct_debit_mandates) )
        self.assertTrue( len(account.brokers) )
        self.assertTrue( account.get_broker_at( self.t3 ) )
        #
        # Create a second account to verify it has a different account number
        #
        # agreement2 = self.create_agreement()
        # self.account_from_agreement(agreement2)
        # self.assertNotEqual( agreement2.account.account_number, agreement1.account.account_number )
        return account

    def test_agreed_to_applied_premium_schedule(self):
        agreement = self.create_agreement()
        self.account_from_agreement(agreement)
        agreement.account.change_status('active')
        premium_schedules = []
        for invested_amount in agreement.invested_amounts:
            self.assertTrue( invested_amount.fulfilled )
            self.assertEqual( invested_amount.current_status_sql, 'verified' )
            self.assertTrue( invested_amount.fulfilled_by )
            if not self._no_insurance_coverage:
                self.assertTrue( len(invested_amount.fulfilled_by[0].applied_coverages) )
            premium_schedules.extend( list(invested_amount.fulfilled_by) )
        self.assertEqual( len(premium_schedules), 2 )
        self.assertTrue( invested_amount.fulfilled )
        single_premium_schedule = [premium for premium in premium_schedules if premium.period_type=='single'][0]
        monthly_premium_schedule = [premium for premium in premium_schedules if premium.period_type=='monthly'][0]
        self.assertTrue( len(single_premium_schedule.applied_features) )
        self.assertEqual( single_premium_schedule.direct_debit, False )
        self.assertEqual( monthly_premium_schedule.direct_debit, True )
        self.assertEqual( single_premium_schedule.valid_from_date, self.t4 )
        self.assertEqual( monthly_premium_schedule.valid_from_date, self.t15 )
        self.assertEqual( single_premium_schedule.get_applied_feature_at( self.t4, self.t4, 0, 'interest_rate' ).value, D('2.1') )
        self.assertEqual( monthly_premium_schedule.get_applied_feature_at( self.t15, self.t15, 0, 'interest_rate' ).value, D('2.2') )
        self.assertTrue( len(single_premium_schedule.commission_distribution) )
        self.assertTrue( len(monthly_premium_schedule.commission_distribution) )
        self.assertEqual( monthly_premium_schedule.get_premiums_invoicing_due_amount_at( self.t15 ), 250 )
        self.assertEqual( monthly_premium_schedule.get_premiums_invoicing_due_amount_at( datetime.date(2400,1,1) ), 250*5*12 )
        self.assertEqual( monthly_premium_schedule.premiums_invoiced_amount, 0 )
        #
        # Both premium schedules should use the same account
        #
        self.assertEqual( single_premium_schedule.account_number, monthly_premium_schedule.account_number )
        return premium_schedules

    def test_direct_debit_synchronisation(self):
        from vfinance.model.financial.synchronize import FinancialSynchronizer
        synchronizer = FinancialSynchronizer(self.t13)
        premium_schedules = self.test_agreed_to_applied_premium_schedule()
        single_premium_schedule = [premium for premium in premium_schedules if premium.period_type=='single'][0]
        monthly_premium_schedule = [premium for premium in premium_schedules if premium.period_type=='monthly'][0]
        self.assertEqual( monthly_premium_schedule.get_applied_feature_at( self.t13, monthly_premium_schedule.valid_from_date, 0, 'invoicing_period').value, 30 )
        list( synchronizer.create_premium_invoices() )
        self.assertEqual( single_premium_schedule.premiums_invoiced_amount, 0 )
        self.assertEqual( monthly_premium_schedule.premiums_invoiced_amount, 250 )
        invoice_item = monthly_premium_schedule.invoice_items[0]
        self.assertEqual( invoice_item.last_direct_debit_request_at, None )
        self.assertEqual( invoice_item.last_direct_debit_batch_id, None )
        synchronizer = FinancialSynchronizer(self.t14)
        messages = list( synchronizer.create_direct_debit_batches() )
        self.assertTrue( messages )

    def test_create_entries_for_single_premium(self):
        from vfinance.admin import jinja2_filters
        # DIRTY HACK: don't include insurance
        self._no_insurance_coverage = True
        premium_schedules = self.test_agreed_to_applied_premium_schedule()

        single_premium_schedule = [premium for premium in premium_schedules if premium.period_type=='single'][0]
        get_amount = lambda description:single_premium_schedule.get_amount_at( single_premium_schedule.premium_amount,
                                                                               single_premium_schedule.valid_from_date,
                                                                               single_premium_schedule.valid_from_date,
                                                                               description )


        self.assertEqual( get_amount('taxation'),                               D('27.20') )
        self.assertEqual( get_amount('premium_fee_1') +
                          get_amount('premium_rate_1') +
                          get_amount('entry_fee'),                              D('133.91') )
        self.assertEqual( get_amount('financed_commissions'),                   D('0.00') )
        self.assertEqual( get_amount('funded_premium'),                         D('24.73') )
        self.assertEqual( get_amount('net_premium'),                            D('2363.62') )

        list(self.synchronizer.attribute_pending_premiums())
        self.visit_premium_schedule(self.account_attribution_visitor, single_premium_schedule, datetime.date.today())
        strings_present = [
            single_premium_schedule.full_account_number,
            'Celie',
            'Dehaen',
            'Willemot NV',
            jinja2_filters.date( datetime.date( 1967, 6, 29 ) ),
            jinja2_filters.currency( 2500 ),
            'Branch 21 Package',
            jinja2_filters.currency( 2.10 ),
            jinja2_filters.currency( 2363.62 ),
            jinja2_filters.currency( 24.73 ), # bonus allocatie
#            'Het verzekerd kapitaal is de reserve verhoogd met 30.00 % van de reserve'
        ]
        notification = self.verify_last_notification_from_account(
            single_premium_schedule.financial_account,
            expected_type = 'certificate',
            strings_present=strings_present
        )
        self.assertEqual( notification.date, self.t3 )

        sales = self.get_last_sales_document()
        sales_data = [str(line.amount) for line in sales.lines]

        self.assertAlmostEqual( 27.20 + 98.91 + 35 + 2338.89, 2500, 1 )
        self.assertAlmostEqual( (133.91 + 2340.27)*1.1/100, 27.20, 1 )
        self.assertTrue(   '-27.20' in sales_data ) # Taxes
        self.assertTrue(   '-98.91' in sales_data )
        self.assertTrue(   '-35.00' in sales_data )
        self.assertTrue( '-2338.89' in sales_data )
        self.assertTrue(    '24.73' in sales_data )
        self.assertTrue( '-2363.62' in sales_data )
        #
        # Check if the premium commissions have been distributed
        #
        premium_rate_commission = self.visitor.get_total_amount_at(single_premium_schedule,
                                                                   document_date=self.t3,
                                                                   account=ProductBookingAccount('premium_rate_1_revenue_broker'))
        self.assertEqual(premium_rate_commission, (D('-98.91'), 0, 0))
        #
        # Check if the funded premium has been distributed
        #
        funded_premium = self.visitor.get_total_amount_at(single_premium_schedule,
                                                          document_date=self.t3,
                                                          account=ProductBookingAccount('funded_premium_master_broker'))
        self.assertEqual(funded_premium, (D('24.73'), 0, 0))
        #
        # Check if the premium commissions have been attributed to the supplier, and
        # check if this only happens once
        #
        for _i in range(2):
            self.visit_premium_schedule(self.supplier_attribution_visitor, single_premium_schedule, datetime.date.today())
        premium_rate_commission = self.visitor.get_total_amount_at(single_premium_schedule,
                                                                   document_date=self.t3,
                                                                   account=ProductBookingAccount('premium_rate_1_cost_broker'))
        self.assertEqual(premium_rate_commission, (D('98.91'), 0, 0))
        #
        # Check if the funded premium has been attributed to the supplier
        #
        funded_premium = self.visitor.get_total_amount_at(single_premium_schedule,
                                                          document_date=self.t3,
                                                          account=ProductBookingAccount('funded_premium_master_broker'))
        self.assertEqual(funded_premium, (0, 0, 0))
        #
        # Add a second premium to the account, and attach it by force
        # to the premium schedule
        #
        second_entry = self.fulfill_agreement( single_premium_schedule.agreed_schedule.financial_agreement,
                                               fulfillment_date = datetime.date(2010, 3, 3),
                                               amount = D('2500') )
        FinancialAccountPremiumFulfillment( of = single_premium_schedule,
                                            entry_book_date = second_entry.book_date,
                                            entry_document = second_entry.document,
                                            entry_book = second_entry.book,
                                            entry_line_number = second_entry.line_number,
                                            fulfillment_type = 'premium_attribution',
                                            amount_distribution = -1 * D('2500') )
        FinancialAccountPremiumFulfillment.query.session.flush()

        #
        # Add an additional interest feature, only valid as of a certain date
        #
        from vfinance.model.financial.feature import FinancialAccountPremiumScheduleFeature
        FinancialAccountPremiumScheduleFeature( described_by = 'additional_interest_rate',
                                                value = D('7.3'),
                                                premium_from_date = datetime.date(2010, 2, 1),
                                                apply_from_date   = datetime.date(2010, 4, 5),
                                                applied_on = single_premium_schedule
                                              )
        FinancialAccountPremiumScheduleFeature.query.session.flush()

        visitor = JoinedVisitor()
        list(visitor.visit_premium_schedule( single_premium_schedule,
                                             datetime.date(2010, 6, 1) ))

        def additional_interest_at(at_date, from_date=None):
            return visitor.get_total_amount_until(single_premium_schedule,
                                                  thru_document_date = at_date,
                                                  from_document_date = from_date,
                                                  fulfillment_type = 'additional_interest_attribution',
                                                  account=FinancialBookingAccount())[0]

        def base_interest_at(at_date, from_date=None):
            return visitor.get_total_amount_until(single_premium_schedule,
                                                  thru_document_date = at_date,
                                                  from_document_date = from_date,
                                                  fulfillment_type = 'interest_attribution',
                                                  account=FinancialBookingAccount())[0]
        def interest_at(at_date):
            return base_interest_at(at_date) + additional_interest_at(at_date)

        def round(x):
            from decimal import ROUND_HALF_UP
            x = D(x)   # to tolerate int parameters instead of decimals
            return x.quantize(D('.01'), rounding=ROUND_HALF_UP)

        def calc_interests(from_date, thru_date, amount, interest_rate, additional_interest_rate):
            days_per_year = D('365')
            one_day_total_interest_factor = (1 + interest_rate + additional_interest_rate)**( D('1')/days_per_year )
            one_day_interest_factor       = (1 + interest_rate)**( D('1')/days_per_year )

            interest = 0
            additional_interest = 0

            ndays = 0
            d = from_date
            while d <= thru_date:
                d += datetime.timedelta(days = 1)
                ndays += 1

                total_interest       = amount * one_day_total_interest_factor - amount
                interest            += amount * one_day_interest_factor - amount
                additional_interest += total_interest - (amount * one_day_interest_factor - amount)
                amount += total_interest

            return (round(interest), round(additional_interest))

        from datetime import date
        interest_rate = D('2.1')/D('100')
        additional_interest_rate = D('0')

        # first amount put on account at feb. 3
        amount = D('2363.62')
        from_date = date(2010, 2, 3 )
        thru_date = date(2010, 2, 28)
        interests = calc_interests(from_date, thru_date, amount, interest_rate, additional_interest_rate)
        total_interest = interests[0] + interests[1]
        amount += interests[0] + interests[1]
        self.assertAlmostEqual(total_interest, -interest_at(thru_date), 2 )

        from_date = date(2010, 3, 1 )
        thru_date = date(2010, 3, 2 )
        interests = calc_interests(from_date, thru_date, amount, interest_rate, additional_interest_rate)
        total_interest += interests[0] + interests[1]
        amount += interests[0] + interests[1]

        # second amount put on account at march 3
        amount += D('2394.62')
        from_date = date(2010, 3, 3 )
        thru_date = date(2010, 3, 31 )
        interests = calc_interests(from_date, thru_date, amount, interest_rate, additional_interest_rate)
        total_interest += interests[0] + interests[1]
        amount += interests[0] + interests[1]
        self.assertAlmostEqual(total_interest, -interest_at(thru_date), 2 )

        # changed additional interest at april 5
        from_date = date(2010, 4, 1 )
        thru_date = date(2010, 4, 4 )
        interests = calc_interests(from_date, thru_date, amount, interest_rate, additional_interest_rate)
        total_interest += interests[0] + interests[1]
        amount += interests[0] + interests[1]
        additional_interest_rate = D('7.3')/D('100')

        from_date = date(2010, 4, 5 )
        thru_date = date(2010, 5, 31 )
        interests = calc_interests(from_date, thru_date, amount, interest_rate, additional_interest_rate)
        total_interest += interests[0] + interests[1]
        amount += interests[0] + interests[1]
        self.assertAlmostEqual(total_interest, -interest_at(thru_date), 2 )

        #
        # check distinction between base interest and additional interest
        #
        thru_date = date(2010, 4, 30 )
        self.assertAlmostEqual( base_interest_at(thru_date, thru_date),          D('-8.18'), 2 )
        self.assertAlmostEqual( additional_interest_at(thru_date, thru_date),   D('-23.55'), 2 )
        thru_date = date(2010, 5, 31 )
        self.assertAlmostEqual( base_interest_at(thru_date, thru_date),          D('-8.50'), 2 )
        self.assertAlmostEqual( additional_interest_at(thru_date, thru_date),   D('-28.27'), 2 )
        return single_premium_schedule

    def get_redeemed_amount( self, premium_schedule, associated_to_id = None ):
        joined = JoinedVisitor()
        return sum( ( joined.get_total_amount_until( premium_schedule,
                                                     account = FinancialBookingAccount(),
                                                     fulfillment_type = ft,
                                                     associated_to_id = associated_to_id )[0] for ft in ['capital_redemption_deduction',
                                                                                                         'interest_redemption_deduction',
                                                                                                         'additional_interest_redemption_deduction'] ), 0 )

    def get_account_value_at( self, premium_schedule, doc_date ):
        joined = JoinedVisitor()
        return joined.get_total_amount_until( premium_schedule,
                                              account = FinancialBookingAccount(),
                                              thru_document_date = doc_date)[0] * -1

    def test_partial_redemption_single_premium( self ):
        single_premium_schedule = self.test_create_entries_for_single_premium()
        redemption_date = self.t3 + datetime.timedelta( days=323 )
        book_thru_date = redemption_date + datetime.timedelta( days = 100 )
        book_thru_date = datetime.date( book_thru_date.year,
                                        book_thru_date.month + 1,
                                        1 ) - datetime.timedelta( days = 1 )
        #
        # define the transaction
        #
        redemption_amount = D('-1000.00')
        transaction = FinancialTransaction( agreement_date = redemption_date,
                                            from_date = redemption_date,
                                            transaction_type = 'partial_redemption',
                                            code=u'666/7777/88888')
        FinancialTransactionPremiumSchedule( within = transaction,
                                             premium_schedule = single_premium_schedule,
                                             described_by = 'amount', quantity = redemption_amount )
        FinancialTransactionCreditDistribution( financial_transaction = transaction,
                                                described_by = 'percentage',
                                                quantity = 100,
                                                iban = 'NL91ABNA0417164300' )
        self.assertFalse( transaction.note )

        FinancialTransaction.query.session.flush()
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())

        joined = JoinedVisitor()
        # make sure the redemption only happens once
        for i in range( 2 ):
            list(joined.visit_premium_schedule( single_premium_schedule, book_thru_date ))
            redeemed = self.get_redeemed_amount( single_premium_schedule )
            self.assertEqual( redeemed, 1000 )
        # Verify the transaction revenue
        redemption_rate_revenue = joined.get_total_amount_at( single_premium_schedule,
                                                              redemption_date,
                                                              account = ProductBookingAccount('redemption_rate_revenue') )[0]
        self.assertAlmostEqual( redemption_rate_revenue, redemption_amount * ( D(5) - D('0.08333') * 10 ) / D(100), 1 )
        # verify that intrest is only attributed for the remaining part
        value_before_redemption = self.get_account_value_at( single_premium_schedule, redemption_date - datetime.timedelta(1) )
        value_after_redemption = self.get_account_value_at( single_premium_schedule, redemption_date )
        self.assertTrue( value_after_redemption < value_before_redemption )
        days_after_redemption = (book_thru_date - redemption_date).days
        value_and_intrest_after_redemption = value_after_redemption * D('1.094') ** ( D(days_after_redemption) / 365 ) # 2.1% + 7.3%
        value_at_thru_date = self.get_account_value_at( single_premium_schedule, book_thru_date )
        self.assertAlmostEqual( value_at_thru_date, value_and_intrest_after_redemption, 2 )
        #
        # define a second partial transaction
        #
        redemption_date = book_thru_date + datetime.timedelta( days = 1 )
        book_thru_date = redemption_date + datetime.timedelta( days = 1 )
        transaction = FinancialTransaction( agreement_date = redemption_date,
                                            from_date = redemption_date,
                                            transaction_type = 'partial_redemption',
                                            code=u'666/7777/88889')
        FinancialTransactionPremiumSchedule( within = transaction,
                                             premium_schedule = single_premium_schedule,
                                             described_by = 'percentage', quantity = D('-50.00') )

        FinancialTransaction.query.session.flush()
        FinancialTransactionCreditDistribution( financial_transaction = transaction,
                                                iban = 'NL91ABNA0417164300' )
        FinancialTransaction.query.session.flush()
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())
        list(joined.visit_premium_schedule( single_premium_schedule, book_thru_date ))
        redeemed = self.get_redeemed_amount( single_premium_schedule )
        # second redemption is 1 day after thru date, so 1 additional day of interest
        self.assertAlmostEqual( redeemed - 1000, ( value_at_thru_date / 2 ) * D('1.094') ** ( D(1) / 365 ), 1 )
        return transaction

    def test_redemption_single_premium( self ):
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        from vfinance.model.financial.summary import account_summary
        agreement = self.create_agreement()
        person = self.natuurlijke_persoon_case.create_natuurlijke_persoon()
        subscriber_role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='subscriber')
        agreement.roles.append(subscriber_role)
        agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='exit_at_first_decease' ) )
        agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='mail_to_first_subscriber' ) )
        single_premium_schedule = FinancialAgreementPremiumSchedule(financial_agreement=agreement,
                                                                    product=self._product,
                                                                    amount=D('65411.90'),
                                                                    duration=200*12,
                                                                    period_type='single',)
        for feature in ['premium_rate_1', 'premium_fee_1', 'funded_premium_rate_1', 'entry_fee', 'premium_taxation_physical_person']:
            single_premium_schedule.agreed_features.append( FinancialAgreementPremiumScheduleFeature( apply_from_date = self.tp,
                                                                                                      premium_from_date = self.tp,
                                                                                                      described_by = feature,
                                                                                                      value=0 ) )
        single_premium_schedule.agreed_features.append( FinancialAgreementPremiumScheduleFeature( apply_from_date = self.tp,
                                                                                                  premium_from_date = self.tp,
                                                                                                  described_by = 'interest_rate',
                                                                                                  value=D('3.55') ) )
        agreement.broker_relation = agreement.get_available_broker_relations()[-1]
        FinancialAgreementRole.query.session.flush()
        self.button_complete(agreement)
        self.button_verified(agreement)
        self.fulfill_agreement(agreement)
        self.button_agreement_forward(agreement)
        agreement.account.change_status('active')
        #
        # move from agreement to account
        #
        single_premium_schedule = list(single_premium_schedule.fulfilled_by)[0]
        list(self.synchronizer.attribute_pending_premiums())
        redemption_date = self.t3 + datetime.timedelta( days=323 )
        book_thru_date = redemption_date + datetime.timedelta( days=100 )
        #
        # define the transaction
        #
        redemption_amount = D('-31505.05')
        transaction = FinancialTransaction( agreement_date = redemption_date,
                                            from_date = redemption_date,
                                            transaction_type = 'partial_redemption',
                                            code=u'666/7777/88888')
        FinancialTransactionPremiumSchedule( within = transaction,
                                             premium_schedule = single_premium_schedule,
                                             described_by = 'amount', quantity = redemption_amount )
        FinancialTransactionCreditDistribution( financial_transaction = transaction,
                                                iban = 'NL91ABNA0417164300' )

        FinancialTransaction.query.session.flush()
        self.assertEqual(single_premium_schedule.last_transaction, None)
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())
        self.session.expire_all()
        self.assertEqual(single_premium_schedule.last_transaction, redemption_date)

        joined = JoinedVisitor()
        list(joined.visit_premium_schedule( single_premium_schedule, book_thru_date ))
        #
        # Transaction completion document - PARTIAL REDEMPTION
        #
        document = TransactionDocument()
        model_context = MockModelContext()
        model_context.obj = transaction
        for step in document.model_run(model_context):
            if isinstance( step, action_steps.ChangeObject ):
                step.get_object().notification_type = 'transaction-completion'
        # numbers already verified above
        # this is to test field injection and template logic
        strings_present = [
            'Dehaen',
            'uw verzoek tot gedeeltelijke afkoop van ',
            '29.676,84',
            # 'Het afgekochte bedrag zal na aftrek van eventuele kosten en/of nog verschuldigde bedragen binnen een periode van 30 dagen'
        ]
        self.assert_generated_transaction_document(step.path, strings_present)
        #
        # Account Movements (transaction details) document
        #
        document = FinancialAccountDocument()
        options = FinancialAccountDocument.Options()
        options.notification_type = 'account-movements'
        options.from_date = self.t3
        options.thru_date = datetime.date(year=2010, month=12, day=1)
        context = document.get_context( single_premium_schedule.financial_account, options )
        self.assert_valid_account_movements_document_context( context )
        model_context = MockModelContext()
        model_context.obj = single_premium_schedule.financial_account
        for step in document.model_run(model_context):
            if isinstance( step, action_steps.ChangeObject ):
                step.get_object().notification_type = 'account-movements'
            if isinstance(step, action_steps.open_file.WordJinjaTemplate):
                # numbers already verified above
                # this is to test field injection and template logic
                strings_present = [
                    'Dehaen',
                    'Betreft: Overzicht verrichtingen contract',
                    'Hierbij vindt u de details van de verrichtingen die gebeurd zijn binnen uw verzekeringscontract',
                    'Investering'
                ]
                self.assert_generated_account_movements_document(step.path, strings_present)
        #
        # Test some account summaries
        #
        model_context = MockModelContext()
        model_context.obj = single_premium_schedule
        fpas_summary = account_summary.FinancialAccountPremiumScheduleSummary()
        list(fpas_summary.model_run(model_context, options))

        model_context = MockModelContext()
        model_context.obj = single_premium_schedule.financial_account
        fa_summary = account_summary.FinancialAccountSummary()
        list( fa_summary.model_run(model_context, options) )
        ft_evolution = account_summary.FinancialAccountEvolution()
        list( ft_evolution.model_run( model_context ) )

        model_context = MockModelContext()
        model_context.obj = transaction
        ft_summary = account_summary.FinancialTransactionAccountsSummary()
        list(ft_summary.model_run(model_context, options))
        return transaction

    def test_redemption_multiple_premiums( self ):
        # A single redemption needs multiple premiums
        #
        # Initial situation is 2 premiums of 2500 euro
        single_premium_schedule = self.test_create_entries_for_single_premium()
        redemption_date = self.t3 + datetime.timedelta( days=323 )
        book_thru_date = redemption_date + datetime.timedelta( days = 100 )
        book_thru_date = datetime.date( book_thru_date.year,
                                        book_thru_date.month + 1,
                                        1 ) - datetime.timedelta( days = 1 )
        # Redeem more than available from 1 premium
        redemption_amount = D('-4000.00')
        transaction = FinancialTransaction( agreement_date = redemption_date,
                                            from_date = redemption_date,
                                            transaction_type = 'partial_redemption',
                                            code=u'666/7777/88888')
        FinancialTransactionPremiumSchedule( within = transaction,
                                             premium_schedule = single_premium_schedule,
                                             described_by = 'amount', quantity = redemption_amount )
        FinancialTransactionCreditDistribution( financial_transaction = transaction,
                                                iban = 'NL91ABNA0417164300' )

        FinancialTransaction.query.session.flush()
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())

        joined = JoinedVisitor()
        list(joined.visit_premium_schedule( single_premium_schedule, book_thru_date ))
        redeemed = self.get_redeemed_amount( single_premium_schedule )
        self.assertEqual( redeemed, -1 * redemption_amount )
        # Value of the first premium should be 0 right after the redemption,
        # and should stay 0
        premiums = list( joined.get_entries( single_premium_schedule, account = FinancialBookingAccount(), fulfillment_type='depot_movement' ) )
        premium_1, premium_2 = premiums
        self.assertTrue( premium_1.doc_date < premium_2.doc_date )
        premium_1_value = joined.get_total_amount_until( single_premium_schedule,
                                                         thru_document_date = redemption_date,
                                                         account =  FinancialBookingAccount(),
                                                         associated_to_id = premium_1.fulfillment_id,
                                                         )[0] + premium_1.amount
        self.assertEqual( premium_1_value, 0 )
        premium_1_value = joined.get_total_amount_until( single_premium_schedule,
                                                         thru_document_date = book_thru_date,
                                                         account =  FinancialBookingAccount(),
                                                         associated_to_id = premium_1.fulfillment_id,
                                                         )[0] + premium_1.amount
        self.assertEqual( premium_1_value, 0 )
        # Sum of both redemptions should total the requested redemption
        premium_1_redemption = self.get_redeemed_amount( single_premium_schedule, associated_to_id = premium_1.fulfillment_id )
        premium_2_redemption = self.get_redeemed_amount( single_premium_schedule, associated_to_id = premium_2.fulfillment_id )
        self.assertEqual( premium_1_redemption + premium_2_redemption, -1 * redemption_amount )
        # Verify the transaction revenue
        redemption_rate_1 = D(5) - D('0.08333') * 10
        redemption_rate_2 = D(5) - D('0.08333') * 9
        redemption_rate_1_revenue = -1 * redemption_rate_1 * premium_1_redemption / D(100)
        redemption_rate_2_revenue = -1 * redemption_rate_2 * premium_2_redemption / D(100)
        redemption_rate_revenue = joined.get_total_amount_at( single_premium_schedule,
                                                              redemption_date,
                                                              account = ProductBookingAccount('redemption_rate_revenue') )[0]
        self.assertAlmostEqual( redemption_rate_revenue, redemption_rate_1_revenue + redemption_rate_2_revenue, 1 )

    def test_profit_attribution( self ):
        single_premium_schedule = self.test_create_entries_for_single_premium()
        profit_attribution_date = self.profit_attribution_date
        book_thru_date = datetime.date( profit_attribution_date.year,
                                        profit_attribution_date.month + 1,
                                        1 ) - datetime.timedelta( days = 1 )
        transaction = FinancialTransaction( agreement_date = profit_attribution_date,
                                            from_date = profit_attribution_date,
                                            transaction_type = 'profit_attribution',
                                            code=u'666/7777/99999')
        FinancialTransactionPremiumSchedule( within = transaction,
                                             premium_schedule = single_premium_schedule,
                                             described_by = 'amount', quantity = 100 )
        
        FinancialTransaction.query.session.flush()
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())

        joined = JoinedVisitor()
        list(joined.visit_premium_schedule( single_premium_schedule, book_thru_date ))

        profit_attribution = joined.get_total_amount_until( single_premium_schedule,
                                                            book_thru_date,
                                                            account = FinancialBookingAccount(),
                                                            fulfillment_type = 'profit_attribution' )[0]
        self.assertAlmostEqual( profit_attribution, -100 )
        #
        # Verify intrest on profit attribution
        #
        # additional interest became valid before profit_attribution_date
        total_interest_rate = D('2.1') + D('7.3')
        future_value = single_period_future_value( 100, profit_attribution_date, book_thru_date, total_interest_rate, 365 )
        profit_entry = list( joined.get_entries( single_premium_schedule, account = FinancialBookingAccount(), fulfillment_type='profit_attribution' ) )[0]
        profit_value = joined.get_total_amount_until( single_premium_schedule,
                                                         thru_document_date = book_thru_date,
                                                         account = FinancialBookingAccount(),
                                                         associated_to_id = profit_entry.fulfillment_id,
                                                         )[0] + profit_entry.amount
        self.assertAlmostEqual( profit_value, -1 * future_value, 1 )
        #
        # Add a third premium to the account, and attach it by force
        # to the premium schedule
        #
        third_entry = self.fulfill_agreement( single_premium_schedule.agreed_schedule.financial_agreement,
                                              fulfillment_date = self.premium_after_profit_attribution_date,
                                              amount = D('2500') )
        FinancialAccountPremiumFulfillment( of = single_premium_schedule,
                                            entry_book_date = third_entry.book_date,
                                            entry_document = third_entry.document,
                                            entry_book = third_entry.book,
                                            entry_line_number = third_entry.line_number,
                                            fulfillment_type = 'premium_attribution',
                                            amount_distribution = -1 * D('2500') )
        FinancialAccountPremiumFulfillment.query.session.flush()
        #
        # Initiate a redemption for an amount larger than the first 2 premiums
        #
        transaction = FinancialTransaction( agreement_date = self.redemption_after_profit_attribution_date,
                                            from_date = self.redemption_after_profit_attribution_date,
                                            transaction_type = 'partial_redemption',
                                            code=u'666/7777/99999')
        FinancialTransactionPremiumSchedule( within = transaction,
                                             premium_schedule = single_premium_schedule,
                                             described_by = 'amount', quantity = -6000 )
        FinancialTransactionCreditDistribution( financial_transaction = transaction,
                                                iban = 'NL91ABNA0417164300' )
        FinancialTransaction.query.session.flush()
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())
        list(joined.visit_premium_schedule( single_premium_schedule, self.redemption_after_profit_attribution_date ))
        redeemed_profit = joined.get_total_amount_until( single_premium_schedule,
                                                         self.redemption_after_profit_attribution_date,
                                                         account = FinancialBookingAccount(),
                                                         fulfillment_type = 'capital_redemption_deduction',
                                                         associated_to_id = profit_entry.fulfillment_id )[0]
        self.assertEqual( redeemed_profit, 0 )
        #
        # Initiate a full redemption
        #
        transaction = FinancialTransaction( agreement_date = self.full_redemption_date,
                                            from_date = self.full_redemption_date,
                                            transaction_type = 'full_redemption',
                                            code=u'666/7777/99999')
        ftps = FinancialTransactionPremiumSchedule( within = transaction,
                                                    premium_schedule = single_premium_schedule,
                                                    described_by = 'percentage', quantity = -100 )
        FinancialTransactionPremiumScheduleTask(creating=ftps, described_by='terminate_payment_thru_date')
        FinancialTransactionCreditDistribution( financial_transaction = transaction,
                                                iban = 'NL91ABNA0417164300' )
        FinancialTransaction.query.session.flush()
        self.button_complete(transaction)
        self.button(transaction, TransactionStatusVerified())
        list(joined.visit_premium_schedule( single_premium_schedule, self.full_redemption_date ))
        redeemed_profit = joined.get_total_amount_until( single_premium_schedule,
                                                         self.full_redemption_date,
                                                         account = FinancialBookingAccount(),
                                                         fulfillment_type = 'capital_redemption_deduction',
                                                         associated_to_id = profit_entry.fulfillment_id )[0]
        self.assertNotEqual( redeemed_profit, 0 )

    def test_direct_debit(self):
        from vfinance.model.bank.direct_debit import DirectDebitBatch
        from vfinance.model.bank.invoice import InvoiceItem
        premium_schedule = [premium for premium in self.test_agreed_to_applied_premium_schedule() if premium.period_type=='monthly'][0]
        invoice_description = str(random.randint(0,10000000000))
        dossier_kost = InvoiceItem(doc_date = self.t0,
                                   premium_schedule = premium_schedule,
                                   item_description = invoice_description,
                                   amount = 250)
        domiciliering = DirectDebitBatch.get_open_direct_debit_batch(described_by='local', spildatum=dossier_kost.doc_date )
        logger.debug('test domicil %s'%domiciliering.id)
        before = len(domiciliering.composed_of)
        DirectDebitBatch.query.session.flush()
        self.assertEqual( premium_schedule.financial_account.get_functional_setting_description_at(dossier_kost.doc_date, 'direct_debit_batch' ),
                          'direct_debit_batch_3' )
        self.assertTrue(dossier_kost.button_voeg_toe_aan_domiciliering() )
        self.assertFalse(dossier_kost.button_voeg_toe_aan_domiciliering() )
        last_direct_debit_batch = dossier_kost.last_direct_debit_batch
        # not equal, since the last batch should be batch 3,
        self.assertNotEqual(last_direct_debit_batch, domiciliering)
        self.assertEqual(last_direct_debit_batch.batch, 'direct_debit_batch_3' )
        domiciliering.query.session.expire_all()
        after = len( domiciliering.composed_of )
        self.assertEqual( before, after )
        # make sure the invoice item amount is in the direct debit details
        details = list(d for d in last_direct_debit_batch.generate_details() if d.remark_1==invoice_description)
        self.assertEqual(len(details), 1)
        self.assertEqual(sum(d.amount for d in details), 250)

    def test_financial_documents( self ):
        from vfinance.model.financial.document_action import FinancialDocumentWizardAction
        from vfinance.model.financial.constants import document_output_types
        #
        # create an account for the package, so there are some documents
        # to print
        #
        self.test_create_entries_for_single_premium()
        model_context = MockModelContext()
        action = FinancialDocumentWizardAction()
        #
        # test various notification types with all all output types
        #
        for notification_type in ['account-state', 'account-movements']:
            for output_type, _output_type_name in document_output_types:
                for i, step in enumerate( action.model_run( model_context ) ):
                    if i == 0:
                        options = step.get_object()
                        options.package = self._package.id
                        options.notification_type = notification_type
                        options.output_type = output_type
                        options.origin = 'TEST'
                    #
                    # when the MessageBox pops up, something went wront
                    #
                    self.assertNotEqual( type( step ), action_steps.MessageBox )
                # documents should be generated
                self.assertTrue( i >= 2 )

    def test_run_simulation(self):
        transaction_simulate = RunTransactionSimulation()

        single_premium_schedule = self.test_create_entries_for_single_premium()

        self.redemption_date = datetime.date.today() - datetime.timedelta(weeks=1)

        transaction = FinancialTransaction(agreement_date=self.redemption_date,
                                           from_date=self.redemption_date,
                                           transaction_type='full_redemption',
                                           code=u'000/0000/00000')
        ftps = FinancialTransactionPremiumSchedule(within=transaction,
                                                   premium_schedule=single_premium_schedule,
                                                   described_by='percentage', quantity=-100)
        FinancialTransactionPremiumScheduleTask(creating=ftps, described_by='terminate_payment_thru_date')
        FinancialTransactionCreditDistribution(financial_transaction=transaction,
                                               iban='NL91ABNA0417164300')

        self.session.flush()
        self.assertFalse(transaction.note)

        model_context = MockModelContext()
        model_context.obj = transaction
        for step in transaction_simulate.model_run(model_context):
            if isinstance(step, PrintJinjaTemplate):
                # Get the new transaction total amount
                past_transaction_total = step.context.get('transaction_total')

        # Set the from_date to today
        transaction.from_date = datetime.date.today()

        for step in transaction_simulate.model_run(model_context):
            if isinstance(step, PrintJinjaTemplate):
                self.assertFalse(self.session.is_active)
                html = step.html
                # Check for a red notification
                notification = u'<span style="color:#f00; font-weight:bold"> - Simulation</span>'
                self._assert_generated_string(html, [notification])
                # Get the transaction total amount
                today_transaction_total = step.context.get('transaction_total')

        # Set the from_date to a later date
        transaction.from_date = self.redemption_date + datetime.timedelta(weeks=2)

        for step in transaction_simulate.model_run(model_context):
            if isinstance(step, PrintJinjaTemplate):
                # Get the new transaction total amount
                future_transaction_total = step.context.get('transaction_total')

        # Check if the new_transaction_total is bigger than transaction_total
        self.assertTrue(abs(today_transaction_total) > abs(past_transaction_total))
        self.assertTrue(abs(future_transaction_total) > abs(today_transaction_total))

        # check if database has not been changed by simulation
        #self.assertEqual(transaction.__dict__, status_pre)

class ImportCase(AbstractFinancialCase):

    @classmethod
    def setUpClass(cls):
        AbstractFinancialCase.setUpClass()
        cls.branch_21_case = Branch21Case('setUp')
        cls.branch_21_case.setUpClass()

    def setUp(self):
        AbstractFinancialCase.setUp(self)
        self.branch_21_case.setUp()
        # verify existence of product
        from vfinance.model.financial.product import FinancialProduct
        from vfinance.model.financial.package import ( FinancialPackage,
                                                       FinancialItemClause )

        product_query = FinancialProduct.query.filter(FinancialProduct.name=='Secure 21')

        if product_query.count() == 0:
            product = FinancialProduct(name='Secure 21',
                             from_date=self.tp,
                             account_number_prefix = 124,
                             account_number_digits = 6,
                             premium_sales_book = 'VPrem',
                             premium_attribution_book = u'DOMTV',
                             depot_movement_book = u'RESBE',
                             interest_book = u'INT',
                             supplier_distribution_book = u'COM',
                             funded_premium_book = 'FPREM' )
            product.flush()

        self.assertEqual(product_query.count(), 1)
        self._product = product_query.first()

        package_query = FinancialPackage.query.filter(FinancialPackage.name=='Secure 21')
        if package_query.count() == 0:
            self._package = FinancialPackage( name = 'Secure 21',
                                              from_customer = 400000,
                                              thru_customer = 499999,
                                              from_supplier = 8000,
                                              thru_supplier = 9000,
                                              )
            object_session( self._package ).flush()

        self._package = package_query.first()

        self.assertEqual( package_query.count() , 1 )

        # create some custom clauses if they dont exist
        for id in [12, 133, 11, 148]:
            if self.session.query( FinancialItemClause ).filter_by( id = id ).count() == 0:
                FinancialItemClause( id = id, available_for = self._package, name = str( id ) )
        self.session.flush()

    def test_rabobank_import(self):
        from vfinance.connector.import_wizard import RabobankImportFormat
        import glob
        import os

        class d(object):
            pass
        options = d()

        # remove leftover imports
        for code in ['023/1000/03261',
                     '023/1000/03362',
                     '023/1000/03463',
                     '023/1000/03564',
                     '023/1000/03665',
                     '023/1000/03766',
                     '023/1000/03867',
                     '023/1000/03968']:
            FinancialAgreement.query.filter(FinancialAgreement.code==code).delete()

        rbf = RabobankImportFormat()

        for fn in glob.glob(os.path.join(test_data_folder, 'csv_rabobank', '*.csv')):
            options.filename = fn
            list( rbf.model_run( None, options ) )


    def test_rabobank_import_data(self):
        from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon
        from vfinance.connector.import_wizard import RabobankImportFormat
        from os import path
        from datetime import date

        class d(object):
            pass
        options = d()
        options.filename = path.join(test_data_folder, 'csv_rabobank', '20110823_Subscriptions_PATRONALE.csv')


        # remove leftover imports
        for code in [u'023/1000/03665',u'023/1000/03766',u'023/1000/03867',u'023/1000/03968']:
            FinancialAgreement.query.filter(FinancialAgreement.code==code).delete()

        for nn in ['75121935159', '54042926230', '77030712542', '46070346572']:
            NatuurlijkePersoon.query.filter(NatuurlijkePersoon._nationaal_nummer==nn).delete()

        # test basic import

        number_of_fa = FinancialAgreement.query.count()

        rbf = RabobankImportFormat()
        list( rbf.model_run( None, options ) )

        self.assertEqual(FinancialAgreement.query.count(), number_of_fa + 4)

        # verify agreement data
        for agreement in [
            {
                'code': '023/1000/03766',
                'from_date': date(2011, 8, 25),
                'agreement_date': date(2011, 8, 22),
                'invested_amount': 17000,
                'geboortedatum': date(1954, 4, 29),
                'gender': 'v',
                'taal': 'nl',
                'zip': '2540',
                'burgerlijke_staat': 'h'
                },
            {
                'code': '023/1000/03968',
                'from_date': date(2011, 8, 25),
                'agreement_date': date(2011, 8, 22),
                'invested_amount': 20000,
                'geboortedatum': date(1946, 7, 3),
                'gender': 'm',
                'taal': 'fr',
                'zip': '5310',
                'burgerlijke_staat': 'h'
                }
            ]:

            fa = FinancialAgreement.query.filter(FinancialAgreement.code==agreement['code']).first()

            self.assertEqual(fa.from_date, agreement['from_date'])
            self.assertEqual(fa.agreement_date, agreement['agreement_date'])
            self.assertEqual(len(fa.invested_amounts), 1)
            self.assertEqual(fa.invested_amounts[0].amount, agreement['invested_amount'])

            np = [role for role in fa.roles if role.described_by=='subscriber'][0].natuurlijke_persoon

            self.assertEqual(np.geboortedatum, agreement['geboortedatum'])
            self.assertEqual(np.gender, agreement['gender'])
            self.assertEqual(np.taal, agreement['taal'])
            self.assertEqual(np.postcode, agreement['zip'])
            self.assertEqual(np.burgerlijke_staat, agreement['burgerlijke_staat'])

    def test_json_export_import_agreement(self):
        import json
        from vfinance.connector.import_wizard import JSONImportFormat
        jif = JSONImportFormat()

        class d(object):
            pass
        options = d()

        agreement = self.branch_21_case.create_agreement()
        self.branch_21_case.complete_agreement( agreement )

        json_export = FinancialAgreementJsonExport()
        context = MockModelContext()
        context.obj = agreement
        action_steps = list( json_export.model_run( context ) )
        options.filename = action_steps[-1].get_path()

        def import_agreement( options ):
            list( jif.model_run( context, options ) )
            return Session().query( FinancialAgreement ).order_by( FinancialAgreement.id.desc() ).first()

        with self.assertRaises(UserException):
            import_agreement(options)

        json_structure = json.load(open(options.filename))
        counter = int(json_structure[0]['code'][-1])
        counter += 1
        json_structure[0]['code']=u'260/0051/' + str(counter).rjust(5, '0')
        counter += 1
        json.dump(json_structure, open(options.filename, 'w'), indent=3)
        agreement_1 = import_agreement( options )
        json_structure[0]['code']=u'260/0051/' + str(counter).rjust(5, '0')
        counter += 1
        json.dump(json_structure, open(options.filename, 'w'), indent=3)
        agreement_2 = import_agreement( options )

        roles_1 = set([role.natuurlijke_persoon for role in agreement_1.roles])
        roles_2 = set([role.natuurlijke_persoon for role in agreement_2.roles])

        self.assertEqual( roles_1, roles_2 )
        #
        # met nieuwe natuurlijke persoon en zelfde nat nummer
        #
        json_structure = json.load( open( options.filename ) )
        json_structure[0]['roles'][0]['natuurlijke_persoon']['voornaam'] = unicode( datetime.datetime.now() )
        json_structure[0]['code']=u'260/0051' + str(counter).rjust(5, '0')
        counter += 1
        json.dump( json_structure, open( options.filename, 'w' ), indent = 3 )
        agreement_3 = import_agreement( options )
        roles_3 = set([role.natuurlijke_persoon for role in agreement_3.roles])
        self.assertEqual( roles_2, roles_3 )
        #
        # met 2 nieuwe natuurlijke personen met onderling gelijk
        # nationaal nummer dat nog niet in de database zit
        #
        json_structure = json.load( open( options.filename ) )
        json_structure[0]['roles'][0]['natuurlijke_persoon']['voornaam'] = unicode( datetime.datetime.now() )
        json_structure[0]['roles'][0]['natuurlijke_persoon']['naam'] = 'f'*50
        json_structure[0]['roles'][0]['natuurlijke_persoon']['nationaal_nummer'] = unicode( datetime.datetime.now() )[-20:]
        json_structure[0]['roles'].append( {'natuurlijke_persoon':json_structure[0]['roles'][0]['natuurlijke_persoon'],
                                            } )
        json_structure[0]['code']=u'260/0051/' + str(counter).rjust(5, '0')
        counter += 1
        json.dump( json_structure, open( options.filename, 'w' ), indent = 3 )
        agreement_3 = import_agreement( options )
        roles_3 = set([role.natuurlijke_persoon for role in agreement_3.roles])
        self.assertNotEqual( roles_2, roles_3 )
        self.assertEqual( len( roles_2 ) + 1, len( roles_3 ) )

