import logging
import calendar
import decimal
from decimal import Decimal as D
import datetime
from dateutil.relativedelta import relativedelta
import itertools

from integration.tinyerp.convenience import add_months_to_date
from sqlalchemy import orm, sql, event
from sqlalchemy.ext import hybrid

from camelot.admin.action import Action, field_action
from camelot.admin.object_admin import ObjectAdmin
from camelot.core.exception import UserException
from camelot.core.utils import ugettext_lazy as _, ugettext
from camelot.core.qt import QtGui
from camelot.core.orm import Entity
from camelot.core.memento import memento_change
from camelot.model.authentication import end_of_times
from camelot.view import forms
from camelot.view.controls import delegates
from camelot.view import action_steps
from camelot.view.art import ColorScheme

from vfinance.model.financial.product import FinancialProduct
from vfinance.model.financial.package import FinancialPackage
from vfinance.model.financial.premium import (PremiumScheduleMixin,
                                              FinancialAccountPremiumFulfillment,
                                              FinancialAgreementPremiumSchedule)
from vfinance.model.financial import constants as financial_constants
from vfinance.model.financial.agreement import FinancialAgreement
from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature
from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.model.financial.notification.utils import calculate_duration
from vfinance.model.financial.notification.premium_schedule_document import PremiumScheduleDocument, coverage_data, insured_capital_data
from vfinance.model.insurance import constants
from vfinance.model.insurance.agreement import (InsuranceAgreementCoverage,
                                                InsuredLoanAgreement)
from vfinance.model.insurance.product import InsuranceCoverageLevel
from vfinance.model.insurance.credit_insurance import CreditInsurancePremiumSchedule
from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon
from vfinance.model.financial.agreement import FinancialAgreementRole
from vfinance.model.bank.natuurlijke_persoon import person_fields
from vfinance.model.bank import constants as bank_constants
from vfinance.model.bank.entry import InMemoryEntryFulfillmentTables, Entry
from vfinance.model.bank.rechtspersoon import Rechtspersoon
from vfinance.model.bank.statusmixin import StatusComplete, StatusIncomplete, set_status


logger = logging.getLogger(__name__)

class IncompleteAgreement(StatusIncomplete ):
    verbose_name = _('Incomplete')

    def model_run(self, model_context):
        facade = model_context.get_object()

        facade.change_status('incomplete')

        memento = model_context.admin.get_related_admin(FinancialAgreement).get_memento()
        memento.register_changes([memento_change(model=unicode(FinancialAgreement.__name__),
                                                 primary_key=[facade.id],
                                                 previous_attributes={'completion time':int((datetime.datetime.now() - facade._created_at).seconds),
                                                                      'status': 'incomplete'},
                                                 memento_type='facade creation')])

        orm.object_session(facade).flush()

        facade = model_context.session.merge(facade)

        yield action_steps.OpenFormView([facade],
                                        model_context.admin.get_related_admin(FinancialAgreement))
        yield action_steps.gui.CloseView()





class CompleteAgreement(StatusComplete):
    verbose_name = _('Complete')

    def model_run(self, model_context):
        facade = model_context.get_object()

        facade.is_complete()

        created_at = facade._created_at

        set_status(facade._facade_session, facade)
        facade._facade_session.flush()
        facade.change_status('complete')
        facade._facade_session.flush()
        facade = model_context.session.merge(facade)

        memento = model_context.admin.get_related_admin(FinancialAgreement).get_memento()
        memento.register_changes([memento_change(model=unicode(FinancialAgreement.__name__),
                                                 primary_key=[facade.id],
                                                 previous_attributes={'completion time':int((datetime.datetime.now() - created_at).seconds),
                                                                      'status': 'complete'},
                                                 memento_type='facade creation')])

        yield action_steps.OpenFormView([facade],
                                        model_context.admin.get_related_admin(FinancialAgreement))
        yield action_steps.gui.CloseView()

class DiscardAgreement(Action):

    verbose_name = _('Discard')

    def model_run(self, model_context):
        facade = model_context.get_object()
        if facade is not None:
            session = orm.object_session(facade)
            session.expunge(facade)
        yield action_steps.gui.CloseView()


#class OptionsValidator(ObjectValidator):
#
#    def validate_object(self, obj):
#        messages = super(OptionsValidator, self).validate_object(obj)
#        if not len(messages):
#            for m in obj.get_messages():
#                messages.append(m)
#        return messages


class SelectNatuurlijkePersoon(field_action.SelectObject):

    def get_state(self, model_context):
        state = super(SelectNatuurlijkePersoon, self).get_state(model_context)
        state.visible = True
        return state

class CalculatePremium(Action):

    verbose_name = _('Calc Credit Insurance')

    def model_run(self, model_context):
        for options in model_context.get_selection():
            options.update_premium()
            yield action_steps.UpdateObject(options)

    def get_state(self, model_context):
        state = super(CalculatePremium, self).get_state(model_context)
        facade = model_context.get_object()
        if facade.product is None:
            state.enabled = False
        if not facade.has_insured_party():
            state.enabled = False
        return state

