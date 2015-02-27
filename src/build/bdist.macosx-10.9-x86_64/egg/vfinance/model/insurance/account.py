'''
Created on Jun 30, 2010

@author: tw55413
'''
import datetime
from copy import deepcopy

from sqlalchemy import orm, schema
import sqlalchemy.types

from camelot.core.orm import Entity, ManyToOne, using_options, OneToMany
from camelot.model.authentication import end_of_times
from camelot.core.utils import ugettext_lazy as _
import camelot.types

from ..financial.premium import (financial_account_premium_schedule_table,
                                 FinancialAccountPremiumSchedule,
                                 FinancialAccountPremiumScheduleHistory,
                                 )
from vfinance.model.insurance.agreement import InsuredLoanAgreementAccountMixin, InsuredLoanAgreement, InsuranceAgreementCoverage, InsuranceAgreementAccountCoverageMixin
from vfinance.admin.vfinanceadmin import VfinanceAdmin
import constants

def coverage_for_choices(insurance_account_coverage):
    coverage_levels = []
    if insurance_account_coverage and insurance_account_coverage.premium:
        premium = insurance_account_coverage.premium
        product = premium.product
        if product:
            available_coverages = product.available_coverages
            if available_coverages:
                for available_coverage in available_coverages:
                    for level in available_coverage.with_coverage_levels:
                        coverage_levels.append( (level, unicode(level)) )
    coverage_levels.append( (None, '') )
    return coverage_levels
               
# utility function for InsuranceAccountCoverage.Admin
def delete_from_list(list, item):
    def find(list, item):
        i = 0
        for el in list:
            if el == item:
                return i
            i += 1
    
    del list[find(list, item)]
    return list

class InsuranceAccountCoverage(Entity, InsuranceAgreementAccountCoverageMixin):

    __tablename__ = 'insurance_account_coverage'

    premium_id = schema.Column(sqlalchemy.types.Integer(),
                               schema.ForeignKey(financial_account_premium_schedule_table.c.id,
                                                 ondelete='cascade',
                                                 onupdate='cascade'),
                               nullable=False)
    premium = orm.relationship(
        FinancialAccountPremiumSchedule,
        backref = orm.backref('applied_coverages',
                              cascade='all, delete, delete-orphan')
    )
    coverage_for = ManyToOne('vfinance.model.insurance.product.InsuranceCoverageLevel', required=True, ondelete = 'restrict', onupdate = 'restrict')
    coverage_limit = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0 )
    coverage_amortization = ManyToOne('InsuredLoanAccount')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )

    @property
    def full_account_number(self):
        return self.premium.full_account_number

    @property
    def coverage_from_date( self ):
        return self.from_date
    
    @property
    def smoking_status(self):
        smoking_strings = {True:_('Smoker'), False:_('Non-smoker'), None:_('Unknown')}
        if self.premium and self.premium.financial_account:
            if self.premium.financial_account.has_insured_party():
                return smoking_strings[self.premium.financial_account.get_insured_party_smoking_status()]
            else:
                return _('Unknown')
        return _('Unknown')
    
    @classmethod
    def create_account_from_agreement(cls, agreement, premium, from_date):
        """Given a InsuranceAgreementCoverage, create a InsuranceAccountCoverage for it
        :return: the InsuranceAccountCoverage
        """
        from integration.tinyerp.convenience import add_months_to_date
        coverage_from_date = agreement.from_date or from_date
        account = cls(premium = premium, 
                      coverage_for = agreement.coverage_for,
                      coverage_limit = agreement.coverage_limit,
                      from_date = coverage_from_date,
                      thru_date = min( add_months_to_date(coverage_from_date, agreement.duration),
                                       end_of_times() )
                      )
        
        # for credit insurance
        if agreement.coverage_amortization:
            ca_item = agreement.coverage_amortization
            ins_loan_acc = InsuredLoanAccount(loan = ca_item.loan,
                               loan_amount = ca_item.loan_amount,
                               interest_rate = ca_item.interest_rate,
                               number_of_months = ca_item.number_of_months,
                               type_of_payments = ca_item.type_of_payments,
                               payment_interval = ca_item.payment_interval,
                               starting_date = ca_item.get_starting_date,
                               credit_institution = ca_item.credit_institution
                               )
            ins_loan_acc.insurance_account_coverage.append(account)
        return account            

    class Admin(InsuranceAgreementCoverage.Admin):
        verbose_name = _('Account Coverage')
        
        list_display = ['premium_id', 'full_account_number',] + delete_from_list(deepcopy(InsuranceAgreementCoverage.Admin.list_display), 'duration')
        list_display.extend(['from_date', 'thru_date'])

        form_display = delete_from_list(deepcopy(InsuranceAgreementCoverage.Admin.form_display), 'duration')
        form_display.insert(len(form_display)-1, 'from_date')
        form_display.insert(len(form_display)-1, 'thru_date')
        
        field_attributes = deepcopy(InsuranceAgreementCoverage.Admin.field_attributes)
        field_attributes['coverage_for']['choices'] = coverage_for_choices
        field_attributes['premium_id'] = {'name': 'Premium schedule id'}
        
        def get_depending_objects(self, obj):
            if obj.premium:
                yield obj.premium
                if obj.premium.financial_account:
                    yield obj.premium.financial_account
            if obj.coverage_for:
                yield obj.coverage_for
            if obj.coverage_amortization:
                yield obj.coverage_amortization


        def get_query(self, *args, **kwargs):
            query = VfinanceAdmin.get_query(self, *args, **kwargs)
            query = query.options(orm.subqueryload('coverage_for'))
            query = query.options(orm.subqueryload('premium'))
            return query
        
        def get_related_status_object(self, obj):
            if obj.premium is not None:
                return obj.premium.financial_account
            return None
            

