from decimal import Decimal as D
import datetime
import logging
import itertools
from operator import attrgetter

LOGGER = logging.getLogger('vfinance.model.financial.account')

import sqlalchemy.types
from sqlalchemy import sql, orm, schema

from camelot.core.exception import UserException
from camelot.core.orm import ( Entity, Field, OneToMany, ManyToOne, 
                               using_options, ColumnProperty )
from camelot.model.authentication import end_of_times
# from camelot.admin.entity_admin import EntityAdmin
from camelot.admin.action import Action, list_filter
from camelot.admin.object_admin import ObjectAdmin
from camelot.view import forms, action_steps
from camelot.view.controls import delegates
from camelot.core.utils import ugettext_lazy as _
from camelot.model.type_and_status import Status
from camelot.core.qt import Qt
import camelot.types

from vfinance.model.bank.notification import Addressee, AddresseePerson
from vfinance.model.bank.dual_person import DualPerson, CommercialRelation
from vfinance.model.bank.entry import Entry
from vfinance.model.financial.agreement import (FinancialAgreementAccountMixin,
                                                FinancialAgreement,
                                                FunctionalSettingMixin)
from ..bank.dossier import DossierMixin, AbstractDossierBroker
from ..bank.statusmixin import BankStatusMixin, BankRelatedStatusAdmin
from vfinance.model.financial.summary.account_summary import FinancialAccountOverview
from vfinance.model.financial.notification.account_document import FinancialAccountDocument
from ..bank.statusmixin import BankStatusAdmin
from ..bank.account import status_form_actions

from constants import account_statuses, account_roles, functional_settings, item_clause_types    
   
account_editable = lambda account:account.current_status in ['draft', None]
     
class FinancialAccountChange( Action ):
    
    verbose_name = _('Change')
    
    def model_run( self, model_context ):
        
        class ChangeOptions( object ):
            
            def __init__( self ):
                self.change = None
                self.from_date = datetime.date.today()
                self.new_broker_relation = None
                
            class Admin( ObjectAdmin ):
                list_display = ['change', 'from_date', 'new_broker_relation' ]
                field_attributes = { 'change':{'editable':True,
                                               'delegate':delegates.ComboBoxDelegate,
                                               'choices': [(None,''), ('broker_relation','Broker Relation')]},
                                     'from_date':{'editable':True,
                                                  'delegate':delegates.DateDelegate},
                                     'new_broker_relation':{'delegate':delegates.Many2OneDelegate,
                                                            'target':CommercialRelation,
                                                            'editable':lambda o:o.change == 'broker_relation'},
                                     }
                                     
        options = ChangeOptions()
        yield action_steps.ChangeObject( options )
        thru_date = options.from_date - datetime.timedelta( days = 1 )
        with model_context.session.begin():
            for i, account in enumerate( model_context.get_selection() ):
                yield action_steps.UpdateProgress( i, model_context.selection_count, text = u'Change %s'%unicode( account ) )
                if options.change == 'broker_relation':
                    change_needed = True
                    unchanged_fields = { 'broker_agent':None }
                    current_broker = account.get_broker_at( options.from_date )
                    if current_broker:
                        for field_name in unchanged_fields.keys():
                            unchanged_fields[field_name] = getattr( current_broker, field_name )
                        if current_broker.broker_relation == options.new_broker_relation:
                            change_needed = False
                        if change_needed:
                            current_broker.thru_date = thru_date
                    if change_needed:
                        FinancialAccountBroker( financial_account = account,
                                                from_date = options.from_date,
                                                broker_relation = options.new_broker_relation,
                                                **unchanged_fields )
            yield action_steps.UpdateProgress( text = 'Saving changes' )
            yield action_steps.FlushSession( model_context.session )
            
            
