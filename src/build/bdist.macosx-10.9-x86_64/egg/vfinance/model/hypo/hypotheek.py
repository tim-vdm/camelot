import collections
from copy import copy
import datetime
import logging
import os
from decimal import Decimal as D

import sqlalchemy.types
from sqlalchemy import sql, orm, schema

from camelot.core.orm import  (Entity, OneToMany, ManyToOne, 
                               using_options, ColumnProperty)
from camelot.admin.entity_admin import EntityAdmin
from camelot.admin.action import CallMethod, list_filter
from camelot.model.authentication import end_of_times
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.core.conf import settings
from camelot.core.exception import UserException
from camelot.core.utils import ugettext, ugettext_lazy as _
import camelot.types

from ..bank.agreement import AbstractAgreement
from ..bank.product import Product
from ..bank.schedule import ScheduleMixin

from vfinance.model.bank import constants as bank_constants
from vfinance.model.bank.dossier import DossierMixin
from vfinance.model.bank.dual_person import DualPerson, DualPersonFeature, name_of_dual_person
from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon
from vfinance.model.bank.rechtspersoon import Rechtspersoon
from vfinance.model.bank.constrained import ConstrainedDocument
from vfinance.model.bank.varia import PostcodeGemeente
from vfinance.model.hypo.summary.credit_application_verification import CreditApplicationVerification
from vfinance.admin.vfinanceadmin import VfinanceAdmin

from . import constants
from .state import ChangeState
from ...sql import greatest, bool_or

logger = logging.getLogger('vfinance.model.hypo.hypotheek')

types_aflossing = [('vast_kapitaal', 'Vast kapitaal'),
                   ('vaste_aflossing', 'Vast bedrag'),
                   ('bullet', 'Enkel intrest'),
                   ('cummulatief', 'Alles op einddatum'),
                   ('vaste_annuiteit', 'Vaste annuiteit')]

def maand_rente_naar_periodieke_rente(maand_rente, interval):
  """Rente per maand naar periodieke rente, waarbij interval het aantal intervals
  is per jaar, dwz het aantal aflossingen per jaar
  @maand_rente wordt altijd naar decimal geconverteerd
  @return periodieke rente als string
  """
  return str( (100 * ((1+D(maand_rente)/100)**(12/interval)-1) ).quantize( D('0.00001') ) )

class GoedMixin( PostcodeGemeente ):
  verwerving  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
  # Onder de venale waarde van een onroerend goed verstaat men de prijs die men voor 
  # het onroerend goed normaal mag verwachten bij een verkoop nadat er voldoende 
  # publiciteit voor de verkoop gemaakt is en waarbij er een normale mededinging was 
  # van het aantal kandidaat- kopers.
  venale_verkoopwaarde  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
  postcode  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=False)
  huurwaarde  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
  # replaced with backref waarborgen  =  OneToMany('vfinance.model.hypo.hypotheek.Waarborg', )
  bestemming  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
  straat  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=False)
  type  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
  gemeente  =  schema.Column(sqlalchemy.types.Unicode(30), nullable=False)
  # replaced with backref eigenaar  =  OneToMany('vfinance.model.hypo.hypotheek.EigenaarGoed', )
  # fields for tinyerp compatibility

  @property
  def name(self):
      return '%s, %s %s'%(self.straat or '', self.postcode or '', self.gemeente or '')

  def __unicode__(self):
      return self.name

  auto_postcode = property(PostcodeGemeente._get_postcode, PostcodeGemeente._set_postcode)
  
  class Admin(EntityAdmin):
      list_display =  ['venale_verkoopwaarde', 'straat', 'auto_postcode', 'gemeente']
      form_display =  forms.Form([forms.GroupBoxForm(_('Adres'),['straat','auto_postcode','gemeente',], columns=2),'bestemming','type','venale_verkoopwaarde','huurwaarde','verwerving','eigenaar','waarborgen',], columns=2)
      field_attributes = {
                          'verwerving':{'editable':True, 'name':_('Aard van verwerving'), 'choices':[('aankoop', 'Aankoop'), ('openbaar', 'Openbaar'),('andere', 'Andere'), ('erfenis', 'Erfenis'), ('schenking', 'Schenking')]},
                          'venale_verkoopwaarde':{'editable':True, 'name':_('Venale verkoop')},
                          'postcode':{'editable':True, 'name':_('Postcode')},
                          'auto_postcode':{'editable':True, 'name':_('Postcode')},
                          'huurwaarde':{'editable':True, 'name':_('Maandelijkse huuropbrengst')},
                          'waarborgen':{'editable':True, 'name':_('Waarborgen eerder in rang')},
                          'bestemming':{'editable':True, 'name':_('Bestemming'), 'choices':[(None, ''), ('eigen_woning', 'Eigen woning'), ('tweede_verblijf', '2de verblijf'), ('opbrengst', 'Opbrengsteigendom'), ('handelspand', 'Handelspand')]},
                          'straat':{'editable':True, 'name':_('Straat nummer bus')},
                          'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                          'type':{'editable':True, 'name':_('Type eigendom'), 'choices':[(None,''), ('bouwgrond', 'Bouwgrond'), ('appartement', 'Appartement'), ('rijwoning', 'Rijwoning'), ('half_open', 'Half open bebouwing'), ('bungalow', 'Bungalow'), ('villa', 'Villa'), ('woonboot', 'Woonboot'), ('complex', 'Complex')]},
                          'gemeente':{'editable':True, 'name':_('Gemeente')},
                          'eigenaar':{'editable':True, 'name':_('Eigenaars')},
                          'hypotheek_id':{'editable':True, 'name':_('Hypotheek')},
                         }    
      
class Goed( Entity, GoedMixin ):
    """een onroerend goed"""
    using_options(tablename='hypo_goed', order_by=['id'])  
    hypotheek_id  =  schema.Column(sqlalchemy.types.Integer(), name='hypotheek_id', nullable=True, index=True)
    hypotheek  =  ManyToOne('vfinance.model.hypo.hypotheek.Hypotheek', field=hypotheek_id, backref='ander_goed')      
        
