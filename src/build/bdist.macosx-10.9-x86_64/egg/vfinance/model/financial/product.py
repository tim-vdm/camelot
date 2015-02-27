import copy
import datetime

import sqlalchemy.types
from sqlalchemy import schema, orm

from camelot.core.orm import (Entity, ManyToOne,
                              using_options)
from camelot.model.authentication import end_of_times
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _
import camelot.types

from security import FinancialFund
from ..bank.statusmixin import ( status_form_actions,
                                 BankRelatedStatusAdmin )
from ..bank.product import Product
from ..bank.constants import hypo_feature_offset

from decimal import Decimal as D

import logging
LOGGER = logging.getLogger('vfinance.model.financial.product')


class FinancialProduct(Product):

    from_feature = 1
    thru_feature = hypo_feature_offset

    fund_number_digits = schema.Column(sqlalchemy.types.Integer(), default=0)
    #financed_commissions_prefix = schema.Column(camelot.types.Code(account_code))
    financed_commissions_prefix = schema.Column(sqlalchemy.types.Unicode(15))
    risk_sales_book = schema.Column(sqlalchemy.types.Unicode(25))
    redemption_book = schema.Column(sqlalchemy.types.Unicode(25))
    switch_book = schema.Column(sqlalchemy.types.Unicode(25))
    funded_premium_book = schema.Column(sqlalchemy.types.Unicode(25))
    premium_sales_book = schema.Column(sqlalchemy.types.Unicode(25))
    financed_commissions_sales_book = schema.Column(sqlalchemy.types.Unicode(25))
    premium_attribution_book = schema.Column(sqlalchemy.types.Unicode(25))
    profit_attribution_book = schema.Column(sqlalchemy.types.Unicode(25))
    depot_movement_book = schema.Column(sqlalchemy.types.Unicode(25))
    quotation_book = schema.Column(sqlalchemy.types.Unicode(25))
    interest_book = schema.Column(sqlalchemy.types.Unicode(25))
    days_a_year = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=365)
    # number of days in a year for calculation of age, no longer used
    age_days_a_year = schema.Column(sqlalchemy.types.Numeric(precision=8, scale=4), nullable=False, default=D('365.25'))
    unit_linked = schema.Column(sqlalchemy.types.Boolean(), default=False, nullable=False)
    numbering_scheme = schema.Column(camelot.types.Enumeration([(1, 'product'), (2, 'global'), (3, 'as_requested')]), default='product', nullable=False)
    profit_shared = schema.Column(sqlalchemy.types.Boolean(), default=False, nullable=False)

    @classmethod
    def __declare_last__(cls):
        cls.declare_last()

    __mapper_args__ = {
        'polymorphic_identity': u'insurance',
    }

    def get_available_coverages_at(self, application_date):
        for available_coverage in self.available_coverages:
            if available_coverage.from_date <= application_date and available_coverage.thru_date >= application_date:
                yield available_coverage

    def get_available_coverage_levels_at(self, application_date):
        for available_coverage in self.get_available_coverages_at(application_date):
            for coverage_level in available_coverage.with_coverage_levels:
                yield coverage_level

    class Admin(Product.Admin):
        verbose_name = _('Insurance Product definition')
        verbose_name_plural = _('Insurance Product definitions')
        list_display = Product.Admin.list_display + ['unit_linked']
        list_filter = Product.Admin.list_filter + ['unit_linked']
        form_actions = status_form_actions
        form_display = copy.deepcopy(Product.Admin.form_display)
        form_display.add_tab(_('Insurances'), ['available_coverages'])
        form_display.add_tab(_('Funds'), ['available_funds'])
        form_display.add_tab(_('Financial'), [
            'days_a_year', #'age_days_a_year',
            'unit_linked',])
        form_display.add_tab(_('Accounting Rules'), forms.Form([
            'account_number_prefix', 'account_number_digits',
            'premium_sales_book', 'financed_commissions_sales_book', 'depot_movement_book', 'premium_attribution_book',
            'financed_commissions_prefix', 'funded_premium_book',
            'risk_sales_book', 'quotation_book',
            'redemption_book', 'switch_book', 'interest_book',
            'profit_attribution_book', 'accounting_year_transfer_book',
            'external_application_book', 'supplier_distribution_book', forms.Break(),
            'numbering_scheme', 'fund_number_digits', 'available_accounts',
            ], columns=2))


class ProductFundAvailability(Entity):
    using_options(tablename='financial_product_fund_availability')
    available_for = ManyToOne(Product,
                              nullable=False,
                              ondelete='cascade', onupdate='cascade',
                              backref=orm.backref('available_funds', cascade='all, delete, delete-orphan')
                              )
    fund = ManyToOne('vfinance.model.financial.security.FinancialSecurity', required = True, ondelete = 'restrict', onupdate = 'cascade')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    default_target_percentage = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)

    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Fund Availability')
        verbose_name_plural = _('Fund Availabilities')
        list_display = ['fund', 'from_date', 'thru_date', 'default_target_percentage']
        field_attributes = {'fund':{'minimal_column_width':35,
                                    'target':FinancialFund}}

        def get_related_status_object(self, o):
            return o.available_for
