import itertools
import logging

import sqlalchemy.types
from sqlalchemy import schema, orm, sql

from camelot.core.orm import ( Entity, OneToMany, ManyToOne, 
                               using_options, Session, ColumnProperty )
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _

from vfinance.model.bank.dual_person import DualPerson, name_of_dual_person
from vfinance.admin.vfinanceadmin import VfinanceAdmin
from .summary import CustomerSummary
from camelot.core.conf import settings

logger = logging.getLogger('vfinance.model.bank.customer')

class SupplierAccount(DualPerson):
    using_options(tablename='bank_supplier')
    __table_args__ = ( schema.CheckConstraint('natuurlijke_persoon is not null or rechtspersoon is not null', name='bank_supplier_persoon_fk'), )
    rechtspersoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon', nullable=True, index=True)
    rechtspersoon  =  ManyToOne( 'vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id,
                                 ondelete = 'restrict', onupdate = 'cascade', backref='supplier_accounts' )
    natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon', nullable=True, index=True)
    natuurlijke_persoon  =  ManyToOne( 'vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id,
                                       ondelete = 'restrict', onupdate = 'cascade', backref='supplier_accounts' )
    accounting_number = schema.Column('supplier_number', sqlalchemy.types.Integer(), nullable=True)

    @classmethod
    def find_by_dual_person(cls, natuurlijke_persoon, rechtspersoon, from_number, thru_number):
        session = Session()
        if (natuurlijke_persoon is not None) or (rechtspersoon is not None):
            query = session.query(cls)
            query = query.filter_by(rechtspersoon=rechtspersoon, natuurlijke_persoon=natuurlijke_persoon)
            query = query.filter(cls.accounting_number >= from_number )
            query = query.filter(cls.accounting_number <= thru_number )
            return query.first()
        return None

    def owned_by(self):
        SA = orm.aliased(SupplierAccount)
        return sql.select( [name_of_dual_person(SA)],
                           whereclause= (SA.id==self.id))
    
    owned_by = ColumnProperty( owned_by, deferred = True )
    
    @property
    def full_account_number(self):
        supplier_account = settings.get( 'BANK_ACCOUNT_SUPPLIER', None )
        if supplier_account and self.accounting_number:
            return str( int(supplier_account) + self.accounting_number )
        
    def __unicode__(self):
        return u'%s - %s'%( self.full_account_number,
                            self.owned_by )

    class Admin(DualPerson.Admin):
        verbose_name = _('Supplier Account')
        list_display = ['accounting_number'] + ['owned_by']
        list_search = ['owned_by']
        form_display = DualPerson.Admin.form_display.get_fields() + ['accounting_number']
        #field_attributes = {'accounting_number': {'editable': False}
                            #}
    
class AccountHolder(DualPerson):
    using_options(tablename='bank_persoon')
    __table_args__ = ( schema.CheckConstraint('natuurlijke_persoon is not null or rechtspersoon is not null', name='bank_persoon_persoon_fk'), )
    rechtspersoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon', nullable=True, index=True)
    rechtspersoon  =  ManyToOne( 'vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id,
                                 ondelete = 'restrict', onupdate = 'cascade' )
    accounts  =  OneToMany('vfinance.model.bank.customer.AccountHolderAccount', inverse='account_holder')
    natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon', nullable=True, index=True)
    natuurlijke_persoon  =  ManyToOne( 'vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id,
                                       ondelete = 'restrict', onupdate = 'cascade' )
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
 
    def __unicode__( self ):
        return self.name
        
    class Admin( DualPerson.Admin ):
        pass