class FinancialAccountAdmin(BankStatusAdmin):
    verbose_name = _('Financial Account')
    verbose_name_plural = _('Financial Accounts')
    list_display = ['id', 'package_name', 'subscriber_1', 'subscriber_2', 'account_suffix', 'broker', 'master_broker']
    list_filter = BankStatusAdmin.list_filter + [list_filter.ComboBoxFilter('package_name')]
    list_search = ['premium_schedules.account_number', 'id', 'subscriber_1', 'subscriber_2']
    search_all_fields = False
    form_state = 'maximized'
    disallow_delete = True
    
    form_display = forms.TabForm([(_('Account'), forms.Form(['package', 'current_status', 'roles', 'premium_schedules', 'text'], columns=2)),
                                  (_('Items'), ['items']),
                                  (_('Brokers'), ['brokers']),
                                  (_('Assets'), ['assets']),
                                  (_('Invoicing'), ['direct_debit_mandates']),
                                  (_('Settings'), ['applied_functional_settings']),
                                  #(_('Entries'), ['related_entries',]), # leave value of form, since calculating it right will take too much time 'value']),
                                  (_('Documents and Notifications'), ['notifications', 'documents']),
                                  (_('Agreements'), ['agreements']),
                                  (_('Transactions'), ['transactions']),
                                  #(_('Tasks'), ['tasks']),
                                  (_('Status'), ['status']),
                                  ])
    field_attributes = {'product':{'editable':account_editable},
                        'id':{'editable':False},
                        'subscriber_1':{'minimal_column_width':20},
                        'subscriber_2':{'minimal_column_width':20},
                        'premium_schedules':{'editable':True},
                        'current_status':{'name':_('Current status'), 'editable':False},
                        'related_entries':{'python_type':list, 'delegate':delegates.One2ManyDelegate, 'target':Entry, 'editable':False},
                        'agreements':{'admin':FinancialAgreement.AdminOnAccount},
                        }

    always_editable_fields = ['text']

    form_actions = list(itertools.chain((FinancialAccountOverview(),
                                        FinancialAccountDocument(),
                                        FinancialAccountChange()),
                                        (status_form_actions),
                                        # Commented out code replaced by
                                        # status_form_actions like FinancialAgreement
                                        #CallMethod( _('Close'),
                                        #            lambda obj:obj.button_closed(),
                                        #            enabled = lambda obj:(obj is not None) and obj.current_status in ['active', 'delayed']),
                                        #CallMethod( _('Delay'),
                                        #            lambda obj:obj.button_delayed(),
                                        #            enabled = lambda obj:(obj is not None) and obj.current_status in ['active']),
                                        #CallMethod( _('Activate'),
                                        #            lambda obj:obj.button_active(),
                                        #            enabled = lambda obj:(obj is not None) and obj.current_status in ['delayed']),
                                        #(ForceStatus(),)
                                        ))
                    
    list_actions = [FinancialAccountChange()]
    
    def get_search_identifiers(self, obj):
        search_identifiers = super(FinancialAccountAdmin, self).get_search_identifiers(obj)
        
        search_identifiers[Qt.DisplayRole] = u'%s %s' % (self.primary_key(obj), unicode(obj))
        
        return search_identifiers
    
    
