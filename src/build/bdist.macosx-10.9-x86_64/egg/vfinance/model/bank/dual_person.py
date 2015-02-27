'''
Created on Apr 20, 2010

@author: tw55413
'''

import copy

from sqlalchemy import sql, schema, orm, types
from sqlalchemy.ext.declarative import declared_attr
import sqlalchemy.types

from camelot.view import forms
from camelot.admin import table
from camelot.view.controls import delegates
from camelot.admin.validator.entity_validator import EntityValidator
from camelot.core.orm import Entity, ManyToOne
from camelot.core.utils import ugettext_lazy as _
import camelot.types

from . import constants
from .natuurlijke_persoon import NatuurlijkePersoon
from .rechtspersoon import Rechtspersoon
from .direct_debit import AbstractBankAccount
from constrained import ConstrainedDocument
from vfinance.admin.vfinanceadmin import VfinanceAdmin

class PersoonValidator(EntityValidator):

    def validate_object(self, p):
        messages = super(PersoonValidator,self).validate_object(p)
        if (p.rechtspersoon is None) == (p.natuurlijke_persoon is None):
            messages.append('Gelieve ofwel een natuurlijke persoon, ofwel een rechtspersoon te selecteren')
        return messages
    
dual_fields = {'telefoon':'Telefoon', 'taal':'Taal', 'address_one_line':'Adres', 'full_name':'Naam', 'straat':'Straat', 'postcode':'Postcode', 'gemeente':'Gemeente', 'fax':'Fax'}


def name_of_dual_person(dual_person_class):
    """:return: a query for the name of a dual person"""
    from sqlalchemy.orm import aliased
    
    NP = aliased(NatuurlijkePersoon)
    RP = aliased(Rechtspersoon)

    np_name = sql.select( [NP.name_query( NP )] ).where( NP.id==dual_person_class.natuurlijke_persoon_id ).limit( 1 )
    rp_name = sql.select([RP.name] ).where( RP.id==dual_person_class.rechtspersoon_id).limit(1)
    return sql.functions.coalesce( np_name.as_scalar(), rp_name.as_scalar() )
        
