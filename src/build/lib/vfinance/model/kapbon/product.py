import calendar
import datetime
import logging
import math
import operator

import sqlalchemy.types
from sqlalchemy import sql, schema

from camelot.core.orm import Entity, ManyToOne, using_options
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _
import camelot.types

from ..bank.rechtspersoon import Rechtspersoon
from ..bank.natuurlijke_persoon import NatuurlijkePersoon

logger = logging.getLogger( 'vfinance.model.kapbon.product' )
#  constant
#  sales_line_desc

ACCOUNT_PREFIX = '142134' # used to be 17434
ACCOUNT_ORIGINAL_PREFIX = '17434'

def format_venice_product_nummer(product_id):
  return '%s%04d' % (ACCOUNT_PREFIX, product_id)

def format_venice_kapbon_nummer(product_id, serie_nummer):
  if serie_nummer:
    return '%s%06d' % (format_venice_product_nummer(product_id), serie_nummer)
  else:
    return '%sxxxxxx' % (format_venice_product_nummer(product_id) )

class ProductPenalisatie(Entity):
     """ De penalisatie die gedurende een bepaalde termijn geldig is voor een bepaald product """
     using_options(tablename='kapbon_product_penalisatie')
     looptijd_maanden  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     product_id  =  schema.Column(sqlalchemy.types.Integer(), name='product', nullable=True, index=True)
     product  =  ManyToOne('vfinance.model.kapbon.product.ProductBeschrijving', field=product_id, backref='penalisaties')
     penalisatie  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=False)
     volgorde  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)

     @property
     def looptijd_jaren( self ):
         """@todo : copy from tiny"""
         return 0
       
     @property
     def name( self ):
         """@todo : copy from tiny"""
         return ''
       
     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['volgorde', 'looptijd_maanden', 'penalisatie']
          form_display =  forms.Form(['volgorde','looptijd_maanden','looptijd_jaren','penalisatie',], columns=2)
          field_attributes = {
                              'looptijd_maanden':{'editable':True, 'name':_('Termijn in maanden')},
                              'product':{},
                              'product':{'editable':True, 'name':_('Product beschrijving')},
                              'penalisatie':{'editable':True, 'name':_('Penalisatie')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                              'volgorde':{'editable':True, 'name':_('Volgorde van deeltermijn')},
                              'looptijd_jaren':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Termijn in jaren')},
                             }
#  sales_header_data
#  sales_header_desc

def add_months_to_date(start_date, months):
  year, month = map(sum, zip((start_date.year, 1), divmod(start_date.month + months - 1, 12)))
  weekday, numdays = calendar.monthrange(year, month)
  return datetime.date(year, month, min(numdays, start_date.day))

class Kapbon(Entity):
     """ De kapitalisatiebon """
     using_options(tablename='kapbon_kapbon')
     
     @property
     def actuariele_rente( self ):
         pass
       
     @property
     def datum( self ):
         pass
       
     @property
     def termijnen( self ):
         pass
       
     controle_stuk_nummer  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     pand  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
     mathematisch_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     afkoop_datum_aanvraag  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     bestelling_id  =  schema.Column(sqlalchemy.types.Integer(), name='bestelling', nullable=True, index=True)
     bestelling  =  ManyToOne('vfinance.model.kapbon.product.Bestelling', field=bestelling_id, backref='kapbonnen')
     betaal_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     
     @property
     def act_mathematisch( self ):
         pass
       
     in_bewaring  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
     afkoop_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     
     @property
     def mathematisch( self ):
         pass
       
     serie_nummer  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     afkoop_terug_te_betalen_korting  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
     
     @property
     def name( self ):
         pass
       
     #afkopers  =  OneToMany('vfinance.model.kapbon.product.Afkoper', inverse='kapbon')
     coupure  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=False)
     controle_watermerk  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
     #afkoop_document  =  OneToMany('vfinance.model.kapbon.product.AfkoopDocument', inverse='kapbon')
     opmerking  =  schema.Column(camelot.types.RichText(), nullable=True)
     
     @property
     def afkoop_intrest( self ):
         pass
       
     geen_controle_stuk_nummer  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
     
     @property
     def afkoop_roerende_voorheffing( self ):
         pass
       
     stuk_nummer  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     aan_toonder  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
     afkoop_gekapitaliseerd_bedrag  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
     controle_handtekening  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
     betaald  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
     
     @property
     def afkoop_kapitaal( self ):
       pass
     
     state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     afkoop_klant_nummer  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     product_id  =  schema.Column(sqlalchemy.types.Integer(), name='product', nullable=False, index=True)
     product  =  ManyToOne('vfinance.model.kapbon.product.ProductBeschrijving', field=product_id)
     gestolen_stuk_nummer  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     controle_diefstal  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)

     @property
     def afkoop_te_storten_op_rekening_klant( self ):
         pass
       
     @property
     def bestelbon_nummer( self ):
         pass
       
     @property
     def product_versie_str( self ):
         pass
       
     @property
     def aan_toonder_str( self ):
         pass
       
     kapbon_nummer_import  =  schema.Column(sqlalchemy.types.Unicode(15), nullable=True)
     
     @property
     def mathematisch_op_datum( self ):
         pass
       
     @property
     def nummer( self ):
          if self.state == 'draft' or self.product==None or self.serie_nummer==None:
            return ''
          return format_venice_kapbon_nummer( self.product.id, self.serie_nummer).replace( ACCOUNT_PREFIX, ACCOUNT_ORIGINAL_PREFIX )

     @property
     def datum_start( self ):
          if self.bestelling != None:
              return self.bestelling.datum_start
     
     @property
     def datum_einde( self ):
       if self.product == None:
         return None
       looptijd_maanden = [ p.looptijd_maanden for p in self.product.termijnen ]
       end_date = self.datum_start
       for m in looptijd_maanden:
         end_date = add_months_to_date(end_date, m)
       return end_date
     
     @property
     def te_betalen_op_vervaldag( self ):
       if self.coupure == None:
         return
       product_versie = self.product_versie
       if not product_versie:
         logger.warning('Er bestaat nog geen product versie voor het product van deze bon! (bon id %d)' % self.id)
         return 0.0
       return self.coupure * reduce(operator.mul, [ math.pow(1 + rente.rente / 100.0, rente.beschrijving.looptijd_jaren) for rente in product_versie.rentes ], 1.0)

     @property
     def product_versie( self ):
       if self.product == None:
         return None
       return KapProduct.query.filter( sql.and_( KapProduct.beschrijving == self.product,
                                                 KapProduct.start_datum <= self.datum_start ) ).order_by( KapProduct.start_datum.desc() ).first()
     
     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['nummer', 'bestelbon_nummer', 'stuk_nummer', 'product_versie_str', 'coupure', 'mathematisch', 'te_betalen_op_vervaldag', 'aan_toonder_str', 'state', 'datum_einde', 'afkoop_datum', 'in_bewaring']
          form_display =  forms.Form([forms.TabForm([(_('Algemeen'), forms.Form(['nummer','stuk_nummer','gestolen_stuk_nummer','bestelling','product','pand','product_versie_str','actuariele_rente','coupure','mathematisch','te_betalen_op_vervaldag','aan_toonder','datum','datum_start','datum_einde','betaald','betaal_datum','state','in_bewaring','opmerking',], columns=2)),(_('Afkopen'), forms.Form([forms.GroupBoxForm(_('Bedragen'),['afkoop_datum_aanvraag','afkoop_datum','afkoop_kapitaal','afkoop_gekapitaliseerd_bedrag','afkoop_intrest','afkoop_roerende_voorheffing','afkoop_terug_te_betalen_korting','afkoop_te_storten_op_rekening_klant','afkopers',], columns=2),forms.GroupBoxForm(_('Controle'),['controle_watermerk','controle_handtekening','controle_stuk_nummer','controle_diefstal','geen_controle_stuk_nummer',], columns=2),forms.GroupBoxForm(_('Acties'),[], columns=2),], columns=2)),(_('Mathematische waarde'), forms.Form(['mathematisch_datum','mathematisch_op_datum',], columns=2)),], position=forms.TabForm.WEST)], columns=2)
          field_attributes = {
                              'actuariele_rente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Actuariele Rente')},
                              'datum':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Besteldatum')},
                              'termijnen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Termijnen')},
                              'controle_stuk_nummer':{'editable':True, 'name':_('Stuknummer')},
                              'pand':{'editable':True, 'name':_('In pand gegeven')},
                              'mathematisch_datum':{'editable':True, 'name':_('Datum mathematische waarde')},
                              'afkoop_datum_aanvraag':{'editable':True, 'name':_('Datum aanvraag afkoop')},
                              'bestelling':{},
                              'bestelling':{'editable':True, 'name':_('Bestelling')},
                              'betaal_datum':{'editable':False, 'name':_('Betaaldatum')},
                              'act_mathematisch':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Actuariele Mathematische waarde')},
                              'in_bewaring':{'editable':True, 'name':_('In bewaring')},
                              'afkoop_datum':{'editable':True, 'name':_('Afkoop datum')},
                              'mathematisch':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Mathematische waarde vandaag')},
                              'serie_nummer':{'editable':False, 'name':_('Nummer')},
                              'afkoop_terug_te_betalen_korting':{'editable':True, 'name':_('Terug te betalen korting')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                              'te_betalen_op_vervaldag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Te betalen op vervaldag')},
                              'afkopers':{'editable':True, 'name':_('Afkopers')},
                              'coupure':{'editable':True, 'name':_('Coupure')},
                              'controle_watermerk':{'editable':True, 'name':_('Watermerk gecontroleerd')},
                              'afkoop_document':{'editable':True, 'name':_('Venice Afkoop Doc')},
                              'opmerking':{'editable':True, 'name':_('Opmerking')},
                              'afkoop_intrest':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Intrest')},
                              'geen_controle_stuk_nummer':{'editable':True, 'name':_('Negeer stuknummer')},
                              'afkoop_roerende_voorheffing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Roerende voorheffing')},
                              'stuk_nummer':{'editable':True, 'name':_('Stuknummer')},
                              'aan_toonder':{'editable':True, 'name':_('Aan toonder')},
                              'afkoop_gekapitaliseerd_bedrag':{'editable':True, 'name':_('Gekapitaliseerd bedrag')},
                              'controle_handtekening':{'editable':True, 'name':_('Handtekening gecontroleerd')},
                              'datum_start':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Start datum')},
                              'betaald':{'editable':False, 'name':_('Betaald')},
                              'afkoop_kapitaal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Gekapitaliseerd bedrag op vervaldag')},
                              'state':{'editable':False, 'name':_('Status'), 'choices':[('draft', 'Opmaak'), ('doorgevoerd', 'Doorgevoerd'), ('ticked', 'Afgepunt'), ('afgedrukt', 'Afgedrukt'), ('verified', 'Gecontroleerd'), ('beeindigd', 'Afgekocht')]},
                              'afkoop_klant_nummer':{'editable':True, 'name':_('Klant nummer Venice')},
                              'product':{},
                              'product':{'editable':True, 'name':_('Kapitalisatiebon product')},
                              'gestolen_stuk_nummer':{'editable':True, 'name':_('Gestolen stuknummer')},
                              'controle_diefstal':{'editable':True, 'name':_('Gecontroleerd op diefstal')},
                              'product_versie':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Product versie')},
                              'afkoop_te_storten_op_rekening_klant':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Bedrag voor klant')},
                              'bestelbon_nummer':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Bestelbon nummer')},
                              'product_versie_str':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Product versie')},
                              'aan_toonder_str':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Aan toonder')},
                              'nummer':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Nummer')},
                              'kapbon_nummer_import':{'editable':False, 'name':_('Kapbon nummer uit import')},
                              'mathematisch_op_datum':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Mathematische waarde op datum')},
                              'datum_einde':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Vervaldag')},
                             }
