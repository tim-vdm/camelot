import calendar
import collections
import datetime
import logging
from decimal import Decimal as D
from operator import attrgetter

import dateutil

#from vfinance.model.insurance.real_number import quantize

import sqlalchemy.types
from sqlalchemy import sql, schema, orm, event
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import aliased
from sqlalchemy.ext.hybrid import hybrid_property

from camelot.admin.not_editable_admin import not_editable_admin
from camelot.model.authentication import end_of_times
from camelot.core.conf import settings
from camelot.core.exception import UserException
from camelot.core.orm import ( Entity, ManyToOne, using_options,
                               OneToMany, ColumnProperty, transaction)
from camelot.core.sql import metadata
from camelot.core.utils import ugettext, ugettext_lazy as _
import camelot.types

from constants import period_types, period_types_by_granularity, commission_types

from integration.tinyerp.convenience import add_months_to_date, months_between_dates

from ..bank.history import HistoryMixin
from ..bank.invoice import InvoiceItem

from .product import FinancialProduct, Product

from vfinance.model.bank.fulfillment import AbstractFulfillment, add_entry_fields
from vfinance.model.bank.schedule import ScheduleMixin
from vfinance.model.bank.feature import FeatureMock
from vfinance.model.financial.agreement import FinancialAgreement
from vfinance.model.financial.account import FinancialAccount
from vfinance.model.financial.formulas import get_amount_at, get_rate_at

LOGGER = logging.getLogger('vfinance.model.financial.premium')

insured_party_data = collections.namedtuple('insured_party_data',
                                            'genders, birth_dates, smokers, surmortalities, ' + \
                                            'mortality_table_per_coverage, amortization, individual_mortality_tables_per_coverage')