class DualPerson( Entity, ConstrainedDocument):
    """Base class om een object de dualiteit 
    natuurlijke_persoon / rechtspersoon te geven, column and foreign key
    constraint are defined here. define the relationship on the subclass
    itself, to specify cascading, backrefs, join conditions without fuckup"""
    
    __abstract__ = True

    id = schema.Column(sqlalchemy.types.Integer(), primary_key=True)
    
    def __getattr__(self, attr):
        if attr in constants.role_feature_names:
            feature = self.features.get(attr)
            if feature is not None:
                return feature.value
            else:
                return None
        return super(DualPerson, self).__getattr__(attr)
        
    @declared_attr
    def rechtspersoon_id(self):
        return schema.Column('rechtspersoon', 
                             types.Integer(),
                             schema.ForeignKey(Rechtspersoon.id,
                                               onupdate='cascade',
                                               ondelete='restrict'),
                             nullable=True,
                             index=True)

    @property
    def organization_id(self):
        return self.rechtspersoon_id
    
    @declared_attr
    def natuurlijke_persoon_id(self):
        return schema.Column('natuurlijke_persoon',
                             types.Integer(),
                             schema.ForeignKey(NatuurlijkePersoon.id,
                                               onupdate='cascade',
                                               ondelete='restrict'),
                             nullable=True,
                             index=True)
    
    @property
    def person_id(self):
        return self.natuurlijke_persoon_id

    @classmethod
    def find_by_dual_person(cls, dual_person):
        """Find a dual person of this type that refers to the same underlying person as the dual person of another type"""
        if dual_person.organization_id:
            return cls.query.filter_by(rechtspersoon_id=dual_person.organization_id).first()
        elif dual_person.person_id:
            return cls.query.filter_by(natuurlijke_persoon_id=dual_person.person_id).first()
        return None

    @classmethod
    def find_or_create_by_dual_person(cls, dual_person):
        """Find a dual person of this type that refers to the same underlying person as the dual person of another type,
        if no such person is found create one, and return it"""
        p = cls.find_by_dual_person(dual_person)
        if not p:
            if not (dual_person.organization_id or dual_person.person_id):
                raise Exception('No rechtspersoon or natuurlijke persoon found')
            p = cls(rechtspersoon_id=dual_person.organization_id, natuurlijke_persoon_id=dual_person.person_id)
        return p
        
    @property
    def name( self ):
        if self.natuurlijke_persoon:
            return (self.natuurlijke_persoon.naam  or '') + ' ' + (self.natuurlijke_persoon.voornaam or '')
        if self.rechtspersoon:
            return self.rechtspersoon.name or ''
        
    @property
    def registration_number(self):
        """Rijksregister ingeval natuurlijke persoon, ondernemingsnummer in geval rechtspersoon
        """
        if self.natuurlijke_persoon:
            return self.natuurlijke_persoon.nationaal_nummer
        if self.rechtspersoon:
            return self.rechtspersoon.ondernemingsnummer
        
    def get_dual_field(self, field_name):
        if self.natuurlijke_persoon:
            return getattr(self.natuurlijke_persoon, field_name)
        if self.rechtspersoon:
            return getattr(self.rechtspersoon, field_name)
                    
    straat  =  property(lambda self:self.get_dual_field('straat'))
    street = property(lambda self:self.straat)
    taal  =  property(lambda self:self.get_dual_field('taal'))
    language = property(lambda self:self.taal)
    address_one_line  =  property(lambda self:self.get_dual_field('address_one_line'))
    gemeente  =  property(lambda self:self.get_dual_field('gemeente'))
    city = property(lambda self:self.gemeente)
    first_name  =  property(lambda self:self.get_dual_field('first_name'))
    last_name  =  property(lambda self:self.get_dual_field('last_name'))
    full_name  =  property(lambda self:self.get_dual_field('full_name'))
    gender =   property(lambda self:self.get_dual_field('gender'))
    titel = property(lambda self:self.get_dual_field('titel'))
    geboortedatum  =  property(lambda self:self.get_dual_field('geboortedatum'))
    geboorteplaats = property(lambda self:self.get_dual_field('geboorteplaats'))
    nationaliteit = property(lambda self:self.get_dual_field('nationaliteit'))
    burgerlijke_staat = property(lambda self:self.get_dual_field('burgerlijke_staat'))
    telefoon  =  property(lambda self:self.get_dual_field('telefoon'))
    mobile  =  property(lambda self:self.get_dual_field('mobile'))
    fax  =  property(lambda self:self.get_dual_field('fax'))
    email  =  property(lambda self:self.get_dual_field('email'))
    bank_accounts  =  property(lambda self:self.get_dual_field('bank_accounts'))
    phone = property(lambda self:self.telefoon)
    postcode  =  property(lambda self:self.get_dual_field('postcode'))
    zipcode = property(lambda self:self.postcode)
    land  =  property(lambda self:self.get_dual_field('land'))
    country = property(lambda self:self.land)
    tax_number = property(lambda self:self.get_dual_field('tax_number'))
    rookgedrag = property(lambda self:self.get_dual_field('rookgedrag'))
    datum_overlijden = property(lambda self:self.get_dual_field('datum_overlijden'))

    correspondentie_straat = property(lambda self:self.get_dual_field('correspondentie_straat'))
    correspondentie_postcode = property(lambda self:self.get_dual_field('_correspondentie_postcode'))
    correspondentie_gemeente = property(lambda self:self.get_dual_field('correspondentie_gemeente'))
    correspondentie_land = property(lambda self:self.get_dual_field('correspondentie_land'))
     
    mail_street = property(lambda self:self.get_dual_field('correspondentie_straat') or self.get_dual_field('straat'))
    mail_zipcode = property(lambda self:self.get_dual_field('_correspondentie_postcode') or self.get_dual_field('postcode'))
    mail_city = property(lambda self:self.get_dual_field('correspondentie_gemeente') or self.get_dual_field('gemeente'))
    mail_country = property(lambda self:self.get_dual_field('correspondentie_land') or self.get_dual_field('land'))
    
    def constraint_generator(self, passed):
        for c in ConstrainedDocument.constraint_generator(self, passed):
            yield c
        if self.natuurlijke_persoon:
            for c in self.natuurlijke_persoon.constraint_generator(passed):
                yield c
        if self.rechtspersoon:
            for c in self.rechtspersoon.constraint_generator(passed):
                yield c
        
    class Admin(VfinanceAdmin):
        validator = PersoonValidator
        list_display =  ['natuurlijke_persoon', 'rechtspersoon']
        list_search = ['name']
        form_display = forms.Form(list_display + ['straat', 'postcode', 'gemeente', 'telefoon'], columns=2)
        field_attributes = {
                            'gemeente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Gemeente')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'address_one_line':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Adres')},
                            'natuurlijke_persoon':{'editable':True, 'name':_('Natuurlijke persoon')},
                            'rechtspersoon':{'editable':True, 'name':_('Rechtspersoon')},
                            'straat':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Straat')},
                            'postcode':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Postcode')},
                            'full_name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                            'taal':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Taal')},
                            'telefoon':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Telefoon')},
                           }
        field_attributes.update(ConstrainedDocument.Admin.field_attributes)

        

