import datetime
from decimal import Decimal as D
import logging
import operator

import sqlalchemy.types
from sqlalchemy import orm, schema, sql

from camelot.core.orm import Entity, ManyToOne
from camelot.admin.action import Action, CallMethod, list_filter
from camelot.core.exception import UserException
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import transaction
from camelot.view.controls import delegates
from camelot.view import forms

from camelot.view import action_steps

from vfinance.admin.translations import Translations
from vfinance.admin.vfinanceadmin import VfinanceAdmin
import mortgage_table

from . import constants
from ..bank.financial_functions import round_up
from ..bank.venice import get_dossier_bank
from ..bank.visitor import CustomerBookingAccount, ProductBookingAccount
from .summary.redemption import RedemptionAction
from .visitor import AbstractHypoVisitor
from .hypotheek import HypoApplicationMixin

LOGGER = logging.getLogger( 'vfinance.model.hypo.terugbetaling' )

def bepaal_wederbeleggingsvergoeding(bedrag,
                                     openstaand_kapitaal, 
                                     resterend_kapitaal,
                                     start_datum, 
                                     datum_stopzetting,
                                     agreement_date,
                                     euribor,
                                     sheet=None,
                                     language=None):
    """Bepaal de wederbeleggingsvergoeding
    :param sheet: overzichtsheet waarin de berekening vd 
        wederbellegingsvergoeding wordt geplaatst
    """
    from integration.spreadsheet import Cell, Sub, Mul, Div, Pow, Add, Max, Sum, Range
    from integration.spreadsheet.html import HtmlSpreadsheet
    if not sheet:
        sheet = HtmlSpreadsheet()
    wederbeleggingsvergoeding = D(0)
    dossier = bedrag.dossier
    translations = Translations(dossier.taal)
    ugettext = translations.ugettext
    LOGGER.debug( unicode(dossier) )
    wettelijk_kader = dossier.aanvraag.wettelijk_kader
    
    row = 6
    sheet.render(Cell('A', row, ugettext('Wettelijk kader')))
    sheet.render(Cell('B', row, wettelijk_kader))
    row += 1
    sheet.render(Cell('A', row, ugettext('Openstaand kapitaal')))
    cell_openstaand_kapitaal = Cell('B', row, openstaand_kapitaal)
    row += 1
    sheet.render(Cell('A', row, ugettext('Resterend kapitaal')))
    cell_resterend_kapitaal = Cell('B', row, resterend_kapitaal)
    row += 1
    sheet.render(Cell('A', row, ugettext('Terug te betalen kapitaal')))
    cell_terug_te_betalen_kapitaal =  Cell('B', row, Sub(cell_openstaand_kapitaal, cell_resterend_kapitaal))
    sheet.render(cell_openstaand_kapitaal, cell_resterend_kapitaal, cell_terug_te_betalen_kapitaal)
    row += 1
    sheet.render(Cell('A', row, ugettext('Maand rente')))
    periodieke_rente = D(bedrag.goedgekeurde_rente)
    interval = bedrag.goedgekeurd_terugbetaling_interval
    if wettelijk_kader=='ar225':
        jaar_rente = D(bedrag.goedgekeurde_jaarrente ) * D(100)
        maand_rente = (jaar_rente / D(12)) or (periodieke_rente / (12 / interval))
        cell_maand_rente =  Cell('B', row, maand_rente )
        wederbeleggingsvergoeding = (maand_rente * 6 * (openstaand_kapitaal-resterend_kapitaal)) / D(100)
        row += 1
        cell_wederbeleggingsvergoeding = Cell('B', row, Div(Mul(cell_maand_rente, 6, cell_terug_te_betalen_kapitaal),100))
    elif wettelijk_kader=='wet4892':
        maand_rente = periodieke_rente / (12 / interval)
        cell_maand_rente =  Cell('B', row, maand_rente )
        row += 1
        wederbeleggingsvergoeding = (maand_rente * 3 * (openstaand_kapitaal-resterend_kapitaal)) / D(100)
        cell_wederbeleggingsvergoeding = Cell('B', row, Div(Mul(cell_maand_rente, 3, cell_terug_te_betalen_kapitaal),100))
    elif wettelijk_kader=='andere':
        maand_rente = periodieke_rente / (12 / interval)
        cell_maand_rente =  Cell('B', row, maand_rente )
        row += 1
        funding_loss = dossier.get_functional_setting_description_at(agreement_date, 'funding_loss')
        if funding_loss != 'discounted_repayment':
            wederbeleggingsvergoeding = (maand_rente * 6 * (openstaand_kapitaal-resterend_kapitaal)) / D(100)
            cell_wederbeleggingsvergoeding = Cell('B', row, Div(Mul(cell_maand_rente, 6, cell_terug_te_betalen_kapitaal),100))
        else:
            sheet.render(Cell('A', row, 'Euribor'))
            if not euribor:
                raise UserException('Please fill in the Euribor rate')
            cell_euribor = Cell('B', row, float(euribor))
            row += 1
            sheet.render(Cell('A', row, ugettext('Discontovoet')))
            cell_disconto = Cell('B', row, Div(cell_euribor, Mul(interval, 100)))
            row += 1
            sheet.render(cell_euribor, cell_disconto)
            f = D(euribor) / (interval * 100)
            aantal_enkel_intrest, aantal_kapitaalsaflossingen = mortgage_table.aantal_aflossingen(bedrag)
            interval = 12/bedrag.goedgekeurd_terugbetaling_interval
            aflossingen = [a for a in mortgage_table.aflossingen( D(bedrag.goedgekeurde_rente), 
                                                                  bedrag.goedgekeurd_type_aflossing, 
                                                                  bedrag.goedgekeurd_bedrag - resterend_kapitaal, 
                                                                  aantal_kapitaalsaflossingen, 
                                                                  interval, 
                                                                  start_datum, 
                                                                  aantal_enkel_intrest, 
                                                                  D(bedrag.goedgekeurde_jaarrente or 0)*100) ]
            n = 0
            sheet.render(Cell('A', row, ugettext('Toekomstige Aflossingen')))
            sheet.render(Cell('B', row, ugettext('Datum')))
            sheet.render(Cell('C', row, ugettext('Bedrag')))
            sheet.render(Cell('D', row, ugettext('Verdisconteerd bedrag')))
            row += 1
            eerste_aflossing, laatste_aflossing = None, None
            for a in aflossingen:
                if a.datum > datum_stopzetting:
                    sheet.render(Cell('B', row+n, a.datum))
                    sheet.render()
                    cell_aflossing = Cell('C', row+n, a.aflossing)
                    cell_aflossing_verdisconteerd = Cell('D', row+n, Div(cell_aflossing, Pow(Add(1,cell_disconto), n)))
                    sheet.render( cell_aflossing, cell_aflossing_verdisconteerd)
                    aflossing_verdisconteerd = a.aflossing / (1+f)**(n)
                    LOGGER.debug('aflossing %s %s, n=%s : %s'%(a.datum, a.aflossing, n, aflossing_verdisconteerd) )
                    wederbeleggingsvergoeding += aflossing_verdisconteerd
                    laatste_aflossing = cell_aflossing_verdisconteerd
                    if n==0:
                        eerste_aflossing = cell_aflossing_verdisconteerd
                    n = n + 1
            row += n
            sheet.render(Cell('A', row, ugettext('Totaal verdisconteerde aflossingen')))
            if eerste_aflossing and laatste_aflossing:
                cell_totaal_verdisconteerd = Cell('B', row, Sum(Range(eerste_aflossing,laatste_aflossing)))
            else:
                cell_totaal_verdisconteerd = Cell('B', row, 0.0)
            row += 1
            sheet.render(Cell('A', row, ugettext('Waarde aflossingen')))
            cell_waarde_aflossingen = Cell('B', row, Sub(cell_totaal_verdisconteerd, cell_terug_te_betalen_kapitaal))
            row += 1
            sheet.render(cell_totaal_verdisconteerd, cell_waarde_aflossingen)
            LOGGER.debug('openstaand kapitaal : %s'%openstaand_kapitaal)
            LOGGER.debug('resterend kapitaal : %s'%resterend_kapitaal)
            wederbeleggingsvergoeding -= (openstaand_kapitaal - resterend_kapitaal)
            zes_maand_rente = (maand_rente * 6 * (openstaand_kapitaal-resterend_kapitaal) / D(100) )
            cell_zes_maand_rente = Cell('B', row, Div(Mul(cell_maand_rente, 6, cell_terug_te_betalen_kapitaal),100))
            sheet.render( Cell('A', row, ugettext('Zes maand rente')), cell_zes_maand_rente )
            row += 1
            wederbeleggingsvergoeding = max(wederbeleggingsvergoeding, zes_maand_rente)
            LOGGER.debug('wederbeleggingsvergoeding : %s'%wederbeleggingsvergoeding)
            cell_wederbeleggingsvergoeding = Cell('B', row, Max(cell_zes_maand_rente, cell_waarde_aflossingen) )
    else:
        raise Exception('Onbekend wettelijk kader %s'%dossier.aanvraag.wettelijk_kader)
    sheet.render(Cell('A', cell_wederbeleggingsvergoeding.row, ugettext('Wederbeleggingsvergoeding')))
    sheet.render(cell_maand_rente, cell_wederbeleggingsvergoeding)
    return round_up(wederbeleggingsvergoeding), round_up(maand_rente)