class PremiumScheduleMixin(ScheduleMixin):
    """Common properties for a FinancialAgreement and a FinancialAccount
    Premium Schedule"""

    class Amortization(object):
        """Subclass to be used in methods of PremiumScheduleMixin"""
    
        def __init__(self, coverage_limit, loan_intrest_rate, loan_starting_date, loan_type_of_payments, loan_amount, loan_number_of_months, loan_payment_interval):
            from vfinance.model.hypo.mortgage_table import mortgage_table
            
            one_over_twelve    = D(1) / D(12)
            monthly_interest   = (1 + ( loan_intrest_rate )/100)**(one_over_twelve) - 1
            # start date of loan if given, otherwise the start date of the premium schedule
            self.start_date = loan_starting_date
            self.coverage_fraction = coverage_limit/100
            self.initial_capital = loan_amount
            self.table = list(mortgage_table(monthly_interest*100,
                                             loan_type_of_payments,
                                             loan_amount,
                                             loan_number_of_months,  # will have to change
                                             loan_payment_interval,
                                             loan_starting_date))
            self.number_of_payments = len( self.table )
    
        def insured_capital_remaining_at_date(self, date):
            """Calculate capital remaining at a certain date.
            """
            # warning: the mortgage_table function assumes the mortgage is payed at the last day of every month.
            # We will only assume it to have been payed as of the next day, i.e. the first day of the next month.
            # This explains the '>' instead of '>=' for the date comparison.in the while loop.
            if date <= self.table[0].date:
                return float( self.initial_capital*self.coverage_fraction )
            i = 0
            while i < self.number_of_payments and date > self.table[i].date:
                i += 1
            return float( self.table[i-1].capital_due )*float(self.coverage_fraction)
        
    def get_funds_at(self, valid_date):
        """Get a list of active fund distributions at a certain date.
        Always ordered by the id the fund distribution. not on the id of the fund
        since the same fund might appear multiple times within a different
        distribution
        """
        funds = [f for f in self.fund_distribution if f.from_date<=valid_date and f.thru_date>=valid_date]
        funds.sort( key = lambda f:f.id )
        return funds
    
    @staticmethod
    def add_days_to_date(thedate, ndays):
        """
        Adds 'ndays' to 'thedate', and adds all leap days necessary. Hence adding 10*365 days to any date will always
        advance exactly 10 years.
        If ndays is negative, the result will be abs(ndays) earlier than 'thedate', where leap days
        are not counted as a day. Hence adding -10*365 days to any date will always go back exactly 10 years.
        """
        from vfinance.model.financial.interest import leap_days
        from datetime import timedelta

        if thedate == None:
            return None

        def add(thedate, ndays):
            # add ndays
            first_result = thedate + timedelta(days = ndays)
            # add leapdays between the two dates
            leapdays = leap_days(thedate, first_result)
            result = first_result + timedelta(days = leapdays)
            # every add may have caused us to encounter more leapdays...
            while leapdays < leap_days(thedate, result):
                leapdays = leap_days(thedate, result)
                result = first_result + timedelta(days = leapdays)
            return result

        def subtract(thedate, ndays):
            # ndays = negative number!
            # start with max amount of leapdays (as negative number)
            leapdays = -((-ndays / 365) + 1)
            result = thedate + timedelta(days = ndays + leapdays)
            # loop to check amount of leapdays
            while add(result, -ndays) < thedate:
                leapdays += 1
                result = thedate + timedelta(days = ndays + leapdays)
            return result

        if ndays == 0:
            return thedate
        if ndays > 0:
            return add(thedate, ndays)
        if ndays < 0:
            return subtract(thedate, ndays)

    def get_account_type_at( self, booking_number, book_date ):
        """
        :param booking_number: a string with the account number
        :param book_date: the date at which there was a booking on this account
        :return: the account type for the given number at the given date
        """
        if booking_number.startswith( settings.HYPO_ACCOUNT_KLANT[:-7] ):
            return 'customer'
        if booking_number == self.full_account_number:
            return 'uninvested'
        if booking_number == self.financed_commissions_account_number:
            return 'financed_commissions'
        for fund_distribution in self.fund_distribution:
            if fund_distribution.full_account_number == booking_number:
                return 'fund'
            elif fund_distribution.fund.full_account_number == booking_number:
                return 'security'
            elif ''.join(fund_distribution.fund.transfer_revenue_account or '') == booking_number:
                return 'transfer_revenue'
        return self.product.get_account_type_at( booking_number, book_date )

    def get_premiums_due_at(self, due_date):
        if None in (self.valid_from_date, self.period_type, self.valid_thru_date):
            return 0
        if self.valid_from_date > due_date:
            return 0
        if self.period_type == 'single':
            number_of_premiums_due = 1
        else:
            payment_thru_date =  min( self.valid_thru_date - datetime.timedelta(days=1),
                                      due_date,
                                      self.payment_thru_date - datetime.timedelta(days=1) )
            delta = dateutil.relativedelta.relativedelta( payment_thru_date, self.valid_from_date )
            months_passed = delta.years * 12 + delta.months
            number_of_premiums_due = (months_passed / period_types_by_granularity[self.period_type] ) + 1
        return number_of_premiums_due

    def get_premiums_invoicing_due_amount_at(self, due_date):
        """The total amount of premiums that ought to be invoiced at a specific date.
        """
        number_of_premiums_due = self.get_premiums_due_at( due_date )
        if self.premium_amount:
            return number_of_premiums_due * self.premium_amount
        return None

    @property
    def planned_premiums(self):
        return self.get_premiums_due_at( self.valid_thru_date )

    @property
    def planned_premium_amount(self):
        """:return: the total amount of premiums that is planned to be payed"""
        return self.get_premiums_invoicing_due_amount_at( self.valid_thru_date )

    @property
    def funds_target_percentage_total(self):
        return sum(fund_distribution.target_percentage for fund_distribution in self.fund_distribution)

    def get_product(self):
        return self.product

    @property
    def applicable_features(self):
        """The list of features that apply to this premium at the fulfillment date of
        the agreement"""
        from constants import product_features
        fulfillment_date = self.fulfillment_date # this is an expensive operation
        if None in (self.premium_amount, self.valid_from_date, fulfillment_date):
            return []
        features_by_description = dict()
        
        for _key, description, _unit, _transaction, _comment in product_features:
            feature = self.get_applied_feature_at(fulfillment_date, fulfillment_date, self.premium_amount, description)
            if feature.value != None:
                features_by_description[description] = feature
        descriptions = features_by_description.keys()
        descriptions.sort()
        return [features_by_description[d] for d in descriptions]

    def get_amount_at( self, premium_amount, application_date, attribution_date, described_by ):
        """
        Calculate a certain amount (taxes, commissions, etc.) for a premium amount.

        :param premium_amount: the premium_amount, as received by the company from the customer
        :param application_date: the date at which to calculate the amount
        :param attribution_date: the date at which the amount was transferred from the customer
            to the company
        :param described_by: the type of amount requested.
        :return: a decimal or integer of the amount requested
        """
        return get_amount_at( self, premium_amount, application_date, attribution_date, described_by )

    def get_roles_at( self, application_date, described_by = None ):
        """
        :param application_date: date at which to know the roles
        :param role_type: None if all roles should be returned, a specific role
        type, if only those should be returned.
        :return: a list of roles
        """
        # FIXME duplicate code in model.bank.dossier.py:DossierMixin
        roles = [role for role in self.roles if role.from_date<=application_date and \
                    role.thru_date>=application_date and \
                    (described_by==None or role.described_by==described_by)]
        return sorted(sorted(roles, key=attrgetter('id')), key=attrgetter('rank'))

    def get_role_name_at(self, application_date, role_type, rank):
        """
        :param application_date: date at which to know the roles
        :param role_type: a specific role type
        :param rank: an integer number specifying the rank of the role
            within the specific role type
        :return: a string with the name of the the person within that role,
            or None if there is no such role
        """
        for role in self.get_roles_at(application_date, role_type):
            if role.rank == rank:
                return role.name

    def get_rate_at( self, premium_amount, application_date, attribution_date, described_by ):
        """
        Calculate a certain rate (taxes, commissions, etc.) for a premium amount.

        :param premium_amount: the premium_amount, as received by the company from the customer
        :param application_date: the date at which to calculate the amount
        :param attribution_date: the date at which the amount was transferred from the customer
            to the company
        :param described_by: the type of amount requested.
        :return: a decimal or integer of the rate requested
        """
        return get_rate_at( self, premium_amount, application_date, attribution_date, described_by )

    def get_commission_distribution(self, commission_type, commission_receiver):
        distribution = 0
        for commission_distribution in self.commission_distribution:
            if commission_distribution.described_by==commission_type and commission_distribution.recipient==commission_receiver:
                distribution += ( commission_distribution.distribution or 0 )
        return distribution

    def generate_premium_billing_amounts(self, from_date, thru_date):
        """
        :return: a generator of tuples of the form (i, date, amount) indicating which amount should be billed
        at which date
        """
        if self.period_type == 'single':
            if self.valid_from_date >= from_date and self.valid_from_date <= thru_date:
                yield (1, self.valid_from_date, self.amount)
        elif self.valid_from_date <= thru_date and self.valid_thru_date >= from_date:
            months_per_period = period_types_by_granularity[self.period_type]
            premium_date = self.valid_from_date
            i = 1
            while premium_date <= thru_date and premium_date <= self.valid_thru_date:
                yield (i, premium_date, self.amount)
                premium_date = add_months_to_date(self.valid_from_date, months_per_period * i)
                i += 1

    # check if the premium includes credit insurance
    def has_credit_insurance(self):
        for cov in self.agreed_coverages:
            if cov.has_credit_insurance():
                return True
        return False

    # check if the premium includes fully specified credit insurance
    def has_fully_specified_credit_insurance(self):
        for agreed_coverage in self.agreed_coverages:
            if agreed_coverage.has_credit_insurance() and ((agreed_coverage.coverage_for.type in ('fixed_amount', 'decreasing_amount')) or agreed_coverage.loan_defined):
                return True
        return False

    def get_insured_party_data( self,
                                from_date,
                                individual_mortality_tables = False):
        """
        Return genders, birth_dates, smoking status, surmortalities, and mortality tables for the insured parties in a premium schedule.

        :param premium_schedule: a FinancialAgreementPremiumSchedule or FinancialAccountPremiumSchedule
        :param from_date: date at which to retreive insured party data
        :param individual_mortality_tables: if set to true, individual mortality tables are also returned instead of only a 'joint' mortality table
        per coverage (makes no difference in case of only a single insured party).
        """
        from vfinance.model.insurance.mortality_table import MortalityTable, MortalityTable2Lives

        # extract necessary features
        premium_from_date = self.valid_from_date
        premium_amount = self.premium_amount
        reduction_non_smoker = float( str(self.get_applied_feature_at(from_date, premium_from_date, premium_amount, 'insurance_reduction_non_smoker', default=0).value))/100.0
        general_reduction = float( str(self.get_applied_feature_at(from_date, premium_from_date, premium_amount, 'insurance_general_risk_reduction', default=0).value))/100.0
        extra_age_days = int( self.get_applied_feature_at(from_date, premium_from_date, premium_amount, 'insurance_fictitious_extra_age', default=0).value )

        # extract gender, birth date and smoking habits of insured party(s)
        genders = []
        birth_dates = []
        smokers = []
        surmortalities = []

        gender_translation = {'m':'male', 'v':'female'}

        for role in self.get_roles_at( from_date, described_by='insured_party'):
            genders.append( gender_translation[role.natuurlijke_persoon.gender or 'm'] )
            birth_dates.append( self.add_days_to_date(role.natuurlijke_persoon.birthdate, -extra_age_days) )
            smokers.append(role.natuurlijke_persoon.smoker)
            surmortalities.append(max(0, float( str(role.surmortality or 0) ))/100.0)

        if len(genders) > 2:
            raise Exception(ugettext('There can be no more than 2 insured parties at %s. on account %s'%(from_date, unicode(self) )))

        coverages = self.get_coverages_at( from_date )
        if coverages and not genders:
            raise Exception(ugettext('There is no insured party at %s on account %s'%(from_date, unicode( self ) )))

        # adapt surmortalities to smoking status and gender
        insured_persons = len(genders)
        for i in range(0, insured_persons):
            if genders[i] == 'male':
                gender_reduction_non_smoker = float( self.get_applied_feature_at(from_date, premium_from_date, premium_amount, 'insurance_reduction_non_smoker_male', default=0).value )/100.0
                gender_reduction_smoker = float( self.get_applied_feature_at(from_date, premium_from_date, premium_amount, 'insurance_reduction_smoker_male', default=0).value )/100.0
            elif genders[i] == 'female':
                gender_reduction_non_smoker = float( self.get_applied_feature_at(from_date, premium_from_date, premium_amount, 'insurance_reduction_non_smoker_female', default=0).value )/100.0
                gender_reduction_smoker = float( self.get_applied_feature_at(from_date, premium_from_date, premium_amount, 'insurance_reduction_smoker_female', default=0).value )/100.0
            else:
                raise Exception('unknown gender')
            if not smokers[i]:
                # risk reductions are treated as negative surmortalities
                surmortalities[i] = MortalityTable.add_surmortalities(surmortalities[i], -reduction_non_smoker, -general_reduction, -gender_reduction_non_smoker)
            else:
                # risk reductions are treated as negative surmortalities
                surmortalities[i] = MortalityTable.add_surmortalities(surmortalities[i], -general_reduction, -gender_reduction_smoker)

        # create mortality table
        mortality_table_per_coverage = None
        individual_mortality_tables_per_coverage = None
        amortization = None
        if coverages:
            # every coverage can have different mortality rate tables (and hence different mortality tables)
            mortality_table_per_coverage = {}
            individual_mortality_tables_per_coverage = {}
            for coverage in coverages:
                mrate_tables = []
                for g,s in zip( genders, smokers ):
                    table = coverage.get_mortality_rate_table( g, s )
                    mrate_tables.append(table)
                    if not table:
                        raise Exception(ugettext('Missing mortality rate table product definition of %s')%unicode(self))
                if insured_persons == 1:
                    mortality_table = MortalityTable(mrate_tables[0], surmortalities[0])
                    if individual_mortality_tables:
                        individual_mortality_tables_per_coverage[coverage] = [mortality_table]
                else:
                    mortality_table = MortalityTable2Lives(mrate_tables[0], mrate_tables[1], surmortalities[0], surmortalities[1])
                    if individual_mortality_tables:
                        mortality_table1 = MortalityTable(mrate_tables[0], surmortalities[0])
                        mortality_table2 = MortalityTable(mrate_tables[1], surmortalities[1])
                        individual_mortality_tables_per_coverage[coverage] = [mortality_table1, mortality_table2]
                mortality_table_per_coverage[coverage] = mortality_table

                # amortization table (in case of credit insurance)
                loan = coverage.coverage_amortization
                if coverage.has_credit_insurance():
                    if amortization:
                        raise Exception(ugettext('Only one amortization coverage per premium allowed!'))
                    if coverage.coverage_for.type == 'fixed_amount':
                        amortization = self.Amortization(D(100),
                                                        0,
                                                        self.valid_from_date,
                                                        'bullet',
                                                        coverage.coverage_limit,
                                                        self.duration,
                                                        12)
                    elif coverage.coverage_for.type == 'decreasing_amount':
                        amortization = self.Amortization(D(100),
                                                        0,
                                                        self.valid_from_date,
                                                        'fixed_capital_payment',
                                                        coverage.coverage_limit,
                                                        self.duration,
                                                        1)
                    elif coverage.coverage_for.type == 'amortization_table':
                        amortization = self.Amortization(coverage.coverage_limit, loan.interest_rate, loan.get_starting_date,
                                                         loan.type_of_payments, loan.loan_amount, loan.number_of_months, loan.payment_interval)
                    else:
                        raise UserException('Unhandled coverage level type {0}'.format(coverage.coverage_for.type))

        return insured_party_data(genders = genders,
                                  birth_dates = birth_dates,
                                  smokers = smokers,
                                  surmortalities = surmortalities,
                                  mortality_table_per_coverage = mortality_table_per_coverage,
                                  amortization = amortization,
                                  individual_mortality_tables_per_coverage = individual_mortality_tables_per_coverage)

