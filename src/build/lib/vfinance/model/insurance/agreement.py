'''
Created on Jun 26, 2010

@author: tw55413
'''

import sqlalchemy.types
from sqlalchemy import schema

from camelot.core.orm import Entity, ManyToOne, using_options, OneToMany
from camelot.admin.entity_admin import EntityAdmin
from camelot.core.utils import ugettext_lazy as _, ugettext
from camelot.admin.validator.entity_validator import EntityValidator
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.view.utils import enumeration_to_string
import camelot.types

from vfinance.model.hypo.beslissing import GoedgekeurdBedrag
from ..bank.statusmixin import BankRelatedStatusAdmin

import constants

from integration.tinyerp.convenience import add_months_to_date
from decimal import Decimal as D

def coverage_for_choices(insurance_agreement_coverage):
    coverage_levels = []
    premium_schedule = None
    agreement_date = None
    if insurance_agreement_coverage.premium is not None:
        agreement_date = insurance_agreement_coverage.premium.financial_agreement.agreement_date

    if insurance_agreement_coverage and insurance_agreement_coverage.premium:
        premium_schedule = insurance_agreement_coverage.premium
    if premium_schedule and premium_schedule.product:
        for coverage_level in premium_schedule.product.get_available_coverage_levels_at(agreement_date):
            coverage_levels.append( (coverage_level, unicode(coverage_level)) )
    return coverage_levels

class InsuranceAgreementCoverageValidator(EntityValidator):

    def objectValidity(self, coverage):
        messages = super(InsuranceAgreementCoverageValidator,self).objectValidity(coverage)
        if coverage.coverage_for != None:
            if coverage.coverage_for.type == 'amortization_table':
                    if coverage.coverage_limit <= 0:
                        messages.append(ugettext("Coverage limit should always be greater or equal than zero."))
                    if coverage.coverage_limit > 100:
                        messages.append(ugettext("Coverage limit should always be less or equal than 100."))
        return messages

class InsuranceAgreementAccountCoverageMixin(object):
    """Shared functionality between a InsuranceAgreementCoverage and a InsuranceAccountCoverage"""

    @property
    def coverage_thru_date( self ):
        return self.thru_date
    
    @property
    def loan_defined(self):
        if self.coverage_amortization:
            return True
        return False
    
    def has_credit_insurance(self):
        if self.coverage_for and self.coverage_for.type and self.coverage_for.type in ('amortization_table', 'fixed_amount', 'decreasing_amount'):
            return True
        return False   
    
    def default_duration(self):
        if self.premium:
            return self.premium.duration
    
    def get_mortality_rate_table( self, gender, smoker ):
        """Convenience function that returns the mortality rate tables that should be used 
        with this coverage for the specified gender.
        
        :param gender: specified by the descriptive strings in constants.mortality_rate_table_types, i.e. 'male' or 'female'.
        """
        return self.coverage_for.used_in.get_mortality_rate_table( gender, smoker )
    
def coverage_level_suffix(insurance_agreement_coverage):
    coverage_level = insurance_agreement_coverage.coverage_for
    if coverage_level is not None:
        coverage_type = coverage_level.type
        if coverage_type is not None:
            return constants.coverage_level_suffixes[coverage_type]
    return ''
    
