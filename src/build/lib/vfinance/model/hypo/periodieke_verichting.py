import calendar
import copy
import datetime
from decimal import Decimal as D
import logging
import operator

import sqlalchemy.types
from sqlalchemy import sql, orm, schema

from camelot.core.exception import UserException
from camelot.core.orm import ( Entity, using_options,
                               ColumnProperty )
from camelot.admin.action import Action
from camelot.admin.object_admin import ObjectAdmin
from camelot.view.controls import delegates
from camelot.view import forms, action_steps
from camelot.view.proxy.queryproxy import QueryTableProxy
from camelot.core.utils import ugettext_lazy as _

from integration.tinyerp.convenience import months_between_dates

from vfinance.admin.vfinanceadmin import VfinanceAdmin

from ...supergenerator import supergenerator, _from
from ..bank.financial_functions import round_up
from ..bank.entry import Entry
from .fulfillment import MortgageFulfillment
from .beslissing import GoedgekeurdBedrag
from wijziging import Wijziging
from dossier import Dossier, Factuur
from mortgage_table import aflossingen_van_bedrag

logger = logging.getLogger('vfinance.model.hypo.periodieke_verichting')

#
# Query strings that used to be here in tiny erp have been moved to
# bank/entry.py
#

from .visitor.invoice_item import InvoiceItemVisitor
from ..bank.invoice import InvoiceItem
from ...connector.accounting import AccountingSingleton, AccountingRequest

#  DEFAULT_WORKSHEET
#  laatste_betaling_op_rekening_van_afpunt_sessies
#  done_form
#  books

class HandleInvoiceItemOption(object):
    
    def __init__(self, invoice_item, action, tick_date=None):
        self.invoice_item = invoice_item
        self.action = action
        self.doc_date = invoice_item.doc_date
        self.booked_amount = invoice_item.booked_amount
        self.item_description = invoice_item.item_description
        self.amount = invoice_item.amount
        self.open_amount = invoice_item.open_amount
        self.item_type = invoice_item.row_type
        self.tick_date = tick_date
    
    class Admin(ObjectAdmin):
        list_display = ['item_type', 'doc_date', 'item_description', 'amount', 'open_amount', 'booked_amount', 'tick_date', 'action']
        field_attributes = {'doc_date': {'delegate': delegates.DateDelegate},
                            'amount': {'delegate': delegates.FloatDelegate},
                            'booked_amount': {'delegate': delegates.FloatDelegate},
                            'open_amount': {'delegate': delegates.FloatDelegate},
                            'tick_date': {'delegate': delegates.DateDelegate},
                            'action': {'delegate': delegates.ComboBoxDelegate,
                                       'editable': True,
                                       'choices': [(None, ''), 
                                                   ('book', 'Book'), 
                                                   ('cancel', 'Cancel')]}
                            }

class BookInvoiceItem(Action):
    
    verbose_name = _('Book')
    default_action = 'book'
    
    def model_run(self, model_context):
        visitor = InvoiceItemVisitor()
        accounting = AccountingSingleton()
        today = datetime.date.today()
        for i, invoice_item in enumerate(model_context.get_selection()):
            options = []
            openstaande_vervaldagen = list(invoice_item.dossier.get_openstaande_vervaldagen(invoice_item.doc_date, payment_thru_date=today))
            bookable_items = dict()
            if invoice_item.dossier is not None:
                bookable_items = dict((ovvd.vervaldag.id, ovvd.afpunt_datum) for ovvd in openstaande_vervaldagen)
            if invoice_item.booked_amount == 0:
                options.append(HandleInvoiceItemOption(invoice_item, self.default_action))
            if len(invoice_item.modified_by):
                for modifier in invoice_item.modified_by:
                    if (modifier.row_type != 'payment_reminder') and (len(modifier.bookings)==0) and (modifier.status != 'canceled'):
                        action = 'cancel'
                        tick_date = bookable_items.get(modifier.related_to_id, None)
                        if tick_date is not None:
                            action = 'book'
                        options.append(HandleInvoiceItemOption(modifier, action, tick_date))
                yield action_steps.ChangeObjects(options, model_context.admin.get_related_admin(HandleInvoiceItemOption))
            for option in options:
                proposed_invoice_item = option.invoice_item
                if option.action == 'book':
                    yield action_steps.UpdateProgress(i, 
                                                      model_context.selection_count, 
                                                      u'Book item {0.id} : {0.item_description}'.format(proposed_invoice_item))
                    with accounting.begin(model_context.session):
                        for step in visitor.create_invoice_item_sales(proposed_invoice_item):
                            if isinstance(step, AccountingRequest):
                                accounting.register_request(step)
                            yield action_steps.UpdateProgress(i, 
                                                              model_context.selection_count, 
                                                              detail=unicode(step))
                elif option.action == 'cancel':
                    proposed_invoice_item.status = 'canceled'
                    yield action_steps.FlushSession(model_context.session)
                yield action_steps.UpdateObject(proposed_invoice_item)
    
    def get_state(self, model_context):
        state = super(BookInvoiceItem, self).get_state(model_context)
        for invoice_item in model_context.get_selection():
            if (invoice_item is None) or (invoice_item.status=='canceled'):
                state.enabled = False
                break
        return state