class TeHypothekerenGoed( Entity, GoedMixin, ConstrainedDocument ):
    """Het te hypothekeren goed"""
    using_options( tablename='hypo_te_hypothekeren_goed', order_by=['id'] )
    compromis  =  schema.Column(camelot.types.File(upload_to=os.path.join('hypo.te_hypothekeren_goed', 'compromis')), nullable=True)
    rang  =  property(lambda self:self.get_rang())
    vrijwillige_verkoop  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    # replaced with backref eigenaar  =  OneToMany('vfinance.model.hypo.hypotheek.EigenaarGoed', )
    gedwongen_verkoop  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    schatter  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon')
    brandverzekering_id  =  schema.Column(sqlalchemy.types.Integer(), name='brandverzekering', nullable=True, index=True)
    brandverzekering  =  ManyToOne('vfinance.model.hypo.hypotheek.Verzekering', field=brandverzekering_id)
    schattingsverslag  =  schema.Column(camelot.types.File(upload_to=os.path.join('hypo.te_hypothekeren_goed', 'schattingsverslag')), nullable=True)
    # replaced with backref aanvragen  =  OneToMany('vfinance.model.hypo.hypotheek.GoedAanvraag', )
    kadaster  =  schema.Column(sqlalchemy.types.Unicode(40), nullable=True)
    # replaced with backref waarborgen  =  OneToMany('vfinance.model.hypo.hypotheek.Waarborg', inverse='te_hypothekeren_goed_id', )
    bewoonbare_oppervlakte = schema.Column(sqlalchemy.types.Numeric(precision=5, scale=2), nullable=True)
    # Te controleren en implementeren bij implementatie features
    # grond_oppervlakte = schema.Column(sqlalchemy.types.Unicode(15), nullable=True)
    straat_breedte_grond = schema.Column(sqlalchemy.types.Numeric(precision=5, scale=2), nullable=True)
    straat_breedte_gevel = schema.Column(sqlalchemy.types.Numeric(precision=5, scale=2), nullable=True)
    
    @property
    def dossiers(self):
        from .dossier import Dossier, AkteDossier
        from .beslissing import Beslissing
        from .akte import Akte
        query = orm.object_session(self).query(Dossier)
        query = query.join(AkteDossier)
        query = query.join(Akte)
        query = query.join(Beslissing)
        query = query.join(Hypotheek)
        query = query.join(GoedAanvraag)
        query = query.join(TeHypothekerenGoed)
        query = query.filter(TeHypothekerenGoed.id==self.id)
        return query.all()
  
    @property
    def state(self):
        for dossier in self.dossiers:
            if dossier.state != 'ended':
              return 'active'
        return 'passive'
  
    @property
    def rang(self):
        return len(self.waarborgen)+1
    
    def constraints(self):
        yield (1, 'schattingsverslag', bool(self.schattingsverslag))
        yield (2, 'compromis', bool(self.compromis))
    
    def __unicode__(self):
        return self.name

    auto_postcode = property(PostcodeGemeente._get_postcode, PostcodeGemeente._set_postcode)
    
    class Admin(VfinanceAdmin):
        verbose_name = _('Onroerend goed')
        verbose_name_plural = _('Onroerende goeden')
        list_display =  ['gedwongen_verkoop', 'straat', 'auto_postcode', 'gemeente', 'kadaster', 'state']
        form_state = 'maximized'
        form_display =  forms.TabForm([(_('Goed'), forms.Form([forms.GroupBoxForm(_('Adres'),['straat','auto_postcode','gemeente','kadaster',], columns=2),
                                                               forms.GroupBoxForm(_('Opmerkingen'),['related_constraints',], columns=2),
                                                               forms.GroupBoxForm(_('Waarde'),['venale_verkoopwaarde','vrijwillige_verkoop','gedwongen_verkoop','huurwaarde',
                                                                                               'bewoonbare_oppervlakte', # 'grond_oppervlakte',
                                                                                               'straat_breedte_grond', 'straat_breedte_gevel',], columns=2),
                                                               forms.GroupBoxForm(_('Eigenaars'),['eigenaar',], columns=2),])),
                                       (_('Waarborg'), forms.Form([forms.GroupBoxForm(_('Waarborgen eerder in rang'),['waarborgen',]),
                                                                   forms.GroupBoxForm(_('Bijkomend'),['schatter','schattingsverslag','bestemming','verwerving','compromis','type',], columns=2),
                                                                   forms.GroupBoxForm(_('Verzekeringen'),['brandverzekering',]),])),
                                       (_('Hypotheken'), forms.Form(['aanvragen', 'dossiers',], columns=2)),
                                       ], position=forms.TabForm.WEST)
        field_attributes = copy(Goed.Admin.field_attributes)
        field_attributes.update({
                            # 'grond_oppervlakte': {'editable': True, 'name': _('Grondoppervlakte')},
                            'compromis':{'editable':True, 'name':_('Compromis')},
                            'rang':{'editable':False, 'delegate':delegates.IntegerDelegate, 'name':_('Rang')},
                            'auto_postcode':{'editable':True, 'name':_('Postcode')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                            'vrijwillige_verkoop':{'editable':True, 'name':_('Vrijwillige openbare verkoop')},
                            'eigenaar':{'editable':True, 'name':_('Eigenaars')},
                            'gedwongen_verkoop':{'editable':True, 'name':_('Gedwongen openbare verkoop')},
                            'schatter':{'editable':True, 'name':_('Schatter')},
                            'brandverzekering':{'editable':True, 'name':_('Brand Verzekering')},
                            'state':{'editable':False, 'delegate':delegates.TextEditDelegate, 'name':_('Status')},
                            'schattingsverslag':{'editable':True, 'name':_('Schattingsverslag')},
                            'aanvragen':{'editable':True, 'name':_('Aanvragen')},
                            'kadaster':{'editable':True, 'name':_('Kadastraal perceelnummer')},
                            'dossiers':{'editable':False, 
                                        'python_type':list, 
                                        'delegate':delegates.One2ManyDelegate, 
                                        'target':'Dossier', 
                                        'name':_('Dossiers')},
                            'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                            'type':{'editable':True, 'name':_('Type eigendom'), 'choices':[(None,''), ('bouwgrond', 'Bouwgrond'), ('appartement', 'Appartement'), ('rijwoning', 'Rijwoning'), ('half_open', 'Half open bebouwing'), ('bungalow', 'Bungalow'), ('villa', 'Villa'), ('kasteel', 'Kasteeldomein')]},
                            'waarborgen':{'editable':True, 'name':_('Waarborgen eerder in rang')},
                            'bestemming':{'editable':True, 'name':_('Bestemming'), 'choices':[('eigen_woning', 'Eigen woning'), ('tweede_verblijf', '2de verblijf'), ('opbrengst', 'Opbrengsteigendom'), ('handelspand', 'Handelspand')]},
                           })
        field_attributes.update(ConstrainedDocument.Admin.field_attributes)

class GoedAanvraag(Entity, ConstrainedDocument):
    """Relatie tussen het te hypothekeren goed en de hypotheek aanvraag"""
    using_options(tablename='hypo_goed_aanvraag')
    te_hypothekeren_goed_id  =  schema.Column(sqlalchemy.types.Integer(), name='te_hypothekeren_goed', nullable=False, index=True)
    te_hypothekeren_goed  =  ManyToOne('vfinance.model.hypo.hypotheek.TeHypothekerenGoed', field=te_hypothekeren_goed_id, backref='aanvragen')
    hypothecaire_inschrijving  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    hypothecair_mandaat  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    hypotheek_id  =  schema.Column(sqlalchemy.types.Integer(), name='hypotheek', nullable=False, index=True)
    hypotheek  =  ManyToOne('vfinance.model.hypo.hypotheek.Hypotheek', field=hypotheek_id, backref='gehypothekeerd_goed')
    aanhorigheden = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2))# source: HY_BedragAanhorigheden from HypoSoft Lening table
    prijs_grond = schema.Column(sqlalchemy.types.Numeric(precision=10, scale=2), nullable=True)
    waarde_voor_werken = schema.Column(sqlalchemy.types.Numeric(precision=10, scale=2), nullable=True)
    waarde_verhoging = schema.Column(sqlalchemy.types.Numeric(precision=10, scale=2), nullable=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__(self):
        if self.te_hypothekeren_goed:
            return unicode(self.te_hypothekeren_goed)
        return u''

    class Admin(EntityAdmin):
        list_display =  ['te_hypothekeren_goed', 'hypothecaire_inschrijving', 'hypothecair_mandaat', 'hypotheek' ]
        form_display =  forms.Form(['te_hypothekeren_goed','hypothecaire_inschrijving','hypothecair_mandaat', 'prijs_grond', 'waarde_voor_werken', 'waarde_verhoging','related_constraints',])
        field_attributes = {
                            'te_hypothekeren_goed':{'editable':True, 'name':_('Te hypothekeren goed')},
                            'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                            'hypothecaire_inschrijving':{'editable':True, 'name':_('Hypothecaire inschrijving')},
                            'hypothecair_mandaat':{'editable':True, 'name':_('Hypothecair mandaat')},
                            'hypotheek':{'editable':True, 'name':_('Hypotheek')},
                           }
        field_attributes.update(ConstrainedDocument.Admin.field_attributes)

class AkteAanvraag(Entity):
    """Relatie tussen een verleden akte en een hypotheek aanvraag"""
    using_options(tablename='hypo_akte_aanvraag')
    percentage  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
    akte_id  =  schema.Column(sqlalchemy.types.Integer(), name='akte', nullable=True, index=True)
    akte  =  ManyToOne('vfinance.model.hypo.akte.Akte', field=akte_id)
    hypotheek_id  =  schema.Column(sqlalchemy.types.Integer(), name='hypotheek', nullable=True, index=True)
    hypotheek  =  ManyToOne('vfinance.model.hypo.hypotheek.Hypotheek', field=hypotheek_id)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__(self):
        return self.name

    class Admin(EntityAdmin):
        list_display =  ['akte', 'hypotheek', 'percentage']
        form_display =  forms.Form(['akte','percentage',])
        field_attributes = {
                            'percentage':{'editable':True, 'name':_('Toegekend percentage')},
                            'akte':{'editable':True, 'name':_('Akte')},
                            'hypotheek':{'editable':True, 'name':_('Hypotheek')},
                           }

class Verzekering(Entity):
    using_options(tablename='hypo_verzekering')
    polis  =  schema.Column(sqlalchemy.types.Unicode(40), nullable=True)
    amount  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    makelaar  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon')
    maatschappij  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon')
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    @property
    def name(self):
        return self.polis
    
    def __unicode__(self):
        return self.name

    class Admin(EntityAdmin):
        list_display =  ['polis', 'makelaar', 'maatschappij', 'amount']
        form_display =  forms.Form(['makelaar','maatschappij','polis','amount',])
        field_attributes = {
                            'polis':{'editable':True, 'name':_('Polisnummer')},
                            'amount':{'editable':True, 'name':_('Verzekerd bedrag')},
                            'makelaar':{'editable':True, 'name':_('Makelaar')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                            'maatschappij':{'editable':True, 'name':_('Maatschappij')},
                           }

class OntlenerLopendKrediet( DualPerson ):
    using_options(tablename='hypo_ontlener_lopend_krediet')
    __table_args__ = ( schema.CheckConstraint('natuurlijke_persoon is not null or rechtspersoon is not null', name='hypo_ontlener_lopend_krediet_persoon_fk'),)
    rechtspersoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon', nullable=True, index=True)
    rechtspersoon  =  ManyToOne( 'vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id,
                                 onupdate = 'cascade', ondelete = 'restrict' )
    natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon', nullable=True, index=True)
    natuurlijke_persoon  =  ManyToOne( 'vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id,
                                       onupdate = 'cascade', ondelete = 'restrict' )
    related_constraints  =  property(lambda self:self.get_constraints())
    lopend_krediet_id  =  schema.Column(sqlalchemy.types.Integer(), name='lopend_krediet', nullable=True, index=True)
    lopend_krediet  =  ManyToOne('vfinance.model.hypo.hypotheek.LopendKrediet', field=lopend_krediet_id, backref='ontlener')
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__(self):
        return self.name

    class Admin(DualPerson.Admin):
        list_display =  ['natuurlijke_persoon', 'rechtspersoon', 'telefoon']
        form_display =  forms.Form([forms.GroupBoxForm(_('Natuurlijke persoon'),['natuurlijke_persoon',]),forms.GroupBoxForm(_('Rechtspersoon'),['rechtspersoon',]),])
        field_attributes = {
                            'rechtspersoon':{'editable':True, 'name':_('Rechtspersoon')},
                            'straat':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Straat')},
                            'gemeente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Gemeente')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                            'natuurlijke_persoon':{'editable':True, 'name':_('Natuurlijke persoon')},
                            'taal':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Taal')},
                            'postcode':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Postcode')},
                            'full_name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                            'lopend_krediet':{'editable':True, 'name':_('unknown')},
                            'telefoon':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Telefoon')},
                           }

class EigenaarGoed(DualPerson, ConstrainedDocument):
    """De eigenaar van een onroerend goed, al dan niet te hypothekeren"""
    using_options(tablename='hypo_eigenaar_goed')
    __table_args__ = ( schema.CheckConstraint('natuurlijke_persoon is not null or rechtspersoon is not null', name='hypo_eigenaar_goed_persoon_fk'), )
    rechtspersoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon', nullable=True, index=True)
    rechtspersoon  =  ManyToOne( 'vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id, 
                                 onupdate = 'cascade', ondelete = 'restrict' )
    goed_id_id  =  schema.Column(sqlalchemy.types.Integer(), name='goed_id', nullable=True, index=True)
    goed_id  =  ManyToOne('vfinance.model.hypo.hypotheek.Goed', field=goed_id_id, backref='eigenaar')
    natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon', nullable=True, index=True)
    natuurlijke_persoon  =  ManyToOne( 'vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id,
                                       onupdate = 'cascade', ondelete = 'restrict' )
    te_hypothekeren_goed_id_id  =  schema.Column(sqlalchemy.types.Integer(), name='te_hypothekeren_goed_id', nullable=True, index=True)
    te_hypothekeren_goed_id  =  ManyToOne('vfinance.model.hypo.hypotheek.TeHypothekerenGoed', field=te_hypothekeren_goed_id_id, backref='eigenaar')
    percentage  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    type  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__(self):
        return self.name

    class Admin(DualPerson.Admin):
        list_display =  ['natuurlijke_persoon', 'rechtspersoon', 'type', 'percentage']
        form_display =  forms.Form([forms.GroupBoxForm(_('Natuurlijke persoon'),['natuurlijke_persoon',], columns=2),
                                    forms.GroupBoxForm(_('Rechtspersoon'),['rechtspersoon',], columns=2),
                                    'type','percentage',], columns=2)

        field_attributes = {
                            'rechtspersoon':{'editable':True, 'name':_('Rechtspersoon')},
                            'straat':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Straat')},
                            'gemeente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Gemeente')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                            'goed_id':{'editable':True, 'name':_('Goed')},
                            'natuurlijke_persoon':{'editable':True, 'name':_('Natuurlijke persoon')},
                            'te_hypothekeren_goed_id':{'editable':True, 'name':_('Goed')},
                            'postcode':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Postcode')},
                            'full_name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'percentage':{'editable':True, 'name':_('Percentage eigendom')},
                            'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                            'type':{'editable':True, 'name':_('Type eigendom'), 'choices':[(None,''), ('vruchtgebruik', 'Vruchtgebruik'), ('naakte_eigendom', 'Naakte eigendom'), ('volle_eigendom', 'Volle eigendom')]},
                            'taal':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Taal')},
                            'telefoon':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Telefoon')},
                           }
        field_attributes.update(ConstrainedDocument.Admin.field_attributes)
