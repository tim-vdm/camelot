from decimal import Decimal as D
import logging

import sqlalchemy.types
from sqlalchemy import sql, schema

from camelot.core.orm import Entity, OneToMany, ManyToOne, using_options
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _

from vfinance.admin.vfinanceadmin import VfinanceAdmin

from hypotheek import Bedrag

doelen = Bedrag.doelen_description.keys()

logger = logging.getLogger('vfinance.model.hypo.rentevoeten')

def create_tarief_voorwaarden_evaluators():
  
  def quotiteit_klein(x, beslissing):
    logger.debug('quotiteit : %s'%beslissing.quotiteit)
    return beslissing.quotiteit < x
  
  def woonsparen(x, beslissing):
    return beslissing.hypotheek.woonsparen > 0
  
  def aflossing_klein(x, beslissing):
    return beslissing.terugbetalingsratio < x
  
  def quotiteit_groter(x, beslissing):
    logger.debug('quotiteit : %s'%beslissing.quotiteit)
    return beslissing.quotiteit > x
  
  def handelsdoeleinden(x, beslissing):
    return beslissing.hypotheek.handelsdoeleinden > 0
  
  def eerdere_rang(x, beslissing):
    return beslissing.hypotheek.bestaande_inschrijvingen > 0
  
  def inkomsten_niet_bewezen(x, beslissing):
    logger.debug('beroepsinkomsten_bewezen : %s'%beslissing.hypotheek.beroepsinkomsten_bewezen)
    return beslissing.hypotheek.beroepsinkomsten_bewezen==0
  
  def investeringskrediet(x, beslissing):
    return beslissing.wettelijk_kader == 'andere'
  
  return locals()

tarief_voorwaarden_evaluators = create_tarief_voorwaarden_evaluators()

class RenteTabel(Entity):
    using_options(tablename='hypo_rente_tabel')
    looptijd  =  schema.Column(sqlalchemy.types.Integer(), nullable=False, default=60)
    type_aflossing  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False, default=unicode('vast_kapitaal'))
    categorie_id  =  schema.Column(sqlalchemy.types.Integer(), name='categorie', nullable=False, index=True)
    categorie  =  ManyToOne('vfinance.model.hypo.rentevoeten.RenteTabelCategorie', field=categorie_id, backref='tabel')
    historiek  =  OneToMany('vfinance.model.hypo.rentevoeten.RenteHistoriek', inverse='tabel')
    name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=True)
    
    def __unicode__(self):
        return self.name or ''

    @classmethod
    def tabel_from_bedrag(cls, categorie, bedrag):
        """Zoek binnen een bepaalde categorie de passende tabel voor een bedrag, dwz de tabel met
        dezelfde type_aflossing en de laagste looptijd die hoger is dan de looptijd van het bedrag.
        
        als geen tabel gevonden met een looptijd hoger dan die van het bedrag, neem de tabel met
        de hoogste looptijd.
        
        @param bedrag: een browse object vh type gevraagd bedrag
        
        returns de id van de tabel on None als geen gevonden.
        
        """
        logger.debug('zoek tabel voor bedrag %s in categorie %s'%(bedrag.id, categorie.id))
        tabel = cls.query.filter( sql.and_( cls.categorie==categorie, cls.type_aflossing==bedrag.type_aflossing, cls.looptijd >= bedrag.looptijd) ).order_by(cls.looptijd).first()
        if tabel == None:
            tabel = cls.query.filter( sql.and_( cls.categorie==categorie, cls.type_aflossing=='alle', cls.looptijd >= bedrag.looptijd) ).order_by(cls.looptijd).first()
        if tabel == None:
            tabel = cls.query.filter( sql.and_( cls.categorie==categorie, cls.type_aflossing==bedrag.type_aflossing) ).order_by(cls.looptijd).first()
        if tabel == None:
            tabel = cls.query.filter( sql.and_( cls.categorie==categorie, cls.type_aflossing=='alle') ).order_by(cls.looptijd).first()        
        logger.debug('gevonden tabel is %s'%tabel)
        return tabel

    class Admin(EntityAdmin):
        list_display =  ['looptijd', 'type_aflossing']
        form_display =  forms.Form(['looptijd','type_aflossing','historiek',], columns=2)
        field_attributes = {'looptijd':{'delegate':delegates.MonthsDelegate, 'editable':True, 'name':_('Looptijd')},
                            'type_aflossing':{'editable':True, 'name':_('Aflossing'), 'choices':[('vast_kapitaal', 'Vast kapitaal'), ('vaste_aflossing', 'Vast bedrag'), ('bullet', 'Enkel intrest'), ('cummulatief', 'Alles op einddatum'), ('alle', 'Alle')]},
                            'categorie':{},
                            'categorie':{'editable':True, 'name':_('Categorie')},
                            'historiek':{'editable':True, 'name':_('Historiek')},
                            'name':{'editable':True, 'name':_('Naam')},
                           }