#  kapbon_book

def snap_date(datum):
  if datum.day <= 8:
    return datetime.date(datum.year, datum.month, 1)
  if (datum.day >= 9) and (datum.day <= 21):
    return datetime.date(datum.year, datum.month, 15)
  year, month = divmod(datum.month, 12)
  return datetime.date(datum.year + year, month + 1, 1)

class Bestelling(Entity):
     """ Bestelling """
     using_options(tablename='kapbon_bestelling')
     open_amount  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
     temp_product_id  =  schema.Column(sqlalchemy.types.Integer(), name='temp_product', nullable=True, index=True)
     temp_product  =  ManyToOne('vfinance.model.kapbon.product.ProductBeschrijving', field=temp_product_id)
     opmerking  =  schema.Column(camelot.types.RichText(), nullable=True)
     datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
     temp_aan_toonder  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
     venice_doc  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     datum_start_priv  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     
     @property
     def aantal( self ):
          pass
     
     korting  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
     
     @property
     def te_betalen( self ):
          pass
     
     temp_coupure  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
     venice_active_year  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     venice_book_type  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     venice_book  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     makelaar_id_id  =  schema.Column(sqlalchemy.types.Integer(), name='makelaar_id', nullable=True, index=True)
     makelaar_id  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=makelaar_id_id)
     #kopers  =  OneToMany('vfinance.model.kapbon.product.Koper', inverse='bestelling')
     #kapbonnen  =  OneToMany('vfinance.model.kapbon.product.Kapbon', inverse='bestelling')
     bestelbon_nummer  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     
     @property
     def belegd_bedrag( self ):
          pass
     
     afleveringstaks  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
     
     @property
     def name( self ):
          pass
     
     
     @property
     def waarde_op_vervaldag( self ):
          pass
     
     temp_aantal  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     venice_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     administratiekosten  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)

     @property
     def datum_start( self ):
          if self.datum_start_priv:
            return self.datum_start_priv
          if self.datum:
            return snap_date( self.datum )

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['bestelbon_nummer', 'datum', 'aantal', 'belegd_bedrag', 'waarde_op_vervaldag', 'state']
          form_display =  forms.Form([forms.GroupBoxForm(_('Gegevens'),['bestelbon_nummer','datum','korting','administratiekosten','datum_start','makelaar_id','opmerking','state',], columns=2),'kopers',forms.GroupBoxForm(_('Invoer kapitalisatiebonnen'),['temp_aantal','temp_coupure','temp_product','temp_aan_toonder',], columns=2),'kapbonnen','te_betalen','belegd_bedrag','waarde_op_vervaldag',forms.GroupBoxForm(_('Unknown'),['venice_id','venice_doc',], columns=2),], columns=2)
          field_attributes = {
                              'datum_start':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Start datum')},
                              'open_amount':{'editable':False, 'name':_('Openstaand bedrag')},
                              'temp_product':{},
                              'temp_product':{'editable':False, 'name':_('Kapitalisatiebon product')},
                              'opmerking':{'editable':True, 'name':_('Opmerking')},
                              'datum':{'editable':True, 'name':_('Besteldatum')},
                              'temp_aan_toonder':{'editable':False, 'name':_('Aan toonder')},
                              'venice_doc':{'editable':False, 'name':_('Document Nummer Venice')},
                              'datum_start_priv':{'editable':True, 'name':_('Start datum')},
                              'aantal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Aantal')},
                              'korting':{'editable':True, 'name':_('Korting')},
                              'te_betalen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Te betalen')},
                              'temp_coupure':{'editable':False, 'name':_('Coupure')},
                              'venice_active_year':{'editable':False, 'name':_('Actief jaar')},
                              'state':{'editable':False, 'name':_('Status'), 'choices':[('draft', 'Opmaak'), ('doorgevoerd', 'Doorgevoerd'), ('ticked', 'Afgepunt')]},
                              'venice_book_type':{'editable':False, 'name':_('Dagboek Type')},
                              'venice_book':{'editable':False, 'name':_('Dagboek')},
                              'makelaar_id':{},
                              'makelaar_id':{'editable':True, 'name':_('Makelaar')},
                              'kopers':{'editable':True, 'name':_('Kopers')},
                              'kapbonnen':{'editable':True, 'name':_('Kapitalisatiebonnen')},
                              'bestelbon_nummer':{'editable':True, 'name':_('Bestelbonnummer')},
                              'belegd_bedrag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Belegd bedrag')},
                              'afleveringstaks':{'editable':True, 'name':_('Afleveringstaks')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                              'waarde_op_vervaldag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totale waarde op vervaldag')},
                              'makelaar':{},
                              'makelaar':{'editable':True, 'name':_('Makelaar')},
                              'temp_aantal':{'editable':False, 'name':_('Aantal')},
                              'venice_id':{'editable':False, 'name':_('Systeem Nummer Venice')},
                              'administratiekosten':{'editable':True, 'name':_('Administratiekosten')},
                             }