class UnbookInvoiceItem(Action):
    
    verbose_name = _('Unbook')
    
    def model_run(self, model_context):
        visitor = InvoiceItemVisitor(session=model_context.session)
        accounting = AccountingSingleton()
        with accounting.begin(model_context.session):
            for i, invoice_item in enumerate(model_context.get_selection()):
                proposed_invoice_items = [invoice_item]
                if len(invoice_item.modified_by):
                    for modifier in invoice_item.modified_by:
                        if len(modifier.bookings)!=0:
                            proposed_invoice_items.append(modifier)
                for proposed_invoice_item in proposed_invoice_items:
                    yield action_steps.UpdateProgress(i, 
                                                      model_context.selection_count, 
                                                      u'Remove booking for item {0.id} : {0.item_description}'.format(proposed_invoice_item))
                    for loan_schedule_id in visitor.get_booked_schedule_ids(proposed_invoice_item):
                        loan_schedule = model_context.session.query(GoedgekeurdBedrag).filter(GoedgekeurdBedrag.id==loan_schedule_id).first()
                        entries = visitor.get_entries(loan_schedule,
                                                      conditions=[('booking_of_id', operator.eq, proposed_invoice_item.id)])
                        for step in visitor.create_remove_request(loan_schedule, entries):
                            accounting.register_request(step)
                            yield action_steps.UpdateProgress(detail=unicode(step))
                    model_context.session.expire(proposed_invoice_item)
                    yield action_steps.UpdateObject(proposed_invoice_item)
    
    def get_state(self, model_context):
        state = super(UnbookInvoiceItem, self).get_state(model_context)
        for invoice_item in model_context.get_selection():
            if (invoice_item is None) or (len(invoice_item.bookings)==0) or (invoice_item.status=='canceled'):
                state.enabled = False
                break
        return state

class RevertInvoiceItem(UnbookInvoiceItem):
    
    verbose_name = _('Revert')
    
    def model_run(self, model_context):
        visitor = InvoiceItemVisitor(session=model_context.session)
        accounting = AccountingSingleton()
        with accounting.begin(model_context.session):
            for i, invoice_item in enumerate(model_context.get_selection()):
                if len(invoice_item.modified_by):
                    raise UserException('Invoice item has subitems')
                if len(invoice_item.modified_by):
                    raise UserException('Invoice item has related items')
                yield action_steps.UpdateProgress(i, 
                                                  model_context.selection_count,
                                                  u'Revert booking for item {0.id} : {0.item_description}'.format(invoice_item))
                for loan_schedule_id in visitor.get_booked_schedule_ids(invoice_item):
                    loan_schedule = model_context.session.query(GoedgekeurdBedrag).filter(GoedgekeurdBedrag.id==loan_schedule_id).first()
                    entries = visitor.get_entries(loan_schedule,
                                                  conditions=[('booking_of_id', operator.eq, invoice_item.id)])
                    for step in visitor.create_revert_request(loan_schedule, entries):
                        if isinstance(step, AccountingRequest):
                            accounting.register_request(step)
                        yield action_steps.UpdateProgress(i,
                                                          model_context.selection_count,
                                                          detail=unicode(step))
                model_context.session.expire(invoice_item)
                yield action_steps.UpdateObject(invoice_item)
    
    def get_state(self, model_context):
        state = super(RevertInvoiceItem, self).get_state(model_context)
        if state.enabled:
            for invoice_item in model_context.get_selection():
                if invoice_item.booked_amount==0:
                    state.enabled = False
                    break
        return state
    
class CancelInvoiceItem(BookInvoiceItem):
    
    verbose_name = _('Cancel')
    default_action = 'cancel'
    
    @supergenerator
    def model_run(self, model_context):
        for invoice_item in model_context.get_selection():
            if invoice_item.booked_amount != 0:
                raise UserException('Invoice item has been booked',
                                    resolution='Unbook or revert the invoice item first')
        yield _from(super(CancelInvoiceItem, self).model_run(model_context))

    def get_state(self, model_context):
        state = super(CancelInvoiceItem, self).get_state(model_context)
        for invoice_item in model_context.get_selection():
            if (invoice_item is None) or (invoice_item.booked_amount!=0) or (invoice_item.status=='send'):
                state.enabled = False
                break
        return state

class SendInvoiceItem(Action):
    
    verbose_name = _('Send')
    
    def model_run(self, model_context):
        for i, invoice_item in enumerate(model_context.get_selection()):
            invoice_item.status = 'send'
            for modifier in invoice_item.modified_by:
                modifier.status = 'send'
            yield action_steps.FlushSession(model_context.session)