class OverzichtWederbeleggingsvergoeding( Action ):
    
    verbose_name = _( 'Overzicht\nWederbeleggingsvergoeding' )
    
    def model_run( self, model_context ):
        from integration.spreadsheet.xlsx import XlsxSpreadsheet
        from integration.spreadsheet import Cell
        for terugbetaling in model_context.get_selection():
            translations = Translations(terugbetaling.dossier.taal)
            ugettext = translations.ugettext
            sheet = XlsxSpreadsheet()
            sheet.render(Cell('A', 1, ugettext('Wederbeleggingsvergoeding')))
            sheet.render(Cell('A', 2, ugettext('Dossier')))
            sheet.render(Cell('B', 2, terugbetaling.dossier.nummer))
            sheet.render(Cell('A', 3, ugettext('Datum stopzetting')))
            sheet.render(Cell('B', 3, terugbetaling.datum_stopzetting ))
            bepaal_wederbeleggingsvergoeding( terugbetaling.dossier.goedgekeurd_bedrag, 
                                              terugbetaling.openstaand_kapitaal, 
                                              0, 
                                              terugbetaling.dossier.startdatum, 
                                              terugbetaling.datum_stopzetting, 
                                              terugbetaling.datum,
                                              terugbetaling.euribor, 
                                              sheet )
            step = action_steps.OpenString( sheet.generate_xlsx(), '.xlsx' )
            yield step
    