class FinancialAccount(Entity, BankStatusMixin, FinancialAgreementAccountMixin, DossierMixin):
    using_options( tablename='financial_account' )
    
    id = schema.Column( sqlalchemy.types.Integer(), primary_key = True )
    package = ManyToOne('FinancialPackage', required=True, ondelete = 'restrict', onupdate = 'cascade')
    status = Status( enumeration = account_statuses )
    roles = OneToMany('FinancialAccountRole', cascade='all, delete, delete-orphan' )
    items = OneToMany('FinancialAccountItem', cascade='all, delete, delete-orphan' )
    assets = OneToMany('FinancialAccountAssetUsage', cascade='all, delete, delete-orphan' )
    brokers = OneToMany('FinancialAccountBroker', cascade='all, delete, delete-orphan' )
    applied_functional_settings = OneToMany('FinancialAccountFunctionalSettingApplication', cascade='all, delete, delete-orphan')
    notifications = OneToMany('vfinance.model.financial.work_effort.FinancialAccountNotification')
    agreements = OneToMany('vfinance.model.financial.agreement.FinancialAgreement')
    documents = OneToMany('vfinance.model.financial.document.FinancialDocument')
    direct_debit_mandates = OneToMany('vfinance.model.bank.direct_debit.DirectDebitMandate')
    text = Field( camelot.types.RichText, deferred = True )
    #tasks = ManyToMany( 'Task',
    #                    tablename='financial_account_task', 
    #                    remote_colname='task_id',
    #                    local_colname='financial_account_id',
    #                    backref='financial_accounts')
      
    __mapper_args__ = { 'order_by':id }
    
    def __unicode__(self):
        if self.package is not None:
            return u'%s %s %s'%(self.package.name or '',
                                self.subscriber_1 or '',
                                self.subscriber_2 or '' )

    def subscription_customer_at(self, date):
        from vfinance.model.bank.customer import CustomerAccount
        package = self.package
        dual_persons = self.get_roles_at(date, 'subscriber')
        if len(dual_persons):
            return CustomerAccount.find_by_dual_persons(dual_persons,
                                                        from_customer=package.from_customer,
                                                        thru_customer=package.thru_customer)
        else:
            raise Exception('Financial account %s has no subscribers at %s'%(self.id, date))
    
    def package_name( self ):
        from vfinance.model.financial.package import FinancialPackage

        return sql.select( [FinancialPackage.name],
                           whereclause = FinancialPackage.id == self.package_id )
    
    package_name = ColumnProperty( package_name, deferred = True )
        
    @classmethod
    def subscriber_query(cls, account_columns, rank=1):
        from vfinance.model.bank.dual_person import name_of_dual_person
        
        FAR = orm.aliased( FinancialAccountRole )
                
        query = sql.select( 
            [name_of_dual_person(FAR)],
            sql.and_(
                FAR.described_by=='subscriber', 
                FAR.financial_account_id==account_columns.id,
                FAR.thru_date >= datetime.date.today()
            ) 
        ).order_by( FAR.rank, FAR.id ).group_by( FAR.id, FAR.rechtspersoon_id, FAR.natuurlijke_persoon_id, FAR.rank )
        # group by is required to make sure the same person is not returned for multiple offset,
        # eg on the transaction level
        offset = rank - 1
        if offset > 0:
            query = query.offset( offset )
        return query.limit(1)
    
    def account_suffix_query( self ):
        """The suffix of the first premium schedule associated with this account, dont't use
        this result for anything but displaying a hint to the user."""
        from premium import FinancialAccountPremiumSchedule
        from product import FinancialProduct
        query = FinancialAccountPremiumSchedule.account_suffix_query(FinancialProduct, FinancialAccountPremiumSchedule, self)
        query = query.order_by(FinancialAccountPremiumSchedule.id)
        return query.limit(1)
    
    account_suffix = ColumnProperty( account_suffix_query,
                                     deferred = True )
    
    subscriber_1 = ColumnProperty( lambda self:FinancialAccount.subscriber_query( self, 1 ),
                                   deferred = True,
                                   group = 'subscriber' )
  
    subscriber_2 = ColumnProperty( lambda self:FinancialAccount.subscriber_query( self, 2 ),
                                   deferred = True,
                                   group = 'subscriber' )
        
    def broker(self):
        from vfinance.model.bank.dual_person import name_of_dual_person
        from sqlalchemy.orm import aliased
        
        CR = aliased(CommercialRelation)
        FAB = aliased(FinancialAccountBroker)
        
        return sql.select( [name_of_dual_person(CR)],
                           sql.and_(
                               CR.id == FAB.broker_relation_id,
                               FAB.financial_account_id==self.id,
                               FAB.thru_date >= datetime.date.today(),
                               FAB.from_date <= datetime.date.today(),
                           ),
                           from_obj=FAB.table.join(CR.table) ).order_by( FAB.id ).limit(1)
    
    broker = ColumnProperty( broker, deferred = True, group = 'subscriber' )

    def master_broker(self):
        from sqlalchemy.orm import aliased
        from vfinance.model.bank.rechtspersoon import Rechtspersoon
        
        CR = aliased(CommercialRelation)
        FAB = aliased(FinancialAccountBroker)
        
        return sql.select( [Rechtspersoon.name],
                           sql.and_(Rechtspersoon.id==CR.table.c.to_rechtspersoon,
                                    CR.table.c.id == FAB.broker_relation_id,
                                    FAB.financial_account_id==self.id,
                                    FAB.thru_date >= datetime.date.today(),
                                    FAB.from_date <= datetime.date.today(),
                           ),
                           from_obj=CR.table ).limit(1)
    
    master_broker = ColumnProperty( master_broker, deferred = True, group = 'subscriber' )


    @classmethod
    def create_account_from_agreement(cls, agreement):
        """Given a Financial Agreement, create a Financial Account for it
        :return: the financial account created 
        """
        account = None
        if agreement.account is not None:
            #
            # this agreement allready has an account, multiple agreements can
            # be made on a single account
            #
            account = agreement.account
        for agreed_premium_schedule in agreement.invested_amounts:
            for premium_schedule in agreed_premium_schedule.fulfilled_by:
                raise UserException('Premium schedules related to this agreement exist on account {}'.format(premium_schedule.financial_account.id))
        from_date = agreement.fulfillment_date
        if account is None:
            account = cls( package=agreement.package, text=agreement.text )
            for financial_agreement_role in agreement.roles:
                FinancialAccountRole(from_date=from_date, 
                                     described_by=financial_agreement_role.described_by,
                                     natuurlijke_persoon=financial_agreement_role.natuurlijke_persoon,
                                     rechtspersoon=financial_agreement_role.rechtspersoon,
                                     financial_account=account,
                                     rank=financial_agreement_role.rank,
                                     associated_clause=financial_agreement_role.associated_clause,
                                     use_custom_clause=financial_agreement_role.use_custom_clause,
                                     custom_clause=financial_agreement_role.custom_clause,
                                     surmortality=financial_agreement_role.surmortality,
                                     )
            for financial_agreement_item in agreement.agreed_items:
                FinancialAccountItem(from_date=from_date, 
                                     rank=financial_agreement_item.rank,
                                     associated_clause=financial_agreement_item.associated_clause,
                                     use_custom_clause=financial_agreement_item.use_custom_clause,
                                     custom_clause=financial_agreement_item.custom_clause,
                                     described_by=financial_agreement_item.described_by,
                                     financial_account=account,
                                     )
            if agreement.broker_relation or agreement.broker_agent:
                FinancialAccountBroker(financial_account=account,
                                       from_date=from_date,
                                       broker_relation=agreement.broker_relation,
                                       broker_agent=agreement.broker_agent)
            for functional_setting in agreement.agreed_functional_settings:
                FinancialAccountFunctionalSettingApplication(applied_on=account,
                                                             from_date=from_date,
                                                             described_by=functional_setting.described_by,
                                                             clause=functional_setting.clause)
            agreement.account = account
        for financial_agreement_asset_usage in agreement.assets:
            FinancialAccountAssetUsage(from_date=from_date,
                                       asset_usage=financial_agreement_asset_usage.asset_usage,
                                       financial_account=account)
        for document in agreement.documents:
            document.financial_account = account
        for mandate in agreement.direct_debit_mandates:
            mandate.financial_account = account
        return account
    
    def get_items_at(self, application_date, described_by=None):
        """Returns a sorted list (on rank, then id) of applicable items, optionally specified by type
        :param application_date: the date at which the items should be
            applicable
        :param described_by: string to indicate a specific role, see model.financial.constants.item_clause_types
        """
        if described_by:
            items = [item for item in self.items if item.from_date <= application_date and item.thru_date >= application_date and item.described_by==described_by]
        else:
            items = [item for item in self.items if item.from_date <= application_date and item.thru_date >= application_date]
        return sorted(sorted(items, key=attrgetter('rank')), key=attrgetter('id'))
        
    def get_notification_recipients(self, application_date ):
        """The notifications of type notification_type that should be applied
        at application_date.
        :yields: (DualPerson, boolean)
        boolean is True when the DualPerson is a broker 
        """
        from camelot.view.utils import text_from_richtext
        from jinja2 import Markup
        # make sure ranking is respected
        subscribers = sorted([role for role in self.roles if ( role.described_by=='subscriber' and
                                                               role.from_date <= application_date and
                                                               role.thru_date >= application_date )], key=lambda role: role.rank)
        notification_applied = False
        for functional_setting in self.applied_functional_settings:
            if functional_setting.described_by == 'mail_to_first_subscriber':
                for subscriber in subscribers:
                    yield subscriber, False
                    notification_applied = True
                    raise StopIteration
            elif functional_setting.described_by == 'mail_to_all_subscribers':
                for subscriber in subscribers:
                    yield subscriber, False
                    notification_applied = True
            elif functional_setting.described_by == 'mail_to_broker':
                for broker in self.brokers:
                    if broker.from_date <= application_date and broker.thru_date >= application_date:
                        yield broker.broker_relation, True
                        notification_applied = True
            elif functional_setting.described_by == 'mail_to_custom_address':
                for subscriber in subscribers:
                    # making up for the fact that camelot.view.utils.py:text_from_richtext returns an empty string as first item
                    custom_address_lines = [l for l in text_from_richtext(functional_setting.clause.strip()) if l is not '']
                    yield type('CustomAddressRole', (object,), {'titel':subscriber.titel,
                                                                'id': subscriber.id,
                                                                'last_name': subscriber.last_name, 
                                                                'first_name': subscriber.first_name, 
                                                                'natuurlijke_persoon': subscriber.natuurlijke_persoon,
                                                                'rechtspersoon': subscriber.rechtspersoon,
                                                                'address': Markup("<w:br/>".join(custom_address_lines)),
                                                                'mail_to_custom_address': True}), False
                    raise StopIteration
        # failback, send to first subscriber
        if not notification_applied and len(subscribers):
            yield subscribers[0], False
    
    def get_notification_addressees(self, application_date):
        addressees = []
        for recipient, _broker_flag in list(self.get_notification_recipients(application_date)):
            organization = None
            if hasattr(recipient, 'rechtspersoon') and recipient.rechtspersoon:
                organization = recipient.rechtspersoon
            addressees.append(Addressee(organization = organization,
                                        persons = [AddresseePerson(first_name = recipient.natuurlijke_persoon.first_name,
                                                                   middle_name = recipient.natuurlijke_persoon.middle_name,
                                                                   last_name = recipient.natuurlijke_persoon.last_name,
                                                                   personal_title = recipient.natuurlijke_persoon.titel,
                                                                   suffix = None)],
                                        street1 = recipient.straat,
                                        street2 = None,
                                        city_code = recipient.zipcode,
                                        city = recipient.city,
                                        country_code = recipient.country.code,
                                        country = recipient.country.name,))
        return addressees

    def get_pending_entries( self ):
        """Get entries that can be used potentially to distribute over
        the premium schedules of this account
        """
        pending_entries = set()
        for financial_agreement in self.agreements:
            for entry in financial_agreement.related_entries:
                if D(str(entry.open_amount)) <= 0:
                   pending_entries.add( entry )
        return pending_entries
    
    Admin = FinancialAccountAdmin
    
    
