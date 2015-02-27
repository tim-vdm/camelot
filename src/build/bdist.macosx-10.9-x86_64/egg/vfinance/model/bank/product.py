import copy
import datetime
from decimal import Decimal as D
import logging

from camelot.admin.entity_admin import EntityAdmin
from camelot.core.orm import OneToMany, ManyToOne, Entity
from camelot.core.exception import UserException
from camelot.core.utils import ugettext_lazy as _
from camelot.model.authentication import end_of_times
from camelot.model.type_and_status import Status
from camelot.view.controls import delegates
from camelot.view import forms
import camelot.types

from sqlalchemy import schema, sql, orm
from sqlalchemy.ext.declarative import declared_attr
import sqlalchemy.types

from .constants import (commission_receivers,
                        product_features_enumeration,
                        period_types,
                        product_feature_conditions,
                        product_indexes,
                        product_statuses,
                        account_types,
                        free_feature_offset,
                        )
from .index import IndexType
from .feature import AbstractFeatureApplicability
from .statusmixin import (BankRelatedStatusAdmin, BankStatusMixin, BankStatusAdmin,
                          status_form_actions)
from .admin import NumericValidator

account_code = ['999999999999']
feature_prefix = 'feature_'

LOGGER = logging.getLogger( 'vfinance.model.bank.product' )

class ProductMixin(object):
    
    # @todo : add a validator or note that checks that the same account
    # is not defined twice in the same product, or in the product and the
    # in the base product

    def __getattr__(self, name):
        if name.startswith(feature_prefix):
            feature_name = name[len(feature_prefix):]
            today = datetime.date.today()
            for feature in self.get_applied_features_at(today):
                if feature.described_by == feature_name:
                    return feature.value or 0
            return 0
        raise AttributeError(name)

    @property
    def note(self):
        pass

    def is_verifiable(self):
        return True

    def __unicode__(self):
        return self.name or u''

    def get_index_type_at( self, application_date, described_by ):
        for available_index in self.available_indexes:
            if available_index.apply_from_date <= application_date and available_index.apply_thru_date >= application_date:
                if available_index.described_by == described_by:
                    return available_index.index_type

    def get_account_type_at( self, booking_number, book_date ):
        """
        :param booking_number: a string with the account number
        :param book_date: the date at which there was a booking on this account
        :return: the account type for the given number at the given date
        """
        booking_number = booking_number.strip()
        for product_account in self.get_available_accounts():
            if (product_account.from_date <= book_date) and (product_account.thru_date >= book_date):
                if ''.join(product_account.number) == booking_number:
                    return product_account.described_by
        for available_fund in self.available_funds:
            fund = available_fund.fund
            if fund.get_account( 'transfer_revenue' ) == booking_number:
                return 'transfer_revenue'
        raise UserException( 'Booking on account "%s" at %s cannot be identified'%( booking_number, book_date ),
                             resolution = 'Verify the product configuration of %s and make sure the account is defined'%self.name )

    def get_available_broker_relations(self):
        """Generator over the CommercialRelations of type 'broker' for all available brokers
        of the product"""
        for available_broker in self.available_brokers:
            if available_broker.rechtspersoon:
                for commercial_relation in available_broker.rechtspersoon.commercial_relations_to:
                    if commercial_relation.type == 'broker':
                        yield commercial_relation

    def get_all_features(self):
        """
        :return: an iterator over all features, including those of the parent product
        """
        if self.specialization_of is not None:
            for feature in self.specialization_of.get_all_features():
                yield feature
        for feature in self.available_with:
            yield feature

    def get_applied_features_at(self, application_date):
        """
        :param application_date: the date at which the features will be used, eg to book a premium
        :return: a generator of features, the feature with the highest priority comes last
        """
        assert isinstance( application_date, datetime.date )
        for feature in self.get_all_features():
            if feature.apply_from_date <= application_date and feature.apply_thru_date >= application_date:
                yield feature

    def get_book_at( self, book_type, application_date ):
        book = getattr( self, book_type + '_book' )
        if book == None and self.specialization_of != None:
            return self.specialization_of.get_book_at( book_type, application_date )
        return book
    
    def get_available_accounts( self ):
        """
        :return: an iterator over the available product accounts, including 
            those of the base product
        """
        for product_account in self.available_accounts:
            yield product_account
        if self.specialization_of is not None:
            for product_account in self.specialization_of.get_available_accounts():
                yield product_account
        
    def get_accounts( self, account_type ):
        for product_account in self.get_available_accounts():
            if ( product_account.described_by == account_type ):
                yield product_account
                
    def get_account_at( self, account_type, book_date ):
        """
        Get the account number for a specified account_type
        :param account_type: a string such as 'interest_cost'
        :param valid_date: the book date at which the account should be valid
        :return: a string with the account number or an empty string if no 
        such account was defined.
        """
        
        for product_account in self.get_accounts( account_type ):
            if ( product_account.from_date <= book_date and
                 product_account.thru_date >= book_date
                 ):
                return ''.join( product_account.number )
        LOGGER.debug( 'not existing account of type %s at %s requested on product %s'%( account_type, book_date, self.name ) )
        return ''


