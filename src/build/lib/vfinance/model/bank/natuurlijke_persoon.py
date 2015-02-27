import os
from decimal import Decimal as D
import datetime
import phonenumbers
import re
import six

from stdnum.nl import bsn, vat as vat_nl
from stdnum.be import vat as vat_be

import sqlalchemy.types
from sqlalchemy.sql import and_
from sqlalchemy import sql, schema
from sqlalchemy.ext import hybrid

from camelot.core.orm import ( Entity, OneToMany, ManyToOne, 
                               using_options, has_field, ColumnProperty )
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.core.utils import ugettext, ugettext_lazy as _
from camelot.core.qt import QtGui
from camelot.admin.validator.entity_validator import EntityValidator
import camelot.types
from camelot.model.authentication import end_of_times

from constrained import ConstrainedDocument

from constants import sexes

from vfinance.admin.vfinanceadmin import VfinanceAdmin
from vfinance.model.bank.admin import EmailValidator
from vfinance.model.bank.constants import educational_levels

inkomsten = ['beroeps_inkomsten', 'vervangings_inkomsten', 'huur_inkomsten', 'kinderbijslag', 'alimentatie_inkomsten', 'toekomstige_inkomsten', 'andere_inkomsten']
lasten = ['huur_lasten', 'alimentatie_lasten', 'toekomstige_lasten', 'andere_lasten']
beroepen = ['arbeider','bediende','zelfstandige','gepensioneerde','werkzoekende','huisvrouw','arbeidsonbekwaam','bedrijfsleider']
ouders = ['overleden', 'levend_met_eigendom', 'levend_zonder_eigendom']
contracttypes = ['bepaalde_duur', 'onbepaalde_duur', 'interim']
contracttoestanden = ['lopend', 'proefperiode', 'ontslagnemend', 'ontslagen']

#
# https://en.wikipedia.org/wiki/Marital_status
#

burgerlijke_staten = [('o','ongehuwd'),('s','ongehuwd samenwonend'),('ows', 'ongehuwd wettelijk samenwonend'),('h','gehuwd'),('g','gescheiden'),('w','weduwe(naar)'),('f','feitelijk gescheiden')]
talen = [('fr','Frans'), ('nl','Nederlands')]

#
# person fields to use on the proposal and their default value
#
person_fields = [ 
    ('firstname', ''), 
    ('middle_name', ''), 
    ('lastname', ''), 
    ('language', ''), 
    ('gender', ''), 
    ('smoker', False), 
    ('social_security_number', ''), 
    ('birthdate', None),
    ('email', ''), 
    ('phone', ''), 
    ('zipcode', ''),
    ('city', ''), 
    ('street', ''),
    ('civilstate', None),
    ('occupation', ''),
    ('account_iban', ''), 
    ('account_bic', ''),
    ('identity_number', ''),
    ('identity_valid_until', end_of_times()), ]

class Title(Entity):
    using_options(tablename='res_partner_title')
    name =  schema.Column(sqlalchemy.types.Unicode(46), nullable=False)
    shortcut = schema.Column(sqlalchemy.types.Unicode(16), nullable=False)
    domain = schema.Column(sqlalchemy.types.Unicode(24), nullable=False)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    class Admin(EntityAdmin):
        verbose_name = _('Title')
        verbose_name_plural = _('Titles')
        list_display = ['name', 'shortcut', 'domain']
        
    def __unicode__(self):
        return self.name
    
def get_contact_titles(natuurlijke_persoon):
    titles = []
    for title in Title.query.filter_by(domain=u'contact').all():
        titles.append( (title.shortcut, _(title.name)) )
    return titles  + [(None,''), ('','')]

class NatuurlijkePersoonValidator(EntityValidator):

    def objectValidity(self, np):
        messages = super(NatuurlijkePersoonValidator,self).objectValidity(np)
        note = np.note
        if note:
            messages.append( note )
        return messages

from persoon import persoon_fields, adres_form
from varia import PostcodeGemeente

class CommercialRelationAdmin(EntityAdmin):
    list_display = ['type', 'from_rechtspersoon', 'number']
        
class HypotheekAdmin(EntityAdmin):
    verbose_name = _('Hypotheekaanvraag')
    verbose_name_plural = _('Hypotheekaanvragen')
    list_display = ['aanvraag_nummer', 'aanvraag_gevraagd_bedrag', 'aanvraag_state', 'dekkingsgraad_schuldsaldo', 'schuldsaldo_voorzien']
    form_display = ['hypotheek', 'dekkingsgraad_schuldsaldo', 'schuldsaldo_voorzien']
        
class FinancialAgreementAdmin(EntityAdmin):
    list_display = ['described_by', 'financial_agreement']
    form_display = list_display

def validate_ssn( ssn, country_code ):

    if not re.sub('[.\-/ ]', '', ssn).isdigit():
        return False, None, None
    if country_code == 'BE':    
        if not (ssn and len(ssn)==11):
            return False, None, None
        gender = {True:'v', False:'m'}[int(ssn[6:9])%2==0]
        if (97-int(ssn[:-2])%97)==int(ssn[-2:]):
            # born before 2000
            return True, datetime.date(year=1900+int(ssn[:2]), month=(int(ssn[2:4]) or 1), day=(int(ssn[4:6]) or 1)), gender
        elif (97-int('2'+ssn[:-2])%97)==int(ssn[-2:]):
            # born after 2000
            return True, datetime.date(year=2000+int(ssn[:2]), month=(int(ssn[2:4]) or 1), day=(int(ssn[4:6]) or 1)), gender
        return False, None, gender
    if country_code == 'NL':
        if len(ssn) == 9:
            sum_digits = sum( int(ssn[i])*(9-i) for i in range(8) )
            last_digit = sum_digits % 11
            if last_digit != 10:
                return last_digit==int(ssn[8]), None, None
        return False, None, None
    return True, None, None
        
