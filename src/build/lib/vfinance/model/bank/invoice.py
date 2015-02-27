import datetime
import logging

from sqlalchemy import schema, orm, sql
from sqlalchemy.ext import hybrid
import sqlalchemy.types

from camelot.core.exception import UserException
from camelot.core.orm import Entity, ManyToOne, using_options
from camelot.admin.entity_admin import EntityAdmin
from camelot.admin.action import CallMethod
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import transaction
from camelot.view import forms
from camelot.view.controls import delegates
import camelot.types

from ..bank.statusmixin import BankRelatedStatusAdmin

LOGGER = logging.getLogger('vfinance.model.bank.invoice')

from .constants import invoice_item_states

class InvoiceItem(Entity):
    """This entity refers to the InvoiceItem Entity on figure 5.13 p. 229
    in the Premium Schedule overview.

    Each invoice item may be incorporated into an invoice.

    Kosten die van toepassing zijn op een lopend dossier"""
    using_options(tablename='bank_invoice_item', order_by=['doc_date'])
    item_description  =  schema.Column(sqlalchemy.types.Unicode(250), nullable=False)
    origin  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    amount =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False)
    doc_date =  schema.Column(sqlalchemy.types.Date(), nullable=False, default=datetime.date.today)
    #
    # An invoice item might find its origin either in a mortgage dossier
    # or in a FinancialAccount
    #
    dossier_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=True, index=True)
    dossier  =  ManyToOne('vfinance.model.hypo.dossier.Dossier', field=dossier_id)
    status = schema.Column(camelot.types.Enumeration(invoice_item_states), nullable=False, default='to_send')
    #
    # Polymorphic definition
    #
    row_type = schema.Column(sqlalchemy.types.Unicode(40), nullable = False, index=True)
    __table_args__ = (schema.CheckConstraint('dossier_id is not null or premium_schedule_id is not null',
                                             name='invoice_item_schedule'),
                      #schema.CheckConstraint('''(entry_document is not null and entry_line_number is not null and entry_book is not null and entry_book_type is not null) or'''
                                             #'''(entry_document is null and entry_line_number is null and entry_book is null and entry_book_type is null)''',
                                              #name='invoice_item_entry'),
                      )
    __mapper_args__ = {'polymorphic_on' : row_type,
                       'polymorphic_identity': 'invoice_item'}

    @property
    def full_account_number(self):
        if self.premium_schedule is not None:
            return self.premium_schedule.full_account_number

    @property
    def entry_ticked(self):
        return self.open_amount == 0

    def get_open_amount(self):
        #
        # Zoek voor een vervaldag de overeenkomstige betaling, en neem dan
        # hiervan de open amount.  Als er geen betaling gevonden is, veronderstellen
        # we dat er nog nt gesynct is, en dat het volledige bedrag open staat.
        #
        # Open amount zou ook rechtstreeks van het venice doc kunnen worden
        # genomen, maar bij een juist aangemaakt venice doc is dat nog nt ingevuld
        #
        if self.booked_amount == 0:
            return self.amount - self.get_reduction()
        # booking.open_amount might be None when there is no entry for the booking
        return sum(((booking.open_amount or 0) for booking in self.bookings if booking.entry_line_number==1), 0)

    @property
    def open_amount(self):
        return self.get_open_amount()
    
    @property
    def booked_amount(self):
        # booking.amount might be None when there is no entry for the booking
        return sum(((booking.amount or 0) for booking in self.bookings if booking.entry_line_number==1), 0) 

    @property
    def laatste_domiciliering(self):
        if self.last_direct_debit_request_at:
            return 'batch {0.last_direct_debit_batch_id} : {0.last_direct_debit_request_at}'.format(self)

    @property
    def last_direct_debit_batch(self):
        from .direct_debit import DirectDebitBatch
        if self.last_direct_debit_batch_id:
            return orm.object_session(self).query(DirectDebitBatch).get(self.last_direct_debit_batch_id)

    @property
    def last_direct_debit_status(self):
        last_direct_debit_batch = self.last_direct_debit_batch
        if last_direct_debit_batch is not None:
            return last_direct_debit_batch.current_status

    @transaction
    def button_voeg_toe_aan_domiciliering(self):
        return self.voeg_toe_aan_domiciliering()

    def get_reduction(self):
        return 0

    def get_mandate(self):
        """
        :param: the direct debit mandate, valid at the doc date of the invoice
        """
        dossier = self.dossier or self.premium_schedule.financial_account
        return dossier.get_direct_debit_mandate_at(self.doc_date)

    def voeg_toe_aan_domiciliering(self, direct_debit_period=0):
        """:param direct_debit_period: number of days between direct debit and invoice date"""
        from .direct_debit import DirectDebitBatch
        dossier = self.dossier or self.premium_schedule.financial_account
        mandate = self.get_mandate()
        if mandate is None:
            raise UserException('No direct debit mandate at {}'.format(self.doc_date))
        batch_type = dossier.get_functional_setting_description_at( self.doc_date, 'direct_debit_batch' )
        requested_collection_date = self.doc_date - datetime.timedelta(days=direct_debit_period)
        batch = DirectDebitBatch.get_open_direct_debit_batch(described_by=mandate.described_by,
                                                             spildatum=requested_collection_date,
                                                             batch = batch_type)
        if batch.direct_debit_item_for(self) is None:
            return batch.append_invoice_items(mandate, max(requested_collection_date, batch.spildatum), self.item_description, [self])

    def __unicode__(self):
        return u'%s, %s'%(self.item_description or '', self.amount or '')

    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Invoice item')
        verbose_name_plural = _('Invoice items')
        list_display =  ['doc_date', 'row_type', 'item_description', 'amount', 'laatste_domiciliering']
        additional_tabs = [(_('Booking'), ['bookings']),
                           (_('Schedule'), ['dossier', 'premium_schedule']),
                           (_('Collection'), ['collected_via']),
                           ]
        form_display = forms.TabForm([(_('Invoice'), forms.Form(list_display + ['booked_amount'], columns=2)),] + additional_tabs)
        form_actions = [
            CallMethod( _('Domicilieer'),
                        lambda obj:obj.button_voeg_toe_aan_domiciliering(),), ]
        field_attributes = {'booked_amount':{'editable':False, 'name':_('Booked'),'delegate':delegates.FloatDelegate, 'precision':2},
                            'open_amount':{'editable':False, 'name':_('Open'), 'delegate': delegates.FloatDelegate, 'precision': 2},
                            'row_type': {'editable': False, 'name': _('Type'),},
                            'premium_schedule':{'editable':False, 'name':_('Premium')},
                            'dossier':{'editable':False, 'name':_('Dossier')},
                            'bookings':{'editable':False,},
                            'laatste_domiciliering':{'editable':False, 'name': _('Last direct debit'),},
        }
        
        def delete(self, invoice_item):
            if len(invoice_item.bookings):
                raise UserException('Cannot delete while booked')
            if len(invoice_item.collected_via):
                raise UserException('Cannot delete while present in direct debit batch')
            EntityAdmin.delete(self, invoice_item)
            
        def get_related_status_object(self, obj):
            if obj.premium_schedule is not None:
                return obj.premium_schedule.financial_account
            return None

