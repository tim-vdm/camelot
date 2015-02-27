# -*- coding: utf-8 -*-

from vfinance.utils import setup_model

from camelot.test.action import MockModelContext

from vfinance.model.bank.product import ProductFeatureApplicability, ProductFeatureDistribution
from vfinance.model.financial.security import (FinancialSecurityQuotation,
                                               AssignAccountNumber)
from vfinance.model.financial.package import FinancialBrokerAvailability
from vfinance.model.financial.visitor.abstract import FinancialBookingAccount
from vfinance.model.financial.visitor.joined import JoinedVisitor

from decimal import Decimal as D
import datetime
from datetime import date

from test_financial import AbstractFinancialCase
import logging

logger = logging.getLogger('vfinance.test.test_ul3_replay')

class UL3ReplayCase(AbstractFinancialCase):
    """
Replay of dossier 200-0015784

screenshots to be found in documentation/venv/replay/

as well as a .rtf file with a simulation of risk premiums
"""

    # copy-paste with changes from branch 21 tests with strategic changes
    # Creates fixed-amount insurance coverage.
    def create_branch_21(self, gender = 'v', smoker = False, surmortality = 0, birthdate = None, 
                         agreement_from_date = None, initial_payment = 0, include_coverage = 'fixed_amount',
                         risk_charge = 0, insured_capital_charge = 0, fictitious_extra_age = 0):
        from vfinance.model.bank.entry import Entry
        from vfinance.model.financial.product import FinancialProduct
        from vfinance.model.financial.package import ( FinancialNotificationApplicability, 
                                                       FunctionalSettingApplicability, 
                                                       FinancialItemClause, 
                                                       FinancialPackage, 
                                                       FinancialProductAvailability)
        from vfinance.model.insurance.product import InsuranceCoverageAvailability, InsuranceCoverageLevel, InsuranceCoverageAvailabilityMortalityRateTable
        from vfinance.model.bank.direct_debit import BankIdentifierCode
        from vfinance.model.insurance.mortality_table import MortalityRateTable
        setup_model()
        self._bic = BankIdentifierCode(country='BE', code='GEBABEBB', name='BNP Paribas')
        self._product = FinancialProduct(name='Branch 21 Account',
                                         from_date=self.tp,
                                         account_number_prefix = 124,
                                         account_number_digits = 6,
                                         premium_sales_book = 'VPrem',
                                         premium_attribution_book = u'DOMTV',
                                         supplier_distribution_book = u'COM',
                                         depot_movement_book = u'RESBE')
        self._package = FinancialPackage(name='Branch 21 Account',
                                         from_customer = 400000,
                                         thru_customer = 499999,
                                         from_supplier = 8000,
                                         thru_supplier = 9000,
                                         )
        FinancialProductAvailability( available_for = self._package,
                                      product = self._product,
                                      from_date = agreement_from_date or self.tp )

        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_taxation_physical_person', value=D('1.1'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_taxation_legal_person', value=D('4.4'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='entry_fee', value=35)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_fee_1', from_passed_duration=1, value=4)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_rate_1', value=5)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='interest_rate', value=D('2.1'), automated_clearing=False)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='interest_rate', value=D('2.2'), automated_clearing=True)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='redemption_rate', value=5)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='monthly_contract_exit_rate_decrease', automated_clearing=True, value=0.0833)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='monthly_premium_exit_rate_decrease', automated_clearing=False, value=0.0833)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='minimum_exit_fee', value=75)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='invoicing_period', value=30)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='direct_debit_period', value=14)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='direct_debit_investment_delay', value=0)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_reduction_non_smoker', value=D('2.22'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_risk_charge', value=risk_charge)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_insured_capital_charge', value=insured_capital_charge)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_general_risk_reduction', value=D('2.22'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_fictitious_extra_age', value=fictitious_extra_age)

        coverage_availability = InsuranceCoverageAvailability(from_date = self.tp, available_for=self._product, of='life_insurance', availability='optional')
        self._coverage_level = InsuranceCoverageLevel(used_in=coverage_availability, type='fixed_amount', coverage_limit_from=D('0'), coverage_limit_thru=D('1000000'))
        self._coverage_level_pa = InsuranceCoverageLevel(used_in=coverage_availability, type='percentage_of_account', coverage_limit_from=D('0'), coverage_limit_thru=D('1000'))
        self._coverage_level_sa = InsuranceCoverageLevel(used_in=coverage_availability, type='surplus_amount', coverage_limit_from=D('0'), coverage_limit_thru=D('1000000'))

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

        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = self.tp,
                                           notification_type = 'certificate',
                                           template = 'time_deposit/certificate_be.xml',
                                           premium_period_type = 'single',
                                           language= 'nl')

        FinancialNotificationApplicability(available_for = self._package,
                                           from_date = self.tp,
                                           notification_type = 'certificate',
                                           template = 'time_deposit/certificate_be.xml',
                                           premium_period_type = 'single',
                                           language= 'fr')

        FinancialBrokerAvailability( available_for = self._package, 
                                     broker_relation = self.rechtspersoon_case.broker_relation,
                                     from_date = agreement_from_date or self.tp )

        Entry.query.session.flush()

        self._agreement = self.create_agreement()
        agreement = self._agreement
        if agreement_from_date:
            agreement.from_date = agreement_from_date
            if agreement.agreement_date < agreement_from_date:
                agreement.agreement_date = agreement_from_date
        else:
            agreement_from_date = agreement.from_date

        from vfinance.model.financial.agreement import FinancialAgreementRole, FinancialAgreementFunctionalSettingAgreement, FinancialAgreementItem
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature
        from vfinance.model.insurance.agreement import InsuranceAgreementCoverage
        from vfinance.model.financial.commission import FinancialAgreementCommissionDistribution
        from vfinance.model.bank.direct_debit import DirectDebitMandate
        from camelot.core.files.storage import StoredFile

        person = self.natuurlijke_persoon_case.create_natuurlijke_persoon()
        if smoker:
            person.rookgedrag = True
        if gender != 'v':
            person.gender = u'm'
            person.naam = u'Slackenerny'
            person.voornaam = u'Mike'
        if birthdate:
            person.geboortedatum = birthdate

        subscriber_role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='subscriber')
        agreement.automated_clearing = ['000','0000001','01']
        agreement.roles.append(subscriber_role)
        insured_role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='insured_party', surmortality=surmortality)
        agreement.roles.append(insured_role)
        single_premium_schedule = FinancialAgreementPremiumSchedule(product=self._product,amount=initial_payment, duration=200*12, period_type='single', direct_debit=False)
        agreement.invested_amounts.append( single_premium_schedule )
        single_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_rate_1', recipient='broker', distribution=D('4') ) )