def analyze_nationaal_nummer( natuurlijke_persoon ):
    """
    :param natuurlijke_persoon: object of type `NatuurlijkePersoon`    
    :return correct, birthdate, gender: birthdate and gender can only be trusted if correct, otherwise they
    might be None"""
    social_security_number = natuurlijke_persoon._nationaal_nummer
    if not social_security_number:
        return False, None, None
    
    if natuurlijke_persoon.nationaliteit == None:
        return True, None, None
    
    code = natuurlijke_persoon.nationaliteit.code
    ssn = ''.join([c for c in social_security_number if c.isdigit()])
    return validate_ssn(ssn, code)

def mod_97_checksum(number):
    return int(number[:-2]) % 97 == int(number[-2:])






def nationaal_nummer_background_color( natuurlijke_persoon ):
    from camelot.view.art import ColorScheme
    valid, _birthdate, _sex = analyze_nationaal_nummer( natuurlijke_persoon )
    if not valid:
        return ColorScheme.VALIDATION_ERROR


def get_language_choices(o=None):
    return [
        (u'nl', u'Nederlands'),
        (u'fr', u'Frans'),
        (u'it', u'Italiaans'),
        (None,  u'All'),
    ]

class AbstractNatuurlijkePersoon( object ):
    
    def age_at( self, application_date ):
        from vfinance.model.financial.interest import leap_days
        birth_date = self.birthdate
        if not birth_date or birth_date > application_date:
            return 0
        return ((application_date - birth_date).days - leap_days(birth_date, application_date))/365.0
    
class NatuurlijkePersoonMock( AbstractNatuurlijkePersoon ):
    def __init__( self, **kwargs ):
        for field, _default_value in person_fields:
            if field not in ['account_bic', 'account_iban']:
                setattr(self, field, kwargs.get(field, None))
    
    def to_real( self ):
        kwargs = {}
        for field, _default_value in person_fields:
            if field not in ['account_bic', 'account_iban']:
                kwargs[field] = getattr(self, field)
        natuurlijke_persoon = NatuurlijkePersoon( **kwargs )
        return natuurlijke_persoon    

