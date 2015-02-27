import datetime
import logging
import copy
import os
import itertools

import sqlalchemy.types
from sqlalchemy import sql, orm, schema

from camelot.core.orm import ( Entity, OneToMany, ManyToOne,
                               using_options, ColumnProperty )
from camelot.core.utils import ugettext
from camelot.model.authentication import end_of_times
from camelot.admin.action import CallMethod, list_filter
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.view import utils
from camelot.view.art import ColorScheme
from camelot.core.utils import ugettext_lazy as _
from camelot.model.type_and_status import Status
import camelot.types

from vfinance.model.bank.dossier import DossierMixin
from vfinance.model.bank.dual_person import CommercialRelation, DualPerson
from vfinance.model.bank.rechtspersoon import Rechtspersoon
from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon
from vfinance.model.bank.entry import Entry
from vfinance.model.financial.summary.agreement_summary import FinancialAgreementSummary
from vfinance.model.financial.summary.agreement_verification import FinancialAgreementVerificationForm
from .package import FinancialPackage
from ..bank import agreement as bank_agreement, validation
from ..bank.statusmixin import ( BankStatusMixin,
                                 status_form_actions,
                                 BankStatusAdmin,
                                 BankRelatedStatusAdmin )
from ..bank.admin import CodeValidator
from ..bank.constants import Mail

from vfinance.connector.json_ import JsonExportAction

import decimal

from constants import  ( agreement_statuses, agreement_roles,
                         functional_settings, period_types_by_granularity,
                         functional_setting_groups, item_clause_types,
                         exclusiveness_by_functional_setting_group,
                         commission_types )

LOGGER = logging.getLogger('vfinance.model.financial.agreement')


class CommercialRelationAdmin(CommercialRelation.Admin):
    list_display = ['type', 'rechtspersoon', 'from_rechtspersoon', 'number']

class FinancialAgreementAccountMixin(DossierMixin):
    """Shared functionality between a FinancialAgreement and a FinancialAccount"""

    def has_insured_party( self ):
        """Return true if current agreement includes an insured party."""
        for role in self.roles:
            if role.described_by == 'insured_party':
                return True
        return False

    def get_insured_party_smoking_status( self ):
        """Return whether insured party smokes or not."""
        for role in self.roles:
            if role.described_by == 'insured_party':
                return role.natuurlijke_persoon.rookgedrag
        raise Exception(_('There is no insured party.'))

    def get_applied_functional_settings_at( self,
                                            application_date,
                                            functional_setting_group ):
        """
        Return a list with the appliceable functional settings within a group
        """
        from constants import group_by_functional_setting
        if hasattr( self, 'applied_functional_settings' ):
            all_functional_settings = [fs for fs in self.applied_functional_settings if fs.from_date <= application_date and fs.thru_date >= application_date]
        elif hasattr( self, 'agreed_functional_settings' ):
            all_functional_settings = self.agreed_functional_settings
        else:
            raise Exception( 'Object of type %s has no functional settings'%( self.__class__.__name__ ) )
        functional_settings = []
        #
        # first look at the account or agreement level
        #
        for functional_setting in all_functional_settings:
            if group_by_functional_setting[functional_setting.described_by] == functional_setting_group:
                functional_settings.append( functional_setting )
        #
        # if nothing there, look at the package level
        #
        if len( functional_settings ) == 0:
            if self.package is not None:
                for functional_setting in self.package.available_functional_settings:
                    if functional_setting.from_date <= application_date and functional_setting.thru_date >= application_date and functional_setting.availability in ('standard', 'required'):
                        if group_by_functional_setting[functional_setting.described_by] == functional_setting_group:
                            functional_settings.append( functional_setting )
        return functional_settings

    def get_language_at(self, application_date, described_by=None):
        """This method currently returns the language of the role with lowest rank and id.
        In time it might be more correct to use a 'prefered language' field at agreement level.
        """
        roles = self.get_roles_at(application_date, described_by)
        try:
            return roles[0].taal
        except KeyError:
            LOGGER.warning('No roles defined while getting language')
            return None

def available_agents(agreement):
    agents = [(None, '')]
    if agreement.broker_relation and agreement.broker_relation.rechtspersoon:
        for agent_relation in agreement.broker_relation.rechtspersoon.commercial_relations_to:
            if agent_relation.type == 'agent':
                persoon = agent_relation.natuurlijke_persoon or agent_relation.rechtspersoon
                agents.append( (persoon, unicode(persoon)) )
    return agents

class FinancialAgreementJsonExport( JsonExportAction ):
    deepdict = {'status':{},
                'roles':{
                    'natuurlijke_persoon':{},
                    'rechtspersoon':{},
                },
                'invested_amounts':{
                    'commission_distribution':{},
                    'fund_distribution':{},
                    'agreed_features':{},
                    'agreed_coverages':{
                        'coverage_amortization':{},
                    }
                },
                'assets':{
                    'asset_usage':{},
                },
                'broker_agent':{},
                'agreed_items':{},
                'agreed_functional_settings':{},
                'direct_debit_mandates':{}
               }
    exclude = ['id']