class PrintProposal(PremiumScheduleDocument):

    verbose_name = _('Print')

    def model_run(self, model_context):
        for options in model_context.get_selection():
            # choose step according to extension of "CIP notification" defined for package
            package = options.package
            language = options.subscriber__1__taal or 'nl'
            document_generated = False
        
            for notification in package.applicable_notifications:
                # (10, 'credit-insurance-proposal', 'package',           None) in notification_types
                if notification.notification_type == [i for i in financial_constants.notification_types if i[0] == 10][0][1] and \
                   (notification.language == language or not notification.language):
                    with TemplateLanguage(language):
                        if notification.template_extension == '.html':
                            yield action_steps.PrintJinjaTemplate(notification.template.replace('\\', '/'),
                                                                  context=self.get_context(options))
                            document_generated = True
            if not document_generated:
                # fallback in case no 'credit-insurance-proposal' notification was defined for package
                template = 'insurance/credit_insurance_proposal_BE.html'
                with TemplateLanguage(language):
                    yield action_steps.PrintJinjaTemplate(template,
                                                          context=self.get_context(options))

    def get_coverages_data(self, options, doc_date):
        from vfinance.model.financial.visitor.provision import ProvisionVisitor
        provision_visitor = ProvisionVisitor()
        agreement = options.financial_agreement
        amortization = PremiumScheduleMixin.Amortization(agreement.coverage_coverage_limit,
                                                         agreement.loan_interest_rate,
                                                         agreement.loan_from_date,
                                                         agreement.loan_type_of_payments,
                                                         agreement.loan_loan_amount,
                                                         agreement.loan_number_of_months,
                                                         agreement.loan_payment_interval)
        insured_capitals_data = []
        for year in range(agreement.coverage_from_date.year, agreement.coverage_thru_date.year + 1 ):
            coverage_date = datetime.date(year,
                                          agreement.coverage_from_date.month,
                                          min(calendar.monthrange(year,
                                                                  agreement.coverage_from_date.month )[1],
                                              agreement.coverage_from_date.day))
            insured_capital = provision_visitor.insured_capital_at(coverage_date,
                                                                   agreement._coverage,
                                                                   amortization = amortization )
            insured_capitals_data.append( insured_capital_data( from_date = coverage_date,
                                                                insured_capital = insured_capital ) )

        return[coverage_data( reference_number = 1,
                              coverage_limit = agreement.coverage_coverage_limit,
                              duration=calculate_duration(agreement.coverage_from_date, agreement.coverage_thru_date),
                              from_date = agreement.coverage_from_date,
                              thru_date = agreement.coverage_thru_date,
                              type = agreement.coverage_coverage_for.type,
                              insured_capitals = insured_capitals_data,
                              loan = None )]

    def nmonths_to_duration(self, nmonths):
        years  = nmonths / 12
        months = nmonths % 12
        string = str(years) + ' years'
        if months > 0:
            string += ', ' + str(months) + ' months'
        return string 

    def get_context( self, options ):
        tables = InMemoryEntryFulfillmentTables(Entry.__table__,
                                                FinancialAccountPremiumFulfillment.__table__)
        options.update_premium()
        premium_schedule = None
        if len(options.invested_amounts):
            premium_schedule = options.invested_amounts[-1]

        ps_data = self.get_premium_schedule_data(premium_schedule,
                                                 options.from_date,
                                                 tables = tables)

        context = {
            'today': datetime.date.today(),
            'now': datetime.datetime.now(),
            'title': u'{}(*) {} {}'.format(ugettext('premium proposal').capitalize(),
                                           ugettext('credit insurance').capitalize(),
                                           options.package.name),
            'code': options.code,
            'product': options.premium_product.name,
            'proposal': options,
            'premiums_data': [ps_data],

            'name1_present':True if options.insured_party__1__firstname or options.insured_party__1__lastname else False, 
            'mister1':'M.' if options.insured_party__1__gender == 'm' else 'Ms.', 
            'gender_1': 'male' if options.insured_party__1__gender == 'm' else 'female',
            'first_name_1':options.insured_party__1__firstname, 
            'last_name_1':options.insured_party__1__lastname,
            'smoker_1':'yes' if options.insured_party__1__smoker else 'no',
            'surmortality1_present':True if options.insured_party__1__surmortality > 0 else False,
            'surmortality1':options.insured_party__1__surmortality,
            'birthdate': options.insured_party__1__birthdate,
            
            'two_insured_parties':options.two_insured_parties,

            'name2_present':True if options.insured_party__2__firstname or options.insured_party__2__lastname else False, 
            'mister2':'M.' if options.insured_party__2__gender == 'm' else 'Ms.', 
            'gender_2': 'male' if options.insured_party__2__gender == 'm' else 'female',
            'first_name_2':options.insured_party__2__firstname, 
            'last_name_2':options.insured_party__2__lastname,
            'smoker_2':'yes' if options.insured_party__2__smoker else 'no',
            'surmortality2_present':True if options.insured_party__2__surmortality > 0 else False,
            'surmortality2':options.insured_party__2__surmortality,
            'birthdate2': options.insured_party__2__birthdate,
            
            'subscriber_name1_present':True if options.subscriber__1__firstname or options.subscriber__1__lastname else False, 
            'subscriber_mister1':'M.' if options.subscriber__1__gender == 'm' else 'Ms.', 
            'subscriber_gender1':'male' if options.subscriber__1__gender == 'm' else 'female', 
            'subscriber_first_name_1':options.subscriber__1__firstname, 
            'subscriber_last_name_1':options.subscriber__1__lastname,
            'subscriber_birthdate': options.subscriber__1__birthdate,
            
            'two_subscribers':options.two_subscribers,

            'subscriber_name2_present':True if options.subscriber__2__firstname or options.subscriber__2__lastname else False, 
            'subscriber_mister2':'M.' if options.subscriber__2__gender == 'm' else 'Ms.', 
            'subscriber_gender2':'male' if options.subscriber__2__gender == 'm' else 'female', 
            'subscriber_first_name_2':options.subscriber__2__firstname, 
            'subscriber_last_name_2':options.subscriber__2__lastname,
            'subscriber_birthdate2': options.subscriber__2__birthdate,
            
            'broker': options.broker_relation,
            
            'loan_amount':options.loan_loan_amount,
            'loan_interest_rate':D(options.loan_interest_rate).quantize(decimal.Decimal('1.0000')),
            'loan_duration':self.nmonths_to_duration(options.loan_number_of_months),
            'loan_type_of_payments':options.loan_type_of_payments,
            'loan_payment_interval_present':True if options.loan_type_of_payments != 'bullet' else False, # 2 = Bullet
            'loan_payment_interval':dict(constants.insured_loan_interval_types)[options.loan_payment_interval],
            'loan_from_date': options.from_date,
            'loan_thru_date': options.from_date + relativedelta( months = +options.loan_number_of_months ),

            'insurance_payment_interval': options.period_type,
            'insurance_premium': float(options.premium_amount),
            'insurance_duration_present': True if options.period_type != 'single' else False, 
            'insurance_duration': self.nmonths_to_duration( options.premium_payment_duration ),
            'insurance_number_of_payments': options.premium_planned_premiums,
            'coverage_coverage_limit': options.coverage_coverage_limit,
            'coverage_fraction': D(options.coverage_coverage_limit/100).quantize(decimal.Decimal('1.00')),

            'insured_party__1__subscriber__1__identical': options.insured_party_1_subscriber_1_identical,
        } 
        for role in ['insured_party', 'subscriber', 'payer', 'beneficiary']:
            for name, _default_value in person_fields:
                for i in range( 1, 3 ):
                    field = '{0}__{1}__{2}'.format(role, i, name)
                    try:
                        context[field] = getattr(options, field)
                    except AttributeError:# as ae:
                        # this need not be a problem, just that some fields do not make sense, e.g. if the payer is a smoker or not ...
                        # logger.warning('Attribute requested which is not in Options object: {0}'.format(ae))
                        # we'll do nothing with them, as they prolly won't be used anywhere
                        pass
        return context

    def get_state(self, model_context):
        state = super(PrintProposal, self).get_state(model_context)
        facade = model_context.get_object()
        for message in facade.get_messages(proposal_mode=True):
            state.enabled = False
        return state