#            return 

class DualPersonFeature(Entity):
    
    __abstract__ = True
    
    value = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=5),
                          nullable=False,
                          default=0)
    described_by = schema.Column(camelot.types.Enumeration(constants.role_features),
                                 nullable=False)

class BankAccount( DualPerson, AbstractBankAccount ):
    __tablename__ = 'bank_bank_account'

    natuurlijke_persoon = orm.relationship(NatuurlijkePersoon, backref='bank_accounts')
    rechtspersoon = orm.relationship(Rechtspersoon, backref='bank_accounts')
    
    Admin = AbstractBankAccount.Admin

class Bestuurder( DualPerson ):
    __tablename__='bank_bestuurder'
    natuurlijke_persoon_id = schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon')
    rechtspersoon_id = schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon')
    natuurlijke_persoon  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id, backref='bestuurde_rechtspersoon')
    rechtspersoon  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id, backref='bestuurde_rechtspersoon') 
    bestuurde_rechtspersoon_id = schema.Column(sqlalchemy.types.Integer(), name='bestuurde_rechtspersoon')
    bestuurde_rechtspersoon  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=bestuurde_rechtspersoon_id, backref='bestuurder')
    datum_mandaat  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    bruto_vergoeding  =  schema.Column(sqlalchemy.types.Float(precision=2), nullable=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    class Admin(DualPerson.Admin):
        form_display =  forms.Form(['datum_mandaat','bruto_vergoeding',forms.GroupBoxForm(_('Rechtspersoon'),['rechtspersoon',]),forms.GroupBoxForm(_('Natuurlijke persoon'),['natuurlijke_persoon',]),])
        field_attributes = copy.copy(DualPerson.Admin.field_attributes)
        field_attributes.update({
                            'bestuurde_rechtspersoon':{'editable':True, 'name':_('Bestuurde rechtspersoon')},
                            'datum_mandaat':{'editable':True, 'name':_('Mandaat sinds')},
                            'bruto_vergoeding':{'editable':True, 'name':_('Bruto vergoeding')},
                           })

class OnBestuurderAdmin(Bestuurder.Admin):
    list_display = ['bestuurde_rechtspersoon', 'datum_mandaat', 'bruto_vergoeding']
    form_display = list_display

NatuurlijkePersoon.Admin.field_attributes['bestuurde_rechtspersoon']['admin'] = OnBestuurderAdmin
Rechtspersoon.Admin.field_attributes['bestuurde_rechtspersoon']['admin'] = OnBestuurderAdmin

class EconomischeEigenaar(DualPerson):
    __tablename__='bank_economische_eigenaar'
    natuurlijke_persoon_id = schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon')
    rechtspersoon_id = schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon')
    natuurlijke_persoon  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id, backref='eigendom_rechtspersoon')
    rechtspersoon  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id, backref='eigendom_rechtspersoon') 
    rechtspersoon_waarvan_eigenaar_id = schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon_waarvan_eigenaar')
    rechtspersoon_waarvan_eigenaar  =  ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_waarvan_eigenaar_id)
    percentage_eigendom = schema.Column(sqlalchemy.types.Integer(), default=100)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    class Admin(DualPerson.Admin):
        list_display =  ['natuurlijke_persoon', 'rechtspersoon', 'percentage_eigendom']
        form_display =  forms.Form(['percentage_eigendom',forms.GroupBoxForm(_('Rechtspersoon'),['rechtspersoon',]),forms.GroupBoxForm(_('Natuurlijke persoon'),['natuurlijke_persoon',]),])
        field_attributes = copy.copy(DualPerson.Admin.field_attributes)
        field_attributes.update({
                            'rechtspersoon_waarvan_eigenaar':{'editable':True, 'name':_('Rechtspersoon waarvan eigenaar')},
                            'percentage_eigendom':{'editable':True, 'name':_('Percentage eigendom')},
                           })