class NatuurlijkePersoon(Entity, ConstrainedDocument, PostcodeGemeente, AbstractNatuurlijkePersoon):
    # convenience getter/setter methods
    # mainly for translations of member field variable names (NL to EN, cf. 'gemeente'=='city')
    def attrsetter(attr):
        def set_any(self, value):
            setattr(self, attr, value)
        return set_any

    def attrgetter(attr):
        def get_any(self):
            return getattr(self, attr)
        return get_any

    using_options(tablename='bank_natuurlijke_persoon', order_by=['id'])
    toekomstige_inkomsten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    toestand_moeder  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    aktiviteit_sinds  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    titel  =  schema.Column(sqlalchemy.types.Unicode(46))
    naam  =  schema.Column(sqlalchemy.types.Unicode(30), nullable=False)
    last_name = property(attrgetter('naam'), attrsetter('naam'))
    lastname = property(attrgetter('naam'), attrsetter('naam'))
    totaal_lasten  =  property(lambda self:self.get_totaal_lasten())
    levensonderhoud  =  property(lambda self:self.get_levensonderhoud())
    postcode_gemeente  =  property(lambda self:self.get_postcode_gemeente())
    zipcode_city = property(lambda self:self.postcode_gemeente)
    kinderen_ten_laste_onbekend  =  schema.Column(sqlalchemy.types.Integer(), nullable=True, default=0)
    kredietcentrale_url  =  property(lambda self:self.get_url_kredietcentrale())
    adres_sinds  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    postcode  =  schema.Column(sqlalchemy.types.Unicode(24), nullable=True)
    contract_type  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    kinderen_ten_laste  =  OneToMany('vfinance.model.bank.natuurlijke_persoon.KindTenLaste', inverse='lasthebber')
    partner  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon')

    identiteitskaart_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    identity_valid_until = property(attrgetter('identiteitskaart_datum'), attrsetter('identiteitskaart_datum'))
    kredietkaarten  =  schema.Column(sqlalchemy.types.Boolean(), nullable=False, default=False)
    feitelijk_rechtspersoon  =  schema.Column(sqlalchemy.types.Boolean(), nullable=False, default=False)
    telefoon_werk  =  schema.Column(sqlalchemy.types.Unicode(64), nullable=True)
    identiteitskaart_nummer  =  schema.Column(sqlalchemy.types.Unicode(30), nullable=True)
    identity_number = property(attrgetter('identiteitskaart_nummer'), attrsetter('identiteitskaart_nummer'))
    taal = schema.Column(sqlalchemy.types.Unicode(50), nullable=False, default=unicode('nl'))
    language = property(attrgetter('taal'), attrsetter('taal'))
    alimentatie_lasten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    andere_ten_laste  =  OneToMany('vfinance.model.bank.natuurlijke_persoon.AndereTenLaste', inverse='lasthebber')
    nationaliteit_id = schema.Column(sqlalchemy.types.Integer(), name='nationaliteit')
    nationaliteit  =  ManyToOne('vfinance.model.bank.varia.Country_', field=nationaliteit_id)
    nationality = property(attrgetter('nationaliteit'), attrsetter('nationaliteit'))

    alimentatie_inkomsten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    datum_verplaatsing  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    verplaats_naar_natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer, name='verplaats_naar_natuurlijke_persoon')
    verplaats_naar_natuurlijke_persoon  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=verplaats_naar_natuurlijke_persoon_id)
    
    werkgever_sinds  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    kinderbijslag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    actieve_producten  =  property(lambda self:self.get_actieve_producten())
    toekomstige_lasten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    andere_inkomsten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    email  =  schema.Column(sqlalchemy.types.Unicode(64), nullable=True)
    burgerlijke_staat_sinds  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    beroeps_inkomsten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    werkgever  =  schema.Column(sqlalchemy.types.Unicode(40), nullable=True)
    fax  =  schema.Column(sqlalchemy.types.Unicode(64), nullable=True)
    beroep  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    occupation = property(attrgetter('beroep'), attrsetter('beroep'))
    totaal_ten_laste  =  property(lambda self:self.get_totaal_ten_laste())
    aktiviteit  =  schema.Column(sqlalchemy.types.Unicode(40), nullable=True)
    geboorteplaats  =  schema.Column(sqlalchemy.types.Unicode(30), nullable=True)
    toestand_vader  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    #bestuurde_rechtspersoon  =  OneToMany('vfinance.model.bank.rechtspersoon.Bestuurder', inverse='natuurlijke_persoon') #replace by backref
    kredietcentrale_geverifieerd  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    contract_toestand  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    voornaam  =  schema.Column(sqlalchemy.types.Unicode(30), nullable=False)
    first_name = property(attrgetter('voornaam'), attrsetter('voornaam'))
    firstname = property(attrgetter('voornaam'), attrsetter('voornaam'))
    totaal_inkomsten  =  property(lambda self:self.get_totaal_inkomsten())
    middle_name = schema.Column( sqlalchemy.types.Unicode( 40 ) )
    vervangings_inkomsten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    beroepsinkomsten_bewijs  =  schema.Column(camelot.types.File(upload_to=os.path.join('bank.natuurlijke_persoon', 'beroepsinkomsten_bewijs')), nullable=True)
    address  =  property(lambda self:self.get_address())
    active  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    huur_lasten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    huur_inkomsten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    gemeente  =  schema.Column(sqlalchemy.types.Unicode(128), nullable=True)
    city = property(attrgetter('gemeente'), attrsetter('gemeente'))
    land_id = schema.Column(sqlalchemy.types.Integer(), name='land')
    land  =  ManyToOne('vfinance.model.bank.varia.Country_', field=land_id)
    country = property(attrgetter('land'), attrsetter('land'))
    correspondentie_land_id = schema.Column(sqlalchemy.types.Integer(), name='correspondentie_land')
    correspondentie_land  =  ManyToOne('vfinance.model.bank.varia.Country_', field=correspondentie_land_id) 
    nummer  =  property(lambda self:self.id)
    number = property(lambda self:self.nummer)
    straat  =  schema.Column(sqlalchemy.types.Unicode(128), nullable=True)
    street = property(attrgetter('straat'), attrsetter('straat'))
    _nationaal_nummer  =  schema.Column(sqlalchemy.types.Unicode(20), nullable=True, name = 'nationaal_nummer' )
    
    def get_nationaal_nummer( self ):
        return self._nationaal_nummer
    
    def set_nationaal_nummer( self, nationaal_nummer ):
        self._nationaal_nummer = nationaal_nummer
        correct, birthdate, gender = analyze_nationaal_nummer( self )
        if correct:
            if self.geboortedatum == None:
                self.geboortedatum = birthdate
            if self.gender == None:
                self.gender = gender
        
    nationaal_nummer = property( get_nationaal_nummer, set_nationaal_nummer )
    social_security_number = property(attrgetter('_nationaal_nummer'), set_nationaal_nummer)
    
    gender  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True, default=None )

    @hybrid.hybrid_property
    def sex(self):
        return self.gender

    @sex.expression
    def sex(self):
        return sql.select([NatuurlijkePersoon.gender])

    @sex.setter
    def sex(self, sex):
        self.gender = {'M': 'm', 'F': 'v'}[sex]

    kredietcentrale_verificatie  =  schema.Column(camelot.types.File(upload_to=os.path.join('bank.natuurlijke_persoon','kredietcentrale_verificatie')), nullable=True)
    functie_id = schema.Column(sqlalchemy.types.Integer(), name='functie')
    functie  =  ManyToOne('vfinance.model.bank.varia.Function_', field=functie_id)
    #eigendom_rechtspersoon  =  OneToMany('vfinance.model.bank.rechtspersoon.EconomischeEigenaar') # replace by backref
    geboortedatum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    birth_date =  property(attrgetter('geboortedatum'), attrsetter('geboortedatum'))

    @hybrid.hybrid_property
    def birthdate(self):
        return self.geboortedatum

    @birthdate.expression
    def birthdate(self):
        return sql.select([NatuurlijkePersoon.geboortedatum])

    @birthdate.setter
    def birthdate(self, birthdate):
        self.geboortedatum = birthdate

    btw_nummer  =  schema.Column(sqlalchemy.types.Unicode(15), nullable=True)
    huwelijkscontract  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    aankomstdatum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    andere_lasten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)
    identiteitskaart  =  schema.Column(camelot.types.File(upload_to=os.path.join('bank.natuurlijke_persoon', 'identiteitskaart')), nullable=True)
    gsm  =  schema.Column(sqlalchemy.types.Unicode(64), nullable=True)
    mobile =  property(lambda self:self.gsm)
    burgerlijke_staat  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    civil_state = property(attrgetter('burgerlijke_staat'), attrsetter('burgerlijke_staat'))
    civilstate = property(attrgetter('burgerlijke_staat'), attrsetter('burgerlijke_staat'))
    telefoon  =  schema.Column(sqlalchemy.types.Unicode(64), nullable=True)
    phone =  property(attrgetter('telefoon'), attrsetter('telefoon'))
    beroepsinkomsten_bewezen  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    datum_overlijden = schema.Column(sqlalchemy.types.Date(), nullable=True)
    akte_bekendheid_overlijden  =  schema.Column(camelot.types.File(upload_to=os.path.join('bank.natuurlijke_persoon', 'akte_bekendheid_overlijden')), nullable=True)
    rookgedrag = schema.Column(sqlalchemy.types.Boolean, default=False, nullable=False)
    smoker = property(attrgetter('rookgedrag'), attrsetter('rookgedrag'))
    educational_level = schema.Column(camelot.types.Enumeration(educational_levels), nullable=True)
    
    @property
    def smoking(self):
        return self.rookgedrag
    
    no_commercial_mailings = schema.Column(sqlalchemy.types.Boolean(), nullable=False, default=False)
    origin  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    
    for field_name, field_type, type_args, field_kwargs in persoon_fields:
        has_field(field_name, field_type(*type_args), **field_kwargs)
    
    def __unicode__(self):
        if None in (self.naam, self.voornaam):
            return u''
        return u'%s %s'%(self.naam, self.voornaam)

    auto_postcode = property(PostcodeGemeente._get_postcode, PostcodeGemeente._set_postcode)
    zipcode = property(attrgetter('postcode'), attrsetter('postcode'))
    correspondentie_postcode = property(PostcodeGemeente._get_correspondentie_postcode, PostcodeGemeente._set_correspondentie_postcode)
    tax_number = schema.Column(sqlalchemy.types.Unicode(40), nullable=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    def get_levensonderhoud(self):
      
        def levensonderhoud_staat(staat):
            if staat in ['s', 'h']:
                return D('834.14')/2
            return D('625.60')
        
        def levensonderhoud_ten_laste(aantal_personen):
            return aantal_personen * D('208.54')
        
        return levensonderhoud_staat(self.burgerlijke_staat) + levensonderhoud_ten_laste(self.totaal_ten_laste)
      
    def get_totaal_ten_laste(self):
        return len(self.kinderen_ten_laste) + len(self.andere_ten_laste) + (self.kinderen_ten_laste_onbekend or 0)
    
    def get_nummer(self):
        return self.id
    
    @property
    def note( self ):
        if self.naam and self.voornaam and self.geboortedatum:
            if NatuurlijkePersoon.query.filter(and_(NatuurlijkePersoon.naam.ilike(self.naam.strip()),
                                                    NatuurlijkePersoon.voornaam.ilike(self.voornaam.strip()),
                                                    NatuurlijkePersoon.geboortedatum==self.geboortedatum,
                                                    NatuurlijkePersoon.id!=self.id)).count():
                return ugettext( 'Een persoon met deze naam en geboortedatum bestaat reeds' )
        if self.nationaal_nummer:
            if NatuurlijkePersoon.query.filter(and_(NatuurlijkePersoon._nationaal_nummer==self.nationaal_nummer,
                                                    NatuurlijkePersoon.id!=self.id)).count():
                return ugettext( 'Een persoon met dit nationaal nummer bestaat reeds' )
            
            correct, birthdate, gender = analyze_nationaal_nummer( self )
            if correct:
                if birthdate not in (None, self.geboortedatum):
                    return ugettext( 'Geboortedatum en nationaal nummer komen niet overeen' )
                if gender not in (None, self.gender):
                    return ugettext( 'Geslacht en nationaal nummer komen niet overeen' )
                
    @classmethod
    def name_query( cls, np_columns ):
        return sql.functions.coalesce(np_columns.naam,'') + ' ' + sql.functions.coalesce(np_columns.voornaam,'')
    
    def name(self):
        return NatuurlijkePersoon.name_query( NatuurlijkePersoon )
    
    name = ColumnProperty( name, deferred = True )
    
    def name_search(self):
        return sql.expression.cast(self.naam + ' ' + self.voornaam + ' ' + self.naam, sqlalchemy.types.Unicode)
    
    name_search = ColumnProperty( name_search, deferred = True )
        
    @property
    def full_name( self ):
        return ' '.join( [ getattr( self, a ) for a in [ 'titel', 'naam', 'voornaam' ] if getattr( self, a ) ] )

    def get_address(self):
        return '%s\n%s %s'%(self.straat, self.postcode, self.gemeente)
    
    @property
    def address_one_line( self ):
        return '%s %s %s'%( self.postcode, self.gemeente, self.straat )
    
#    @transform_read( [ 'titel', 'naam', 'voornaam' ] )
#    def get_full_name(self, cr, uid, record):
#      return _join_record_(record)
#    
#    @transform_read( [ 'postcode', 'gemeente' ] )
#    def get_postcode_gemeente(self, cr, uid, record):
#      return _join_record_(record)
#    
    def get_totaal_inkomsten(self):
        return sum( [ink for ink in [getattr(self, i) for i in inkomsten] if ink])
    
    def get_totaal_lasten(self):
        return sum( [last for last in [getattr(self, l) for l in lasten] if last] )
    
    def get_url_kredietcentrale(self):
        return 'https://kcp.nbb.be/nbblogin/pub/nbblogin-capi.jsp?target=KCPIA0101'
  
    def constraints(self):
        yield (1, 'bewijs van beroepsinkomsten', bool(self.beroepsinkomsten_bewijs))
        yield (2, 'verificatie kredietcentrale', bool(self.kredietcentrale_verificatie))
        yield (3, 'copie identiteitskaart', bool(self.identiteitskaart))
        yield (4, 'nummer identiteitskaart', bool(self.identiteitskaart_nummer))
        
    class Admin(VfinanceAdmin):
        verbose_name = _('Natuurlijke persoon')
        verbose_name_plural = _('Natuurlijke personen')
        validator = NatuurlijkePersoonValidator
        # we use _postcode, to make the field importable
        list_display =  ['id', 'naam', 'voornaam', 'telefoon', 'geboortedatum', 'straat', 'auto_postcode', 'gemeente']
        list_search = ['name_search']
        form_state = 'maximized'
        form_display =  forms.TabForm([(_('Persoon'), forms.Form([forms.WidgetOnlyForm('note'), 
                                                                  forms.HBoxForm([['nationaliteit', 'nationaal_nummer', 'gender','titel','naam','voornaam', 'middle_name', 'identiteitskaart',
                                                                                   'geboortedatum','geboorteplaats', 'datum_overlijden', 'akte_bekendheid_overlijden'],
                                                                                  ['rookgedrag', 'educational_level', 'tax_number', 'identiteitskaart_nummer','identiteitskaart_datum',
                                                                                   'taal','aankomstdatum', ]]),
                                                                  'nota', 'related_constraints',])),
                                       (_('Familie'), forms.Form(['burgerlijke_staat', 'burgerlijke_staat_sinds', 'huwelijkscontract', 'partner', 'kinderen_ten_laste_onbekend','kinderen_ten_laste','andere_ten_laste',
                                                                  'totaal_ten_laste','toestand_moeder','toestand_vader',])),
                                       (_('Adres'), [forms.HBoxForm([['telefoon','telefoon_werk',], 
                                                                    ['gsm','email', 'no_commercial_mailings']])] + adres_form),
                                       (_('Beroep'), forms.Form(['beroep',
                                                                 forms.GroupBoxForm(_('Beroepsgegevens loontrekkende'),['functie',forms.HBoxForm([['werkgever','werkgever_sinds',], 
                                                                                                                                                  ['contract_type','contract_toestand',]]),]),
                                                                 forms.GroupBoxForm(_('Beroepsgegevens zelfstandige'),forms.HBoxForm([['aktiviteit','aktiviteit_sinds',],
                                                                                                                                      ['btw_nummer',]]))])),
                                       (_('Budget'), forms.Form([forms.GroupBoxForm(_('Maandelijkse inkomsten'),forms.HBoxForm([['beroeps_inkomsten','huur_inkomsten','alimentatie_inkomsten','andere_inkomsten','beroepsinkomsten_bewezen',], 
                                                                                                                                ['vervangings_inkomsten','kinderbijslag','toekomstige_inkomsten','totaal_inkomsten','beroepsinkomsten_bewijs',]])),
                                                                 forms.GroupBoxForm(_('Maandelijkse lasten'),forms.HBoxForm([['huur_lasten','andere_lasten','totaal_lasten',], 
                                                                                                                             ['alimentatie_lasten','toekomstige_lasten',]])),
                                                                 forms.GroupBoxForm(_('Financieel'),forms.Form(['kredietcentrale_url','kredietcentrale_verificatie', 
                                                                                                                'kredietkaarten','kredietcentrale_geverifieerd', 'bank_accounts'], columns=2)) 
                                                                 ], scrollbars=True)),
                                       #(_('Taken'), forms.Form(['taken'])), 
                                       (_('Extra'), forms.Form(['feitelijk_rechtspersoon','verplaats_naar_natuurlijke_persoon','datum_verplaatsing', 'origin'])),
                                       (_('Producten'), forms.TabForm([(_('Bonnen en contracten'), ['onderschreven_kapcontract','gunstig_kapcontract','gekochte_kapbon']),
                                                                       (_('Overeenkomsten'), ['financial_agreements']),
                                                                       ])),
                                       (_('Gerelateerde'), forms.Form(['bestuurde_rechtspersoon','eigendom_rechtspersoon','representing'])),
                                       (_('Tussenpersoon'), forms.Form(['commercial_relations_from', 'supplier_accounts'])),
                                       ], position=forms.TabForm.WEST)

        class CountryDependentValidator(QtGui.QValidator):

            def __init__(self, country=None, **kwargs):
                QtGui.QValidator.__init__(self)
                if country is not None:
                    self.country_code = country.code
                else:
                    self.country_code = None


        class NationalNumberValidator(CountryDependentValidator):

            def validate(self, qtext, position):
                ptext = six.text_type(qtext)
                ptext_clean = re.sub('[.\-/ ]', '', ptext)
                length = len(ptext_clean)

                if not ptext:
                    return(QtGui.QValidator.Acceptable, 1)

                #if ptext and length > 0 and position == len(ptext) and ptext[position-1].isalpha():
                #    return (QtGui.QValidator.Invalid, position)

                if self.country_code is not None:
                    valid = validate_ssn(ptext_clean, self.country_code)[0]
                    if self.country_code == 'BE':
                        #if length > 11:
                        #    return (QtGui.QValidator.Invalid, position)
                        if length == 11:
                            if not valid:
                                #return (QtGui.QValidator.Invalid, 11)
                                return (QtGui.QValidator.Intermediate, 11)
                            elif valid:
                                ptext = ptext_clean
                                ptext = ptext[:2] + '.' + ptext[2:4] + '.' + ptext[4:6] + '-' + ptext[6:9] + '.' + ptext[9:]
                                qtext.clear()
                                qtext.insert(0, ptext)
                                return (QtGui.QValidator.Acceptable, 15)
                        else:
                            return (QtGui.QValidator.Intermediate, position)
                    elif self.country_code == 'NL':
                        try:
                            if bsn.validate(ptext) and length == 9:
                                ptext = bsn.format(ptext)
                                qtext.clear()
                                qtext.insert(0, ptext)
                                return (QtGui.QValidator.Acceptable, len(ptext))
                            else:
                                return (QtGui.QValidator.Intermediate, position)
                        except:
                            return (QtGui.QValidator.Intermediate, position)
                    else:
                        return (QtGui.QValidator.Acceptable, position)


        class VATNumberValidator(QtGui.QValidator):

            def validate(self, qtext, position):
                ptext = six.text_type(qtext).upper()
                ptext_clean = re.sub('[.\-/ ]', '', ptext)
                length = len(ptext_clean)

                if not ptext:
                    return(QtGui.QValidator.Acceptable, 1)

                if ptext and ptext[0].isdigit():
                    qtext.insert(0, 'BE ')
                    return self.validate(qtext, len(qtext))

                if ptext.startswith('BE'):
                    #if position > 2 and ptext[position-1].isalpha():
                    #    return (QtGui.QValidator.Invalid, position)
                    #if length > 12:
                    #    return (QtGui.QValidator.Invalid, position)
                    try:
                        if vat_be.validate(ptext_clean):
                            if length == 12 and ptext[7] != '.':
                                qtext.clear()
                                qtext.insert(0, ptext_clean)
                                qtext.insert(2, ' ')
                                qtext.insert(7, '.')
                                qtext.insert(11, '.')
                                return (QtGui.QValidator.Acceptable, len(ptext) + 3)
                            elif len(qtext) == 15:
                                return (QtGui.QValidator.Acceptable, len(qtext))
                            else:
                                return (QtGui.QValidator.Intermediate, position)
                    except:
                        return (QtGui.QValidator.Intermediate, position)

                if ptext.startswith('NL'):
                    #if length > 14:
                    #    return (QtGui.QValidator.Invalid, position)
                    try:
                        if vat_nl.validate(ptext):
                            if length == 14 and ptext[7] != '.':
                                qtext.clear()
                                qtext.insert(0, ptext)
                                qtext.insert(2, ' ')
                                qtext.insert(7, '.')
                                qtext.insert(11, '.')
                                qtext.insert(14, ' ')
                                return (QtGui.QValidator.Acceptable, len(ptext) + 4)
                            elif len(qtext) == 18:
                                return (QtGui.QValidator.Acceptable, len(qtext))
                    except:
                        return (QtGui.QValidator.Intermediate, position)

                return (QtGui.QValidator.Intermediate, position)


        class IDCardNumberValidator(CountryDependentValidator):

            def validate(self, qtext, position):
                ptext = six.text_type(qtext).upper()
                ptext_clean = re.sub('[.\-/ ]', '', ptext).upper()
                length = len(ptext_clean)

                if not ptext:
                    return(QtGui.QValidator.Acceptable, 0)

                if self.country_code == 'BE':
                    #if ptext[position-1].isalpha():
                    #    return (QtGui.QValidator.Invalid, position)

                    if length == 12:
                        if mod_97_checksum(ptext_clean):
                            qtext.clear()
                            qtext.insert(0, ptext_clean)
                            qtext.insert(3, '-')
                            qtext.insert(11, '-')
                            return (QtGui.QValidator.Acceptable, len(qtext))
                        return (QtGui.QValidator.Intermediate, len(qtext))

                    #if length > 13:
                    #    return (QtGui.QValidator.Invalid, position)

                    return (QtGui.QValidator.Intermediate, position)

                elif self.country_code == 'NL':
                    #if position in range(1, 3) and not ptext[position-1].isalpha():
                    #    return (QtGui.QValidator.Invalid, position)
                    #elif position in range(3, 9) and not ptext[position-1].isalnum():
                    #    return (QtGui.QValidator.Invalid, position)
                    #elif position == 9 and not ptext[position-1].isdigit():
                    #    return (QtGui.QValidator.Invalid, position)

                    if length == 9:
                        if re.match('[A-Z]{2}[\dA-Z]{6}\d', ptext_clean):
                            qtext.clear()
                            qtext.insert(0, ptext_clean)
                            return (QtGui.QValidator.Acceptable, position)

                    if length == 12:
                        if mod_97_checksum(ptext_clean):
                            qtext.clear()
                            qtext.insert(0, ptext_clean)
                            qtext.insert(3, '-')
                            qtext.insert(11, '-')
                            return (QtGui.QValidator.Acceptable, len(qtext))
                        return (QtGui.QValidator.Intermediate, len(qtext))

                    #if length > 9:
                    #    return (QtGui.QValidator.Invalid, position)

                    return (QtGui.QValidator.Intermediate, position)

                else:
                    return (QtGui.QValidator.Acceptable, position)


        class TelephoneNumberValidator(QtGui.QValidator):

            def validate(self, qtext, position):
                ptext = six.text_type(qtext)
                if not ptext:
                    return (QtGui.QValidator.Acceptable, 0)
                try:
                    num  = phonenumbers.parse(ptext, 'BE')
                    if len(ptext) > 8:
                        clean_num = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                        qtext.clear()
                        qtext.insert(0, clean_num)
                        return (QtGui.QValidator.Acceptable, len(qtext))
                    return (QtGui.QValidator.Intermediate, len(qtext))
                except phonenumbers.phonenumberutil.NumberParseException:
                    try:
                        num = phonenumbers.parse(ptext, 'NL')
                        if len(ptext) > 8:
                            clean_num = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                            qtext.clear()
                            qtext.insert(0, clean_num)
                            return(QtGui.QValidator.Acceptable, len(qtext))
                        return (QtGui.QValidator.Intermediate, len(qtext))
                    except phonenumbers.phonenumberutil.NumberParseException:
                        return (QtGui.QValidator.Intermediate, position)



        field_attributes = {
                            'toekomstige_inkomsten':{'editable':True, 'name':_('Toekomstige inkomsten')},
                            'id':{'editable':False, 'name':_('Nummer')},
                            'origin':{'editable':True},
                            'financial_agreements':{'admin':FinancialAgreementAdmin, 'editable':False},
                            'toestand_moeder':{'editable':True, 'name':_('Toestand moeder'), 'choices':lambda o:[(None,'')] + [(ouder,ouder.capitalize()) for ouder in ouders]},
                            'aktiviteit_sinds':{'editable':True, 'name':_('Aktiviteit sinds')},
                            'titel':{'choices':get_contact_titles},
                            'note' : {'delegate':delegates.NoteDelegate, 'label':False},
                            'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                            'naam':{'editable':True, 'name':_('Naam')},
                            'gekochte_kapbon':{'editable':True, 'name':_('Gekochte kapitalisatiebonnen'), 'editable':False},
                            'totaal_lasten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totaal lasten')},
                            'levensonderhoud':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Levensonderhoud')},
                            'postcode_gemeente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Postcode Gemeente')},
                            'kinderen_ten_laste_onbekend':{'editable':True, 'name':_('Kinderen ten laste zonder gegevens')},
                            'kredietcentrale_url':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Ga naar kredietcentrale')},
                            'adres_sinds':{'editable':True, 'name':_('Huidig adres sinds')},
                            'postcode':{'editable':True, 'name':_('Postcode')},
                            'auto_postcode':{'editable':True, 'name':_('Postcode')},
                            'correspondentie_postcode':{'editable':True, 'name':_('Correspondentie postcode')},
                            'no_commercial_mailings':{'name':_('Geen commerciele mailing')},
                            'full_name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Aanspreking')},
                            'contract_type':{'editable':True, 'name':_('Contract type'), 'choices':lambda np:[(None,'')] + [(t,t.capitalize()) for t in contracttypes]},
                            'kinderen_ten_laste':{'editable':True, 'name':_('Kinderen ten laste')},
                            'verplaats_naar_natuurlijke_persoon':{'editable':True, 'name':_('Verplaatst naar natuurlijke persoon')},
                            'identiteitskaart_datum':{'editable':True, 'name':_('Identiteitskaart geldig tot')},
                            'kredietkaarten':{'editable':True, 'name':_('Bezit kredietkaarten')},
                            'feitelijk_rechtspersoon':{'editable':True, 'name':_('Te verplaatsen naar rechtspersoon')},
                            'taal':{'editable':True, 'name':_('Taal'), 'choices':get_language_choices},
                            'alimentatie_lasten':{'editable':True, 'name':_('Alimentatie lasten')},
                            'andere_ten_laste':{'editable':True, 'name':_('Andere personen ten laste')},
                            'nationaliteit':{'editable':True, 'name':_('Nationaliteit')},
                            'alimentatie_inkomsten':{'editable':True, 'name':_('Alimentatie inkomsten')},
                            'datum_verplaatsing':{'editable':True, 'name':_('Verplaatst op datum')},
                            'werkgever_sinds':{'editable':True, 'name':_('Werkgever sinds')},
                            'kinderbijslag':{'editable':True, 'name':_('Kinderbijslag')},
                            'actieve_producten':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Actieve producten')},
                            'toekomstige_lasten':{'editable':True, 'name':_('Toekomstige lasten')},
                            'andere_inkomsten':{'editable':True, 'name':_('Andere inkomsten')},
                            #'email':{'editable':True, 'name':_('E-Mail'), 'from_string': lambda s: ('email', s), 'delegate':delegates.VirtualAddressDelegate, 'address_type':'email'},
                            'email':{'editable':True, 'name':_('E-Mail'), 'validator':EmailValidator()},
                            'burgerlijke_staat_sinds':{'editable':True, 'name':_('Burgerlijke staat sinds')},
                            'beroeps_inkomsten':{'editable':True, 'name':_('Beroeps inkomsten')},
                            'werkgever':{'editable':True, 'name':_('Werkgever')},
                            'fax':{'editable':True, 'name':_('Fax')},
                            'beroep':{'editable':True, 'name':_('Beroep'), 'choices':lambda np:[(None,'')] + [(b,b.capitalize()) for b in beroepen]},
                            'totaal_ten_laste':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totaal aantal personen ten laste')},
                            'aktiviteit':{'editable':True, 'name':_('Aktiviteit')},
                            'geboorteplaats':{'editable':True, 'name':_('Geboorte plaats')},
                            'toestand_vader':{'editable':True, 'name':_('Toestand vader'), 'choices':lambda np:[(None,'')] + [(o, o.capitalize()) for o in ouders]},
                            'bestuurde_rechtspersoon':{'editable':True, 'name':_('Bestuurde rechtspersoon')},
                            'kredietcentrale_geverifieerd':{'editable':True, 'default':'niet_gedaan', 'name':_('Verificatie kredietcentrale'), 'choices':[('niet_gedaan', 'Niet geverifieerd'), ('geen_leningen', 'Geen leningen'), ('leningen', 'Leningen'), ('slechte_betaler', 'Slechte betaler')]},
                            'contract_toestand':{'editable':True, 'name':_('Contract toestand'), 'choices':lambda np:[(None,'')] + [(t,t.capitalize()) for t in contracttoestanden]},
                            'voornaam':{'editable':True, 'name':_('Voornaam')},
                            'totaal_inkomsten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totaal inkomsten')},
                            'vervangings_inkomsten':{'editable':True, 'name':_('Vervangings inkomsten')},
                            'beroepsinkomsten_bewijs':{'editable':True, 'name':_('Bewijs van beroepsinkomsten')},
                            'address':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                            'active':{'editable':True, 'name':_('Active')},
                            'onderschreven_kapcontract':{'editable':True, 'name':_('Onderschreven kapitalisatiecontracten'), 'editable':False},
                            'huur_lasten':{'editable':True, 'name':_('Huur lasten')},
                            'huur_inkomsten':{'editable':True, 'name':_('Huur inkomsten')},
                            'gemeente':{'editable':True, 'name':_('Gemeente')},
                            'land':{'editable':True, 'name':_('Land')},
                            'nummer':{'editable':False, 'delegate':delegates.IntegerDelegate, 'name':_('Nummer')},
                            'straat':{'editable':True, 'name':_('Straat')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'nationaal_nummer':{'editable':True, 'name':_('Nationaal nummer'), 'delegate':delegates.PlainTextDelegate, 'validator':lambda np:np.Admin.NationalNumberValidator(country=np.nationaliteit)},
                            'tax_number':{'editable':True, 'name':_('BTW nummer'), 'delegate':delegates.PlainTextDelegate, 'validator':VATNumberValidator()},
                            'btw_number':{'editable':True, 'name':_('BTW nummer'), 'delegate':delegates.PlainTextDelegate, 'validator':VATNumberValidator()},
                            'identiteitskaart_nummer':{'editable':True, 'name':_('Identiteitskaart'), 'delegate':delegates.PlainTextDelegate, 'validator':lambda np:np.Admin.IDCardNumberValidator(country=np.nationaliteit)},
                            'telefoon':{'editable':True, 'name':_('Telefoon thuis'), 'delegate':delegates.PlainTextDelegate, 'validator':TelephoneNumberValidator()},
                            'gsm':{'editable':True, 'name':_('Mobiel nummer'), 'delegate':delegates.PlainTextDelegate, 'validator':TelephoneNumberValidator()},
                            'telefoon_werk':{'editable':True, 'name':_('Telefoon werk'), 'delegate':delegates.PlainTextDelegate, 'validator':TelephoneNumberValidator()},
                            'gender':{'editable':True, 'name':_('Geslacht'), 'choices':sexes + [(None,'')]},
                            'kredietcentrale_verificatie':{'editable':True, 'name':_('Verificatie kredietcentrale')},
                            'gunstig_kapcontract':{'editable':True, 'name':_('Gunstige kapitalisatiecontracten'), 'editable':False},
                            'functie':{'editable':True, 'name':_('Functie')},
                            'eigendom_rechtspersoon':{'editable':True, 'name':_('Rechtspersoon in eigendom')},
                            'geboortedatum':{'editable':True, 'name':_('Geboortedatum')},
                            'huwelijkscontract':{'editable':True, 'default':'geen', 'name':_('Huwelijkscontract'), 'choices':[('geen', 'geen'), ('gemeenschap', 'gemeenschap van goederen'), ('scheiding', 'scheiding van goederen'), ('scheiding_aanwinsten', 'scheiding van goederen, gemeenschap van aanwinsten')]},
                            'aankomstdatum':{'editable':True, 'name':_('Datum aankomst Belgie')},
                            'andere_lasten':{'editable':True, 'name':_('Andere lasten')},
                            'identiteitskaart':{'editable':True, 'name':_('Identiteitskaart'), 'remove_original':True},
                            'burgerlijke_staat':{'editable':True, 'name':_('Burgerlijke staat'), 'choices':lambda np:[(None,'')] + [(k,v) for k,v in burgerlijke_staten]},
                            'beroepsinkomsten_bewezen':{'editable':True, 'default':'niet_bewezen', 'name':_('Beroepsinkomsten bewezen'), 'choices':[('niet_bewezen', 'Niet bewezen'), ('loonfiche', 'Loonfiche'), ('verklaring_op_eer', 'Verklaring op eer')]},
                            'commercial_relations_from':{'admin':CommercialRelationAdmin},
                            'middle_name':{'name':_('Voorvoegsel')},
                            'representing':{'name':_('Vertegenwoordiger van')},
                            'educational_level':{'name':_('Onderwijs'), 'editable':True},
                           }
        field_attributes.update(ConstrainedDocument.Admin.field_attributes)

        