class FinancialAgreementPremiumSchedule(Entity, PremiumScheduleMixin):

    __tablename__ = 'time_deposit_invested_amount'

    financial_agreement_id = schema.Column(sqlalchemy.types.Integer,
                                           schema.ForeignKey(FinancialAgreement.id,
                                                             ondelete='cascade',
                                                             onupdate='cascade'),
                                           nullable=False)
    
    financial_agreement = orm.relationship(FinancialAgreement,
                                           backref = orm.backref('invested_amounts', cascade='all, delete, delete-orphan'),
                                           enable_typechecks=False)

    product_id = schema.Column(sqlalchemy.types.Integer,
                               schema.ForeignKey(Product.id,
                                                 ondelete='restrict',
                                                 onupdate='cascade'),
                               nullable=False)
    product = orm.relationship(Product)
    duration = schema.Column(sqlalchemy.types.Integer, nullable=False)
    payment_duration = schema.Column(sqlalchemy.types.Integer, nullable=True, default=None)
    period_type = schema.Column(camelot.types.Enumeration(period_types), default='single', nullable=False)
    amount = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False)
    increase_rate = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=5), nullable=False, default=0)
    direct_debit = schema.Column(sqlalchemy.types.Boolean, nullable=False, default=False, index=True)
    commission_distribution = OneToMany('vfinance.model.financial.commission.FinancialAgreementCommissionDistribution', cascade='all, delete, delete-orphan')
    fund_distribution = OneToMany('vfinance.model.financial.fund.FinancialAgreementFundDistribution',
                                  cascade='all, delete, delete-orphan',
                                  order_by=['id'])
    agreed_coverages = OneToMany('vfinance.model.insurance.agreement.InsuranceAgreementCoverage', cascade='all, delete, delete-orphan')
    # non-persistent:
    credit_insurance_calculated = False

    def __unicode__(self):
        return u'%s %i months'%(self.period_type, self.duration or 0)

    def fulfilled(self):

        ps = aliased(FinancialAccountPremiumSchedule)

        return sql.select([sql.func.count(ps.id)],
                          ps.agreed_schedule_id==self.id).limit(1)

    fulfilled = ColumnProperty( fulfilled, deferred = True )

    def current_status_sql( self ):
        query = FinancialAgreement.current_status_query( FinancialAgreement._status_history, FinancialAgreement)
        return query.where( FinancialAgreement.id == self.financial_agreement_id )

    current_status_sql = ColumnProperty( current_status_sql, deferred = True )

    def financial_account_id(self):
        return sql.select( [FinancialAgreement.account_id], FinancialAgreement.id == self.financial_agreement_id )

    financial_account_id = ColumnProperty( financial_account_id, deferred = True )

    def rank(self):

        FAPS = aliased(FinancialAgreementPremiumSchedule)

        return sql.select([sql.func.count(FAPS.id)+1],
                          sql.and_(FAPS.id < self.id,
                                   FAPS.financial_agreement_id == self.financial_agreement_id))

    rank = ColumnProperty(rank, deferred=True, group='description')

    @property
    def fulfillment_date(self):
        """Since we don't know yet when the agreement will be fulfilled, we suppose
        it will be fulfilled on the from date"""
        if self.financial_agreement:
            return self.financial_agreement.from_date

    @property
    def valid_from_date(self):
        if self.financial_agreement:
            return self.financial_agreement.from_date

    @property
    def valid_thru_date(self):
        if self.valid_from_date and self.duration:
            return add_months_to_date( self.valid_from_date, self.duration )

    @property
    def payment_thru_date(self):
        if self.valid_from_date:
            return add_months_to_date( self.valid_from_date, self.payment_duration or self.duration )

    @property
    def premium_amount(self):
        return self.amount

    @property
    def roles(self):
        if self.financial_agreement:
            return self.financial_agreement.roles
        return []

    @hybrid_property
    def history_of_id(self):
        return 0

    def get_coverages_at(self, _application_date):
        return self.agreed_coverages

    def get_coverage_switch_dates(self):
        """Returns a set of dates when some of the coverages change.
        (this function is implemented for compatibility with FinancialAccountPremiumSchedule,
        since coverages never change in an agreement)
        """
        switch_dates = set()
        switch_dates.add( self.valid_from_date )
        switch_dates.add( self.valid_thru_date )
        return switch_dates

    def get_role_switch_dates(self, role_type = None):
        """Returns a set of dates when roles of a certain type may change.
        (this function is implemented for compatibility with FinancialAccountPremiumSchedule,
        since roles never change in an agreement)

        :param role_type: None if all roles should be returned, a specific role
        type, if only those should be returned. (not used, only present for compatibility with
        FinancialAccountPremiumSchedule.get_role_switch_dates).
        """
        switch_dates = set()
        switch_dates.add( self.valid_from_date )
        switch_dates.add( self.valid_thru_date )
        return switch_dates

    from datetime import date
    def get_all_features_switch_dates(self, attribution_date = date(1302, 7, 11)):
        """The dates at which any feature applicable to the premium might switch from value
        :param attribution_date: mysterious parameter of unknown function that is silently ignored.
        Defaults to the date of the battle of the Golden Spurs.
        :return: a set of dates at which any of the features might switch from value
        """
        feature_switch_dates = set()
        for feature in self.product.available_with:
            feature_switch_dates.update( self._switch_dates_for_feature(feature, attribution_date) )
        for feature in self.agreed_features:
            feature_switch_dates.update( self._switch_dates_for_feature(feature, attribution_date) )
        return feature_switch_dates

    def use_default_features(self):
        """Take the default features that need to be overruled from the product
        definition and use them to fill the agreement.
        """
        from feature import FinancialAgreementPremiumScheduleFeature
        from commission import FinancialAgreementCommissionDistribution
        commission_type_features = [t[1] for t in commission_types]
        if not self.financial_agreement.current_status in ['draft', 'incomplete']:
            raise UserException('Agreement should be in draft or incomplete status to assign the default features')
        if not self.product:
            raise UserException('A product should be selected before a default feature can be assigned')
        if not self.valid_from_date:
            raise UserException('Agreement should have a from date to apply default features')
        for product_feature in self.product.get_applied_features_at(self.valid_from_date):
            if self._filter_feature(feature=product_feature,
                                    application_date=self.valid_from_date,
                                    feature_description=None,
                                    agreed_duration=self.duration,
                                    passed_duration=0,
                                    attributed_duration=0,
                                    direct_debit=self.direct_debit,
                                    period_type=self.period_type,
                                    from_date=self.valid_from_date,
                                    premium_amount=self.amount)[0] is False:
                continue
            if product_feature.described_by in commission_type_features:
                total_commission = sum([commission_distribution.distribution for commission_distribution in self.commission_distribution if
                                        commission_distribution.described_by==product_feature.described_by], 0)
                if total_commission == 0 and product_feature.value != 0:
                    for product_feature_distribution in product_feature.distributed_via:
                        FinancialAgreementCommissionDistribution( premium_schedule = self,
                                                                  described_by = product_feature.described_by,
                                                                  recipient = product_feature_distribution.recipient,
                                                                  distribution = product_feature_distribution.distribution )
            else:
                total_commission = 0
            if product_feature.overrule_required:
                product_feature_dict = product_feature.to_dict(exclude=['available_for', 'id', 'available_for_id'])
                if total_commission:
                    product_feature_dict['value'] = total_commission
                FinancialAgreementPremiumScheduleFeature( agreed_on=self, **product_feature_dict )

    def button_default_features(self):
        from camelot.view.remote_signals import get_signal_handler
        self.expire()
        self.use_default_features()
        self.query.session.flush()
        sh = get_signal_handler()
        sh.sendEntityUpdate( self, self.financial_agreement )

    def create_premium(self):
        from commission import FinancialAccountCommissionDistribution
        from fund import FinancialAccountFundDistribution
        from feature import FinancialAccountPremiumScheduleFeature
        from vfinance.model.insurance.account import InsuranceAccountCoverage
        agreement = self.financial_agreement
        account = agreement.account
        fulfillment_date = agreement.fulfillment_date

        if self.fulfilled:
            raise Exception('Premium schedule already created')
        if not account:
            raise Exception('Agreement has no account yet')
        if not fulfillment_date:
            raise Exception('Agreement has no fulfillment date yet')

        from_date = fulfillment_date
        if self.direct_debit:
            direct_debit_delay = int( self.get_applied_feature_at(from_date, from_date, self.amount, 'direct_debit_delay', default=0).value )
            if direct_debit_delay:
                from_date = add_months_to_date( from_date, direct_debit_delay )
                from_date = datetime.date( from_date.year, from_date.month, 1 )

        thru_date = add_months_to_date( from_date, self.duration )
        if self.payment_duration:
            payment_thru_date = add_months_to_date( from_date, self.payment_duration )
        else:
            payment_thru_date = thru_date

        account_number = FinancialAccountPremiumSchedule.new_account_number( self.product, account )
        premium = FinancialAccountPremiumSchedule(financial_account=account,
                                                  account_number=account_number,
                                                  product=self.product,
                                                  valid_from_date=from_date,
                                                  valid_thru_date=thru_date,
                                                  payment_thru_date = payment_thru_date,
                                                  premium_amount=self.amount,
                                                  increase_rate=self.increase_rate,
                                                  period_type=self.period_type,
                                                  direct_debit=self.direct_debit,
                                                  agreed_schedule=self)

        for feature in self.agreed_features:
            FinancialAccountPremiumScheduleFeature(applied_on=premium,
                                                   **feature.to_dict(exclude=['agreed_on', 'id', 'agreed_on_id']) )
        for coverage in self.agreed_coverages:
            InsuranceAccountCoverage.create_account_from_agreement(coverage, premium, from_date)
        for commission_distribution in self.commission_distribution:
            premium.commission_distribution.append( FinancialAccountCommissionDistribution(described_by=commission_distribution.described_by,
                                                                                           recipient=commission_distribution.recipient,
                                                                                           distribution=commission_distribution.distribution,
                                                                                           comment=commission_distribution.comment, ) )
        for fund_distribution in self.fund_distribution:
            FinancialAccountFundDistribution(distribution_of=premium,
                                             fund=fund_distribution.fund,
                                             from_date=from_date,
                                             thru_date=end_of_times(),
                                             target_percentage=fund_distribution.target_percentage)
        return premium

    def calc_credit_insurance_premium(self):
        """ Function to calculate the credit insurance premium in case of an associated credit life insurance.
        """
        from vfinance.model.insurance.credit_insurance import CreditInsurancePremiumSchedule

        if not self.has_credit_insurance():
            raise UserException(_('This agreement doesn\'t include a fully completed credit insurance!'))

        hundred  = D(100)

        # get amortization table coverage and extract coverage fraction
        coverage = None
        for cov in self.agreed_coverages:
            if cov.coverage_for and cov.coverage_for.type:
                if cov.coverage_for.type == 'amortization_table':
                    if coverage:
                        raise UserException(_('Only one amortization table coverage per premium is allowed.'))
                    coverage = cov
                    if not coverage.loan_defined:
                        raise UserException(_('No loan associated with insurance coverage.'))
                    coverage_fraction = D(coverage.coverage_limit)/hundred
                    # extract loan parameters
                    loan = coverage.coverage_amortization
                    initial_capital     = D(loan.get_loan_amount)
                elif cov.coverage_for.type in ('fixed_amount', 'decreasing_amount'):
                    coverage = cov
                    initial_capital = cov.coverage_limit
                    coverage_fraction = 1

        ipd = self.get_insured_party_data( self.valid_from_date )
        if not self.payment_duration:
            raise UserException( _('Please specify a payment duration') )

        # create credit insurance object
        ci = CreditInsurancePremiumSchedule( product = self.product,
                                             mortality_table = ipd.mortality_table_per_coverage[coverage],
                                             amortization_table = ipd.amortization.table,
                                             from_date = self.valid_from_date,
                                             initial_capital = initial_capital,
                                             duration = self.duration,
                                             payment_duration = self.payment_duration,
                                             coverage_duration = coverage.duration,
                                             agreed_features = self.agreed_features,
                                             roles = self.financial_agreement.roles,
                                             birth_dates = ipd.birth_dates,
                                             direct_debit = self.direct_debit,
                                             coverage_fraction = coverage_fraction,
                                             period_type = self.period_type )

        # calculate premium
        all_in_premium = ci.premium_all_in()

        # round amount
        amount = all_in_premium.quantize(D('1.00'))