class BookRepayments(Action):
    
    verbose_name = _('Boek vervaldagen')
    
    def model_run(self, model_context):
        visitor = InvoiceItemVisitor()
        accounting = AccountingSingleton()
        for period in model_context.get_selection():
            repayments_to_update = []
            with accounting.begin(model_context.session):
                repayment_count = period.vervaldag.count()
                booked = 0
                for i, repayment in enumerate(period.vervaldag.yield_per(10)):
                    if repayment.booked_amount != 0:
                        continue
                    if repayment.status == 'canceled':
                        continue
                    repayments_to_update.append(repayment)
                    if i%10 == 0:
                        yield action_steps.UpdateProgress(i, 
                                                          repayment_count, 
                                                          u'Prepare booking item {0.id} : {0.item_description}'.format(repayment))
                    for step in visitor.create_invoice_item_sales(repayment):
                        if isinstance(step, AccountingRequest):
                            accounting.register_request(step)
                    booked += 1
                yield action_steps.UpdateProgress(i, 
                                                  repayment_count,
                                                  u'Register bookings')
            for repayment in repayments_to_update:
                yield action_steps.UpdateObject(repayment)
            yield action_steps.UpdateProgress(1,
                                              1,
                                              detail='{0} of {1} repayments booked'.format(booked, repayment_count),
                                              blocking=True)

class UnbookRepayments(Action):
    
    verbose_name = _('Verwijder boeking vervaldagen')
    
    def model_run(self, model_context):
        visitor = InvoiceItemVisitor()
        accounting = AccountingSingleton()
        for period in model_context.get_selection():
            with accounting.begin(model_context.session):
                repayment_count = period.vervaldag.count()
                unbooked = 0
                for i, repayment in enumerate(period.vervaldag.yield_per(10)):
                    if not len(repayment.bookings):
                        continue
                    yield action_steps.UpdateProgress(i, 
                                                      repayment_count, 
                                                      u'Unbook item {0.id} : {0.item_description}'.format(repayment))
                    loan_schedule = visitor.get_loan_schedule(repayment)
                    entries = visitor.get_entries(
                        loan_schedule,
                        conditions = [('booking_of_id', operator.eq, repayment.id)]
                        )
                    for step in visitor.create_remove_request(loan_schedule, entries):
                        accounting.register_request(step)
                    model_context.session.expire(repayment)
                    unbooked += 1
                    yield action_steps.UpdateObject(repayment)
            yield action_steps.UpdateProgress(1,
                                              1,
                                              detail='{0} of {1} repayments unbooked'.format(unbooked, repayment_count),
                                              blocking=True)

class RemoveRepayments(Action):
    
    verbose_name = _('Verwijder vervaldagen')
    
    def model_run(self, model_context):
        for period in model_context.get_selection():
            repayment_count = period.vervaldag.count()
            removed = 0
            for i, repayment in enumerate(period.vervaldag.yield_per(10)):
                reason = None
                if len(repayment.bookings) is not None:
                    reason = 'Item {0.id} : {0.item_description} is still booked'.format(repayment)
                if repayment.last_direct_debit_batch is not None:
                    reason = 'Item {0.id} : {0.item_description} is in a direct debit batch'.format(repayment)
                if len(repayment.related):
                    reason = 'Item {0.id} : {0.item_description} is in a reminder'.format(repayment)
                if reason is not None:
                    yield action_steps.UpdateProgress(i,
                                                      repayment_count,
                                                      detail=reason)
                else:
                    yield action_steps.UpdateProgress(i, 
                                                      repayment_count, 
                                                      u'Remove item {0.id} : {0.item_description}'.format(repayment))
                    model_context.session.delete(repayment)
                    removed += 1
                    yield action_steps.FlushSession(model_context.session)
            yield action_steps.UpdateProgress(1,
                                              1,
                                              detail='{0} of {1} repayments removed'.format(removed, repayment_count),
                                              blocking=True)
            yield action_steps.UpdateObject(period)