def available_products( options ):
    products = [(None, '')]
    if options.package:
        for product in options.package.get_available_products_at( options.from_date ):
            products.append( ( product, product.name ) )
    return products

proposal_features = [ 'interest_rate',
                      'entry_fee',
                      'premium_taxation_physical_person',
                      'premium_taxation_legal_person',
                      'premium_fee_1',
                      'premium_rate_1',
                      'insurance_reduction_rate',
                      'insurance_insured_capital_charge',
                      'insurance_general_risk_reduction',
                      'insurance_fictitious_extra_age',
                      'premium_fee_2',
                      'premium_rate_2',
                      'premium_multiplier' ]

# all attributes preceeded by a certain prefix point to a specific object 
# in the agreement object hierarchy
coverage_prefix = 'coverage_'
loan_prefix = 'loan_'
mandate_prefix = 'mandate_'

class FinancialAgreementFacade(FinancialAgreement):
    """Provides a flat proxy towards a FinancialAgreement, to make it easy to
    build simplified UI elements around an agreement.

    :param agreement: the `FinancialAgreement` for which a proxy is provided

    """

    def __init__(self, **kwargs):
        """

        """
        #
        # All fields in this object should have a prefix that describes
        # to which object they relate
        #

        super(FinancialAgreementFacade, self).__init__(**kwargs)
        self._facade_session = orm.object_session(self)
        self._created_at = datetime.datetime.now()
        self._attributes = {}
        self.package = None

        default_duration = 20 * 12
        payment_duration = CreditInsurancePremiumSchedule.get_optimal_payment_duration(default_duration)
        # agreement defaults
        if self.agreement_date is None:
            self.agreement_date = datetime.date.today()
        if self.from_date is None:
            self.from_date = datetime.date.today()
        # premium defaults
        premium_schedule = self._create_premium_schedule(
            period_type='yearly',
            duration=default_duration,
            payment_duration=payment_duration,
            direct_debit=False,
        )
        self.invested_amounts.append(premium_schedule)
        ## coverage_defaults
        ## loan defaults
        #loan = self._create_object(InsuredLoanAgreement)
        #loan.loan_amount = decimal.Decimal('100000')
        #loan.interest_rate = decimal.Decimal('5')
        #loan.number_of_months = default_duration
        #loan.type_of_payments = 'fixed_payment'
        #loan.payment_interval = 1
        #coverage.coverage_amortization = loan
        # role defaults
        person = self._create_person()
        # all other roles are optional, and should not be created here
        for role_type in ('subscriber', 'insured_party'):
            self._create_role(role_type, person, 1)
        
        #for role in ['subscriber', 'insured_party', 'beneficiary', 'payer', 'pledgee']:
            #number = 2
            #if role == 'beneficiary':
                #number = 4
            #for i in range(1, number+1):
                #for field, default in person_fields:
                    ##if i > 1:
                        ##default = None
                    #setattr(self, '{0}__{1}__{2}'.format(role, i, field), default)
                #for field, default in [('identity_city',''), ('identity_type', ''), ('surmortality', 0), ('identity_date', ''),]:
                    #setattr(self, '{0}__{1}__{2}'.format(role, i, field), default)

        # these are attributes of the facade itself, that are not available in 
        # the objects behind the facade
        self._attributes = {
            # these fields were added for NL, in phase 1 (single subscriber/insured_party)
            'insured_party__1__relation_subscriber__1': '',
            'insured_party__1__denied_or_increased': 'n',
            'insured_party__1__denied_or_increased_broker': '',
            'insured_party__1__denied_or_increased_reason': '',
            'insured_party__1__denied_or_increased_date': '',
            'insured_party__1__denied_or_increased_amounts': '',
            'standard_beneficiaries_deviation': 'n',
            'pledge_rights': 'n',
            'pledge_number': '',
            'beneficiaries_order_1': '',
            'beneficiaries_order_2': '',
            'beneficiaries_order_3': '',
            'beneficiaries_order_4': '',
            'agent_name': '',
            'agent_straat': '',
            'agent_postcode': '',
            'agent_gemeente': '',
            'agent_telefoon': '',
            'agent_email': '',
            'agent_website': '',
        }

    def _create_object(self, cls):
        """Create an object of type `cls` to its constructor.
        The created object will live in the same session as the proxied agreement.
        
        No attributes are passes as kwargs in the constructor as those would risk
        to modify the session of the agreement or the passed argument.
        """
        obj = cls()
        session = orm.object_session(self)
        obj_session = orm.object_session(obj)
        if session != obj_session:
            if obj_session is not None:
                obj_session.expunge(obj)
            if session is not None:
                session.add(obj)
        return obj

    def _create_person(self):
        person = self._create_object(NatuurlijkePersoon)
        for person_field, person_field_default in person_fields:
            setattr(person, person_field, person_field_default)
        return person

    def _create_organization(self):
        organization = self._create_object(Rechtspersoon)
        return organization

    def _create_role(self, role_type, person=None, rank=1, organization=None):
        role = self._create_object(FinancialAgreementRole)
        role.described_by = role_type
        role.natuurlijke_persoon = person
        role.rechtspersoon = organization
        role.rank = rank
        role.use_custom_clause = False
        role.surmortality = 0
        self.roles.append(role)
        return role

    def _create_premium_schedule(self, period_type, duration, payment_duration, direct_debit):
        premium_schedule = self._create_object(FinancialAgreementPremiumSchedule)
        premium_schedule.product = None
        premium_schedule.period_type = period_type
        premium_schedule.payment_duration = payment_duration
        premium_schedule.duration = duration
        premium_schedule.amount = 0
        premium_schedule.direct_debit = direct_debit
        coverage = self._create_object(InsuranceAgreementCoverage)
        coverage.duration = duration
        premium_schedule.agreed_coverages.append(coverage)
        return premium_schedule

    def has_insured_party(self):
        for role in self.roles:
            if role.described_by == 'insured_party':
                natural_person = role.natuurlijke_persoon
                if natural_person.birthdate and natural_person.gender:
                    return True
        return False

    def get_related_object_for_field(self, name):
        if name.startswith(coverage_prefix):
            for agreed_premium in self.invested_amounts:
                for agreed_coverage in agreed_premium.agreed_coverages:
                    return agreed_coverage, name[len(coverage_prefix):]
        if name.startswith(loan_prefix):
            for agreed_premium in self.invested_amounts:
                for agreed_coverage in agreed_premium.agreed_coverages:
                    return agreed_coverage.coverage_amortization, name[len(loan_prefix):]
        if name.startswith(mandate_prefix):
            for mandate in self.direct_debit_mandates:
                return mandate, name[len(mandate_prefix):]
        for role_type_id, role_type in financial_constants.agreement_roles:
            role_type_prefix = role_type + '__'
            role_type_prefix_length = len(role_type_prefix)
            if name.startswith(role_type_prefix):
                rank = int(name[role_type_prefix_length:role_type_prefix_length+1])
                for role in self.roles:
                    if (role.rank==rank) and (role.described_by==role_type):
                        name = name[role_type_prefix_length+3:]
                        if name in ('surmortality', 'rank', 'custom_clause', 'natuurlijke_persoon'):
                            return role, name
                        return role.natuurlijke_persoon, name
                # role not found
                return None, None
        return self, name
    #
    # To make this object behave as premium schedule, all attributes starting
    # with 'premium_' are available at the object level
    #
    def __getattr__( self, name ):
        related_obj, name = self.get_related_object_for_field(name)
        if related_obj == self:
            return object.__getattribute__(self, name)
        if related_obj is not None:
            return getattr(related_obj, name)
        # name can be None if a related object doesn't exist
        if name is None:
            return None
        logger.error('Attribute not found: {0}.'.format(name))
        return self._attributes[name]

    def __setattr__( self, name, value ):
        related_obj, related_obj_name = self.get_related_object_for_field(name)
        if isinstance(value, Entity):
            session = orm.object_session(value)
            if session != self._facade_session:
                value = self._facade_session.merge(value)
        if related_obj is not None and not isinstance(related_obj, self.__class__):
            return setattr(related_obj, related_obj_name, value)
        # the view might set attributes of roles that don't exist yet, such as
        # the 2nd insured party, this will lead to a related_obj that is None,
        # but those attributes should not be set on the facade, or the will cause
        # __getattr__ to retrieve the faulty value
        if name.startswith('_') or (name in type(self).__dict__):
            return object.__setattr__(self, name, value)
        if name in self._attributes:
            self._attributes[name] = value


    def __unicode__( self ):
        return 'Credit Insurance Proposal Options'

    # Properties that make this class look like a premium schedule, these should
    # be removed in a future version
    #

    @property
    def valid_from_date(self):
        return self.premium_valid_from_date

    @property
    def direct_debit(self):
        return self.premium_direct_debit

    @property
    def planned_premiums(self):
        return self.premium_planned_premiums

    @property
    def period_type(self):
        return self.premium_period_type

    def get_applied_feature_at(self, *args, **kwargs):
        for agreed_premium in self.invested_amounts:
            return agreed_premium.get_applied_feature_at(*args, **kwargs)

    @property
    def loan_amount(self):
        return self.loan_loan_amount
    
    def get_interest_rate(self):
        return self.loan_interest_rate
    
    def set_interest_rate( self, interest_rate ):
        self.loan_interest_rate = interest_rate
        
    interest_rate = property( get_interest_rate, set_interest_rate )
    
    def get_type_of_payments(self):
        return self.loan_type_of_payments

    def set_type_of_payments(self, type_of_payments):
        if type_of_payments == 'bullet':
            self.interest_rate = D(0)
        self.loan_type_of_payments = type_of_payments

    type_of_payments = property( get_type_of_payments, set_type_of_payments)

    @property
    def payment_interval(self):
        return self.loan_payment_interval
    
    @property
    def premium_from_date( self ):
        return self.from_date
    
    @property
    def fulfillment_date(self):
        return self.from_date
    
    @property
    def thru_date(self):
        if self.from_date:
            return add_months_to_date( self.from_date, self.premium_duration )

    @property
    def valid_thru_date(self):
        return self.premium_valid_thru_date

    @property
    def coverage_from_date( self ):
        return self.from_date
    
    @property
    def coverage_thru_date(self):
        if self.from_date:
            return add_months_to_date( self.from_date, self.coverage_duration )

    #
    # Attributes to make this class look like a coverage
    #
    @property
    def coverage_for(self):
        return self.coverage_coverage_for
    
    @property
    def premium(self):
        return self
    
    #
    # End of coverage like attributes
    #
    
    @property
    def loan_from_date( self ):
        return self.from_date
    
    @property
    def payment_thru_date(self):
        if self.from_date:
            return add_months_to_date( self.from_date, self.premium_payment_duration or self.premium_duration )

    def get_messages(self, proposal_mode=None):
        for message in super(FinancialAgreementFacade, self).get_messages(proposal_mode):
            yield message
        if not self.product_has_credit_insurance():
            yield ugettext("Selected product should include credit insurance.")
        for premium_schedule in self.invested_amounts:
            if premium_schedule.period_type != 'single' and premium_schedule.payment_duration:
                if (premium_schedule.payment_duration % financial_constants.period_types_by_granularity[premium_schedule.period_type]) != 0:
                    yield ugettext("Payment duration has to be a whole multiple of the period type.")

    @property
    def agreed_features( self ):
        return self.premium_agreed_features

    @property
    def note_color(self):
        for message in self.get_messages(proposal_mode=True):
            return ColorScheme.NOTIFICATION
        return ColorScheme.aluminium

    def get_note_color(self):
        return self.note_color


    @property
    def note(self):
        for message in self.get_messages(proposal_mode=True):
            return message
        for message in self.get_messages():
            return message

    def get_funds_at( self, application_date):
        return []

    def get_role(self, role_type, rank):
        for role in self.get_roles_at(self.from_date, role_type):
            if role.rank == rank:
                return role

    def remove_role(self, role_type, rank):
        role = self.get_role(role_type, rank)
        if role is not None:
            self.roles.remove(role)

    def compare_roles(self, left_role_type, right_role_type, rank):
        left_role = self.get_role(left_role_type, rank)
        right_role = self.get_role(right_role_type, rank)
        if None not in (left_role, right_role):
            return left_role.natuurlijke_persoon == right_role.natuurlijke_persoon
        return False

    def reuse_role(self, existing_role_type, new_role_type, rank):
        existing_role = self.get_role(existing_role_type, rank)
        if existing_role is not None:
            person = existing_role.natuurlijke_persoon
        else:
            person = self._create_person()
        self._create_role(new_role_type, person, rank)
    
    def add_person_role(self, role_type, rank):
        person = self._create_person()
        return self._create_role(role_type, person, rank)

    def add_organization_role(self, role_type, rank):
        organization = self._create_organization()
        return self._create_role(role_type, rank=rank, organization=organization)

    #
    # Properties to easy the entry of roles
    #

    @property
    def two_subscribers(self):
        return (self.get_role('subscriber', 2) is not None)

    @two_subscribers.setter
    def two_subscribers(self, value):
        if (value==True) and (self.two_subscribers==False):
            self.reuse_role('insured_party', 'subscriber', 2)
        elif (value==False) and (self.two_subscribers==True):
            self.remove_role('subscriber', 2)

    @property
    def two_insured_parties(self):
        return (self.get_role('insured_party', 2) is not None)

    @two_insured_parties.setter
    def two_insured_parties(self, value):
        if value != self.two_insured_parties:
            if value==True:
                person = self._create_person()
                self._create_role('insured_party', person, 2)
            else:
                self.remove_role('insured_party', 2)

    @property
    def insured_party_1_subscriber_1_identical(self):
        return self.compare_roles('insured_party', 'subscriber', 1)

    @insured_party_1_subscriber_1_identical.setter
    def insured_party_1_subscriber_1_identical(self, value):
        if value != self.insured_party_1_subscriber_1_identical:
            self.remove_role('subscriber', 1)
            if value==True:
                self.reuse_role('insured_party', 'subscriber', 1)
            else:
                person = self._create_person()
                self._create_role('subscriber', person, 1)

    @property
    def insured_party_2_subscriber_2_identical(self):
        return self.compare_roles('insured_party', 'subscriber', 2)

    @insured_party_2_subscriber_2_identical.setter
    def insured_party_2_subscriber_2_identical(self, value):
        if value != self.insured_party_2_subscriber_2_identical:
            self.remove_role('subscriber', 2)
            if value==True:
                self.reuse_role('insured_party', 'subscriber', 2)
            else:
                person = self._create_person()
                self._create_role('subscriber', person, 2)

    # check if current product includes credit insurance
    def product_has_credit_insurance(self):
        for premium_schedule in self.invested_amounts:
            if premium_schedule.product is not None:
                for cov in premium_schedule.product.available_coverages:
                    for level in cov.with_coverage_levels:
                        if level.type in ('amortization_table', 'fixed_amount', 'decreasing_amount'):
                            return True
            else:
                return False
        return False

    #
    # Mehods related to the credit insurance premium
    #

    def update_premium(self):
        for premium_schedule in self.invested_amounts:
            premium_schedule.amount =  D('%.2f'%premium_schedule.calc_credit_insurance_premium())

    def calc_credit_insurance_premium(self):
        for premium_schedule in self.invested_amounts:
            return premium_schedule.calc_credit_insurance_premium()

    def default_payment_duration(self):
        from vfinance.model.insurance.credit_insurance import CreditInsurancePremiumSchedule
        if self.loan_number_of_months:
            return CreditInsurancePremiumSchedule.get_optimal_payment_duration(self.loan_number_of_months)
        return None

    def maximum_payment_duration(self):
        if self.loan_number_of_months:
            return self.loan_number_of_months
        return None

    def payment_duration_background_color(self):
        if self.payment_duration > self.maximum_payment_duration():
            return QtGui.QColor('red')
        return None

    class Admin(FinancialAgreement.Admin):

        form_actions = [IncompleteAgreement(),
                        CompleteAgreement(),
                        DiscardAgreement(),
                        CalculatePremium(),
                        PrintProposal()]

        form_display = forms.Form([
            forms.WidgetOnlyForm('note'),
            forms.TabForm( [ ( _('Proposal'),
                               forms.HBoxForm([ 
                                   forms.VBoxForm([ 
                                       ['code', '_package', 'product', 'insured_party__1__taal', 'broker_relation','two_insured_parties'], 
                                       forms.HBoxForm([ 
                                           forms.GroupBoxForm(
                                               _('First insured party'), 
                                               ['insured_party__1__natuurlijke_persoon',
                                                'insured_party__1__nationaliteit', 'insured_party__1__nationaal_nummer', 'insured_party__1__voornaam', 'insured_party__1__naam', 'insured_party__1__geboortedatum', 'insured_party__1__gender', 'insured_party__1__rookgedrag', 'insured_party__1__surmortality']),
                                           forms.GroupBoxForm(
                                               _('Second insured party'), 
                                               ['insured_party__2__natuurlijke_persoon',
                                                'insured_party__2__nationaliteit', 'insured_party__2__nationaal_nummer', 'insured_party__2__voornaam', 'insured_party__2__naam', 'insured_party__2__geboortedatum', 'insured_party__2__gender', 'insured_party__2__rookgedrag', 'insured_party__2__surmortality']) 
                                       ]),
                                       ['two_subscribers'],
                                       forms.HBoxForm([ 
                                           forms.GroupBoxForm(
                                               _('First subscriber'), 
                                               ['insured_party_1_subscriber_1_identical', 'subscriber__1__natuurlijke_persoon',
                                                'subscriber__1__nationaliteit', 'subscriber__1__nationaal_nummer', 'subscriber__1__voornaam', 'subscriber__1__naam', 'subscriber__1__geboortedatum', 'subscriber__1__gender']),
                                           forms.GroupBoxForm(
                                               _('Second subscriber'),
                                               ['insured_party_2_subscriber_2_identical', 'subscriber__2__natuurlijke_persoon',
                                                'subscriber__2__nationaliteit', 'subscriber__2__nationaal_nummer', 'subscriber__2__voornaam', 'subscriber__2__naam', 'subscriber__2__geboortedatum', 'subscriber__2__gender']) 
                                       ]),
                                       forms.Stretch(),
                                   ]),  
                                   forms.VBoxForm([ 
                                       forms.GroupBoxForm(
                                           _('Loan'), 
                                           ['loan_loan_amount', 
                                            'loan_interest_rate', 
                                            'loan_periodic_interest', 
                                            'duration', 
                                            'loan_type_of_payments', 
                                            'loan_payment_interval', 
                                            'from_date',]
                                       ),
                                       forms.GroupBoxForm(
                                           _('Credit Insurance'), 
                                           ['premium_direct_debit', 'premium_period_type', 'premium_payment_duration', 'coverage_coverage_limit', 'premium_amount'] ),
                                       forms.Stretch(),
                                       ],),
                                   ],), ),
                             ( _('Features'),
                               [forms.Form(['feature_'+proposal_feature+'_value' for proposal_feature in proposal_features], columns=2),
                                forms.Stretch(), forms.Stretch()]),
                             ] ),
            ], scrollbars=True)


        form_state = 'maximized'

        field_attributes = FinancialAgreement.Admin.field_attributes
        field_attributes.update({'note':{'delegate':delegates.NoteDelegate, 'background_color': lambda obj: obj.get_note_color()},
                            'product':{'name':_('Product'), 
                                            'delegate':delegates.ComboBoxDelegate,
                                            'choices':available_products,
                                            'target':FinancialProduct,
                                            'nullable':False, 
                                            'editable':True},
                            '_package':{'name':_('Package'), 'delegate':delegates.ManyToOneChoicesDelegate, 
                                                 'target':FinancialPackage,
                                                 'name':'Package',
                                                 'nullable':False, 
                                                 'editable':True},
                            'duration':{'name': _('Duration'),
                                        'delegate': delegates.MonthsDelegate,
                                        'minimum': 1,
                                        'editable': True},
                            'two_insured_parties':{'delegate':delegates.BoolDelegate, 'nullable':False, 'editable':True},
                            'two_subscribers':{'delegate':delegates.BoolDelegate, 'nullable':False, 'editable':True},
                            'insured_party_1_subscriber_1_identical': {'delegate':delegates.BoolDelegate, 'nullable':False, 'editable':True, 'name': 'Use 1st insured party'},
                            'insured_party_2_subscriber_2_identical': {'delegate':delegates.BoolDelegate, 'nullable':False, 'editable':True, 'name': 'Use 2nd insured party'},
                           })

        for proposal_feature in proposal_features:
            field_attributes['feature_'+proposal_feature+'_value'] = {'name': proposal_feature,
                                                                      'precision': bank_constants.product_features_precision[proposal_feature],
                                                                      'suffix': bank_constants.product_features_suffix[proposal_feature],
                                                                      'editable': True
                                                                      }
        ['feature_'+proposal_feature+'_value' for proposal_feature in proposal_features]


        #validator = OptionsValidator
        
        def get_related_admin_for_field(self, related_field_name):
            if related_field_name.startswith(coverage_prefix):
                related_admin = self.get_related_admin(InsuranceAgreementCoverage)
                return related_admin, related_field_name[len(coverage_prefix):]
            if related_field_name.startswith(loan_prefix):
                related_admin = self.get_related_admin(InsuredLoanAgreement)
                return related_admin, related_field_name[len(loan_prefix):]
            for role_type_id, role_type in financial_constants.agreement_roles:
                role_type_prefix = role_type + '__'
                role_type_prefix_length = len(role_type_prefix)
                if related_field_name.startswith(role_type_prefix):
                    related_field_name = related_field_name[role_type_prefix_length+3:]
                    if related_field_name in ('surmortality', 'rank', 'custom_clause', 'natuurlijke_persoon'):
                        return self.get_related_admin(FinancialAgreementRole), related_field_name
                    else:
                        return self.get_related_admin(NatuurlijkePersoon), related_field_name
            return None, related_field_name

        def get_field_attributes(self, field_name):
            related_admin, related_field_name = self.get_related_admin_for_field(field_name)
            if related_admin is not None:
                field_attributes = related_admin.get_field_attributes(related_field_name)
                if related_field_name == 'natuurlijke_persoon':
                    field_attributes['actions'] = [SelectNatuurlijkePersoon()]
            else:
                field_attributes = ObjectAdmin.get_field_attributes(self, field_name)
            return field_attributes

        def get_dynamic_field_attributes(self, obj, field_names):
            for field_name in field_names:
                related_admin, related_field_name = self.get_related_admin_for_field(field_name)
                if related_admin is not None:
                    related_obj, related_field_name = obj.get_related_object_for_field(field_name)
                    if related_obj is None:
                        yield {'editable': False, 'nullable': True}
                    elif field_name.startswith('subscriber__1') and obj.insured_party_1_subscriber_1_identical:
                        yield {'editable': False, 'nullable': True}
                    # dont allow changing the person from within the proposal form
                    elif isinstance(related_obj, (NatuurlijkePersoon,)) and (related_obj.id is not None):
                        yield {'editable': False, 'nullable': True}
                    else:
                        for dynamic_field_attributes in related_admin.get_dynamic_field_attributes(related_obj, [related_field_name]):
                            yield dynamic_field_attributes
                else:
                    for dynamic_field_attributes in ObjectAdmin.get_dynamic_field_attributes(self, obj, [field_name]):
                        yield dynamic_field_attributes

        def flush(self, obj):
            pass

