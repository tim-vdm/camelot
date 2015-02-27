import copy
from decimal import Decimal as D
import logging
import sqlalchemy.types
from sqlalchemy import orm, schema

from camelot.core.exception import UserException
from camelot.admin.entity_admin import EntityAdmin
from camelot.admin.action import Action, list_filter
from camelot.admin.object_admin import ObjectAdmin
from camelot.view.controls import delegates
from camelot.view import forms, action_steps
from camelot.core.utils import ugettext_lazy as _

from vfinance.admin.vfinanceadmin import VfinanceAdmin
from vfinance.model.bank.direct_debit import DirectDebitBatch, DirectDebitInvoice
from vfinance.model.bank.invoice import InvoiceItem
from vfinance.model.financial.formulas import round_up
from .constants import reminder_levels
from .periodieke_verichting import (BookInvoiceItem, UnbookInvoiceItem, 
                                    CancelInvoiceItem, SendInvoiceItem)

from notification.rappel_sheet import RappelSheet
from notification.rappel_letter import RappelLetter
from .dossier import Dossier

logger = logging.getLogger('vfinance.model.hypo.rappel_brief')


class RappelOpenstaandeBetaling(InvoiceItem):
    """Een entry in een rappel brief dat refereert naar een openstaande betaling"""

    __mapper_args__ = {'polymorphic_identity': 'payment_reminder'}
    __tablename__ = None

    def get_open_amount(self):
        return -1 * self.amount

    class Admin(EntityAdmin):
        verbose_name = _('Openstaande betaling')
        verbose_name_plural = _('Openstaande betalingen')
        list_display =  ['doc_date', 'amount', 'item_description']
        form_display =  forms.Form(list_display, columns=2)

#  credit_header_desc
#  credit_header_data
rappel_levels = ['Normaal', 'Streng', 'Ingebrekestelling', 'Opzegging krediet']
#  sales_line_data
#  rappel_sheet_klant

class DirectDebitInvoiceProposal(object):

    verbose_name_plural = _('Direct debit proposals')

    def __init__(self, invoice_item, direct_debit_amount):
        self.invoice_item = invoice_item
        self.doc_date = invoice_item.doc_date
        self.row_type = invoice_item.row_type
        self.item_description = invoice_item.item_description
        self.last_direct_debit = invoice_item.laatste_domiciliering
        self.open_amount = invoice_item.open_amount
        self.direct_debit_amount = direct_debit_amount

    class Admin(ObjectAdmin):
        list_display = ['doc_date',
                        'row_type',
                        'item_description',
                        'last_direct_debit',
                        'open_amount',
                        'direct_debit_amount']
        field_attributes = {'doc_date': {'delegate': delegates.DateDelegate},
                            'open_amount': {'delegate': delegates.FloatDelegate},
                            'direct_debit_amount': {'editable': True, 
                                                    'delegate': delegates.FloatDelegate}}

class AppendToDirectDebitBatch(Action):

    verbose_name = _('Direct debit')

    def model_run(self, model_context):
        yield action_steps.UpdateProgress(text='Search')
        for reminder in model_context.get_selection():
            proposals = []
            for dossier_reminder in reminder.dossier.rappelbrief:
                if dossier_reminder.open_amount:
                    proposals.append(DirectDebitInvoiceProposal(dossier_reminder,
                                                                dossier_reminder.open_amount or 0))
            for repayment_reminder in reminder.openstaande_vervaldag:
                proposals.append(DirectDebitInvoiceProposal(repayment_reminder,
                                                            repayment_reminder.open_amount or 0))
                if repayment_reminder.related_to is not None:
                    proposals.append(DirectDebitInvoiceProposal(repayment_reminder.related_to,
                                                                repayment_reminder.te_betalen - repayment_reminder.intrest_a - repayment_reminder.intrest_b))
                yield action_steps.ChangeObjects(proposals,
                                                 model_context.admin.get_related_admin(DirectDebitInvoiceProposal))
            with model_context.session.begin():
                mandate = reminder.get_mandate()
                if mandate is None:
                    raise UserException('No direct debit mandate')
                batch_type = reminder.dossier.get_functional_setting_description_at(reminder.doc_date, 'direct_debit_batch')
                batch = DirectDebitBatch.get_open_direct_debit_batch(described_by=mandate.described_by,
                                                                     spildatum=reminder.doc_date,
                                                                     batch = batch_type)
                if len(proposals) and sum((p.direct_debit_amount for p in proposals), 0) != 0:
                    direct_debit_item = batch.append_item(mandate, reminder.doc_date, reminder.item_description)
                    for proposal in proposals:
                        if proposal.direct_debit_amount:
                            DirectDebitInvoice(of=proposal.invoice_item, via=direct_debit_item, amount=proposal.direct_debit_amount)
                yield action_steps.FlushSession(model_context.session)