#  ACCOUNT_ORIGINAL_PREFIX
#  credit_header_desc
#  credit_header_data

class KapProduct(Entity):
     """ Een versie van een product beschrijving """
     using_options(tablename='kapbon_product')
     
     @property
     def actuariele_rente( self ):
          pass
     
     start_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     
     @property
     def name( self ):
          pass
     
     @property
     def termijnen_samenvatting( self ):
          pass
     
     #rentes  =  OneToMany('vfinance.model.kapbon.product.ProductRente', inverse='product')
     beschrijving_id  =  schema.Column(sqlalchemy.types.Integer(), name='beschrijving', nullable=True, index=True)
     beschrijving  =  ManyToOne('vfinance.model.kapbon.product.ProductBeschrijving', field=beschrijving_id, backref='versies')
     
     @property
     def rentes_samenvatting( self ):
          pass
     
     @property
     def actuariele_rente_mul( self ):
          pass

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['start_datum', 'termijnen_samenvatting', 'rentes_samenvatting', 'actuariele_rente']
          form_display =  forms.Form(['start_datum','actuariele_rente','rentes',], columns=2)
          field_attributes = {
                              'actuariele_rente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Actuariele rente voor R.V.')},
                              'start_datum':{'editable':True, 'name':_('Geldig vanaf')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                              'termijnen_samenvatting':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('termijnen')},
                              'rentes':{'editable':True, 'name':_('Termijnen')},
                              'beschrijving':{},
                              'beschrijving':{'editable':True, 'name':_('Beschrijving')},
                              'rentes_samenvatting':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('rentes')},
                              'actuariele_rente_mul':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Actuariele rente voor R.V. multiplier')},
                             }