#
# Add properties that manipulate premium schedules by rank
#
for rank in range(1, 3):

    def create_coverage_level_type_property(rank):
        
        def get_coverage_level_type(self):
            for i, agreed_schedule in enumerate(self.invested_amounts):
                if i == rank-1:
                    for agreed_coverage in agreed_schedule.agreed_coverages:
                        if agreed_coverage.coverage_for is not None:
                            return agreed_coverage.coverage_for.type
        
        def set_coverage_level_type(self, value):
            for i, agreed_schedule in enumerate(self.invested_amounts):
                if i == rank-1:
                    if agreed_schedule.product is None:
                        continue
                    for coverage_level in agreed_schedule.product.get_available_coverage_levels_at(self.agreement_date):
                        if coverage_level.type == value:
                            for agreed_coverage in agreed_schedule.agreed_coverages:
                                agreed_coverage.coverage_for = coverage_level
                            break
                    else:
                        raise UserException('Product {0.id} {0.name} has no coverage level of type {1}'.format(agreed_schedule.product, value))
        
        def coverage_level_type_expr(self):
            return sql.select(
                [InsuranceCoverageLevel.type],
                whereclause=sql.and_(InsuranceAgreementCoverage.premium_id==FinancialAgreementPremiumSchedule.id,
                                     FinancialAgreementPremiumSchedule.financial_agreement_id==self.id,
                                     InsuranceCoverageLevel.id==InsuranceAgreementCoverage.coverage_for_id,
                                     ),
                limit=1
            )

        return hybrid.hybrid_property(
            get_coverage_level_type,
            fset=set_coverage_level_type,
            expr=coverage_level_type_expr
        )

    setattr(FinancialAgreementFacade,
            'premium_schedule__{0}__coverage_level_type'.format(rank),
            create_coverage_level_type_property(rank)
            )

    def create_product_property(rank):

        def product_get(self):
            for i, agreed_schedule in enumerate(self.invested_amounts):
                if i == rank-1:
                    return agreed_schedule.product
    
        def product_set(self, value):
            if rank == len(self.invested_amounts) + 1:
                previous_schedule = self.invested_amounts[-1]
                premium_schedule = self._create_premium_schedule(
                    period_type = previous_schedule.period_type,
                    duration = previous_schedule.duration,
                    payment_duration = previous_schedule.payment_duration,
                    direct_debit = previous_schedule.direct_debit
                )
                self.invested_amounts.append(premium_schedule)
            for i, agreed_schedule in enumerate(self.invested_amounts):
                if i == rank-1:
                    agreed_schedule.product = value

        return property(product_get, fset=product_set)

    setattr(FinancialAgreementFacade,
             'premium_schedule__{0}__product'.format(rank),
             create_product_property(rank)
             )

    for property_name in ['product_id', 'duration', 'payment_duration', 'period_type', 'amount']:
    
        def create_premium_schedule_property(rank, name):
    
            def fget(self):
                for i, agreed_schedule in enumerate(self.invested_amounts):
                    if i == rank-1:
                        return getattr(agreed_schedule, name)

            def fset(self, value):
                for i, agreed_schedule in enumerate(self.invested_amounts):
                    if i == rank-1:
                        setattr(agreed_schedule, name, value)
    
            def expr(self):
                return sql.select([getattr(FinancialAgreementPremiumSchedule, name)],
                                  whereclause=FinancialAgreementPremiumSchedule.financial_agreement_id==self.id,
                                  limit=1
                                  )
    
            return hybrid.hybrid_property(fget, fset=fset, expr=expr)
    
        setattr(FinancialAgreementFacade,
                'premium_schedule__{0}__{1}'.format(rank, property_name),
                create_premium_schedule_property(rank, property_name)
                )

    for feature_name in proposal_features:
    
        def create_feature_property(rank, feature_name):
    
            def fget(self):
                pass
    
            def fset(self, value):
                for i, agreed_schedule in enumerate(self.invested_amounts):
                    if i != rank-1:
                        continue
                    agreed_feature = agreed_schedule.agreed_features_by_description.get(feature_name)
                    if agreed_feature is None:
                        agreed_feature = self._create_object(FinancialAgreementPremiumScheduleFeature)
                        agreed_feature.described_by = feature_name
                        agreed_feature.agreed_on = agreed_schedule
                        # set all the defaults, maybe this should go through the admin
                        agreed_feature.premium_from_date = self.from_date
                        agreed_feature.apply_from_date = self.from_date
                        agreed_feature.premium_from_date = self.from_date
                        agreed_feature.premium_thru_date = end_of_times()
                        agreed_feature.apply_from_date = self.from_date
                        agreed_feature.apply_thru_date = end_of_times()
                        agreed_feature.from_amount = D(0)
                        agreed_feature.from_agreed_duration = 0
                        agreed_feature.thru_agreed_duration = 400*12
                        agreed_feature.from_passed_duration = 0
                        agreed_feature.thru_passed_duration = 400*12
                        agreed_feature.from_attributed_duration = 0
                        agreed_feature.thru_attributed_duration = 400*12
                    agreed_feature.value = value
    
            def expr(self):
                return sql.select([FinancialAgreementPremiumScheduleFeature.value],
                                  whereclause=sql.and_(FinancialAgreementPremiumSchedule.financial_agreement_id==self.id,
                                                       FinancialAgreementPremiumSchedule.id==FinancialAgreementPremiumScheduleFeature.agreed_on_id),
                                  limit=1
                                  )
    
            return hybrid.hybrid_property(fget, fset=fset, expr=expr)
    
        setattr(FinancialAgreementFacade,
                'premium_schedule__{0}__{1}'.format(rank, feature_name),
                create_feature_property(rank, feature_name)
                )