class RappelBrief( InvoiceItem ):
    kosten_rappelbrieven  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
    rappel_level  =  schema.Column(sqlalchemy.types.Integer(), nullable=True, default=1)

    __mapper_args__ = {'polymorphic_identity': 'reminder'}
    __tablename__ = None

    @property
    def full_number(self):
        if self.dossier is not None:
            return self.dossier.full_number

    # methods needed for the invoice item visitor
    @classmethod
    def get_book(self, product):
        return product.get_book_at('additional_cost', None)

    @property
    def saldo_vervaldagen( self ):
        return sum( (D(v.te_betalen or 0) for v in self.openstaande_vervaldag), D(0) )

    @property
    def saldo_betalingen( self ):
        return round_up( sum( (D(b.amount or 0) for b in self.openstaande_betaling), D(0) ) )

    @property
    def intrest_a( self ):
        return round_up( sum( (D(v.intrest_a or 0) for v in self.openstaande_vervaldag), D(0) ) )

    @property
    def intrest_b( self ):
        return round_up( sum( (D(v.intrest_b or 0) for v in self.openstaande_vervaldag), D(0) ) )

    @property
    def openstaand_saldo( self ):
        return (self.saldo_vervaldagen or 0) - (self.saldo_betalingen or 0) + (self.kosten_rappelbrieven or 0) + (self.amount or 0)

    @property
    def som_openstaande_betalingen( self ):
        if self.dossier:
            return self.dossier.som_openstaande_betalingen
        return 0

    def __unicode__(self):
        if self.dossier is not None:
            return unicode(self.dossier)

    class Admin(InvoiceItem.Admin):

        def get_query(self, *args, **kwargs):
            query = VfinanceAdmin.get_query(self, *args, **kwargs)
            query = query.options(orm.subqueryload('dossier'))
            query = query.options(orm.subqueryload('bookings'))
            query = query.options(orm.undefer('last_direct_debit_request_at'))
            query = query.options(orm.undefer('last_direct_debit_batch_id'))
            return query

        verbose_name = _('Rappel Brief')
        verbose_name_plural = _('Rappel Brieven')
        list_display =  ['doc_date',
                         'rappel_level',
                         'full_number',
                         'amount',
                         'status',
                         'booked_amount',
                         'laatste_domiciliering']
        list_filter = ['status', list_filter.ComboBoxFilter('dossier.company_id', verbose_name=_('Maatschappij'))]
        form_display = forms.TabForm( [(_('Reminder'),
                                        forms.Form(['dossier','doc_date',
                                                    'rappel_level', 'amount',
                                                    'saldo_vervaldagen','saldo_betalingen',
                                                    'intrest_a','intrest_b',
                                                    'kosten_rappelbrieven', 'openstaand_saldo',
                                                    'status', 
                                                    'openstaande_vervaldag', 'openstaande_betaling'],
                                                    columns=2),)] + InvoiceItem.Admin.additional_tabs )
        form_actions = [ RappelSheet(),
                         RappelLetter(),
                         AppendToDirectDebitBatch(),
                         BookInvoiceItem(),
                         UnbookInvoiceItem(),
                         CancelInvoiceItem(),
                         SendInvoiceItem(),
                         ]
        list_actions = form_actions
        field_attributes = copy.copy(InvoiceItem.Admin.field_attributes)
        field_attributes['saldo_vervaldagen'] = {'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Saldo vervaldagen')}
        field_attributes['dossier'] = {'editable': False, 'name':_('Dossier')}
        field_attributes['full_number'] = {'name': _('Dossier nummer')}
        field_attributes['status'] = {'editable':False, 'name':_('Status')}
        field_attributes['openstaand_saldo'] = {'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Openstaand saldo')}
        field_attributes['som_openstaande_betalingen'] = {'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Openstaande betalingen')}
        field_attributes['rappel_level'] = {'name':_('Rappel niveau'), 'choices':reminder_levels}
        field_attributes['saldo_betalingen'] = {'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Saldo betalingen')}
        field_attributes['openstaande_vervaldag'] = {'editable':True, 'name':_('Openstaande vervaldagen')}
        field_attributes['openstaande_betaling'] = {'editable':True, 'name':_('Openstaande betalingen')}
        field_attributes['intrest_a'] = {'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Intrest a')}
        field_attributes['intrest_b'] = {'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Intrest b')}
        field_attributes['amount'] = {'name': 'Kost brief'}


