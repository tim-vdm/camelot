import functools

import sqlalchemy.types
from sqlalchemy import sql, schema, orm
from sqlalchemy.ext.declarative import declared_attr

from camelot.admin.action.list_action import ExportSpreadsheet
from camelot.admin.entity_admin import EntityAdmin
from camelot.admin import table
from camelot.core.orm import ColumnProperty
from camelot.core.utils import ugettext_lazy as _
from camelot.model.authentication import end_of_times
import camelot.types

from .constants import fulfillment_types
from .entry import Entry
from .visitor import VisitorMixin
from .invoice import InvoiceItem

from camelot.core.qt import Qt


class AbstractFulfillment(object):
    """Relates an Entry to parts of the model
    """
    entry_book_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True)
    entry_document = schema.Column(sqlalchemy.types.Integer(), nullable=False, index=True)
    entry_book = schema.Column(sqlalchemy.types.Unicode(25), nullable=False, index=True)
    entry_line_number = schema.Column(sqlalchemy.types.Integer(), nullable=False, index=True)
    fulfillment_type = schema.Column(camelot.types.Enumeration(fulfillment_types))    
    amount_distribution = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
    from_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True, default=sql.func.current_date())
    thru_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True, default=end_of_times)

    @declared_attr
    def booking_of_id(self):
        return schema.Column('booking_of_id',
                             sqlalchemy.types.Integer(),
                             schema.ForeignKey(InvoiceItem.id,
                                               onupdate='cascade',
                                               ondelete='restrict'),
                             nullable=True,
                             index=True)

    @property
    def entry_key(self):
        """A key unique to the entry this fulfillment entry points to"""
        return (self.entry_book_date, self.entry_book, self.entry_document, self.entry_line_number)

    def __unicode__(self):
        return unicode( self.entry_key )

    @classmethod
    def entry_fields_query( cls, fulfillment_columns, entry_columns, entry_field_names):
        return sql.select( [getattr(entry_columns,  entry_field_name) for entry_field_name in entry_field_names],
                           VisitorMixin.entry_from_fulfillment_condition( fulfillment_columns,
                                                                 entry_columns) )

    @property
    def entry(self):
        return Entry.query.filter( VisitorMixin.entry_from_fulfillment_condition(self, Entry) ).first()

    class Admin(EntityAdmin):
        relation_fields = ['id', 'entry_doc_date', 'account', 'amount', 'fulfillment_type', 'amount_distribution', 'associated_to_id', 'within_id', 'from_date', 'thru_date']
        entry_fields = ['entry_book_date', 'entry_book', 'entry_document', 'entry_line_number', 'presence', 'entry_creation_date']
        verbose_name = _('Entry track')
        list_display = [table.ColumnGroup( 'Relation', relation_fields ),
                        table.ColumnGroup( 'Entry', entry_fields ) ]

        def get_related_toolbar_actions( self, toolbar_area, direction ):
            if toolbar_area == Qt.RightToolBarArea:
                return [ExportSpreadsheet()] + self.list_actions
            return []

def add_entry_fields(FulfillmentClass):
    """
    Adds related fields from Entry to subclasses of AbstractFulfillment
    """

    def entry_field(entry_field_name, columns):
        entry = orm.aliased( Entry )
        return AbstractFulfillment.entry_fields_query(columns, entry.table.c , [entry_field_name])

    def presence(columns):
        entry = orm.aliased( Entry )
        return sql.select( [sql.func.count(entry.id)],
                           VisitorMixin.entry_from_fulfillment_condition(columns, entry) )

    FulfillmentClass.presence = ColumnProperty( presence, deferred=True )
    FulfillmentClass.entry_doc_date = ColumnProperty(functools.partial(entry_field, 'datum'), deferred=True, group = 'entry')
    FulfillmentClass.entry_creation_date = ColumnProperty(functools.partial(entry_field, 'creation_date'), deferred=True, group = 'entry')
    FulfillmentClass.account = ColumnProperty(functools.partial(entry_field, 'account'), deferred=True, group = 'entry')
    FulfillmentClass.amount = ColumnProperty(functools.partial(entry_field, 'amount'), deferred=True, group = 'entry')
    FulfillmentClass.open_amount = ColumnProperty(functools.partial(entry_field, 'open_amount'), deferred=True, group = 'entry')
    FulfillmentClass.quantity = ColumnProperty(functools.partial(entry_field, 'quantity'), deferred=True, group = 'entry')
    
    return FulfillmentClass
    