class Product(Entity, BankStatusMixin, ProductMixin):
    """Financial product is a combination of an Insurance Product of p.184 and a
    Financial Services Product of p.261
    """

    __tablename__ = 'financial_product'

    row_type = schema.Column(sqlalchemy.types.Unicode(40), nullable=False)

    origin  =  schema.Column(sqlalchemy.types.Unicode(30), nullable=True)
    jurisdiction = schema.Column(camelot.types.Enumeration([(1, 'belgian'), (2, 'italian'), (3, 'netherlands'), (4, 'france'), (5, 'german')]))
    account_number_prefix = schema.Column(sqlalchemy.types.Integer(), nullable=False)
    account_number_digits = schema.Column(sqlalchemy.types.Integer(), default=5, nullable=False)
    company_number_digits = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=0)
    rank_number_digits = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=0)
    name = schema.Column(sqlalchemy.types.Unicode(255), nullable=False, index=True)
    code = schema.Column(sqlalchemy.types.Unicode(100), nullable=True, index=True)
    from_date = schema.Column( sqlalchemy.types.Date(), nullable=False, index=True, default=datetime.date.today)
    book_from_date = schema.Column( sqlalchemy.types.Date(), nullable=False, index=True, default=datetime.date.today)
    sales_discontinuation_date = schema.Column( sqlalchemy.types.Date(), nullable=True, index=True)
    support_discontinuation_date = schema.Column( sqlalchemy.types.Date(), nullable=True, index=True)
    accounting_year_transfer_book = schema.Column(sqlalchemy.types.Unicode(25))
    external_application_book = schema.Column(sqlalchemy.types.Unicode(25))
    supplier_distribution_book = schema.Column(sqlalchemy.types.Unicode(25))
    comment = schema.Column(camelot.types.RichText())

    available_coverages = OneToMany('vfinance.model.insurance.product.InsuranceCoverageAvailability', cascade='all, delete, delete-orphan')

    status = Status(enumeration=product_statuses, status_history_table='financialproduct_status')

    __mapper_args__ = {
        'order_by': 'id',
        'polymorphic_on': row_type
    }

    @property
    def specialization_of(self):
        self.declare_last()

    @declared_attr
    def specialization_of_id(cls):
        return schema.Column('specialization_of_id',
                             sqlalchemy.types.Integer(),
                             schema.ForeignKey(cls.id,
                                               ondelete = 'restrict',
                                               onupdate = 'cascade' ),
                             nullable=True)

    @classmethod
    def declare_last(cls):
        """Call this method in subclasses to create the adjacent relations"""
        BaseProduct = orm.aliased(cls)
        cls.base_product = orm.column_property(sql.select([BaseProduct.name],
                                                          whereclause = BaseProduct.id == cls.specialization_of_id))
        cls.specialization_of = orm.relationship(cls, foreign_keys=[cls.specialization_of_id], remote_side=[cls.id])
    
    class Admin(BankStatusAdmin):
        verbose_name = _('Product definition')
        list_display = ['from_date', 'name', 'code', 'account_number_prefix', 'base_product']
        list_filter = ['current_status']
        form_actions = status_form_actions
        form_display = forms.TabForm([
            (_('Definition'), forms.Form([
                'name', 'code', 'specialization_of',
                'jurisdiction', 'from_date',
                'book_from_date', 'sales_discontinuation_date',
                'support_discontinuation_date', 'comment',], columns=2)),
            (_('Features'), ['available_with']),
            (_('Index'), ['available_indexes']),
            (_('Status history'), ['status',]),
            ])
        field_attributes = {
            'available_with':{'name':_('Features'), 'create_inline':True},
            'available_funds':{'name':_('Funds'), 'create_inline':True},
            'available_accounts':{'name':_('Accounts'), 'create_inline':True},
            'base_product':{'editable':False},
            'specialization_of':{'name':_('Base product')},
            'available_indexes': {'name': _('Indexes')},
            #'age_days_a_year':{'name':_('Days a year for age calculation')},
            'completion_book':{'name':_('Dagboek aktes')},
            'repayment_book':{'name':_('Dagboek vervaldagen')},
            'transaction_book':{'name':_('Dagboek wijzigingen')},
            'additional_cost_book':{'name':_('Dagboek rappelkosten')},
            'feature_eerste_herziening':{'name':_('Eerste herziening rente'), 'delegate':delegates.MonthsDelegate},
            'feature_volgende_herzieningen':{'name':_('Volgende herzieningen rente'), 'delegate':delegates.MonthsDelegate},
            'feature_premium_fee_1':{'name':_('Premium fee 1'), 'delegate':delegates.FloatDelegate},
            'feature_premium_rate_1':{'name':_('Premium rate 1'), 'delegate':delegates.FloatDelegate},
        }
        form_state = 'maximized'


