'''
Created on Oct 6, 2010

@author: tw55413
'''
import sqlalchemy.types
from sqlalchemy import schema, orm

import camelot.types

from camelot.admin.entity_admin import EntityAdmin
from camelot.core.orm import Entity, ManyToOne

from ..bank.constants import commission_receivers, product_features_suffix
from ..bank.statusmixin import BankRelatedStatusAdmin
from .premium import (financial_account_premium_schedule_table,
                      FinancialAccountPremiumSchedule,
                      FinancialAccountPremiumScheduleHistory)
from constants import commission_types

def distribution_suffix(o):
    return product_features_suffix.get(o.described_by, '%')

class FinancialAgreementCommissionDistribution( Entity ):

    __tablename__ = 'financial_agreement_commission_distribution'

    premium_schedule = ManyToOne('vfinance.model.financial.premium.FinancialAgreementPremiumSchedule', onupdate='cascade', ondelete='cascade', required=True)
    described_by = schema.Column( camelot.types.Enumeration(commission_types), nullable=False, default=commission_types[0][1] )
    recipient = schema.Column( camelot.types.Enumeration(commission_receivers), nullable=False, default=commission_receivers[0][1] )
    distribution = schema.Column( sqlalchemy.types.Numeric(17,5), nullable=False )
    comment = schema.Column( sqlalchemy.types.Unicode(256) )
    
    class Admin( EntityAdmin ):
        list_display = ['described_by', 'recipient', 'distribution', 'comment']
        field_attributes = {'distribution':{'suffix':distribution_suffix}}

        def get_depending_objects(self, obj):
            if obj.premium_schedule:
                if obj.premium_schedule.financial_agreement:
                    yield obj.premium_schedule.financial_agreement
                        
class FinancialAccountCommissionDistribution( Entity ):

    __tablename__ = 'financial_account_commission_distribution'

    premium_schedule_id = schema.Column(sqlalchemy.types.Integer(),
                                        schema.ForeignKey(financial_account_premium_schedule_table.c.id,
                                                          ondelete='cascade',
                                                          onupdate='cascade'),
                                        nullable=False)
    premium_schedule = orm.relationship(
        FinancialAccountPremiumSchedule,
        backref = orm.backref('commission_distribution', cascade='all, delete, delete-orphan'),
    )
    described_by = schema.Column( camelot.types.Enumeration(commission_types), nullable=False, default=commission_types[0][1] )
    recipient = schema.Column( camelot.types.Enumeration(commission_receivers), nullable=False, default=commission_receivers[0][1] )
    distribution = schema.Column( sqlalchemy.types.Numeric(17,5), nullable=False )
    comment = schema.Column( sqlalchemy.types.Unicode(256) )

    class Admin(BankRelatedStatusAdmin):
        list_display = ['described_by', 'recipient', 'distribution', 'comment']
        field_attributes = {'distribution':{'suffix':distribution_suffix}}

        def get_related_status_object(self, obj):
            if obj.premium_schedule is not None:
                return obj.premium_schedule.financial_account
            return None

FinancialAccountPremiumScheduleHistory.commission_distribution = orm.relationship(
    FinancialAccountCommissionDistribution,
    primaryjoin = orm.foreign(FinancialAccountCommissionDistribution.premium_schedule_id)==FinancialAccountPremiumScheduleHistory.history_of_id,
    viewonly=True,
)
