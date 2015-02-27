import datetime
from decimal import Decimal as D

from vfinance.model.financial import product, security
from vfinance.model.insurance.mortality_table import (
    MortalityRateTable, MortalityRateTableEntry)
from vfinance.model.insurance.product import (InsuranceCoverageAvailability,
                                              InsuranceCoverageAvailabilityMortalityRateTable,
                                              InsuranceCoverageLevel)
from vfinance.model.bank.product import (ProductAccount, ProductFeatureApplicability,
                                         ProductIndexApplicability)
from vfinance.model.bank.index import IndexType

from ...test_case import SessionCase
from ... import app_admin
from . import FinancialMixinCase

class AbstractFinancialProductCase(SessionCase, FinancialMixinCase):
    """
    This test case provides a minimum financial product when the CLASS
    is set up.

    setUp and tearDown will begin and rollback a transaction, so the
    the individual tests dont modify the product configuration.
    """

    tp = datetime.date(2009, 12, 31)

    @classmethod
    def setUpClass(cls):
        SessionCase.setUpClass()
        cls.fund = security.FinancialFund(name='Carmignac Patrimoine %s' % datetime.datetime.now(),
                                          isin='CARMI',
                                          order_lines_from=datetime.date(2000, 1, 1),
                                          purchase_delay=1,
                                          transfer_revenue_account='771',
                                          sales_delay=1,
                                          account_number = security.FinancialFund.new_account_number(),
                                          )
        cls.base_product = product.FinancialProduct(name='Branch 21',
                                                    account_number_prefix=124,
                                                    account_number_digits=6)
        cls.product = product.FinancialProduct(name='Branch 21 Account',
                                               specialization_of=cls.base_product,
                                               from_date=cls.tp,
                                               account_number_prefix=124,
                                               account_number_digits=6,
                                               fund_number_digits=2,
                                               premium_sales_book='VPrem',
                                               premium_attribution_book=u'DOMTV',
                                               depot_movement_book=u'RESBE',
                                               interest_book=u'INT',
                                               funded_premium_book='FPREM',
                                               redemption_book='REDEM',
                                               profit_attribution_book='PROFIT',
                                               supplier_distribution_book = u'COM',
                                               numbering_scheme='global',
                                               unit_linked=True,
                                               )
        cls.create_accounts_for_product(cls.product)
        product_feature_applicability = ProductFeatureApplicability()
        cls.insurance_coverage_availability = InsuranceCoverageAvailability(
            from_date = cls.tp
        )
        mortality_rate_table = MortalityRateTable(name=u"MK")
        for i in range(1,100):
            MortalityRateTableEntry(year=i, l_x=D(100)/i, used_in=mortality_rate_table)
        InsuranceCoverageAvailabilityMortalityRateTable(
            used_in = cls.insurance_coverage_availability,
            mortality_rate_table = mortality_rate_table,
            type = 'male',
        )
        InsuranceCoverageAvailabilityMortalityRateTable(
            used_in = cls.insurance_coverage_availability,
            mortality_rate_table = mortality_rate_table,
            type = 'female',
        )
        cls.index_type = IndexType(name='Market Condition')
        cls.financial_product_index_applicability = ProductIndexApplicability(
            described_by = 'market_fluctuation_exit_rate',
            available_for=cls.product,
            index_type=cls.index_type,
            apply_from_date=datetime.date(2010,  1,  1)
        )
        cls.coverage_level = InsuranceCoverageLevel(
            type = 'fixed_amount',
            used_in = cls.insurance_coverage_availability,
            coverage_limit_thru = D(200000)
        )
        cls.coverage_level = InsuranceCoverageLevel(
            type = 'decreasing_amount',
            used_in = cls.insurance_coverage_availability,
            coverage_limit_thru = D(200000)
        )
        cls.product.available_with = [product_feature_applicability]
        cls.product.available_coverages = [cls.insurance_coverage_availability]
        cls.product.available_funds = [product.ProductFundAvailability(available_for=cls.product,
                                                                        fund=cls.fund,
                                                                        default_target_percentage=100)]
        cls.product.available_indexes = [cls.financial_product_index_applicability]
        cls.session.flush()

    def setUp(self):
        super(AbstractFinancialProductCase, self).setUp()
        self.session.begin()
        self.session.add(self.base_product)
        self.session.add(self.product)

    def tearDown(self):
        self.session.rollback()
        super(AbstractFinancialProductCase, self).tearDown()

class FinancialProductCase(AbstractFinancialProductCase):

    def editability_on_status(self, tested_attr_class, tested_attr_name):
        adm = app_admin.get_related_admin(tested_attr_class)
        self.product.change_status('incomplete')
        try:
            attribute = getattr(self.product, tested_attr_name)
        except AttributeError:
            self.fail("No such attribute: " + tested_attr_name)
        self.assertNotEqual([], attribute)
        for entr in attribute:
            attribs = adm.get_dynamic_field_attributes(entr,
                                                       adm.list_display)
            self.assertNotEqual([], attribs)
            for attr in attribs:
                if(attr['editable']):
                    break
            else:
                self.fail("No editable fields despite status 'incomplete'")
        self.product.change_status('complete')
        for entr in attribute:
            attribs = adm.get_dynamic_field_attributes(entr,
                                                       adm.list_display)
            for attr in attribs:
                self.assertFalse(attr['editable'])

    def test_available_with_editability_on_status(self):
        self.editability_on_status(ProductFeatureApplicability,
                                   'available_with')

    def test_available_coverages_editability_on_status(self):
        self.editability_on_status(InsuranceCoverageAvailability,
                                   'available_coverages')

    def test_available_funds_editability_on_status(self):
        self.editability_on_status(product.ProductFundAvailability,
                                   'available_funds')

    def test_available_accounts_editability_on_status(self):
        self.editability_on_status(ProductAccount,
                                   'available_accounts')

    def test_available_indexes_editability_on_status(self):
        self.editability_on_status(ProductIndexApplicability,
                                   'available_indexes')