class CreateRepayments(Action):
    
    verbose_name = _('Maak vervaldagen en wijzigingen')
    
    def model_run(self, model_context):
        periods = list(model_context.get_selection())
        dossiers = model_context.session.query(Dossier).yield_per(10)
        dossier_count = model_context.session.query(Dossier).count()
        for i, dossier in enumerate(dossiers):
            yield action_steps.UpdateProgress(i, dossier_count, 'Dossier {0.nummer}'.format(dossier))
            for period in periods:
                for step in self.create_invoice_items(model_context, dossier, period):
                    yield step
                yield action_steps.UpdateObject(period)
    
    def create_repayments(self, dossier, gb, from_date, thru_date):
        logger.debug('evalueer aflossingen vanaf %s met aktedatum %s'%(gb.aanvangsdatum, dossier.aktedatum_deprecated))
        aflossing = None
        for a in aflossingen_van_bedrag(gb, (gb.aanvangsdatum), (dossier.aktedatum_deprecated) ):
          if a.datum<=thru_date and a.datum>=from_date:
            if gb.einddatum is None or a.datum<=(gb.einddatum):
              aflossing = a
            break
        if aflossing is not None:
          if dossier.state!='ended' or (dossier.einddatum)>=a.datum:
            payed_before_repayment = sum( (f.bedrag for f in dossier.factuur if f.datum < a.datum), 0 )
            intrest_reduction = 0
            if gb.goedgekeurde_opname_schijven:
                # Voor dossiers met opname schijven (cfr Automat), trek de rente op het nog nt opgenomen bedrag af 
                # van de te betalen aflossing
                intrest_reduction = 0
                days_of_period = (a.datum-a.previous_repayment_date).days
                daily_rate = a.periods * D(gb.goedgekeurde_rente) / (100*days_of_period)
                payed_amount = 0
                for payment in dossier.factuur:
                    if payment.datum < a.previous_repayment_date:
                        payed_amount += payment.bedrag
                        continue
                    if payment.datum >= a.datum:
                        continue
                    payed_amount += payment.bedrag
                    unpayed_days = (payment.datum-a.previous_repayment_date).days
                    payment_intrest_reduction = payment.bedrag * unpayed_days * daily_rate
                    intrest_reduction += payment_intrest_reduction
                    logger.debug('intrest reduction {0.datum} {0.bedrag}euro {1}days : {2}'.format(payment, unpayed_days, payment_intrest_reduction))
                # Amount unpayed at the end of the period
                unpayed_at_end_of_period = max(0, (gb.goedgekeurd_bedrag-payed_amount))
                unpayed_intrest_reduction = unpayed_at_end_of_period * days_of_period * daily_rate
                intrest_reduction += unpayed_intrest_reduction
                # Een wijziging kan het goedgekeurd bedrag onder het reeds betaalde
                # bedrag brengen.  Een factuur kan het reeds betaalde bedrag ook
                # tot boven het ontleende bedrag brengen, dit zou moeten geblokeerd
                # worden.
                intrest_reduction = round_up(min(intrest_reduction, max(0, a.aflossing-a.kapitaal+a.rente_correctie)))
                # Maak rente correctie ongedaan bij opname schijven, deze zat al verwerkt in a.aflossing, dus
                # die moet er terug uit
                intrest_reduction -= a.rente_correctie
            repayment = Vervaldag(dossier=dossier,
                                  openstaand_kapitaal=(a.saldo+a.kapitaal),
                                  doc_date=a.datum,
                                  nummer=a.nummer,
                                  kapitaal=a.kapitaal,
                                  amount=a.aflossing-intrest_reduction,
                                  gefactureerd = payed_before_repayment,
                                  item_description = u'vvd {0.month} {0.year} dossier {1.nummer}'.format(a.datum, dossier)
                                  )
            yield action_steps.CreateObject(repayment)

    def create_invoice_items(self, model_context, dossier, periode):
        with model_context.session.begin():
            # Maak de te af te sluiten opnameperiodes aan in de huidige periode, verifieer of ze reeds aangemaakt zijn, en
            # indien nt nodig, maak ze nt aan
            start = periode.startdatum
            if dossier.goedgekeurd_bedrag.product.book_from_date > periode.startdatum:
                raise StopIteration
            if dossier.state == 'opnameperiode':
              if months_between_dates((dossier.startdatum), (periode.einddatum)) >= dossier.goedgekeurd_bedrag.goedgekeurde_opname_periode:
                if not Wijziging.query.filter( sql.and_( Wijziging.dossier == dossier,
                                                         Wijziging.datum_wijziging >= periode.startdatum,
                                                         Wijziging.datum_wijziging <= periode.einddatum ) ).count():
                  wijziging = Wijziging()
                  wijziging.dossier = dossier
                  wijziging.status = 'draft'
                  first_day, max_day = calendar.monthrange(start.year, start.month)
                  voorstel_datum_wijziging = (datetime.date(start.year, start.month, min((dossier.startdatum).day,max_day)))
                  wijziging.button_maak_voorstel_op_datum( voorstel_datum_wijziging )
                  wijziging.nieuwe_status = 'running'
                  yield action_steps.FlushSession(model_context.session)
                  logger.debug('aanmaak afsluiten opnameperiode : %s '%wijziging.id)
            # aflossingen worden als vervaldagen van het type aflossing gemaakt, verifieer of ze reeds aangemaakt zijn,
            # en indien nt nodig, maak ze nt aan"""
            elif (dossier.state == 'running') or (dossier.state=='ended' and dossier.einddatum >= periode.startdatum):
                start = periode.startdatum
                eind = periode.einddatum
                gb = dossier.get_goedgekeurd_bedrag_at( periode.startdatum )
                if gb is not None:
                    if not Vervaldag.query.filter( sql.and_( Vervaldag.dossier == dossier,
                                                             Vervaldag.status != 'canceled',
                                                             Vervaldag.doc_date >= periode.startdatum,
                                                             Vervaldag.doc_date <= periode.einddatum ) ).count():
                        for step in self.create_repayments(dossier, gb, periode.startdatum, periode.einddatum):
                            yield step
                else:
                    logger.debug('dossier niet actief in deze periode')
                logger.debug('alle vervaldagen bepaald')
                yield action_steps.FlushSession(model_context.session)
            logger.debug('alle vervaldagen aangemaakt')
            #Maak alle reserveringsprovisies aan voor bepaalde dossiers, verifieer of ze reeds aangemaakt
            #zijn, en indien nt nodig, maak ze nt aan
    
            #alle berekeningen worden gedaan op de saldi op het eind van de vorige periode.  de reserveringsprovisie
            #wordt gerekend op de 1e dag van deze periode.
    
            #voor de bepaling van het saldo op het eind vd vorige periode wordt gekeken naar de betaalde facturen
            #voor het afsluiten van de vorige periode alsook de hiervoor aangerekende reserveringsprovisies.
            start_deze_periode = periode.startdatum
            eind = start_deze_periode - datetime.timedelta(days=1)
            start = datetime.date(eind.year, eind.month, 1)
            if dossier.state == 'opnameperiode':
              if dossier.startdatum < start_deze_periode:
                dossier_id = dossier.id
                #
                # verifieer of er reeds een reserveringsprovisie is voor dit dossier/periode
                #
                if Reservation.query.filter( sql.and_( Reservation.dossier == dossier,
                                                       Reservation.status != 'canceled',
                                                       Reservation.doc_date >= periode.startdatum,
                                                       Reservation.doc_date <= periode.einddatum ) ).count() == 0:
                  #
                  # zoniet, maak ze aan
                  #
                  logger.debug('maak reserveringsprovisie voor dossier %i'%dossier_id)
                  gb = dossier.goedgekeurd_bedrag
                  reservation  = Reservation(doc_date=periode.startdatum,
                                             dossier=dossier,
                                             item_description= u'prov {0.month} {0.year} dossier {1.nummer}'.format(periode.startdatum, dossier),
                                             nummer=0,
                                             kapitaal=0)
                  reserveringsprovisies = list( Reservation.query.filter( sql.and_( Reservation.dossier == dossier,
                                                                                    Reservation.doc_date < eind ) ).all() )
                  facturen_voor_periode = ( Factuur.query.filter( sql.and_( Factuur.dossier == dossier,
                                                                            Factuur.datum < start ) ).all() )
                  facturen_in_periode = ( Factuur.query.filter( sql.and_( Factuur.dossier == dossier,
                                                                          Factuur.datum >= start,
                                                                          Factuur.datum <= eind ) ).all() )
                  gefactureerd_voor_periode = D( sum( f.bedrag for f in facturen_voor_periode ) )
                  gefactureerd_in_periode = D( sum( f.bedrag for f in facturen_in_periode ) )
                  geprovisioneerd = D( sum( v.open_amount for v in reserveringsprovisies ) )
                  opgevraagd_kapitaal = gefactureerd_voor_periode + gefactureerd_in_periode + geprovisioneerd
                  saldo_eind_periode = gb.goedgekeurd_bedrag - opgevraagd_kapitaal
                  jaar_rente = D(gb.goedgekeurde_jaarrente or 0)
                  periodieke_rente = D(gb.goedgekeurde_rente or 0)
                  interval = gb.goedgekeurd_terugbetaling_interval
                  if jaar_rente:
                    maand_rente = jaar_rente / 12
                  else:
                    maand_rente = periodieke_rente * 12 / interval
                  intrest = opgevraagd_kapitaal * maand_rente / 100
                  logger.debug('saldo eind periode : %s'%saldo_eind_periode)
                  logger.debug('opgevraagd kapitaal : %s'%opgevraagd_kapitaal)
                  reserveringsprovisie = saldo_eind_periode * D(gb.goedgekeurde_reserverings_provisie or 0)
                  reservation.amount = intrest + reserveringsprovisie
                  reservation.openstaand_kapitaal = opgevraagd_kapitaal
                  reservation.gefactureerd = gefactureerd_voor_periode + gefactureerd_in_periode
                  reservation.geprovisioneerd = geprovisioneerd
            yield action_steps.FlushSession(model_context.session)
            # Maak de voorstellen tot rentewijziging in de huidige periode, verifieer of ze reeds aangemaakt zijn, en indien
            # nt nodig, maak ze nt aan
            if (dossier.state == 'running') or (dossier.state=='ended' and dossier.einddatum >= periode.startdatum):
                gb = dossier.get_goedgekeurd_bedrag_at( periode.startdatum )
                if gb != None and gb.goedgekeurde_eerste_herziening > 0 and gb.goedgekeurd_index_type != None:
                    start = periode.startdatum
                    dossier = gb.dossier
                    _first_day, max_day = calendar.monthrange(start.year, start.month)
                    voorstel_datum_wijziging = datetime.date(start.year, start.month, min((gb.aanvangsdatum).day,max_day))
                    passed_months = months_between_dates((gb.aanvangsdatum), voorstel_datum_wijziging)
                    if passed_months == gb.goedgekeurde_eerste_herziening:
                      if not Wijziging.query.filter( sql.and_( Wijziging.dossier == dossier,
                                                               Wijziging.datum_wijziging >= periode.startdatum,
                                                               Wijziging.datum_wijziging <= periode.einddatum ) ).count():
                        wijziging = Wijziging( datum = voorstel_datum_wijziging,
                                               dossier = dossier,
                                               state = 'draft' )
                        wijziging.button_maak_voorstel_op_datum( voorstel_datum_wijziging )
                        logger.debug('aanmaak rentewijziging : %s '%wijziging.id)
            yield action_steps.FlushSession(model_context.session)
            #Maak wijziging om dossiers af te sluiten die :
            #* afgelopen zijn
            #* enkel afgepunte vervaldagen hebben
            #* enkel afgepunt of geannulleerde rappel brieven
            #* openstaand saldo kapitaal kleiner dan 1.0 euro
            #* resterend saldo kleiner dan 1.0 euro
            tolerantie = 1
            start = periode.startdatum
            vervaldag_query = model_context.session.query(Vervaldag)
            vervaldag_query = vervaldag_query.join(MortgageFulfillment, MortgageFulfillment.booking_of_id==Vervaldag.id)
            vervaldag_query = vervaldag_query.join(Entry, Entry.fulfillment_condition(Entry.table.c, MortgageFulfillment.table.c))
            vervaldag_query = vervaldag_query.filter(Vervaldag.dossier_id == dossier.id)
            vervaldag_query = vervaldag_query.filter(MortgageFulfillment.entry_line_number==1)
            vervaldag_query = vervaldag_query.filter(Entry.ticked==False)
            rappelbrief_query = RappelBrief.query.join(MortgageFulfillment, MortgageFulfillment.booking_of_id==RappelBrief.id)
            rappelbrief_query = rappelbrief_query.join(Entry, Entry.fulfillment_condition(Entry.table.c, MortgageFulfillment.table.c))
            rappelbrief_query = rappelbrief_query.filter(MortgageFulfillment.entry_line_number==1)
            rappelbrief_query = rappelbrief_query.filter(RappelBrief.dossier_id == dossier.id)
            rappelbrief_query = rappelbrief_query.filter(RappelBrief.status != 'canceled')
            rappelbrief_query = rappelbrief_query.filter(Entry.ticked==False)
            if dossier.state == 'running':
              if months_between_dates((dossier.startdatum), (periode.einddatum)) > dossier.goedgekeurd_bedrag.goedgekeurde_looptijd:
                if not Wijziging.query.filter( sql.and_( Wijziging.dossier == dossier,
                                                         Wijziging.datum_wijziging >= periode.startdatum,
                                                         Wijziging.datum_wijziging <= periode.einddatum   ) ).count():
                  if vervaldag_query.count() == 0:
                    if not rappelbrief_query.count() == 0:
                      if abs(dossier.som_openstaande_verrichtingen)<tolerantie and abs(dossier.openstaand_kapitaal)<tolerantie:
                        wijziging = Wijziging( dossier = dossier, state='draft' )
                        _first_day, max_day = calendar.monthrange(start.year, start.month)
                        voorstel_datum_wijziging = (datetime.date(start.year, start.month, min((dossier.startdatum).day,max_day)))
                        wijziging.button_maak_voorstel_op_datum( voorstel_datum_wijziging )
                        wijziging.nieuw_status = 'ended'
                        logger.debug('aanmaak afsluiten opnameperiode : %s '%wijziging.id)
            yield action_steps.FlushSession(model_context.session)
  