#        amount = quantize(all_in_premium, '1.00')

        return amount

    def button_calc_optimal_payment_duration( self ):
        from vfinance.model.insurance.credit_insurance import CreditInsurancePremiumSchedule
        self.payment_duration = CreditInsurancePremiumSchedule.get_optimal_payment_duration( self.duration )

    def button_calc_credit_insurance_premium( self ):
        # calc premium
        self.amount = D( self.calc_credit_insurance_premium() )

    def check_credit_insurance_premium( self ):
        p = D( self.calc_credit_insurance_premium() )
        if abs( D(self.amount) - p ) >= D('0.01'):
            raise UserException( _('Available premiums don\'t match the required credit insurance premiums, please recalculate.'),
                                 detail = """Current premium %s\n"""
                                          """Needed premium %s\n"""%( self.amount, p ) )
        return True

#
# For the FinancialAccountPremiumSchedule, no active record pattern is
# used, as such, the definition of the database table is decoupled from
# the definition of the class
#
# Both the FinancialAccountPremiumSchedule and the
# FinancialAccountPremiumScheduleHistory class are mapped to the same
# financial_account_premium_schedule table, but provide a different view
# on that table
#

financial_account_premium_schedule_id_sequence = schema.Sequence('financial_account_premium_schedule_id_seq', metadata=metadata)

