import datetime

import sqlalchemy.types
from sqlalchemy import schema

from camelot.core.orm import Entity, ManyToOne, using_options
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _

import contract_business as cb

#  natuurlijke_persoon_address_one_line
#  ROUND_DOWN
#  ROUND_UP
#  flip_date
#  ROUND_FLOOR
#  credit_header_data
#  ROUND_CEILING
#  mathematische_reserves
#  datetime_CAPI
#  sales_header_data
#  natuurlijke_persoon_name
#  reductiewaardes
#  constrained_objects
#  credit_header_desc

class Contract(Entity):
     """ORM voor kapitalisatiecontracten via tiny"""
     using_options(tablename='kapcontract_contract')
     intrest  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     makelaar_id_id  =  schema.Column(sqlalchemy.types.Integer(), name='makelaar_id', nullable=True, index=True)
     makelaar_id  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=makelaar_id_id)
     afkoop_venice_doc  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     
     @property
     def eind_datum( self ):
          pass
     
     onderschrijver_id  =  schema.Column(sqlalchemy.types.Integer(), name='onderschrijver', nullable=False, index=True)
     onderschrijver  =  ManyToOne('vfinance.model.kapcontract.contract.Onderschrijver', field=onderschrijver_id)
     
     @property
     def afkoop_intrest( self ):
          pass
     
     @property
     def kapitaal_betaal_datum( self ):
          pass
     
     @property
     def aantal_maanden_reductie( self ):
          pass
     
     afkoop_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     
     @property
     def mathematische_reserve( self ):
          pass
     
     @property
     def afkoop_roerende_voorheffing( self ):
          pass
     
     start_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
     pand  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
     afkoop_venice_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     dubbel  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
     betalings_interval  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
     nummer  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
     
     @property
     def name( self ):
          pass
     
     #begunstigde  =  OneToMany('vfinance.model.kapcontract.Begunstigde', inverse='contract')
     
     @property
     def afkoop_waarde( self ):
          pass
     
     @property
     def totaal_openstaande_vervaldagen( self ):
          pass
     
     @property
     def totaal_openstaande_betalingen( self ):
          pass
     
     premie  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=False)
     state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     reductie_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     looptijd  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
     
     @property
     def afkoop_te_betalen( self ):
          pass
     
     #vervaldagen  =  OneToMany('vfinance.model.kapcontract.Vervaldag', inverse='contract')
     agent_code  =  schema.Column(sqlalchemy.types.Unicode(5), nullable=True)
     kapitaal  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=False)

     @property
     def betaal_datum( self ):
          return cb.betaaldatum( self.start_datum, self.looptijd )
     
     @property
     def aantal_maanden( self ):
       if self.looptijd == None:
            return None
       today = datetime.date.today()
       return cb.aantal_verlopen_maanden( today, self.state, self.afkoop_datum or today, self.reductie_datum or today, self.start_datum or today, self.looptijd )

     @property
     def aantal_betalingen( self ):
          if self.looptijd == None:
               return None
          return cb.aantal_betalingen( self.state, self.aantal_maanden, self.betalings_interval, self.looptijd )
     
     @property
     def ontvangen( self ):
          if self.aantal_betalingen == None:
               return None
          return cb.ontvangen( self.aantal_betalingen, self.premie )
     
     @property
     def reductie_waarde( self ):
          if self.looptijd == None:
               return None
          return cb.reductie_waarde( self.looptijd, self.aantal_maanden, self.kapitaal )
     
     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['nummer', 'onderschrijver', 'start_datum', 'eind_datum', 'looptijd', 'premie', 'state']
          form_display =  forms.Form([forms.TabForm([(_('Contract'), forms.Form([forms.GroupBoxForm(_('Algemeen'),['nummer','makelaar_id',], columns=2),
                                                                                 forms.GroupBoxForm(_('Klant'),['onderschrijver','begunstigde','pand',], columns=2),
                                                                                 forms.GroupBoxForm(_('Bedrag'),['premie','kapitaal','betalings_interval',], columns=2),
                                                                                 forms.GroupBoxForm(_('Looptijd'),['start_datum','eind_datum','looptijd','aantal_maanden','aantal_maanden_reductie','aantal_betalingen','ontvangen','totaal_openstaande_betalingen','totaal_openstaande_vervaldagen',], columns=2),
                                                                                 forms.GroupBoxForm(_('Status'),['state',], columns=2),], columns=2)),
                                                     (_('Reductie'), forms.Form(['reductie_datum','reductie_waarde',], columns=2)),
                                                     (_('Afkoop'), forms.Form(['afkoop_datum','afkoop_waarde','afkoop_intrest','afkoop_roerende_voorheffing','afkoop_te_betalen',forms.GroupBoxForm(_('Venice'),['afkoop_venice_id','afkoop_venice_doc',], columns=2),], columns=2)),
                                                     #(_('Vervaldagen'), forms.Form(['vervaldagen',], columns=2)),
                                                     (_('Extra'), forms.Form(['dubbel',], columns=2)),], position=forms.TabForm.WEST)], columns=2)
          field_attributes = {
                              'intrest':{'editable':True, 'name':_('Intrest')},
                              'makelaar_id':{},
                              'makelaar_id':{'editable':True, 'name':_('Makelaar')},
                              'afkoop_venice_doc':{'editable':False, 'name':_('Afkoop Venice document nummer')},
                              'eind_datum':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Datum einde betalingen')},
                              'onderschrijver':{},
                              'onderschrijver':{'editable':True, 'name':_('Onderschrijver')},
                              'afkoop_intrest':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Afkoop intrest')},
                              'kapitaal_betaal_datum':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Kapitaal op betaaldatum')},
                              'aantal_maanden_reductie':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Aantal maanden reductie')},
                              'afkoop_datum':{'editable':True, 'name':_('Datum afkoop')},
                              'ontvangen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Reeds ontvangen')},
                              'mathematische_reserve':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Mathematische reserve')},
                              'afkoop_roerende_voorheffing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Afkoop roerende voorheffing')},
                              'start_datum':{'editable':True, 'name':_('Datum eerste betaling')},
                              'pand':{'editable':True, 'name':_('In pand gegeven')},
                              'afkoop_venice_id':{'editable':False, 'name':_('Afkoop Venice id')},
                              'dubbel':{'editable':True, 'name':_('Dubbel')},
                              'betalings_interval':{'editable':True, 'name':_('Periodiciteit'), 'choices':[(12, 'Maandelijks'), (4, 'Trimesterieel'), (2, 'Half jaarlijks'), (1, 'Jaarlijks')]},
                              'nummer':{'editable':True, 'name':_('Nummer')},
                              'reductie_waarde':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Reductie waarde')},
                              'name':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Naam')},
                              'begunstigde':{'editable':True, 'name':_('Begunstigden')},
                              'afkoop_waarde':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Afkoop waarde')},
                              'totaal_openstaande_vervaldagen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Bedrag openstaande vervaldagen')},
                              'totaal_openstaande_betalingen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Bedrag openstaande betalingen')},
                              'premie':{'editable':True, 'name':_('Periodieke premie')},
                              'state':{'editable':False, 'name':_('Status'), 'choices':[('canceled', 'Geannulleerd'), ('draft', 'Wachtend'), ('complete', 'Volledig'), ('reduced', 'Reductie'), ('buyout_reduced', 'Afgekocht na reductie'), ('buyout', 'Afgekocht'), ('approved', 'Goedgekeurd'), ('processed', 'Doorgevoerd')]},
                              'reductie_datum':{'editable':True, 'name':_('Datum reductie')},
                              'aantal_maanden':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Aantal voorbije maanden')},
                              'looptijd':{'editable':True, 'name':_('Looptijd (jaar)')},
                              'makelaar':{},
                              'makelaar':{'editable':True, 'name':_('Makelaar')},
                              'afkoop_te_betalen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Afkoop te betalen')},
                              'betaal_datum':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Datum uitbetaling kapitaal')},
                              'vervaldagen':{'editable':False, 'name':_('Vervaldagen')},
                              'agent_code':{'editable':True, 'name':_('Agent code')},
                              'kapitaal':{'editable':True, 'name':_('Gewenst kapitaal')},
                              'aantal_betalingen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Aantal voorbije betalingen')},
                             }