class FinancialAccountBroker(Entity, AbstractDossierBroker):
    using_options(tablename='financial_account_broker')
    financial_account = ManyToOne('FinancialAccount', required = True, ondelete = 'cascade', onupdate = 'cascade')
    broker_relation = ManyToOne('CommercialRelation', required=False, ondelete = 'restrict', onupdate = 'cascade', backref='managed_financial_accounts')
    broker_agent = ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon')
    
    class Admin(BankRelatedStatusAdmin):
        list_display = ['broker_relation', 'broker_agent', 'from_date', 'thru_date']
        
        def get_related_status_object(self, obj):
            return obj.financial_account
    
class FinancialAccountRole(DualPerson):
    using_options(tablename='financial_account_role')
    __table_args__ = ( schema.CheckConstraint( 'natuurlijke_persoon is not null or rechtspersoon is not null', 
                                               name='financial_account_role_persoon_fk'), )
    financial_account = ManyToOne('FinancialAccount', required = True, ondelete = 'cascade', onupdate = 'cascade')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    described_by = schema.Column(camelot.types.Enumeration(account_roles), nullable=False, index=True, default='subscriber')
    natuurlijke_persoon_id = schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon')
    rechtspersoon_id = schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon')
    natuurlijke_persoon  =  ManyToOne( 'vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id, 
                                       ondelete = 'restrict', onupdate = 'cascade',
                                       backref = orm.backref('financial_accounts', passive_deletes = True ) )
    rechtspersoon  =  ManyToOne( 'vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id, 
                                 ondelete = 'restrict', onupdate = 'cascade',
                                 backref = orm.backref('financial_accounts', passive_deletes = True ) )
    rank = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=1)
    associated_clause = ManyToOne('FinancialRoleClause', required=False, ondelete='restrict', onupdate='cascade')
    use_custom_clause = schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    custom_clause = schema.Column( camelot.types.RichText() )
    surmortality = schema.Column(sqlalchemy.types.Numeric(precision=6, scale=2), nullable=True, default=0)

    class Admin( DualPerson.Admin, BankRelatedStatusAdmin ):
        list_display = ['described_by', 'rank', 'surmortality', 'natuurlijke_persoon', 'rechtspersoon', 'from_date', 'thru_date']
        form_display = list_display + ['associated_clause', 'use_custom_clause', 'custom_clause']
        
        def get_related_status_object(self, obj):
            return obj.financial_account
        