financial_account_premium_schedule_table = schema.Table(
    'financial_account_premium_schedule',
    metadata,
    schema.Column('id', sqlalchemy.types.Integer,
                  financial_account_premium_schedule_id_sequence,
                  primary_key=True),
    schema.Column('financial_account_id', sqlalchemy.types.Integer,
                  schema.ForeignKey('financial_account.id',
                                    ondelete='restrict',
                                    onupdate='cascade'),
                  nullable=False),
    schema.Column('product_id', sqlalchemy.types.Integer,
                  schema.ForeignKey('financial_product.id',
                                    ondelete='restrict',
                                    onupdate='cascade'),
                  nullable=False),
    schema.Column('agreed_schedule_id', sqlalchemy.types.Integer,
                  schema.ForeignKey(FinancialAgreementPremiumSchedule.id,
                                    ondelete='restrict',
                                    onupdate='cascade'),
                  nullable=False),
     schema.Column('account_number', sqlalchemy.types.Integer, nullable=False, index=True),
     schema.Column('valid_from_date', sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True ),
     # due date equals valid_from_date to keep things simple
     schema.Column('valid_thru_date', sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True ),
     schema.Column('payment_thru_date', sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True ),
     schema.Column('premium_amount', sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False),
     schema.Column('period_type', camelot.types.Enumeration(period_types), default='single', nullable=False),
     schema.Column('increase_rate', sqlalchemy.types.Numeric(precision=17, scale=5), nullable=False, default=0),
     schema.Column('direct_debit', sqlalchemy.types.Boolean, nullable=False, default=False, index=True),
     schema.Column('version_id', sqlalchemy.types.Integer(), nullable=False),
     schema.Column('from_date', sqlalchemy.types.Date(), default=sql.func.current_date(), nullable=False, index=True),
     schema.Column('thru_date', sqlalchemy.types.Date(), default=end_of_times, nullable=False, index=True),
     schema.Column('history_of_id', sqlalchemy.types.Integer(),
                   schema.ForeignKey('financial_account_premium_schedule.id',
                                     onupdate='cascade',
                                     ondelete='restrict'),
                   index = True,
                   nullable = False,
                   ),
)

#
# the constraint is initially deferred to allow the creation of new versions
# within a transaction.  this implicates that after an historic record is
# inserted, a new version should be created.
#
unique_history_constraint = schema.UniqueConstraint(
    'version_id', 'history_of_id', deferrable=True, initially=u'deferred')
financial_account_premium_schedule_table.append_constraint(
    unique_history_constraint)
#
# only postgres supports a deferred unique constraint, therefor execute
# this DLL only on postgres
#
event.listen(
    financial_account_premium_schedule_table,
    "after_create",
    schema.AddConstraint(unique_history_constraint).execute_if(
        dialect=('postgresql',))
)
event.listen(
    financial_account_premium_schedule_table,
    'before_drop',
    schema.DropConstraint(unique_history_constraint).execute_if(
        dialect=('postgresql',))
)