##  constrained_objects
##  add_calculated_field
#
class Waarborg(Entity):
    """Een genomen waarborg op een al dan niet te hypotheckeren goed"""
    using_options(tablename='hypo_waarborg')
    goed_id_id  =  schema.Column(sqlalchemy.types.Integer(), name='goed_id', nullable=True, index=True)
    goed_id  =  ManyToOne('vfinance.model.hypo.hypotheek.Goed', field=goed_id_id, backref='waarborgen')
    instelling  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon')
    saldo  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    te_hypothekeren_goed_id_id  =  schema.Column(sqlalchemy.types.Integer(), name='te_hypothekeren_goed_id', nullable=True, index=True)
    te_hypothekeren_goed_id  =  ManyToOne('vfinance.model.hypo.hypotheek.TeHypothekerenGoed', field=te_hypothekeren_goed_id_id, backref='waarborgen')
    bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    aanhorigheden  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__(self):
        return self.name

    class Admin(EntityAdmin):
        list_display =  ['bedrag', 'saldo', 'aanhorigheden', 'instelling']
        form_display =  forms.Form(['bedrag','saldo','aanhorigheden','instelling',])
        field_attributes = {
                            'goed_id':{'editable':True, 'name':_('Goed')},
                            'instelling':{'editable':True, 'name':_('Instelling')},
                            'saldo':{'editable':True, 'name':_('Saldo')},
                            'te_hypothekeren_goed_id':{'editable':True, 'name':_('Goed')},
                            'bedrag':{'editable':True, 'name':_('Bedrag')},
                            'aanhorigheden':{'editable':True, 'name':_('Aanhorigheden (percentage)')},
                           }
#  maand_rente_naar_periodieke_rente
#  field_join
# personen = [<class 'bank.rechtspersoon.Rechtspersoon.bestuurder'>, <class 'bank.rechtspersoon.Rechtspersoon.economische_eigenaar'>, <class 'bank.klant.persoon'>, <class 'hypo.hypotheek.hypo_ontlener_lopend_krediet'>, <class 'hypo.hypotheek.hypo_hypotheeknemer'>, <class 'hypo.hypotheek.hypo_eigenaar_goed'>]

class LopendKrediet(Entity):
    using_options(tablename='hypo_lopend_krediet')
    #replaced by backref ontlener  =  OneToMany('vfinance.model.hypo.hypotheek.OntlenerLopendKrediet')
    status = schema.Column(camelot.types.Enumeration(constants.lopend_krediet_statuses), nullable=False, default='lopende')
    maatschappij  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon')
    ontleend_bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    saldo  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    krediet_nummer  =  schema.Column(sqlalchemy.types.Unicode(40), nullable=True)
    einddatum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    maandlast  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    regelmatig_betaald  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    hypotheek_id  =  schema.Column(sqlalchemy.types.Integer(), name='hypotheek', nullable=True, index=True)
    hypotheek  =  ManyToOne('vfinance.model.hypo.hypotheek.Hypotheek', field=hypotheek_id, backref='lopend_krediet')
    # fields added for HypoSoft data
    datum_akte = schema.Column(sqlalchemy.types.Date())
    looptijd = schema.Column(sqlalchemy.types.Integer())
    rentevoet = schema.Column(sqlalchemy.types.Numeric(precision=6, scale=4))
    type_aflossing  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False, default=unicode('vaste_aflossing'))
    verkocht = schema.Column(sqlalchemy.types.Boolean())
    datum_verkoop = schema.Column(sqlalchemy.types.Date())
    prijs_goed = schema.Column(sqlalchemy.types.Numeric(precision=10, scale=2))
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    @property
    def over_te_nemen_saldo(self):
        if self.status is not None:
            return {'over te nemen':self.saldo,
                    'lopende':0,
                    'terugbetaald':0}[self.status]

    @property
    def te_betalen_maandlast(self):
        if self.status is not None:
            return {'over te nemen':0,
                    'lopende':self.maandlast,
                    'terugbetaald':0}[self.status]

    @property
    def name(self):
        return self.krediet_nummer or ''

    def __unicode__(self):
        return self.name

    class Admin(EntityAdmin):
        list_display =  ['maatschappij',
                         'ontleend_bedrag',
                         'maandlast',
                         'saldo',
                         'regelmatig_betaald',
                         'status']
        form_display =  forms.Form(['maatschappij',
                                    'ontleend_bedrag',
                                    'maandlast',
                                    'saldo',
                                    'einddatum',
                                    'krediet_nummer',
                                    'regelmatig_betaald',
                                    'status',
                                    'ontlener',
                                    'datum_akte',
                                    'looptijd',
                                    'rentevoet',
                                    'type_aflossing',
                                    'verkocht',
                                    'datum_verkoop',
                                    'prijs_goed'])
        field_attributes = {'ontlener':{'editable':True, 'name':_('Ontleners')},
                            'maatschappij':{'editable':True, 'name':_('Maatschappij')},
                            'ontleend_bedrag':{'editable':True, 'name':_('Ontleend bedrag')},
                            'saldo':{'editable':True, 'name':_('Saldo')},
                            'krediet_nummer':{'editable':True, 'name':_('Kredietnummer')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Name')},
                            'over_te_nemen_saldo':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Over te nemen saldo')},
                            'einddatum':{'editable':True, 'name':_('Einddatum')},
                            'te_betalen_maandlast':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Te betalen maandlast')},
                            'maandlast':{'editable':True, 'name':_('Gemiddelde maandlast')},
                            'regelmatig_betaald':{'editable':True, 'name':_('Regelmatig betaald')},
                            'type_aflossing':{'choices':types_aflossing},
                            'hypotheek':{'editable':True, 'name':_('Hypotheek')}}

class BijkomendeWaarborg(Entity):
    """
    Een roerend goed dat in waarborg kan worden gegeven voor een lening
    """
    using_options(tablename='hypo_bijkomende_waarborg')
    name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=False)
    state  =  property(lambda self:self.get_state())
    waarde  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False)
    aanvragen  =  OneToMany('vfinance.model.hypo.hypotheek.BijkomendeWaarborgHypotheek', )
    dossiers  =  OneToMany('vfinance.model.hypo.dossier.BijkomendeWaarborgDossier', )
    type  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__(self):
        return self.name

    class Admin(VfinanceAdmin):
        list_display =  ['name', 'type', 'waarde']
        field_attributes = {
                            'name':{'editable':True, 'name':_('Korte beschrijving')},
                            'state':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Status')},
                            'waarde':{'editable':True, 'name':_('Waarde')},
                            'aanvragen':{'editable':True, 'name':_('Aanvragen')},
                            'dossiers':{'editable':True, 'name':_('Dossiers')},
                            'type':{'editable':True, 'name':_('Type'), 'choices':[('andere', 'Andere'), ('aandelen', 'Aandelen'), ('obligaties', 'Obligaties'), ('verzekeringen', 'Verzekeringen'), ('kapitalisatiebonnen', 'Kapitalisatiebonnen')]},
                           }