class RenteHistoriek(Entity):
    """De rente op een bepaalde periode in de tijd rentevoeten worden uitgedrukt in percent per maand"""
    using_options(tablename='hypo_rente_historiek')
    #replaced by backref vermeerderingen  =  OneToMany('vfinance.model.hypo.RenteWijziging', inverse='historiek_id_vermeerdering')
    basis  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=False, default=unicode('0'))
    tabel_id  =  schema.Column(sqlalchemy.types.Integer(), name='tabel', nullable=False, index=True)
    tabel  =  ManyToOne('vfinance.model.hypo.rentevoeten.RenteTabel', field=tabel_id)
    #replaced by backref verminderingen  =  OneToMany('vfinance.model.hypo.rentevoeten.RenteWijziging', inverse='historiek_id_vermindering')
    start_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=True)
    
    def get_basis_dec(self):
        if self.basis:
            return D(self.basis)
        
    def set_basis_dec(self, x):
        if x:
            self.basis = str(x)
        else:
            self.basis = None
        
    basis_dec = property( get_basis_dec, set_basis_dec )
        
    def __unicode__(self):
        return '%s from %s'%(self.basis, self.start_datum)

    @classmethod
    def historiek_from_datum(cls, tabel, datum):
        """Zoek binnen een bepaalde tabel de passende historiek voor een bedrag, dwz de
        eerste historiek die start na datum, return None als zo geen gevonden
        """
        logger.debug('zoek historiek in tabel %s voor datum %s'%(tabel, datum))
        return cls.query.filter( sql.and_(cls.tabel==tabel, cls.start_datum <= datum) ).order_by(cls.start_datum.desc()).first()

    class Admin(EntityAdmin):
        list_display =  ['start_datum', 'basis', 'name']
        form_display =  forms.Form(['start_datum','basis_dec','verminderingen','vermeerderingen',], columns=2)
        field_attributes = {
                            'vermeerderingen':{'editable':True, 'name':_('Rente vermeerderingen')},
                            'basis_dec':{'editable':True, 'name':_('Basis')},
                            'tabel':{},
                            'tabel':{'editable':True, 'name':_('Rente tabel')},
                            'verminderingen':{'editable':True, 'name':_('Rente verminderingen')},
                            'start_datum':{'editable':True, 'name':_('Aanvangsdatum')},
                            'name':{'editable':True, 'name':_('Naam')},
                           }
#  add_variabiliteit_historiek_modaliteiten
variabiliteit_historiek_modaliteiten = [('referentie_index', 'Referentie index'), ('minimale_afwijking', 'Minimale afwijking'), ('maximale_stijging', 'Maximale stijging'), ('maximale_daling', 'Maximale daling'), ('maximale_spaar_ristorno', 'Maximale spaar ristorno'), ('maximale_product_ristorno', 'Maximale ristorno gebonden producten'), ('maximale_conjunctuur_ristorno', 'Maximale conjunctuur ristorno')]
tarief_voorwaarden = [('quotiteit_klein', 'Quotitiet < x% verkoopwaarde'), ('woonsparen', 'Woonsparen'), ('aflossing_klein', 'Maandelijkse aflossing < x% maandinkomen'), ('quotiteit_groter', 'Quotitiet > x% verkoopwaarde'), ('handelsdoeleinden', 'Gebouw voor handelsdoeleinden'), ('eerdere_rang', 'Hypotheek in tweede rang'), ('inkomsten_niet_bewezen', 'Beroepsinkomsten niet bewezen'), ('investeringskrediet', 'Investeringskrediet')]

class RenteWijziging(Entity):
    using_options(tablename='hypo_rente_wijziging')
    voorwaarde  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=True)
    historiek_id_vermindering_id  =  schema.Column(sqlalchemy.types.Integer(), name='historiek_id_vermindering', nullable=True, index=True)
    historiek_id_vermindering  =  ManyToOne('vfinance.model.hypo.rentevoeten.RenteHistoriek', field=historiek_id_vermindering_id, backref='verminderingen')
    wijziging  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=False)
    x  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    historiek_id_vermeerdering_id  =  schema.Column(sqlalchemy.types.Integer(), name='historiek_id_vermeerdering', nullable=True, index=True)
    historiek_id_vermeerdering  =  ManyToOne('vfinance.model.hypo.rentevoeten.RenteHistoriek', field=historiek_id_vermeerdering_id, backref='vermeerderingen')
    
    def __unicode__(self):
        return self.name

    class Admin(EntityAdmin):
        list_display =  ['voorwaarde', 'x', 'wijziging']
        form_display =  forms.Form(['voorwaarde','x','wijziging',], columns=2)
        field_attributes = {
                            'voorwaarde':{'editable':True, 'name':_('Voorwaarde'), 'choices':[('quotiteit_klein', 'Quotitiet < x% verkoopwaarde'), ('woonsparen', 'Woonsparen'), ('aflossing_klein', 'Maandelijkse aflossing < x% maandinkomen'), ('quotiteit_groter', 'Quotitiet > x% verkoopwaarde'), ('handelsdoeleinden', 'Gebouw voor handelsdoeleinden'), ('eerdere_rang', 'Hypotheek in tweede rang'), ('inkomsten_niet_bewezen', 'Beroepsinkomsten niet bewezen'), ('investeringskrediet', 'Investeringskrediet')]},
                            'name':{'editable':True, 'name':_('Naam')},
                            'historiek_id_vermindering':{},
                            'historiek_id_vermindering':{'editable':True, 'name':_('Historiek')},
                            'wijziging':{'editable':True, 'name':_('Wijziging')},
                            'x':{'editable':True, 'name':_('x')},
                            'historiek_id_vermeerdering':{},
                            'historiek_id_vermeerdering':{'editable':True, 'name':_('Historiek')},
                           }