class FinancialAccountPremiumScheduleMixin(PremiumScheduleMixin):
    """
    Provides methods and properties on top of the PremiumScheduleMixin,
    which are specific for the FinancialAccount
    """

    @property
    def end_of_cooling_off(self):
        """The date at which the cooling off will end

        * will result in the valid_from_date if there is no cooling off
        * will result in end_of_times if we don't know when the cooling off will end
        * will result in end_of_times if T6 is known and the investment was declined
        * will result in T8 if T6 is known and the investment was accepted
        """

        if self.agreed_schedule:
            document_date = self.agreed_schedule.financial_agreement.fulfillment_date
            cooling_off_period = self.get_applied_feature_at(document_date, document_date, self.premium_amount, 'cooling_off_period')
            if not cooling_off_period.value:
                return self.valid_from_date
            if self.acceptance == 'accepted':
                return self.acceptance_post_date + datetime.timedelta(days = int(cooling_off_period.value) )
        return end_of_times()

    @property
    def earliest_investment_date(self):
        """as from this date, the premium can be invested

        :return: T9

        * will return end_of_times if we don't know it yet
         """
        if self.agreed_schedule:
            document_date = self.agreed_schedule.financial_agreement.fulfillment_date
            end_of_cooling_off = self.end_of_cooling_off
            investment_delay = self.get_applied_feature_at(document_date, document_date, self.premium_amount, 'investment_delay', default=0)
            if not investment_delay.value:
                return end_of_cooling_off
            if self.acceptance_reception_date:
                return max( end_of_cooling_off, self.acceptance_reception_date + datetime.timedelta( days = int(investment_delay.value) ) )
        return end_of_times()


    @property
    def roles(self):
        if self.financial_account:
            return self.financial_account.roles
        return []

    def get_role_switch_dates(self, role_type = None):
        """Returns a set of dates when roles of a certain type may change.
        :param role_type: None if all roles should be returned, a specific role
        type, if only those should be returned.
        """
        switch_dates = set()
        switch_dates.add( self.valid_from_date )
        switch_dates.add( self.valid_thru_date )
        for role in self.roles:
            if role_type == None or role.described_by == role_type:
                switch_dates.add( role.from_date )
                switch_dates.add( role.thru_date )
        return switch_dates

    def get_coverages_at(self, application_date):
        return [c for c in self.applied_coverages if c.from_date<=application_date and c.thru_date>=application_date]

    def get_coverage_switch_dates(self):
        """Returns a set of dates when some of the coverages change.
        """
        switch_dates = set()
        switch_dates.add( self.valid_from_date )
        switch_dates.add( self.valid_thru_date )
        for c in self.applied_coverages:
            switch_dates.add( c.from_date )
            switch_dates.add( c.thru_date )
        return switch_dates

    @property
    def premiums_invoicing_due_amount(self):
        return self.get_premiums_invoicing_due_amount_at( datetime.date.today() )

    @property
    def full_account_number(self):
        if self.financial_account_id and self.product and self.account_number:
            return u'%s%s%0*i'%( self.product.account_number_prefix,
                                 self.product.fund_number_digits*'0',
                                 self.product.account_number_digits or 1,
                                 self.account_suffix )
    
    @property
    def full_number(self):
        return self.full_account_number

    @property
    def financed_commissions_account_number(self):
        if self.financial_account and self.product and self.account_suffix and self.product.financed_commissions_prefix:
            return u'%s%0*i'%(''.join(self.product.financed_commissions_prefix),
                              self.product.account_number_digits or 1,
                              self.account_suffix)

    def __unicode__(self):
        if self.financial_account!=None and self.premium_amount!=None and self.period_type!=None:
            return u'%s %s %s'%(self.full_account_number, self.premium_amount, self.period_type)
        return u''

    @property
    def fulfillment_date(self):
        if self.agreed_schedule:
            return self.agreed_schedule.financial_agreement.fulfillment_date
        return end_of_times()

    def get_applied_notifications_at(self,
                                     application_date,
                                     notification_type,
                                     subscriber_language=None):
        """The notifications of type notification_type that should be applied
        at application_date
        :yields: FinancialProductNotificationApplicability
        DualPerson is the person to which the notification should be send
        """
        account = self.financial_account
        package = account.package
        if not subscriber_language:
            subscribers = [role for role in self.financial_account.roles if role.described_by=='subscriber']
            if len(subscribers):
                subscriber_language = subscribers[0].language
        for applied_notification in package.get_applied_notifications_at( application_date,
                                                                          notification_type,
                                                                          premium_period_type = self.period_type,
                                                                          subscriber_language = subscriber_language ):
            yield applied_notification

    def has_feature_between(self, from_date, thru_date, feature_description):
        """
        Find out if there are features applied between the from and the thru date

        :return: True or False, indicating if there are features defined
        """
        for feature in self.applied_features:
            if feature.described_by == feature_description and feature.apply_from_date <= thru_date and feature.apply_thru_date >= from_date:
                return True
        for feature in self.product.get_all_features():
            if feature.described_by == feature_description and feature.apply_from_date <= thru_date and feature.apply_thru_date >= from_date:
                return True
        return False

    def get_applied_feature_at(self, application_date, attribution_date, amount, feature_description, default=None):
        """
        :param application_date: the date at which the features will be used, eg to book a premium
        :param attribution_date: the date at which the principal was attributed to the account
        :param feature_description: the name of the feature
        :param default: what will be returned in case no feature is found (distinction between None and 0)
        :return: the applicable feature, or None in no such feature applicable
        """
        #logger.debug( 'get_applied_feature_at')
        agreed_duration = months_between_dates(self.valid_from_date, self.valid_thru_date)
        passed_duration = max( months_between_dates(self.valid_from_date, application_date), 0)
        attributed_duration = max( months_between_dates(attribution_date, application_date), 0)
        #logger.debug( 'agreed duration : %s'%agreed_duration )

        applied_feature = None
        filter_feature = self._filter_feature
        if self.financial_account and self.product:
            for feature in self.product.get_applied_features_at( application_date ):
                if filter_feature( feature,
                                   application_date,
                                   feature_description,
                                   agreed_duration,
                                   passed_duration=passed_duration,
                                   attributed_duration=attributed_duration,
                                   direct_debit = self.direct_debit,
                                   period_type = self.period_type,
                                   from_date = self.valid_from_date,
                                   premium_amount = amount )[0]:
                    applied_feature = feature
        for feature in self.applied_features:
            if filter_feature( feature,
                               application_date,
                               feature_description,
                               agreed_duration,
                               passed_duration=passed_duration,
                               attributed_duration=attributed_duration,
                               direct_debit = self.direct_debit,
                               period_type = self.period_type,
                               from_date = self.valid_from_date,
                               premium_amount = self.premium_amount )[0]:
                applied_feature = feature

        return applied_feature or FeatureMock(default)

    def get_all_features_switch_dates(self, attribution_date ):
        """The dates at which any feature applicable to the premium might switch from value
        :param attribution_date:
        :return: a set of dates at which any of the features might switch from value
        """
        feature_switch_dates = set()
        for feature in self.product.get_all_features():
            feature_switch_dates.update( self._switch_dates_for_feature(feature, attribution_date) )
        for feature in self.applied_features:
            feature_switch_dates.update( self._switch_dates_for_feature(feature, attribution_date) )
        return feature_switch_dates

    @property
    def agreement_code(self):
        """The agreement code as a string"""
        if self.agreement_code:
            return self.agreement_code

class AbstractFinancialAccountPremiumSchedule(FinancialAccountPremiumScheduleMixin):
    """
    Provides ORM properties
    """

    @declared_attr
    def product(cls):
        return orm.relationship(Product)

    @declared_attr
    def product_name(cls):
        return orm.column_property(
            sql.select(
                [Product.name],
                whereclause = Product.id == cls.__table__.c.product_id
            ),
            deferred=True,
            group='product_info')
    
    @declared_attr
    def origin(cls):
        return orm.column_property(
            sql.select( [FinancialAgreement.origin],
                        sql.and_( FinancialAgreement.id == FinancialAgreementPremiumSchedule.financial_agreement_id,
                                  FinancialAgreementPremiumSchedule.id == cls.__table__.c.agreed_schedule_id ) ),
            deferred=True,
            group='agreement')

    @staticmethod
    def agreement_code_query(columns):
        return sql.select( [FinancialAgreement.code],
                           sql.and_( FinancialAgreement.id == FinancialAgreementPremiumSchedule.financial_agreement_id,
                                     FinancialAgreementPremiumSchedule.id == columns.agreed_schedule_id ) )

    @declared_attr
    def agreement_code(cls):
        return orm.column_property(
            cls.agreement_code_query(cls.__table__.c),
            deferred=True,
            group='description')

#
# since the primary key is unique, there can only be one premium schedule
# where primary key equals the history_of_id, this is defined as the 
# current schedule (it should be the highest version of the schedule)
#
# defining the current schedule using dates would not be enforced by the
# constraints.  therefor dates are only used for reporting.
#
current_faps = financial_account_premium_schedule_table.select()
current_faps = current_faps.where(
    financial_account_premium_schedule_table.c.id == financial_account_premium_schedule_table.c.history_of_id
    )