#
# Add properties for organization roles
#


def create_role_property(role_type, property_name):

    def fget(self):
        role = self.get_role(role_type, 1)
        if role is not None:
            return getattr(role, property_name)

    def fset(self, value):
        role = self.get_role(role_type, 1)
        if role is None:
            role = self.add_organization_role(role_type, 1)
        setattr(role.rechtspersoon, property_name, value)

    return hybrid.hybrid_property(fget, fset=fset, expr=None)

for property_name in ['name', 'tax_id']:
    for role_type in ['pledgee']:
        setattr(FinancialAgreementFacade,
                '{0}_{1}'.format(role_type, property_name),
                create_role_property(role_type,  property_name)
                )
#
# Add properties that manipulate all premium schedules at once
#
for property_name in ['duration', 'payment_duration', 'period_type']:

    def create_premium_schedules_property(name):

        def fget(self):
            pass

        def fset(self, value):
            for agreed_schedule in self.invested_amounts:
                setattr(agreed_schedule, name, value)

        def expr(self):
            return sql.select([getattr(FinancialAgreementPremiumSchedule, name)],
                              whereclause=FinancialAgreementPremiumSchedule.financial_agreement_id==self.id,
                              limit=1
                              )

        return hybrid.hybrid_property(fget, fset=fset, expr=expr)

    setattr(FinancialAgreementFacade,
            'premium_schedules_{0}'.format(property_name),
            create_premium_schedules_property(property_name)
            )