#  create_tarief_voorwaarden_evaluators
        
class RenteTabelCategorie(Entity):
    """Een categorie van rentetabellen bevat rentetabellen met een verschillende
  aanvangsdatum, maar met een zelfde toepassingsgebied
  """
    using_options(tablename='hypo_rente_tabel_categorie')
    doel_aankoop_gebouw_registratie  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_herfinanciering  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_nieuwbouw  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    #replaced by backref tabel  =  OneToMany('vfinance.model.hypo.rentevoeten.RenteTabel', inverse='categorie')
    name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=False)
    doel_centralisatie  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_aankoop_terrein  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_handelszaak  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_aankoop_gebouw_btw  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_overbrugging  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_renovatie  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    doel_behoud  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    
    @property
    def description(self):
        return ', '.join([doel for doel in doelen if getattr(self, doel)])
    
    def __unicode__(self):
        return self.name

    @classmethod
    def categorie_from_bedrag(cls, bedrag):
        """Zoek de categorie die het best past bij een bepaald bedrag
        @param bedrag: een browse object vh type gevraagd bedrag
        """
        logger.debug('zoek categorie voor bedrag %s'%bedrag.id)
        matches = {0:None}
        for categorie in cls.query.all():
            match = reduce(lambda x,y:x + (getattr(categorie,y)==True and getattr(bedrag,y)==True), doelen, 0)
            matches[match] = categorie
            logger.debug('categorie %s match=%s'%(categorie, match))
        highest_match = max(matches.keys())
        if highest_match < 1:
            #logger.warn('geen rente categorie gevonden voor gevraagd bedrag %i gevonden'%bedrag._id)
            return None
        else:
            logger.debug('categorie is %s'%matches[highest_match])
            return matches[highest_match]

    class Admin(VfinanceAdmin):
        verbose_name = _('Rente Tabel Categorie')
        verbose_name_plural = _('Rente Tabel Categorieen')
        list_display =  ['name', 'description']
        form_display =  forms.Form(['name',
                                    forms.GroupBoxForm(_('Doelen'),['doel_aankoop_terrein','doel_aankoop_gebouw_btw','doel_aankoop_gebouw_registratie','doel_nieuwbouw','doel_renovatie','doel_herfinanciering','doel_overbrugging','doel_centralisatie','doel_behoud',], columns=2),
                                    'tabel',], columns=2)
        field_attributes = {
                            'doel_aankoop_gebouw_registratie':{'editable':True, 'name':_('Aankoop gebouw met Registratierechten')},
                            'description':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Beschrijving')},
                            'doel_herfinanciering':{'editable':True, 'name':_('Herfinanciering')},
                            'doel_nieuwbouw':{'editable':True, 'name':_('Nieuwbouw')},
                            'tabel':{'editable':True, 'name':_('Tabellen')},
                            'name':{'editable':True, 'name':_('Naam')},
                            'doel_centralisatie':{'editable':True, 'name':_('Centralisatie')},
                            'doel_aankoop_terrein':{'editable':True, 'name':_('Aankoop terrein')},
                            'doel_handelszaak':{'editable':True, 'name':_('Overname handelszaak')},
                            'doel_aankoop_gebouw_btw':{'editable':True, 'name':_('Aankoop gebouw met BTW')},
                            'doel_overbrugging':{'editable':True, 'name':_('Overbruggingskrediet')},
                            'doel_renovatie':{'editable':True, 'name':_('Renovatie')},
                            'doel_behoud':{'editable':True, 'name':_('Behoud onroerend patrimonium')},
                           }
#  tarief_voorwaarden_evaluators
#  add_variabiliteit_type_modaliteiten
variabiliteit_type_modaliteiten = [('eerste_herziening', 'Eerste herziening na (maanden)'), ('volgende_herzieningen', 'Daarna herzieningen om de (maanden)'), ('eerste_herziening_ristorno', 'Eerste herziening ristorno na (maanden)'), ('volgende_herzieningen_ristorno', 'Daarna herzieningen ristorno om de (maanden)')]