#  afkoopwaardes
#  sales_header_desc
#  natuurlijke_persoon_full_name
#  theoretische_waardes
#  states
#  natuurlijke_persoon_postcode_gemeente
#  MINYEAR
#  ROUND_HALF_EVEN
#  ROUND_HALF_UP
#  sales_line_desc
#  sourcelocation
#  ROUND_HALF_DOWN
#  ACCOUNT_PREFIX
#  sales_line_data
#  ROUND_05UP

class Begunstigde(Entity):
     using_options(tablename='kapcontract_begunstigde')
     rechtspersoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon', nullable=True, index=True)
     rechtspersoon  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id, backref='gunstig_kapcontract')
     bankrekening  =  property(lambda self:self.newfun())
     name  =  property(lambda self:self.newfun())
     address_one_line  =  property(lambda self:self.newfun())
     actief_product  =  property(lambda self:self.newfun())
     contract_id  =  schema.Column(sqlalchemy.types.Integer(), name='contract', nullable=True, index=True)
     contract  =  ManyToOne('vfinance.model.kapcontract.contract.Contract', field=contract_id, backref='begunstigde')
     taal  =  property(lambda self:self.newfun())
     straat  =  property(lambda self:self.newfun())
     gemeente  =  property(lambda self:self.newfun())
     full_name  =  property(lambda self:self.newfun())
     related_constraints  =  property(lambda self:self.newfun())
     natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon', nullable=True, index=True)
     natuurlijke_persoon  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id, backref='gunstig_kapcontract')
     telefoon  =  property(lambda self:self.newfun())
     postcode  =  property(lambda self:self.newfun())

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['natuurlijke_persoon', 'rechtspersoon']
          form_display =  forms.Form([forms.GroupBoxForm(_('Natuurlijke persoon'),['natuurlijke_persoon',], columns=2),forms.GroupBoxForm(_('Rechtspersoon'),['rechtspersoon',], columns=2),], columns=2)
          field_attributes = {
                              'rechtspersoon':{},
                              'rechtspersoon':{'editable':True, 'name':_('Rechtspersoon')},
                              'bankrekening':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Bankrekeningnummer')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                              'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                              'actief_product':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Actief contract')},
                              'contract':{},
                              'contract':{'editable':True, 'name':_('Kapitalisatiecontract')},
                              'taal':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Taal')},
                              'straat':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Straat')},
                              'gemeente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Gemeente')},
                              'full_name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                              'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                              'natuurlijke_persoon':{},
                              'natuurlijke_persoon':{'editable':True, 'name':_('Natuurlijke persoon')},
                              'telefoon':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Telefoon')},
                              'postcode':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Postcode')},
                             }