for feature_name in proposal_features:

    def create_feature_property(feature_name):

        def fget(self):
            pass

        def fset(self, value):
            for agreed_schedule in self.invested_amounts:
                agreed_feature = agreed_schedule.agreed_features_by_description.get(feature_name)
                if agreed_feature is None:
                    agreed_feature = self._create_object(FinancialAgreementPremiumScheduleFeature)
                    agreed_feature.described_by = feature_name
                    agreed_feature.agreed_on = agreed_schedule
                    # set all the defaults, maybe this should go through the admin
                    agreed_feature.premium_from_date = self.from_date
                    agreed_feature.apply_from_date = self.from_date
                    agreed_feature.premium_from_date = self.from_date
                    agreed_feature.premium_thru_date = end_of_times()
                    agreed_feature.apply_from_date = self.from_date
                    agreed_feature.apply_thru_date = end_of_times()
                    agreed_feature.from_amount = D(0)
                    agreed_feature.from_agreed_duration = 0
                    agreed_feature.thru_agreed_duration = 400*12
                    agreed_feature.from_passed_duration = 0
                    agreed_feature.thru_passed_duration = 400*12
                    agreed_feature.from_attributed_duration = 0
                    agreed_feature.thru_attributed_duration = 400*12
                agreed_feature.value = value

        def expr(self):
            return sql.select([FinancialAgreementPremiumScheduleFeature.value],
                              whereclause=sql.and_(FinancialAgreementPremiumSchedule.financial_agreement_id==self.id,
                                                   FinancialAgreementPremiumSchedule.id==FinancialAgreementPremiumScheduleFeature.agreed_on_id),
                              limit=1
                              )

        return hybrid.hybrid_property(fget, fset=fset, expr=expr)

    setattr(FinancialAgreementFacade,
            'premium_schedules_{0}'.format(feature_name),
            create_feature_property(feature_name)
            )