class FinancialAccountPremiumSchedule(Entity, AbstractFinancialAccountPremiumSchedule):
    """
    This class maps to the current (in database time) state of the
    premium schedule.
    """

    __table__ = current_faps.alias('current_faps')

    agreed_schedule = orm.relationship(FinancialAgreementPremiumSchedule,
                                       backref = orm.backref('fulfilled_by'),
                                       )

    __mapper_args__ = {
        'exclude_properties': ['from_date', 'thru_date'],
        "version_id_col": financial_account_premium_schedule_table.c.version_id
    }

    @classmethod
    def new_account_number( cls, product, financial_account ):
        from sqlalchemy import func
        # make sure only one instance of this function is running at the same
        # time for the same product by locking the product row
        session = cls.query.session
        product_query = session.query(FinancialProduct)
        product_query = product_query.filter(FinancialProduct.id==product.id)
        product_query = product_query.with_lockmode('update')
        session.execute(product_query)
        q = session.query( cls.account_number )
        q = q.filter( sql.and_( cls.product_id==product.id,
                                cls.financial_account_id==financial_account.id ) )
        # one account can have multiple ps for the same product, so always take
        # the first one
        q = q.order_by( cls.id )
        q = q.limit( 1 )
        existing_account_number = q.scalar()
        if existing_account_number is not None:
            return existing_account_number
        q = session.query(func.max(cls.account_number)).filter(cls.product_id==product.id)
        max = q.scalar()
        if max is None:
            max = 0
        return max+1

    @staticmethod
    def account_status_query(columns):
        from .account import FinancialAccount
        status_type = FinancialAccount._status_history
        return sql.select( [status_type.classified_by],
                          whereclause = sql.and_( status_type.status_for_id == columns.financial_account_id,
                                                  status_type.status_from_date <= sql.functions.current_date(),
                                                  status_type.status_thru_date >= sql.functions.current_date() ),
                          from_obj = [status_type.table] ).order_by(status_type.id.desc()).limit(1)

    def account_status(self):
        return FinancialAccountPremiumSchedule.account_status_query( self )

    account_status = ColumnProperty( account_status, deferred=True, group='account_info' )

    #
    # this method is wrong since it doesn't uses the visitors, this method as 
    # well as all its dependencies should be removed
    #
    @staticmethod
    def number_of_fulfillments_query(columns, type, multiplier=1):
        """:param multiplier: the result is divided by the multiplier before it
        is returned.  this is to reduce bookings of multiple lines back to 1
        """
        return sql.select([sql.func.count(FinancialAccountPremiumFulfillment.of_id) / multiplier],
                           sql.and_(FinancialAccountPremiumFulfillment.of_id==columns.id,
                                    FinancialAccountPremiumFulfillment.fulfillment_type==type) )

    def rank(self):

        FAPS = aliased( FinancialAccountPremiumSchedule )

        return sql.select( [ sql.func.count( FAPS.id)+1 ],
                           sql.and_( FAPS.id < self.id,
                                     FAPS.financial_account_id == self.financial_account_id ) )

    rank = ColumnProperty( rank, deferred=True, group='description' )

    def premiums_invoiced_amount(self):
        from vfinance.model.bank.invoice import InvoiceItem
        return sql.select( [ sql.func.coalesce( sql.func.sum( InvoiceItem.amount ), 0 )],
                           InvoiceItem.premium_schedule_id==self.id )

    premiums_invoiced_amount = ColumnProperty( premiums_invoiced_amount, deferred=True )

    def fulfilled(self):
        return sql.select([sql.func.count(FinancialAccountPremiumFulfillment.of_id)],
                           FinancialAccountPremiumFulfillment.of_id==self.id)

    fulfilled = ColumnProperty( fulfilled, deferred=True, group='fulfillment_info' )

    def premiums_attributed_to_customer(self):
        return FinancialAccountPremiumSchedule.number_of_fulfillments_query(self, 'premium_attribution')

    premiums_attributed_to_customer = ColumnProperty( premiums_attributed_to_customer, deferred=True, group='fulfillment_info' )

    def premiums_attributed_to_account(self):
        return FinancialAccountPremiumSchedule.number_of_fulfillments_query(self, 'depot_movement' )

    premiums_attributed_to_account = ColumnProperty( premiums_attributed_to_account, deferred=True, group='fulfillment_info' )

    def premiums_attributed_to_funds(self):
        return FinancialAccountPremiumSchedule.number_of_fulfillments_query(self, 'fund_attribution')

    premiums_attributed_to_funds = ColumnProperty( premiums_attributed_to_funds, deferred=True, group='fulfillment_info' )

    @classmethod
    def account_suffix_query(cls, product_columns, ps_columns, fa_columns):
        return sql.select( [sql.case({ product_columns.numbering_scheme=='product':ps_columns.account_number,
                                       product_columns.numbering_scheme=='as_requested':ps_columns.account_number},
                                     else_=fa_columns.id)],
                           sql.and_( product_columns.id == ps_columns.product_id,
                                     ps_columns.financial_account_id == fa_columns.id ) )

    def subscriber_1(self):
        from vfinance.model.financial.account import FinancialAccount
        FAC = aliased( FinancialAccount )
        return FinancialAccount.subscriber_query( FAC, 1 ).where( FAC.id == self.financial_account_id )

    subscriber_1 = ColumnProperty( subscriber_1, deferred=True, group='subscriber_info' )

    def subscriber_2(self):
        from vfinance.model.financial.account import FinancialAccount
        FAC = aliased( FinancialAccount )
        return FinancialAccount.subscriber_query( FAC, 2 ).where( FAC.id == self.financial_account_id )

    subscriber_2 = ColumnProperty( subscriber_2, deferred=True, group='subscriber_info' )

    def acceptance(self):
        """Indicates if a notification acceptance has been received and the value of the answer"""
        from vfinance.model.financial.work_effort import FinancialAccountNotificationAcceptance, FinancialAccountNotification
        status_type = FinancialAccountNotificationAcceptance._status_history
        return sql.select( [status_type.classified_by],
                          whereclause = sql.and_( status_type.status_for_id == FinancialAccountNotificationAcceptance.id,
                                                  status_type.status_from_date <= sql.functions.current_date(),
                                                  status_type.status_thru_date >= sql.functions.current_date(),
                                                  FinancialAccountPremiumFulfillment.of_id==self.id
                                                  ),
                          from_obj = [status_type.table.join( FinancialAccountNotificationAcceptance.table ).
                                                        join( FinancialAccountNotification.table ).
                                                        join( FinancialAccountPremiumFulfillment.table, sql.and_(FinancialAccountPremiumFulfillment.entry_book_date==FinancialAccountNotification.entry_book_date,
                                                                                                                 FinancialAccountPremiumFulfillment.entry_document==FinancialAccountNotification.entry_document,
                                                                                                                 FinancialAccountPremiumFulfillment.entry_book==FinancialAccountNotification.entry_book,
                                                                                                                 FinancialAccountPremiumFulfillment.entry_line_number==FinancialAccountNotification.entry_line_number,
                                                                                                                 ))
                          ] ).limit(1)

    acceptance = ColumnProperty( acceptance, deferred=True, group='acceptance_info' )

    @staticmethod
    def acceptance_field(columns, field_name ):
        from vfinance.model.financial.work_effort import FinancialAccountNotificationAcceptance, FinancialAccountNotification
        return sql.select( [ getattr(FinancialAccountNotificationAcceptance, field_name) ],
                          whereclause = sql.and_( FinancialAccountPremiumFulfillment.of_id==columns.id ),
                          from_obj = [FinancialAccountNotificationAcceptance.table.join( FinancialAccountNotification.table ).
                                                                                   join( FinancialAccountPremiumFulfillment.table, sql.and_(FinancialAccountPremiumFulfillment.entry_book_date==FinancialAccountNotification.entry_book_date,
                                                                                                                          FinancialAccountPremiumFulfillment.entry_document==FinancialAccountNotification.entry_document,
                                                                                                                          FinancialAccountPremiumFulfillment.entry_book==FinancialAccountNotification.entry_book,
                                                                                                                          FinancialAccountPremiumFulfillment.entry_line_number==FinancialAccountNotification.entry_line_number,
                                                                                                                           ))
                          ] ).limit(1)

    def acceptance_post_date(self):
        """Indicates if a notification acceptance has been received and the value of the post date"""
        return FinancialAccountPremiumSchedule.acceptance_field(self, 'post_date')

    acceptance_post_date = ColumnProperty( acceptance_post_date, deferred=True, group='acceptance_info' )


    def acceptance_reception_date(self):
        """Indicates if a notification acceptance has been received and the value of the reception date"""
        return FinancialAccountPremiumSchedule.acceptance_field(self, 'reception_date')

    acceptance_reception_date = ColumnProperty( acceptance_reception_date, deferred=True, group='acceptance_info' )

    def unit_linked(self):
        from vfinance.model.financial.product import FinancialProduct
        return sql.select( [FinancialProduct.unit_linked],
                           whereclause = sql.and_(self.product_id == FinancialProduct.id) ).limit(1)

    unit_linked = ColumnProperty( unit_linked, deferred=True, group='product_info' )

    def get_premium_to_customer_fulfillement(self):
        for fulfillment in self.fulfilled_by:
            if fulfillment.fulfillment_type == 'premium_attribution':
                return fulfillment

    def get_document_language_at( self, document_date ):
        subscribers = [role for role in self.financial_account.roles if role.described_by=='subscriber']
        if len(subscribers):
            subscriber_language = subscribers[0].language
        else:
            subscriber_language = None
        return subscriber_language

    def get_receipt_notification(self):
        """
        :return: the FinancialAccountNotification object related to this premium fulfillment, None
        if the premium was not applied on the customer account or the receipt notification
        has not been created yet.
        """
        from vfinance.model.financial.work_effort import FinancialAccountNotification

        premium_fulfillment = self.get_premium_to_customer_fulfillement()
        if not premium_fulfillment:
            return None
        return FinancialAccountNotification.query.filter( sql.and_(FinancialAccountNotification.entry_book_date==premium_fulfillment.entry_book_date,
                                                                   FinancialAccountNotification.entry_document==premium_fulfillment.entry_document,
                                                                   FinancialAccountNotification.entry_book==premium_fulfillment.entry_book,
                                                                   FinancialAccountNotification.entry_line_number==premium_fulfillment.entry_line_number,
                                                                   )).first()

    @transaction
    def create_invoice_item(self, due_date):
        """Create an invoice item to cover the premiums due in the month of
        the due date, and invoice them at the first date of the month
        
        This functionallity should be moved to a visitor.
        
        :param due_date:
        :return: `True` if an invoice item was created, `False` otherwise
        """
        LOGGER.debug('create invoice item for premiums due till %s'%due_date)
        from vfinance.model.bank.invoice import InvoiceItem
        invoice_date = datetime.date(due_date.year, due_date.month, 1)
        due_date = datetime.date( due_date.year, due_date.month, calendar.monthrange( due_date.year,
                                                                                      due_date.month )[1] )
        self.expire(['premiums_invoiced_amount'])
        amount = self.get_premiums_invoicing_due_amount_at( due_date ) - D(str(self.premiums_invoiced_amount))
        if amount > D('0.01'):
            invoice_item = InvoiceItem(premium_schedule=self,
                                       amount=amount,
                                       doc_date=invoice_date,
                                       item_description=self.product.name[:140])
            invoice_item.flush()
            self.expire(['premiums_invoiced_amount'])
            return True
        return False

    def button_create_fund_accounts(self):
        for fund_distribution in self.fund_distribution:
            fund_distribution.create_account()

    def button_create_invoice_item(self):
        self.create_invoice_item(datetime.date.today())