class FinancialAgreement( bank_agreement.AbstractAgreement, FinancialAgreementAccountMixin, BankStatusMixin ):
    """One or more persons agree to subscribe for a FinancialPackage"""
    using_options(tablename='financial_agreement', order_by=['id'])
    agreement_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    from_date = schema.Column( sqlalchemy.types.Date(), nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    #code = schema.Column(camelot.types.Code(parts=code_parts, separator=u'/'), nullable=False, index=True)
    code = schema.Column(sqlalchemy.types.Unicode(15), nullable=False, index=True)
    text = schema.Column( camelot.types.RichText )
    status = Status( enumeration=agreement_statuses )
    roles = OneToMany('FinancialAgreementRole', cascade='all, delete, delete-orphan' )
    assets = OneToMany('FinancialAgreementAssetUsage', cascade='all, delete, delete-orphan' )
    #broker_relation = ManyToOne('CommercialRelation', required=False, ondelete = 'restrict', onupdate = 'cascade', backref='managed_financial_agreements')
    #broker_agent = ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon')
    package_id = schema.Column(sqlalchemy.types.Integer,
                               schema.ForeignKey(FinancialPackage.id,
                                                 ondelete='restrict',
                                                 onupdate='cascade'),
                               index=True,
                               nullable=False)
    package = orm.relationship(FinancialPackage)
    document = schema.Column(camelot.types.File(upload_to=os.path.join('product.financial_agreements', 'document')))
    account = ManyToOne('vfinance.model.financial.account.FinancialAccount', required=False, ondelete='restrict', onupdate='cascade')
    agreed_items = OneToMany('FinancialAgreementItem', cascade='all, delete, delete-orphan')
    agreed_functional_settings = OneToMany('FinancialAgreementFunctionalSettingAgreement', cascade='all, delete, delete-orphan')
    documents = OneToMany('vfinance.model.financial.document.FinancialDocument')
    direct_debit_mandates = OneToMany('vfinance.model.bank.direct_debit.DirectDebitMandate')
    #tasks = ManyToMany( 'Task',
    #                    tablename='financial_agreement_task',
    #                    remote_colname='task_id',
    #                    local_colname='financial_agreement_id',
    #                    backref='financial_agreements')

    def broker(cls):
        from vfinance.model.bank.dual_person import name_of_dual_person
        from sqlalchemy.orm import aliased
        CR = aliased(CommercialRelation)
        return sql.select( [name_of_dual_person(CR)],
                           CR.id == cls.broker_relation_id,
                           from_obj=CR.table ).limit(1)

    def get_note_color(self):
        return ColorScheme.NOTIFICATION

    broker = ColumnProperty( broker, deferred = True )

    def master_broker(cls):
        from sqlalchemy.orm import aliased
        CR = aliased(CommercialRelation)
        return sql.select( [Rechtspersoon.name],
                           sql.and_(Rechtspersoon.id==CR.table.c.to_rechtspersoon,
                                    CR.table.c.id == cls.broker_relation_id),
                           from_obj=CR.table ).limit(1)

    master_broker = ColumnProperty( master_broker, deferred = True )

    @classmethod
    def next_agreement_code(cls, session):
        """
        Create a new agreement code based on the last agreement code
        found in the database.
        """
        last_code_slect = sql.select([FinancialAgreement.code],
                                     order_by = FinancialAgreement.code.desc(),
                                     limit=1
                                     )
        last_code = session.execute(last_code_slect).scalar()
        base, check = validation.split_ogm(last_code)
        if base is None:
            base = 0
        next_base = base+1
        next_base_str = '%010i'%next_base
        next_check = validation.checksum(next_base)
        return '/'.join([next_base_str[0:3], next_base_str[3:7], next_base_str[7:]+'%02i'%next_check])

    @staticmethod
    def premium_sum_query(columns):
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        return sql.select( [sql.func.coalesce( sql.func.sum(FinancialAgreementPremiumSchedule.amount), 0 )],
                           columns.id == FinancialAgreementPremiumSchedule.financial_agreement_id )

    def has_document(self):
        return self.document != None

    has_document = ColumnProperty( has_document, deferred = True )

    def invested_amount(self):
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        return FinancialAgreement.premium_sum_query( self ).where(FinancialAgreementPremiumSchedule.direct_debit==False)

    invested_amount = ColumnProperty( invested_amount, deferred = True )

    def has_account_schedules(self):
        """
        `True` if there are Financial Account Premium Schedules related to this
        agreement.  This is used to quickly filter out agreements for which nothing
        has happened yet.
        """
        from vfinance.model.financial.premium import (FinancialAgreementPremiumSchedule,
                                                      FinancialAccountPremiumSchedule)
        return sql.select([sql.func.coalesce(sql.func.count(FinancialAccountPremiumSchedule.id), 0) > 0],
                          sql.and_(self.id == FinancialAgreementPremiumSchedule.financial_agreement_id,
                                   FinancialAgreementPremiumSchedule.id==FinancialAccountPremiumSchedule.agreed_schedule_id
                                   ))

    has_account_schedules = ColumnProperty( has_account_schedules, deferred = True )

    @property
    def amount_due(self):
        return sum(a.amount for a in self.invested_amounts if a.direct_debit==False and a.amount) - self.amount_on_hold


    @property
    def fulfillment_date(self):
        """The agreement fulfimment date or T4"""

        if not len( self.invested_amounts ):
            return None

        if not self.is_fulfilled:
            return None

        start_conditions = self.get_applied_functional_settings_at( self.agreement_date,
                                                                    'start_condition' )
        if 'start_at_from_date' in [c.described_by for c in start_conditions] and self.current_status == 'verified':
            return self.from_date

        running_sum = 0
        dates = [self.from_date] + [ps.product.from_date for ps in self.invested_amounts]
        for entry in self.related_entries:
            if entry.amount < 0:
                running_sum = running_sum - entry.amount
                dates.append( entry.doc_date )
                if running_sum >= self.invested_amount:
                    break

        return max(dates)

    @property
    def related_entries(self):
        from vfinance.model.financial.visitor.abstract import AbstractVisitor
        visitor = AbstractVisitor()
        related_entries = []
        for faps in self.invested_amounts:
            if faps.product and self.code and self.agreement_date:
                pending_premiums_account = faps.product.get_account_at( 'pending_premiums', self.agreement_date )
                related_entries.extend( Entry.query.filter( sql.and_(Entry.remark.like( u'%' + self.code + u'%' ),
                                                                     Entry.account == ''.join(pending_premiums_account) ) ).all() )
                for direct_debit_mandate in self.direct_debit_mandates:
                    related_entries.extend( Entry.query.filter( sql.and_(Entry.remark.like( u'%' + direct_debit_mandate.iban.replace('-','') + u'%' ),
                                                                         Entry.account == ''.join(pending_premiums_account) ) ).all() )
                #
                # premiums might have been attributed to customer account
                #
                for agreed_premium_schedule in self.invested_amounts:
                    for account_premium_schedule in agreed_premium_schedule.fulfilled_by:
                        if account_premium_schedule.id is not None:
                            for entry_data in visitor.get_entries( account_premium_schedule,
                                                                   fulfillment_type = 'premium_attribution' ):
                                related_entries.append( Entry.get( entry_data.id ) )
        related_entries = list( set( related_entries ) )
        related_entries.sort( key=lambda e:e.doc_date)
        return related_entries

    @property
    def amount_on_hold(self):
        return sum( decimal.Decimal('%.2f'%entry.open_amount)*-1 for entry in self.related_entries if entry.ticked==False)

    @property
    def note(self):
        """A string describing what should be done next to complete the agreement, None if the
        agreement is complete"""
        for message in self.get_messages():
            return message

    def get_messages(self, proposal_mode=False):
        from vfinance.model.bank.natuurlijke_persoon import analyze_nationaal_nummer
        if not self.package:
            yield ugettext('Select a package')
        if not proposal_mode:
            # the code is a required field, so don't check for it on the note,
            # to be able to fill in the agreement while not having a code yet
            for _agreement in self.query.filter(sql.and_(FinancialAgreement.code==self.code, FinancialAgreement.id!=self.id)).all():
                yield ugettext('Another agreement with the same code exists')
            for role in self.roles:
                natuurlijke_persoon = role.natuurlijke_persoon
                if role.natuurlijke_persoon:
                    if not natuurlijke_persoon.nationaliteit:
                        yield ugettext(u'{} {} {} has no country code'.format(role.described_by, role.rank, unicode(role.natuurlijke_persoon)))
                    correct, _birthdate, _sex = analyze_nationaal_nummer( natuurlijke_persoon )
                    if not correct:
                        yield ugettext(u'%s %d %s has an incorrect national number')%(role.described_by, role.rank, unicode(role.natuurlijke_persoon))
            #
            # Verify if this broker is allowd to distributed the package
            #
            if self.broker_relation and not self.broker_relation in self.get_available_broker_relations():
                yield ugettext('Broker is not allowed to distribute this package')
        if not self.agreement_date:
            yield ugettext('Enter the agreement date')
        if not self.from_date:
            yield ugettext('Enter the date from which the agreement starts')
        # Check if a broker is required for the selected FinancialPackage
        if self.get_functional_setting_description_at(self.agreement_date,  'broker_definition') == 'broker_relation_required':
            if not self.broker:
                yield ugettext('A broker is required for the specified package')
        if not len(self.roles):
            yield ugettext('Specify the persons and their roles')
        # for 'required' insurances (e.g. credit insurance)
        # 1. collect required insurance coverage levels (including multiplicity)
        required_coverages = {}
        # 2. collect agreed insurance coverage levels (including multiplicity)
        agreed_coverages = {}
        for premium in self.invested_amounts:
            if premium.payment_duration != None:
                if premium.payment_duration > premium.duration:
                    yield ugettext( 'Payment duration should be smaller than duration' )
                period_duration = period_types_by_granularity[premium.period_type]
                if period_duration and (premium.payment_duration % period_duration):
                    yield ugettext( 'Payment duration has to be a whole multiple of period type.' )
            if premium.product is not None:
                if premium.product not in self.package.get_available_products_at( self.agreement_date ):
                    yield ugettext( 'Product not allowed within this package' )
                for cov in premium.product.available_coverages:
                    if cov.availability == 'required' and cov.from_date <= self.agreement_date and cov.thru_date >= self.agreement_date:
                        for level in cov.with_coverage_levels:
                            required_coverages[level.id] = required_coverages.get(level.id, 0) + 1
                if self.from_date < premium.product.from_date:
                    yield ugettext('Agreement cannot start before product')
            else:
                if not premium.product:
                    yield ugettext('Select a product')
            for cov in premium.agreed_coverages:
                #
                # Verify duration of coverage
                #
                if premium.valid_from_date and premium.valid_thru_date:
                    if cov.from_date:
                        if cov.from_date < premium.valid_from_date or cov.from_date > premium.valid_thru_date:
                            yield ugettext('Coverage should start between the from and thru dates of the premium schedule')
                    if cov.thru_date:
                        if cov.thru_date < premium.valid_from_date or cov.thru_date > premium.valid_thru_date:
                            yield ugettext('Coverage should end between the from and thru dates of the premium schedule')
                if cov.coverage_for:
                    agreed_coverages[cov.coverage_for.id] = agreed_coverages.get(cov.coverage_for.id, 0) + 1
            minimum_insured_party_age = premium.get_applied_feature_at( self.from_date,
                                                                        self.from_date,
                                                                        premium.amount,
                                                                        'minimum_insured_party_age',
                                                                        default = 0 ).value
            maximum_insured_party_age = premium.get_applied_feature_at( self.from_date,
                                                                        self.from_date,
                                                                        premium.amount,
                                                                        'maximum_insured_party_age',
                                                                        default = None ).value
            minimum_subscriber_age = premium.get_applied_feature_at(self.from_date,
                                                                    self.from_date,
                                                                    premium.amount,
                                                                    'from_subscriber_age',
                                                                    default=None).value
            maximum_subscriber_age = premium.get_applied_feature_at(self.from_date,
                                                                    self.from_date,
                                                                    premium.amount,
                                                                    'thru_subscriber_age',
                                                                    default=None).value
            for role in self.roles:
                if role.described_by == 'insured_party' and role.natuurlijke_persoon!=None:
                    insured_party_from_age = role.natuurlijke_persoon.age_at( self.from_date )
                    insured_party_thru_age = role.natuurlijke_persoon.age_at( premium.valid_thru_date )
                    if insured_party_from_age < minimum_insured_party_age:
                        yield ugettext('Insured party %s years old, minimum age of %s is required')%( insured_party_from_age, minimum_insured_party_age )
                    if maximum_insured_party_age and insured_party_thru_age > maximum_insured_party_age:
                        yield ugettext('Insured party will be %s years old on the the premium-schedule thru_date, maximum age of %s is required')%( insured_party_thru_age, maximum_insured_party_age )
                if role.described_by == 'subscriber' and role.natuurlijke_persoon != None:
                    subscriber_from_age = role.natuurlijke_persoon.age_at(self.from_date)
                    subscriber_thru_age = role.natuurlijke_persoon.age_at(premium.valid_thru_date)
                    if minimum_subscriber_age and subscriber_from_age < minimum_subscriber_age:
                        yield ugettext('Subscriber {0} years old, minimum age of {1} is required').format(subscriber_from_age, minimum_subscriber_age)
                    if maximum_subscriber_age and subscriber_thru_age > maximum_subscriber_age:
                        yield ugettext('Subscriber will be {0} years old on the premium-schedule thru_date, maximum age of {1} is required').format(subscriber_thru_age, maximum_subscriber_age)

            for i in range(1, 6):
                minimum_premium_rate = premium.get_applied_feature_at(self.from_date,
                                                                      self.from_date,
                                                                      premium.amount,
                                                                      'from_premium_rate_{}'.format(i),
                                                                      default=None).value
                maximum_premium_rate = premium.get_applied_feature_at(self.from_date,
                                                                      self.from_date,
                                                                      premium.amount,
                                                                      'thru_premium_rate_{}'.format(i),
                                                                      default=None).value

                premium_rate = premium.get_applied_feature_at(self.from_date,
                                                              self.from_date,
                                                              premium.amount,
                                                              'premium_rate_{}'.format(i),
                                                              default=None).value
                if premium_rate is not None:
                    if minimum_premium_rate is not None and premium_rate < minimum_premium_rate:
                        yield ugettext('Premium rate {} cannot be less than {}').format(i, minimum_premium_rate)
                    if maximum_premium_rate is not None and premium_rate > maximum_premium_rate:
                        yield ugettext('Premium rate {} cannot be more than {}').format(i, maximum_premium_rate)

            for i in range(1, 5):
                minimum_premium_fee = premium.get_applied_feature_at(self.from_date,
                                                                     self.from_date,
                                                                     premium.amount,
                                                                     'from_premium_fee_{}'.format(i),
                                                                     default=None).value
                maximum_premium_fee = premium.get_applied_feature_at(self.from_date,
                                                                     self.from_date,
                                                                     premium.amount,
                                                                     'thru_premium_fee_{}'.format(i),
                                                                     default=None).value

                premium_fee = premium.get_applied_feature_at(self.from_date,
                                                             self.from_date,
                                                             premium.amount,
                                                             'premium_fee_{}'.format(i),
                                                             default=None).value

                if premium_fee is not None:
                    if minimum_premium_fee is not None and premium_fee < minimum_premium_fee:
                        yield ugettext('Premium fee {} cannot be less than {}').format(i, minimum_premium_fee)
                    if maximum_premium_fee is not None and premium_fee > maximum_premium_fee:
                        yield ugettext('Premium fee {} cannot be higher than  {}').format(i, maximum_premium_fee)


            # Check duration of premium_schedule
            minimum_duration_premium_schedule = premium.get_applied_feature_at(self.from_date,
                                                                               self.from_date,
                                                                               premium.amount,
                                                                               'premium_schedule_from_duration',
                                                                               default=None).value

            maximum_duration_premium_schedule = premium.get_applied_feature_at(self.from_date,
                                                                               self.from_date,
                                                                               premium.amount,
                                                                               'premium_schedule_thru_duration',
                                                                               default=None).value

            if premium.duration is not None:
                if minimum_duration_premium_schedule is not None and premium.duration < minimum_duration_premium_schedule:
                    yield ugettext('Duration of the premium schedule can\'t be less than {}').format(minimum_duration_premium_schedule)

                if maximum_duration_premium_schedule is not None and premium.duration > maximum_duration_premium_schedule:
                    yield ugettext('Duration of the premium schedule can\'t be more than {}').format(maximum_duration_premium_schedule)

            # Check if agreement_date within range
            min_difference_agreement_from_date = int(premium.get_applied_feature_at(self.from_date,
                                                                                    self.from_date,
                                                                                    premium.amount,
                                                                                    'min_difference_agreement_from_date',
                                                                                    default=-150000).value)
            max_difference_agreement_from_date = int(premium.get_applied_feature_at(self.from_date,
                                                                                    self.from_date,
                                                                                    premium.amount,
                                                                                    'max_difference_agreement_from_date',
                                                                                    default=150000).value)

            delta_from_agreement_date = self.from_date - self.agreement_date

            if not min_difference_agreement_from_date <= delta_from_agreement_date.days <= max_difference_agreement_from_date:
                yield ugettext('From date should fall between {} and {}'.format(self.agreement_date + datetime.timedelta(min_difference_agreement_from_date),
                                                                                self.agreement_date + datetime.timedelta(max_difference_agreement_from_date)))


        # check if all required coverages are also agreed, and with correct multiplicity
        for key in required_coverages.iterkeys():
            agreed_multiplicity = agreed_coverages.get(key, 0)
            if agreed_multiplicity < required_coverages[key]:
                if (required_coverages[key] - agreed_multiplicity) == 1:
                    print 'agreed coverages', agreed_coverages
                    yield ugettext('Specify premium with required insurance: ') + str(key)
                else:
                    yield ugettext('Specify premium with required insurance: ') + str(key) + ' (' + str(required_coverages[key] - agreed_multiplicity) \
                                                                    + ugettext(' times)')
        # ... end required insurance part
        # for credit insurance
        if self.has_credit_insurance():
            for premium in self.invested_amounts:
                if premium.has_credit_insurance():
                    for agreed_coverage in premium.agreed_coverages:
                        if (agreed_coverage.has_credit_insurance()) and (agreed_coverage.coverage_for.type not in ('fixed_amount', 'decreasing_amount')):
                            if not agreed_coverage.loan_defined:
                                yield ugettext('Please add covered loan(s) to credit insurance(s) in premiums.')
        # ... end credit insurance part
        # for any insurance: require that all roles are present
        insurance = False
        for premium in self.invested_amounts:
            if premium.agreed_coverages:
                insurance = True
        # ... end any insurance part
        # for credit insurance (again)
        if not len(self.invested_amounts):
            yield ugettext('Specify the premiums')
        if self.has_credit_insurance():
            for premium in self.invested_amounts:
                if premium.has_credit_insurance():
                    for role in self.roles:
                        if role.described_by == 'insured_party':
                            if not (role.geboortedatum and role.gender):
                                yield ugettext('Birthdate and gender of the insured party are needed to calculate the insurance premiums')
                    if not premium.amount > 1:  # for now, 1 is the default value
                        yield ugettext('Please calculate credit insurance premiums.')
        if not proposal_mode:
            if insurance:
                # in proposal mode, there is not necessary a benficiary yet
                if not self.has_all_insurance_roles():
                    yield ugettext('Please specify subscriber(s), one or more beneficiaries and exactly one insured party for the insurance(s)')
            if not len(self.direct_debit_mandates):
                 for premium in self.invested_amounts:
                     if premium.direct_debit:
                         yield ugettext('Enter the direct debit mandates')
            if self.package is not None:
                if self.package.available_functional_settings:
                    for functional_setting_group in functional_setting_groups:
                        selectable = list( self.package.get_selectable_functional_settings(self.agreement_date, functional_setting_group) )
                        exclusive = exclusiveness_by_functional_setting_group[functional_setting_group]
                        selected = [functional_setting for functional_setting in self.agreed_functional_settings if functional_setting.group == functional_setting_group]
                        if selectable and not selected:
                            yield ugettext('Select one of the settings : %s')%(', '.join([fs.get_verbose_name() for fs in selectable]))
                        if len(selected) > 1 and exclusive:
                            yield ugettext('Too many functional settings selected')
        #
        # Verify if the commissions and funds have been distributed correctly
        #
        for premium in self.invested_amounts:
            if premium.product is not None:
                for product_feature in premium.product.available_with:
                    if product_feature.overrule_required:
                        if product_feature.premium_period_type==None or product_feature.premium_period_type==premium.period_type:
                            found = False
                            for agreed_feature in premium.agreed_features:
                                if agreed_feature.described_by == product_feature.described_by:
                                    found = True
                                    break
                            if not found:
                                yield ugettext('The product feature %s should be overruled in this agreement, <br/>'%product_feature.described_by + \
                                                'press the <b>Default Features</b> button to use the product defaults')
                if premium.product.unit_linked:
                    if not len(premium.fund_distribution):
                        yield ugettext('Select the funds to invest in, press the <b>Default Funds</b> <br/>' + \
                                        'button to use the product defaults')
                    if premium.funds_target_percentage_total!=100:
                        yield ugettext('Select a total of 100% target funds')
                else:
                    if len(premium.fund_distribution):
                        yield ugettext('Fund selection not possible for this product')

            if not proposal_mode:
                for commission_type in commission_types:
                    distribution_sum = sum( ((commission.distribution or 0) for commission in premium.commission_distribution if commission.described_by==commission_type[1]), 0 )
                    feature_value = premium.get_applied_feature_at( premium.valid_from_date,
                                                                    premium.valid_from_date,
                                                                    premium.amount,
                                                                    commission_type[1],
                                                                    default=0 ).value
                    if feature_value != distribution_sum:
                        yield ugettext( 'Incorrect distribution of the %s of %s for the %s premium : %s distributed' )%( commission_type[1],
                                                                                                                          feature_value,
                                                                                                                          premium.period_type,
                                                                                                                          distribution_sum )
                # Verifiy if the needed broker and agent are completed to create a commission booking
                for commission in premium.commission_distribution:
                    if commission.distribution != 0:
                        if commission.recipient in ('broker', 'master_broker'):
                            if self.broker_relation is None:
                                yield ugettext('Select the broker relation')
                        if commission.recipient in ('agent'):
                            if self.broker_agent is None:
                                yield ugettext('Select the broker agent')

        for item in self.agreed_items:
            if not item.use_custom_clause:
                item.custom_clause = None
                if not item.associated_clause:
                    yield ugettext('No associated clause specified')
            if item.use_custom_clause:
                if set(utils.text_from_richtext(item.custom_clause)) == set(['']):
                    yield ugettext('No custom clause specified')

    def package_name( self ):
        from vfinance.model.financial.package import FinancialPackage

        FP = orm.aliased(FinancialPackage)

        return sql.select( [FP.name],
                           whereclause = FP.id == self.package_id )

    package_name = ColumnProperty( package_name, deferred = True )

    def get_available_broker_relations(self):
        relations = []
        if self.package:
            for available_broker in self.package.available_brokers:
                if available_broker.from_date <= self.agreement_date and available_broker.thru_date >= self.agreement_date:
                    relations.append( available_broker.broker_relation )
        return relations

    def get_future_value_at(self, future_value_date):
        """The assumed future value, when everything goes along plan the plan known
        until future_value_date"""
        return sum( premium.get_future_value_at( future_value_date ) for premium in self.invested_amounts )

    def is_fulfilled(self):
        """Indicates if all conditions are met to create an account for this agreement
        :return: True or False
        """
        start_conditions = self.get_applied_functional_settings_at( self.agreement_date,
                                                                    'start_condition' )
        if 'start_at_from_date' in [c.described_by for c in start_conditions] and self.current_status == 'verified':
            return True
        return self.current_status=='verified' and self.amount_due<=0

    def use_default_features(self):
        for premium in self.invested_amounts:
            premium.use_default_features()

    def use_default_funds(self):
        """Take the default funds from the product definition and use them to
        fill the agreement"""
        from fund import FinancialAgreementFundDistribution
        if not self.current_status in ['draft']:
            raise Exception('Agreement should be in draft status to assign funds')
        for premium in self.invested_amounts:
            if premium.product and premium.product.unit_linked:
                agreed_funds_to_remove = list(premium.fund_distribution)
                for af in agreed_funds_to_remove:
                    premium.fund_distribution.remove( af )
                for pf in premium.product.available_funds:
                    premium.fund_distribution.append( FinancialAgreementFundDistribution(fund=pf.fund,
                                                                                         target_percentage=pf.default_target_percentage) )

    def is_verifiable( self ):
        if self.has_credit_insurance():
            self.check_credit_insurance_premiums()
        return True

    def is_complete( self ):
        if self.has_credit_insurance():
            self.check_credit_insurance_premiums()
        return super( FinancialAgreement, self ).is_complete()

    def subscriber_1(self):
        from vfinance.model.bank.dual_person import name_of_dual_person
        from sqlalchemy.orm import aliased

        FAR = aliased( FinancialAgreementRole )

        return sql.select( [name_of_dual_person(FAR)],
                           sql.and_(FAR.described_by=='subscriber',
                                    FAR.financial_agreement_id==self.id) ).order_by( FAR.rank, FAR.id ).limit(1)

    subscriber_1 = ColumnProperty( subscriber_1, deferred = True )

    def subscriber_2(self):
        from vfinance.model.bank.dual_person import name_of_dual_person
        from sqlalchemy.orm import aliased

        FAR = aliased( FinancialAgreementRole )

        return sql.select( [name_of_dual_person(FAR)],
                           sql.and_(FAR.described_by=='subscriber',
                                    FAR.financial_agreement_id==self.id) ).order_by( FAR.rank, FAR.id ).offset(1).limit(1)

    subscriber_2 = ColumnProperty( subscriber_2, deferred = True )

    def check_credit_insurance_premiums(self):
        for premium in self.invested_amounts:
            if premium.has_credit_insurance():
                premium.check_credit_insurance_premium()

    def has_credit_insurance(self):
        for premium in self.invested_amounts:
            for cov in premium.agreed_coverages:
                if cov.has_credit_insurance():
                    return True
        return False

    # check if current agreement includes all roles needed for an insurance, and exactly one insured party
    def has_all_insurance_roles(self):
        subscriber     = False
        beneficiary   = False
        insured_party = 0
        for role in self.roles:
            if role.described_by == 'subscriber':
                subscriber = True
            if role.described_by in ('beneficiary', 'pledgee'):
                beneficiary = True
            if role.described_by == 'insured_party':
                insured_party += 1
        #
        # beneficiary might be a clause
        #
        if len(self.agreed_items):
            beneficiary = True
        return subscriber and beneficiary and insured_party

    def __unicode__(self):
        if self.package and self.subscriber_1:
            return u'%s : %s'%(self.package.name, self.subscriber_1)
        return u''

    class Admin(BankStatusAdmin):

        verbose_name = _('Financial Agreement')
        list_display = ['id', 'code', 'package_name', 'agreement_date', 'subscriber_1', 'subscriber_2', 'current_status', 'invested_amount', 'broker', 'master_broker', 'account_id']
        form_size = (1050,700)
        form_state = 'maximized'
        copy_exclude = ['id', 'state', 'code', 'agreement_date', 'from_date', 'document', 'origin', 'account', 'account_id', 'package', 'package_id']
        copy_deep = {'roles':{},
                     'agreed_items':{},
                     'agreed_functional_settings':{},
                     'invested_amounts':{
                         'commission_distribution':{},
                         'fund_distribution':{},
                         'agreed_features':{},
                         'agreed_coverages':{
                             'coverage_amortization':{},
                         },
                     },
                     'direct_debit_mandates':{}}
        form_display = forms.Form([forms.WidgetOnlyForm('note'),
                                   forms.TabForm([(_('Agreement'), forms.Form(['package',
                                                                               'code',
                                                                               'agreement_date',
                                                                               'from_date',
                                                                               'document',
                                                                               'broker_relation',
                                                                               'broker_agent',
                                                                               'current_status',
                                                                               'account',
                                                                               'roles',
                                                                               'agreed_items'], columns=2)),
                                                  (_('Premium'), ['invested_amounts', 'direct_debit_mandates', 'related_entries']),
                                                  (_('Settings'), ['agreed_functional_settings']),
                                                  (_('Assets'), ['assets']),
                                                  (_('Extra'), ['text', 'documents', 'origin']),
                                                  #(_('Tasks'), ['tasks']),
                                                  (_('Status history'), ['status',])])])
        form_actions = tuple(itertools.chain(
                                (CallMethod( _('Default Funds'),
                                    lambda obj:obj.use_default_funds(),
                                    enabled = lambda obj:(obj is not None) and obj.current_status in ['draft'] and obj.package!=None), ) ,
                                (status_form_actions),
                                (FinancialAgreementSummary(),
                                    FinancialAgreementJsonExport(),
                                    FinancialAgreementVerificationForm(), ))
                            )
        list_actions = status_form_actions
        list_filter = BankStatusAdmin.list_filter + [list_filter.ComboBoxFilter('package.name'),
                       list_filter.ComboBoxFilter('has_document'),
                       list_filter.ComboBoxFilter('has_account_schedules'),
                       ]
        list_search = ['subscriber_1', 'subscriber_2']
        field_attributes = {'id':{'editable':False},
                            'code':{'validator':CodeValidator(), 'tooltip':u'bvb. \'789/5345/88943\''},
                            'current_status':{'name':_('Current status'), 'editable':False},
                            'agreed_functional_settings':{'name':_('Agreed settings'), 'create_inline':True},
                            'amount_on_hold':{'delegate':delegates.CurrencyDelegate},
                            'described_by':{'name':_('Type')},
                            'origin':{'editable':False},
                            'document':{'remove_original':True},
                            'subscriber_1':{'minimal_column_width':20},
                            'subscriber_2':{'minimal_column_width':20},
                            'assets':{'create_inline':False},
                            'pending':{'editable':False, 'delegate':delegates.BoolDelegate},
                            'broker_agent' : {'choices': available_agents},
                            'roles':{'create_inline':False},
                            'agreed_coverages':{'create_inline':False},
                            'agreed_functional_settings':{'create_inline':False},
                            'status':{'editable':False},
                            'related_entries':{'python_type':list, 'delegate':delegates.One2ManyDelegate, 'target':Entry, 'editable':False},
                            'note':{'delegate':delegates.NoteDelegate},
                            'invested_amounts':{'create_inline':False},
                            'invested_amount':{'delegate':delegates.CurrencyDelegate},
                            'amount_due':{'delegate':delegates.CurrencyDelegate},
                            'funds_target_percentage_total':{'name':_('Total percentage'), 'delegate':delegates.FloatDelegate, 'editable':False},
                            'agreed_funds':{'name':_('Funds'), 'create_inline':True},
                            'future_value_chart':{'delegate':delegates.ChartDelegate},
                            }

        always_editable_fields = ['text']

        def get_mail(self, obj, previous_state, current_state):
            return Mail(from_='info@vfinance.com',
                        to='pieterjan.delaruelle@gmail.com',
                        subject='Status of agreement {} changed from {} to {}'.format(obj.code, previous_state, current_state),
                        body='')

        def get_subclass_tree(self):
            return []

    class AdminOnAccount(Admin):
        list_display = ['code', 'agreement_date', 'current_status', 'invested_amount']


class FunctionalSettingMixin(object):

    @property
    def group(self):
        """:return: the group of functional settings to which this functional setting belongs"""
        from constants import group_by_functional_setting
        return group_by_functional_setting[self.described_by]

    @property
    def custom_clause(self):
        """:return: True if this functional setting allows a custom clause, False if not"""
        from constants import custom_clause_by_functional_setting
        if self.described_by is not None:
            return custom_clause_by_functional_setting[self.described_by]

class FinancialAgreementFunctionalSettingAgreement(Entity, FunctionalSettingMixin):
    using_options(tablename='financial_agreement_functional_setting_agreement')
    agreed_on = ManyToOne('FinancialAgreement', required = True, ondelete = 'cascade', onupdate = 'cascade', enable_typechecks=False)
    described_by = schema.Column( camelot.types.Enumeration(functional_settings), nullable=False, default='exit_at_first_decease')
    clause = schema.Column(camelot.types.RichText())


    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Financial Agreement Setting')
        verbose_name_plural = _('Financial Agreement Settings')
        list_display = ['described_by', 'clause']
        field_attributes = {'described_by':{'name':_('Description')},
                            'clause':{'editable':lambda fs:fs.custom_clause}}

        def get_depending_objects(self, obj):
            if obj.agreed_on:
                yield obj.agreed_on

        def get_related_status_object(self, obj):
            return obj.agreed_on

def get_clauses_for_agreement_role(agreement_role):
    from package import FinancialRoleClause
    clauses = [(None, '')]
    if agreement_role.financial_agreement:
        for clause in FinancialRoleClause.query.filter_by(described_by=agreement_role.described_by,
                                                          available_for=agreement_role.financial_agreement.package).all():
            clauses.append( (clause, clause.name) )
    return clauses

class AbstractCustomClause(object):

    def _get_shown_clause(self):
        if self.use_custom_clause:
            return self.custom_clause
        if self.associated_clause:
            return self.associated_clause.clause

    def _set_shown_clause(self, new_clause):
        if self.use_custom_clause:
            self.custom_clause = new_clause

class AbstractRole( object ):

    @property
    def thru_date( self ):
        return end_of_times()

class RoleMock( AbstractRole ):

    def __init__( self, from_date, described_by ):
        self.id = id(self)
        self.from_date = from_date
        self.natuurlijke_persoon = None
        self.rechtspersoon = None
        self.surmortality = 0
        self.described_by = described_by
        self.rank = 1

    def to_agreement_role(self, financial_agreement ):
        agreement_role = FinancialAgreementRole( financial_agreement = financial_agreement )
        if self.natuurlijke_persoon:
            agreement_role.natuurlijke_persoon = self.natuurlijke_persoon.to_real()
        if self.rechtspersoon:
            agreement_role.rechtspersoon = self.rechtspersoon.to_real()
        agreement_role.surmortality = self.surmortality
        agreement_role.described_by = self.described_by
        return agreement_role

class FinancialAgreementRole(DualPerson, AbstractCustomClause, AbstractRole):
    using_options( tablename='financial_agreement_role' )
    __table_args__ = ( schema.CheckConstraint( 'natuurlijke_persoon is not null or rechtspersoon is not null',
                                               name='financial_agreement_role_persoon_fk'), )
    financial_agreement = ManyToOne('FinancialAgreement', required = True, ondelete = 'cascade', onupdate = 'cascade', enable_typechecks=False)
    described_by = schema.Column(camelot.types.Enumeration(agreement_roles), nullable=False, index=True, default='subscriber')
    natuurlijke_persoon = orm.relationship(NatuurlijkePersoon,
                                           backref = orm.backref('financial_agreements', passive_deletes = True) )
    rechtspersoon  =  orm.relationship(Rechtspersoon,
                                       backref = orm.backref('financial_agreements', passive_deletes = True) )
    rank = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=1)
    associated_clause = ManyToOne('FinancialRoleClause', required=False, ondelete='restrict', onupdate='cascade')
    use_custom_clause = schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    custom_clause = schema.Column( camelot.types.RichText() )
    shown_clause = property(AbstractCustomClause._get_shown_clause, AbstractCustomClause._set_shown_clause)
    surmortality = schema.Column(sqlalchemy.types.Numeric(precision=6, scale=2), nullable=True, default=0)

    @property
    def from_date( self ):
        if self.financial_agreement:
            return self.financial_agreement.from_date

    class Admin(DualPerson.Admin, BankRelatedStatusAdmin):
        verbose_name = _('Role within financial agreement')
        validator = DualPerson.Admin.validator
        list_display = DualPerson.Admin.list_display + ['described_by', 'rank', 'surmortality']
        form_display = forms.Form(list_display + ['associated_clause', 'use_custom_clause', 'shown_clause'])
        field_attributes = copy.copy(DualPerson.Admin.field_attributes)
        field_attributes.update({'described_by':{'name':_('Type')},
                                 'rank':{'choices':[(i,str(i)) for i in range(1,10)]},
                                 'associated_clause':{'choices':get_clauses_for_agreement_role, 'editable':lambda o:o.use_custom_clause!=True},
                                 'shown_clause':{'editable':lambda o:o.use_custom_clause==True,
                                                  'delegate':delegates.RichTextDelegate},
                                 'surmortality':{'suffix':'%', 'minimum':0,
                                                 'editable':lambda o: o.described_by == 'insured_party'}})

        def get_depending_objects(self, obj):
            if obj.financial_agreement:
                obj.financial_agreement.expire(['subscriber_1', 'subscriber_2'])
                yield obj.financial_agreement

        def get_related_status_object(self, o):
            return o.financial_agreement



