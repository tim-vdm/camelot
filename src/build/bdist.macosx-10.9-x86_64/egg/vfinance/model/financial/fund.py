import datetime
import logging

logger = logging.getLogger('vfinance.model.financial.fund')

import sqlalchemy.types
from sqlalchemy import sql, schema, orm

from camelot.admin.action import list_filter
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.model.authentication import end_of_times
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import ( Entity, ManyToOne, using_options, 
                               ColumnProperty )

from .constants import transaction_distribution_fund_percentage_editable
from .premium import (FinancialAccountPremiumSchedule,
                      financial_account_premium_schedule_table,
                      FinancialAccountPremiumScheduleHistory)
from .security import FinancialFund, FinancialSecurity, FinancialSecurityQuotation
from ...sql import datetime_to_date
from vfinance.model.bank.entry import Entry
from vfinance.model.bank.statusmixin import BankRelatedStatusAdmin
from vfinance.admin.vfinanceadmin import VfinanceAdmin


class FundDistributionMixin(object):
    
    def get_fund_choices(self):
        fund_choices = [(None, '')]
        if self.distribution_of is not None:
            product = self.distribution_of.get_product()
            if product is not None:
                for available_fund in product.available_funds:
                    fund = available_fund.fund
                    fund_choices.append( (fund, fund.name) )
        fund_choices.sort(key=lambda fc:fc[1])
        return fund_choices
    
class FinancialAgreementFundDistribution(Entity, FundDistributionMixin):
    using_options(tablename='financial_agreement_fund_distribution')
    distribution_of = ManyToOne('vfinance.model.financial.premium.FinancialAgreementPremiumSchedule', required = True, ondelete = 'cascade', onupdate = 'cascade')
    fund = ManyToOne('vfinance.model.financial.security.FinancialSecurity', required = True, ondelete = 'restrict', onupdate = 'cascade')
    target_percentage = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False, default=0)
    
    @property
    def from_date(self):
        if self.distribution_of is not None:
            return self.distribution_of.from_date
        return None

    @property
    def thru_date(self):
        if self.distribution_of is not None:
            return self.distribution_of.thru_date
        return None

    @property
    def value_on_agreement(self):
        if self.fund and self.distribution_of.valid_from_date:
            return self.fund.value_at( self.distribution_of.valid_from_date ) or 0
        return 0
    
    @property
    def value_known_on_agreement_date(self):
        if self.fund and self.distribution_of.valid_from_date and self.fund.value_at( self.distribution_of.valid_from_date )!=None:
            return True
        return False
        
    class Admin(EntityAdmin):
        verbose_name = _('Financial Agreement Fund')
        list_display = ['fund', 'target_percentage', 'value_on_agreement']
        field_attributes = {'fund':{'minimal_column_width':35,
                                    'choices':lambda fafd:fafd.get_fund_choices(),
                                    'target':FinancialFund},
                            'value_on_agreement':{'delegate':delegates.CurrencyDelegate},
                            'value_known_on_agreement_date':{'delegate':delegates.BoolDelegate,
                                                             'name':_('Value known')},
                            }
        
        def get_depending_objects(self, obj):
            if obj.distribution_of:
                yield obj.distribution_of
                yield obj.distribution_of.financial_agreement
                
