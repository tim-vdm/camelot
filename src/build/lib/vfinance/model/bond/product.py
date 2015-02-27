import sqlalchemy.types
from sqlalchemy import schema

from camelot.core.orm import Entity, ManyToOne, using_options
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _
import camelot.types

#  constant
#  days_between_dates_without_leapdays
#  DEFAULT_BOND_ACCOUNT_BONDS

class BondOwner(Entity):
     """De eigenaar van een bond"""
     using_options(tablename='bond_owner')
     klant_id  =  schema.Column(sqlalchemy.types.Integer(), name='klant', nullable=True, index=True)
     klant  =  ManyToOne('vfinance.model.bank.customer.CustomerAccount', field=klant_id)
     bankrekening  =  schema.Column(sqlalchemy.types.Unicode(16), nullable=False)
     from_date  =  schema.Column(sqlalchemy.types.Date(), nullable=True, name='from')
     name  =  property(lambda self:self.newfun())
     address_one_line  =  property(lambda self:self.newfun())
     thru  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     bond_id  =  schema.Column(sqlalchemy.types.Integer(), name='bond', nullable=True, index=True)
     bond  =  ManyToOne('vfinance.model.bond.product.BondProduct', field=bond_id, backref='owner')

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['klant', 'bond', 'from_date', 'thru', 'bankrekening']
          form_display =  forms.Form(['klant','bond','from_date','thru','bankrekening',], columns=2)
          field_attributes = {
                              'klant':{},
                              'klant':{'editable':False, 'name':_('Klant')},
                              'bankrekening':{'editable':True, 'name':_('Bankrekeningnummer')},
                              'from_date':{'editable':False, 'name':_('Vanaf')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                              'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                              'thru':{'editable':False, 'name':_('Tot en met')},
                              'bond':{},
                              'bond':{'editable':False, 'name':_('Obligatie')},
                             }
#  sales_header_data
#  sales_header_desc
#  credit_header_desc
#  sales_line_desc

class BondSubscriber(Entity):
     """De onderschrijver van een bond"""
     using_options(tablename='bond_subscriber')
     rechtspersoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon', nullable=True, index=True)
     rechtspersoon  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id)
     bankrekening  =  property(lambda self:self.newfun())
     name  =  property(lambda self:self.newfun())
     address_one_line  =  property(lambda self:self.newfun())
     natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon', nullable=True, index=True)
     natuurlijke_persoon  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id)
     bestelling_id  =  schema.Column(sqlalchemy.types.Integer(), name='bestelling', nullable=True, index=True)
     bestelling  =  ManyToOne('vfinance.model.bond.product.BondBestelling', field=bestelling_id, backref='subscribers')
     straat  =  property(lambda self:self.newfun())
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
                              'bankrekening':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Bankrekeningnummer')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                              'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                              'natuurlijke_persoon':{},
                              'natuurlijke_persoon':{'editable':True, 'name':_('Natuurlijke persoon')},
                              'bestelling':{},
                              'bestelling':{'editable':True, 'name':_('Bestelling')},
                              'straat':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Straat')},
                              'gemeente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Gemeente')},
                              'full_name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                              'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                              'taal':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Taal')},
                              'telefoon':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Telefoon')},
                              'postcode':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Postcode')},
                             }