class InsuranceAgreementCoverage(Entity, InsuranceAgreementAccountCoverageMixin):
    """This entity refers to PolicyItem on fig 5.11 p 217
    It was renamed from PolicyItem to InsuranceAgreementCoverage to maintain
    naming consistency with the FinancialAgreement
    
    There is no InsuranceAgreement type in our model, The FinancialAgreement fulfills
    that role.
    """
    using_options(tablename='insurance_agreement_coverage')
    premium = ManyToOne('vfinance.model.financial.premium.FinancialAgreementPremiumSchedule', required=True, ondelete = 'cascade', onupdate = 'cascade')
    coverage_for = ManyToOne('vfinance.model.insurance.product.InsuranceCoverageLevel', required=True, ondelete = 'restrict', onupdate = 'restrict')
    coverage_limit = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=100 )
    duration = schema.Column(sqlalchemy.types.Integer, nullable=False, default=12)
    coverage_amortization = ManyToOne('InsuredLoanAgreement') #, cascade='all, delete, delete-orphan')
    from_date = schema.Column( sqlalchemy.types.Date(), default = None, nullable=True, index = True )
    
    @property
    def thru_date(self):
        if self.premium and self.premium.valid_from_date:
            return add_months_to_date( self.from_date or self.premium.valid_from_date, self.duration )
        
    @property
    def coverage_from_date( self ):
        if self.from_date:
            return self.from_date
        if self.premium:
            return self.premium.valid_from_date
        
    @property
    def smoking_status(self):
        smoking_strings = {True:_('Smoker'), False:_('Non-smoker'), None:_('Non-smoker')}
        if self.premium:
            if self.premium.financial_agreement.has_insured_party():
                return smoking_strings[self.premium.financial_agreement.get_insured_party_smoking_status()]
            else:
                return _('Unknown')
        return _('Unknown')
    
    def __unicode__(self):
        cov_type = u''
        if self.coverage_for and self.coverage_for.type:
            cov_type =  self.coverage_for.type.replace('_',' ')
        cov_lim = u''
        if self.coverage_limit:
            cov_lim = u'{0} {1}'.format(self.coverage_limit, coverage_level_suffix(self))
        cov_dur = u''
        if self.duration:
            y, m = divmod(self.duration, 12)
            cov_dur = u'{0} year(s) {1} month(s)'.format(y, m)
        return u'{0}/{1}/{2}'.format(cov_type, cov_lim, cov_dur)

    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Agreed Coverage')
        list_display = ['coverage_for', 'coverage_limit', 'duration', 'smoking_status', 'loan_defined']
        form_display = ['coverage_for', 'coverage_limit',  'duration', 'coverage_amortization', 'from_date']
        field_attributes = {'coverage_for':{ 'minimal_column_width':25,
                                            'choices':coverage_for_choices},
                            'coverage_limit':{'suffix':coverage_level_suffix},
                            'coverage_amortization':{'name':'Covered loan', 'minimal_column_width':40,
                                                     'editable':lambda o: o.has_credit_insurance()},
                            'smoking_status':{'editable':False, 'delegate':delegates.PlainTextDelegate},
                            'loan_defined':{'editable':False, 'delegate':delegates.BoolDelegate},
                            'duration':{'delegate':delegates.MonthsDelegate, 
                                        'default':lambda o: o.default_duration(),
                                        'tooltip':lambda x: _('Duration of the coverage (not necessarily the same as the premium payment\'s duration)')}}
        form_size = (700, 400)        
        validator = InsuranceAgreementCoverageValidator

        def get_related_status_object(self, obj):
            if obj.premium is not None:
                return obj.premium.financial_agreement

        def get_depending_objects(self, obj):
            if obj.premium:
                yield obj.premium
                if obj.premium.financial_agreement:
                    yield obj.premium.financial_agreement
            if obj.coverage_for:
                yield obj.coverage_for
            yield obj.coverage_amortization
            
            
class InsuredLoanValidator(EntityValidator):

    def objectValidity(self, loan):
        messages = super(InsuredLoanValidator,self).objectValidity(loan)
        # check if 'required' fields are ok
        if loan.loan == None:
            if loan.loan_amount <= 0:
                messages.append(ugettext("Loan amount should always be greater or equal than zero."))
            if loan.interest_rate < 0:
                messages.append(ugettext("Interest rate should always be greater or equal than zero."))
            if loan.number_of_months <= 0:
                messages.append(ugettext("Number of months should always be greater or equal than zero."))
        return messages

class GoedgekeurdBedragAdmin(GoedgekeurdBedrag.Admin):
    list_display = ['aanvraagnummer', 'ontlener_name', 'goedgekeurd_bedrag', 'goedgekeurde_rente', 'goedgekeurde_looptijd', 'goedgekeurd_type_aflossing']
    list_search = ['aanvraagnummer', 'ontlener_name']
    
