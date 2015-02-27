from datetime import date
from decimal import Decimal as D
import calendar
import datetime
import logging
import math

import sqlalchemy.types
from sqlalchemy import orm, sql, schema

from camelot.core.orm import ( Entity, ManyToOne, using_options )
from camelot.admin.action import CallMethod, list_filter
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import transaction
import camelot.types

from integration.tinyerp.convenience import months_between_dates

from vfinance.admin.vfinanceadmin import VfinanceAdmin

from mortgage_table import aflossingen_van_bedrag, hoogste_aflossing
from akte import akte_line_desc, akte_header_data, akte_header_desc, akte_line_data
from vfinance.model.bank.venice import get_dossier_bank
from .visitor import AbstractHypoVisitor
from .notification.mortgage_table import MortgageTable
from .hypotheek import HypoApplicationMixin

LOGGER = logging.getLogger('vfinance.model.hypo.wijziging')

wet13398 = date(year=1998, month=3, day=13)
modaliteiten4 = ['type_aflossing', 'type_vervaldag', 'terugbetaling_interval']
#  Sunday
#  oneWeek
#  March
variabiliteit_historiek_modaliteiten = [('referentie_index', 'Referentie index'), ('minimale_afwijking', 'Minimale afwijking'), ('maximale_stijging', 'Maximale stijging'), ('maximale_daling', 'Maximale daling'), ('maximale_spaar_ristorno', 'Maximale spaar ristorno'), ('maximale_product_ristorno', 'Maximale ristorno gebonden producten'), ('maximale_conjunctuur_ristorno', 'Maximale conjunctuur ristorno')]
#  Friday
#  MinDateTime
dossier_statussen = [('opnameperiode', 'In opname periode'), ('running', 'Lopende'), ('ended', 'Beeindigd')]
modaliteiten1 = ['rente', 'opname_periode', 'opname_schijven', 'reserverings_provisie', 'aflossing', 'intrest_a', 'intrest_b', 'jaarrente']
#  done_form
variabiliteit_type_modaliteiten = [('eerste_herziening', 'Eerste herziening na (maanden)'), ('volgende_herzieningen', 'Daarna herzieningen om de (maanden)'), ('eerste_herziening_ristorno', 'Eerste herziening ristorno na (maanden)'), ('volgende_herzieningen_ristorno', 'Daarna herzieningen ristorno om de (maanden)')]
#  oneDay
#  mxDateTimeAPI
#  Epoch
#  books
#  July
#  oneMinute
#  September
#  December
#  Tuesday
#  Month
#  wet13398
#  MaxDateTimeDelta