class Terugbetaling(Entity, HypoApplicationMixin):
     """Document voor het uitvoeren van een vervroegde terugbetaling"""
     
     _book = 'Hypaf'
     
     __tablename__ = 'hypo_terugbetaling'

     onbetaalde_rente  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     openstaande_betalingen  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     nalatigheidsintresten_a  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     open_amount  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False, default = datetime.date.today)
     nalatigheidsintresten_b  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     rappelkosten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     dagrente_correctie  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     wederbeleggingsvergoeding  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True, default=unicode('pending'))
     schadevergoeding_uitwinning  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     venice_book_type  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     venice_book  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     gerechtskosten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     venice_doc  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     datum_terugbetaling  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
     venice_active_year  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     datum_stopzetting  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     openstaand_kapitaal  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     euribor = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=5))
     dossier_id  =  schema.Column(sqlalchemy.types.Integer(), name='dossier', nullable=False, index=True)
     dossier  =  ManyToOne('vfinance.model.hypo.dossier.Dossier', field=dossier_id, backref='terugbetaling')
     dagrente_percentage  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
     datum_laatst_betaalde_vervaldag  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     venice_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)

     def __getattr__( self, name ):
          if name in [ 'goedgekeurde_rente', 'goedgekeurde_looptijd', 'goedgekeurd_type_aflossing', 'goedgekeurd_terugbetaling_interval']:
               if self.dossier == None:
                    return None
               return getattr( self.dossier, name )
          raise AttributeError()
     
     @property
     def borrower_1_name(self):
         if self.dossier is not None:
             return self.dossier.borrower_1_name
 
     @property
     def borrower_2_name(self):
         if self.dossier is not None:
             return self.dossier.borrower_2_name

     @property
     def company_id(self):
         if self.dossier is not None:
             return self.dossier.company_id
 
     @property
     def nummer(self):
         if self.dossier is not None:
             return self.dossier.nummer
         
     @property
     def rank(self):
         if self.dossier is not None:
             return self.dossier.rank
       
     @property
     def intresten_geboekt_na_afsluiten_dossier(self):
          """De intresten geboekt na het afsluiten vh dossier moeten terug uit de dagrentes gehaald worden, 
          om te verhinderen dat ze dubbel geteld worden"""
          intresten_na_afsluiten = 0
          if self.dossier:
               if self.datum_stopzetting:
                   visitor = AbstractHypoVisitor()
                   for loan_schedule in self.dossier.loan_schedules:
                       for fulfillment_type in ['repayment', 'reservation']:
                           intresten_na_afsluiten -= visitor.get_total_amount_until(loan_schedule,
                                                                                    fulfillment_type=fulfillment_type,
                                                                                    from_document_date=self.datum_stopzetting + datetime.timedelta(days=1),
                                                                                    account=ProductBookingAccount('rente'))[0]
          return intresten_na_afsluiten
     
     @property
     def openstaande_betalingen_na_afsluiten_dossier( self ):
       if self.datum_stopzetting and self.dossier:
           return -1 * sum([b.open_amount for b in self.dossier.openstaande_betaling if b.book_date > self.datum_stopzetting])
       return 0

     @property
     def aantal_dagen( self ):
          if self.datum_terugbetaling and self.datum_stopzetting:
               return max((self.datum_terugbetaling - self.datum_stopzetting).days, 0)
          return 0
     
     @property
     def dagrente_bedrag( self ):
          return max(0, (self.te_betalen or 0)*D(self.dagrente_percentage or 0)/100)
     
     @property
     def dagrente( self ):
          return self.aantal_dagen*self.dagrente_bedrag + ( self.dagrente_correctie or 0 )
     
     @property
     def nalatigheidsintresten( self ):
          return (self.nalatigheidsintresten_a or 0) + (self.nalatigheidsintresten_b or 0)
     
     @property
     def totaal( self ):
          return self.dagrente + self.te_betalen - self.openstaande_betalingen_na_afsluiten_dossier
     
     @property
     def dagrente_minus_intresten_geboekt_na_afsluiten_dossier( self ):
          return self.dagrente - self.intresten_geboekt_na_afsluiten_dossier
    
     @property
     def te_betalen( self ):
          return ( self.openstaand_kapitaal or 0 ) + \
                 ( self.wederbeleggingsvergoeding or 0 ) + \
                 ( self.nalatigheidsintresten_a or 0 ) + \
                 ( self.nalatigheidsintresten_b or 0 ) + \
                 ( self.onbetaalde_rente or 0 ) + \
                 ( self.rappelkosten or 0 ) + \
                 ( self.gerechtskosten or 0 ) + \
                 ( self.schadevergoeding_uitwinning or 0 ) - \
                 ( self.openstaande_betalingen or 0 )

     @transaction
     def button_canceled( self ):
         self.state = 'canceled'
         orm.object_session( self ).flush()

     def _validate_loan(self):
         if self.dossier is None:
             raise UserException('Gelieve eerst een dossier te selecteren')
         if self.datum_terugbetaling is None:
             raise UserException('Gelieve eerst een datum van terugbetaling te selecteren')
         if self.dossier.state == 'ended':
             raise UserException('Dossier is reeds beeindigd')

     def button_maak_voorstel( self ):
         self._validate_loan()
         session = orm.object_session( self )
         other_repayments = session.query(Terugbetaling)
         other_repayments = other_repayments.filter(sql.and_(Terugbetaling.dossier_id==self.dossier.id,
                                                             Terugbetaling.id!=self.id))
         for other_repayment in other_repayments:
             if other_repayment.state not in ('processed', 'canceled'):
                 raise UserException('Een eerdere terugbetaling werd niet afgewerkt',
                                     resolution='Annuleer de eerdere terugbetaling of pas deze aan',
                                     detail='De terugbetaling {0.id} in status {0.state}'.format(other_repayment))

         LOGGER.info( 'maak voorstel terugbetaling %s, dossier %s'%(self.id, self.dossier.nummer) )
         visitor = AbstractHypoVisitor()
         datum_stopzetting = self.dossier.startdatum

         repayment_doc_dates = set()
         payed_repayment_doc_dates = set()
         for loan_schedule in self.dossier.loan_schedules:
             for entry in visitor.get_entries(loan_schedule,
                                              fulfillment_types=['repayment', 'reservation'],
                                              thru_document_date=self.datum,
                                              account=CustomerBookingAccount()):
                 repayment_doc_dates.add(entry.doc_date)
                 if entry.open_amount == 0:
                     payed_repayment_doc_dates.add(entry.doc_date)

         if len(repayment_doc_dates):
             datum_stopzetting = max(datum_stopzetting, max(repayment_doc_dates))

         openstaande_vervaldagen = [ v for v in self.dossier.get_openstaande_vervaldagen( datum_stopzetting, 
                                                                                          tolerantie = 0) ]
         openstaande_vervaldagen_reeds_betaald = [ v for v in openstaande_vervaldagen if v.afpunt_datum ]
         LOGGER.debug('openstaande vervaldagen')
         for v in openstaande_vervaldagen:
             LOGGER.debug( str(v) )
         #
         # Zoek de laatst betaalde vervaldag
         #
         if len(payed_repayment_doc_dates):
             datum_laatst_betaalde_vervaldag = max(payed_repayment_doc_dates)
         else:
             datum_laatst_betaalde_vervaldag = self.dossier.startdatum
         openstaand_kapitaal = self.dossier.get_theoretisch_openstaand_kapitaal_at( datum_laatst_betaalde_vervaldag )
         #
         # Zoek openstaande vervaldagen voor de afsluitdatum die nog niet betaald zijn
         #
         openstaande_vervaldagen_voor_afsluiten = [ v for v in openstaande_vervaldagen if (v.doc_date <= datum_stopzetting and not v.afpunt_datum) ]
         nalatigheidsintresten_a = sum( [ v.intrest_a for v in openstaande_vervaldagen_voor_afsluiten ], 0 )
         nalatigheidsintresten_b = sum( [ v.intrest_b for v in openstaande_vervaldagen_voor_afsluiten ], 0 )
         onbetaalde_rente = sum( [ v.rente for v in openstaande_vervaldagen_voor_afsluiten ] )
         LOGGER.debug('openstaande vervaldagen voor afsluiten')
         for v in openstaande_vervaldagen_voor_afsluiten:
             LOGGER.debug(str(v))
         # 
         # Bepaal kosten van onbetaalde rappelbrieven
         #
         rappelkosten = 0
         for loan_schedule in self.dossier.loan_schedules:
             for entry in visitor.get_entries(loan_schedule,
                                              fulfillment_types=['reminder'],
                                              conditions=[('open_amount', operator.ne, 0)],
                                              account=CustomerBookingAccount()):
                 rappelkosten += entry.open_amount
         #
         # Bepaal de wederbeleggingsvergoeding
         #
         wederbeleggingsvergoeding, maand_rente = bepaal_wederbeleggingsvergoeding( self.dossier.goedgekeurd_bedrag, 
                                                                                    openstaand_kapitaal, 
                                                                                    0, 
                                                                                    self.dossier.startdatum, 
                                                                                    datum_stopzetting, 
                                                                                    self.datum,
                                                                                    self.euribor )
         #
         # Bepaal de openstaande betalingen voor de vervaldatum
         #
         
         som_openstaande_betalingen = -1 * sum( [b.open_amount for b in self.dossier.openstaande_betaling if b.book_date<=datum_stopzetting], 0 )
         openstaande_betalingen = som_openstaande_betalingen - sum( [v.te_betalen for v in openstaande_vervaldagen_reeds_betaald], 0 )
         dagrente_percentage = '%4f'%(maand_rente/30)
         with session.begin():
             self.datum_stopzetting = datum_stopzetting
             self.datum_laatst_betaalde_vervaldag = datum_laatst_betaalde_vervaldag
             self.openstaande_betalingen = openstaande_betalingen
             self.openstaand_kapitaal = openstaand_kapitaal
             self.nalatigheidsintresten_a = nalatigheidsintresten_a
             self.nalatigheidsintresten_b = nalatigheidsintresten_b
             self.onbetaalde_rente = onbetaalde_rente
             self.rappelkosten = rappelkosten
             self.wederbeleggingsvergoeding = wederbeleggingsvergoeding
             self.dagrente_percentage = dagrente_percentage
   
     @transaction
     def button_undo_process( self ):
         self.dossier.state = 'running'
         self.dossier.einddatum = None
         self.state = 'pending'
         orm.object_session( self ).flush()
         self.remove_from_venice()
         
     @transaction
     def button_process( self ):
         """Voer een terugbetaling door, doe nodige boekingen in venice en pas 
         status dossier aan"""
         from integration.venice.venice import d2v
         from integration.venice.sales_template import ( sales_header_desc,
                                                         sales_line_desc,
                                                         sales_header_data,
                                                         sales_line_data )
         self._validate_loan()
         vd, constants = get_dossier_bank()
         context = vd.CreateYearContext(self.datum_terugbetaling.year)
         balance = context.CreateBalan(False)
         visitor = AbstractHypoVisitor()
         goedgekeurd_bedrag = self.dossier.get_goedgekeurd_bedrag_at( self.datum_terugbetaling )
         product = goedgekeurd_bedrag.product
         book = product.get_book_at( 'transaction', self.datum_terugbetaling )
         LOGGER.info( 'terugbetaling %s, dossier %s'%(self.id, self.dossier.nummer) )
         line_dicts = []
         full_account_number = visitor.get_full_account_number_at( goedgekeurd_bedrag, self.datum_terugbetaling )
         customer = visitor.get_customer_at(goedgekeurd_bedrag, self.datum_terugbetaling)
         te_betalen = {
             'saldo_rekening_vordering':full_account_number,
             'wederbeleggingsvergoeding':int(product.get_account_at('wederbeleggingsvergoeding', self.datum_terugbetaling)),
             'nalatigheidsintresten':int(product.get_account_at('nalatigheidsintresten', self.datum_terugbetaling)),
             'rappelkosten':int(product.get_account_at('rappelkosten', self.datum_terugbetaling)),
             'gerechtskosten':int(product.get_account_at('gerechtskosten', self.datum_terugbetaling)),
             'schadevergoeding_uitwinning':int(product.get_account_at('schadevergoeding', self.datum_terugbetaling)),
             'dagrente_minus_intresten_geboekt_na_afsluiten_dossier':int(product.get_account_at('rente', self.datum_terugbetaling)),
         }
         for field, account in te_betalen.items():
             if field=='saldo_rekening_vordering':
                 amount = balance.GetBalance(full_account_number, 0)
             else:
                 amount = getattr( self, field )
             if amount:
                 remark = '%s terugbetaling dossier %s'%(field.replace('_',' '), self.dossier.nummer)
                 LOGGER.debug( '%s : %s'%(remark, amount) )
                 amount = float('%.2f'%amount)
                 line_dicts.append( dict(ent_amountdocc=-1.0 * amount, ent_account=account, ent_remark=remark) )
         total = -1 * sum( e['ent_amountdocc'] for e in line_dicts)
         header_dict = { 
             'cst_number':customer.accounting_number,
             'asl_docdate':d2v(self.datum_terugbetaling),
             'asl_bookdate':d2v(self.datum_terugbetaling),
             'asl_expdate':d2v(self.datum_terugbetaling),
             'asl_remark':'terugbetaling %s, dossier %s'%(self.id, self.dossier.nummer),
             'asl_totaldocc':'%.2f'%total,
             'asl_basenotsubmitdocc':'%.2f'%total,
             'asl_vatduenormdocc':'0.00',
             'asl_vatdednormdocc':'0.00',
             'asl_book':book,
             'asl_currency':'EUR',
         }
         self.state = 'processed'
         self.venice_book = book
         self.venice_book_type = 'Sales'
         self.dossier.state = 'ended'
         self.dossier.einddatum = self.datum_terugbetaling
         orm.object_session( self ).flush()
         if line_dicts:
             data,desc = vd.create_files( sales_header_desc, sales_line_desc, 
                                          sales_header_data, sales_line_data, 
                                          header_dict, line_dicts )
             sales = context.CreateSales(True)    
             sys_num, doc_num = vd.import_files(sales, desc, data)
         else:
             sys_num, doc_num = 0, 0
         LOGGER.debug('geboekt met sys_num : %s'%sys_num)
         self.venice_id = sys_num
         self.venice_doc = doc_num
         orm.object_session( self ).flush()

     def remove_from_venice( self ):
         # verify if we will be able to remove everything
         dossier, constants = get_dossier_bank()
         if not self.venice_id:
             raise UserException( 'object %s %s has no associated object in Venice'%(self.__class__.__name__, self.id) )
         # check if we can create a writeable year object for every year
         datum = self.datum
         venice_table = dossier.CreateYearContext(datum.year).CreateSales(True)
         venice_id = self.venice_id
         
         # remove all venice_ids
         self.venice_id = 0
         self.venice_doc = 0
         self.venice_book = ''
         self.venice_book_type = ''
         self.venice_active_year = ''
         orm.object_session( self ).flush()

         if venice_table.SeekBySysNum(constants.smEqual, venice_id):
             venice_table.Delete(constants.dmNoReport)

     def __unicode__(self):
          return u'%s : %s %s'%( self.full_number, 
                                 self.borrower_1_name or '', 
                                 self.borrower_2_name or '' )

     class Admin(VfinanceAdmin):
          verbose_name = _('Terugbetaling')
          verbose_name_plural = _('Terugbetalingen')
          form_state = 'maximized'
          list_display =  ['full_number', 'borrower_1_name', 'borrower_2_name', 'datum', 'datum_terugbetaling', 'state']
          list_search = ['dossier.nummer', 'dossier.roles.rechtspersoon.name', 'dossier.roles.natuurlijke_persoon.name']
          list_filter = ['state', list_filter.ComboBoxFilter('dossier.company_id', verbose_name=_('Maatschappij'))]
          form_actions = [ CallMethod( _('Maak voorstel'), lambda o:o.button_maak_voorstel(), enabled=lambda o:(o is not None) and (o.state=='pending') ),
                           CallMethod( _('Voer door'), lambda o:o.button_process(), enabled=lambda o:(o is not None) and (o.state == 'pending') ),
                           CallMethod( _('Undo doorvoeren'), lambda o:o.button_undo_process(), enabled=lambda o:(o is not None) and (o.state == 'processed') ),
                           CallMethod( _('Annuleer'), lambda o:o.button_canceled(), enabled=lambda o:(o is not None) and (o.state=='pending') ),
                           OverzichtWederbeleggingsvergoeding(), 
                           RedemptionAction( ), ]
          form_display =  forms.TabForm( [ ( _('Terugbetaling'),
                                             forms.Form( ['dossier', 'datum', 'state',
                                                          forms.GroupBoxForm(_('Info'),['goedgekeurde_rente','goedgekeurde_looptijd',
                                                                                        'goedgekeurd_type_aflossing','goedgekeurd_terugbetaling_interval',], columns=2),
                                                          forms.GroupBoxForm(_('Te betalen'),[
                                                              'euribor', forms.Break(),
                                                              'datum_laatst_betaalde_vervaldag',
                                                              'datum_stopzetting','openstaand_kapitaal',
                                                              'wederbeleggingsvergoeding','nalatigheidsintresten_a',
                                                              'nalatigheidsintresten_b','onbetaalde_rente',
                                                              'rappelkosten','gerechtskosten',
                                                              'schadevergoeding_uitwinning',
                                                              'openstaande_betalingen', forms.Break(),
                                                              'te_betalen',], columns=2),
                                                          forms.GroupBoxForm(_('Dagrente'),['dagrente_percentage', forms.Break(),
                                                                                            'dagrente_bedrag', forms.Break(),
                                                                                            'datum_terugbetaling', forms.Break(),
                                                                                            'aantal_dagen', forms.Break(),
                                                                                            'dagrente_correctie', forms.Break(),
                                                                                            'dagrente', forms.Break(),
                                                                                            'intresten_geboekt_na_afsluiten_dossier',
                                                                                            'openstaande_betalingen_na_afsluiten_dossier', forms.Break(),
                                                                                            'dagrente_minus_intresten_geboekt_na_afsluiten_dossier',], columns=2),
                                                          forms.GroupBoxForm(_('Totaal'), [
                                                              'totaal', forms.Break()], columns=2),
                                                          forms.Stretch(),
                                                          ], columns = 2, scrollbars = True) ),
                                           ( _('Extra'), forms.Form( ['venice_id','venice_doc',forms.Stretch()], columns = 2 ) ) ] )
          
          field_attributes = {'onbetaalde_rente':{'editable':True, 'name':_('Onbetaalde rente')},
                              'openstaande_betalingen':{'editable':True, 'name':_('Openstaande betalingen')},
                              'nalatigheidsintresten_a':{'editable':True, 'name':_('Nalatigheidsintresten a')},
                              'dagrente_bedrag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Dagrente (bedrag per dag)')},
                              'open_amount':{'editable':False, 'name':_('Openstaand bedrag')},
                              'datum':{'editable':True, 'name':_('Datum')},
                              'dagrente_minus_intresten_geboekt_na_afsluiten_dossier':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Dagrente (te boeken bedrag)')},
                              'totaal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totaal te betalen')},
                              'nalatigheidsintresten_b':{'editable':True, 'name':_('Nalatigheidsintresten b')},
                              'rappelkosten':{'editable':True, 'name':_('Rappelkosten')},
                              'dagrente_correctie':{'editable':True, 'name':_('Correctie bedrag dagrente')},
                              'nalatigheidsintresten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Nalatigheidsintresten')},
                              'goedgekeurd_terugbetaling_interval':{'editable':False, 
                                                                    'delegate':delegates.ComboBoxDelegate,
                                                                    'choices':constants.hypo_terugbetaling_intervallen,
                                                                    'name':_('Terugbetaling')},
                              'goedgekeurde_looptijd':{ 'editable':False, 
                                                        'delegate':delegates.IntegerDelegate,
                                                        'name':_('Goedgekeurde looptijd (maanden)') },
                              'wederbeleggingsvergoeding':{'editable':True, 'name':_('Wederbeleggingsvergoeding')},
                              'te_betalen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Te betalen')},
                              'goedgekeurde_rente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde rente')},
                              'state':{'editable':False, 'name':_('Status'), 'choices':[('pending', 'Wachtend'),
                                                                                        ('doorgevoerd', 'Doorgevoerd'),
                                                                                        ('processed', 'Doorgevoerd'), 
                                                                                        ('canceled', 'Geannulleerd'), 
                                                                                        ('ticked', 'Afgepunt')]},
                              'schadevergoeding_uitwinning':{'editable':True, 'name':_('Schadevergoeding uitwinning')},
                              'venice_book_type':{'editable':False, 'name':_('Dagboek Type')},
                              'venice_book':{'editable':False, 'name':_('Dagboek')},
                              'gerechtskosten':{'editable':True, 'name':_('Gerechtskosten')},
                              'venice_doc':{'editable':False, 'name':_('Document Nummer Venice')},
                              'openstaande_betalingen_na_afsluiten_dossier':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Openstaande betalingen na afsluiten dossier')},
                              'intresten_geboekt_na_afsluiten_dossier':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Geboekte intresten na afsluiten dossier')},
                              'datum_terugbetaling':{'editable':True, 'name':_('Datum van terugbetaling')},
                              'venice_active_year':{'editable':False, 'name':_('Actief jaar')},
                              'dagrente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Dagrente (eindbedrag)')},
                              'datum_stopzetting':{'editable':True, 'name':_('Datum stopzetting rekening')},
                              'openstaand_kapitaal':{'editable':True, 'name':_('Openstaand Kapitaal')},
                              'euribor':{'name':_('Euribor'), 'suffix': ' %'},
                              'full_number':{'name': _('Dossier')},
                              'dossier':{'editable':True, 'name':_('Hypotheek dossier')},
                              'goedgekeurd_type_aflossing':{ 'editable':False, 
                                                             'delegate':delegates.ComboBoxDelegate,
                                                             'choices':constants.hypo_types_aflossing,
                                                             'name':_('Goedgekeurd type aflossing') },
                              'dagrente_percentage':{'editable':True, 'name':_('Dagrente (percentage)')},
                              'datum_laatst_betaalde_vervaldag':{'editable':True, 'name':_('Datum laatst betaalde vervaldag')},
                              'venice_id':{'editable':False, 'name':_('Systeem Nummer Venice')},
                              'aantal_dagen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Aantal dagen')},
                             }

          def get_query(self, *args, **kwargs):
              query = VfinanceAdmin.get_query(self, *args, **kwargs)
              query = query.options(orm.subqueryload('dossier'))
              query = query.options(orm.subqueryload('dossier.roles'))
              query = query.options(orm.subqueryload('dossier.roles.natuurlijke_persoon'))
              query = query.options(orm.subqueryload('dossier.roles.rechtspersoon'))
              query = query.options(orm.undefer('dossier.roles.natuurlijke_persoon.name'))
              query = query.options(orm.undefer('dossier.roles.rechtspersoon.name'))
              return query