def get_coverage_limit(self):
    coverage_limits = set(
        agreed_coverage.coverage_limit for agreed_coverage in itertools.chain.from_iterable(
        agreed_schedule.agreed_coverages for agreed_schedule in self.invested_amounts
        )
    )
    if len(coverage_limits) == 1:
        return coverage_limits.pop()

def set_coverage_limit(self, coverage_limit):
    for agreed_schedule in self.invested_amounts:
        for agreed_coverage in agreed_schedule.agreed_coverages:
            agreed_coverage.coverage_limit = coverage_limit

def coverage_limit_expr(self):
    return sql.select(
        [InsuranceAgreementCoverage.coverage_limit],
        whereclause=sql.and_(InsuranceAgreementCoverage.premium_id==FinancialAgreementPremiumSchedule.id,
                             FinancialAgreementPremiumSchedule.financial_agreement_id==self.id),
        limit=1
    )

FinancialAgreementFacade.premium_schedules_coverage_limit = hybrid.hybrid_property(
    get_coverage_limit,
    fset=set_coverage_limit,
    expr=coverage_limit_expr)

#
# A single duration property that manipulates the premium duration,
# the loan duration, coverage duration and the premium payment duration
#

def get_duration(self):
    durations = set(
        agreed_coverage.coverage_duration for agreed_coverage in itertools.chain.from_iterable(
        agreed_schedule.agreed_coverages for agreed_schedule in self.invested_amounts
        )
    )
    durations.update(set(
        agreed_schedule.duration for agreed_schedule in self.invested_amounts
    )
    )
    if len(durations) == 1:
        return durations.pop()