class CreateDossierRepayments(CreateRepayments):
    
    def model_run(self, model_context):
        dossiers = list(model_context.get_selection())
        periods = model_context.session.query(Periode).all()
        for i, period in enumerate(periods):
            yield action_steps.UpdateProgress(i, len(periods), text=unicode(period))
            for dossier in dossiers:
                for step in self.create_invoice_items(model_context, dossier, period):
                    yield step
                model_context.session.expire(dossier)
                yield action_steps.UpdateObject(dossier)

Dossier.Admin.form_actions.append(CreateDossierRepayments())

from rappel_brief import RappelBrief

class Vervaldag(InvoiceItem):
    opmerking  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    nummer  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    openstaand_kapitaal  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
    kapitaal  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
    gefactureerd  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)

    __mapper_args__ = {'polymorphic_identity': 'repayment'}
    __tablename__ = None

    @classmethod
    def get_book(self, product):
        return product.get_book_at('repayment', None)
    
    @ColumnProperty
    def periode_id( self ):
        return sql.select( [Periode.id] ).where( sql.and_( Periode.startdatum >= self.doc_date,
                                                           Periode.einddatum <= self.doc_date ) ).limit( 1 )

    def __unicode__(self):
        return self.dossier.name

    @property
    def rente(self):
        if None not in (self.amount, self.kapitaal):
            return self.amount - self.kapitaal

    @property
    def dossier_nummer(self):
        return self.dossier.nummer

    @property
    def dossier_full_number(self):
        return self.dossier.full_number

    @property
    def korting(self):
        return self.get_reduction()

    def get_reduction(self):
        if None not in (self.dossier, self.doc_date, self.openstaand_kapitaal, self.rente):
            reductions = (a for t, a in self.dossier.get_reductions_at(self.doc_date, self.openstaand_kapitaal))
            return sum(reductions, D(0))

    class Admin(InvoiceItem.Admin):
        verbose_name = _('Vervaldag')
        verbose_name_plural = _('Vervaldagen')
        list_display =  ['status', 'doc_date', 'row_type', 'dossier_full_number',
                         'nummer', 'amount', 'kapitaal', 'rente', 'korting',
                         'booked_amount', 'laatste_domiciliering',]
        form_actions = InvoiceItem.Admin.form_actions + [
            BookInvoiceItem(),
            UnbookInvoiceItem(),
            CancelInvoiceItem(),
            RevertInvoiceItem(),
            #CallMethod( _('Punt af'), lambda vvd:vvd.punt_af(), enabled = lambda vvd:vvd.state in ['doorgevoerd']),
            #CallMethod( _('Verwijder afpunting'), lambda vvd:vvd.verwijder_afpunting(), enabled = lambda vvd:vvd.state in ['ticked'])
        ]
        repayment_form_fields = ['status', 'doc_date', 'row_type', 'dossier', 'nummer', 'openstaand_kapitaal','amount','laatste_domiciliering']
        form_display = forms.TabForm( [(_('Repayment'),
                                        forms.Form(repayment_form_fields + ['kapitaal','rente','korting'], columns=2)
                                        ),] + InvoiceItem.Admin.additional_tabs )
        field_attributes = copy.copy(InvoiceItem.Admin.field_attributes)
        field_attributes['amount'] = {'editable':True, 'name':_('Aflossing')}
        field_attributes['geprovisioneerd'] = {'editable':True, 'name':_('Reeds geprovisioneerd')}
        field_attributes['periode'] = {'editable':True, 'name':_('Periode')}
        field_attributes['open_amount'] = {'editable':False, 'name':_('Openstaand bedrag')}
        field_attributes['gefactureerd'] = {'editable':True, 'name':_('Reeds gefactureerd')}
        field_attributes['doc_date'] = {'editable':True, 'name':_('Datum vervaldag')}
        field_attributes['open_amount_or_aflossing'] = {'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Openstaand bedrag')}
        field_attributes['rente'] = {'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Rente')}
        field_attributes['dossier_full_number'] = {'editable':False, 'name':_('Dossier')}
        field_attributes['korting'] = {'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Korting')}
        field_attributes['type'] = {'editable':False, 'name':_('Type'), 'choices':[('aflossing', 'Aflossing'), ('reserveringsprovisie', 'Reserveringsprovisie')]}
        field_attributes['nummer'] = {'editable':True, 'name':_('Nummer')}
        field_attributes['openstaand_kapitaal'] = {'editable':True, 'name':_('Openstaand kapitaal voor vervaldag')}
        field_attributes['dossier'] = {'editable':True, 'name':_('Dossier')}
        field_attributes['kapitaal'] = {'editable':True, 'name':_('Kapitaal')}
        
        def get_related_toolbar_actions(self, toolbar_area, direction):
            actions = InvoiceItem.Admin.get_related_toolbar_actions(self, toolbar_area, direction)
            if actions:
                actions.append(BookInvoiceItem())
                actions.append(UnbookInvoiceItem())
            return actions