class InsuredLoanAgreementAccountMixin(object):
    """Shared functionality between a InsuredLoanAgreement and a InsuredLoanAccount"""
    
    # getter functions that return either the attributes, either the corresponding attribute of the associated loan
    @property
    def get_loan_amount(self):
        if self.loan == None:
            return self.loan_amount
        else:
            return D(str(self.loan.goedgekeurd_bedrag))
        
    @property
    def get_interest_rate(self):
        if self.loan == None:
            return self.interest_rate
        else:
            # convert periodic interest to yearly interest and return
            return ((1 + D(str(self.loan.goedgekeurde_rente))/D(100))**(D(12/self.get_payment_interval)) - 1)*D(100)
        
    @property
    def get_periodic_interest_rate(self):
        if self.loan == None:
            return self.periodic_interest
        else:
            return D(str(self.loan.goedgekeurde_rente))
        
    @property
    def get_number_of_months(self):
        if self.loan == None:
            return self.number_of_months
        else:
            return self.loan.goedgekeurde_looptijd
        
    @property
    def get_type_of_payments(self):
        if self.loan == None:
            return self.type_of_payments
        else:
            payment_type_translation = {
                'vaste_aflossing':'fixed_payment',
                'bullet':'bullet',
                'vast_kapitaal':'fixed_capital_payment',
                'cummulatief':'cummulative',
            }
            return payment_type_translation[self.loan.goedgekeurd_type_aflossing]
        
    @property
    def get_payment_interval(self):
        if self.loan == None:
            return self.payment_interval
        else:
            # according to choices of 'goedgekeurd_terugbetaling_interval' from hypo.beslissingen.GoedgekeurdBedrag,
            # we have to tranform the interval to get the number of months between payments
            return 12/self.loan.goedgekeurd_terugbetaling_interval
        
    @property
    def get_starting_date(self):
        from vfinance.model.insurance.account import InsuredLoanAccount
        if self.loan == None:
            if self.starting_date:
                return self.starting_date
            if isinstance(self, InsuredLoanAgreement) and len( self.insurance_agreement_coverage ):
                return self.insurance_agreement_coverage[0].premium.financial_agreement.valid_from_date
            elif isinstance(self, InsuredLoanAccount) and len( self.insurance_account_coverage ):
                return self.insurance_account_coverage[0].premium.valid_from_date
        else:
            return self.loan.aktedatum

    def _get_periodic_interest(self):
        # calculate from yearly interest rate
        if self.interest_rate and self.payment_interval:
            return ((1 + D(str(self.interest_rate))/D(100))**(1/D(12/self.payment_interval)) - 1)*D(100)
        else:
            return 0

    def _set_periodic_interest(self, rate):
        rate = D(str(rate))
        # set yearly interest rate
        self.interest_rate = ((1 + rate/D(100))**D(12/self.payment_interval) - 1)*D(100)
    
    periodic_interest = property(_get_periodic_interest, _set_periodic_interest)        
            
    def _get_number_of_years(self):
        if self.get_number_of_months:
            return self.get_number_of_months/12

    def _set_number_of_years(self, nyears):
        if nyears:
            self.number_of_months = 12*nyears
    
    number_of_years = property(_get_number_of_years, _set_number_of_years)         

    def get_mortgage_table(self):
        from vfinance.model.hypo.mortgage_table import mortgage_table

        interest   = self.get_interest_rate/100
        one_over_twelve = D(1)/D(12)
        monthly_interest = (1 + interest)**(one_over_twelve) - 1
        
        return list(mortgage_table(monthly_interest*100, 
                                   self.get_type_of_payments, 
                                   self.get_loan_amount, 
                                   12*self.number_of_years, 
                                   self.get_payment_interval, 
                                   self.get_starting_date))
        
    @property
    def name(self):
        def human_readable(str):
            return str.replace('_', ' ').capitalize()
        if self.loan_amount and self.interest_rate >= 0 and self.number_of_months and self.type_of_payments:
            return '%s, %s %%, %s months, %s'%(self.loan_amount, self.interest_rate.quantize(D('1.0000')), self.number_of_months, human_readable(self.type_of_payments))
        else:
            return '(insured loan incomplete)'

    def __unicode__(self):
        return self.name
    
