import copy

from sqlalchemy import sql, orm, schema
import sqlalchemy.types

from camelot.admin.action import list_filter
from camelot.core.orm import (using_options, ManyToOne, 
                              ColumnProperty  )
import camelot.types

from ..bank.statusmixin import BankRelatedStatusAdmin
from ..bank.feature import AbstractFeatureApplicability
from ..bank.product import feature_choices_from_product

from vfinance.admin.vfinanceadmin import VfinanceAdmin

from constants import period_types, transaction_features_enumeration
from ..bank.constants import product_features_enumeration

from .premium import (FinancialAgreementPremiumSchedule,
                      FinancialAccountPremiumSchedule,
                      financial_account_premium_schedule_table,
                      FinancialAccountPremiumScheduleHistory)

def agreement_feature_choices(agreement_feature):
    if agreement_feature.agreed_on is not None:
        return feature_choices_from_product(agreement_feature.agreed_on.product)
    return []

class FinancialAgreementPremiumScheduleFeature(AbstractFeatureApplicability):
    using_options(tablename='financial_agreement_premium_feature', order_by=['premium_from_date', 'described_by'])
    agreed_on_id = schema.Column(sqlalchemy.types.Integer(),
                                  schema.ForeignKey(FinancialAgreementPremiumSchedule.id, ondelete='cascade', onupdate='cascade'),
                                  nullable = False,
                                  index = True)
    agreed_on = orm.relationship(FinancialAgreementPremiumSchedule,  backref=orm.backref('agreed_features', cascade='all, delete, delete-orphan'))
    described_by = schema.Column( camelot.types.Enumeration(product_features_enumeration), nullable=False, default='interest_rate')
    premium_period_type = schema.Column(camelot.types.Enumeration([(0,None)] + period_types), default=None, nullable=True)
    comment = schema.Column( camelot.types.RichText() ) 

    # returns from_date of the associated FinancialAgreement (used to set default values for from-dates) 
    def default_premium_from_date(self):
        if self.agreed_on and self.agreed_on.financial_agreement:
            return self.agreed_on.financial_agreement.from_date
        return None

    class Admin(AbstractFeatureApplicability.Admin):
        field_attributes = copy.copy(AbstractFeatureApplicability.Admin.field_attributes)
        field_attributes['described_by'] = {'choices':agreement_feature_choices}
        field_attributes['premium_from_date'] = {'default':lambda o: o.default_premium_from_date()}
        field_attributes['apply_from_date']   = {'default':lambda o: o.default_premium_from_date()}
        
        def get_depending_objects(self, obj):
            if obj.agreed_on:
                yield obj.agreed_on.financial_agreement

FinancialAgreementPremiumSchedule.agreed_features_by_description = orm.relationship(
    FinancialAgreementPremiumScheduleFeature,
    collection_class = orm.collections.attribute_mapped_collection('described_by'),
    cascade = 'all, delete-orphan'
)

def account_feature_choices(account_feature):
    if account_feature.applied_on is not None:
        return feature_choices_from_product(account_feature.applied_on.product)
    return []

class FinancialAccountPremiumScheduleFeature(AbstractFeatureApplicability):

    __tablename__ = 'financial_account_premium_feature'

    applied_on_id = schema.Column(sqlalchemy.types.Integer(),
                                  schema.ForeignKey(financial_account_premium_schedule_table.c.id, ondelete='restrict', onupdate='cascade'),
                                  nullable = False,
                                  index = True)
    applied_on = orm.relationship(FinancialAccountPremiumSchedule,  backref=orm.backref('applied_features', cascade='all, delete, delete-orphan'))
    described_by = schema.Column( camelot.types.Enumeration(product_features_enumeration), nullable=False, default='interest_rate')
    premium_period_type = schema.Column(camelot.types.Enumeration([(0,None)] + period_types), default=None, nullable=True)
    comment = schema.Column( camelot.types.RichText() )

    __mapper_args__ = {
        'order_by': ['premium_from_date', 'described_by']
    }

    def account_suffix(self):
        from product import FinancialProduct
        from account import FinancialAccount
        return FinancialAccountPremiumSchedule.account_suffix_query( FinancialProduct, FinancialAccountPremiumSchedule, FinancialAccount ).where( FinancialAccountPremiumSchedule.id == self.applied_on_id )
    
    account_suffix = ColumnProperty( account_suffix, deferred = True, group = 'premium_schedule' )
    
    def product_name( self ):
        from product import FinancialProduct
        return sql.select( [FinancialProduct.name] ).where( sql.and_( FinancialAccountPremiumSchedule.id == self.applied_on_id,
                                                                      FinancialProduct.id == FinancialAccountPremiumSchedule.product_id ) )
    
    product_name = ColumnProperty( product_name, deferred = True, group = 'premium_schedule' )
    
    def premium_schedule_from_date( self ):
        return sql.select( [FinancialAccountPremiumSchedule.valid_from_date] ).where( FinancialAccountPremiumSchedule.id == self.applied_on_id )
    
    premium_schedule_from_date = ColumnProperty( premium_schedule_from_date, deferred = True, group = 'premium_schedule' )
    
    @property
    def full_account_number(self):
        if self.applied_on is not None:
            return self.applied_on.full_account_number

    class Admin( AbstractFeatureApplicability.Admin, BankRelatedStatusAdmin):
        expanded_list_search = ['premium_schedule_from_date', 'from_agreed_duration', 'thru_agreed_duration', 'from_passed_duration', 
                                'thru_passed_duration', 'from_attributed_duration', 'thru_attributed_duration', 'premium_from_date', 'premium_thru_date', 
                                'apply_from_date', 'apply_thru_date',]
        list_display = ['applied_on_id', 'full_account_number', 'premium_schedule_from_date',] + AbstractFeatureApplicability.Admin.list_display
        list_filter = [list_filter.ComboBoxFilter('described_by'),
                       list_filter.ComboBoxFilter('product_name'),
                       list_filter.ComboBoxFilter('premium_period_type'),
                       list_filter.ComboBoxFilter('automated_clearing'), ]
        field_attributes = copy.copy(AbstractFeatureApplicability.Admin.field_attributes)
        field_attributes['applied_on_id'] = {'name': 'Premium schedule id'}
        field_attributes['described_by'] = {'choices':account_feature_choices}
        
        def get_query(self, *args, **kwargs):
            query = VfinanceAdmin.get_query(self, *args, **kwargs)
            query = query.options(orm.subqueryload('applied_on'))
            return query
        
        def get_related_status_object(self, obj):
            if obj.applied_on is not None:
                return obj.applied_on.financial_account
            return None

FinancialAccountPremiumScheduleHistory.applied_features = orm.relationship(
    FinancialAccountPremiumScheduleFeature,
    primaryjoin = FinancialAccountPremiumScheduleHistory.history_of_id==orm.foreign(FinancialAccountPremiumScheduleFeature.applied_on_id),
    viewonly=True,
)

class FinancialTransactionPremiumScheduleFeature(AbstractFeatureApplicability):
    using_options(tablename='financial_transaction_premium_feature', order_by=['premium_from_date', 'described_by'])
    applied_on = ManyToOne('FinancialTransactionPremiumSchedule', required = True, ondelete = 'restrict', onupdate = 'cascade')
    described_by = schema.Column( camelot.types.Enumeration(transaction_features_enumeration), nullable=False, default='redemption_rate')
    premium_period_type = schema.Column(camelot.types.Enumeration([(0,None)] + period_types), default=None, nullable=True)
    comment = schema.Column( camelot.types.RichText() )


