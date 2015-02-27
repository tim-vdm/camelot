import datetime
from decimal import Decimal as D

from sqlalchemy import orm

from camelot.core.exception import UserException

from ..test_model.test_financial.test_premium import AbstractFinancialAgreementPremiumScheduleCase

from vfinance.model.bank.varia import Country_
from vfinance.facade.financial_agreement import FinancialAgreementFacade


class TestCreditInsuranceFacade(AbstractFinancialAgreementPremiumScheduleCase):

    @classmethod
    def setUpClass(cls):
        AbstractFinancialAgreementPremiumScheduleCase.setUpClass()
        cls.product.unit_linked = False
        cls.session.flush()

    def test_field_attributes(self):
        #
        # check if the field attributes are correct
        #
        facade_admin = self.app_admin.get_related_admin(FinancialAgreementFacade)
        birthdate_attrs = facade_admin.get_field_attributes('insured_party__1__birthdate')
        self.assertEqual(birthdate_attrs['python_type'], datetime.date)
        sex_attrs = facade_admin.get_field_attributes('insured_party__1__sex')
        self.assertEqual(sex_attrs['python_type'], str)
        self.assertEqual(sex_attrs['length'], 50)
        from_date_attrs = facade_admin.get_field_attributes('from_date')
        self.assertEqual(from_date_attrs['python_type'], datetime.date)
        agreement_date_attrs = facade_admin.get_field_attributes('agreement_date')
        self.assertEqual(agreement_date_attrs['python_type'], datetime.date)
        duration_attrs = facade_admin.get_field_attributes('premium_schedules_duration')
        self.assertEqual(duration_attrs['python_type'], int)

        package_id_attrs = facade_admin.get_field_attributes('package_id')
        self.assertEqual(package_id_attrs['python_type'], int)
        product_id_attrs = facade_admin.get_field_attributes('premium_schedule__1__product_id')
        self.assertEqual(product_id_attrs['python_type'], int)

        feature_value_attrs = facade_admin.get_field_attributes('premium_schedules_premium_rate_1')
        self.assertEqual(feature_value_attrs['python_type'], float)
        self.assertEqual(feature_value_attrs['decimal'], True)

        feature_value_attrs = facade_admin.get_field_attributes('premium_schedule__1__premium_fee_1')
        self.assertEqual(feature_value_attrs['python_type'], float)
        self.assertEqual(feature_value_attrs['decimal'], True)

        limit_attrs = facade_admin.get_field_attributes('premium_schedules_coverage_limit')
        self.assertEqual(limit_attrs['python_type'], float)
        self.assertEqual(limit_attrs['decimal'], True)

        type_attrs = facade_admin.get_field_attributes('premium_schedule__1__coverage_level_type')
        self.assertEqual(type_attrs['python_type'], str)
        self.assertTrue(len(type_attrs['choices']) > 0)

        type_attrs = facade_admin.get_field_attributes('premium_schedule__2__coverage_level_type')
        self.assertEqual(type_attrs['python_type'], str)
        self.assertTrue(len(type_attrs['choices']) > 0)

    def test_single_product_premium_calculation(self):
        #
        # check if a calculation can be made
        #
        facade = FinancialAgreementFacade()
        self.assertTrue('package' in facade.note)
        
        facade.agreement_date = self.t0
        facade.from_date = self.t1
        facade.package = self.package

        facade.insured_party__1__birthdate = datetime.date(1980, 1, 1)
        facade.insured_party__1__sex = 'M'

        facade.premium_schedule__1__product = self.package.available_products[0].product
        facade.premium_schedule__1__premium_fee_1 = D(100)

        facade.duration = 5*12

        facade.premium_schedules_coverage_limit = D('150000')
        facade.premium_schedules_payment_duration = 5*12
        facade.premium_schedules_coverage_level_type = 'decreasing_amount'
        facade.premium_schedules_premium_rate_1 = D(20)
        facade.premium_schedules_period_type = 'single'

        facade.update_premium()
        self.assertTrue(facade.premium_schedule__1__amount)
        self.assertFalse(facade.premium_schedule__2__amount)
        return facade

    def test_complete_agreement(self):
        facade = self.test_single_product_premium_calculation()
        facade.insured_party__1__nationality = self.session.query(Country_).filter(Country_.code=='BE').first()
        facade.insured_party__1__social_security_number = '81070339504'
        facade.insured_party__1__first_name = u'Test'
        facade.insured_party__1__last_name = u'Vantestergem'
        facade.pledgee_name = 'Krefima'
        facade.pledgee_tax_id = 'BE 0456.249.396'
        facade.code = '000/0000/00000'
        facade.use_default_features()
        orm.object_session(facade).flush()
        #self.assertFalse(facade.note)

    def test_double_product_premium_calculation(self):
        #
        # check if a calculation can be made
        #
        facade = FinancialAgreementFacade()
        self.assertTrue('package' in facade.note)
        
        facade.agreement_date = self.t0
        facade.from_date = self.t1
        facade.package = self.package

        facade.insured_party__1__birthdate = datetime.date(1980, 1, 1)
        facade.insured_party__1__sex = 'M'

        facade.premium_schedule__1__product = self.package.available_products[0].product
        facade.premium_schedule__1__premium_fee_1 = D(100)

        facade.premium_schedule__2__product = self.package.available_products[0].product

        self.assertEqual(len(facade.invested_amounts), 2)

        facade.duration = 5*12

        facade.premium_schedule__1__coverage_level_type = 'fixed_amount'
        facade.premium_schedule__2__coverage_level_type = 'decreasing_amount'
        
        facade.premium_schedules_coverage_limit = D('150000')
        facade.premium_schedules_payment_duration = 5*12
        
        facade.premium_schedules_premium_rate_1 = D(20)
        facade.premium_schedules_period_type = 'single'

        facade.update_premium()

        self.assertEqual(facade.premium_schedule__1__coverage_level_type, 'fixed_amount')
        self.assertEqual(facade.premium_schedule__2__coverage_level_type, 'decreasing_amount')

        self.assertTrue(facade.premium_schedule__1__amount)
        self.assertTrue(facade.premium_schedule__2__amount)
        self.assertTrue(facade.premium_schedule__1__amount > facade.premium_schedule__2__amount)

    def test_properties(self):
        #
        # check the of the properties
        #
        today = datetime.date.today()
        facade = FinancialAgreementFacade()
        facade.package = self.package
        self.assertEqual(facade.from_date, today)
        self.assertEqual(facade.agreement_date, today)
        # party
        facade.insured_party__1__birthdate = datetime.date(1982, 1, 1)
        insured_parties = list(facade.get_roles_at(facade.agreement_date, 'insured_party'))
        subscribers = list(facade.get_roles_at(facade.agreement_date, 'insured_party'))
        self.assertEqual(len(insured_parties), 1)
        self.assertEqual(len(subscribers), 1)
        self.assertEqual(insured_parties[0].natuurlijke_persoon.geboortedatum, datetime.date(1982, 1, 1))
        self.assertEqual(subscribers[0].natuurlijke_persoon.geboortedatum, datetime.date(1982, 1, 1))
        facade.insured_party__1__sex = 'M'
        self.assertEqual(insured_parties[0].natuurlijke_persoon.gender, 'm')
        self.assertEqual(subscribers[0].natuurlijke_persoon.gender, 'm')
        facade.insured_party__1__sex = 'F'
        self.assertEqual(insured_parties[0].natuurlijke_persoon.gender, 'v')
        self.assertEqual(subscribers[0].natuurlijke_persoon.gender, 'v')
        # coverage
        facade.premium_schedules_coverage_limit = D(122000)
        with self.assertRaises(UserException):
            facade.premium_schedule__1__coverage_level_type = 'bogus_type'
        facade.premium_schedule__1__coverage_level_type = 'decreasing_amount'
        self.assertEqual(len(facade.invested_amounts), 1)
        for agreed_schedule in facade.invested_amounts:
            coverages = agreed_schedule.agreed_coverages
            self.assertEqual(len(coverages), 1)
            self.assertEqual(coverages[0].coverage_limit, D(122000))
            self.assertEqual(coverages[0].coverage_for.type, 'decreasing_amount')
        self.assertEqual(facade.premium_schedules_coverage_limit, D(122000))
        self.assertEqual(facade.premium_schedule__1__coverage_level_type, 'decreasing_amount')
        # premium
        facade.premium_schedules_duration = 12*12
        facade.premium_schedules_payment_duration = 1
        facade.premium_schedules_period_type = 'single'
        facade.premium_schedules_premium_rate_1 = D(3)
        facade.premium_schedule__1__premium_fee_1 = D(100)
        for i, agreed_schedule in enumerate(facade.invested_amounts):
            self.assertEqual(agreed_schedule.duration, 12*12)
            self.assertEqual(agreed_schedule.payment_duration, 1)
            self.assertEqual(agreed_schedule.period_type, 'single')
            self.assertEqual(agreed_schedule.get_applied_feature_at(
                facade.from_date,
                facade.from_date,
                0,
                'premium_rate_1',
                default = D(10) ).value, D(3) )
            premium_fee_feature = agreed_schedule.get_applied_feature_at(
                facade.from_date,
                facade.from_date,
                0,
                'premium_fee_1',
                default = D(10) )
            if i == 0:
                self.assertEqual(premium_fee_feature.value, D(100))
        # facade
        facade.duration = 14*12
        facade.from_date = self.t1
        for agreed_schedule in facade.invested_amounts:
            self.assertEqual(agreed_schedule.duration, 14*12)
            self.assertEqual(agreed_schedule.valid_from_date, self.t1)
            for coverage in agreed_schedule.agreed_coverages:
                self.assertEqual(coverage.duration, 14*12)
                self.assertEqual(coverage.coverage_from_date, self.t1)