#  ACCOUNT_PREFIX

class ProductRente(Entity):
     """ Rente van een termijn van een product versie """
     using_options(tablename='kapbon_product_rente')
      
     @property
     def looptijd_maanden( self ):
          pass
        
     product_id  =  schema.Column(sqlalchemy.types.Integer(), name='product', nullable=True, index=True)
     product  =  ManyToOne('vfinance.model.kapbon.product.KapProduct', field=product_id, backref='rentes')
     rente  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=False)
      
     @property
     def rente_mul( self ):
          pass
      
     @property
     def name( self ):
          pass
        
     beschrijving_id  =  schema.Column(sqlalchemy.types.Integer(), name='beschrijving', nullable=True, index=True)
     beschrijving  =  ManyToOne('vfinance.model.kapbon.product.ProductTermijnBeschrijving', field=beschrijving_id)
      
     @property
     def volgorde( self ):
          pass
      
     @property
     def rente_op_maandbasis_mul( self ):
          pass
      
     @property
     def rente_op_maandbasis( self ):
          pass

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['volgorde', 'looptijd_maanden', 'rente']
          form_display =  forms.Form(['beschrijving','volgorde','looptijd_maanden','rente',], columns=2)
          field_attributes = {
                              'looptijd_maanden':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('looptijd in maanden')},
                              'product':{},
                              'product':{'editable':True, 'name':_('Product')},
                              'rente':{'editable':True, 'name':_('Rente')},
                              'rente_mul':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Rente multiplier')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                              'beschrijving':{},
                              'beschrijving':{'editable':True, 'name':_('Termijn')},
                              'volgorde':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('volgorde')},
                              'rente_op_maandbasis_mul':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Rente op maandbasis multiplier')},
                              'rente_op_maandbasis':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Rente op maandbasis')},
                             }