##  natuurlijke_persoon_full_name
#
##  natuurlijke_persoon_address
#
class Bedrag(Entity, ScheduleMixin):
    """Een ontleend bedrag als deel van een hypotheek, het doel van het bedrag en de wijze
  waarop het zal worden terugbetaald"""
  
    doelen_description = {
      'doel_aankoop_terrein' : 'Aankoop terrein',
      'doel_aankoop_gebouw_btw' : 'Aankoop gebouw met BTW',
      'doel_aankoop_gebouw_registratie' : 'Aankoop gebouw met Registratierechten',
      'doel_nieuwbouw' : 'Nieuwbouw',
      'doel_renovatie' : 'Renovatie',
      'doel_herfinanciering' : 'Herfinanciering',
      'doel_overbrugging' : 'Overbruggingskrediet',
      'doel_centralisatie' : 'Centralisatie',
      'doel_behoud' : 'Behoud onroerend patrimonium',
      'doel_handelszaak' : 'Overname handelszaak'
    }
    
    looptijden = {6:'6 maand'}
    for i in range(1,5):
        looptijden[i*12] = '%i jaar'%i
    for i in range(5,26,5):
        looptijden[i*12] = '%i jaar'%i
      
    types_aflossing =  {
      'vaste_aflossing':'Vast bedrag',
      'vast_kapitaal':'Vast kapitaal',
      'bullet':'Enkel intrest',
      'cummulatief':'Alles op einddatum',
      'vaste_annuiteit':'Vaste annuiteiten',
    }
  
    using_options(tablename='hypo_bedrag')
    product = ManyToOne(Product, required=True, ondelete='restrict', onupdate='cascade')
    type_vervaldag  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    doel_nieuwbouw  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_herfinanciering  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    opname_periode  =  schema.Column(sqlalchemy.types.Integer(), default=0)
    doel_handelszaak  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_aankoop_terrein  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    terugbetaling_start  =  schema.Column(sqlalchemy.types.Integer(), default=0)
    bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), default=0, nullable=False)
    doel_renovatie  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_behoud  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_aankoop_gebouw_btw  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_aankoop_gebouw_registratie  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_centralisatie  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_overbrugging  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    terugbetaling_interval  =  schema.Column(sqlalchemy.types.Integer(), nullable=True, default=12)
    looptijd  =  schema.Column(sqlalchemy.types.Integer(), default=60, nullable=False)
    opname_schijven = schema.Column(sqlalchemy.types.Integer(), default=0, nullable=True)
    type_aflossing  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False, default=unicode('vaste_aflossing'))
    hypotheek_id_id  =  schema.Column(sqlalchemy.types.Integer(), name='hypotheek_id', nullable=True, index=True)
    hypotheek_id  =  ManyToOne('vfinance.model.hypo.hypotheek.Hypotheek', field=hypotheek_id_id, backref='gevraagd_bedrag')

    agreed_features = orm.relationship('HypoApplicationFeatureAgreement',
                                       cascade = 'all, delete-orphan')
    agreed_features_by_description = orm.relationship('HypoApplicationFeatureAgreement',
                                                      #backref = 'of',
                                                      collection_class = orm.collections.attribute_mapped_collection('described_by'),
                                                      cascade = 'all, delete-orphan')

    def __getattr__(self, attr):
        if attr in constants.hypo_feature_names:
            feature = self.agreed_features_by_description.get(attr)
            if feature is not None:
                return feature.value
            else:
                return None
        raise AttributeError(attr)

    def __setattr__(self, attr, value):
        if attr in constants.hypo_feature_names:
            self.agreed_features_by_description[attr] = HypoApplicationFeatureAgreement(value=value,
                                                                                        described_by=attr)
        else:
            return super(Bedrag, self).__setattr__(attr, value)

    @property
    def doelen(self):
        return ', '.join( [ ugettext( self.doelen_description[k] ) for k in self.doelen_description.keys() if getattr(self,k) ] )

    def get_rente_historiek(self):
        from rentevoeten import RenteTabelCategorie, RenteTabel, RenteHistoriek
        categorie = RenteTabelCategorie.categorie_from_bedrag(self)
        if categorie:
          tabel = RenteTabel.tabel_from_bedrag(categorie, self)
          if tabel:
            return RenteHistoriek.historiek_from_datum(tabel, self.hypotheek_id.aanvraagdatum)
        
    @property
    def basis_rente(self):
        
        def basis_rente(historiek, interval):
            logger.debug('basis rente voor historiek %s'%historiek)
            if historiek:
                return maand_rente_naar_periodieke_rente(historiek.basis, interval)
            return 0
        
        logger.debug('get_basis_rente bedrag : %s'%self.id)
        historiek = self.get_rente_historiek()
        logger.debug('historiek : %s'%historiek)
        return basis_rente(historiek, self.terugbetaling_interval)

    @property
    def name(self):
        return '%s, %s maand, %s'%(self.bedrag or 0, self.looptijd or 0, Bedrag.types_aflossing[self.type_aflossing])
    
    @property
    def aktedatum(self):
        if self.hypotheek_id:
            return self.hypotheek_id.aktedatum

    @property
    def valid_from_date(self):
        return self.aktedatum

    @property
    def duration(self):
        return self.looptijd

    @property
    def direct_debit(self):
        if self.hypotheek_id:
            return self.hypotheek_id.domiciliering

    @property
    def period_type(self):
        return self.terugbetaling_interval
  
    def __unicode__(self):
        return self.name

    class Admin(EntityAdmin):
        list_display =  ['product', 'bedrag', 'looptijd', 'type_aflossing', 'type_vervaldag']
        form_display =  forms.TabForm([(_('Gevraagd bedrag'), forms.Form(['product','bedrag','opname_periode','looptijd','terugbetaling_start', 'opname_schijven',
                                                                          'terugbetaling_interval','type_aflossing', 'type_vervaldag', 'state_guarantee',
                                                                          forms.GroupBoxForm(_('Doelen'),['doel_aankoop_terrein','doel_aankoop_gebouw_btw','doel_aankoop_gebouw_registratie','doel_nieuwbouw','doel_renovatie','doel_herfinanciering','doel_overbrugging','doel_centralisatie','doel_behoud',], columns=2),
                                                                          forms.GroupBoxForm(_('Evaluatie'), ['basis_rente', 'goedgekeurd_bedrag']) ], columns=2)),
                                       #(_('Features'), ['agreed_features']),
                                       ])
        field_attributes = {
                            'type_vervaldag':{'editable':True, 'name':_('Vervaldag valt op'), 'choices':[('akte', 'periodieke vervaldag lening'), ('maand', '1e van de maand')]},
                            'doel_nieuwbouw':{'editable':True, 'name':_('Nieuwbouw')},
                            'doel_herfinanciering':{'editable':True, 'name':_('Herfinanciering')},
                            'opname_periode':{'editable':True, 'name':_('Opname periode (maanden)')},
                            'doel_handelszaak':{'editable':True, 'name':_('Overname handelszaak')},
                            'doel_aankoop_terrein':{'editable':True, 'name':_('Aankoop terrein')},
                            'terugbetaling_start':{'editable':True, 'name':_('Uitstel betaling (maanden)')},
                            'bedrag':{'editable':True, 'name':_('Gevraagd bedrag')},
                            'goedgekeurd_bedrag': {'editable':False},
                            'doel_renovatie':{'editable':True, 'name':_('Renovatie')},
                            'doel_behoud':{'editable':True, 'name':_('Behoud onroerend patrimonium')},
                            'doel_aankoop_gebouw_btw':{'editable':True, 'name':_('Aankoop gebouw met BTW')},
                            'doel_aankoop_gebouw_registratie':{'editable':True, 'name':_('Aankoop gebouw met Registratierechten')},
                            'name':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Naam')},
                            'basis_rente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Basis rente')},
                            'doel_centralisatie':{'editable':True, 'name':_('Centralisatie')},
                            'aktedatum':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Aktedatum')},
                            'doel_overbrugging':{'editable':True, 'name':_('Overbruggingskrediet')},
                            # NOTE values also defined in vfinance/art/tempaltes/includes/approved_amount_table.html
                            'terugbetaling_interval':{'editable':True, 'name':_('Terugbetaling'), 'choices':[(12, 'maandelijks'), (4, 'trimesterieel'), (1, 'jaarlijks')]},
                            'looptijd':{'editable':True, 'name':_('Looptijd (maanden)')},
                            'product':{'delegate':delegates.ManyToOneChoicesDelegate},
                            'type_aflossing':{'editable':True, 'name':_('Aflossing'), 'choices':types_aflossing},
                            'hypotheek_id':{'editable':True, 'name':_('Hypotheek')},
                            'doelen':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Doelen')},
                            'state_guarantee':{'editable':True, 'delegate':delegates.FloatDelegate, 'decimal': True, 'name':_('Bedrag gewestwaarborg')},
                           }