class ProductAccount(Entity):
    """Accounts in the accounting system on which the visitors will do
    bookings"""

    __tablename__ = 'financial_product_account'

    
    described_by = schema.Column(camelot.types.Enumeration(account_types), nullable=False, index=True, default='additional_interest_cost')
    #number = schema.Column(camelot.types.Code(account_code), nullable=False)
    number = schema.Column(sqlalchemy.types.Unicode(15), nullable=False)
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    
    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Account')
        list_display = ['described_by', 'from_date', 'thru_date', 'number']
        field_attributes = {
            'described_by':{'name':_('Type')},
            'from_date':{'name':_('From book date')},
            'thru_date':{'name':_('Thru book date')},
            'number':{'validator': NumericValidator()},
        }

        def get_related_status_object(self, o):
            return o.available_for

# Force order of list to make sure the same product account is always retrieved first
# when multiple product accounts have the same number
ProductAccount.available_for = ManyToOne(Product,
                                         nullable=False,
                                         ondelete='cascade', onupdate = 'cascade',
                                         backref=orm.backref('available_accounts',
                                                             cascade='all, delete, delete-orphan',
                                                             order_by=[ProductAccount.id])
                                         )

class ProductIndexApplicability(Entity):
    """Indexes that should be used within financial products
    """

    __tablename__ = 'financial_product_index_applicability'

    available_for = ManyToOne(Product,
                              nullable=False,
                              ondelete='cascade', onupdate='cascade',
                              backref=orm.backref('available_indexes', cascade='all, delete, delete-orphan'))
    index_type = ManyToOne(IndexType, required=True, ondelete='restrict', onupdate='cascade')
    described_by = schema.Column(camelot.types.Enumeration(product_indexes), nullable=False, index=True, default='market_fluctuation_exit_rate')
    apply_from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    apply_thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )

    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Applicable Index')
        list_display = ['described_by', 'index_type', 'apply_from_date', 'apply_thru_date']
        field_attributes = {
            'described_by':{'name':_('Type')}
        }

        def get_related_status_object(self, obj):
            if obj is not None:
                return obj.available_for
            return None

def product_feature_choices(product_feature_applicability):
    product = product_feature_applicability.available_for
    return feature_choices_from_product(product)

def feature_choices_from_product(product):
    choices = []
    if product is not None:
        for number, name in product_features_enumeration:
            if (number >= product.from_feature and number <= product.thru_feature) or (number > free_feature_offset):
                choices.append((name, name))
    return choices