FinancialAccountPremiumScheduleHistory.applied_coverages = orm.relationship(
    InsuranceAccountCoverage,
    primaryjoin = FinancialAccountPremiumScheduleHistory.history_of_id==orm.foreign(InsuranceAccountCoverage.premium_id),
    viewonly=True,
)

class CoverageOnAccountPremiumScheduleAdmin(InsuranceAccountCoverage.Admin):
    list_display = delete_from_list(deepcopy(InsuranceAgreementCoverage.Admin.list_display), 'duration') + ['from_date', 'thru_date']

class InsuredLoanAccount(Entity, InsuredLoanAgreementAccountMixin):
    using_options(tablename='insurance_insured_loan_account')
    loan = ManyToOne('vfinance.model.hypo.beslissing.GoedgekeurdBedrag', required = False, ondelete = 'restrict', onupdate = 'restrict')
    loan_amount = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    interest_rate = schema.Column( sqlalchemy.types.Numeric(precision=10, scale=5), nullable=True)
    number_of_months = schema.Column( sqlalchemy.types.Integer(), nullable=True, default = 0)
    type_of_payments = schema.Column( camelot.types.Enumeration(constants.payment_types), nullable=True, default='fixed_payment')
    payment_interval = schema.Column( sqlalchemy.types.Integer(), nullable=True, default=1)
    starting_date = schema.Column( sqlalchemy.types.Date(), nullable=True )
    insurance_account_coverage = OneToMany('InsuranceAccountCoverage')
    credit_institution = ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', required = False, ondelete = 'restrict', onupdate = 'restrict')
    # Note: no from and thru date, these are already present in the InsuranceAccountCoverage

    @property
    def insurance_payment_interval(self):
        if self.insurance_account_coverage:
            return self.insurance_account_coverage[0].premium.period_type
                
    class Admin(InsuredLoanAgreement.Admin):

        def get_depending_objects(self, obj):
            if obj.insurance_account_coverage:
                if obj.insurance_account_coverage[0]:
                    yield obj.insurance_account_coverage[0]