class BondBestelling(Entity):
     """ Bestelling """
     using_options(tablename='bond_bestelling')
     makelaar_id_id  =  schema.Column(sqlalchemy.types.Integer(), name='makelaar_id', nullable=True, index=True)
     makelaar_id  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=makelaar_id_id)
     #bestellijnen  =  OneToMany('vfinance.model.bond.product.Bestellijn', inverse='bestelling')
     #bonds  =  OneToMany('vfinance.model.bond.product.Bond', inverse='bestelling')
     open_amount  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
     datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
     state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     #subscribers  =  OneToMany('vfinance.model.bond.product.Subscriber', inverse='bestelling')
     opmerking  =  schema.Column(camelot.types.RichText(), nullable=True)
     venice_active_year  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     
     @property
     def belegd_bedrag( self ):
          pass
     
     @property
     def aantal( self ):
          pass
     
     venice_doc  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     nummer  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
     bankrekening  =  schema.Column(sqlalchemy.types.Unicode(16), nullable=False)
     
     @property
     def name( self ):
          pass
     
     @property
     def te_betalen( self ):
          pass
     
     venice_book_type  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
     venice_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
     venice_book  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['nummer', 'datum', 'aantal', 'belegd_bedrag', 'te_betalen', 'state']
          form_display =  forms.Form([forms.TabForm([(_('Bestelling'), forms.Form([forms.GroupBoxForm(_('Gegevens'),['nummer','datum','bankrekening','makelaar_id',], columns=2),'subscribers','bestellijnen','te_betalen','belegd_bedrag',forms.GroupBoxForm(_('Status'),['state','venice_doc',], columns=2),'opmerking',], columns=2)),(_('Obligaties'), forms.Form(['bonds',], columns=2)),], position=forms.TabForm.WEST)], columns=2)
          field_attributes = {
                              'makelaar_id':{},
                              'makelaar_id':{'editable':True, 'name':_('Makelaar')},
                              'bestellijnen':{'editable':True, 'name':_('Bestellijnen')},
                              'bonds':{'editable':False, 'name':_('Obligaties')},
                              'open_amount':{'editable':False, 'name':_('Openstaand bedrag')},
                              'datum':{'editable':True, 'name':_('Intekendatum')},
                              'state':{'editable':False, 'name':_('Status'), 'choices':[('draft', 'Opmaak'), ('canceled', 'Geannuleerd'), ('doorgevoerd', 'Doorgevoerd'), ('ticked', 'Afgepunt')]},
                              'subscribers':{'editable':True, 'name':_('Onderschrijvers')},
                              'opmerking':{'editable':True, 'name':_('Opmerking')},
                              'venice_active_year':{'editable':False, 'name':_('Actief jaar')},
                              'belegd_bedrag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Belegd bedrag')},
                              'aantal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Aantal')},
                              'venice_doc':{'editable':False, 'name':_('Document Nummer Venice')},
                              'nummer':{'editable':True, 'name':_('Bestelbon nummer')},
                              'bankrekening':{'editable':True, 'name':_('Bankrekeningnummer')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                              'te_betalen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Te betalen')},
                              'makelaar':{},
                              'makelaar':{'editable':True, 'name':_('Makelaar')},
                              'venice_book_type':{'editable':False, 'name':_('Dagboek Type')},
                              'venice_id':{'editable':False, 'name':_('Systeem Nummer Venice')},
                              'venice_book':{'editable':False, 'name':_('Dagboek')},
                             }
#  credit_header_data

class BondProduct(Entity):
     """Een versie van een product beschrijving"""
     using_options(tablename='bond_product')
     
     @property
     def roerende_voorheffing( self ):
          pass
     
     
     @property
     def looptijd_maanden( self ):
          pass
     
     code  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
     
     @property
     def coupure( self ):
          pass
     
     
     @property
     def coupon( self ):
          pass
     
     coupon_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
     start_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
     beschrijving_id  =  schema.Column(sqlalchemy.types.Integer(), name='beschrijving', nullable=True, index=True)
     beschrijving  =  ManyToOne('vfinance.model.bond.product.BondProductBeschrijving', field=beschrijving_id, backref='versies')
     
     @property
     def dagrente( self ):
          pass
     
     
     @property
     def name( self ):
          pass
     
     
     @property
     def beschrijving_name( self ):
          pass
     
     afsluit_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
     
     @property
     def coupon_te_betalen( self ):
          pass
     
     rente  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=False)
     
     @property
     def eerste_coupon_datum( self ):
          pass
     
     
     @property
     def eind_datum( self ):
          pass
     
     
     @property
     def periodiciteit( self ):
          pass
     

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['code', 'start_datum', 'afsluit_datum', 'coupon_datum', 'rente']
          form_display =  forms.Form(['code','start_datum','afsluit_datum','coupon_datum','rente',], columns=2)
          field_attributes = {
                              'roerende_voorheffing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Roerende voorheffing')},
                              'looptijd_maanden':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Looptijd in maanden')},
                              'code':{'editable':True, 'name':_('Code')},
                              'coupure':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Coupure')},
                              'coupon':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Coupon')},
                              'coupon_datum':{'editable':True, 'name':_('Coupon datum')},
                              'start_datum':{'editable':True, 'name':_('Start datum')},
                              'beschrijving':{},
                              'beschrijving':{'editable':True, 'name':_('Beschrijving')},
                              'dagrente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Dagrente')},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                              'beschrijving_name':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Naam product beschrijving')},
                              'afsluit_datum':{'editable':True, 'name':_('Afsluit datum')},
                              'coupon_te_betalen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Coupon te betalen')},
                              'rente':{'editable':True, 'name':_('Rente')},
                              'eerste_coupon_datum':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Eerste coupon datum')},
                              'eind_datum':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Eind datum')},
                              'periodiciteit':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Periodiciteit')},
                             }
#  business_to_tiny
#  sales_line_data

class BondProductBeschrijving(Entity):
     """ Product beschrijving """
     using_options(tablename='bond_product_beschrijving')
     looptijd_maanden  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
     #versies  =  OneToMany('vfinance.model.bond.product.Product', inverse='beschrijving')
     name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=False)
     coupure  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=False)
     
     @property
     def periodiciteit( self ):
          pass
     

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['name', 'looptijd_maanden', 'coupure']
          form_display =  forms.Form(['name','looptijd_maanden','coupure','versies',], columns=2)
          field_attributes = {
                              'looptijd_maanden':{'editable':True, 'name':_('Looptijd in maanden')},
                              'versies':{'editable':True, 'name':_('Versies')},
                              'name':{'editable':True, 'name':_('Naam')},
                              'coupure':{'editable':True, 'name':_('Coupure')},
                              'periodiciteit':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Periodiciteit')},
                             }