class AbstractCustomClause(object):

    def _get_shown_clause(self):
        if self.use_custom_clause:
            return self.custom_clause
        if self.associated_clause:
            return self.associated_clause.clause

    def _set_shown_clause(self, new_clause):
        if self.use_custom_clause:
            self.custom_clause = new_clause

def associated_clause_choices(financial_account_item):
    associated_clauses = []
    # get only associated clauses available to the related product
    account = financial_account_item.financial_account 
    if account:
        package = account.package
        if package:
            available_item_clauses = package.available_item_clauses
            if available_item_clauses:
                for available_item_clause in available_item_clauses:
                    associated_clauses.append( (available_item_clause, unicode(available_item_clause.name)) )
    associated_clauses.append( (None, '') )
    return associated_clauses
                    
class FinancialAccountItem(Entity, AbstractCustomClause):
    __table_args__ = (schema.CheckConstraint("(associated_clause_id IS NULL AND use_custom_clause = 't' AND custom_clause IS NOT NULL) OR (associated_clause_id > 0 AND use_custom_clause = 'f')",
                                             name='check_account_associated_clause_or_custom_clause'),)
    using_options(tablename='financial_account_item')
    financial_account = ManyToOne('FinancialAccount', required = True, ondelete = 'cascade', onupdate = 'cascade')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    rank = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=1)
    associated_clause = ManyToOne('FinancialItemClause', required=False, ondelete='restrict', onupdate='cascade')
    use_custom_clause = schema.Column(sqlalchemy.types.Boolean(), nullable=False, default=False)
    custom_clause = schema.Column( camelot.types.RichText() )
    described_by = schema.Column( camelot.types.Enumeration(item_clause_types), nullable=False, index=True, default='beneficiary' )
       
    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Item within financial account')
        list_display = ['rank', 'described_by', 'associated_clause', 'use_custom_clause', 'from_date', 'thru_date']
        form_display = forms.Form(['rank', 'described_by', 'from_date', 'thru_date', 'associated_clause', 'use_custom_clause', 'custom_clause'])
        field_attributes = {
            'described_by':{'name':_('Type')},
            'associated_clause':{'choices':associated_clause_choices}
        }
        
        def get_related_status_object(self, obj):
            return obj.financial_account
        