Dossier.Admin.field_attributes['repayments'] = {'target':Vervaldag, 'name': _('Vervaldagen')}

class Reservation(Vervaldag):
    geprovisioneerd  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
    __mapper_args__ = {'polymorphic_identity': 'reservation'}
    __tablename__ = None
    
    class Admin(Vervaldag.Admin):
        verbose_name = _('Reserveringsprovisie')
        verbose_name_plural = _('Reserveringsprovisies')
        form_display = forms.TabForm( [(_('Reservation'),
                                        forms.Form(Vervaldag.Admin.repayment_form_fields + ['geprovisioneerd','gefactureerd','rente','korting'], columns=2)
                                        ),] + InvoiceItem.Admin.additional_tabs )

def first_day_of_month():
    now = datetime.date.today()
    return datetime.date(now.year, now.month, 1)

def last_day_of_month():
    now = datetime.date.today()
    return datetime.date(now.year, now.month, calendar.monthrange(now.year, now.month)[1] )

class AppendToDirectDebitBatch(Action):

    verbose_name = _('Direct debit')

    def model_run(self, model_context):
        yield action_steps.UpdateProgress(text='Search repayments with direct debit')
        dd_counter = 0
        for period in model_context.get_selection():
            invoice_items = []
            for invoice_item in period.vervaldag:
                if invoice_item.dossier.domiciliering:
                    invoice_items.append(invoice_item)
            # to make sure the first direct debit batch created, is the one with
            # earliest date
            invoice_items.sort(key=lambda ii:ii.doc_date)
            with model_context.session.begin():
                for i, invoice_item in enumerate(invoice_items):
                    yield action_steps.UpdateProgress(i, len(invoice_items), invoice_item.item_description)
                    mandate = invoice_item.get_mandate()
                    if mandate is None:
                        yield action_steps.UpdateProgress(detail='No direct debit mandate for dossier {0.dossier.nummer} at {0.doc_date}'.format(invoice_item))
                    elif invoice_item.laatste_domiciliering is not None:
                        yield action_steps.UpdateProgress(detail='Repayment for dossier {0.dossier.nummer} already in batch {0.laatste_domiciliering}'.format(invoice_item))
                    else:
                        try:
                            invoice_item.voeg_toe_aan_domiciliering()
                            dd_counter += 1
                        except UserException as exc:
                            yield action_steps.UpdateProgress(detail='Issue with {0.dossier.nummer} to batch : {1.text}'.format(invoice_item, exc))
                    # flush after each invoice item, since it might have created
                    # a new batch that should be retrieved
                    yield action_steps.FlushSession(model_context.session)
            for invoice_item in invoice_items:
                yield action_steps.UpdateObject(invoice_item)
        yield action_steps.UpdateProgress(1, 1, blocking=True,
                                          text='Finished',
                                          detail='{0} repayments appended to direct debit batch'.format(dd_counter))