Dossier.Admin.field_attributes['rappelbrief'] = {'target':RappelBrief, 'name': _('Rappelbrieven')}

class RappelOpenstaandeVervaldag( InvoiceItem ):
    afpunt_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    te_betalen  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
    intrest_a  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
    intrest_b  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)

    __mapper_args__ = {'polymorphic_identity': 'repayment_reminder'}
    __tablename__ = None

    # methods needed for the invoice item visitor
    @classmethod
    def get_book(self, product):
        return product.get_book_at('additional_cost', None)
    
    @property
    def aflossing( self ):
        if self.related_to:
            return self.related_to.amount

    @property
    def dossier_nummer( self ):
        if self.related_to:
            return self.related_to.dossier_nummer

    @property
    def openstaand_kapitaal( self ):
        if self.related_to:
            return self.related_to.openstaand_kapitaal

    @property
    def openstaand( self ):
        if self.related_to:
            return self.te_betalen

    @property
    def kapitaal( self ):
        if self.related_to:
            return self.related_to.kapitaal

    @property
    def status_vervaldag( self ):
        if self.related_to:
            return self.related_to.status

    def get_open_amount(self):
        open_amount = super(RappelOpenstaandeVervaldag, self).get_open_amount()
        if open_amount is not None:
            return open_amount
        return self.intrest_a + self.intrest_b

    def __unicode__(self):
        if self.dossier is not None:
            return self.dossier.name


    class Admin(EntityAdmin):
        verbose_name = _('Openstaande vervaldag')
        verbose_name_plural = _('Openstaande vervaldagen')
        # amount visible, to allow end user to make manipulations
        list_display =  ['doc_date', 'related_doc_date', 'amount', 'aflossing', 'kapitaal', 'intrest_a', 'intrest_b', 'status', 'laatste_domiciliering', 'booked_amount', 'open_amount']
        form_display = forms.TabForm( [(_('Repayment reminder'),
                                        forms.Form(['doc_date', 'related_doc_date', 'openstaand_kapitaal','aflossing','kapitaal','intrest_a','intrest_b','te_betalen','status_vervaldag','status','laatste_domiciliering'],
                                                    columns=2),)] + InvoiceItem.Admin.additional_tabs )
        form_actions = [
            BookInvoiceItem(),
            UnbookInvoiceItem(),
            CancelInvoiceItem(),
            SendInvoiceItem(),
        ]
        field_attributes = copy.copy(InvoiceItem.Admin.field_attributes)
        field_attributes['aflossing'] = {'delegate':delegates.FloatDelegate}
        field_attributes['status_vervaldag'] = {'editable':False, 'name':_('Status vervaldag')}
        field_attributes['te_betalen'] = {'editable':True, 'name':_('Te betalen')}
        field_attributes['rappel_brief'] = {'editable':False, 'name':_('Rappel brief')}
        field_attributes['kapitaal'] = {'delegate':delegates.FloatDelegate}
        field_attributes['intrest_a'] = {'name':_('Intrest a')}
        field_attributes['intrest_b'] = {'name':_('Intrest b')}
        field_attributes['related_doc_date']['name'] = _('Datum vervaldag')

RappelBrief.Admin.field_attributes['openstaande_vervaldag']['admin'] = RappelOpenstaandeVervaldag.Admin
RappelBrief.Admin.field_attributes['openstaande_vervaldag']['target'] = RappelOpenstaandeVervaldag
RappelBrief.Admin.field_attributes['openstaande_betaling']['admin'] = RappelOpenstaandeBetaling.Admin
RappelBrief.Admin.field_attributes['openstaande_betaling']['target'] = RappelOpenstaandeBetaling

RappelBrief.openstaande_vervaldag = orm.relationship(RappelOpenstaandeVervaldag,
                                                     order_by=[RappelOpenstaandeVervaldag.related_doc_date],
                                                     primaryjoin=RappelOpenstaandeVervaldag.modifier_of_id==RappelBrief.id)

RappelBrief.openstaande_betaling = orm.relationship(RappelOpenstaandeBetaling,
                                                    order_by=[RappelOpenstaandeBetaling.doc_date],
                                                    primaryjoin=RappelOpenstaandeBetaling.modifier_of_id==RappelBrief.id)