class HypoApplicationFeatureAgreement(Entity):

    __tablename__ = 'hypo_application_feature_agreement'
  
    agreed_on_id = schema.Column(sqlalchemy.types.Integer(),
                                 schema.ForeignKey(Bedrag.id,
                                                   ondelete = 'cascade',
                                                   onupdate = 'cascade' ),
                                 nullable=False )
    described_by = schema.Column( camelot.types.Enumeration(constants.hypo_features), nullable=False, default='initial_approved_amount')
    value = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=5), nullable=False, default=D(0))
    comment = schema.Column( camelot.types.RichText() )

    class Admin( EntityAdmin ):
        verbose_name = _('Gevraagd bedrag Feature')
        verbose_name_plural = _('Hypo Dossier Features')
        list_display = ['described_by', 'value',]
        form_display = list_display + ['comment']
        field_attributes = {'described_by':{'name':_('Description')},}

class BijkomendeWaarborgHypotheek(Entity):
    """De koppeling tussen een bijkomende waarborg en een hypotheek aanvraag"""
    using_options(tablename='hypo_bijkomende_waarborg_hypotheek')
    bijkomende_waarborg_id  =  schema.Column(sqlalchemy.types.Integer(), name='bijkomende_waarborg', nullable=False, index=True)
    bijkomende_waarborg  =  ManyToOne('vfinance.model.hypo.hypotheek.BijkomendeWaarborg', field=bijkomende_waarborg_id)
    hypotheek_id  =  schema.Column(sqlalchemy.types.Integer(), name='hypotheek', nullable=True, index=True)
    hypotheek  =  ManyToOne('vfinance.model.hypo.hypotheek.Hypotheek', field=hypotheek_id, backref='bijkomende_waarborg')
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    @property
    def type(self):
        if self.bijkomende_waarborg:
            return self.bijkomende_waarborg.type

    @property
    def waarde(self):
        if self.bijkomende_waarborg:
            return self.bijkomende_waarborg.waarde        

    def __unicode__(self):
        if self.hypotheek:
          return unicode(self.hypotheek)
        return ''

    class Admin(EntityAdmin):
        list_display =  ['bijkomende_waarborg', 'type', 'waarde']
        field_attributes = {
                            'waarde':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Waarde')},
                            'bijkomende_waarborg':{'editable':True, 'name':_('Bijkomende waarborg')},
                            'type':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Type')},
                            'hypotheek':{'editable':True, 'name':_('Aanvragen')},
                           }

def nieuw_aanvraagnummer(application, company_id=None):
    from sqlalchemy import func
    session = orm.object_session(application)
    company_id = company_id or application.company_id or default_company_id()
    q = session.query(func.max(Hypotheek.aanvraagnummer)).filter(Hypotheek.company_id==company_id)
    max = q.scalar()
    if max is None:
        return 1
    return max+1

def default_company_id():
    return int(settings.get('HYPO_COMPANY_ID', 0))

class RequestCompleteAction( ChangeState ):
  
    def change_state( self, model_context, obj ):
        from beslissing import Beslissing
        if obj.note != None:
            raise UserException( obj.note )
        with model_context.session.begin():
            Beslissing( state='te_nemen', hypotheek_id=obj.id, 
                        datum_voorwaarde = obj.aanvraagdatum )   
            for step in super( RequestCompleteAction, self ).change_state( model_context, obj ):
                yield step

class HypoAbstractRole(object):
  described_by = schema.Column(camelot.types.Enumeration(constants.request_roles), nullable=False, index=True, default='borrower')
  rank = schema.Column(camelot.types.Enumeration(constants.request_ranks), nullable=False, default=1 )
  thru_date = schema.Column(sqlalchemy.types.Date(), nullable=False, default=end_of_times)
  
  related_constraints  =  property(lambda self:self.get_constraints())

class HypoApplicationRole(DualPerson, HypoAbstractRole):
    """De aanvrager van een hypotheek, di een combinatie van een natuurlijke persoon of rechtspersoon en nog
  wat bijkomende gegevens"""

    __tablename__ = 'hypo_application_role'
    __table_args__ = ( schema.CheckConstraint( 'natuurlijke_persoon is not null or rechtspersoon is not null', 
                                               name='hypo_application_role_persoon_fk'), )

    natuurlijke_persoon = orm.relationship(NatuurlijkePersoon)
    rechtspersoon  = orm.relationship(Rechtspersoon)

    application = ManyToOne('vfinance.model.hypo.hypotheek.Hypotheek', 
                            nullable=False,
                            backref=orm.backref('roles', cascade='all, delete, delete-orphan'))
    features = orm.relationship( 'HypoApplicationRoleFeature',
                                 backref = 'of',
                                 collection_class = orm.collections.attribute_mapped_collection('described_by'),
                                 cascade = 'all, delete-orphan' )

    def __setattr__(self, attr, value):
        if attr in bank_constants.role_feature_names:
            self.features[attr] = HypoApplicationRoleFeature(value=value,
                                                             described_by=attr)
        else:
            return super(HypoApplicationRole, self).__setattr__(attr, value)

    @property
    def from_date(self):
        if self.application:
            return self.application.aanvraagdatum

    @property
    def aanvraag_nummer(self):
        if self.application:
            return self.application.aanvraagnummer
        
    @property
    def aanvraag_gevraagd_bedrag(self):
        if self.application:
            return self.application.totaal_gevraagd_bedrag

    @property
    def aanvraag_state(self):
        if self.application:
            return self.application.state
                   
    @property
    def totaal_lasten(self):
        if self.natuurlijke_persoon:
            return self.natuurlijke_persoon.totaal_lasten
        return 0

    @property
    def totaal_inkomsten(self):
        if self.natuurlijke_persoon:
            return self.natuurlijke_persoon.totaal_inkomsten
        return 0
    
    @property
    def levensonderhoud(self):
        if self.natuurlijke_persoon:
            return self.natuurlijke_persoon.levensonderhoud
        return 0
    
    def __unicode__(self):
        return self.name

    class Admin( DualPerson.Admin ):
        verbose_name = _('Aanvraag rol')
        list_display =  ['described_by', 'rank', 'natuurlijke_persoon', 'rechtspersoon', 'thru_date', 'telefoon']
        form_display =  forms.Form(list_display + ['company_coverage_limit', 'person_coverage_limit'], columns=2)
        field_attributes = {'described_by': {'choices': constants.request_role_choices},
                            'thru_date': {'editable': lambda r:r.described_by=='guarantor'},
                            'company_coverage_limit': {'editable': lambda r:r.described_by=='borrower',
                                                       'delegate':delegates.FloatDelegate,
                                                       'name': 'Dekkingsgraad SSV maatschappij'},
                            'person_coverage_limit': {'editable': lambda r:r.described_by=='borrower',
                                                      'delegate':delegates.FloatDelegate,
                                                      'name': 'Dekkingsgraad SSV persoon'},
                            }
        
    @classmethod  
    def name_query(self, cls, alias):
        return sql.select([name_of_dual_person(alias)],
                           whereclause=(alias.id==cls.id))
      