class FinancialAccountAssetUsage(Entity):
    using_options(tablename='financial_account_asset_usage')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    financial_account = ManyToOne('FinancialAccount', required = True, ondelete = 'cascade', onupdate = 'cascade')
    asset_usage = ManyToOne('vfinance.model.hypo.hypotheek.TeHypothekerenGoed', required = True, ondelete = 'restrict', onupdate = 'cascade')
    
    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Asset used within a financial account')
        list_display = ['asset_usage', 'from_date', 'thru_date']
        field_attributes = {'asset_usage':{'name':_('Asset'), 'minimal_column_width':45}}
        form_size = (400,200)
        
        def get_related_status_object(self, obj):
            return obj.financial_account

class FinancialAccountFunctionalSettingApplication(Entity, FunctionalSettingMixin):
    using_options(tablename='financial_account_functional_setting_application')
    applied_on = ManyToOne('FinancialAccount', required = True, ondelete = 'restrict', onupdate = 'cascade')
    described_by = schema.Column( camelot.types.Enumeration(functional_settings), nullable=False, default='exit_at_first_decease')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    clause = schema.Column(camelot.types.RichText())
    
    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Financial Account Setting')
        verbose_name_plural = _('Financial Account Settings')
        list_display = ['applied_on_id', 'described_by', 'from_date', 'thru_date']
        form_display = list_display + ['clause']
        field_attributes = {'described_by':{'name':_('Description')},
                            'clause':{'editable':lambda fs:fs.custom_clause},
                            'applied_on_id': {'name': 'Financial account id'}}
        list_filter = ['described_by']
        
        def get_related_status_object(self, obj):
            return obj.applied_on

class FunctionalSettingApplicationAccountAdmin(FinancialAccountFunctionalSettingApplication.Admin):
    list_display = ['described_by', 'from_date', 'thru_date']
    form_display = list_display + ['clause']

FinancialAccount.Admin.field_attributes['applied_functional_settings'] = {'admin': FunctionalSettingApplicationAccountAdmin}