class Wijziging(Entity, HypoApplicationMixin):
     """De hypotheek wijziging klasse laat toe wijzigingen aan een hypotheek dossier aan te
     brengen, en ze tevens te traceren"""

     _book = 'NewHy'

     using_options(tablename='hypo_wijziging')
     origin  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     nieuwe_eerste_herziening_ristorno  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     nieuw_terugbetaling_start  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     datum_wijziging  =  schema.Column(sqlalchemy.types.Date(), nullable=False, default = datetime.date.today)
     open_amount  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False, default = datetime.date.today)
     nieuwe_rente  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
     nieuw_type_aflossing  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     nieuw_bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     #nieuw_goedgekeurd_bedrag = OneToMany('vfinance.model.hypo.beslissing.GoedgekeurdBedrag', inverse='wijziging')
     nieuwe_volgende_herzieningen  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     nieuwe_maximale_daling  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
     huidige_status  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     nieuwe_opname_schijven  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     nieuwe_opname_periode  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     dossier_id  =  schema.Column(sqlalchemy.types.Integer(), name='dossier', nullable=False, index=True)
     dossier  =  ManyToOne('vfinance.model.hypo.dossier.Dossier', field=dossier_id)
     nieuwe_reserverings_provisie  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
     nieuwe_looptijd  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     nieuwe_eerste_herziening  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     nieuw_vast_bedrag = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2))
     nieuwe_volgende_herzieningen_ristorno  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     wederbeleggingsvergoeding  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
     nieuwe_status  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True, default = unicode('draft') )
     nieuwe_maximale_product_ristorno  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
     opmerking  =  schema.Column(camelot.types.RichText(), nullable=True)

     @property
     def huidig_bedrag(self):
          LOGGER.debug('get huidig bedrag')
          if self.vorig_goedgekeurd_bedrag and self.vorige_startdatum:
               if self.dossier.state=='opnameperiode':
                    return self.vorig_goedgekeurd_bedrag.goedgekeurd_bedrag
               else:
                    for aflossing in aflossingen_van_bedrag( self.vorig_goedgekeurd_bedrag, 
                                                             self.vorige_startdatum):
                         if aflossing.datum >= self.datum_wijziging:
                              # we gaan er van uit dat de wijziging in voegen treedt na de laatste aflossing
                              return aflossing.saldo + aflossing.kapitaal
                    return 0
          return None

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
     def nieuw_goedgekeurd_bedrag(self):
          from beslissing import GoedgekeurdBedrag
          return GoedgekeurdBedrag.query.filter( GoedgekeurdBedrag.wijziging_id == self.id ).first()

     nieuwe_maximale_stijging  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
     vorige_startdatum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     huidige_volgende_herzieningen  =  property(lambda self:self.get_huidige_volgende_herzieningen())
     nieuwe_jaarrente  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
     nieuwe_maximale_conjunctuur_ristorno  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
     vorig_goedgekeurd_bedrag_id  =  schema.Column(sqlalchemy.types.Integer(), name='vorig_goedgekeurd_bedrag', nullable=True, index=True)
     vorig_goedgekeurd_bedrag  =  ManyToOne('vfinance.model.hypo.beslissing.GoedgekeurdBedrag', field=vorig_goedgekeurd_bedrag_id)
     nieuwe_maximale_spaar_ristorno  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
     euribor  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True, default = 4)
     huidige_volgende_herzieningen_ristorno  =  property(lambda self:self.get_huidige_volgende_herzieningen_ristorno())
     nieuwe_minimale_afwijking  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
     nieuwe_referentie_index  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
     nieuwe_intrest_a  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
     nieuwe_intrest_b  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
     
     venice_book_type  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     venice_book  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     venice_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     venice_active_year  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     venice_doc  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)

     goedgekeurd_index_type_id  =  schema.Column(sqlalchemy.types.Integer(), name='goedgekeurd_index_type', nullable=True, index=True)
     goedgekeurd_index_type  =  ManyToOne('vfinance.model.bank.index.IndexType', field=goedgekeurd_index_type_id)

     def __getattr__( self, name ):
          from beslissing import modaliteiten1, modaliteiten2, modaliteiten4
          from rentevoeten import variabiliteit_type_modaliteiten, variabiliteit_historiek_modaliteiten
          if name.startswith( 'goedgekeurd_' ):
               suffix = name[len('goedgekeurd_'):]
               if suffix in modaliteiten2 + modaliteiten4:
                    if self.vorig_goedgekeurd_bedrag == None:
                         return None
                    return getattr( self.vorig_goedgekeurd_bedrag, name )
          if name.startswith( 'goedgekeurde_' ):
               suffix = name[len('goedgekeurde_'):]
               if suffix in modaliteiten1 + [n for n,t_ in variabiliteit_type_modaliteiten] + [n for n,t_ in variabiliteit_historiek_modaliteiten] + ['looptijd']:
                    if self.vorig_goedgekeurd_bedrag == None:
                         return None
                    return getattr( self.vorig_goedgekeurd_bedrag, name )
          if name.startswith( 'huidige_' ):
               suffix = name[len('huidige_'):]
               if suffix in ['maximale_spaar_ristorno', 'maximale_product_ristorno', 'maximale_conjunctuur_ristorno', 'jaarrente', 'intrest_a', 'intrest_b', 'reserverings_provisie']:
                    if self.vorig_goedgekeurd_bedrag == None:
                         return None
                    return getattr( self.vorig_goedgekeurd_bedrag, 'goedgekeurde_%s'%suffix )
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
     def huidig_aantal_aflossingen( self ):
          if not self.vorig_goedgekeurd_bedrag:
               return 0    
          return int(math.ceil((self.huidige_looptijd * self.goedgekeurd_terugbetaling_interval / 12)))

     @property
     def huidige_aflossing( self ):
          if not self.vorig_goedgekeurd_bedrag:
               return 0
          return hoogste_aflossing(D(self.huidige_rente), self.goedgekeurd_type_aflossing, self.huidig_bedrag, self.huidig_aantal_aflossingen, 
                                   (12/self.goedgekeurd_terugbetaling_interval), jaar_rente=D(self.vorig_goedgekeurd_bedrag.goedgekeurde_jaarrente or 0)*100)

     @property
     def huidige_looptijd( self ):
          if self.vorig_goedgekeurd_bedrag and self.vorige_startdatum:
               if self.dossier.state=='opnameperiode':
                    return self.vorig_goedgekeurd_bedrag.goedgekeurde_looptijd
               else:      
                    passed_months = months_between_dates((self.vorige_startdatum), (self.datum_wijziging))
                    LOGGER.debug('passed months : %s'%passed_months)
                    if passed_months > self.goedgekeurd_terugbetaling_start:
                         return max( self.goedgekeurde_looptijd + (self.goedgekeurd_terugbetaling_start or 0) - passed_months, 0)
                    else:
                         return self.goedgekeurde_looptijd
          return 0

     @property
     def huidige_opname_periode( self ):
          if self.vorig_goedgekeurd_bedrag and self.vorige_startdatum:
               passed_months = months_between_dates((self.vorige_startdatum), (self.datum_wijziging))
               if self.dossier.state=='opnameperiode':
                    return max((self.vorig_goedgekeurd_bedrag.goedgekeurde_opname_periode or 0) - passed_months, 0)
               else:
                    return 0
          return 0

     @property
     def huidige_opname_schijven( self ):
          if self.vorig_goedgekeurd_bedrag and self.vorige_startdatum:
               passed_months = months_between_dates((self.vorige_startdatum), (self.datum_wijziging))
               return max( (self.vorig_goedgekeurd_bedrag.goedgekeurde_opname_schijven or 0) - passed_months, 0)
          return 0  

     @property
     def huidige_eerste_herziening( self ):
          if self.vorig_goedgekeurd_bedrag and self.vorige_startdatum:
               passed_months = months_between_dates((self.vorige_startdatum), (self.datum_wijziging))
               if passed_months >= self.goedgekeurde_eerste_herziening:
                    return self.goedgekeurde_volgende_herzieningen
               else:
                    return self.goedgekeurde_eerste_herziening - passed_months
          return 0

     @property
     def huidige_volgende_herzieningen( self ):
          return self.goedgekeurde_volgende_herzieningen

     @property
     def huidige_eerste_herziening_ristorno( self ):
          if self.vorig_goedgekeurd_bedrag and self.vorige_startdatum:
               passed_months = months_between_dates((self.vorige_startdatum), (self.datum_wijziging))
               if passed_months >= self.goedgekeurde_eerste_herziening_ristorno:
                    return self.goedgekeurde_volgende_herzieningen_ristorno
               else:
                    return self.goedgekeurde_eerste_herziening_ristorno - passed_months

     @property
     def huidige_volgende_herzieningen_ristorno( self ):
          return self.goedgekeurde_volgende_herzieningen_ristorno

     @property
     def huidige_referentie_index( self ):
          from ..bank.index import IndexHistory, index_volgens_terugbetaling_interval
          if self.vorig_goedgekeurd_bedrag and self.goedgekeurd_index_type:
               datum_wijziging = ( self.datum_wijziging )
               index_delta = 1
               if (self.dossier.beslissing_nieuw.datum_voorwaarde)<wet13398:
                    index_delta = 2
               datum_index = date( day = 1, 
                                   month = datum_wijziging.month-index_delta+{True:12,False:0}[datum_wijziging.month<=index_delta], 
                                   year = datum_wijziging.year-{True:1,False:0}[datum_wijziging.month<=index_delta])
               index_historiek = IndexHistory.query.filter( sql.and_( IndexHistory.described_by == self.goedgekeurd_index_type,
                                                                      IndexHistory.from_date <= datum_index ) ).order_by( IndexHistory.from_date.desc() ).first()
               if index_historiek:
                    return index_volgens_terugbetaling_interval(index_historiek.value, self.goedgekeurd_terugbetaling_interval)
          else:
               return 0

     @property
     def huidige_rente( self ):
          LOGGER.debug('get huidige rente')
          if self.vorig_goedgekeurd_bedrag and self.vorige_startdatum:
               passed_months = months_between_dates((self.vorige_startdatum), (self.datum_wijziging))
               LOGGER.debug('passed months ' + str(passed_months) )
               LOGGER.debug('index type ' + str(self.goedgekeurd_index_type) )
               if self.goedgekeurd_index_type and passed_months >= self.goedgekeurde_eerste_herziening:
                    huidige_rente = D(self.goedgekeurde_rente)
                    LOGGER.debug('datum voorwaarde ' + str(self.dossier.beslissing_nieuw.datum_voorwaarde) )
                    if (self.dossier.beslissing_nieuw.datum_voorwaarde)<wet13398:
                         huidige_rente = huidige_rente*D(self.huidige_referentie_index)/D(self.goedgekeurde_referentie_index) 
                    else:
                         huidige_rente = huidige_rente - D(self.goedgekeurde_referentie_index) + D(self.huidige_referentie_index)
                    LOGGER.debug('aangepaste rente voor aftopping ' + str(huidige_rente))
                    huidige_rente = min(huidige_rente, D(self.goedgekeurde_rente) +  D(self.goedgekeurde_maximale_stijging) )
                    huidige_rente = max(huidige_rente, D(self.goedgekeurde_rente) +  D(self.goedgekeurde_maximale_daling) )
                    LOGGER.debug('aangepaste rente na aftopping ' + str(huidige_rente))
                    if abs(huidige_rente-D(self.goedgekeurde_rente))<D(self.goedgekeurde_minimale_afwijking):
                         LOGGER.debug('wijziging te klein, return goedgekeurde rente ' + str(self.goedgekeurde_rente))
                         return self.goedgekeurde_rente
                    LOGGER.debug('wijziging groot genoeg, return gewijzigde rente' + str(self.goedgekeurde_rente))
                    return '%.4f'%huidige_rente
               else:
                    LOGGER.debug('return goedgekeurde rente' + str(self.goedgekeurde_rente) )
                    return self.goedgekeurde_rente
          LOGGER.debug('return default 0')
          return 0

     @property
     def huidige_minimale_afwijking( self ):
          if self.vorig_goedgekeurd_bedrag and self.goedgekeurd_index_type:
               return self.goedgekeurde_minimale_afwijking
          else:
               return 0

     @property
     def huidige_maximale_stijging( self ):
          if self.vorig_goedgekeurd_bedrag and self.goedgekeurd_index_type:
               return '%.4f'%(D(self.goedgekeurde_maximale_stijging) - (D(self.huidige_rente) - D(self.goedgekeurde_rente)))
          else:
               return 0

     @property
     def huidig_type_aflossing( self ):
          if self.vorig_goedgekeurd_bedrag:
               return self.vorig_goedgekeurd_bedrag.goedgekeurd_type_aflossing
          return 'vaste_aflossing'

     @property
     def huidige_maximale_daling( self ):
          if self.vorig_goedgekeurd_bedrag and self.goedgekeurd_index_type:
               return '%.4f'%(D(self.goedgekeurde_maximale_daling) - (D(self.huidige_rente) - D(self.goedgekeurde_rente)))
          else:
               return 0

     @property
     def huidig_terugbetaling_start( self ):
          if self.vorig_goedgekeurd_bedrag and self.vorige_startdatum:
               passed_months = months_between_dates((self.vorige_startdatum), (self.datum_wijziging))
               if self.dossier.state=='opnameperiode':
                    return self.vorig_goedgekeurd_bedrag.goedgekeurd_terugbetaling_start
               else:
                    if passed_months > self.vorig_goedgekeurd_bedrag.goedgekeurd_terugbetaling_start:
                         return 0
                    else:
                         return max(self.vorig_goedgekeurd_bedrag.goedgekeurd_terugbetaling_start - passed_months, 0)
          return 0

     @property
     def nieuw_aantal_aflossingen( self ):
          return {True:lambda:0, False:lambda:int(math.ceil(self.nieuwe_looptijd * self.vorig_goedgekeurd_bedrag.goedgekeurd_terugbetaling_interval / 12))}[self.vorig_goedgekeurd_bedrag==None]()

     @property
     def nieuwe_aflossing( self ):
          return {True:lambda:0, 
                  False:lambda:hoogste_aflossing(D(self.nieuwe_rente), 
                                                 self.nieuw_type_aflossing or self.vorig_goedgekeurd_bedrag.goedgekeurd_type_aflossing, 
                                                 self.nieuw_bedrag, 
                                                 self.nieuw_aantal_aflossingen, 
                                                 (12/self.vorig_goedgekeurd_bedrag.goedgekeurd_terugbetaling_interval), 
                                                 jaar_rente=D(self.nieuwe_jaarrente or 0)*100)}[self.vorig_goedgekeurd_bedrag==None]()


     def button_maak_voorstel( self ):
          LOGGER.debug('maak voorstel : bedrag %s, datum %s'%(self.dossier.goedgekeurd_bedrag.id, self.dossier.startdatum ))
          today = datetime.date.today()
          first_day, max_day = calendar.monthrange(today.year, today.month)
          voorstel_datum_wijziging = date(today.year, today.month, min(self.dossier.startdatum.day,max_day))
          return self.button_maak_voorstel_op_datum( voorstel_datum_wijziging )

     def button_maak_voorstel_op_datum( self, voorstel_datum_wijziging ):
          index_type = None
          if self.dossier.goedgekeurd_bedrag.goedgekeurd_index_type:
               index_type = self.dossier.goedgekeurd_bedrag.goedgekeurd_index_type
          self.goedgekeurd_index_type = index_type
          self.vorig_goedgekeurd_bedrag = self.dossier.goedgekeurd_bedrag 
          self.vorige_startdatum = self.dossier.startdatum 
          self.datum_wijziging = voorstel_datum_wijziging
          self.huidige_status = self.dossier.state
          update = dict( [('nieuwe_%s'%m,getattr(self,'huidige_%s'%m)) for m in (modaliteiten1 + modaliteiten3 + ['status'] + [field for field,name in variabiliteit_historiek_modaliteiten + variabiliteit_type_modaliteiten])] + [('nieuw_%s'%m, getattr(self, 'huidig_%s'%m)) for m in modaliteiten2])
          update['nieuw_type_aflossing'] = self.huidig_type_aflossing
          if abs(D(self.goedgekeurde_rente)-D(self.huidige_rente))<D('0.000001'):
               update['nieuwe_referentie_index'] = self.goedgekeurde_referentie_index
          for key, value in update.items():
               if key != 'nieuwe_aflossing': # this is read only
                    setattr( self, key, value )
          orm.object_session( self ).flush()

     def button_wederbeleggingsvergoeding( self ):
          from . import terugbetaling
          wdb, _maandrente = terugbetaling.bepaal_wederbeleggingsvergoeding( self.dossier.goedgekeurd_bedrag, 
                                                                             self.huidig_bedrag, 
                                                                             self.nieuw_bedrag, 
                                                                             self.dossier.startdatum, 
                                                                             self.datum_wijziging,
                                                                             self.datum,
                                                                             D(self.euribor) )
          self.wederbeleggingsvergoeding = wdb
          orm.object_session( self ).flush()

     @transaction
     def button_cancel( self ):
          self.state = 'canceled'
          orm.object_session( self ).flush()

     @transaction
     def button_approve( self ):
          self.state = 'approved'
          orm.object_session( self ).flush()	 

     @transaction
     def button_process( self ):
          self.process()
          
     def process(self):
          #
          # There's a special dummy state 'importing' which allows to process wijzigingen without
          # touching Venice
          #
          visitor = AbstractHypoVisitor()
          from beslissing import GoedgekeurdBedrag
          from integration.venice.venice import d2v
          original_state = self.state
          if original_state in ('approved', 'importing'):
               product = self.vorig_goedgekeurd_bedrag.product
               delta_bedrag = self.nieuw_bedrag-self.huidig_bedrag
               sys_num = 0
               doc_num = 0
               d = dict( ('goedgekeurde_%s'%m, getattr( self, 'nieuwe_%s'%m )) for m in (modaliteiten1+modaliteiten3) if m!='aflossing' )
               d.update( ('goedgekeurde_%s'%m, getattr( self, 'nieuwe_%s'%m )) for m,name in variabiliteit_type_modaliteiten + variabiliteit_historiek_modaliteiten )
               d.update( ('goedgekeurd_%s'%m, getattr( self, 'nieuw_%s'%m )) for m in modaliteiten2 )
               if self.goedgekeurd_index_type:
                    d['goedgekeurd_index_type']=self.goedgekeurd_index_type
               d['goedgekeurd_vast_bedrag'] = self.nieuw_vast_bedrag
               d['goedgekeurd_type_aflossing'] = self.nieuw_type_aflossing or self.vorig_goedgekeurd_bedrag.goedgekeurd_type_aflossing
               d['goedgekeurd_type_vervaldag'] = self.vorig_goedgekeurd_bedrag.goedgekeurd_type_vervaldag
               d['goedgekeurd_terugbetaling_interval'] = self.vorig_goedgekeurd_bedrag.goedgekeurd_terugbetaling_interval
               d['bedrag'] = self.vorig_goedgekeurd_bedrag.bedrag
               d['type'] = 'wijziging'
               d['product'] = self.vorig_goedgekeurd_bedrag.product
               d['wijziging_id'] = self.id
               d['venice_id'] = sys_num
               d['venice_doc'] = doc_num
               d['state'] = 'processed'
               LOGGER.info('wijzig dossier %s naar %s'%(self.dossier.nummer, d))
               goedgekeurd_bedrag = GoedgekeurdBedrag( **d )
               einddatum = self.dossier.einddatum
               if self.nieuwe_status in ('running', 'opnameperiode'):
                    einddatum = None
               if self.nieuwe_status in ('ended',):
                    einddatum = self.datum_wijziging
               self.state = 'processed'
               self.dossier.goedgekeurd_bedrag = goedgekeurd_bedrag
               self.dossier.startdatum = self.datum_wijziging
               self.dossier.einddatum = einddatum
               self.dossier.state = self.nieuwe_status
               orm.object_session( self ).flush()
               if abs(delta_bedrag) > D('0.001') and original_state!='importing':
                    vd, constants = get_dossier_bank()
                    account_vordering = visitor.get_full_account_number_at( self.dossier.goedgekeurd_bedrag, self.datum_wijziging )
                    account_klant = visitor.get_customer_at( self.dossier.goedgekeurd_bedrag, self.datum_wijziging ).full_account_number
                    remark = 'wijziging ontleend bedrag dossier %s'%self.dossier.nummer
                    header_dict = { 'snd_bookdate':d2v(self.datum_wijziging),
                                    'snd_remark':remark,
                                    'snd_book':product.get_book_at( 'completion', self.datum_wijziging ),
                                    }
                    line_dicts = []
                    line_dicts.append(dict(ent_amountdocc=delta_bedrag, ent_remark=remark, ent_account=account_vordering))
                    line_dicts.append(dict(ent_amountdocc=(-1*delta_bedrag)+self.wederbeleggingsvergoeding, ent_remark=remark, ent_account=account_klant))
                    line_dicts.append(dict(ent_amountdocc=-1*self.wederbeleggingsvergoeding, ent_remark=remark, ent_account=int(product.get_account_at('wederbeleggingsvergoeding', self.datum_wijziging) )))
                    (name_data, name_desc) = vd.create_files(akte_header_desc, akte_line_desc, akte_header_data, akte_line_data, header_dict, line_dicts)
                    context = vd.CreateYearContext(self.datum_wijziging.year)
                    sndry = context.CreateSndry(True)
                    sys_num, doc_num = vd.import_files(sndry, name_desc, name_data)
                    LOGGER.info('geboekt met sys_num : %s'%sys_num)         
                    self.venice_id = sys_num
                    self.venice_doc = doc_num
               orm.object_session( self ).flush()
               return goedgekeurd_bedrag

     @transaction
     def button_remove( self ):
          session = orm.object_session( self )
          if self.state=='processed' and self.vorig_goedgekeurd_bedrag and self.vorige_startdatum:
               datum = self.datum_wijziging
               venice_doc = self.venice_doc	
               nieuwe_goedgekeurd_bedrag = self.dossier.goedgekeurd_bedrag
               self.dossier.goedgekeurd_bedrag = self.vorig_goedgekeurd_bedrag
               self.dossier.startdatum = self.vorige_startdatum 
               self.dossier.einddatum = self.dossier.einddatum
               self.dossier.state = self.huidige_status
               session.delete( nieuwe_goedgekeurd_bedrag )
               self.state = 'draft' 
               session.flush()
               if venice_doc:
                    vd, constants = get_dossier_bank()
                    context = vd.CreateYearContext(datum.year)
                    sndry = context.CreateSndry(True)
                    LOGGER.debug('verwijder wijziging %s met venice doc %s'%(self.id, venice_doc))
                    if sndry.SeekByDocNum(constants.smEqual, self._book, venice_doc):
                         LOGGER.debug('found in Venice')
                         sndry.Delete(constants.dmNoReport)
                         LOGGER.warn('wijziging met doc num %s in boekjaar %s verwijderd'%(venice_doc, datum.year))
                    self.venice_id = 0
                    self.venice_doc = 0
                    session.flush()

     def __unicode__(self):
          if self.datum and self.dossier:
               return u'%s %s'%( unicode( self.dossier ), unicode( self.datum ) )
          return u''

     class Admin(VfinanceAdmin):
          verbose_name = _('Wijziging')
          verbose_name_plural = _('Wijzigingen')
          list_display =  ['full_number', 'borrower_1_name', 'borrower_2_name', 'datum', 'state', 'huidige_status', 'nieuwe_status']
          list_search = ['dossier.nummer', 'dossier.roles.rechtspersoon.name', 'dossier.roles.natuurlijke_persoon.name']
          list_filter = ['state', list_filter.ComboBoxFilter('dossier.company_id', verbose_name=_('Maatschappij'))]
          form_state = 'maximized'
          form_actions = [ CallMethod( _('Maak voorstel'), lambda o:o.button_maak_voorstel(), enabled=lambda o:(o is not None) and (o.state=='draft') ),
                           CallMethod( _('Bepaal\nwederbeleggingsvergoeding'), lambda o:o.button_wederbeleggingsvergoeding(), enabled=lambda o:(o is not None) and (o.state=='draft') ),
                           CallMethod( _('Annuleer'), lambda o:o.button_cancel(), enabled=lambda o:(o is not None) and (o.state in ('draft', 'approved')) ),
                           CallMethod( _('Keur goed'), lambda o:o.button_approve(), enabled=lambda o:(o is not None) and (o.state=='draft' ) ),
                           CallMethod( _('Voer door'), lambda o:o.button_process(), enabled=lambda o:(o is not None) and (o.state=='approved') ),
                           CallMethod( _('Undo doorvoeren'), lambda o:o.button_remove(), enabled=lambda o:(o is not None) and (o.state=='processed') ),
                           MortgageTable(),
                           ]
          form_display =  forms.TabForm( [(_('Wijziging'), forms.Form([ 'dossier','datum',
                                                                        'vorige_startdatum', 'datum_wijziging', 
                                                                        'euribor','wederbeleggingsvergoeding', 
                                                                        'state', 'opmerking'], columns=2)),
                                          (_('Modaliteiten'), 
                                           forms.GridForm( [ [ forms.Label(''),                     forms.Label(_('Vorige')),             forms.Label(_('Op datum wijziging')), forms.Label(_('Wijzigen naar')) ],
                                                             [ forms.Label('Bedrag'),               'goedgekeurd_bedrag',                 'huidig_bedrag',                      'nieuw_bedrag'],
                                                             [ forms.Label('Rente'),                'goedgekeurde_rente',                 'huidige_rente',                      'nieuwe_rente'],
                                                             [ forms.Label('Reserveringsprovisie'), 'goedgekeurde_reserverings_provisie', 'huidige_reserverings_provisie',      'nieuwe_reserverings_provisie'],
                                                             [ forms.Label('Looptijd'),             'goedgekeurde_looptijd',              'huidige_looptijd',                   'nieuwe_looptijd'],
                                                             [ forms.Label('Opname periode'),       'goedgekeurde_opname_periode',        'huidige_opname_periode',             'nieuwe_opname_periode'],
                                                             [ forms.Label('Opname schijven'),      'goedgekeurde_opname_schijven',       'huidige_opname_schijven',            'nieuwe_opname_schijven'],
                                                             [ forms.Label('Uitstel betaling'),     'goedgekeurd_terugbetaling_start',    'huidig_terugbetaling_start',         'nieuw_terugbetaling_start'],
                                                             [ forms.Label('Type aflossing'),       'huidig_type_aflossing',              'huidig_type_aflossing',              'nieuw_type_aflossing'],
                                                             [ forms.Label('Aflossing'),            'goedgekeurde_aflossing',             'huidige_aflossing',                  'nieuwe_aflossing'],
                                                             [ forms.Label('Status'),               'huidige_status',                     'huidige_status',                     'nieuwe_status' ],
                                                             ] ) ),
                                          (_('Variabiliteit'), 
                                           forms.GridForm( [ [ forms.Label(''),                      forms.Label(_('Vorige')),             forms.Label(_('Op datum wijziging')), forms.Label(_('Wijzigen naar')) ],
                                                             [ forms.Label('Eerste herziening'),     'goedgekeurde_eerste_herziening',     'huidige_eerste_herziening',          'nieuwe_eerste_herziening'],
                                                             [ forms.Label('Volgende herzieningen'), 'goedgekeurde_volgende_herzieningen', 'huidige_volgende_herzieningen',      'nieuwe_volgende_herzieningen'],
                                                             [ forms.Label('Referentie index'),      'goedgekeurde_referentie_index',      'huidige_referentie_index',           'nieuwe_referentie_index'],
                                                             [ forms.Label('Minimale afwijking'),    'goedgekeurde_minimale_afwijking',    'huidige_minimale_afwijking',         'nieuwe_minimale_afwijking'],
                                                             [ forms.Label('Maximale stijging'),     'goedgekeurde_maximale_stijging',     'huidige_maximale_stijging',          'nieuwe_maximale_stijging'],
                                                             [ forms.Label('Maximale daling'),       'goedgekeurde_maximale_daling',       'huidige_maximale_daling',            'nieuwe_maximale_daling'],
                                                             ] ) ),
                                          (_('Ristorno'), 
                                           forms.GridForm( [ [ forms.Label(''),                                     forms.Label(_('Vorige')),                      forms.Label(_('Op datum wijziging')),      forms.Label(_('Wijzigen naar')) ],
                                                             [ forms.Label('Eerste herziening'),                    'goedgekeurde_eerste_herziening_ristorno',     'huidige_eerste_herziening_ristorno',      'nieuwe_eerste_herziening_ristorno'],
                                                             [ forms.Label('Volgende herzieningen'),                'goedgekeurde_volgende_herzieningen_ristorno', 'huidige_volgende_herzieningen_ristorno',  'nieuwe_volgende_herzieningen_ristorno'],
                                                             [ forms.Label('Maximale spaar ristorno'),              'goedgekeurde_maximale_spaar_ristorno',        'huidige_maximale_spaar_ristorno',         'nieuwe_maximale_spaar_ristorno'],
                                                             [ forms.Label('Maximale ristorno gebonden producten'), 'goedgekeurde_maximale_product_ristorno',      'huidige_maximale_product_ristorno',       'nieuwe_maximale_product_ristorno'],
                                                             [ forms.Label('Maximale conjunctuur ristorno'),        'goedgekeurde_maximale_conjunctuur_ristorno',  'huidige_maximale_conjunctuur_ristorno',   'nieuwe_maximale_conjunctuur_ristorno'],
                                                             ] ) ),
                                          (_('Extra'), forms.Form(['venice_id','venice_doc',], columns = 2 ) ) 
                                          ], position=forms.TabForm.WEST )

          field_attributes = {
               'origin':{'editable':True, 'name':_('Origin')},
               'huidige_maximale_stijging':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Maximale stijging')},
               'goedgekeurd_type_vervaldag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Vervaldag valt op')},
               'nieuwe_eerste_herziening_ristorno':{'editable':True, 'name':_('Nieuwe Eerste herziening ristorno na (maanden)')},
               'nieuw_terugbetaling_start':{'editable':True, 'name':_('Nieuw uitstel betaling')},
               'datum_wijziging':{'editable':True, 'name':_('Datum van wijziging')},
               'open_amount':{'editable':False, 'name':_('Openstaand bedrag')},
               'huidig_aantal_aflossingen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Resterend aantal aflossingen')},
               'datum':{'editable':True, 'name':_('Datum')},
               'nieuwe_rente':{'editable':True, 'name':_('Nieuwe rente')},
               'huidige_intrest_b':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde intrest b')},
               'huidige_intrest_a':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde intrest a')},
               'huidige_jaarrente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde jaarrente')},
               'goedgekeurde_rente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde rente')},
               'nieuw_type_aflossing':{'editable':True, 'name':_('Nieuw Type Aflossing'), 'choices':[('vast_kapitaal', 'Vast kapitaal'), ('vaste_aflossing', 'Vast bedrag'), ('bullet', 'Enkel intrest'), ('cummulatief', 'Alles op einddatum'), ('', '')]},
               'nieuw_bedrag':{'editable':True, 'name':_('Nieuw bedrag')},
               'goedgekeurde_intrest_b':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Intrest b')},
               'name':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Naam')},
               'goedgekeurde_maximale_conjunctuur_ristorno':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Maximale conjunctuur ristorno')},
               'goedgekeurde_opname_periode':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opname periode (maanden)')},
               'goedgekeurde_eerste_herziening_ristorno':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Eerste herziening ristorno na (maanden)')},
               'huidige_maximale_daling':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Maximale daling')},
               'goedgekeurde_maximale_spaar_ristorno':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Maximale spaar ristorno')},
               'goedgekeurde_eerste_herziening':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Eerste herziening na (maanden)')},
               'venice_book_type':{'editable':False, 'name':_('Dagboek Type')},
               'goedgekeurde_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde aflossing')},
               'goedgekeurde_maximale_daling':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Maximale daling')},
               'venice_book':{'editable':False, 'name':_('Dagboek')},
               'goedgekeurde_minimale_afwijking':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Minimale afwijking')},
               'huidige_eerste_herziening_ristorno':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Eerste herziening ristorno')},
               'huidige_reserverings_provisie':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Reserveringsprovisie')},
               'nieuw_goedgekeurd_bedrag':{'editable':True, 'name':_('Nieuw goedgekeurd bedrag')},
               'nieuwe_volgende_herzieningen':{'editable':True, 'name':_('Nieuwe Daarna herzieningen om de (maanden)')},
               'nieuwe_maximale_daling':{'editable':True, 'name':_('Nieuwe Maximale daling')},
               'huidige_status':{'editable':False, 'name':_('Huidige status'), 'choices':[('opnameperiode', 'In opname periode'), ('running', 'Lopende'), ('ended', 'Beeindigd')]},
               'goedgekeurd_bedrag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurd bedrag')},
               'nieuwe_opname_schijven':{'editable':True, 'name':_('Nieuwe opname schijven')},
               'nieuwe_opname_periode':{'editable':True, 'name':_('Nieuwe opnameperiode')},
               'goedgekeurde_maximale_product_ristorno':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Maximale ristorno gebonden producten')},
               'huidige_looptijd':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Resterende looptijd')},
               'goedgekeurd_terugbetaling_start':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Uitstel Betaling (maanden)')},
               'goedgekeurde_reserverings_provisie':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde reserveringsprovisie')},
               'huidig_type_aflossing':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Huidig type aflossing')},
               'full_number':{'name': 'Dossier nummer'},
               'dossier':{'editable':True, 'name':_('Dossier')},
               'goedgekeurd_type_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurd type aflossing')},
               'huidige_referentie_index':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Referentie index')},
               'goedgekeurde_jaarrente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde rente')},
               'goedgekeurde_volgende_herzieningen_ristorno':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Daarna herzieningen ristorno om de (maanden)')},
               'huidige_opname_schijven':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Resterende opname schijven')},
               'huidige_maximale_conjunctuur_ristorno':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Huidige Maximale conjunctuur ristorno')},
               'nieuwe_reserverings_provisie':{'editable':True, 'name':_('Nieuwe reserveringsprovisie')},
               'goedgekeurde_referentie_index':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Referentie index')},
               'nieuwe_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Nieuwe aflossing')},
               'nieuwe_looptijd':{'editable':True, 'name':_('Nieuwe looptijd')},
               'huidige_minimale_afwijking':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Minimale afwijkging')},
               'nieuwe_eerste_herziening':{'editable':True, 'name':_('Nieuwe Eerste herziening na (maanden)')},
               'huidig_terugbetaling_start':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Resterend uitstel betaling')},
               'venice_active_year':{'editable':False, 'name':_('Actief jaar')},
               'goedgekeurde_volgende_herzieningen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Daarna herzieningen om de (maanden)')},
               'nieuwe_volgende_herzieningen_ristorno':{'editable':True, 'name':_('Nieuwe Daarna herzieningen ristorno om de (maanden)')},
               'huidige_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Huidige aflossing')},
               'huidige_eerste_herziening':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Eerste rente herziening')},
               'goedgekeurd_terugbetaling_interval':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Terugbetaling')},
               'venice_doc':{'editable':False, 'name':_('Document Nummer Venice')},
               'goedgekeurde_looptijd':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde looptijd (maanden)')},
               'goedgekeurde_maximale_stijging':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Maximale stijging')},
               'wederbeleggingsvergoeding':{'editable':True, 'name':_('Wederbeleggingsvergoeding')},
               'goedgekeurde_opname_schijven':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opname schijven (maanden)')},
               'nieuwe_status':{'editable':True, 'name':_('Nieuwe status'), 'choices':[('opnameperiode', 'In opname periode'), ('running', 'Lopende'), ('ended', 'Beeindigd')]},
               'state':{'editable':False, 'name':_('Status'), 'choices':[('draft', 'Draft'), ('approved', 'Goedgekeurd'), ('canceled', 'Afgekeurd'), ('processed', 'Doorgevoerd'), ('ticked', 'Afgepunt'), ('removed', 'Verwijderd')]},
               'nieuwe_maximale_product_ristorno':{'editable':True, 'name':_('Nieuwe Maximale ristorno gebonden producten')},
               'opmerking':{'editable':True, 'name':_('Opmerking')},
               'huidige_opname_periode':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Resterende opname periode')},
               'huidige_rente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Rente')},
               'huidig_bedrag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Resterend bedrag')},
               'nieuwe_maximale_stijging':{'editable':True, 'name':_('Nieuwe Maximale stijging')},
               'vorige_startdatum':{'editable':False, 'name':_('Start datum')},
               'huidige_volgende_herzieningen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Daarna renteherzieningen om de')},
               'nieuwe_jaarrente':{'editable':True, 'name':_('Nieuwe jaarrente')},
               'nieuwe_maximale_conjunctuur_ristorno':{'editable':True, 'name':_('Nieuwe Maximale conjunctuur ristorno')},
               'goedgekeurde_intrest_a':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Intrest a')},
               'huidige_maximale_spaar_ristorno':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Huidige Maximale spaar ristorno')},
               'vorig_goedgekeurd_bedrag':{},
               'vorig_goedgekeurd_bedrag':{'editable':True, 'name':_('Vorig goedgekeurd bedrag')},
               'nieuwe_maximale_spaar_ristorno':{'editable':True, 'name':_('Nieuwe Maximale spaar ristorno')},
               'euribor':{'editable':True, 'name':_('Euribor (percentage)')},
               'huidige_volgende_herzieningen_ristorno':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Daarna herzieningen ristorno om de')},
               'nieuw_aantal_aflossingen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Nieuw aantal aflossingen')},
               'huidige_maximale_product_ristorno':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Huidige Maximale ristorno gebonden producten')},
               'nieuwe_minimale_afwijking':{'editable':True, 'name':_('Nieuwe Minimale afwijking')},
               'nieuwe_referentie_index':{'editable':True, 'name':_('Nieuwe Referentie index')},
               'nieuwe_intrest_a':{'editable':True, 'name':_('Nieuwe intrest a')},
               'nieuwe_intrest_b':{'editable':True, 'name':_('Nieuwe intrest b')},
               'venice_id':{'editable':False, 'name':_('Systeem Nummer Venice')},
               'goedgekeurd_index_type':{},
               'goedgekeurd_index_type':{'editable':False, 'name':_('Type index')},
          }

          def get_query(self, *args, **kwargs):
              query = VfinanceAdmin.get_query(self, *args, **kwargs)
              query = query.options(orm.joinedload('dossier'))
              query = query.options(orm.joinedload('dossier.roles'))
              return query

#  done_fields
#  MinDateTimeDelta
#  August
#  Monday
#  June
#  MaxDateTime
#  wizard_fields
#  November
#  October
#  January
#  Wednesday
#  current_myriad
#  POSIX
#  oneSecond
#  oneHour
#  months_between_dates
#  wizard_form
#  Julian
#  akte_header_desc
#  Thursday
venice_documents = ['hypo.vervaldag', 'hypo.rappel_openstaande_vervaldag', 'hypo.rappel_brief', 'hypo.terugbetaling', 'hypo.wijziging', 'hypo.betaling']
#  May
#  field_getter_from_goedgekeurd_bedrag
#  Gregorian
modaliteiten2 = ['terugbetaling_start', 'bedrag']
#  February
modaliteiten3 = ['looptijd']
#  akte_line_desc
#  April
#  Weekday
#  akte_header_data
#  Saturday
#  akte_line_data