def get_clauses_for_agreement_item(agreement_item):
    from package import FinancialItemClause
    clauses = [(None, '')]
    if agreement_item and agreement_item.financial_agreement:
        for clause in FinancialItemClause.query.filter_by(available_for=agreement_item.financial_agreement.package).all():
            clauses.append( (clause, clause.name) )
    return clauses

class FinancialAgreementItem(Entity, AbstractCustomClause):
    #__table_args__ = (schema.CheckConstraint("(associated_clause_id IS NULL AND use_custom_clause = 't' AND custom_clause IS NOT NULL) OR (associated_clause_id > 0 AND use_custom_clause = 'f')",
    #                                         name='check_agreement_associated_clause_or_custom_clause'),)
    using_options(tablename='financial_agreement_item')
    financial_agreement = ManyToOne('FinancialAgreement', required = True, ondelete = 'cascade', onupdate = 'cascade', enable_typechecks=False)
    rank = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=1)
    associated_clause = ManyToOne('FinancialItemClause', required=False, ondelete='restrict', onupdate='cascade')
    use_custom_clause = schema.Column(sqlalchemy.types.Boolean(), nullable=False, default=False)
    custom_clause = schema.Column( camelot.types.RichText() )
    shown_clause = property(AbstractCustomClause._get_shown_clause, AbstractCustomClause._set_shown_clause)
    described_by = schema.Column( camelot.types.Enumeration(item_clause_types), nullable=False, index=True, default='beneficiary' )

    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Item within financial agreement')
        list_display = ['rank', 'described_by', 'associated_clause', 'use_custom_clause']
        form_display = forms.Form(['rank', 'described_by', 'associated_clause', 'use_custom_clause', 'shown_clause'])
        field_attributes = copy.copy(DualPerson.Admin.field_attributes)
        field_attributes.update({'rank':{'choices':[(i,str(i)) for i in range(1,5)]},
                                 'described_by':{'name':_('Type')},
                                 'associated_clause':{'choices':get_clauses_for_agreement_item, 'editable':lambda o:o.use_custom_clause!=True},
                                 'shown_clause':{'editable':lambda o:o.use_custom_clause==True,
                                                 'delegate':delegates.RichTextDelegate}})

        def get_depending_objects(self, obj):
            if obj.financial_agreement:
                yield obj.financial_agreement

        def get_related_status_object(self, obj):
            return obj.financial_agreement

class FinancialAgreementAssetUsage(Entity):
    using_options(tablename='financial_agreement_asset_usage')
    financial_agreement = ManyToOne('FinancialAgreement', required = True, ondelete = 'cascade', onupdate = 'cascade', enable_typechecks=False)
    asset_usage = ManyToOne('vfinance.model.hypo.hypotheek.TeHypothekerenGoed', required = True, ondelete = 'restrict', onupdate = 'cascade')

    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Asset used within agreement')
        list_display = ['asset_usage']
        field_attributes = {'asset_usage':{'name':_('Asset'), 'minimal_column_width':45}}
        form_size = (400,100)

        def get_related_status_object(self, obj):
            return obj.financial_agreement