class AfkoopDocument(Entity):
     using_options(tablename='kapbon_afkoop_document')
     venice_doc  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     kapbon_id  =  schema.Column(sqlalchemy.types.Integer(), name='kapbon', nullable=False, index=True)
     kapbon  =  ManyToOne('vfinance.model.kapbon.product.Kapbon', field=kapbon_id)
     open_amount  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
     datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
     venice_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     venice_book_type  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     venice_active_year  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     venice_book  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  []
          form_display =  []
          field_attributes = {
                              'venice_doc':{'editable':False, 'name':_('Document Nummer Venice')},
                              'kapbon':{},
                              'kapbon':{'editable':True, 'name':_('Kapitalisatiebon')},
                              'open_amount':{'editable':False, 'name':_('Openstaand bedrag')},
                              'datum':{'editable':True, 'name':_('Datum')},
                              'venice_id':{'editable':False, 'name':_('Systeem Nummer Venice')},
                              'state':{'editable':True, 'name':_('Status'), 'choices':[('draft', 'Opmaak'), ('processed', 'Doorgevoerd'), ('ticked', 'Afgepunt')]},
                              'venice_book_type':{'editable':False, 'name':_('Dagboek Type')},
                              'venice_active_year':{'editable':False, 'name':_('Actief jaar')},
                              'venice_book':{'editable':False, 'name':_('Dagboek')},
                             }