#  MAXYEAR
#  natuurlijke_persoon_address

class Onderschrijver(Entity):
     using_options(tablename='kapcontract_onderschrijver')
     rechtspersoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon', nullable=True, index=True)
     rechtspersoon  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id, backref='onderschreven_kapcontract')
     bankrekening  =  property(lambda self:self.newfun())
     address_one_line  =  property(lambda self:self.newfun())
     actief_product  =  property(lambda self:self.newfun())
     #contract  =  OneToMany('vfinance.model.kapcontract.Contract', inverse='onderschrijver')
     taal  =  property(lambda self:self.newfun())
     straat  =  property(lambda self:self.newfun())
     gemeente  =  property(lambda self:self.newfun())
     full_name  =  property(lambda self:self.newfun())
     related_constraints  =  property(lambda self:self.newfun())
     natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon', nullable=True, index=True)
     natuurlijke_persoon  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id, backref='onderschreven_kapcontract')
     telefoon  =  property(lambda self:self.newfun())
     postcode  =  property(lambda self:self.newfun())

     def __unicode__(self):
          return unicode(self.natuurlijke_persoon or self.rechtspersoon or '')

     class Admin(EntityAdmin):
          list_display =  ['natuurlijke_persoon', 'rechtspersoon']
          form_display =  forms.Form([forms.GroupBoxForm(_('Natuurlijke persoon'),['natuurlijke_persoon',], columns=2),forms.GroupBoxForm(_('Rechtspersoon'),['rechtspersoon',], columns=2),], columns=2)
          field_attributes = {
                              'rechtspersoon':{},
                              'rechtspersoon':{'editable':True, 'name':_('Rechtspersoon')},
                              'bankrekening':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Bankrekeningnummer')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                              'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                              'actief_product':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Actief contract')},
                              'contract':{'editable':True, 'name':_('Kapitalisatiecontract')},
                              'taal':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Taal')},
                              'straat':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Straat')},
                              'gemeente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Gemeente')},
                              'full_name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                              'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                              'natuurlijke_persoon':{},
                              'natuurlijke_persoon':{'editable':True, 'name':_('Natuurlijke persoon')},
                              'telefoon':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Telefoon')},
                              'postcode':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Postcode')},
                             }
