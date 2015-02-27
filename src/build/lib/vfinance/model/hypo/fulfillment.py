from ..bank.fulfillment import AbstractFulfillment, add_entry_fields
from ..bank.admin import RelatedEntries

from camelot.admin.not_editable_admin import not_editable_admin
from camelot.core.orm import Entity, using_options, ManyToOne, ColumnProperty

from sqlalchemy import orm, sql

from .beslissing import GoedgekeurdBedrag
from .dossier import Dossier
from .wijziging import Wijziging
from ..bank.product import Product
from ..bank.invoice import InvoiceItem

@add_entry_fields
class MortgageFulfillment( Entity, AbstractFulfillment ):
    using_options(tablename='hypo_loan_schedule_fulfillment', order_by=['id'])
    of = ManyToOne(GoedgekeurdBedrag, required=True, ondelete = 'restrict', onupdate = 'cascade')
    booking_of = orm.relationship(InvoiceItem, backref='bookings')
    within = ManyToOne(Wijziging, required=False, ondelete = 'restrict', onupdate = 'cascade')

    def account_suffix(self):
        query =  sql.select([(Dossier.nummer*sql.func.pow(10, Product.rank_number_digits)) + Dossier.rank])
        query = query.where(Dossier.goedgekeurd_bedrag_id==self.of_id)
        query = query.where(GoedgekeurdBedrag.id==Dossier.goedgekeurd_bedrag_id)
        query = query.where(GoedgekeurdBedrag.product_id==Product.id)
        return query

    account_suffix = ColumnProperty( account_suffix, deferred=True )

    def account_number_prefix(self):
        pr = orm.aliased(Product)
        query =  sql.select([pr.account_number_prefix])
        query = query.where(GoedgekeurdBedrag.id==self.of_id)
        query = query.where(GoedgekeurdBedrag.product_id==pr.id)
        return query

    account_number_prefix = ColumnProperty( account_number_prefix, deferred=True )

    @property
    def product_name(self):
        return self.of.product.name
    
    Admin = not_editable_admin( AbstractFulfillment.Admin )

MortgageFulfillment.associated_to = ManyToOne(MortgageFulfillment) # slows things down, backref='associated')

GoedgekeurdBedrag.Admin.form_actions.append(RelatedEntries(MortgageFulfillment))