class BondBestellijn(Entity):
     """Bestellijn in een bestelling"""
     using_options(tablename='bond_bestellijn')
     
     @property
     def belegd_bedrag( self ):
          pass
     
     product_id  =  schema.Column(sqlalchemy.types.Integer(), name='product', nullable=False, index=True)
     product  =  ManyToOne('vfinance.model.bond.product.BondProduct', field=product_id)
     state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     aantal  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
     verlopen_dagen_in_rekening  =  schema.Column(sqlalchemy.types.Boolean(), nullable=False)
     correctie_rente  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=False)
     
     @property
     def verlopen_dagen( self ):
          pass
     
     @property
     def te_betalen( self ):
          pass
     
     
     @property
     def dagrente( self ):
          pass
     
     bestelling_id  =  schema.Column(sqlalchemy.types.Integer(), name='bestelling', nullable=True, index=True)
     bestelling  =  ManyToOne('vfinance.model.bond.product.BondBestelling', field=bestelling_id, backref='bestellijnen')

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['product', 'aantal', 'verlopen_dagen_in_rekening', 'verlopen_dagen', 'dagrente', 'correctie_rente', 'te_betalen', 'state']
          form_display =  forms.Form(['product','aantal','verlopen_dagen','verlopen_dagen_in_rekening','dagrente','correctie_rente','te_betalen','state',], columns=2)
          field_attributes = {
                              'belegd_bedrag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Belegd bedrag')},
                              'product':{},
                              'product':{'editable':True, 'name':_('Product')},
                              'state':{'editable':False, 'name':_('Status'), 'choices':[('compact', 'Obligaties nog niet aangemaakt'), ('expanded', 'Obligaties aangemaakt')]},
                              'aantal':{'editable':True, 'name':_('Aantal')},
                              'verlopen_dagen_in_rekening':{'editable':True, 'name':_('Breng verlopen dagen in rekening')},
                              'correctie_rente':{'editable':True, 'name':_('Correctie rente')},
                              'verlopen_dagen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Verlopen dagen')},
                              'te_betalen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Te betalen')},
                              'dagrente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Dagrente')},
                              'bestelling':{},
                              'bestelling':{'editable':True, 'name':_('Bestelling')},
                             }
#  acc_gen
#  format_venice_kapbon_nummer
#  format_venice_product_nummer
#  months_between_dates
#  snap_date

class Bond(Entity):
     """De obligatiebon"""
     using_options(tablename='bond_bond')   
     
     @property
     def nummer( self ):
          pass
     
     state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)   
     
     @property
     def name( self ):
          pass
     
     opmerking  =  schema.Column(camelot.types.RichText(), nullable=True)
     #owner  =  OneToMany('vfinance.model.bond.product.Owner', inverse='bond')
     
     @property
     def payment( self ):
          pass
     
     bestelling_id  =  schema.Column(sqlalchemy.types.Integer(), name='bestelling', nullable=False, index=True)
     bestelling  =  ManyToOne('vfinance.model.bond.product.BondBestelling', field=bestelling_id, backref='bonds')
     product_id  =  schema.Column(sqlalchemy.types.Integer(), name='product', nullable=False, index=True)
     product  =  ManyToOne('vfinance.model.bond.product.BondProduct', field=product_id)   
     
     @property
     def last_owner( self ):
          pass
     
     serie_nummer  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)

     def __unicode__(self):
          return self.name

     class Admin(EntityAdmin):
          list_display =  ['product', 'serie_nummer', 'nummer', 'last_owner', 'state']
          form_display =  forms.Form([forms.TabForm([(_('Algemeen'), forms.Form(['product','serie_nummer','nummer','state','last_owner','opmerking',], columns=2)),(_('Betalingen'), forms.Form(['payment',], columns=2)),], position=forms.TabForm.WEST)], columns=2)
          field_attributes = {
                              'nummer':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Nummer')},
                              'state':{'editable':False, 'name':_('Status'), 'choices':[('draft', 'Opmaak'), ('doorgevoerd', 'Doorgevoerd')]},
                              'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                              'opmerking':{'editable':True, 'name':_('Opmerking')},
                              'owner':{'editable':True, 'name':_('Eigendom van')},
                              'payment':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Betalingen')},
                              'bestelling':{},
                              'bestelling':{'editable':False, 'name':_('Bestelling')},
                              'product':{},
                              'product':{'editable':False, 'name':_('Product')},
                              'last_owner':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Laatste eigenaar')},
                              'serie_nummer':{'editable':False, 'name':_('Serie nummer')},
                             }
