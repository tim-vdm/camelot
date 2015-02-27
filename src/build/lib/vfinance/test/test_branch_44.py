import datetime
from decimal import Decimal as D
import logging

from camelot.model.party import end_of_times

from vfinance.model.bank.account import Account
from vfinance.model.financial.agreement import FinancialAgreementRole, FinancialAgreementFunctionalSettingAgreement
from vfinance.model.financial.visitor.abstract import FinancialBookingAccount
from vfinance.model.financial.visitor.joined import JoinedVisitor


from test_financial import AbstractFinancialCase
import test_branch_21
import test_branch_23

logger = logging.getLogger('vfinance.test.test_branch_44')

class Branch44Case(AbstractFinancialCase):
    
    code = u'000/0000/00101'
    t9 = AbstractFinancialCase.t4

    @classmethod
    def setUpClass(cls):
        AbstractFinancialCase.setUpClass()
        cls.branch_21_case = test_branch_21.Branch21Case( 'setUp' )
        cls.branch_23_case = test_branch_23.Branch23Case( 'setUp' )
        cls.branch_21_case.setUpClass()
        cls.branch_23_case.setUpClass()

    def setUp( self ):
        from vfinance.model.bank.entry import Entry
        from vfinance.model.financial.package import ( FinancialPackage, 
                                                       FinancialNotificationApplicability,
                                                       FunctionalSettingApplicability,
                                                       FinancialProductAvailability,
                                                       FinancialBrokerAvailability )
        super( Branch44Case, self ).setUp()
        self.branch_21_case = test_branch_21.Branch21Case( 'setUp' )
        self.branch_21_case.setUp()
        self.branch_23_case = test_branch_23.Branch23Case( 'setUp' )
        self.branch_23_case.setUp()
        self.branch_23_case.complete_funds()
        self.rechtspersoon_case = self.branch_23_case.rechtspersoon_case
        self.natuurlijke_persoon_case = self.branch_23_case.natuurlijke_persoon_case
        self.tp = self.branch_21_case.tp
        self._package = FinancialPackage( name = 'Branch 44 Package',
                                          from_customer = 1,
                                          thru_customer = 10000,
                                          from_supplier = 8000,
                                          thru_supplier = 9000,
                                          )
        FinancialProductAvailability( available_for = self._package,
                                      product = self.branch_21_case._product,
                                      from_date = self.tp )
        FinancialProductAvailability( available_for = self._package,
                                      product = self.branch_23_case._product,
                                      from_date = self.tp )
        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = self.tp,
                                           notification_type = 'certificate',
                                           template = 'time_deposit/certificate_branch44_nl_BE.xml',
                                           language = 'nl',
                                           premium_period_type = 'single')
        FunctionalSettingApplicability(from_date = self.tp, available_for=self._package, described_by='exit_at_first_decease', availability='selectable')
        FunctionalSettingApplicability(from_date = self.tp, available_for=self._package, described_by='exit_at_last_decease', availability='selectable')
        FunctionalSettingApplicability(from_date = self.tp,
                                       available_for=self._package,
                                       described_by='exit_at_first_decease',
                                       availability='standard')
        FinancialBrokerAvailability( available_for = self._package,
                                     broker_relation = self.rechtspersoon_case.broker_relation,
                                     from_date = self.tp )
        Entry.query.session.flush()
            
    def complete_agreement( self, agreement ):
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        from vfinance.model.financial.commission import FinancialAgreementCommissionDistribution
        from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature
        
        person_subscriber = self.natuurlijke_persoon_case.create_natuurlijke_persoon()
        person_insured_party = self.natuurlijke_persoon_case.create_natuurlijke_persoon(persoon_data=self.natuurlijke_persoon_case.natuurlijke_personen_data[6])
        
        subscriber_role = FinancialAgreementRole(natuurlijke_persoon=person_subscriber, described_by='subscriber', rank=1)
        insured_party_role = FinancialAgreementRole(natuurlijke_persoon=person_insured_party, described_by='insured_party', rank=2)
        
        agreement.roles.append(subscriber_role)
        agreement.roles.append(insured_party_role)

        branch_21_premium_schedule = FinancialAgreementPremiumSchedule( product=self.branch_21_case._product, amount=2500, duration=200*12, period_type='single', direct_debit=False)
        branch_21_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_rate_1', recipient='broker', distribution=D('5') ) )
        branch_21_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='funded_premium_rate_1', recipient='company', distribution=D('1') ) )
        branch_21_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='entry_fee', recipient='company', distribution=D('35') ) )
        
        branch_23_premium_schedule = FinancialAgreementPremiumSchedule(product=self.branch_23_case._product, amount=2500, duration=200*12, period_type='single')
        branch_23_premium_schedule.agreed_features.append( FinancialAgreementPremiumScheduleFeature(apply_from_date = self.tp, premium_from_date = self.tp, described_by='cooling_off_period', value=0) )
        branch_23_premium_schedule.agreed_features.append( FinancialAgreementPremiumScheduleFeature(apply_from_date = self.tp, premium_from_date = self.tp, described_by='investment_delay', value=0) )
        branch_23_premium_schedule.agreed_features.append( FinancialAgreementPremiumScheduleFeature(apply_from_date = self.tp, premium_from_date = self.tp, described_by='financed_commissions_rate', value=6) )
        branch_23_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='financed_commissions_rate', recipient='broker', distribution=D('6') ) )
                
        agreement.invested_amounts.append( branch_21_premium_schedule )
        agreement.invested_amounts.append( branch_23_premium_schedule )
        agreement.use_default_funds()

        agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='exit_at_first_decease' ) )
        agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='mail_to_first_subscriber' ) )
        
        # agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='mail_to_first_subscriber' ) )
        agreement.broker_relation = agreement.get_available_broker_relations()[-1]
        FinancialAgreementRole.query.session.flush()
        return agreement
                
    def test_create_entries( self ):
        from vfinance.model.financial.synchronize import FinancialSynchronizer
        synchronizer = FinancialSynchronizer( self.t4 )
        #
        # setup the agreement
        #
        agreement = self.create_agreement()
        self.complete_agreement( agreement )
        self.button_complete(agreement)
        self.button_verified(agreement)
        entry = self.fulfill_agreement( agreement, amount = sum( ps.amount for ps in agreement.invested_amounts ) )
        self.assertTrue( entry in agreement.related_entries )
        self.assertTrue( agreement.is_fulfilled() )
        #
        # create the account
        #
        self.button_agreement_forward(agreement)
        account = agreement.account
        self.assertEqual( len( account.get_pending_entries() ), 1 )
        #
        # match the premiums
        #
        list( synchronizer.attribute_pending_premiums() )
        for premium_schedule in account.premium_schedules:
            self.assertEqual( premium_schedule.premiums_attributed_to_customer, 1 )
        #
        # run forward
        #
        book_thru_date = datetime.date(2010, 5, 31 )
        for premium_schedule in account.premium_schedules:
            self.assertNotEqual( premium_schedule.end_of_cooling_off, end_of_times() )
            self.assertNotEqual( premium_schedule.earliest_investment_date, end_of_times() )
            
            joined = JoinedVisitor()
            list(joined.visit_premium_schedule( premium_schedule, book_thru_date ))
            #
            # verify if something happened on the account
            #
            initial_amount = joined.get_total_amount_until( premium_schedule,
                                                            thru_document_date = self.t4,
                                                            account = FinancialBookingAccount() )[0]
            self.assertTrue( initial_amount < 0 )
            final_amount = joined.get_total_amount_until( premium_schedule,
                                                          thru_document_date = book_thru_date,
                                                          account = FinancialBookingAccount() )[0]
            self.assertNotEqual( initial_amount, final_amount )
            
        #
        # Verify if proper accounts have been created
        #
        previous_account_number = None
        for premium_schedule in account.premium_schedules:
            account_number = premium_schedule.full_account_number
            self.assertTrue( Account.get_by( number = account_number ) )
            self.assertNotEqual( account_number, previous_account_number )
            previous_account_number = account_number
        #
        # Verify if proper document has been created
        #
        notification = self.verify_last_notification_from_account( account, 'certificate' )
        context = notification.get_context()
        #
        # context should contain data for branch 21 and branch 23 premium
        # schedule
        #
        self.assertEqual( len( context['premiums_data'] ), 2 )
        notification.create_message()
        return account.premium_schedules