HypoApplicationRole.name = ColumnProperty(lambda cls: HypoApplicationRole.name_query(cls, orm.aliased(HypoApplicationRole)),
                                          deferred=True)

class HypoApplicationRoleFeature(DualPersonFeature):

    __tablename__ = 'hypo_application_role_feature'

    of_id = schema.Column(sqlalchemy.types.Integer(), 
                          schema.ForeignKey(HypoApplicationRole.id,
                                            ondelete = 'cascade',
                                            onupdate = 'cascade' ),
                          nullable=False )

request_complete_action = RequestCompleteAction( _('Complete'), 'complete', ('draft', 'incomplete') )
request_incomplete_action = ChangeState( _('Incomplete'), 'incomplete', ('draft', 'canceled') )
request_canceled_action = ChangeState( _('Cancel'), 'canceled', ('draft', 'incomplete') ) 


class HypoApplicationMixin(DossierMixin):

    @property
    def checksum(self):
        numbers = (self.company_id, self.rank, self.nummer,)
        if None in numbers:
           return None
        return int('%03i%02i%05i'%numbers)%97 or 97
    
    @property
    def full_number(self):
        return '%03i-%02i-%05i-%02i'%(self.company_id or 0, self.rank or 0, self.nummer or 0, self.checksum or 0)

    @property
    def taal( self ):
        taal = 'nl'
        for role in self.get_roles_at(datetime.date.today(), 'borrower'):
            if role.taal:
              taal = role.taal
            break
        return taal

    def __unicode__(self):
        return self.full_number

functional_setting_prefix = 'agreed_functional_setting_'