#  sales_line_data

class ProductBeschrijving(Entity):
     """ Product beschrijving """
     using_options(tablename='kapbon_product_beschrijving')
     
     @property
     def looptijd_maanden( self ):
          pass
     
     @property
     def code( self ):
          pass
        
     #versies  =  OneToMany('vfinance.model.kapbon.product.Product', inverse='beschrijving')
     naam  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=False)
     #termijnen  =  OneToMany('vfinance.model.kapbon.product.ProductTermijnBeschrijving', inverse='product')
     #penalisaties  =  OneToMany('vfinance.model.kapbon.product.ProductPenalisatie', inverse='product')
     standaard_commissie  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
     
     @property
     def termijnen_samenvatting( self ):
          pass
     
     @property
     def looptijd_jaren( self ):
          pass
     
     @property
     def name( self ):
          pass
        
     minimum_serienummer  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['code', 'naam', 'looptijd_maanden', 'termijnen_samenvatting']
          form_display =  forms.Form(['code','naam','termijnen','versies','penalisaties','minimum_serienummer','standaard_commissie',], columns=2)
          field_attributes = {
                              'looptijd_maanden':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totale looptijd in maanden')},
                              'code':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Code')},
                              'versies':{'editable':True, 'name':_('Versies')},
                              'naam':{'editable':True, 'name':_('Naam')},
                              'termijnen':{'editable':True, 'name':_('Beschrijving termijnen')},
                              'penalisaties':{'editable':True, 'name':_('Penalisatie termijnen')},
                              'standaard_commissie':{'editable':True, 'name':_('Standaard commissie')},
                              'termijnen_samenvatting':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Termijnen')},
                              'looptijd_jaren':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totale looptijd in jaren')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                              'minimum_serienummer':{'editable':True, 'name':_('Minimum serienummer')},
                             }

class Koper(Entity):
     """De koper van een kapbon """
     using_options(tablename='kapbon_koper')
     rechtspersoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon', nullable=True, index=True)
     rechtspersoon  =  ManyToOne(Rechtspersoon, field=rechtspersoon_id, backref='gekochte_kapbon')
     bankrekening  =  property(lambda self:self.newfun())
     taal  =  property(lambda self:self.newfun())
     name  =  property(lambda self:self.newfun())
     address_one_line  =  property(lambda self:self.newfun())
     actief_product  =  property(lambda self:self.newfun())
     bestelling_id  =  schema.Column(sqlalchemy.types.Integer(), name='bestelling', nullable=True, index=True)
     bestelling  =  ManyToOne('vfinance.model.kapbon.product.Bestelling', field=bestelling_id, backref='kopers')
     straat  =  property(lambda self:self.newfun())
     gemeente  =  property(lambda self:self.newfun())
     full_name  =  property(lambda self:self.newfun())
     related_constraints  =  property(lambda self:self.newfun())
     natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon', nullable=True, index=True)
     natuurlijke_persoon  =  ManyToOne(NatuurlijkePersoon, field=natuurlijke_persoon_id, backref='gekochte_kapbon')
     telefoon  =  property(lambda self:self.newfun())
     postcode  =  property(lambda self:self.newfun())

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['natuurlijke_persoon', 'rechtspersoon']
          form_display =  forms.Form(['rechtspersoon','natuurlijke_persoon',], columns=2)
          field_attributes = {
                              'rechtspersoon':{},
                              'rechtspersoon':{'editable':True, 'name':_('Rechtspersoon')},
                              'bankrekening':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Bankrekeningnummer')},
                              'taal':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Taal')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                              'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                              'actief_product':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Actief contract')},
                              'bestelling':{},
                              'bestelling':{'editable':True, 'name':_('Bestelling')},
                              'straat':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Straat')},
                              'gemeente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Gemeente')},
                              'full_name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                              'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                              'natuurlijke_persoon':{},
                              'natuurlijke_persoon':{'editable':True, 'name':_('Natuurlijke persoon')},
                              'telefoon':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Telefoon')},
                              'postcode':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Postcode')},
                             }