class ProductFeatureApplicability(AbstractFeatureApplicability):

    __tablename__ = 'product_feature_applicability'

    available_for = ManyToOne(Product,
                              nullable=False,
                              ondelete='cascade', onupdate='cascade',
                              backref=orm.backref('available_with', cascade='all, delete, delete-orphan'))
    described_by = schema.Column( camelot.types.Enumeration(product_features_enumeration), nullable=False, default='interest_rate')
    premium_period_type = schema.Column(camelot.types.Enumeration([(None,'All')] + period_types), default=None, nullable=True)
    comment = schema.Column( camelot.types.RichText() )

    __mapper_args__ = {
        'order_by': ['premium_from_date', 'described_by'],
    }

    # returns from_date of the associated FinancialAgreement (used to set default values for from-dates)
    def product_from_date(self):
        if self.available_for:
            return self.available_for.from_date
        return None

    def get_conditions( self ):
        return self.limited_by

    class Admin(AbstractFeatureApplicability.Admin, BankRelatedStatusAdmin):
        form_display = forms.Form( [forms.WidgetOnlyForm('note'), 'described_by', 'value',
                                    forms.TabForm( [ (_('Applicability'), forms.Form( AbstractFeatureApplicability.Admin.list_display[2:], columns=2) ),
                                                     (_('Distribution'), ['distributed_via'] ),
                                                     (_('Conditions'), ['limited_by'] ),
                                                     (_('Extra'), ['comment'] ) ] ) ])
        field_attributes = copy.deepcopy(AbstractFeatureApplicability.Admin.field_attributes)
        field_attributes['described_by'] = {'choices': product_feature_choices}
        field_attributes['premium_from_date'] = {'default':lambda o: o.product_from_date()}
        field_attributes['apply_from_date']   = {'default':lambda o: o.product_from_date()}

        def get_related_status_object(self, o):
            return o.available_for

class ProductFeatureDistribution( Entity ):

    __tablename__ = 'financial_product_feature_distribution'

    of = ManyToOne(ProductFeatureApplicability,
                   onupdate='cascade', ondelete='cascade',
                   nullable=False,
                   backref=orm.backref('distributed_via', cascade='all, delete, delete-orphan'))
    recipient = schema.Column( camelot.types.Enumeration(commission_receivers), nullable=False, default=commission_receivers[0][1] )
    distribution = schema.Column( sqlalchemy.types.Numeric(17,5), nullable=False )
    comment = schema.Column( sqlalchemy.types.Unicode(256) )

    class Admin( EntityAdmin ):
        list_display = ['recipient', 'distribution', 'comment']

class ProductFeatureCondition( Entity ):

    __tablename__ = 'financial_product_feature_condition'

    limit_for = ManyToOne(ProductFeatureApplicability,
                          onupdate='cascade', ondelete='cascade',
                          nullable=False,
                          backref=orm.backref('limited_by', cascade='all, delete, delete-orphan'))
    described_by = schema.Column( camelot.types.Enumeration([pf[:2] for pf in product_feature_conditions]), nullable=False, default='average_insured_age')
    value_from = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=D('0.0') )
    value_thru = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=D('100.0') )

    def evaluate( self, premium_schedule ):
        """Evaluate this condition on a premium schedule
        :param premium_schedule:
        :return: True of the condition is met, False otherwise
        """
        insured_at_from_date = [r.natuurlijke_persoon for r in premium_schedule.get_roles_at( premium_schedule.valid_from_date, described_by = 'insured_party' ) if r.natuurlijke_persoon ]

        if not len( insured_at_from_date ):
            return False

        if self.described_by == 'average_insured_age':
            value = sum( np.age_at( premium_schedule.valid_from_date ) for np in insured_at_from_date ) / len( insured_at_from_date )
        elif self.described_by == 'insured_male':
            value = sum( np.gender == 'm' for np in insured_at_from_date )
        elif self.described_by == 'insured_female':
            value = sum( np.gender == 'v' for np in insured_at_from_date )
        else:
            return False

        if value < self.value_from:
            return False
        if value > self.value_thru:
            return False
        return True

    class Admin( EntityAdmin ):
        list_display = ['described_by', 'value_from', 'value_thru']
        field_attributes = { 'described_by':{ 'name':'Type' } }