#        monthly_premium_schedule = FinancialAgreementPremiumSchedule(amount=250, duration=5*12, period_type='monthly', direct_debit=True)
#        monthly_premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_rate_1', recipient='broker', distribution=D('4') ) )
#        agreement.invested_amounts.append( monthly_premium_schedule )
        agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='exit_at_first_decease' ) )
        agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='mail_to_first_subscriber' ) )
        single_premium_schedule.agreed_features.append( FinancialAgreementPremiumScheduleFeature(apply_from_date = agreement_from_date, premium_from_date = agreement_from_date, described_by='premium_rate_1', value=4) )
        if include_coverage == 'fixed_amount':
            single_premium_schedule.agreed_coverages.append( InsuranceAgreementCoverage(coverage_for=self._coverage_level, coverage_limit=D('100000'), duration = 200*12) )
        elif include_coverage == 'percentage_of_account':
            single_premium_schedule.agreed_coverages.append( InsuranceAgreementCoverage(coverage_for=self._coverage_level_pa, coverage_limit=D('100'), duration = 200*12) )
        elif include_coverage == 'surplus_amount':
            single_premium_schedule.agreed_coverages.append( InsuranceAgreementCoverage(coverage_for=self._coverage_level_sa, coverage_limit=D('100000'), duration = 200*12) )
        agreement.agreed_items.append( FinancialAgreementItem(associated_clause=self._clause) )
        mandate = DirectDebitMandate(financial_agreement=agreement,iban='BE06001349359522', bank_identifier_code=self._bic, document=StoredFile(None, 'mandate.pdf') )
        mandate.identification = mandate.get_default_identification()
        agreement.broker_relation = agreement.get_available_broker_relations()[-1]
        FinancialAgreementRole.query.session.flush()

    def create_mortality_rate_tables(self):
        from vfinance.model.insurance.mortality_table  import MortalityRateTable
        setup_model()
        self._mk = MortalityRateTable(name=u"MK")
        self._mk.generate_male_table()
        self._fk = MortalityRateTable(name=u"FK")
        self._fk.generate_female_table()
        MortalityRateTable.query.session.flush()        

    def test_age(self):
        # from UL3 screenshot:
        today = date(2010, 12, 22)
        birthdate = date(1974, 1, 13)
        age_in_days_ul3 = 13492
        # age calculation that also counts leap days
        age_in_days = (today - birthdate).days

        self.assertEqual(age_in_days, age_in_days_ul3)
        # the above test passes, proving that UL3 doesn't calculate age in the same way as v-finance!

    # data from UL3 risk simulation (non-smoker)
    ul3values_near_future = { date(2011, 1,  31) : D('14.92'),
                              date(2013, 1,  31) : D('16.56'),
                              }
    ul3values_middle_future = { date(2021, 12, 31) : D('27.63'),
                                date(2026, 12, 31) : D('40.55'),
                                }
    ul3values_far_future =  { date(2042,  8, 31) : D('168.18'),
                              date(2045, 12, 31) : D('225.76'),
                              }

    def test_risk_premiums_monthly_calculation(self):
        """Reproduce UL3 simulation using custom monthly calculation.
        """
        from vfinance.model.insurance.mortality_table  import MortalityTable
        from vfinance.model.financial.visitor.provision import ProvisionVisitor
        from integration.tinyerp.convenience import add_months_to_date
        from vfinance.model.financial.interest import leap_days
        from datetime import timedelta

        self.create_mortality_rate_tables()
        mortality_table = MortalityTable(self._mk)
        d = date(2011, 1, 1)
        birthdate = date(2011 - 30, 1, 1)

        pv = ProvisionVisitor()
        insured_capital = 100000
        reduction_non_smoker = D('2.22')/D('100')
        age = 0
        age_limit = 65
        risks = {}
        while age < age_limit:
            age    = float(pv.age_at(d, birthdate))/365
            next_d = add_months_to_date(d, 1)
            ndays = (next_d - d).days  - leap_days(d, next_d)
            t = float(ndays)/float(365) 
            q = mortality_table.ftq_x(t, age)
            risk = D(str(q))*(1 - reduction_non_smoker)*insured_capital 
#            print "van %s tot %s: age = %s, risk = %s" % (d, next_d, age, risk)
            risks[next_d + timedelta(days=-1)] = risk
            d = next_d

        for d in self.ul3values_near_future:
            self.assertAlmostEqual(risks[d], self.ul3values_near_future[d], 2)
        for d in self.ul3values_middle_future:
            self.assertAlmostEqual(risks[d], self.ul3values_middle_future[d], 1)
        for d in self.ul3values_far_future:
            self.assertAlmostEqual(risks[d], self.ul3values_far_future[d], 1)

    def test_provision_visitor_risk_premiums(self):
        """Reproduce UL3 simulation using provision visitor.
        """
        from vfinance.model.financial.visitor.provision import ProvisionVisitor
        from integration.tinyerp.convenience import add_months_to_date

        from_date = date(2011, 1, 1)
        birthdate = date(2011 - 30, 1, 1)
        self.create_branch_21(gender = 'm', 
                              smoker = True, 
                              surmortality = 0, 
                              birthdate = birthdate, 
                              agreement_from_date = from_date)

        premium_schedule = self._agreement.invested_amounts[0]
        prov_visitor = ProvisionVisitor()

        alldates = list(prov_visitor.get_document_dates( premium_schedule, premium_schedule.valid_from_date, premium_schedule.valid_thru_date))
        # limit to max 35 years
        dates = []
        for d in alldates:
            if d <= add_months_to_date(premium_schedule.valid_from_date, 35*12):
                dates.append(d)

        premiums = []
        risks = {}
        for e in prov_visitor.get_provision(premium_schedule, 
                                            premium_schedule.valid_from_date, 
                                            dates, 
                                            None, 
                                            premiums,
                                            clip_provision_to_zero = True):
            d = e[0].date
            risk = e[0].risk
            risks[d] = risk

        for d in self.ul3values_near_future:
            self.assertAlmostEqual(risks[d], -self.ul3values_near_future[d], 2)
        for d in self.ul3values_middle_future:
            self.assertAlmostEqual(risks[d], -self.ul3values_middle_future[d], 1)
        for d in self.ul3values_far_future:
            # calculation per day should yield slightly higher result
            self.assertTrue(-risks[d] > self.ul3values_far_future[d])
            # but difference should be small
            self.assertTrue(-risks[d] - self.ul3values_far_future[d] < D('0.5'))

    def tst_provision_visitor_risk_premiums_smoker(self):
        """Reproduce UL3 simulation using provision visitor.
        """
        from vfinance.model.financial.visitor.provision import ProvisionVisitor
        from integration.tinyerp.convenience import add_months_to_date

        from_date = date(2011, 1, 1)
        birthdate = date(2011 - 30, 1, 1)
        self.create_branch_21(gender = 'm', 
                              smoker = False, 
                              surmortality = 0, 
                              birthdate = birthdate, 
                              agreement_from_date = from_date)

        premium_schedule = self._agreement.invested_amounts[0]
        prov_visitor = ProvisionVisitor()

        alldates = list(prov_visitor.get_document_dates( premium_schedule, premium_schedule.valid_from_date, premium_schedule.valid_thru_date))
        # limit to max 35 years
        dates = []
        for d in alldates:
            if d <= add_months_to_date(premium_schedule.valid_from_date, 35*12):
                dates.append(d)

        premiums = []
        risks = {}
        for e in prov_visitor.get_provision(premium_schedule, 
                                            premium_schedule.valid_from_date, 
                                            dates, 
                                            None, 
                                            premiums,
                                            clip_provision_to_zero = True):
            d = e[0].date
            risk = e[0].risk
            risks[d] = risk

        for d in self.ul3values_near_future:
            self.assertAlmostEqual(risks[d], -self.ul3values_near_future[d], 2)
        for d in self.ul3values_middle_future:
            self.assertAlmostEqual(risks[d], -self.ul3values_middle_future[d], 1)
        for d in self.ul3values_far_future:
            # calculation per day should yield slightly higher result
            self.assertTrue(-risks[d] > self.ul3values_far_future[d])
            # but difference should be small
            self.assertTrue(-risks[d] - self.ul3values_far_future[d] < D('0.5'))

    def test_risk_charge(self):
        """Checks if risk charge is correctly applied in provision visitor.
        (at least for fixed amount coverage).
        """
        from vfinance.model.financial.visitor.provision import ProvisionVisitor

        from_date = date(2011, 1, 1)
        thru_date = date(2012, 3, 2)  # basically random
        birthdate = date(2011 - 30, 1, 1)

        # first case: without charge
        self.create_branch_21(gender = 'm', 
                              smoker = False, 
                              surmortality = 0, 
                              birthdate = birthdate, 
                              agreement_from_date = from_date,
                              risk_charge = 0)

        premium_schedule = self._agreement.invested_amounts[0]
        prov_visitor = ProvisionVisitor()

        # calc deducted risk premium after 1 year
        dates = [ thru_date ]
        premiums = []
        e_no_charge = list(prov_visitor.get_provision( premium_schedule, 
                                                       premium_schedule.valid_from_date, 
                                                       dates, 
                                                       None, 
                                                       premiums,
                                                       round_output = False,
                                                       clip_provision_to_zero = True))[0]
        risk_no_charge = e_no_charge[0].risk

        # second case: with charge
        risk_charge = D('5')  # =5%
        self.create_branch_21(gender = 'm', 
                              smoker = False, 
                              surmortality = 0, 
                              birthdate = birthdate, 
                              agreement_from_date = from_date,
                              risk_charge = risk_charge)

        premium_schedule = self._agreement.invested_amounts[0]

        # calc deducted risk premium after 1 year
        e_with_charge = list(prov_visitor.get_provision( premium_schedule, 
                                                         premium_schedule.valid_from_date, 
                                                         dates, 
                                                         None, 
                                                         premiums,
                                                         round_output = False,
                                                         clip_provision_to_zero = True))[0]
        risk_with_charge = e_with_charge[0].risk

        # check correspondence
        self.assertAlmostEqual(risk_with_charge, risk_no_charge*(1 + risk_charge/D('100')), 6)

    def test_insured_capital_charge(self):
        """Checks if insured capital charge is correctly applied in provision visitor.
        (at least for fixed amount coverage).
        """
        from vfinance.model.financial.visitor.provision import ProvisionVisitor

        from_date = date(2011, 1 ,  1)
        thru_date = date(2011, 12, 31)  # must be exactly one year
        birthdate = date(2011 - 30, 1, 1)

        # first case: without charge
        self.create_branch_21(gender = 'm', 
                              smoker = False, 
                              surmortality = 0, 
                              birthdate = birthdate, 
                              agreement_from_date = from_date,
                              insured_capital_charge = 0)

        premium_schedule = self._agreement.invested_amounts[0]
        prov_visitor = ProvisionVisitor()

        # calc deducted risk premium after 1 year
        dates = [ thru_date ]
        premiums = []
        e_no_charge = list(prov_visitor.get_provision(premium_schedule, 
                                                      premium_schedule.valid_from_date, 
                                                      dates, 
                                                      None, 
                                                      premiums,
                                                      round_output = False,
                                                      clip_provision_to_zero = True))[0]
        risk_no_charge = e_no_charge[0].risk

        # second case: with charge
        insured_capital_charge = D('5')  # =5%
        self.create_branch_21(gender = 'm', 
                              smoker = False, 
                              surmortality = 0, 
                              birthdate = birthdate, 
                              agreement_from_date = from_date,
                              insured_capital_charge = insured_capital_charge)

        premium_schedule = self._agreement.invested_amounts[0]

        # calc deducted risk premium after 1 year
        e_with_charge = list(prov_visitor.get_provision(premium_schedule, 
                                                        premium_schedule.valid_from_date, 
                                                        dates, 
                                                        None, 
                                                        premiums,
                                                        round_output = False,
                                                        clip_provision_to_zero = True))[0]
        risk_with_charge = e_with_charge[0].risk

        # check correspondence
        insured_capital = D('100000')  # defined in coverage limit of fixed amount insurance coverage
        self.assertAlmostEqual(risk_no_charge - risk_with_charge, insured_capital_charge/D('100')*insured_capital, 6)

    def test_only_interest(self):
        """Test provision visitor without risk, hence only interest.
        """
        from vfinance.model.financial.visitor.provision import ProvisionVisitor, premium_data
        from integration.tinyerp.convenience import add_months_to_date
        from vfinance.model.financial.interest import single_period_future_value

        initial_capital = 100000
        self.create_branch_21(gender = 'm', initial_payment = initial_capital, include_coverage = False)

        # calc interest after 35 years using visitor (only interest, since no insurance coverage)
        premium_schedule = self._agreement.invested_amounts[0]
        from_date = premium_schedule.valid_from_date
        thru_dates = []
        # calc provision for coming 35 years
        for i in range(1, 35):
            thru_dates.append( add_months_to_date(premium_schedule.valid_from_date, i*12) ) 

        net_premium_amount = premium_schedule.get_amount_at( premium_schedule.premium_amount,
                                                             premium_schedule.valid_from_date,
                                                             premium_schedule.valid_from_date,
                                                             'net_premium' )            