FinancialAccountPremiumSchedule.financial_account = orm.relationship(
    FinancialAccount,
    backref=orm.backref('premium_schedules',
                        order_by = [FinancialAccountPremiumSchedule.id],
                        cascade='all, delete, delete-orphan'))

@event.listens_for(FinancialAccountPremiumSchedule, 'before_insert')
def receive_before_premium_schedule_insert(mapper, connection, target):
    """
    For the initial history of the premium schedule, the history_of_id column
    needs to be filled with the id itself.  Therefor the id is fetched explicitly
    from the sequence and then assigned to both the id and the history_of_id column.
    """
    next_id = connection.execute(financial_account_premium_schedule_id_sequence.next_value()).scalar()
    target.id = next_id
    target.history_of_id = next_id

class FinancialAccountPremiumScheduleHistory(
    Entity,
    AbstractFinancialAccountPremiumSchedule,
    HistoryMixin):
    """
    The FinancialAccountPremiumScheduleHistory represents the past versions
    of the FinancialAccountPremiumSchedule.  This is used for reporting
    purposes as wel as for unverification of transactions that made changes
    to the FinancialAccountPremiumSchedule.
    
    This class has two additional properties, the `from_date` and the
    `thru_date`, representing the point in time when this history was valid.
    """

    __tablename__ = None
    __table__ = financial_account_premium_schedule_table

    financial_account = orm.relationship(FinancialAccount)

@add_entry_fields
class FinancialAccountPremiumFulfillment( Entity, AbstractFulfillment ):
    """
    A fulfillment refers to an actual entry (aka line) in the accounting system.

    The fulfillment annotates this line with the data needed to process and
    query this line with regard to a premium schedule.
    """
    using_options(tablename='financial_account_premium_fulfillment', order_by=['id'])
    of_id = schema.Column(sqlalchemy.types.Integer,
                          schema.ForeignKey('financial_account_premium_schedule.id',
                                            ondelete='restrict',
                                            onupdate='cascade'),
                          nullable=False)
    of = orm.relationship(FinancialAccountPremiumSchedule, backref=orm.backref('fulfilled_by'))
    within = ManyToOne('vfinance.model.financial.transaction.FinancialTransactionPremiumSchedule', required=False, ondelete = 'restrict', onupdate = 'cascade')
    associated_to = ManyToOne('FinancialAccountPremiumFulfillment') # slows things down, backref='associated')

    def product_name(self):
        ps = aliased(FinancialAccountPremiumSchedule)
        pr = aliased(FinancialProduct)
        return sql.select([pr.name],
                          sql.and_(pr.id==ps.product_id,
                                   ps.id==self.of_id))

    product_name = ColumnProperty( product_name, deferred=True )

    def account_number_prefix(self):
        ps = aliased(FinancialAccountPremiumSchedule)
        pr = aliased(FinancialProduct)
        return sql.select([pr.account_number_prefix],
                          sql.and_(pr.id==ps.product_id,
                                   ps.id==self.of_id))

    account_number_prefix = ColumnProperty( account_number_prefix, deferred=True )

    def account_number(self):
        ps = aliased(FinancialAccountPremiumSchedule)
        return sql.select([ps.account_number],
                          sql.and_(ps.id==self.of_id))

    account_number = ColumnProperty( account_number, deferred=True )


    class Admin(AbstractFulfillment.Admin):
        form_display = AbstractFulfillment.Admin.relation_fields + AbstractFulfillment.Admin.entry_fields + ['of_id', 'account_number_prefix', 'account_number','product_name', 'from_date', 'thru_date']
        list_filter = ['product_name', 'presence',]
        list_action = []

    Admin = not_editable_admin( Admin )

premium_schedule_account_suffix_query = FinancialAccountPremiumSchedule.account_suffix_query(
    Product.__table__.c,
    FinancialAccountPremiumSchedule.__table__.c,
    FinancialAccount.__table__.c)

FinancialAccountPremiumSchedule.account_suffix = orm.column_property(
    premium_schedule_account_suffix_query,
    deferred=True
)

premium_schedule_history_account_suffix_query = FinancialAccountPremiumSchedule.account_suffix_query(
    Product.__table__.c,
    financial_account_premium_schedule_table.c,
    FinancialAccount.__table__.c)

FinancialAccountPremiumScheduleHistory.account_suffix = orm.column_property(
    premium_schedule_history_account_suffix_query,
    deferred=True
)

FinancialAccountPremiumFulfillment.account_suffix = orm.column_property(
    premium_schedule_account_suffix_query.where(sql.and_(FinancialAccountPremiumSchedule.id==FinancialAccountPremiumFulfillment.__table__.c.of_id)),
    deferred=True
)

FinancialAccountPremiumSchedule.last_premium_attribution = ColumnProperty(lambda ps:
    sql.select([sql.func.max(FinancialAccountPremiumFulfillment.entry_book_date)],
    whereclause = sql.and_(FinancialAccountPremiumFulfillment.entry_book_date <= sql.func.current_date(),
                           FinancialAccountPremiumFulfillment.__table__.c.of_id == ps.id,
                           FinancialAccountPremiumFulfillment.__table__.c.fulfillment_type == 'premium_attribution'
                           ),
    ),
    deferred=True
    )

InvoiceItem.premium_schedule_id = schema.Column(sqlalchemy.types.Integer(),
                                                schema.ForeignKey(financial_account_premium_schedule_table.c.id,
                                                                  ondelete='restrict',
                                                                  onupdate='cascade'),
                                                nullable=True)
InvoiceItem.premium_schedule = orm.relationship(
    FinancialAccountPremiumSchedule,
    backref = orm.backref('invoice_items')
)