class Periode(Entity):
    using_options(tablename='hypo_periode')
    startdatum  =  schema.Column(sqlalchemy.types.Date(), nullable=False, default = first_day_of_month)
    einddatum  =  schema.Column(sqlalchemy.types.Date(), nullable=False, default = last_day_of_month)
    state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False, default = unicode('aanmaken'))

    @property
    def wijziging(self):
        """Zoek alle wijzigingen die in deze periode dienen te worden doorgevoerd"""
        if None not in (self.einddatum, self.startdatum):
            return Wijziging.query.filter( sql.and_( Wijziging.datum_wijziging <= self.einddatum,
                                                     Wijziging.datum_wijziging >= self.startdatum ) )

    @property
    def vervaldag(self):
        """Zoek alle vervaldagen die in deze periode dienen te worden doorgevoerd"""
        if None not in (self.einddatum, self.startdatum):
            return Vervaldag.query.filter( sql.and_( Vervaldag.doc_date <= self.einddatum,
                                                     Vervaldag.doc_date >= self.startdatum ) )

    @property
    def rappel_brieven(self):
        """Zoek alle rappel brieven die in deze periode zijn aangemaakt"""
        if None not in (self.einddatum, self.startdatum):
            return RappelBrief.query.filter( sql.and_( RappelBrief.doc_date <= self.einddatum,
                                                       RappelBrief.doc_date >= self.startdatum ) )

    def name(self):
        return '%s tot %s'%(self.startdatum, self.einddatum)

    def __unicode__(self):
        return '%s tot %s'%(self.startdatum, self.einddatum)

    def button_maak_rappel_brieven(self):
        """indien er vervaldagen langer dan 1 maand open staan op datum van aanmaak van de rappel brief, en er
        onvoldoende saldo is om deze af te punten, maak dan een rappel brief aan.
        """
        import datetime.datetime
        start = (self.startdatum)
        datum_brief = min(start, datetime.datetime.datetime.date.today())
        datum_openstaand = datum_brief - datetime.timedelta(days=30)
        #
        # Dossiers met openstaande vervaldagen en nog geen rappel brief in
        #
        query = """
          select distinct hypo_vervaldag.dossier as dossier_id
          from hypo_vervaldag
          join hypo_dossier on (hypo_dossier.id=hypo_vervaldag.dossier)
          where hypo_vervaldag.state='doorgevoerd' and hypo_vervaldag.datum<='%s'
          and coalesce((select hypo_rappel_brief.datum from hypo_rappel_brief
                        where hypo_rappel_brief.dossier=hypo_vervaldag.dossier
                        order by hypo_rappel_brief.datum desc limit 1),'%s')<='%s'
          and ((hypo_dossier.opzegging_status is null) or (hypo_dossier.opzegging_status='') or (hypo_dossier.opzegging_status='geen'))
          order by hypo_vervaldag.dossier"""%((datum_openstaand), (datum_openstaand), (datum_openstaand))

        dossier_ids = [row['dossier_id'] for row in orm.object_session( self ).execute( sql.text( query ), mapper=Entry ) if row['dossier_id']]
        #
        # Loop over de dossiers, check of er onvoldoende saldo is, en indien nodig
        # maak rappel brief aan.
        #
        for dossier_id in dossier_ids:
          dossier = Dossier.get( dossier_id )
          if dossier.som_openstaande_verrichtingen > 0:
            logger.debug('maak rappel brief for dossier %s'%(dossier.nummer))
            dossier.create_rappel( datum_brief )

    class Admin(VfinanceAdmin):
        verbose_name = _('Periode')
        list_display =  ['startdatum', 'einddatum']
        form_state = 'maximized'
        form_display =  forms.Form([forms.TabForm([(_('Wijzigingen'), forms.Form(['startdatum','einddatum','wijziging',], columns=2)),(_('Vervaldagen'), forms.Form(['vervaldag',], columns=2)),(_('Rappel brieven'), forms.Form(['rappel_brieven',], columns=2)),], position=forms.TabForm.WEST)], columns=2)
        form_actions = [ CreateRepayments(),
                         RemoveRepayments(),
                         BookRepayments(),
                         UnbookRepayments(),
                         AppendToDirectDebitBatch(),
                         ]
        field_attributes = {
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'startdatum':{'editable':True, 'name':_('Start datum')},
                            'einddatum':{'editable':True, 'name':_('Eind datum')},
                            'state':{'editable':False, 'name':_('Status'), 'choices':[('aanmaken', 'Aan te maken'), ('doorvoeren', 'Door te voeren'), ('doorgevoerd', 'Doorgevoerd')]},
                            'wijziging':{'editable':False, 'delegate':delegates.One2ManyDelegate, 'name':_('Te wijzigen'), 'target':Wijziging, 'proxy':QueryTableProxy},
                            'rappel_brieven':{'editable':False, 'delegate':delegates.One2ManyDelegate, 'name':_('Te wijzigen'), 'target':RappelBrief, 'proxy':QueryTableProxy},
                            'vervaldag':{'editable':False, 'delegate':delegates.One2ManyDelegate, 'name':_('Vervaldagen'), 'target':Vervaldag, 'proxy':QueryTableProxy},
                           }


#  start_euro
#  sales_line_desc
#  wizard_fields
#  sales_line_data