#  acc_gen

class Afkoper(Entity):
     """De afkoper van een kapbon """
     using_options(tablename='kapbon_afkoper')
     rechtspersoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon', nullable=True, index=True)
     rechtspersoon  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id)
     kapbon_id  =  schema.Column(sqlalchemy.types.Integer(), name='kapbon', nullable=True, index=True)
     kapbon  =  ManyToOne('vfinance.model.kapbon.product.Kapbon', field=kapbon_id, backref='afkopers')
     name  =  property(lambda self:self.newfun())
     address_one_line  =  property(lambda self:self.newfun())
     straat  =  property(lambda self:self.newfun())
     natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon', nullable=True, index=True)
     natuurlijke_persoon  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id)
     bankrekening  =  property(lambda self:self.newfun())
     gemeente  =  property(lambda self:self.newfun())
     full_name  =  property(lambda self:self.newfun())
     related_constraints  =  property(lambda self:self.newfun())
     taal  =  property(lambda self:self.newfun())
     telefoon  =  property(lambda self:self.newfun())
     postcode  =  property(lambda self:self.newfun())

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['natuurlijke_persoon', 'rechtspersoon']
          form_display =  forms.Form(['rechtspersoon','natuurlijke_persoon',], columns=2)
          field_attributes = {
                              'rechtspersoon':{},
                              'rechtspersoon':{'editable':True, 'name':_('Rechtspersoon')},
                              'kapbon':{},
                              'kapbon':{'editable':True, 'name':_('Kapitalisatiebon')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                              'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                              'straat':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Straat')},
                              'natuurlijke_persoon':{},
                              'natuurlijke_persoon':{'editable':True, 'name':_('Natuurlijke persoon')},
                              'bankrekening':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Bankrekeningnummer')},
                              'gemeente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Gemeente')},
                              'full_name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                              'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                              'taal':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Taal')},
                              'telefoon':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Telefoon')},
                              'postcode':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Postcode')},
                             }
#  format_venice_kapbon_nummer
#  format_venice_product_nummer
#  add_months_to_date

class ProductTermijnBeschrijving(Entity):
     """ Termijn beschrijving """
     using_options(tablename='kapbon_product_termijn_beschrijving')
     looptijd_maanden  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     product_id  =  schema.Column(sqlalchemy.types.Integer(), name='product', nullable=True, index=True)
     product  =  ManyToOne('vfinance.model.kapbon.product.ProductBeschrijving', field=product_id, backref='termijnen')
     volgorde  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
     
     @property
     def name( self ):
       pass

     @property
     def looptijd_jaren( self ):
       return float( self.looptijd_maanden or 0 ) / 12.0
     
     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['volgorde', 'looptijd_maanden']
          form_display =  forms.Form(['volgorde','looptijd_maanden','looptijd_jaren',], columns=2)
          field_attributes = {
                              'looptijd_maanden':{'editable':True, 'name':_('Termijn in maanden')},
                              'looptijd_jaren':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Termijn in jaren')},
                              'product':{},
                              'product':{'editable':True, 'name':_('Product beschrijving')},
                              'volgorde':{'editable':True, 'name':_('Volgorde van deeltermijn')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                             }
#  months_between_dates
#  kapbon_afkoop_book
#  snap_date