#  natuurlijke_persoon_full_name

class KindTenLaste(Entity):
    using_options(tablename='bank_kind_ten_laste')
    kind_id = schema.Column(sqlalchemy.types.Integer(), name='kind')
    kind  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=kind_id)
    name  =  property(lambda self:self.get_name())
    lasthebber_id = schema.Column(sqlalchemy.types.Integer(), name='lasthebber')
    lasthebber  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=lasthebber_id)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    class Admin(EntityAdmin):
        list_display =  ['kind']
        form_display =  forms.Form(['kind',])
        field_attributes = {
                            'kind':{'editable':True, 'name':_('Kind')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'lasthebber':{'editable':True, 'name':_('Lasthebber')},
                           }
#  constrained_objects
#  natuurlijke_persoon_postcode_gemeente
#  _str_

class AndereTenLaste(Entity):
    using_options(tablename='bank_andere_ten_laste')
    persoon_id = schema.Column(sqlalchemy.types.Integer(), name='persoon')
    persoon  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=persoon_id)
    name  =  property(lambda self:self.get_name())
    lasthebber_id = schema.Column(sqlalchemy.types.Integer(), name='lasthebber')
    lasthebber  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=lasthebber_id)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    class Admin(EntityAdmin):
        list_display =  ['persoon']
        form_display =  forms.Form(['persoon',])
        field_attributes = {
                            'persoon':{'editable':True, 'name':_('Persoon')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'lasthebber':{'editable':True, 'name':_('Lasthebber')},
                           }
#  postcode_changed
#  natuurlijke_persoon_address