class OnEconomischeEigenaarAdmin(EconomischeEigenaar.Admin):
    list_display = ['rechtspersoon_waarvan_eigenaar', 'percentage_eigendom']
    form_display = list_display

NatuurlijkePersoon.Admin.field_attributes['eigendom_rechtspersoon']['admin'] = OnEconomischeEigenaarAdmin
Rechtspersoon.Admin.field_attributes['eigendom_rechtspersoon']['admin'] = OnEconomischeEigenaarAdmin

class CommercialRelationValidator(PersoonValidator):
    pass

class CommercialRelation(DualPerson):
    __tablename__='bank_commercial_relation'
    # from_rechtspersoon is het kanaal
    from_rechtspersoon_id = schema.Column('to_rechtspersoon',
                                          sqlalchemy.types.Integer(),
                                          schema.ForeignKey(Rechtspersoon.id,
                                                            onupdate='cascade',
                                                            ondelete='restrict'),
                                          nullable=False)
    from_rechtspersoon  =  orm.relationship(Rechtspersoon,
                                            foreign_keys = (from_rechtspersoon_id,),
                                            backref='commercial_relations_to')
    # natuurlijke_persoon en rechspersoon zijn distributeurs
    type = schema.Column(camelot.types.Enumeration([(1, 'broker'), (2, 'agent')]), nullable=False, index=True, default='broker')
    number = schema.Column(sqlalchemy.types.Unicode(20))
    
    @property
    def supervisory_authority_number(self):
        if self.rechtspersoon:
            for official_number in self.rechtspersoon.official_numbers:
                if official_number.type=='cbfa':
                    return official_number.number
        return ''

    def __unicode__(self):
        if self.from_rechtspersoon and (self.rechtspersoon_id or self.natuurlijke_persoon_id) and self.type:
            return u'%s as %s for %s'%(unicode(self.name), self.type, unicode(self.from_rechtspersoon))
        return u'Unknown'
        
    class Admin(DualPerson.Admin):
        verbose_name = _('Commercial relation')
        verbose_name_plural = _('Commercial relations')
        list_display = table.Table( ['rechtspersoon', 'natuurlijke_persoon', 'type', 'from_rechtspersoon', 
                                     table.ColumnGroup( _('Numbers'), [ 'number', 'supervisory_authority_number'] ),
                                     table.ColumnGroup( _('Address'), [  'street', 'zipcode', 'city', 'phone', 'email', 'language'] ) ] )
        form_display = ['rechtspersoon', 'natuurlijke_persoon', 'type', 'from_rechtspersoon', 'number', 'available_packages']
        list_filter = ['type']
        validator = CommercialRelationValidator
        list_search = ['rechtspersoon.name', 'natuurlijke_persoon.naam']
        field_attributes = {'type' : {'name':_('This is a')},
                            'supervisory_authority_number' : {'editable':False},
                            'from_rechtspersoon':{'name':_('From'), 'minimal_column_width':30}, }
        
    class OnDualPersonAdmin(Admin):
        list_display = ['type', 'from_rechtspersoon', 'number']
        form_display = list_display + ['available_packages']

CommercialRelation.rechtspersoon  = orm.relationship(Rechtspersoon, 
                                                     backref='commercial_relations_from',
                                                     foreign_keys=(CommercialRelation.rechtspersoon_id,))

Rechtspersoon.Admin.field_attributes['commercial_relations_from']['admin'] = CommercialRelation.OnDualPersonAdmin

CommercialRelation.natuurlijke_persoon  = orm.relationship(NatuurlijkePersoon, 
                                                           backref='commercial_relations_from',
                                                           foreign_keys=(CommercialRelation.natuurlijke_persoon_id,))

NatuurlijkePersoon.Admin.field_attributes['commercial_relations_from']['admin'] = CommercialRelation.OnDualPersonAdmin