class Hypotheek(AbstractAgreement, ConstrainedDocument, HypoApplicationMixin):
    """Het hypotheek document, van aanvraag tot goedkeuring"""
    
    kosten = {
      'aankoopprijs':'Aankoopprijs',
      'notariskosten_aankoop':'Notariskosten aankoopakte',
      'kosten_bouwwerken' : 'Bestek bouwwerken',
      'kosten_verzekering' :'Verzekeringskosten',
      'kosten_btw' : 'Te betalen btw',
      'kosten_architect' : 'Ereloon architect',
      'notariskosten_hypotheek' : 'Notariskosten hypotheek',
      'kosten_andere' : 'Andere kosten',
      'wederbelegingsvergoeding' : 'Wederbelegingsvergoeding',
      'handlichting' : 'Handlichting',
      'saldo_lopend_krediet' : 'Saldo over te nemen kredieten'
    }
    
    evaluaties = {
      'woonsparen':'Woonsparen'
    }
  
    using_options(tablename='hypo_hypotheek')
    #replaced with backref gevraagd_bedrag  =  OneToMany('vfinance.model.hypo.hypotheek.Bedrag', )
    kosten_andere  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    kosten_bouwwerken  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    
    company_id = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=default_company_id)
    aanvraagnummer = schema.Column(sqlalchemy.types.Integer(), nullable=False)
    rank = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=0)
    
    schattingskosten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    # replaced by backref lopend_krediet  =  OneToMany('vfinance.model.hypo.hypotheek.LopendKrediet')
    domiciliering  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    ontvangen_voorschot  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    #replaced by backref    bijkomende_waarborg  =  OneToMany('vfinance.model.hypo.hypotheek.BijkomendeWaarborgHypotheek')
    kosten_architect  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    #replaced by backref    gehypothekeerd_goed  =  OneToMany('vfinance.model.hypo.hypotheek.GoedAanvraag', )
    aanvraagdocument  =  schema.Column(camelot.types.File(upload_to=os.path.join('hypo.hypotheek', 'aanvraagdocument')), nullable=True)
    kosten_btw  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    eigen_middelen  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    woonsparen  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    dossier  =  OneToMany('vfinance.model.hypo.dossier.Dossier')
    notariskosten_aankoop  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    domiciliering_rekening  =  schema.Column(sqlalchemy.types.Unicode(15), nullable=True)
    aankoopprijs  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    beslissingen  =  OneToMany('vfinance.model.hypo.beslissing.Beslissing', )
    aktedatum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    verzekeringskosten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    wederbelegingsvergoeding  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    temp_copy_from_id  =  schema.Column(sqlalchemy.types.Integer(), name='temp_copy_from', nullable=True, index=True)
    temp_copy_from  =  ManyToOne('vfinance.model.hypo.hypotheek.Hypotheek', field=temp_copy_from_id)
    achterstal_rekening  =  schema.Column(sqlalchemy.types.Unicode(4), nullable=True)
    kosten_verzekering  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    #akte  =  OneToMany('vfinance.model.hypo.hypotheek.AkteAanvraag', )
    achterstal  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    state  =  schema.Column(sqlalchemy.types.Unicode(15), nullable=True, default=u'draft')
    waarborgen  =  property(lambda self:self.get_waarborgen())
    handlichting  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    #replaced with backref    ander_goed  =  OneToMany('vfinance.model.hypo.hypotheek.Goed', )
    notariskosten_hypotheek  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    correctie_levensonderhoud  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    wettelijk_kader  =  schema.Column(sqlalchemy.types.Unicode(15), nullable=True, default=u'wet4892')
    aanvraagdatum  =  schema.Column(sqlalchemy.types.Date(), nullable=False, default=datetime.date.today)
    beroepsinkomsten_bewezen  =  property(lambda self:self.get_beroepsinkomsten_bewezen())
    bijkomende_informatie = schema.Column(camelot.types.RichText)
    direct_debit_mandates = OneToMany('vfinance.model.bank.direct_debit.DirectDebitMandate')

    __table_args__ = ( schema.UniqueConstraint(company_id, aanvraagnummer, rank), )

    @property
    def nummer(self):
        return self.aanvraagnummer

    @property
    def note(self):
        """A string describing what should be done next to complete the agreement, None if the
        agreement is complete"""
        if not self.aanvraagdatum:
            return ugettext('Gelieve de aanvraagdatum in te vullen')
        if not self.aktedatum:
            return ugettext('Gelieve de aktedatum in te vullen')
        if self.aktedatum < self.aanvraagdatum:
            return ugettext('De aktedatum dient later dan de aanvraagdatum te zijn')
        if not len( self.gevraagd_bedrag ):
            return ugettext('Gelieve de gevraagde bedragen in te vullen')
        if not len( self.get_roles_at(self.aanvraagdatum, 'borrower') ):
            return ugettext('Gelieve de hypotheeknemers in te vullen')
        for direct_debit_mandate in self.direct_debit_mandates:
            if not direct_debit_mandate.is_valid():
                return ugettext('Invalid direct debit mandate')
    
    @property
    def borrower_1_name(self):
        borrowers = self.get_roles_at(self.aanvraagdatum, 'borrower')
        if len(borrowers) > 0:
            return borrowers[0].name
          
    @property
    def borrower_2_name(self):
        borrowers = self.get_roles_at(self.aanvraagdatum, 'borrower')
        if len(borrowers) > 1:
            return borrowers[1].name
  
    @property
    def name(self):
        return u', '.join([(a.name or u'') for a in self.get_roles_at(self.aanvraagdatum, 'borrower')])
      
    @property     
    def totaal_investering(self):
        return sum((getattr(self, kost) or 0) for kost in self.kosten.keys() )
    
    @property
    def totaal_te_financieren(self):
        return self.totaal_investering - (self.eigen_middelen or 0)
  
    @property
    def totaal_gevraagd_bedrag(self):
        return sum(b.bedrag or 0 for b in self.gevraagd_bedrag)
    
    @property
    def totaal_inkomsten(self):
        return sum(a.totaal_inkomsten or 0 for a in self.get_roles_at(self.aanvraagdatum, 'borrower'))

    @property
    def totaal_lasten(self):
        return sum(a.totaal_lasten or 0 for a in self.get_roles_at(self.aanvraagdatum, 'borrower'))
        
    @property
    def levensonderhoud(self):
        return sum(a.levensonderhoud or 0 for a in self.get_roles_at(self.aanvraagdatum, 'borrower'))
    
    @property
    def maandlast_lopend_krediet(self):
        return sum(lk.te_betalen_maandlast or 0 for lk  in self.lopend_krediet)

    @property
    def saldo_lopend_krediet(self):
        return sum(lk.over_te_nemen_saldo or 0 for lk  in self.lopend_krediet)

    @property
    def beroepsinkomsten_bewezen(self):
        """Return True als er enkel natuurlijke personen bij de aanvragers zitten en die hun beroepsinkomsten
        allemaal bewezen zijn.  Return False als er geen aanvragers zijn"""
        natuurlijke_persoon_bij_aanvragers = False
        for aanvrager in self.get_roles_at(self.aanvraagdatum, 'borrower'):
            if aanvrager.natuurlijke_persoon:
                natuurlijke_persoon_bij_aanvragers = True
                np = aanvrager.natuurlijke_persoon
                if np.beroepsinkomsten_bewezen!='loonfiche' and np.beroepsinkomsten_bewezen!='verklaring_op_eer':
                    return False
        return natuurlijke_persoon_bij_aanvragers

    def get_te_hypothekeren_goed_sum(self, field):
        query = sql.select( [sql.func.sum( getattr(TeHypothekerenGoed, field) )],
                            from_obj=Hypotheek.__table__.join(GoedAanvraag.__table__).join(TeHypothekerenGoed.__table__),
                            whereclause=Hypotheek.id==self.id,
                            group_by=Hypotheek.id)
        return orm.object_session(self).execute(query).scalar() or 0
      
    @property
    def gedwongen_verkoop(self):
        return self.get_te_hypothekeren_goed_sum('gedwongen_verkoop')
    
    @property
    def vrijwillige_verkoop(self):
        return self.get_te_hypothekeren_goed_sum('vrijwillige_verkoop')

    def get_bijkomende_waarborg_sum(self, field):
        query = sql.select( [sql.func.sum( getattr(BijkomendeWaarborg, field) )],
                            from_obj=Hypotheek.__table__.join(BijkomendeWaarborgHypotheek.__table__).join(BijkomendeWaarborg.__table__),
                            whereclause=Hypotheek.id==self.id,
                            group_by=Hypotheek.id)
        return orm.object_session(self).execute(query).scalar() or 0
      
    @property
    def waarborg_bijkomend_waarde(self):
        return self.get_bijkomende_waarborg_sum('waarde')
      
    def get_waarborg_sum(self, field):
        query = sql.select( [sql.func.sum( getattr(Waarborg, field) )],
                            from_obj=Hypotheek.__table__.join(GoedAanvraag.__table__).join(TeHypothekerenGoed.__table__).join(Waarborg.__table__),
                            whereclause=Hypotheek.id==self.id,
                            group_by=Hypotheek.id)
        return orm.object_session(self).execute(query).scalar() or 0

    @property
    def bestaande_inschrijvingen(self):
        return self.get_waarborg_sum('bedrag')
    
    @property
    def saldo_bestaande_inschrijvingen(self):
        return self.get_waarborg_sum('saldo')
    
    @classmethod
    def waarborg_bedrag( cls ):
        return sql.select( [sql.func.sum( Waarborg.bedrag ) ],
                           whereclause = Waarborg.te_hypothekeren_goed_id_id==TeHypothekerenGoed.id,
                           group_by = Waarborg.te_hypothekeren_goed_id_id ).label( 'waarborg_bedrag' )    

    @property
    def waarborgen_venale_verkoop(self):
        venale_verkoop = sql.select( [ sql.func.sum( greatest( TeHypothekerenGoed.venale_verkoopwaarde - 1.2 * sql.func.coalesce( self.waarborg_bedrag(),
                                                                                                                                   0.0 ),
                                                                0.0 ) ) ],
                                     from_obj = TeHypothekerenGoed.__table__.join( GoedAanvraag.__table__ ),
                                     whereclause= GoedAanvraag.hypotheek_id == (self.id or 0 ),
                                     group_by = GoedAanvraag.hypotheek_id )
        
        for row in orm.object_session( self ).execute( venale_verkoop ):
            return D(row[0]) or 0
        
        return 0
    
    @property
    def hypothecaire_waarborgen(self):
        venale_verkoop = sql.select( [ sql.func.sum( greatest( TeHypothekerenGoed.gedwongen_verkoop - 1.2 * sql.func.coalesce( self.waarborg_bedrag(),
                                                                                                                                  0.0 ),
                                                               0.0 ) ) ],
                                    from_obj = TeHypothekerenGoed.__table__.join( GoedAanvraag.__table__ ),
                                    whereclause= GoedAanvraag.hypotheek_id == (self.id or 0 ),
                                    group_by = GoedAanvraag.hypotheek_id )
       
        for row in orm.object_session( self ).execute( venale_verkoop ):
            return D(row[0]) or 0
       
        return 0
    
    @property
    def waarborgen(self):
        return self.hypothecaire_waarborgen + self.waarborg_bijkomend_waarde
    
    @property
    def handelsdoeleinden(self):        
        select = sql.select( [ Hypotheek.id, bool_or( TeHypothekerenGoed.bestemming == 'handelspand' ).label('handelspand') ],
                             from_obj = Hypotheek.__table__.join( GoedAanvraag.__table__ ).join( TeHypothekerenGoed.__table__ ),
                             group_by = Hypotheek.id,
                             whereclause = Hypotheek.id == self.id )
        for row in orm.object_session( self ).execute( select ):
            return row.handelspand or False
        
        return False

    def constraint_generator(self, passed):
        for c in ConstrainedDocument.constraint_generator(self, passed):
            yield c
        for aanvrager in self.get_roles_at(self.aanvraagdatum, 'borrower'):
            for c in aanvrager.constraint_generator(passed):
                yield c
        for goed_aanvraag in self.gehypothekeerd_goed:
            if goed_aanvraag.te_hypothekeren_goed:
                for c in goed_aanvraag.te_hypothekeren_goed.constraint_generator(passed):
                    yield c

    def button_copy_from(self):
        if not self.temp_copy_from:
            return True
        self.Admin(None, self.__class__).copy( self.temp_copy_from, self )
        return True

    def button_refresh(self):
        self.expire()

    def get_applied_functional_settings_at( self,
                                            application_date,
                                            functional_setting_group ):
        """
        Return a list with the appliceable functional settings within a group
        """
        functional_settings = []
        #
        # first look at the account or agreement level
        #
        for functional_setting in self.agreed_functional_settings:
            if constants.hypo_group_by_functional_setting[functional_setting.described_by] == functional_setting_group:
                functional_settings.append( functional_setting )
        return functional_settings

    # This code might need to move to the Loan Application Proxy eventually

    def get_related_object_for_field(self, name):
        if name.startswith(functional_setting_prefix):
            functional_setting_group = name[len(functional_setting_prefix):]
            for functional_setting in self.get_applied_functional_settings_at(self.aanvraagdatum, functional_setting_group):
                return functional_setting, 'described_by'
            return None, 'described_by'
        return None, None

    def __getattr__(self, name):
        related_obj, related_obj_name = self.get_related_object_for_field(name)
        if related_obj_name is not None:
            if related_obj is not None:
                return getattr(related_obj, related_obj_name)
            return None
        raise AttributeError(name)

    def __setattr__(self, name, value):
        related_obj, related_obj_name = self.get_related_object_for_field(name)
        if related_obj_name is not None:
            if related_obj is not None:
                if value is not None:
                    return setattr(related_obj, related_obj_name, value)
                else:
                    return self.agreed_functional_settings.remove(related_obj)
            else:
                return HypoApplicationFunctionalSettingAgreement(agreed_on=self,
                                                                 described_by=value)
        super(Hypotheek, self).__setattr__(name, value)

    class Admin(VfinanceAdmin):
      
        def __init__(self, app_admin, entity):
            VfinanceAdmin.__init__(self, app_admin, entity)
            self._hypo_functional_setting_choices = collections.defaultdict(list)
            for _number, name, group, _custom_clause, _exclusive in constants.hypo_functional_settings_by_group:
                self._hypo_functional_setting_choices[group].append((name, name))

        verbose_name = _('Hypotheek')
        verbose_name_plural = _('Hypotheken')
        form_size = (900,600)
        form_state = 'maximized'
        list_display =  ['state',
                         'full_number',
                         'borrower_1_name',
                         'borrower_2_name',
                         'totaal_gevraagd_bedrag',
                         'aktedatum'
                         ]
        list_filter = ['state', 'wettelijk_kader', list_filter.ComboBoxFilter('company_id')]
        list_search = ['roles.natuurlijke_persoon.name',
                       'roles.rechtspersoon.name']
        copy_exclude = ['state', 'dossier', 'beslissingen', 'related_constraints', 'akte', 'aanvraagnummer', 'id']
        copy_deep = { 'roles':{},
                      'lopend_krediet':{},
                      'gevraagd_bedrag':{},
                      'gehypothekeerd_goed':{},
                      'bijkomende_waarborg':{},
                      'ander_goed':{}, }
        form_actions =  [ CallMethod(_('Kopieer Aanvraag'), lambda o:o.button_copy_from(), ),
                          request_complete_action,
                          request_incomplete_action,
                          request_canceled_action,
                          CallMethod(  _('Refresh'), lambda o:o.button_refresh(), enabled=lambda o:(o is not None) and (o.id is not None)),
                          CreditApplicationVerification() ]
        form_display =  forms.Form( [ forms.WidgetOnlyForm('note'), 
                                      forms.TabForm([(_('Aanvragers'), forms.Form(['temp_copy_from','aanvraagdatum',
                                                                                   'company_id', 'aanvraagnummer',
                                                                                   'aktedatum', forms.Break(),
                                                                                   'wettelijk_kader', 'agreed_functional_setting_state_guarantee',
                                                                                   'aanvraagdocument', 'state',
                                                                                   'broker_relation', 'broker_agent',
                                                                                   'roles',], columns=2)),
                                                     (_('Lopende kredieten'), forms.Form(['lopend_krediet',])),
                                                     (_('Krediet'), forms.Form([forms.GroupBoxForm(_('Kosten'),['aankoopprijs','notariskosten_aankoop','kosten_bouwwerken','kosten_architect','kosten_btw','kosten_verzekering','notariskosten_hypotheek','kosten_andere','saldo_lopend_krediet','wederbelegingsvergoeding','handlichting',], columns=2),'totaal_investering','eigen_middelen','totaal_te_financieren','gevraagd_bedrag','domiciliering','domiciliering_rekening',], columns=2)),
                                                     (_('Waarborgen'), forms.Form(['gehypothekeerd_goed', 'bijkomende_waarborg'])), #'akte',])),
                                                     (_('Bijkomend'), forms.Form(['direct_debit_mandates','ander_goed', 'agreed_functional_settings', 'bijkomende_informatie',], columns=2)),
                                                     (_('Evaluatie'), forms.Form(['gedwongen_verkoop','bestaande_inschrijvingen','saldo_bestaande_inschrijvingen','hypothecaire_waarborgen','waarborg_bijkomend_waarde','waarborgen','beroepsinkomsten_bewezen','woonsparen','levensonderhoud','correctie_levensonderhoud','waarborg_bijkomend_waarde','ontvangen_voorschot','schattingskosten','verzekeringskosten','achterstal','achterstal_rekening',], columns=2)), #'beslissingen',])),
                                                     (_('Status'), forms.Form([forms.GroupBoxForm(_('Opmerkingen'),['related_constraints',]), 'dossier','rank'])),
                                                     ], position=forms.TabForm.WEST)
                                     ] )

        field_attributes = {'agreed_functional_settings': {'name': _('Settings')},
                            'agreed_functional_setting_state_guarantee': {'name': _('Gewestwaarborg')},
                            'full_number':{'editable':False, 'name':_('Aanvraag')},
                            'gevraagd_bedrag':{'editable':True, 'name':_('Gevraagde bedragen')},
                            'kosten_andere':{'editable':True, 'name':_('Andere kosten')},
                            'kosten_bouwwerken':{'editable':True, 'name':_('Bestek bouwwerken')},
                            'aanvraagnummer':{'editable':True, 'name':_('Aanvraagnummer'), 'default': nieuw_aanvraagnummer},
                            'schattingskosten':{'editable':True, 'name':_('Schattingskosten')},
                            'lopend_krediet':{'editable':True, 'name':_('Lopende kredieten')},
                            'domiciliering':{'editable':True, 'name':_('Terugbetaling met domiciliering')},
                            'ontvangen_voorschot':{'editable':True, 'name':_('Ontvangen voorschot')},
                            'bijkomende_waarborg':{'editable':True, 'name':_('Bijkomende waarborgen')},
                            'taal':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Taal')},
                            'kosten_architect':{'editable':True, 'name':_('Ereloon architect')},
                            'levensonderhoud':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Levensonderhoud')},
                            'borrower_1_name':{'editable':False, 'minimal_column_width':30, 'delegate':delegates.PlainTextDelegate, 'name':_('Eerste ontlener')},
                            'borrower_2_name':{'editable':False, 'minimal_column_width':30, 'delegate':delegates.PlainTextDelegate, 'name':_('Tweede ontlener')},
                            'gehypothekeerd_goed':{'editable':True, 'name':_('Te hypothekeren goeden')},
                            'aanvraagdocument':{'editable':True, 'name':_('Ondertekend aanvraagdocument')},
                            'kosten_btw':{'editable':True, 'name':_('Te betalen btw')},
                            'eigen_middelen':{'editable':True, 'name':_('Eigen middelen')},
                            'bestaande_inschrijvingen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Bestaande inschrijvingen')},
                            'saldo_lopend_krediet':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Over te nemen saldo lopende kredieten')},
                            'woonsparen':{'editable':True, 'name':_('Woonsparen')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam'), 'minimal_column_width':50},
                            'dossier':{'editable':True, 'name':_('Dossiers')},
                            'notariskosten_aankoop':{'editable':True, 'name':_('Notariskosten aankoopakte')},
                            'aanvrager':{'editable':True, 'name':_('Aanvragers')},
                            'waarborgen_venale_verkoop':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Waarborg bij vrijwillige verkoop')},
                            'domiciliering_rekening':{'editable':True, 'name':_('Bankrekening voor domiciliering')},
                            'aankoopprijs':{'editable':True, 'name':_('Aankoopprijs')},
                            'beslissingen':{'editable':True, 'name':_('Beslissingen')},
                            'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                            'totaal_gevraagd_bedrag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totaal gevraagd bedrag')},
                            'gedwongen_verkoop':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Waarde bij gedwongen verkoop')},
                            'aktedatum':{'editable':True, 'name':_('Voorziene datum akte')},
                            'verzekeringskosten':{'editable':True, 'name':_('Verzekeringskosten')},
                            'wederbelegingsvergoeding':{'editable':True, 'name':_('Wederbelegingsvergoeding')},
                            'totaal_lasten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totaal lasten')},
                            'handelsdoeleinden':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Bestemd voor handelsdoeleinden')},
                            'vrijwillige_verkoop':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Waarde bij vrijwillige verkoop')},
                            'hypothecaire_waarborgen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Hypothecaire waarborgen')},
                            'temp_copy_from':{'editable':True, 'name':_('Kopieer alles uit')},
                            'achterstal_rekening':{'editable':True, 'name':_('Rekening achterstal')},
                            'kosten_verzekering':{'editable':True, 'name':_('Verzekeringskosten')},
                            'akte':{'editable':True, 'name':_('Eerder verleden aktes')},
                            'maandlast_lopend_krediet':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Maandlast lopende kredieten')},
                            'achterstal':{'editable':True, 'name':_('Achterstal')},
                            'state':{'editable':False, 'name':_('Status'), 'choices':constants.hypotheek_states},
                            'totaal_investering':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totaal investering')},
                            'waarborgen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('In aanmerking te nemen waarborgen')},
                            'saldo_bestaande_inschrijvingen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Saldo bestaande inschrijvingen')},
                            'handlichting':{'editable':True, 'name':_('Handlichting')},
                            'ander_goed':{'editable':True, 'name':_('Andere goeden')},
                            'totaal_te_financieren':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Te financieren bedrag')},
                            'notariskosten_hypotheek':{'editable':True, 'name':_('Notariskosten hypotheek')},
                            'totaal_inkomsten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totaal inkomsten')},
                            'correctie_levensonderhoud':{'editable':True, 'name':_('Correctie Levensonderhoud')},
                            'waarborg_bijkomend_waarde':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Waarde bijkomende waarborgen')},
                            'wettelijk_kader':{'editable':True, 'name':_('Wettelijk kader'), 'choices':constants.wettelijke_kaders},
                            'makelaar':{'editable':True, 'name':_('Makelaar')},
                            'aanvraagdatum':{'editable':True, 'name':_('Datum van aanvraag')},
                            'beroepsinkomsten_bewezen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Beroepsinkomsten bewezen')},
                            'note':{'delegate':delegates.NoteDelegate},
                            'rank':{'editable':False},
                            'company_id':{'name': _('Maatschappij')},
                           }
        field_attributes.update(ConstrainedDocument.Admin.field_attributes)
        
        def get_field_attributes(self, field_name):
            field_attributes = VfinanceAdmin.get_field_attributes(self, field_name)
            if field_name.startswith(functional_setting_prefix):
                field_attributes['editable'] = lambda hypotheek:hypotheek.id is not None
                field_attributes['delegate'] = delegates.ComboBoxDelegate
                field_attributes['choices'] = self._hypo_functional_setting_choices[field_name[len(functional_setting_prefix):]]
            return field_attributes

        def get_query(self, *args, **kwargs):
            query = VfinanceAdmin.get_query(self, *args, **kwargs)
            query = query.options(orm.subqueryload('roles'))
            query = query.options(orm.undefer('roles.name'))
            query = query.options(orm.subqueryload('gevraagd_bedrag'))
            return query
          

class HypoApplicationFunctionalSettingAgreement(Entity):

    __tablename__ = 'hypo_application_functional_setting_agreement'

    agreed_on = ManyToOne(Hypotheek, 
                          nullable=False, ondelete='restrict', onupdate='cascade',
                          backref=orm.backref('agreed_functional_settings', cascade='all, delete, delete-orphan'))
    described_by = schema.Column(camelot.types.Enumeration(constants.hypo_functional_settings), nullable=False, default='direct_debit_batch_1')
    clause = schema.Column(camelot.types.RichText())

    class Admin(EntityAdmin):
        verbose_name = _('Loan Setting')
        verbose_name_plural = _('Loan Settings')
        list_display = ['described_by', 'clause']
        field_attributes = {'described_by':{'name':_('Description')},}
