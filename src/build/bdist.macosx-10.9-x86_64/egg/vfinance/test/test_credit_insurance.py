# encoding=UTF-8
'''
@author: michael
'''
from datetime import date
from decimal import Decimal
from decimal import Decimal as D
from vfinance.model.insurance.real_number import real, set_real_mode, to_decimal, \
                                                 reset_to_decimal_mode, FLOAT
import copy
import dateutil

from vfinance.test.test_financial import AbstractFinancialCase

from vfinance.model.bank.product import ProductFeatureApplicability
from vfinance.model.insurance.mortality_table  import MortalityRateTable
from vfinance.model.insurance.agreement import InsuranceAgreementCoverage, InsuredLoanAgreement
from vfinance.model.financial.package import FinancialPackage, FinancialNotificationApplicability, FinancialProductAvailability, FinancialBrokerAvailability
from vfinance.model.financial.product import FinancialProduct
from vfinance.model.insurance.product import InsuranceCoverageAvailability, InsuranceCoverageLevel, \
                                             InsuranceCoverageAvailabilityMortalityRateTable
from vfinance.model.financial.agreement import FinancialAgreement, FinancialAgreementRole, FinancialAgreementFunctionalSettingAgreement
from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature
from vfinance.model.financial.commission import FinancialAgreementCommissionDistribution
from vfinance.model.financial.visitor.provision import ProvisionVisitor, premium_data
from vfinance.model.financial.visitor.account_attribution import AccountAttributionVisitor
from vfinance.model.financial.visitor.joined import JoinedVisitor
from vfinance.model.financial.notification import utils