#        premiums = [(from_date, net_premium_amount, premium_schedule.amount)]
        premiums = [ premium_data(date = from_date, amount = net_premium_amount, gross_amount = premium_schedule.amount, associated_surrenderings = None) ]
        prov_visitor = ProvisionVisitor()
        future_values = {}
        for e in prov_visitor.get_provision( premium_schedule, 
                                             premium_schedule.valid_from_date, 
                                             thru_dates, 
                                             None, 
                                             premiums,
                                             round_output = False, 
                                             round_provision = False):
            d = e[0].date
            provision = e[0].provision
            future_values[d] = provision

        # calc interest using interest functions
        interest = premium_schedule.get_applied_feature_at(from_date, from_date, 0, 'interest_rate', default=0).value

        for d in thru_dates:
            future_value_alt = single_period_future_value(net_premium_amount, from_date, d, interest, 365)
            self.assertAlmostEqual( future_values[d], future_value_alt, 5 )

    def test_fictitious_extra_age(self):
        """Checks if fictitious extra age feature is correctly applied in provision visitor.
        """
        from vfinance.model.financial.visitor.provision import ProvisionVisitor, premium_data
        from datetime import timedelta

        from_date = date(2011, 1, 1)
        thru_date = date(2015, 7, 2)  # basically random
        birthdate1 = date(2011 - 30, 1, 1)
        birthdate2 = date(2011 - 30 - 1, 7, 1)  # around six months older
        initial_capital = D('100000')
        extra_age_days = -(birthdate2 - birthdate1).days  # minus to get positive number

        # first case: around 0.5 year of extra age
        self.create_branch_21(gender = 'm', 
                              smoker = False, 
                              surmortality = 0, 
                              birthdate = birthdate1, 
                              agreement_from_date = from_date,
                              initial_payment = initial_capital,
                              fictitious_extra_age = extra_age_days)

        premium_schedule = self._agreement.invested_amounts[0]
        prov_visitor = ProvisionVisitor()

        # calc evolution
        dates = [ from_date, from_date + timedelta(days = 400), thru_date ]
        net_premium_amount = premium_schedule.get_amount_at( premium_schedule.premium_amount,
                                                             premium_schedule.valid_from_date,
                                                             premium_schedule.valid_from_date,
                                                             'net_premium' )
        premiums = [ premium_data(date = from_date, amount = net_premium_amount, gross_amount = premium_schedule.amount,
                                  associated_surrenderings = None) ]
        e_extra_age = list(prov_visitor.get_provision(premium_schedule, 
                                                      premium_schedule.valid_from_date, 
                                                      dates, 
                                                      None, 
                                                      premiums,
                                                      round_output = False))

        # second case: no extra age, but simply older
        self.create_branch_21(gender = 'm', 
                              smoker = False, 
                              surmortality = 0, 
                              birthdate = birthdate2, 
                              agreement_from_date = from_date,
                              initial_payment = initial_capital,
                              fictitious_extra_age = 0)

        premium_schedule = self._agreement.invested_amounts[0]

        # calc evolution
        e_older = list(prov_visitor.get_provision(premium_schedule, 
                                                  premium_schedule.valid_from_date, 
                                                  dates, 
                                                  None, 
                                                  premiums,
                                                  round_output = False))

        # check correspondence
        for i in range(0, len(e_extra_age)):
            pvd = e_extra_age[i]
            d1, prov1, interest1, add_interest1, risk1 = pvd[0].date, pvd[0].provision, pvd[0].interest, pvd[0].additional_interest, pvd[0].risk  
            pvd = e_older[i]
            d2, prov2, interest2, add_interest2, risk2 = pvd[0].date, pvd[0].provision, pvd[0].interest, pvd[0].additional_interest, pvd[0].risk
            self.assertEqual(d1, d2)
            self.assertAlmostEqual(prov1, prov2, 6)
            self.assertAlmostEqual(interest1, interest2, 6)
            self.assertAlmostEqual(add_interest1, add_interest2, 6)
            self.assertAlmostEqual(risk1, risk2, 6)

    def test_insured_surplus_amount(self):
        """Checks if surplus amount insurance charge is correctly applied in provision visitor.
        """
        from vfinance.model.financial.visitor.provision import ProvisionVisitor
        from datetime import timedelta

        from_date = date(2011, 1, 1)
        thru_date = date(2016, 3, 2)  # basically random
        birthdate = date(2011 - 30, 1, 1)

        insured_capital_charge = D('5')  # =5%

        # first case: fixed amount, clip provision to zero
        self.create_branch_21(gender = 'm', 
                              smoker = False, 
                              surmortality = 0, 
                              birthdate = birthdate, 
                              agreement_from_date = from_date,
                              initial_payment = 0,
                              insured_capital_charge = insured_capital_charge
                              )

        premium_schedule = self._agreement.invested_amounts[0]
        prov_visitor = ProvisionVisitor()

        # calc deducted risk premiums
        dates = [ from_date, from_date + timedelta(days = 400), thru_date ]
        premiums = []
        e_fixed_amount = list(prov_visitor.get_provision(premium_schedule, 
                                                         premium_schedule.valid_from_date, 
                                                         dates, 
                                                         None, 
                                                         premiums,
                                                         round_output = False,
                                                         clip_provision_to_zero = True  # to make sure insured amount remains the same
                                                         ))

        # second case: surplus amount equal to amount in fixed amount case
        self.create_branch_21(gender = 'm', 
                              smoker = False, 
                              surmortality = 0, 
                              birthdate = birthdate, 
                              agreement_from_date = from_date,
                              initial_payment = 0,
                              insured_capital_charge = insured_capital_charge,
                              include_coverage = 'surplus_amount')

        premium_schedule = self._agreement.invested_amounts[0]

        # calc deducted risk premiums
        e_surplus_amount = list(prov_visitor.get_provision(premium_schedule, 
                                                           premium_schedule.valid_from_date, 
                                                           dates, 
                                                           None, 
                                                           premiums,
                                                           round_output = False,
                                                           clip_provision_to_zero = False  # no clipping this time
                                                           ))

        # risk deducted in both cases should be the same (due to provision clipping in fixed amount case)
        for i in range(0, len(e_fixed_amount)):
            pvd = e_fixed_amount[i]
            d1, risk1 = pvd[0].date, pvd[0].risk
            pvd = e_surplus_amount[i]
            d2, risk2 = pvd[0].date, pvd[0].risk
            self.assertEqual(d1, d2)
            self.assertAlmostEqual(risk1, risk2, 6)

    def setup_elitis_strategy_plan(self, start_date):
        from vfinance.model.financial.package import FinancialPackage, FinancialProductAvailability
        from vfinance.model.financial.product import FinancialProduct, ProductFundAvailability
        from vfinance.model.financial.security import FinancialFund, FinancialSecurityQuotationPeriodType, FinancialSecurityFeature
        from vfinance.model.insurance.mortality_table import MortalityRateTable
        from vfinance.model.insurance.product import InsuranceCoverageAvailability, InsuranceCoverageLevel, InsuranceCoverageAvailabilityMortalityRateTable

        one_day = datetime.timedelta(days=1)

        self._package = FinancialPackage(name='Elitis Supreme Strategy',
                                         from_customer = 400000,
                                         thru_customer = 499999,
                                         from_supplier = 8000,
                                         thru_supplier = 9000,
                                         )
        FinancialBrokerAvailability( available_for = self._package,
                                     broker_relation = self.rechtspersoon_case.broker_relation,
                                     from_date = datetime.date(2000,1,1) )
        self._product = FinancialProduct(name='Elitis Supreme Strategy',
                                         from_date=start_date,
                                         account_number_prefix = 152,
                                         account_number_digits = 6,
                                         premium_sales_book = 'VPrem',
                                         quotation_book = 'Qout',
                                         premium_attribution_book = u'DOMTV',
                                         depot_movement_book = u'RESBE',
                                         unit_linked=True,
                                         fund_number_digits=3,
                                         numbering_scheme='global',
                                         financed_commissions_prefix='22352',
                                         financed_commissions_sales_book='GIT',
                                         risk_sales_book = u'RISK',
                                         supplier_distribution_book = u'COM',
                                         )
        FinancialProductAvailability( available_for = self._package,
                                      product = self._product,
                                      from_date = start_date or self.tp )
        self.create_accounts_for_product( self._product )

        ProductFeatureApplicability(apply_from_date = start_date, 
                                    premium_from_date = start_date, 
                                    available_for=self._product, 
                                    described_by='insurance_general_risk_reduction', 
                                    value=D('2.22'))

        ProductFeatureApplicability(apply_from_date = start_date + one_day, 
                                    premium_from_date = start_date, 
                                    available_for=self._product, 
                                    described_by='premium_taxation_physical_person',
                                    value=D('1.1'))

        commission_ul3 = D('2')
        management_ul3 = D('2')
        fund_entry_rate_ul3 = D('1')

        premium_rate_1 = -1 * ( 1/((1+management_ul3/100)*(1+commission_ul3/100)) - 1 ) * 100
        fund_entry_rate = 100 * (1 - 100 / ( 100 + fund_entry_rate_ul3 ) )

        feature = ProductFeatureApplicability(apply_from_date = start_date + one_day, 
                                              premium_from_date = start_date, 
                                              available_for=self._product, 
                                              described_by='premium_rate_1',
                                              value=premium_rate_1)
        ProductFeatureDistribution(of=feature, recipient='company', distribution=premium_rate_1)
        

        self.fund_1 = FinancialFund(name='Elitis Invesment Research Value Fund %s'%datetime.datetime.now(),
                                    isin = 'EIR',
                                    purchase_delay = 0,
                                    transfer_revenue_account = '7123' )

        FinancialSecurityFeature( financial_security=self.fund_1,
                                  described_by = 'entry_rate',
                                  value = fund_entry_rate,
                                  apply_from_date = start_date + one_day )

        self._fund_availability = ProductFundAvailability(available_for=self._product,
                                                          fund=self.fund_1,
                                                          default_target_percentage=100)

        self.fund_1.quotation_period_types.append( FinancialSecurityQuotationPeriodType( 
            from_date=datetime.date(2000,1,1),
            thru_date=datetime.date(2400,1,1),
            quotation_period_type = 'monthly',) )

        self.button(self.fund_1, AssignAccountNumber())
        self.button_complete(self.fund_1)
        self.button_verified(self.fund_1)

        coverage_availability = InsuranceCoverageAvailability(available_for=self._product,
                                                              from_date=datetime.date(2000,1,1),
                                                              thru_date=datetime.date(2400,12,31),
                                                              of = 'life_insurance',
                                                              availability = 'optional',)

        mortality_rate_table = MortalityRateTable(name='MK')
        mortality_rate_table.generate_male_table()

        InsuranceCoverageAvailabilityMortalityRateTable(used_in=coverage_availability,
                                                        type='male',
                                                        mortality_rate_table=mortality_rate_table)

        self._coverage_level = InsuranceCoverageLevel(used_in = coverage_availability,
                                                      type = 'fixed_amount',
                                                      coverage_limit_from = 0,
                                                      coverage_limit_thru = 200000)

        self._coverage_level_percentage = InsuranceCoverageLevel(used_in = coverage_availability,
                                                                 type = 'percentage_of_account',
                                                                 coverage_limit_from = 0,
                                                                 coverage_limit_thru = 110)
        self.session.flush()

    def test_monthly_premium(self):
        #
        # Test grootboek of 200-0045132
        # met maandelijkse premies
        #
        from datetime import date as d
        from vfinance.model.financial.agreement import FinancialAgreementRole
        from vfinance.model.financial.summary.agreement_summary import FinancialAgreementSummary
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature

        from vfinance.model.insurance.agreement import InsuranceAgreementCoverage

        from vfinance.model.bank.direct_debit import DirectDebitMandate

        start_date = datetime.date(2009, 12, 30)
        coverage_start_date = datetime.date(2010, 1, 1)
        run_date = datetime.date(2011, 1, 1)
        self.setup_elitis_strategy_plan(start_date)

        quotation_dates = []
        quotations = """23-12-2009 12:00	248.730000
30-12-2009 12:00	249.840000
01-01-2010 12:00	249.840000
06-01-2010 12:00	262.320000
13-01-2010 12:00	261.410000
20-01-2010 12:00	265.590000
27-01-2010 12:00	249.230000
03-02-2010 12:00	259.760000
10-02-2010 12:00	252.490000
17-02-2010 12:00	258.900000
24-02-2010 12:00	259.790000
03-03-2010 12:00	267.840000
10-03-2010 12:00	273.360000
17-03-2010 12:00	270.620000
24-03-2010 12:00	272.210000
31-03-2010 12:00	274.120000
07-04-2010 12:00	285.870000
14-04-2010 12:00	286.480000
21-04-2010 12:00	287.030000
28-04-2010 12:00	279.740000
05-05-2010 12:00	271.380000
12-05-2010 12:00	273.000000
19-05-2010 12:00	264.220000
26-05-2010 12:00	249.740000
02-06-2010 12:00	259.440000
09-06-2010 12:00	260.510000
16-06-2010 12:00	271.710000
23-06-2010 12:00	272.420000
30-06-2010 12:00	261.950000
07-07-2010 12:00	258.580000
14-07-2010 12:00	267.640000
22-07-2010 12:00	266.740000
28-07-2010 12:00	270.680000
04-08-2010 12:00	270.780000
11-08-2010 12:00	267.670000
18-08-2010 12:00	267.220000
25-08-2010 12:00	261.400000
01-09-2010 12:00	264.400000
08-09-2010 12:00	268.950000
15-09-2010 12:00	273.470000
22-09-2010 12:00	268.970000
29-09-2010 12:00	270.190000
06-10-2010 12:00	268.930000
13-10-2010 12:00	269.970000
20-10-2010 12:00	266.280000
27-10-2010 12:00	270.010000
03-11-2010 12:00	272.290000
10-11-2010 12:00	278.100000
17-11-2010 12:00	265.120000
24-11-2010 12:00	268.400000
01-12-2010 12:00	275.000000
08-12-2010 12:00	274.260000
15-12-2010 12:00	268.620000
22-12-2010 12:00	274.190000
29-12-2010 12:00	272.490000
30-12-2010 12:00	272.490000"""

        import re
        line_expression = re.compile(r'^(?P<day>[0-9]{2}).(?P<month>[0-9]{2}).(?P<year>[0-9]{4}).*(?P<before>[0-9]{3}).(?P<after>[0-9]{6}).*')
        for quotation_line in quotations.split('\n') :
            match = line_expression.match(quotation_line)
            day = datetime.datetime( int(match.group('year')), 
                                     int(match.group('month')),
                                     int(match.group('day')) )
            value = D(match.group('before')+'.'+match.group('after') )
            quotation = FinancialSecurityQuotation(financial_security=self.fund_1, 
                                                   from_datetime=day, 
                                                   purchase_date=day.date(),
                                                   sales_date=day.date(),
                                                   value=value)
            if day.date() != start_date:
                # on start date, we want the investment to take place immediately, otherwise
                # wait at least one day
                quotation.set_default_dates()
            quotation_dates.append(day.date())

        invested_amount = D('9246.75') #D('8694.56') 
        coverage_limit = D('110')
        monthly_amount = D('258.82')

        session = FinancialAgreementRole.query.session

        agreement = self.create_agreement()#code=['200', '0045', '13200'])
        agreement.from_date = start_date
        agreement.agreement_date = start_date

        person = self.natuurlijke_persoon_case.create_natuurlijke_persoon(self.natuurlijke_persoon_case.natuurlijke_personen_data[5])
        role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='subscriber')
        agreement.roles.append(role)
        role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='insured_party')
        agreement.roles.append(role)
        role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='beneficiary')
        agreement.roles.append(role)

        session.flush()
        self.fund_1.change_quotation_statuses( 'verified' )

        single_premium_schedule = FinancialAgreementPremiumSchedule(amount=monthly_amount,
                                                                    product=self._product,
                                                                    duration=200*12,
                                                                    period_type='monthly',
                                                                    direct_debit=True,
                                                                    financial_agreement=agreement)

        FinancialAgreementPremiumScheduleFeature(agreed_on=single_premium_schedule,
                                                 apply_from_date = start_date, 
                                                 premium_from_date = start_date, 
                                                 described_by='maximum_additional_premium_accepted', 
                                                 value=invested_amount)

        InsuranceAgreementCoverage(premium=single_premium_schedule,
                                   coverage_for=self._coverage_level_percentage,
                                   coverage_limit=coverage_limit,
                                   from_date=coverage_start_date,
                                   duration=12*5)

        mandate = DirectDebitMandate( from_date = start_date, 
                                      described_by = 'local',
                                      financial_agreement = agreement,
                                      iban = '038-18086-%i'%agreement.id )
        mandate.identification = mandate.get_default_identification()

        session.flush()
        agreement.use_default_funds()
        self.button_complete(agreement)
        self.button_verified(agreement)

        self.fulfill_agreement(agreement, fulfillment_date=start_date, amount=invested_amount)
        # since the amount on this entry is not
        #
        # First synchronization create account and move premium to customer
        # without moving further so we can check the intermediate state
        #
        financial_account_premium_schedule = None
        self.button_agreement_forward(agreement)
        for fulfillment in single_premium_schedule.fulfilled_by:
            financial_account_premium_schedule = fulfillment
        self.assertTrue( financial_account_premium_schedule )
        list(self.synchronizer.attribute_pending_premiums())
        
        premiums_payed_at = [d(2010,  1, 6),
                             d(2010,  2, 3),
                             d(2010,  3, 10),
                             d(2010,  4, 1),
                             d(2010,  5, 1),
                             d(2010,  6, 9),
                             d(2010,  7, 6),
                             d(2010,  8, 2),
                             d(2010,  9, 1),
                             d(2010, 10, 1),
                             d(2010, 10, 28),
                             d(2010, 11, 30)]
        for premium_date in premiums_payed_at:
            self.fulfill_agreement(agreement, 
                                   fulfillment_date=premium_date, 
                                   amount=monthly_amount,
                                   remark='Nr domiciliation %s'%mandate.identification)#iban.replace('-',''))

        #
        # See if we have pending premiums
        #
        self.assertEqual( len(agreement.related_entries), 13 )

        list(self.synchronizer.attribute_pending_premiums())
        self.assertEqual( financial_account_premium_schedule.fulfillment_date, start_date )
        #
        # Verify the attribution of premiums to the account
        # 
        from vfinance.model.financial.visitor.account_attribution import AccountAttributionVisitor
        from vfinance.model.financial.visitor.customer_attribution import CustomerAttributionVisitor
        customer_attribution = CustomerAttributionVisitor()
        customer_attribution.get_customer_at( financial_account_premium_schedule, self.t3 )
        self.visit_premium_schedule(customer_attribution, financial_account_premium_schedule, run_date)
        account_attribution_visitor = AccountAttributionVisitor()
        document_dates = set( account_attribution_visitor.get_document_dates(financial_account_premium_schedule,
                                                                             start_date,
                                                                             run_date) )
        self.assertTrue( start_date in document_dates )
        self.assertEqual( len(document_dates), 13)
        #
        # Check if the pending premiums have been used, the direct debited are not
        # longer there
        #
        # self.assertEqual( len(agreement.related_entries), 1 )
        #
        # Calculate some risk premiums
        #
        from vfinance.model.financial.visitor.risk_deduction import RiskDeductionVisitor

        risk_deduction_visitor = RiskDeductionVisitor()
        for pvd, details in risk_deduction_visitor.get_provision(financial_account_premium_schedule, 
                                                                 datetime.date(2010, 1, 1), 
                                                                 [datetime.date(2010, 1, 31)], 
                                                                 [invested_amount], # + D('552.19'), # due to quotation change at 1/1/2010
                                                                 premiums = [] ):
            date, interest, risk = pvd.date, pvd.interest + pvd.additional_interest, pvd.risk
            self.assertEqual( date,         datetime.date(2010, 1, 31) )
            self.assertEqual( interest,     0 )
            self.assertEqual( risk,         D('0.37') * -1 )
        #
        # Now do a full run forward
        #
        joined = JoinedVisitor()
        list(joined.visit_premium_schedule( financial_account_premium_schedule, run_date))
        #
        # Invoices should be created
        #
        financial_account_premium_schedule.create_invoice_item( run_date )
        session.expire( financial_account_premium_schedule )
        self.assertTrue( len(financial_account_premium_schedule.invoice_items) )
        fund_distribution = financial_account_premium_schedule.fund_distribution[0]

        def depot_movement_at(at_date):
            return account_attribution_visitor.get_total_amount_at(financial_account_premium_schedule, 
                                                                   at_date, 
                                                                   fulfillment_type = 'depot_movement',
                                                                   account = FinancialBookingAccount() )[0]


        def fund_attribution_at(at_date):
            return account_attribution_visitor.get_total_amount_at(financial_account_premium_schedule, 
                                                                   at_date, 
                                                                   fulfillment_type = 'fund_attribution', 
                                                                   account = FinancialBookingAccount('fund', fund_distribution.fund) )[:2]

        def financed_commissions_at(at_date):
            return account_attribution_visitor.get_total_amount_at(financial_account_premium_schedule, 
                                                                   at_date,
                                                                   fulfillment_type = 'financed_commissions_deduction', 
                                                                   account = FinancialBookingAccount() )[:2]

        def fund_value_at(at_date):
            return account_attribution_visitor.get_total_amount_until(financial_account_premium_schedule, 
                                                                      at_date, 
                                                                      account = FinancialBookingAccount('fund', fund_distribution.fund) )[:2]

        #
        # First premium should be without taxes and commissions
        #
        self.assertEqual( depot_movement_at( start_date ), -1 * invested_amount )
        #
        # After that, taxes and commissions should be deduced
        #
        self.assertEqual( depot_movement_at( datetime.date(2010,  1,  6) ), D('-246.06') )
        self.assertEqual( depot_movement_at( datetime.date(2010,  9,  1) ), D('-246.06') )
        #
        # Assert value and units after intial transer
        #
        self.assertEqual( fund_value_at( datetime.date(2010,  1,  1) ),       (D('-9246.75'), D('37.010686')) ) # in UL3, the number of units is 37.010674
        #
        # Fund attribution for risk premiums
        #
        for attribution_date, amount, units in [
            (datetime.date(2010,  1,  6), D('0.37') + D('-243.62'), D('-0.001411') + D('0.928713') ), # in UL3, the number of units is 0.001410
            (datetime.date(2010,  2,  3), D('0.35') + D('-243.62'), D('-0.001348') + D('0.937865') ), # UL3 : 0.001347, 0.937866
            (datetime.date(2010,  3,  3), D('0.41'),                 D('-0.001531') ),
            (datetime.date(2010,  3, 10), D('-243.62'),              D('0.891205') ),
            (datetime.date(2010,  4,  7), D('0.44') + D('-243.62'),  D('-0.001540') + D('0.852205') ),  # UL3 : 0.00139
            (datetime.date(2010,  5,  5), D('0.47') + D('-243.62'),  D('-0.001732') + D('0.897708') ), 
            (datetime.date(2010,  6,  2), D('0.41'),                 D('-0.001581') ), # UL3 : 0.001580
            (datetime.date(2010,  6,  9), D('-243.62'),              D('0.935165') ), # UL3 : 0.935166
            (datetime.date(2010,  7,  7), D('0.45') + D('-243.62'),  D('-0.001741') + D('0.942145') ), # UL3 : 0.46 risk en 0.942146
            (datetime.date(2010,  8,  4), D('0.48') + D('-243.62'),  D('-0.001773') + D('0.899697') ),
            #(datetime.date(2010,  9,  8), D('0.46') + D('-243.62'),  D('-0.001711') + D('0.921406') ), # UL3 : 0.56 euro - 0.002082  en 0.921407 op 7/9 -> 16% gestegen tov vorige maand verschil
            ]:
            self.assertEqual( fund_attribution_at( attribution_date ), (amount, units ) ) 
        #
        # Value before second risk premium
        #
        self.assertEqual( fund_value_at( datetime.date(2010,  3,  3) ), (D('-10411.73'), D('38.872974')) ) # in UL3, 38.872964
        self.assertEqual( fund_value_at( datetime.date(2010,  4,  7) ), (D('-11610.56'), D('40.614844')) ) # in UL3, 40.614836
        self.assertEqual( fund_value_at( datetime.date(2010,  5,  5) ), (D('-11265.21'), D('41.510820')) ) # in UL3. 41.510812
        self.assertEqual( fund_value_at( datetime.date(2010,  6,  2) ), (D('-10769.15'), D('41.509239')) ) # in UL3. 41.509232
        self.assertEqual( fund_value_at( datetime.date(2010,  7,  7) ), (D('-11218.45'), D('43.384808')) ) # in UL3, 43.384764
        self.assertEqual( fund_value_at( datetime.date(2010,  8,  4) ), (D('-11990.87'), D('44.282732')) ) # in UL3, 44.282688

        #
        # see if the agreement summary works, move this to the end of the test
        # as it takes a long time to complete.
        #
        agreement_summary = FinancialAgreementSummary()
        context = MockModelContext()
        context.obj = agreement
        list( agreement_summary.model_run( context ) )

    def test_elitis(self):
        #
        # Test grootboek of 200-0015784
        #
        # Start datum moet de laatste NAV datum zijn in UL3
        #
        from datetime import date as d
        from vfinance.model.financial.agreement import FinancialAgreementRole
        from vfinance.model.financial.summary.agreement_summary import FinancialAgreementSummary
        from vfinance.model.financial.commission import FinancialAgreementCommissionDistribution
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature

        from vfinance.model.insurance.agreement import InsuranceAgreementCoverage

        from vfinance.model.financial.visitor.abstract import AbstractVisitor
        from vfinance.model.financial.visitor.joined import JoinedVisitor
        abstract_visitor = AbstractVisitor()
        joined_visitor = JoinedVisitor()

        start_date = datetime.date(2007,12,31)
        self.setup_elitis_strategy_plan( start_date )
        invested_amount = D('84682.27')
        coverage_limit = D('67102.80')
        financed_commissions_amount = D('117.43') * 4 + D('71.51') # 555.56
        financed_commissions_quarterly_amount = D('140.91')
        financed_commissions_rate = 100 * financed_commissions_amount/invested_amount
        financed_commissions_deduction_rate = 100 * financed_commissions_quarterly_amount/financed_commissions_amount
        financed_commissions_deduced_interest = 100 * D('23.48') / D('140.91')

        session = FinancialAgreementRole.query.session

        quotation_dates = []
        for day, quotation in [(datetime.datetime(year=2007, month=10, day=10),  D('432.17')),
                               (datetime.datetime(year=2007, month=10, day=17),  D('430.26')),
                               (datetime.datetime(year=2007, month=10, day=31),  D('422.83')),
                               (datetime.datetime(year=2007, month=11, day=7),   D('402.31')),
                               (datetime.datetime(year=2007, month=11, day=14),  D('495.20')),
                               (datetime.datetime(year=2007, month=11, day=21),  D('371.21')),
                               (datetime.datetime(year=2007, month=11, day=28),  D('387.35')),
                               (datetime.datetime(year=2007, month=12, day=5),   D('397.87')),
                               (datetime.datetime(year=2007, month=12, day=12),  D('399.24')),
                               (datetime.datetime(year=2007, month=12, day=19),  D('388.15')),
                               (datetime.datetime(year=2007, month=12, day=27),  D('399.80')),
                               (datetime.datetime(year=2007, month=12, day=31),  D('399.80')), ## Dummy quotation to force evaluation at import date
                               (datetime.datetime(year=2008, month=1, day=2),    D('395.23')),

                               (datetime.datetime(year=2008, month=1, day=9),     D('386.34')),
                               (datetime.datetime(year=2008, month=1, day=16),    D('365.13')),
                               (datetime.datetime(year=2008, month=1, day=23),    D('341.67')),
                               (datetime.datetime(year=2008, month=1, day=30),    D('352.11')),

                               (datetime.datetime(year=2008, month=2, day=6),     D('342.91')),
                               (datetime.datetime(year=2008, month=2, day=13),    D('343.25')),
                               (datetime.datetime(year=2008, month=2, day=20),    D('347.63')),
                               (datetime.datetime(year=2008, month=2, day=27),    D('349.86')),

                               (datetime.datetime(year=2008, month=3, day=5),     D('336.73')),
                               (datetime.datetime(year=2008, month=3, day=12),    D('328.42')),
                               (datetime.datetime(year=2008, month=3, day=19),    D('315.86')),
                               (datetime.datetime(year=2008, month=3, day=26),    D('325.64')),

                               (datetime.datetime(year=2008, month=4, day=2),     D('345.05')),
                               (datetime.datetime(year=2008, month=4, day=9),     D('338.98')),
                               (datetime.datetime(year=2008, month=4, day=16),    D('338.25')),
                               (datetime.datetime(year=2008, month=4, day=23),    D('343.02')),

                               (datetime.datetime(year=2008, month=5, day=7),     D('357.13')),
                               (datetime.datetime(year=2008, month=5, day=14),    D('335.10')),
                               (datetime.datetime(year=2008, month=5, day=21),    D('343.73')),
                               (datetime.datetime(year=2008, month=5, day=28),    D('343.21')),

                               (datetime.datetime(year=2008, month=6, day=4),     D('344.99')),
                               (datetime.datetime(year=2008, month=6, day=11),    D('324.89')),
                               (datetime.datetime(year=2008, month=6, day=18),    D('328.04')),
                               (datetime.datetime(year=2008, month=6, day=25),    D('312.87')),

                               (datetime.datetime(year=2008, month=7, day=2),     D('295.95')),
                               (datetime.datetime(year=2008, month=7, day=9),     D('295.66')),
                               (datetime.datetime(year=2008, month=7, day=16),    D('281.95')),
                               (datetime.datetime(year=2008, month=7, day=23),    D('306.74')),
                               (datetime.datetime(year=2008, month=7, day=30),    D('295.89')),

                               (datetime.datetime(year=2008, month=8, day=6),     D('304.41')),
                               (datetime.datetime(year=2008, month=8, day=13),    D('299.55')),
                               (datetime.datetime(year=2008, month=8, day=20),    D('291.84')),
                               (datetime.datetime(year=2008, month=8, day=27),    D('288.89')),

                               (datetime.datetime(year=2008, month=9, day=3),     D('296.24')),
                               (datetime.datetime(year=2008, month=9, day=10),    D('290.60')),
                               (datetime.datetime(year=2008, month=9, day=17),    D('256.38')),
                               (datetime.datetime(year=2008, month=9, day=24),    D('258.09')),

                               (datetime.datetime(year=2008, month=10, day=1),    D('250.34')),
                               (datetime.datetime(year=2008, month=10, day=8),    D('205.55')),
                               (datetime.datetime(year=2008, month=10, day=15),   D('196.49')),
                               (datetime.datetime(year=2008, month=10, day=22),   D('181.26')),
                               (datetime.datetime(year=2008, month=10, day=29),   D('164.36')),

                               (datetime.datetime(year=2008, month=11, day=5),    D('193.1')),
                               (datetime.datetime(year=2008, month=11, day=12),   D('182.92')),
                               (datetime.datetime(year=2008, month=11, day=19),   D('160.40')),
                               (datetime.datetime(year=2008, month=11, day=26),   D('164.18')),

                               (datetime.datetime(year=2008, month=12, day=3),    D('167.18')),
                               (datetime.datetime(year=2008, month=12, day=10),   D('180.56')),
                               (datetime.datetime(year=2008, month=12, day=17),   D('169.31')),
                               (datetime.datetime(year=2008, month=12, day=24),   D('165.18')),

                               ]:
            quotation = FinancialSecurityQuotation(financial_security=self.fund_1, 
                                                   from_datetime=day, 
                                                   purchase_date=day.date(),
                                                   sales_date=day.date(),
                                                   value=quotation)
            if day.date() != start_date:
                # on start date, we want the investment to take place immediately, otherwise
                # wait at least one day
                quotation.set_default_dates()
            quotation_dates.append(day.date())

        agreement = self.create_agreement()
        agreement.from_date = start_date
        agreement.agreement_date = start_date
        agreement.broker_relation = agreement.get_available_broker_relations()[-1]

        person = self.natuurlijke_persoon_case.create_natuurlijke_persoon(self.natuurlijke_persoon_case.natuurlijke_personen_data[4])
        role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='subscriber')
        agreement.roles.append(role)
        role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='insured_party')
        agreement.roles.append(role)
        role = FinancialAgreementRole(natuurlijke_persoon=person, described_by='beneficiary')
        agreement.roles.append(role)

        single_premium_schedule = FinancialAgreementPremiumSchedule(product=self._product,
                                                                    amount=invested_amount,
                                                                    duration=200*12,
                                                                    period_type='single',
                                                                    financial_agreement=agreement)

        FinancialAgreementPremiumScheduleFeature(agreed_on=single_premium_schedule,
                                                 apply_from_date = start_date, 
                                                 premium_from_date = start_date, 
                                                 described_by='financed_commissions_rate', 
                                                 value=financed_commissions_rate)

        FinancialAgreementPremiumScheduleFeature(agreed_on=single_premium_schedule,
                                                 apply_from_date = start_date, 
                                                 premium_from_date = start_date, 
                                                 described_by='financed_commissions_deduction_rate', 
                                                 value=financed_commissions_deduction_rate)

        FinancialAgreementPremiumScheduleFeature(agreed_on=single_premium_schedule,
                                                 apply_from_date = start_date, 
                                                 premium_from_date = start_date, 
                                                 described_by='financed_commissions_deduced_interest', 
                                                 value=financed_commissions_deduced_interest)

        FinancialAgreementPremiumScheduleFeature(agreed_on=single_premium_schedule,
                                                 apply_from_date = start_date, 
                                                 premium_from_date = start_date, 
                                                 described_by='financed_commissions_periodicity', 
                                                 value=3)

        FinancialAgreementCommissionDistribution(premium_schedule=single_premium_schedule,
                                                 described_by='financed_commissions_rate', 
                                                 recipient='broker', 
                                                 distribution=financed_commissions_rate )

        InsuranceAgreementCoverage(premium=single_premium_schedule,
                                   coverage_for=self._coverage_level,
                                   coverage_limit=coverage_limit,
                                   duration=12*200)
        session.flush()
        self.fund_1.change_quotation_statuses( 'verified' )
        agreement.use_default_funds()
        self.button_complete(agreement)
        self.button_verified(agreement)

        #
        # see if the agreement summary works
        #
        agreement_summary = FinancialAgreementSummary()
        context = MockModelContext()
        context.obj = agreement
        list( agreement_summary.model_run( context ) )

        self.fulfill_agreement(agreement, fulfillment_date=start_date)

        #
        # First synchronization will put money on the account
        #
        from vfinance.model.financial.synchronize import FinancialSynchronizer, SynchronizerOptions
        sync_options = SynchronizerOptions()
        sync_options.run_forward = False
        synchronizer = FinancialSynchronizer(max(quotation_dates))
        list( synchronizer.all( sync_options ) )

        financial_account_premium_schedule = None
        for fulfillment in single_premium_schedule.fulfilled_by:
            financial_account_premium_schedule = fulfillment            
        #
        # Verify there is no cooling of
        #
        self.assertEqual( financial_account_premium_schedule.end_of_cooling_off, start_date )

        #
        # Calculate some risk premiums
        #
        from vfinance.model.financial.visitor.risk_deduction import RiskDeductionVisitor

        risk_deduction_visitor = RiskDeductionVisitor()
        for pvd, details in risk_deduction_visitor.get_provision( financial_account_premium_schedule, 
                                                                  datetime.date(2008, 11, 1), 
                                                                  [datetime.date(2008, 11, 30)], 
                                                                  [D('34573.23')],
                                                                  premiums = [] ):
            date, provision, interest, risk = pvd.date, pvd.provision, pvd.interest + pvd.additional_interest, pvd.risk
            self.assertEqual( date,         datetime.date(2008, 11, 30) )
            self.assertEqual( interest,     0 )
            self.assertEqual( risk,         D('5.85') * -1 )
            self.assertEqual( provision,    D('34567.38') )

        for pvd, details in risk_deduction_visitor.get_provision( financial_account_premium_schedule, 
                                                                  datetime.date(2008, 7, 1), 
                                                                  [datetime.date(2008, 7, 31)], 
                                                                  [ D('65992.55') + D('0.20') ],
                                                                  premiums = [] ):
            date, provision, interest, risk = pvd.date, pvd.provision, pvd.interest + pvd.additional_interest, pvd.risk
            self.assertEqual( date,         datetime.date(2008, 7, 31) )
            self.assertEqual( interest,     0 )
            self.assertEqual( risk,         D('0.21') * -1 ) # UL3 says 0.20 ! !
            self.assertEqual( provision,    D('65992.54') )  # UL3 says 65992.55 ! !

        #
        # Calculate some financed commission premiums
        #
        from vfinance.model.financial.visitor.financed_commission import FinancedCommissionVisitor
        financed_commission_visitor = FinancedCommissionVisitor()
        remaining_capital = financed_commissions_amount
        for doc_date, ul3_capital, ul3_interest in [(d(2008,  3,  31),  D('117.43'), D('23.48') ), # UL3 says 117.43, 23.48 
                                                    (d(2008,  6,  30),  D('117.43'), D('23.48') ),
                                                    (d(2008,  9,  30),  D('117.43'), D('23.48') ),
                                                    (d(2008, 12,  31),  D('117.43'), D('23.48') ),
                                                    (d(2009,  3,  31),  D('71.51'),  D('14.30') ), ]: # UL3 says 71.51, 14.33
            total_amount, interest, capital, remaining_capital = financed_commission_visitor.get_amount_to_deduce_at( financial_account_premium_schedule, 
                                                                                                                      doc_date,
                                                                                                                      start_date,
                                                                                                                      financed_commissions_amount,
                                                                                                                      remaining_capital )
            self.assertEqual( interest, ul3_interest )
            self.assertEqual( capital, ul3_capital )
            self.assertEqual( total_amount, ul3_interest + ul3_capital)