class FinancialAccountFundDistribution(Entity, FundDistributionMixin):

    __tablename__ = 'financial_account_fund_distribution'

    distribution_of_id = schema.Column(sqlalchemy.types.Integer(),
                                       schema.ForeignKey(financial_account_premium_schedule_table.c.id, ondelete='cascade', onupdate='cascade'),
                                       nullable = False,
                                       index = True)
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    fund_id = schema.Column(sqlalchemy.types.Integer(),
                            schema.ForeignKey(FinancialSecurity.id, ondelete='restrict', onupdate='cascade'),
                            nullable = False,
                            index = True)
    fund = orm.relationship(FinancialSecurity)
    target_percentage = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False, default=0)
       
    @staticmethod
    def full_account_number_for_fund(premium_schedule, fund):
        product = premium_schedule.product
        if product is not None:
            if product.fund_number_digits:
                args = ( product.account_number_prefix, 
                         product.fund_number_digits, 
                         fund.account_number, 
                         product.account_number_digits or 1, 
                         premium_schedule.account_suffix )
                fmt = u'%s%0*i%0*i'
            else:
                args = ( product.account_number_prefix, 
                         product.account_number_digits or 1, 
                         premium_schedule.account_suffix )
                fmt = u'%s%0*i'
            if None not in args:
                return fmt%args
    
    @property
    def full_account_number(self):
        if None not in (self.distribution_of, self.fund):
            return self.full_account_number_for_fund(self.distribution_of,
                                                     self.fund)
            
    @staticmethod
    def financial_security_name_query( columns ):
        return sql.select( [FinancialSecurity.name],
                           whereclause = FinancialSecurity.id==columns.fund_id )
        
    def value_and_quantity_at_query(self, value_date, application_date):
        
        return sql.select( [sql.func.sum( Entry.amount * -1 ), sql.func.sum( Entry.quantity ) / 1000 ],
                           whereclause = sql.and_( Entry.account == self.full_account_number,
                                                   Entry.book_date <= application_date,
                                                   Entry.datum <= value_date ) )
          
    @ColumnProperty
    def financial_security_name( self ):
        return FinancialAccountFundDistribution.financial_security_name_query(self)
        
    def attribute_premium_to_fund(self, book_date):
        """Convert the premium value to fund units.
        
        :return: a list of FinancialAccountPremiumFulfillments that were generated
        """
        fulfillments = []
        for order in self.ordered_with:
            fulfillment = order.attribute_premium_to_fund(book_date)
            if fulfillment:
                fulfillments.append( fulfillment )
        return fulfillments
        
    class Admin(VfinanceAdmin):
        verbose_name = _('Financial Account Fund')
        list_display = ['distribution_of_id', 'full_account_number', 'fund', 'target_percentage', 'from_date', 'thru_date']
        list_filter = [list_filter.ComboBoxFilter('financial_security_name')]
        form_display = list_display
        field_attributes = {'fund':{'minimal_column_width':45,
                                    'choices':lambda fafd:fafd.get_fund_choices(),},
                            'distribution_of_id': {'name': 'Premium schedule id'},
                            }
        list_actions = []

        def get_query(self, *args, **kwargs):
            query = VfinanceAdmin.get_query(self, *args, **kwargs)
            query = query.options(orm.subqueryload('distribution_of'))
            return query

class FundDistributionPremiumScheduleAdmin(FinancialAccountFundDistribution.Admin):
    list_display = ['full_account_number', 'fund', 'target_percentage', 'from_date', 'thru_date']
    form_display = list_display

FinancialAccountFundDistribution.distribution_of = orm.relationship(
    FinancialAccountPremiumSchedule,
    backref=orm.backref('fund_distribution', order_by=[FinancialAccountFundDistribution.id], cascade='all, delete, delete-orphan')
)

FinancialAccountPremiumSchedule.last_quotation = ColumnProperty(lambda ps:
    sql.select([sql.func.max(datetime_to_date(FinancialSecurityQuotation.from_datetime))],
    whereclause = sql.and_(FinancialSecurityQuotation.current_status=='verified',
                           datetime_to_date(FinancialSecurityQuotation.from_datetime) <= sql.func.current_date(),
                           FinancialAccountFundDistribution.fund_id == FinancialSecurityQuotation.financial_security_id,
                           FinancialAccountFundDistribution.distribution_of_id==ps.id
                           ),
    ),
    deferred=True
    )

FinancialAccountPremiumScheduleHistory.fund_distribution = orm.relationship(
    FinancialAccountFundDistribution,
    primaryjoin = FinancialAccountPremiumScheduleHistory.history_of_id==orm.foreign(FinancialAccountFundDistribution.distribution_of_id),
    viewonly=True,
    order_by=[FinancialAccountFundDistribution.id]
)

class FinancialTransactionFundDistribution(Entity, FundDistributionMixin):
    using_options(tablename='financial_transaction_fund_distribution')
    distribution_of = ManyToOne('vfinance.model.financial.transaction.FinancialTransactionPremiumSchedule', required = True, ondelete = 'cascade', onupdate = 'cascade')
    fund = ManyToOne('vfinance.model.financial.security.FinancialSecurity', required = True, ondelete = 'restrict', onupdate = 'cascade')
    target_percentage = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False, default=0)
    change_target_percentage = schema.Column( sqlalchemy.types.Boolean(), nullable=False, default=False)
    new_target_percentage = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False, default=0)
               
    @property
    def full_account_number(self):
        if self.distribution_of and self.distribution_of and self.fund:
            return FinancialAccountFundDistribution.full_account_number_for_fund( self.distribution_of.premium_schedule, self.fund )
        
    class Admin(BankRelatedStatusAdmin):
        def ftfd_editable(obj):
            if obj and obj.distribution_of:
                return transaction_distribution_fund_percentage_editable[obj.distribution_of.described_by]
            return False
            
        verbose_name = _('Financial Transaction Fund Fistribution')
        list_display = ['fund', 'target_percentage', 'change_target_percentage', 'new_target_percentage']
        field_attributes = {'fund':{'minimal_column_width':45,
                                    'choices':lambda fafd:fafd.get_fund_choices(),},
                            'change_target_percentage':{'editable':False},
                            'new_target_percentage':{'editable':False},
                            'target_percentage':{'editable':ftfd_editable} }
                            
        def get_related_status_object(self, obj):
            if obj.distribution_of is not None:
               return obj.distribution_of.within               
            return None