class AbstractCreditInsuranceCase(AbstractFinancialCase):

    def setUp(self):
        AbstractFinancialCase.setUp(self)
        # first set decimal mode
        set_real_mode(FLOAT)  # set to float
        self._mk = MortalityRateTable(name=u"MK")
        self._mk.generate_male_table()
        self._fk = MortalityRateTable(name=u"FK")
        self._fk.generate_female_table()
        self.session.flush()

    def create_product_definition(self, name, reduction, interest_rate = Decimal('3.25')):
        self._package = FinancialPackage(name=name,
                                         from_customer = 400000,
                                         thru_customer = 499999,
                                         from_supplier = 8000,
                                         thru_supplier = 9000,
                                         )
        self._product = FinancialProduct(name=name, 
                                         from_date=self.tp,
                                         account_number_prefix = 124,
                                         account_number_digits = 6,
                                         premium_sales_book = u'VPrem',
                                         premium_attribution_book = u'DOMTV',
                                         depot_movement_book = u'RESBE',
                                         supplier_distribution_book = u'COM',
                                         # age_days_a_year = Decimal('365.23'),
                                         # for risk bookings
                                         risk_sales_book = u'RISK',
                                         # for interest bookings
                                         interest_book = u'INT',
                                        )
        FinancialProductAvailability( available_for = self._package,
                                      product = self._product,
                                      from_date = self.tp )
        FinancialBrokerAvailability( available_for = self._package,
                                     broker_relation = self.rechtspersoon_case.broker_relation,
                                     from_date = self.tp )
        self.create_accounts_for_product( self._product )

        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='interest_rate', value=interest_rate)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_reduction_non_smoker',  value=Decimal('15'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_general_risk_reduction',        value=reduction)
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_surmortality',          value=Decimal('0'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_insured_capital_charge',value=Decimal('0.03'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_rate_1',       value=Decimal('15'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_fee_1',                     value=Decimal('4'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='premium_taxation_physical_person',value=Decimal('1.1'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_risk_charge', value=Decimal('0'))
        ProductFeatureApplicability(apply_from_date = self.tp, premium_from_date = self.tp, available_for=self._product, described_by='insurance_fictitious_extra_age', value=0)

        coverage_availability = InsuranceCoverageAvailability(from_date = self.tp, available_for=self._product, of='life_insurance', availability='required')
        self._coverage_level = InsuranceCoverageLevel(used_in=coverage_availability, type='amortization_table', coverage_limit_from=1, coverage_limit_thru=100)

        InsuranceCoverageAvailabilityMortalityRateTable(used_in = coverage_availability, type = 'male', mortality_rate_table = self._mk)
        InsuranceCoverageAvailabilityMortalityRateTable(used_in = coverage_availability, type = 'female', mortality_rate_table = self._fk)
        
        self.fr_ssv_certificate = FinancialNotificationApplicability(available_for = self._package,
                                                                     from_date = self.t0,
                                                                     notification_type = 'certificate',
                                                                     template = 'time_deposit/certificate_ssv_fr_BE.xml',
                                                                     language = 'fr',
                                                                     premium_period_type = 'yearly')
                                                                            
        self.nl_ssv_certificate = FinancialNotificationApplicability(available_for = self._package,
                                                                     from_date = self.tp,
                                                                     notification_type = 'certificate',
                                                                     template = 'time_deposit/certificate_ssv_nl_BE.xml',
                                                                     language = 'nl',
                                                                     premium_period_type = 'yearly')
                                                                            
        FinancialProduct.query.session.flush()                

    def create_person(self, smoker = True, male = True):
        # create natural person
        persoon_data = copy.copy( self.natuurlijke_persoon_case.natuurlijke_personen_data[0] )
        # due to strange behavior after changes to test_natuurlijke_persoon.py, we (temporarily?)
        # create persons ourselves here.
        
        def get_country(code, name):
            from vfinance.model.bank.varia import Country_
            c = Country_(**{'name':name,'code':code})
            c.flush()
            return c

        def create_natuurlijke_persoon(persoon_data):
            """Helper function to create a unique natuurlijke persoon"""
            from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon
            # first create titles if they don't exist yet
            self.natuurlijke_persoon_case.create_titles([(u'M.', u'M.', u'contact'),(u'Ms.', u'Ms.', u'contact')])
            #persoon_data['land'] 
            persoon_data['land'] = get_country(u'ÎT', u'Itålia')
            persoon_data['correspondentie_land'] = get_country(u'MÃ', u'Macedonië')
            persoon_data['nationaliteit'] = get_country(u'ÎT', u'Itålia')
            persoon = NatuurlijkePersoon(**persoon_data)
            self.assertTrue( persoon.land )
            persoon.flush()
            return persoon

        if male:
            persoon_data['gender'] = u'm'
            if smoker:
                persoon_data['voornaam'] = u'Guust'
                persoon_data['naam'] = u'Flater'
                persoon_data['taal'] = u'nl'
            else:
                persoon_data['voornaam'] = u'Marcel'
                persoon_data['naam'] = u'Kiekeboe'
                persoon_data['taal'] = u'nl'
        else:
            persoon_data['gender'] = u'v'
            persoon_data['voornaam'] = u'Fanny'
            persoon_data['naam'] = u'Kiekeboe'
            persoon_data['taal'] = u'nl'

        persoon_data['geboortedatum'] = date(1970, 7, 1)
        persoon_data['rookgedrag'] = smoker
        #self._person = self.create_natuurlijke_persoon(persoon_data)
        self._person = create_natuurlijke_persoon(persoon_data)
        FinancialProduct.query.session.flush()
        
    def create_agreement(self,
                         loan_amount = Decimal('150000'),
                         interest_rate = Decimal('6'),
                         number_of_months = 240,
                         period_type='yearly',
                         surmortality = None,
                         surmortality2 = None,
                         insurance_reduction_rate = None):
        # create agreement
        self.t1 = date(2010, 11, 15) # What is this line doing ?? if t1 is changed, all other t's should be changed as well
        # FYI:self.t1 is also used in test_documents(self)
        self._agreement = FinancialAgreement(package = self._package,
                                             code = self.next_agreement_code(),
                                             agreement_date = self.t0,
                                             from_date = self.t1
                                             )
        self._agreement.agreed_functional_settings.append( FinancialAgreementFunctionalSettingAgreement( described_by='exit_at_last_decease' ) )
        self._agreement.flush()
        self._agreement.change_status('draft')
        self._agreement.broker_relation = self._agreement.get_available_broker_relations()[-1]
        self.assertFalse( self._agreement.is_complete() )
        role = FinancialAgreementRole(natuurlijke_persoon=self._person, described_by = 'subscriber')
        self._agreement.roles.append(role)
        self.assertFalse( self._agreement.is_complete() )
        role = FinancialAgreementRole(natuurlijke_persoon=self._person, described_by = 'insured_party', surmortality = surmortality)
        self._agreement.roles.append(role)
        role = FinancialAgreementRole(natuurlijke_persoon=self._person, described_by = 'beneficiary')
        self._agreement.roles.append(role)
        # if exists, add second insured party
        if hasattr(self, '_person2') and self._person2 != None:
          role = FinancialAgreementRole(natuurlijke_persoon=self._person2, described_by = 'insured_party', surmortality = surmortality2)
          self._agreement.roles.append(role)
        
        self._premium = FinancialAgreementPremiumSchedule(product=self._product,
                                                          period_type=period_type,
                                                          duration = number_of_months,
                                                          amount=0,
                                                          payment_duration=number_of_months)
        if insurance_reduction_rate is not None:
            FinancialAgreementPremiumScheduleFeature(described_by='insurance_reduction_rate',
                                                     value=insurance_reduction_rate,
                                                     apply_from_date = self.tp,
                                                     premium_from_date = self.tp,
                                                     agreed_on = self._premium)
        self._premium.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_rate_1', recipient='broker', distribution=D('15') ) )
        self._premium.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_fee_1', recipient='broker', distribution=D('4') ) )    
        self._coverage = InsuranceAgreementCoverage(coverage_for=self._coverage_level, coverage_limit=100, duration = 12)
        self._loan = InsuredLoanAgreement(loan_amount = loan_amount,
                                          interest_rate = interest_rate,
                                          number_of_months = number_of_months,
                                          credit_institution=self.rechtspersoon_case.rechtspersoon_1 )
        #self._loan = InsuredLoanAgreement( loan_amount = loan_amount, interest_rate = 0, type_of_payments = 'bullet', number_of_months = number_of_months, credit_institution=self.rechtspersoon_1 )
        self._loan.insurance_agreement_coverage.append(self._coverage)
        self._premium.agreed_coverages.append(self._coverage)
        self._agreement.invested_amounts.append(self._premium)
        self._premium.button_calc_optimal_payment_duration()
        self._loan.update_upstream()  # only necessary in tests, automatic with user interface

        FinancialProduct.query.session.flush()
        return self._agreement

class CreditInsuranceCase( AbstractCreditInsuranceCase ):
       
    # for document tests (Jeroen)
    def create_account(self):
        self._premium.button_calc_credit_insurance_premium()
        self._agreement.invested_amounts[0].flush()
        self.button_complete(self._agreement)
        self.button_verified(self._agreement)
        self.fulfill_agreement( self._agreement )
        self.button_agreement_forward( self._agreement )
        self._agreement.flush()
        # Necessary because of dates
        self._agreement.account.change_status('draft')
        # copied from branch 21 (without exact knowledge of what it does)
        self._premium_schedules = []
        for invested_amount in self._agreement.invested_amounts:
            self.assertEqual( invested_amount.current_status_sql, 'verified' )
            self._premium_schedules.extend( list(invested_amount.fulfilled_by) )
        self._agreement.flush()
        self._account = self._agreement.account
                                    
    # test for mortality table in book-based (non-patigny) formulas
    @reset_to_decimal_mode
    def test_mortality_table(self):
        from vfinance.model.insurance.mortality_table import MortalityTable, MortalityTable2Lives

        # mortality table (in this case: for men)
        mtable = MortalityTable(self._mk)

        x = 5
        l_x = mtable.fl_x(x)
        q_x = mtable.fq_x(x)
        self.assertAlmostEqual(l_x, real('995256.03372'), 4)
        self.assertAlmostEqual(q_x, real('0.000969669011'))

        x = 65
        l_x = mtable.fl_x(x)
        q_x = mtable.fq_x(x)
        self.assertAlmostEqual(l_x, real('716046.27396'), 4)
        self.assertAlmostEqual(q_x, real('0.029148200298'))

        # mortality table (in this case: for women)
        mtable = MortalityTable(self._fk)

        x = 10
        l_x = mtable.fl_x(x)
        q_x = mtable.fq_x(x)
        self.assertAlmostEqual(l_x, real('992386.34314'), 4)
        self.assertAlmostEqual(q_x, real('0.000780486311'))

        x = 70
        l_x = mtable.fl_x(x)
        q_x = mtable.fq_x(x)
        self.assertAlmostEqual(l_x, real('698012.54892'), 4)
        self.assertAlmostEqual(q_x, real('0.037546149544'))

        # test to check if surmortality works correctly
        mtable = MortalityTable(self._fk)
        # second table with 60% surmortality
        mtablesurm = MortalityTable(self._fk, real('0.6'))

        x = 30
        q_x = mtable.fq_x(x)
        p_x = mtable.fp_x(x)
        q_x2 = mtablesurm.fq_x(x)
        p_x2 = mtablesurm.fp_x(x)
        self.assertAlmostEqual(real('1.6')*q_x, q_x2, 10)
        self.assertAlmostEqual(q_x,  1 - p_x,  10)
        self.assertAlmostEqual(q_x2, 1 - p_x2, 10)
        t = 1/real('365')
        q_x = mtable.ftq_x(t, x)
        p_x = mtable.ftp_x(t, x)
        q_x2 = mtablesurm.ftq_x(t, x)
        p_x2 = mtablesurm.ftp_x(t, x)
        self.assertAlmostEqual(real('1.6')*q_x, q_x2, 10)
        self.assertAlmostEqual(q_x,  1 - p_x,  10)
        self.assertAlmostEqual(q_x2, 1 - p_x2, 10)
        t = 1/real('12')
        q_x = mtable.ftq_x(t, x)
        p_x = mtable.ftp_x(t, x)
        q_x2 = mtablesurm.ftq_x(t, x)
        p_x2 = mtablesurm.ftp_x(t, x)
        self.assertAlmostEqual(real('1.6')*q_x, q_x2, 10)
        self.assertAlmostEqual(q_x,  1 - p_x,  10)
        self.assertAlmostEqual(q_x2, 1 - p_x2, 10)

        # test to check if insurance on 2 lives works correctly
        mtabley = MortalityTable(self._mk)
        mtable2lives = MortalityTable2Lives(self._fk, self._mk)
        x = 30
        y = real('40.5')
        q_x = mtable.fq_x(x)
        p_x = mtable.fp_x(x)
        q_y = mtabley.fq_x(y)
        q_xy = mtable2lives.fq_xy(x, y)
        p_xy = mtable2lives.fp_xy(x, y)
        self.assertAlmostEqual(q_x + q_y - q_x*q_y, q_xy, 10)
        self.assertAlmostEqual(q_x,  1 - p_x,  10)
        self.assertAlmostEqual(q_xy, 1 - p_xy, 10)

        # check surmortality
        mtablea = MortalityTable(self._mk)
        mtableb = MortalityTable(self._mk, real('0.6'))
        for i in range(1, 91):
            qa = mtablea.fq_x(i)
            qb = mtableb.fq_x(i)
            self.assertAlmostEqual(qb, real('1.6')*qa, 10)
            qc = mtablea.fq_x(i + real('0.5'))
            qd = mtableb.fq_x(i + real('0.5'))
            # the recalculated mortality table method results in inaccurately imposed surmortality rates,
            # hence only 2 Decimals are required
            self.assertAlmostEqual(qd, real('1.6')*qc, 2)

        # test to check if insurance on 2 lives works correctly with surmortality
        mtabley = MortalityTable(self._mk, real('0.6'))
        mtable2lives = MortalityTable2Lives(self._fk, self._mk, 0, real('0.6'))
        x = 30
        y = real('40.5')
        q_x = mtable.fq_x(x)
        q_ysurm = mtabley.fq_x(y)
        q_xy = mtable2lives.fq_xy(x, y)
        p_xy = mtable2lives.fp_xy(x, y)
        self.assertAlmostEqual(q_x + q_ysurm - q_x*q_ysurm, q_xy, 10)
        self.assertAlmostEqual(q_xy, 1 - p_xy, 10)
        
        # check if multiplication property holds (failed in case of surmortality in previous implementation)
        # A. No surmortality
        mtable = MortalityTable(self._mk)
        x = real('40.3')
        t = real('2.21')
        u = real('0.08')
        tupx = mtable.ftp_x(t + u, x)
        tpx  = mtable.ftp_x(t    , x)
        upxt = mtable.ftp_x(u    , x + t)
        self.assertAlmostEqual(tupx, tpx * upxt, 10)
        # B. With surmortality
        mtable = MortalityTable(self._mk, real('0.6'))
        x = real('40.3')
        t = real('2.21')
        u = real('0.08')
        tupx = mtable.ftp_x(t + u, x)
        tpx  = mtable.ftp_x(t    , x)
        upxt = mtable.ftp_x(u    , x + t)
        self.assertAlmostEqual(tupx, tpx * upxt, 15)
        
    def tst_future_value(self):
        """Start by calculating the future value of an amount very simple, and increase the difficutly
        """
        from vfinance.model.financial.interest import single_period_future_value, leap_days
        import datetime
        principal_amount = 1000
        days_a_year = 360
        age = 25
        annual_percentage_rate = real(5)
        from_date = datetime.date(year=2000, month=1, day=1)  
        #
        # only apply interest, all at once
        #
        thru_date = from_date + datetime.timedelta(days=days_a_year*20 - 1)
        thru_date = thru_date + datetime.timedelta( leap_days(from_date, thru_date) )
        only_interest_at_once = single_period_future_value( principal_amount, from_date, thru_date, annual_percentage_rate, days_a_year )

        #
        # only apply interest, on a monthly basis
        #
        interval_from_date = from_date
        interval_start_capital = principal_amount
        for _i in range(12*20):
            thru_date = interval_from_date + datetime.timedelta(days=29)
            thru_date = thru_date + datetime.timedelta( leap_days(interval_from_date, thru_date) )
            interval_start_capital = single_period_future_value( interval_start_capital, interval_from_date, thru_date, annual_percentage_rate, days_a_year )
            interval_from_date = thru_date + datetime.timedelta(days=1)
        only_interest_monthly = interval_start_capital
        
        self.assertAlmostEqual(only_interest_at_once, only_interest_monthly, 6)

        #
        # use a mortality table where nobody dies
        #
        from vfinance.model.insurance.mortality_table  import MockMortalityTable
        from vfinance.model.insurance.credit_insurance import CreditInsurance2
        eternal_life = MockMortalityTable()
        eternal_life_yearly = CreditInsurance2.future_value(eternal_life, age, principal_amount, from_date, thru_date, annual_percentage_rate, days_a_year, D(360) )
        self.assertAlmostEqual(eternal_life_yearly, only_interest_monthly, 6)
        eternal_life_monthly = CreditInsurance2.future_value(eternal_life, age, principal_amount, from_date, thru_date, annual_percentage_rate, days_a_year, D(30) )
        self.assertAlmostEqual(eternal_life_monthly, only_interest_monthly, 6)
        # eternal_life_daily = CreditInsurance2.future_value(eternal_life, age, principal_amount, from_date, thru_date, annual_percentage_rate, days_a_year, D(1) )
        # seems not to work yet, maybe leap days
        #self.assertAlmostEqual(eternal_life_daily, only_interest_at_once, 6)

    def test_calc_premium_in_various_cases(self):

        def new_agreement(smoker = True, male = True, two_insured_parties = False, **kwargs):
            self.create_person(smoker = smoker, male = male)
            if two_insured_parties:
                self._person2 = self._person
                self.create_person(male = False)
            else:
                self._person2 = None
            self.create_agreement(**kwargs)
            self._premium.button_calc_credit_insurance_premium()
            self._agreement.invested_amounts[0].flush()
            
        # Family:
        self.create_product_definition(u'Credit Insurance - Family', D('0'))

        # default
        new_agreement()
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('985.03'), 2)
        # non-smoker
        new_agreement(smoker = False)
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('847.22'), 2)
        # non-smoker female
        new_agreement(smoker = False, male = False)
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('537.06'), 2)
        # monthly
        new_agreement(period_type = 'monthly')
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('87.85'), 2)
        # monthly with reduction
        new_agreement(period_type = 'monthly', insurance_reduction_rate=D('50'))
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('46.30'), 2)
        # surmortality
        new_agreement(surmortality = D('50'))
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('1439.17'), 2)

        # check the same, but by specifying periodic interest (monthly)
        new_agreement()        
        self._loan.periodic_interest = real('0.5')
        self.assertAlmostEqual(real(self._loan.interest_rate), real('6.1677811864'), 5)
        self._premium.button_calc_credit_insurance_premium()
        self._agreement.invested_amounts[0].flush()
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('989.69'), 2)

        # check the same, but by specifying periodic interest (quarterly)
        new_agreement()        
        self._loan.payment_interval = 3;
        self._loan.periodic_interest = real('1.1')
        self.assertAlmostEqual(real(self._loan.interest_rate), real('4.4731338640'), 5)
        self._premium.button_calc_credit_insurance_premium()
        self._agreement.invested_amounts[0].flush()
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('1622.86'), 2) # warning: value doesn't originate from excel

        # Affinity:
        self.create_product_definition(u'Credit Insurance - Affinity', D('10'))

        # default
        new_agreement()        
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('893.24'), 2)
        # non-smoker
        new_agreement(smoker = False)
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('768.81'), 2)
        # non-smoker female
        new_agreement(smoker = False, male = False)
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('489.03'), 2)
        # monthly
        new_agreement(period_type = 'monthly')        
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('80.06'), 2)
        # surmortality
        new_agreement(surmortality = D('50'))
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('1303.73'), 2)


        # Two insured parties:
        # default
        new_agreement(two_insured_parties = True)
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('1386.25'), 2)
        # non-smoker
        new_agreement(smoker = False, two_insured_parties = True)
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('1264.72'), 2)
        # monthly
        new_agreement(period_type = 'monthly', two_insured_parties = True)        
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('121.99'), 2)
        # surmortality
        new_agreement(surmortality = D('50'), two_insured_parties = True)
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('1629.0'), 2)
        # surmortality second person
        new_agreement(surmortality2 = D('50'), two_insured_parties = True)
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('1787.33'), 2)
        # surmortality both persons
        new_agreement(surmortality = D('50'), surmortality2 = D('40'), two_insured_parties = True)
        self.assertAlmostEqual(real(self._agreement.invested_amount), real('1946.71'), 2)

    # function for use in provision tests: calc provision at endof contract:
    def check_provision_at_end(self):
        premium_schedule = self._premium
        prov_visitor = ProvisionVisitor()
        thru_date = premium_schedule.valid_thru_date
        if premium_schedule.has_credit_insurance():
            for cov in premium_schedule.agreed_coverages:
                if cov.has_credit_insurance:
                    thru_date = cov.thru_date

        # construct premium payment tuples list
        premiums = []
        net_premium_amount = premium_schedule.get_amount_at( premium_schedule.amount, 
                                                             premium_schedule.valid_from_date, 
                                                             premium_schedule.valid_from_date, 
                                                             'net_premium' )
        visitor = AccountAttributionVisitor()
        for d in visitor.get_payment_dates(premium_schedule, premium_schedule.valid_from_date, premium_schedule.valid_thru_date):
            premiums.append( premium_data(date = d, amount = net_premium_amount, gross_amount = premium_schedule.amount, 
                                          associated_surrenderings = None) )

        # calc provision at end, first without rounding
        pvd = list(prov_visitor.get_provision(premium_schedule, premium_schedule.valid_from_date, [thru_date], None, premiums, round_output = False))[0]
        self.assertTrue( pvd[0].provision > 0 )
        self.assertAlmostEqual( abs(pvd[0].provision), 0, delta = 2 * len(premiums) * 0.01 )

        # calc provision at end, with rounding
        pvd = list(prov_visitor.get_provision(premium_schedule, premium_schedule.valid_from_date, [thru_date], None, premiums, round_output = True))[0] 
        self.assertTrue( pvd[0].provision > 0 )
        self.assertAlmostEqual( abs(pvd[0].provision), 0, delta = 2 * len(premiums) * 0.01 )

    @reset_to_decimal_mode
    def test_check_provision_at_end_of_contract(self):
        
        def check_agreement(two_insured_parties = False, **kwargs):
            self.create_person()
            if two_insured_parties:
                self._person2 = self._person
                self.create_person(male = False)
            else:
                self._person2 = None
            self.create_agreement(**kwargs)
            self._premium.button_calc_credit_insurance_premium()
            self._agreement.invested_amounts[0].flush()
            self.check_provision_at_end()
            
        self.create_product_definition(u'Credit Insurance - Affinity', D('10'))

        # check default agreement
        check_agreement()
        # check with monthly payment
        check_agreement(period_type = 'monthly')
        # check with surmortality
        check_agreement(surmortality = Decimal('50'))
        # check with monthly payment and surmortality
        check_agreement(period_type = 'monthly', surmortality = Decimal('50'))
       
        # same tests but with very high loan amount
        loan_amount = Decimal('100000000')  # one hundred million
        check_agreement(loan_amount = loan_amount)
        # check with monthly payment
        check_agreement(loan_amount = loan_amount, period_type = 'monthly')
        # check with surmortality
        check_agreement(loan_amount = loan_amount, surmortality = Decimal('50'))
        # check with monthly payment and surmortality
        check_agreement(loan_amount = loan_amount, period_type = 'monthly', surmortality = Decimal('50'))

        # same tests but with very high loan amount and two insured parties
        loan_amount = Decimal('100000000')  # one hundred million
        check_agreement(True, loan_amount = loan_amount)
        # check with monthly payment
        check_agreement(True, loan_amount = loan_amount, period_type = 'monthly')
        # check with surmortality
        check_agreement(True, loan_amount = loan_amount, surmortality = Decimal('50'))
        # check with monthly payment and surmortality
        check_agreement(True, loan_amount = loan_amount, period_type = 'monthly', surmortality = Decimal('50'))
        # same but with surmortality on second person
        check_agreement(True, loan_amount = loan_amount, period_type = 'monthly', surmortality2 = Decimal('50'))
        # same but with surmortality on both persons
        check_agreement(True, loan_amount = loan_amount, period_type = 'monthly', surmortality = Decimal('-30'), surmortality2 = Decimal('50'))

    # Previously, a 'risk bonus' (positive risk) was erroneously added to contracts that no longer had any risk.
    # Before this was fixed (by not dividing by p in the provision visitor when there is no insured capital)
    # this test failed. 
    @reset_to_decimal_mode
    def test_check_risk_bonus(self):
        from integration.tinyerp.convenience import add_months_to_date
        
        self.create_product_definition(u'Credit Insurance - Affinity', D('10'))
        self.create_person()
        self._person2 = None
        self.create_agreement(period_type = 'monthly')
        self._premium.button_calc_credit_insurance_premium()
        self._agreement.invested_amounts[0].flush()
        self._coverage.duration = 5*12
        self._coverage.flush()
            
        premium_schedule = self._premium
        prov_visitor = ProvisionVisitor()
        thru_date = premium_schedule.valid_thru_date
        if premium_schedule.has_credit_insurance():
            for cov in premium_schedule.agreed_coverages:
                if cov.has_credit_insurance:
                    thru_date = cov.thru_date

        # construct premium payment tuples list
        premiums = []
        net_premium_amount = premium_schedule.get_amount_at( premium_schedule.amount, 
                                                             premium_schedule.valid_from_date, 
                                                             premium_schedule.valid_from_date, 
                                                             'net_premium' )
        visitor = AccountAttributionVisitor()
        for d in visitor.get_payment_dates(premium_schedule, premium_schedule.valid_from_date, premium_schedule.valid_thru_date):
            premiums.append( premium_data(date = d, amount = net_premium_amount, gross_amount = premium_schedule.amount, 
                                          associated_surrenderings = None) )

        # calc provisions
        from_date = self._agreement.from_date
        dates = [ from_date, 
                  add_months_to_date(from_date, 5*12),
                  add_months_to_date(from_date, 5*12 + 2), 
                  add_months_to_date(from_date, 6*12),
                  thru_date ]
        result = list(prov_visitor.get_provision(premium_schedule, premium_schedule.valid_from_date, dates, None, premiums, round_output = False))
        for r in result:
            pvd = r[0]
            self.assertTrue( pvd.provision > 0 )
            self.assertTrue( pvd.risk <= 0 )


    def verify_recursive_provision_calculation(self):
        # make sure recursive provision calculation is equal to analytic calculation
        from vfinance.model.insurance.credit_insurance import CreditInsurancePremiumSchedule
        from vfinance.model.financial.interest import leap_days
        from datetime import timedelta

        def is_leap_day(date):
            return date.month == 2 and date.day == 29
        
        def create_credit_insurance_premium_schedule(premium):
            hundred  = D(100)
    
            # get amortization table coverage and extract coverage fraction
            coverage = None
            for cov in premium.agreed_coverages:
                if cov.coverage_for and cov.coverage_for.type and cov.coverage_for.type == 'amortization_table':
                    if coverage:
                        raise Exception('Only one amortization table coverage per premium is allowed.')
                    coverage = cov
            if not coverage.loan_defined:
                raise Exception('No loan associated with insurance coverage.')
            coverage_fraction = D(coverage.coverage_limit)/hundred
    
            # extract loan parameters
            loan = coverage.coverage_amortization
            amortization_table = loan.get_mortgage_table()
    
            initial_capital     = D(loan.get_loan_amount)
    
            start_date = loan.get_starting_date
                
            ipd = premium.get_insured_party_data( premium.valid_from_date )
            if not premium.payment_duration:
                raise Exception('Please specify a payment duration')
    
            # create credit insurance object
            ci = CreditInsurancePremiumSchedule( product = premium.product,
                                                 mortality_table = ipd.mortality_table_per_coverage[coverage], 
                                                 amortization_table = amortization_table, 
                                                 from_date = start_date, 
                                                 initial_capital = initial_capital, 
                                                 duration = premium.duration, 
                                                 payment_duration= premium.payment_duration,
                                                 coverage_duration = premium.duration,
                                                 agreed_features = premium.agreed_features,
                                                 roles = premium.financial_agreement.roles,
                                                 birth_dates = ipd.birth_dates,
                                                 direct_debit = premium.direct_debit,
                                                 coverage_fraction = coverage_fraction, 
                                                 period_type = premium.period_type )
            return ci

        def daterange_inclusive(start_date, end_date):
            for n in range(int ((end_date - start_date).days) + 1):
                yield start_date + timedelta(n)

        # calc provision at end of contract:
        premium_schedule = self._premium
        prov_visitor = ProvisionVisitor()
        from_date = self._agreement.from_date
        thru_date = premium_schedule.valid_thru_date
        if premium_schedule.has_credit_insurance():
            for cov in premium_schedule.agreed_coverages:
                if cov.has_credit_insurance:
                    thru_date = cov.thru_date

        # construct premium payment tuples list
        premiums = []
        payment_dates = []
        net_premium_amount = premium_schedule.get_amount_at( premium_schedule.amount, 
                                                             premium_schedule.valid_from_date, 
                                                             premium_schedule.valid_from_date, 
                                                             'net_premium' )
        visitor = AccountAttributionVisitor()
        for d in visitor.get_payment_dates(premium_schedule, premium_schedule.valid_from_date, premium_schedule.valid_thru_date):
            premiums.append( premium_data(date = d, amount = net_premium_amount, gross_amount = premium_schedule.amount, 
                                          associated_surrenderings = None) )
            payment_dates.append( d )
            
        # request response at first 40 and last 40 days
        all_dates = []
        for single_date in daterange_inclusive(from_date + timedelta(days =  0), from_date + timedelta(days =  40)):
            all_dates.append( single_date )
        for single_date in daterange_inclusive(thru_date - timedelta(days =  40), thru_date):
            all_dates.append( single_date )

        ci = create_credit_insurance_premium_schedule(premium_schedule)
        all_in_premium = ci.premium_all_in()

        # calculate provision at start of day 0 (small negative number due to rounding of the premium)   
        initial_provision = ci.V_k_daily_analytic(0, all_in_premium, payment_dates)
        self.assertTrue( initial_provision <= 0)
        self.assertAlmostEqual( abs(initial_provision), 0, delta = 2 * len(premiums) * 0.01 )
        
        # calc provision at all dates (recursively), starting with the above calculated initial provision
        # (without the initial provision the recursive solution will differ (slightly) from the analytic since it would start at zero)
        pvd = list(prov_visitor.get_provision(premium_schedule, premium_schedule.valid_from_date, all_dates, [ initial_provision ], premiums, round_output = False))

        for p in pvd:
            d = p[0].date
            if is_leap_day( d ):
                continue
            # calc day number
            i = (d - from_date).days - leap_days(from_date, d)
            # calc provision analytically (at day i+1 since it calculates the provision at the start of the day,
            # whereas the recursive solution gives us the provision at the end of the day)
            provision_analytic  = ci.V_k_daily_analytic(i+1, all_in_premium, payment_dates)
            provision_recursive = p[0].provision
            self.assertAlmostEqual( real( provision_recursive ), real( provision_analytic ), delta = 0.0001 )
            
    @reset_to_decimal_mode
    def test_verify_recursive_provision_calculation(self):
        # make sure recursive provision calculation is equal to analytic calculation for various cases

        def check_agreement(two_insured_parties = False, **kwargs):
            self.create_person()
            if two_insured_parties:
                self._person2 = self._person
                self.create_person(male = False)
            else:
                self._person2 = None
            self.create_agreement(**kwargs)
            self._premium.button_calc_credit_insurance_premium()
            self._agreement.invested_amounts[0].flush()
            self.verify_recursive_provision_calculation()

        self.create_product_definition(u'Credit Insurance - Family', D('0'))
        
        # very high loan amount, monthly
        check_agreement(period_type = 'monthly', loan_amount = Decimal('100000000'), interest_rate = Decimal('0.05'))
        # very high loan amount, surmortality
        check_agreement(period_type = 'monthly', loan_amount = Decimal('100000000'), interest_rate = Decimal('0.05'), surmortality = Decimal('50'))
        # very high loan amount, yearly
        check_agreement(period_type = 'yearly', loan_amount = Decimal('100000000'), interest_rate = Decimal('0.05'))
        # very high loan amount, monthly, two insured parties
        check_agreement(two_insured_parties = True, period_type = 'monthly', loan_amount = Decimal('100000000'), interest_rate = Decimal('0.05'))

            
    @reset_to_decimal_mode
    def test_credit_insurance_flow(self):
        self.create_product_definition(u'Credit Insurance - Family', D('0'))
        self.create_person()
        # create agreement
        self.t1 = date(2010, 11, 15)
        agreement = FinancialAgreement(package = self._package,
                                       code = self.next_agreement_code(),
                                       agreement_date = self.t0,
                                       from_date = self.t1
                                       )
        agreement.flush()
        agreement.broker_relation = agreement.get_available_broker_relations()[-1]
        agreement.change_status('draft')
        self.assertFalse( agreement.is_complete() )
        
        role = FinancialAgreementRole(natuurlijke_persoon=self._person, described_by = 'subscriber')
        agreement.roles.append(role)
        agreement.flush()
        self.assertFalse( agreement.is_complete() )

        premium = FinancialAgreementPremiumSchedule(product=self._product, period_type='yearly', amount=0)
        premium.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_rate_1', recipient='broker', distribution=to_decimal('15') ) )
        premium.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_fee_1', recipient='broker', distribution=to_decimal('4') ) )
        coverage = InsuranceAgreementCoverage(coverage_for=self._coverage_level, coverage_limit=100, duration = 12)
        amount     = to_decimal('150000')
        interest   = to_decimal('6')
        nmonths    = 240
        loan = InsuredLoanAgreement(loan_amount = amount, interest_rate = interest, number_of_months = nmonths)
        loan.insurance_agreement_coverage.append(coverage)
        premium.agreed_coverages.append(coverage)       
        agreement.invested_amounts.append(premium)
        loan.update_upstream()  # only necessary in tests, automatic with user interface
        premium.button_calc_optimal_payment_duration()

        with self.assertRaises( Exception ):
            agreement.is_complete()

        role = FinancialAgreementRole(natuurlijke_persoon=self._person, described_by = 'insured_party')
        agreement.roles.append(role)
        agreement.flush()
        with self.assertRaises( Exception ):
            agreement.is_complete()

        role = FinancialAgreementRole(natuurlijke_persoon=self._person, described_by = 'beneficiary')
        agreement.roles.append(role)
        agreement.flush()
        with self.assertRaises( Exception ):
            agreement.is_complete()

        premium.button_calc_credit_insurance_premium()
        agreement.invested_amounts[0].flush()
        self.assertTrue( agreement.is_complete() )
        
        # add second loan
        premium = FinancialAgreementPremiumSchedule(product=self._product, 
                                                    amount=0,
                                                    period_type='yearly')
        premium.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_rate_1', recipient='broker', distribution=to_decimal('15') ) )
        premium.commission_distribution.append( FinancialAgreementCommissionDistribution( described_by='premium_fee_1', recipient='broker', distribution=to_decimal('4') ) )
        coverage = InsuranceAgreementCoverage(coverage_for=self._coverage_level, coverage_limit=100, duration = 12)
        amount     = to_decimal('150000')
        interest   = to_decimal('6')
        nmonths    = 240
        loan = InsuredLoanAgreement(loan_amount = amount, interest_rate = interest, number_of_months = nmonths,
                                     type_of_payments = 'fixed_capital_payment')
        loan.insurance_agreement_coverage.append(coverage)
        premium.agreed_coverages.append(coverage)
        agreement.invested_amounts.append(premium)
        loan.update_upstream()  # only necessary in tests, automatic with user interface
        premium.button_calc_optimal_payment_duration()

        premium.button_calc_credit_insurance_premium()
        premium.flush()
        self.assertAlmostEqual(real(agreement.invested_amount), real('1792.82'), 2)
        
        self.button_complete(agreement)
        self.button_incomplete(agreement)
        self.button_complete(agreement)
        self.button_draft(agreement)
        
        # introduce error in premium value
        agreement.invested_amounts[1].amount += to_decimal('200')
        agreement.invested_amounts[1].flush()
        with self.assertRaises( Exception ):
            agreement.is_complete()
        agreement.invested_amounts[1].button_calc_credit_insurance_premium()
        agreement.invested_amounts[1].flush()
        agreement.flush()
        self.button_complete(agreement)
        
        # apparently, we have to re-load the agreement, otherwise  invested_amount remains wrong
        id = agreement.id
        FinancialAgreement.query.session.expunge_all()
        agreement = FinancialAgreement.query.filter_by(id=id).one()
        
        self.assertAlmostEqual(real(agreement.invested_amount), real('1792.82'), 2)

        self.button_complete(agreement)
        self.button_verified(agreement)
        self.fulfill_agreement( agreement )
        self.button_agreement_forward( agreement )
        
        agreement.flush()
        
        # Necessary because of dates
        agreement.account.change_status('draft')
        #
        # create account premium schedules
        #
        premium_schedules = []
        for invested_amount in agreement.invested_amounts:
            premium_schedules.extend( list(invested_amount.fulfilled_by) )
        self.assertEqual( len(premium_schedules), 2 )
        self.assertTrue( invested_amount.fulfilled )
        #
        # Create reports
        #
        from vfinance.model.financial.report_action import FinancialReportAction
        from vfinance.model.financial.report.coverages import InsuredCoveragesReport
        report = FinancialReportAction()
        options = FinancialReportAction.Options()

        options.report = InsuredCoveragesReport
        list( report.write_files( options ) )
    
    @reset_to_decimal_mode
    def test_documents(self):
        from vfinance.model.financial.notification.premium_schedule_document import PremiumScheduleDocument
        self.create_product_definition(u'Credit Insurance - Family', D('0'))
        self.create_person()
        self.create_agreement()
        agreed_mortgage_table = self._loan.get_mortgage_table()
        # print agreed_mortgage_table
        self.assertTrue( len(agreed_mortgage_table) )
        self.create_account()
        list(self.synchronizer.attribute_pending_premiums())
        # account available as self._account, e.g.:
        #insured_loan = self._premium_schedules[0].applied_coverages[0].coverage_amortization
        # account_mortgage_table = insured_loan.get_mortgage_table()
        # print account_mortgage_table
        # print self._account.account_number

        self.fulfill_agreement( self._premium_schedules[0].agreed_schedule.financial_agreement )
        visitor = JoinedVisitor()
        list(visitor.visit_premium_schedule( self._premium_schedules[0], self.t1 ))
        self._premium_schedules[0].expire()
        #
        # test context of a PremiumScheduleDocument
        #
        action = PremiumScheduleDocument()
        options = PremiumScheduleDocument.Options()
        options.notification_type = 'certificate'
        options.from_document_date = self.tp
        context = action.get_context( premium_schedule = self._premium_schedules[0],
                                      recipient = None,
                                      options = options )
        premiums_data = context['premiums_data'][0]
        self.assertTrue( premiums_data.coverages )
        coverage_data = premiums_data.coverages[0]
        self.assertTrue( coverage_data.insured_capitals )
        insured_capitals_data = coverage_data.insured_capitals
        self.assertEqual( insured_capitals_data[-1].insured_capital, 0 )
        self.assertEqual( insured_capitals_data[0].insured_capital, self._loan.get_loan_amount )
        self.assertTrue( coverage_data.loan )
        loan_data = coverage_data.loan
        self.assertEqual( loan_data.loan_amount, 150000 )
        # 
        # test content of generated document
        #
        strings_present = ['974,31 EUR',
                           '10,72 EUR',
                           '985,03 EUR',
                           '0,4868% maandelijks (6,00% per jaar)']

        notification = self.verify_last_notification_from_account (
            self._account,
            expected_type = 'certificate',
            strings_present=strings_present
        )
        self.assertEqual( notification.application_of, self.nl_ssv_certificate)
        self.assertEqual( notification.date, self.t1 )
        # test calculate_months(d1, d2)
        d1 = coverage_data.from_date
        d2 = coverage_data.thru_date
        calculated_duration = utils.calculate_duration(d1, d2)
        self.assertEqual(calculated_duration, 240)
        self.assertEqual(d1 + dateutil.relativedelta.relativedelta(months=+240), d2)

    def test_performance( self ):
        
        def run():
            self.test_create_entries_single_premium()
            
        import cProfile
        command = 'run()'
        cProfile.runctx( command, globals(), locals(), filename='credit_insurance.profile' )

    def test_create_entries_single_premium(self, enddate = date(2020, 12, 1), **agreement_kwargs):
        self.create_product_definition(u'Credit Insurance - Family', D('0'))
        self.create_person()
        # create agreement
        self.t1 = date(2010, 11, 15)
        agreement = self.create_agreement(period_type='single',
                                          number_of_months=120,
                                          **agreement_kwargs)

        agreed_schedule = agreement.invested_amounts[0]
        agreed_schedule.button_calc_credit_insurance_premium()
        self.session.flush()
        self.assertTrue( agreement.is_complete() )

        self.button_complete(agreement)
        self.button_verified(agreement)
        self.fulfill_agreement( agreement )
        self.button_agreement_forward( agreement )
        self.session.flush()

        # Necessary because of dates
        agreement.account.change_status('draft')
        self.assertTrue( agreed_schedule.fulfilled )

        premium_schedule = agreement.account.premium_schedules[0]
        list(self.synchronizer.attribute_pending_premiums())
        visitor = JoinedVisitor()
        list(visitor.visit_premium_schedule( premium_schedule, enddate))

        # calc provision value
        from vfinance.model.financial.visitor import RiskDeductionVisitor
        v = RiskDeductionVisitor()
        accounts = v.get_accounts(premium_schedule)
        d = date(2010, 12, 1)
        while d <= enddate:
            total_provision = sum( v.get_total_amount_until(premium_schedule, 
                                                            d,
                                                            account = account)[0] for account in accounts ) * -1
            if d.month < 12:
                d = date(d.year, d.month + 1, d.day)
            else:
                d = date(d.year + 1, 1, d.day)
                
            self.assertTrue( total_provision > -0.001 )
                
        return premium_schedule

    def test_create_entries_single_premium_insurance_reduction(self, **agreement_kwargs):
        return self.test_create_entries_single_premium(insurance_reduction_rate=D(50))
        
    def test_create_entries_yearly_premium(self, **agreement_kwargs):
        self.create_product_definition(u'Credit Insurance - Family', D('0'))
        self.create_person()
        self.create_agreement(number_of_months = 120, **agreement_kwargs)
        self._premium.button_calc_credit_insurance_premium()
        self._agreement.invested_amounts[0].flush()

        agreement = self._agreement
        self.button_complete(agreement)
        self.button_verified(agreement)
        self.fulfill_agreement( agreement )
        self.button_agreement_forward( agreement )
        agreement.flush()
    
        # Necessary because of dates
        agreement.account.change_status('draft')
        # copied from branch 21 (without exact knowledge of what it does)
        premium_schedules = []
        for invested_amount in agreement.invested_amounts:
            premium_schedules.extend( list(invested_amount.fulfilled_by) )
        self.assertTrue( invested_amount.fulfilled )

        yearly_premium_schedule = [premium for premium in agreement.account.premium_schedules if premium.period_type=='yearly'][0]
        list(self.synchronizer.attribute_pending_premiums())

        # add other payments
        from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment
        for i in range(1, yearly_premium_schedule.payment_thru_date.year - yearly_premium_schedule.valid_from_date.year): 
            #
            # Add a premium to the account, and attach it by force
            # to the premium schedule
            #
            d = date(self.t1.year + i, self.t1.month, self.t1.day)
            second_entry = self.fulfill_agreement( yearly_premium_schedule.financial_account, 
                                                   fulfillment_date = d, 
                                                   amount = yearly_premium_schedule.premium_amount,
                                                   remark = agreement.code )
            FinancialAccountPremiumFulfillment( of = yearly_premium_schedule,
                                                entry_book_date = second_entry.book_date,
                                                entry_document = second_entry.document,
                                                entry_book = second_entry.book,
                                                entry_line_number = second_entry.line_number,
                                                fulfillment_type = 'premium_attribution',
                                                amount_distribution = -1 * yearly_premium_schedule.premium_amount) 
        FinancialAccountPremiumFulfillment.query.session.flush()
        
        enddate = date(2020, 12, 1)
        visitor = JoinedVisitor()
        list(visitor.visit_premium_schedule( yearly_premium_schedule, enddate ))

        # calc provision value
        from vfinance.model.financial.visitor import RiskDeductionVisitor
        v = RiskDeductionVisitor()
        accounts = v.get_accounts(yearly_premium_schedule)
        d = date(2010, 12, 1)
        while d <= enddate:
            total_provision = sum( v.get_total_amount_until(yearly_premium_schedule, 
                                                            d,
                                                            account = account)[0] for account in accounts ) * -1
            self.assertTrue( total_provision > -1 )
            if d.month < 12:
                d = date(d.year, d.month + 1, d.day)
            else:
                d = date(d.year + 1, 1, d.day)
                
        self.assertAlmostEqual( total_provision, 0, 0 )

    def test_create_entries_yearly_premium_insurance_reduction(self, **agreement_kwargs):
        return self.test_create_entries_yearly_premium(insurance_reduction_rate=D(50))