#        #
#        # Create an order and place it at each end of the month
#        #
#        # order_dates = [start_date, datetime.date(2007,12,31)] + [datetime.date(2008,i,calendar.monthrange(2008,i)[1]) for i in range(1,12)]
#        order_dates = [start_date, datetime.date(2007,12,31)] + [qd - datetime.timedelta(days=1) for qd in quotation_dates]
#        for order_date in order_dates:
#            joined_visitor.visit_premium_schedule(financial_account_premium_schedule, order_date)

        list(joined_visitor.visit_premium_schedule( financial_account_premium_schedule, max(quotation_dates) ))

        fund_distribution = financial_account_premium_schedule.fund_distribution[0]

        def fund_attribution_at(at_date):
            return abstract_visitor.get_total_amount_at(financial_account_premium_schedule, 
                                                        at_date, 
                                                        fulfillment_type='fund_attribution', 
                                                        account=FinancialBookingAccount('fund', fund_distribution.fund) )[:2]

        def financed_commissions_at(at_date):
            return abstract_visitor.get_total_amount_at(financial_account_premium_schedule, 
                                                        at_date,
                                                        fulfillment_type='financed_commissions_deduction', 
                                                        account=FinancialBookingAccount() )[:2]

        def fund_value_at(at_date):
            return abstract_visitor.get_total_amount_until(financial_account_premium_schedule, 
                                                           at_date, 
                                                           account=FinancialBookingAccount('fund', fund_distribution.fund) )[:2]

        self.assertEqual( financed_commissions_at( datetime.date(2008,  3,  31) )[0], D('140.91') )
        self.assertEqual( financed_commissions_at( datetime.date(2008,  6,  30) )[0], D('140.91') )
        self.assertEqual( financed_commissions_at( datetime.date(2008,  9,  30) )[0], D('140.91') )

        self.assertEqual( fund_attribution_at( datetime.date(2007, 12, 31) ), (D('-84682.27'), D('211.811580')) ) # in UL3, the exact number of units is 211.811590
        self.assertEqual( fund_attribution_at( datetime.date(2008,  4,  2) ), (D('140.91'),    D('-0.408376')) ) # in UL3, the number of units is -0.408376
        self.assertEqual( fund_attribution_at( datetime.date(2008,  7,  2) ), (D('140.91') + D('0.20'),    D('-0.476128') + D('-0.000676')) ) # exact numbers from UL3
        self.assertEqual( fund_attribution_at( datetime.date(2008,  8,  6) ), (D('0.87'),    D('-0.002858')) ) # exact numbers from UL3

        self.assertEqual( fund_value_at( datetime.date(2008,  8,  27) ),      (D('-60933.71'), D('210.923542')) ) # in UL3, the number of units is 210.923553
        self.assertEqual( fund_attribution_at( datetime.date(2008,  9,  3) ), (D('1.11'),      D('-0.003747')) ) # exact numbers from UL3
        self.assertEqual( fund_attribution_at( datetime.date(2008, 10,  1) ), (D('140.91'),    D('-0.562875')) ) # in UL3, the number of units is -0.562874
        self.assertEqual( fund_attribution_at( datetime.date(2008, 10,  8) ), (D('2.38'),      D('-0.011579')) ) # exact numbers from UL3
        self.assertEqual( fund_attribution_at( datetime.date(2008, 11,  5) ), (D('5.85'),      D('-0.030296')) ) # in UL3, the number of units is -0.030295