class InsuredLoanAgreement(Entity, InsuredLoanAgreementAccountMixin):
    using_options(tablename='insurance_insured_loan')
    loan = ManyToOne('vfinance.model.hypo.beslissing.GoedgekeurdBedrag', required = False, ondelete = 'restrict', onupdate = 'restrict')
    loan_amount = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    interest_rate = schema.Column( sqlalchemy.types.Numeric(precision=10, scale=5), nullable=True)
    number_of_months = schema.Column( sqlalchemy.types.Integer(), nullable=True, default = 0)
    type_of_payments = schema.Column( camelot.types.Enumeration(constants.payment_types), nullable=True, default='fixed_payment')
    payment_interval = schema.Column( sqlalchemy.types.Integer(), nullable=True, default=1)
    starting_date = schema.Column( sqlalchemy.types.Date(), nullable=True )
    insurance_agreement_coverage = OneToMany('InsuranceAgreementCoverage')  # can only contain one element
    credit_institution = ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', required = False, ondelete = 'restrict', onupdate = 'restrict')
                
    # Updates the 'upstream' coverage and premium with the right data
    def update_upstream(self):
        # set coverage duration
        self.insurance_agreement_coverage[0].duration = self.number_of_months
        # set premium duration
        self.insurance_agreement_coverage[0].premium.duration = self.number_of_months
        # apparently, these changes aren't persisted, so we flush
        self.query.session.flush()
    
    class Admin(EntityAdmin):        
        verbose_name = _('Insured Loan')
        list_display = ['get_loan_amount', 'get_interest_rate', 'get_periodic_interest_rate', 'get_number_of_months', 'get_type_of_payments', 'get_payment_interval', 'get_starting_date']
        form_display = forms.HBoxForm( [ [forms.GroupBoxForm(_('Loan'), [forms.GroupBoxForm(_('Select existing loan...'),['loan']), 
                                   forms.GroupBoxForm(_('...or enter new loan data'), ['loan_amount', 'interest_rate', 'periodic_interest', 'number_of_years', 'type_of_payments', 'payment_interval', 'starting_date', 'credit_institution'])]),
                                          ], 
                                   [forms.GroupBoxForm(_('Loan summary'),['get_loan_amount', 'get_interest_rate', 'get_periodic_interest_rate', 'get_number_of_months', 'get_type_of_payments', 'get_payment_interval', 'get_starting_date'])]])
        field_attributes = {'payment_interval':{'name':_('Loan payment interval'),'choices':constants.insured_loan_interval_types, 
                                                'editable':lambda o:not o.loan},
                            'loan':{'minimal_column_width':10, 'admin':GoedgekeurdBedragAdmin},
                            'loan_amount':{'editable':lambda o:not o.loan, 'minimum':0}, 
                            'type_of_payments':{'editable':lambda o:not o.loan}, 
                            'interest_rate':{'name':_('Yearly interest rate'), 'suffix':'%', 'editable':lambda o:not o.loan},
                            'periodic_interest':{'name':_('Periodic interest rate'), 'suffix':'%', 'editable':lambda o:not o.loan,
                                                 'delegate':delegates.FloatDelegate, 'precision':7, 'minimum':0, 'calculator':True,
                                                 'tooltip':lambda x: _('Interest rate for the period define by \'Loan payment interval\'')},
                            'starting_date':{'name':_('Starting date (optional)'), 'editable':lambda o:not o.loan,
                                             'tooltip':lambda x: _('Use when the loan doesn\'t start at the same date as the credit insurance agreement.')},
                            'number_of_months':{'name':_('Duration'), 'delegate':delegates.MonthsDelegate, 'editable':lambda o:not o.loan,},
                            'credit_institution':{'editable':lambda o:not o.loan}, 
                            'get_loan_amount':{'name':_('Loan amount'), 'delegate':delegates.FloatDelegate}, 
                            'get_interest_rate':{'name':_('Yearly interest rate'), 'delegate':delegates.FloatDelegate, 
                                                 'precision':5,'suffix':'%'},
                            'get_periodic_interest_rate':{'name':_('Periodic interest rate'), 'delegate':delegates.FloatDelegate, 
                                                 'precision':7, 'suffix':'%',
                                                 'tooltip':lambda x: _('Interest rate for the period define by \'Loan payment interval\'')},
#                            'get_number_of_months':{'name':_('Duration'), 'delegate':delegates.MonthsDelegate},
                            'number_of_years':{'name':_('Duration (in years)'), 'delegate':delegates.IntegerDelegate, 'editable':lambda o:not o.loan},
                            'get_type_of_payments':{'name':_('Type of payments'), 
                                                    'choices': [(v[1], enumeration_to_string(v[1])) for v in constants.payment_types], 
                                                    'delegate':delegates.ComboBoxDelegate, 'editable':False},
                            'get_payment_interval':{'name':_('Loan payment interval'), 'choices': constants.insured_loan_interval_types, 
                                                    'delegate':delegates.ComboBoxDelegate, 'editable':False},
                            'get_starting_date':{'name':_('Starting date (optional)'), 'delegate':delegates.DateDelegate},
                            }
        form_size = (1125, 550)
        validator = InsuredLoanValidator

        # we abuse this function to set the coverage duration and the premium payment duration
        def get_depending_objects(self, obj):
            if obj.insurance_agreement_coverage:
                if obj.insurance_agreement_coverage[0]:
                    # set coverage and premium duration
                    obj.update_upstream() 
                    # and yield
                    yield obj.insurance_agreement_coverage[0]
                    # because apparently get_depending_objects doesn't chain:
                    if obj.insurance_agreement_coverage[0].premium:
                        yield obj.insurance_agreement_coverage[0].premium
                        if obj.insurance_agreement_coverage[0].premium.financial_agreement:
                            yield obj.insurance_agreement_coverage[0].premium.financial_agreement
