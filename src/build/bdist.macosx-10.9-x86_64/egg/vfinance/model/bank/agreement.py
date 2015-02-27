"""
Classes common to a FinancialAgreement and a HypoApplication
"""

from sqlalchemy import schema, types, orm
from camelot.core.orm import Entity
from sqlalchemy.ext.declarative import declared_attr

from .rechtspersoon import Rechtspersoon
from .dual_person import CommercialRelation

class AbstractAgreement(Entity):
    """Common persisted attributes of a FinancialAgreement and a HypoApplication
    """
    
    __abstract__ = True
    
    @declared_attr
    def broker_relation_id(cls):
        return schema.Column('broker_relation_id',
                             types.Integer(),
                             schema.ForeignKey(CommercialRelation.id,
                                               ondelete='restrict',
                                               onupdate='cascade'),
                             nullable=True,
                             index=True)

    @declared_attr
    def broker_agent_id(cls):
        return schema.Column('broker_agent_id',
                             types.Integer(),
                             schema.ForeignKey(Rechtspersoon.id,
                                               ondelete='restrict',
                                               onupdate='cascade'),
                             nullable=True,
                             index=True)
    
    @declared_attr
    def broker_relation(cls):
        return orm.relationship(CommercialRelation)
    
    @declared_attr
    def broker_agent(cls):
        return orm.relationship(Rechtspersoon)

    origin = schema.Column(types.Unicode(50), nullable=True)