class CustomerAccount(Entity):
    using_options(tablename='bank_klant')
    account_holders  =  OneToMany('vfinance.model.bank.customer.AccountHolderAccount', inverse='customer_account')
    state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True, default=u'draft')
    #bond_ownership  =  OneToMany('vfinance.modelbond.Owner', inverse='klant')
    venice_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    accounting_number = schema.Column('venice_nummer', sqlalchemy.types.Integer(), nullable=True)

    @property
    def name(self):
        return u', '.join((account_holder.name or '') for account_holder in self.account_holders)
    
    def __unicode__(self):
        return self.name

    @classmethod
    def get_full_account_number(cls, accounting_number):
        customer_account = settings.get( 'HYPO_ACCOUNT_KLANT', 400000000000 )
        return str( int(customer_account) + accounting_number )

    @property
    def full_account_number(self):
        if self.accounting_number:
            return self.get_full_account_number(self.accounting_number)
  
    def holder_1(self):
        AH = orm.aliased( AccountHolder )
        AHA = orm.aliased( AccountHolderAccount )
        
        return sql.select( [name_of_dual_person(AH)],
                           whereclause = sql.and_(AHA.customer_account_id==self.id,
                                                  AHA.account_holder_id==AH.id),
                           ).order_by(AH.id).limit(1)
    
    holder_1 = ColumnProperty( holder_1, deferred = True )
 
    def holder_2(self):
        AH = orm.aliased( AccountHolder )
        AHA = orm.aliased( AccountHolderAccount )
        
        return sql.select( [name_of_dual_person(AH)],
                           whereclause = sql.and_(AHA.customer_account_id==self.id,
                                                  AHA.account_holder_id==AH.id),
                           ).order_by(AH.id).offset(1).limit(1)
    
    holder_2 = ColumnProperty( holder_2, deferred = True )

    @classmethod
    def filtered_dual_persons(cls, dual_persons):
        dp_key = lambda dp:(dp.person_id, dp.organization_id)
        for _key, group in itertools.groupby(dual_persons, key=dp_key):
            for dual_person in itertools.islice(group, 1):
                yield dual_person
        
    @classmethod
    def find_by_dual_persons(cls, dual_persons, from_customer, thru_customer):
        '''
        Geef een klant id voor een gegeven lijst van personen.
        
        :param dual_persons: Een lijst met rechtspersoon.persoon meta-instances
        :return: None indien niet gevonden.
        :param from_customer: the minimal value to be used for the customer number
        :param thru_customer: the maximal value to be used for the customer number
        '''
        
        def min_key(iterable, key=lambda x: x):
            _m, _i, e = min([ (key(el), index, el) for index, el in enumerate(iterable) ])
            return e
        
        dual_persons = list(cls.filtered_dual_persons(dual_persons))
        account_holders = [ AccountHolder.find_by_dual_person(dual_person) for dual_person in dual_persons ]
        account_holder_ids = [account_holder.id for account_holder in account_holders if account_holder]
        if len(dual_persons) != len(account_holder_ids):
            return None
        
        account_ids_by_account_holder = list( AccountHolderAccount.find_customer_account_ids_by_account_holder_ids(account_holder_ids, from_customer, thru_customer) )
        customer_account_ids = reduce(set.intersection, [ set(account_ids) for _account_holder_id, account_ids in account_ids_by_account_holder ])
        
        if not customer_account_ids:
            return None
            
        account_holder_ids_by_customer_account = list( AccountHolderAccount.find_account_holder_ids_by_customer_account_ids(customer_account_ids) )
        candidate_account, candidate_account_holders = min_key(account_holder_ids_by_customer_account, key=lambda x: len(x[1]))
        if len(candidate_account_holders) == len(dual_persons):
            return cls.get(candidate_account)
        return None
        
    @classmethod
    def create_by_dual_persons(cls, dual_persons, from_customer, thru_customer):
        if not len(dual_persons):
            raise Exception('Need at least one person for the creation of a customer')
        customer_account = cls(state='draft')
        for dual_person in cls.filtered_dual_persons(dual_persons):
            account_holder =  AccountHolder.find_or_create_by_dual_person(dual_person)
            AccountHolderAccount(account_holder=account_holder, customer_account=customer_account)
        return customer_account

    class Admin(VfinanceAdmin):
        verbose_name = _('Customer Account')
        verbose_name_plural = _('Customer Accounts')
        list_display =  ['accounting_number', 'holder_1', 'holder_2']
        list_search = ['holder_1', 'holder_2']
        list_actions = [CustomerSummary()]
        form_actions = list_actions
        form_display =  forms.TabForm( [(_('Account Holders'), forms.Form(['accounting_number', 'state', 'full_account_number', 'account_holders',], columns=2)),
                                        ])
        field_attributes = {
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name'), 'minimal_column_width':75},
                            'account_holders':{'editable':True, 'name':_('Account holders')},
                            'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                            'state':{'editable':False, 'name':_('State'), 'choices':[('draft', 'Nog niet aangemaakt'), ('aangemaakt', 'Aangemaakt')]},
                            'bond_ownership':{'editable':True, 'name':_('Obligaties in eigendom')},
                            'venice_id':{'editable':False, 'name':_('Venice systeemnummer')},
                            'accounting_number':{'editable':False, 'name':_('Customer Number')},
                           }
#  min_key

class AccountHolderAccount(Entity):
    using_options(tablename='bank_persoon_klant_rel')
    primary_contact  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    account_holder_id  =  schema.Column(sqlalchemy.types.Integer(), name='persoon', nullable=True, index=True)
    account_holder  =  ManyToOne('vfinance.model.bank.customer.AccountHolder', field=account_holder_id)
    customer_account_id  =  schema.Column(sqlalchemy.types.Integer(), name='klant', nullable=True, index=True)
    customer_account  =  ManyToOne('vfinance.model.bank.customer.CustomerAccount', field=customer_account_id)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    @classmethod
    def find_customer_account_ids_by_account_holder_ids(cls, account_holder_ids, from_customer, thru_customer):
        query = cls.query.join(AccountHolderAccount.customer_account).filter(sql.and_(CustomerAccount.accounting_number >= from_customer,
                                                                                     CustomerAccount.accounting_number <= thru_customer))
        for account_holder_id in account_holder_ids:
            yield (account_holder_id, list(account_holder_account.customer_account_id for account_holder_account in query.filter(cls.account_holder_id==account_holder_id)))

    @classmethod
    def find_account_holder_ids_by_customer_account_ids(cls, customer_account_ids):
        for customer_account_id in customer_account_ids:
            yield (customer_account_id, list(account_holder_account.account_holder_id for account_holder_account in cls.query.filter_by(customer_account_id=customer_account_id) ))

    @property
    def name(self):
        if self.account_holder:
            return self.account_holder.name
        else:
            return 'unknown'
    
    def __unicode__(self):
        return self.name

    class Admin(EntityAdmin):
        list_display =  ['account_holder', 'primary_contact']
        form_display =  forms.Form(['account_holder','primary_contact',], columns=2)
        field_attributes = {
                            'primary_contact':{'editable':True, 'name':_('Preferentieel contact')},
                            'account_holder':{'editable':True, 'name':_('Persoon')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                            'klant':{'editable':True, 'name':_('Klant')},
                           }