InvoiceItem.modifier_of_id = schema.Column(
    sqlalchemy.types.Integer(),
    schema.ForeignKey(InvoiceItem.id,ondelete='restrict', onupdate='cascade'),
    index=True,)

InvoiceItem.modified_by = orm.relationship(
    InvoiceItem, cascade='all',
    foreign_keys = [InvoiceItem.modifier_of_id],
    backref=orm.backref('modifier_of', remote_side=[InvoiceItem.id])
)

InvoiceItem.related_to_id = schema.Column(
    sqlalchemy.types.Integer(),
    schema.ForeignKey(InvoiceItem.id,ondelete='restrict', onupdate='cascade'),
    index=True,)

InvoiceItem.related = orm.relationship(
    InvoiceItem,
    foreign_keys = [InvoiceItem.related_to_id],
    backref=orm.backref('related_to', remote_side=[InvoiceItem.id])
)

def related_doc_date_fget(self):
    if self.related_to is not None:
        return self.related_to.doc_date

related_invoice_item_table = sql.alias(InvoiceItem.__table__)

def related_doc_date_expr(self):
    return sql.select([related_invoice_item_table.c.doc_date]).where(related_invoice_item_table.c.id==self.related_to_id).label('related_doc_date')

InvoiceItem.related_doc_date = hybrid.hybrid_property(
    fget=related_doc_date_fget,
    expr=related_doc_date_expr)

InvoiceItem.Admin.field_attributes['related_doc_date'] = {'delegate': delegates.DateDelegate}


class HypoInvoiceItemAdmin(InvoiceItem.Admin):
    list_display = ['doc_date', 'row_type', 'dossier', 'item_description', 'amount', 'laatste_domiciliering']
    
    def get_query(self, *args, **kwargs):
        query = super(HypoInvoiceItemAdmin, self).get_query(*args, **kwargs)
        return query.filter(InvoiceItem.dossier_id!=None)

class FinancialInvoiceItemAdmin(InvoiceItem.Admin):
    list_display = ['premium_schedule_id', 'full_account_number', 'doc_date', 'row_type', 'item_description', 'amount', 'laatste_domiciliering']
    
    def get_subclass_tree(self):
        return []

    def get_query(self, *args, **kwargs):
        query = super(FinancialInvoiceItemAdmin, self).get_query(*args, **kwargs)
        query = query.options(orm.subqueryload('premium_schedule'))
        return query.filter(InvoiceItem.premium_schedule_id!=None)
