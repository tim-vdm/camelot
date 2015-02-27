import os

import sqlalchemy.types
from sqlalchemy import schema, sql
from sqlalchemy.ext import hybrid

from camelot.core.orm import ( Entity, OneToMany, ManyToOne, 
                               using_options, has_field )
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _
import camelot.types

from constrained import ConstrainedDocument
from varia import PostcodeGemeente

from .persoon import persoon_fields, adres_form
from . import validation

from vfinance.admin.vfinanceadmin import VfinanceAdmin


def tax_id_background_color(organization):
    from camelot.view.art import ColorScheme
    valid = validation.tax_id(organization.ondernemingsnummer)
    if not valid:
        return ColorScheme.VALIDATION_ERROR

class RechtspersoonMock( object ):
    
    def __init__( self, name ):
        self.name = name

    def to_real( self ):
        rechtspersoon = Rechtspersoon()
        rechtspersoon.name = self.name
        return rechtspersoon

class Rechtspersoon(Entity, ConstrainedDocument, PostcodeGemeente):
    using_options(tablename='bank_rechtspersoon', order_by=['id'])
    id = schema.Column(sqlalchemy.types.Integer(), primary_key=True, nullable=False)
    actieve_producten  =  property(lambda self:self.get_actieve_producten())
    postcode  =  schema.Column(sqlalchemy.types.Unicode(24), nullable=True)
    zipcode = property(lambda self:self._postcode)
    vorm  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    vertegenwoordiger_id  = schema.Column(sqlalchemy.types.Integer(), name='vertegenwoordiger')
    vertegenwoordiger  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=vertegenwoordiger_id, backref='representing')
    representative = property(lambda self:self.vertegenwoordiger)
    taal  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False, default=unicode('nl'))
    email  =  schema.Column(sqlalchemy.types.Unicode(64), nullable=True)
    fax  =  schema.Column(sqlalchemy.types.Unicode(64), nullable=True)
    ondernemingsnummer  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=False)
    oprichtingsdatum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    
    def _get_oprichtingsdatum(self):
        return self.oprichtingsdatum
    
    def _set_oprichtingsdatum(self, value):
        self.oprichtingsdatum = value

    # needed to get values from dual person object
    # will probably never be used in this context
    # it made sense ... somewhat
    geboortedatum = property(_get_oprichtingsdatum, _set_oprichtingsdatum)
    gender = ''
    titel = ''
    geboorteplaats = ''
    nationaliteit = ''
    burgerlijke_staat = ''
    rookgedrag = False
    datum_overlijden = ''
    land_id = schema.Column(sqlalchemy.types.Integer(), name='land')
    land  =  ManyToOne('vfinance.model.bank.varia.Country_', field=land_id)
    country = property(lambda self:self.land)
    correspondentie_land_id = schema.Column(sqlalchemy.types.Integer(), name='correspondentie_land')
    correspondentie_land  =  ManyToOne('vfinance.model.bank.varia.Country_', field=correspondentie_land_id)    
    statuten  =  schema.Column(camelot.types.File(upload_to=os.path.join('bank.rechtspersoon', 'statuten')), nullable=True)
    jaarverslag  =  OneToMany('vfinance.model.bank.rechtspersoon.Jaarverslag')
    juridische_vorm  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    gemeente  =  schema.Column(sqlalchemy.types.Unicode(128), nullable=True)
    city = property(lambda self:self.gemeente)
    straat  =  schema.Column(sqlalchemy.types.Unicode(128), nullable=True)
    street = property(lambda self:self.straat)
    name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=False)
    short_name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=True)
    economische_eigenaar  =  OneToMany('vfinance.model.bank.rechtspersoon.EconomischeEigenaar', inverse='rechtspersoon_waarvan_eigenaar')
    eigendom_rechtspersoon  =  OneToMany('vfinance.model.bank.rechtspersoon.EconomischeEigenaar', inverse='rechtspersoon')
    activiteit  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=True)
    gsm  =  schema.Column(sqlalchemy.types.Unicode(64), nullable=True)
    mobile =  property(lambda self:self.gsm)
    telefoon  =  schema.Column(sqlalchemy.types.Unicode(64), nullable=True)
    phone = property(lambda self:self.telefoon)
    bestuurders  =  schema.Column(camelot.types.File(upload_to=os.path.join('bank.rechtspersoon', 'bestuurders')), nullable=True)
    origin  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    official_numbers = OneToMany('vfinance.model.bank.official_number.OfficialNumber')
    first_name = property(lambda self:self.vertegenwoordiger.first_name)
    last_name = property(lambda self:self.vertegenwoordiger.last_name)
    
    for field_name, field_type, type_args, field_kwargs in persoon_fields:
        has_field(field_name, field_type(*type_args), **field_kwargs)
    
    def __unicode__(self):
        return self.name
    
    auto_postcode = property(PostcodeGemeente._get_postcode, PostcodeGemeente._set_postcode)
    correspondentie_postcode = property(PostcodeGemeente._get_correspondentie_postcode, PostcodeGemeente._set_correspondentie_postcode)
    tax_number = schema.Column(sqlalchemy.types.Unicode(40), nullable=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    @hybrid.hybrid_property
    def tax_id(self):
        return self.ondernemingsnummer

    @tax_id.expression
    def tax_id(self):
        return sql.select([Rechtspersoon.ondernemingsnummer])

    @tax_id.setter
    def tax_id(self, tax_id):
        self.ondernemingsnummer = tax_id

    def constraints(self):
        yield (1, 'statuten', bool(self.statuten) )
        yield (2, 'benoeming bestuurders', bool(self.bestuurders) )

    @property
    def address_one_line( self ):
        return '%s %s %s'%( self.postcode, self.gemeente, self.straat )
    
    @property
    def full_name( self ):
        return self.name
    
    class Admin(VfinanceAdmin):
        verbose_name = _('Rechtspersoon')
        verbose_name_plural = _('Rechtspersonen')
        list_display =  ['id', 'name', 'vertegenwoordiger', 'ondernemingsnummer', 'telefoon', 'straat', 'auto_postcode', 'gemeente', 'land']
        form_state = 'maximized'
        form_display =  forms.Form([forms.TabForm([(_('Rechtspersoon'), forms.Form([
                                                    forms.HBoxForm([['name', 'short_name', 'juridische_vorm','statuten', 'gsm', 'fax', 'taal'], 
                                                                    ['ondernemingsnummer', 'tax_number','vorm','email','telefoon','activiteit','oprichtingsdatum',]]),
                                                                    'nota', 'related_constraints',])),
                                                   (_('Adres'), adres_form),
                                                   (_('Financieel'), ['jaarverslag', 'bank_accounts']),
                                                   (_('Bestuur'), forms.Form(['bestuurders','vertegenwoordiger','bestuurder','economische_eigenaar',])),
                                                   (_('Producten'), forms.Form(['onderschreven_kapcontract','gunstig_kapcontract','gekochte_kapbon',])),
                                                   (_('Gerelateerde'),  forms.Form(['bestuurde_rechtspersoon','eigendom_rechtspersoon',])),
                                                   (_('Tussenpersoon'), forms.TabForm([(_('Gegevens'), ['official_numbers',
                                                                                                        'commercial_relations_from',
                                                                                                        'supplier_accounts']),
                                                                                       ])),
                                                   #(_('Taken'), forms.Form(['taken'])),
                                                   (_('Extra'), forms.Form(['origin',])), 
                                                   ], position=forms.TabForm.WEST),])
        field_attributes = {
                            'bestuurder':{'editable':True, 'name':_('Bestuurders')},
                            'id':{'editable':False, 'name':_('Nummer')},
                            'official_numbers':{'editable':True, 'name':_('Erkenningsnummers')},
                            'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                            'actieve_producten':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Actieve producten')},
                            'gekochte_kapbon':{'editable':True, 'name':_('Gekochte kapitalisatiebonnen')},
                            'postcode':{'editable':True, 'name':_('Postcode')},
                            'correspondentie_postcode':{'editable':True, 'name':_('Correspondentie postcode')},
                            'commercial_relations_from':{'create_inline':True},
                            'auto_postcode':{'editable':True, 'name':_('Postcode')},
                            'vorm':{'editable':True, 'name':_('Vorm'), 'choices':[(None,''), 
                                                                                  ('andere', 'Andere'), 
                                                                                  ('BVBA', 'Bvba'), 
                                                                                  ('NV', 'Nv'),
                                                                                  ('VZW', 'Vzw'),
                                                                                  ('CVBA ', 'Cvba'),
                                                                                  ('VOF', 'Vof'),]},
                            'vertegenwoordiger':{'editable':True, 'name':_('Vertegenwoordiger')},
                            'bestuurde_rechtspersoon':{'editable':True, 'name':_('Bestuurde rechtspersoon')},
                            'taal':{'editable':True, 'name':_('Taal'), 'choices':[('fr', 'Frans'), ('nl', 'Nederlands')]},
                            'email':{'editable':True, 'name':_('E-Mail')},
                            'fax':{'editable':True, 'name':_('Fax')},
                            'gunstig_kapcontract':{'editable':True, 'name':_('Gunstige kapitalisatiecontracten')},
                            'ondernemingsnummer':{'name':_('Ondernemingsnummer'),
                                                  'tooltip':'eg : BE 0456.249.396',
                                                  'background_color': tax_id_background_color},
                            'onderschreven_kapcontract':{'editable':True, 'name':_('Onderschreven kapitalisatiecontracten')},
                            'oprichtingsdatum':{'editable':True, 'name':_('Oprichtingsdatum')},
                            'land':{'editable':True, 'name':_('Land')},
                            'statuten':{'editable':True, 'name':_('Laatst aangepaste statuten')},
                            'jaarverslag':{'editable':True, 'name':_('Jaarverslagen')},
                            'juridische_vorm':{'editable':True, 'name':_('Juridische vorm'), 'choices':[(None, ''), ('vrij_beroep', 'Vrij beroep'), ('vennootschap', 'Vennootschap'), ('eenmanszaak', 'Eenmanszaak')]},
                            'gemeente':{'editable':True, 'name':_('Gemeente')},
                            'straat':{'editable':True, 'name':_('Straat')},
                            'name':{'editable':True, 'name':_('Maatschappelijke naam')},
                            'short_name':{'editable':True, 'name':_('Verkorte naam')},
                            'economische_eigenaar':{'editable':True, 'name':_('Economische eigenaars')},
                            'full_name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'eigendom_rechtspersoon':{'editable':True, 'name':_('Rechtspersoon in eigendom')},
                            'activiteit':{'editable':True, 'name':_('Activiteit')},
                            'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                            'gsm':{'editable':True, 'name':_('Mobiel nummer')},
                            'telefoon':{'editable':True, 'name':_('Telefoon')},
                            'bestuurders':{'editable':True, 'name':_('Laatste benoeming bestuurders')},
                            'origin':{'editable':False},
                           }
        field_attributes.update(ConstrainedDocument.Admin.field_attributes)
#  natuurlijke_persoon_address_one_line
#  dual_field_getter
#  natuurlijke_persoon_name

class Jaarverslag(Entity):
    using_options(tablename='bank_jaarverslag_rechtspersoon')
    verslag  =  schema.Column(camelot.types.File(upload_to=os.path.join('bank.jaarverslag_rechtspersoon', 'verslag')), nullable=True)
    rechtspersoon_id = schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon')
    rechtspersoon  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id)
    datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    class Admin(EntityAdmin):
        list_display =  ['datum']
        form_display =  forms.Form(['datum','verslag',])
        field_attributes = {
                            'verslag':{'editable':True, 'name':_('Jaarverslag')},
                            'rechtspersoon':{'editable':True, 'name':_('Rechtspersoon')},
                            'datum':{'editable':True, 'name':_('Datum')},
                           }
#  natuurlijke_persoon_full_name
#  constrained_objects
#  natuurlijke_persoon


#  natuurlijke_persoon_address