def set_duration(self, value):
    for agreed_schedule in self.invested_amounts:
        agreed_schedule.duration = value
        for agreed_coverage in agreed_schedule.agreed_coverages:
            agreed_coverage.duration = value

def duration_expr(self):
    return sql.select([FinancialAgreementPremiumSchedule.duration],
                      whereclause=FinancialAgreementPremiumSchedule.financial_agreement_id==self.id,
                      limit=1
                      )

FinancialAgreementFacade.duration = hybrid.hybrid_property(
    get_duration,
    fset=set_duration,
    expr=duration_expr)

#
# Add automagic completion of fields
#
@event.listens_for(FinancialAgreementFacade.package, 'set')
def package_set(target, value, oldvalue, initiator):
    if value is not None:
        for product in value.get_available_products_at(target.from_date):
            for agreed_schedule in target.invested_amounts:
                agreed_schedule.product = product
            break
    else:
        for premium_schedule in target.invested_amounts:
            premium_schedule.product = None

@event.listens_for(FinancialAgreementPremiumSchedule.product, 'set')
def product_set(target, value, oldvalue, initiator):
    if target.valid_from_date is None:
        return
    if target.valid_thru_date is None:
        return
    if value is not None:
        for available_coverage in value.available_coverages:
            if available_coverage.from_date <= target.valid_from_date and available_coverage.thru_date >= target.valid_thru_date:
                for coverage in target.agreed_coverages:
                    coverage.coverage_for = available_coverage.with_coverage_levels[0]
