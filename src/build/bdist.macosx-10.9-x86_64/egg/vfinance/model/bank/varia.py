import sqlalchemy.types
from sqlalchemy import schema

from camelot.core.orm import Entity, using_options
from camelot.admin.entity_admin import EntityAdmin
from camelot.core.utils import ugettext_lazy as _

class Postcodes(Entity):
    using_options(tablename='bank_postcodes')
    provincie  =  schema.Column(sqlalchemy.types.Unicode(30), nullable=False)
    priority  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    gewest  =  schema.Column(sqlalchemy.types.Unicode(30), nullable=False)
    postcode  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=False)
    gemeente  =  schema.Column(sqlalchemy.types.Unicode(128), nullable=False)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    class Admin(EntityAdmin):
        verbose_name = _('Postcode')
        verbose_name_plural = _('Postcodes')
        list_display =  ['postcode', 'gemeente', 'gewest', 'provincie']
        field_attributes = {
                            'provincie':{'editable':True, 'name':_('Provincie')},
                            'priority':{'editable':True, 'name':_('Prioriteit')},
                            'gewest':{'editable':True, 'name':_('Gewest')},
                            'postcode':{'editable':True, 'name':_('Postcode')},
                            'gemeente':{'editable':True, 'name':_('Gemeente')},
                           }
        
class PostcodeGemeente(object):
    """Abstract object to fill in the commune when a postcode was 
    entered, the concrete implementation should have a '_postcode'
    field and a 'gemeente' field"""
    
    def _get_postcode(self):
        return self.postcode
      
    def _set_postcode(self, postcode):
        self.postcode = postcode
        postcode_gemeente = Postcodes.query.filter_by(postcode=postcode).order_by('priority asc').limit(1).first()
        if postcode_gemeente:
            self.gemeente = postcode_gemeente.gemeente
    
    auto_postcode = property(_get_postcode, _set_postcode)
    
    def _get_correspondentie_postcode(self):
        return self._correspondentie_postcode
      
    def _set_correspondentie_postcode(self, postcode):
        self._correspondentie_postcode = postcode
        postcode_gemeente = Postcodes.query.filter_by(postcode=postcode).order_by('priority asc').limit(1).first()
        if postcode_gemeente:
            self.correspondentie_gemeente = postcode_gemeente.gemeente
    
    correspondentie_postcode = property(_get_correspondentie_postcode, _set_correspondentie_postcode) 
    
class Country_(Entity):
    using_options(tablename='res_country')
    name = schema.Column(sqlalchemy.types.Unicode(64), nullable=False)
    code = schema.Column(sqlalchemy.types.Unicode(2), nullable=False)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    create_uid = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    create_date = schema.Column(sqlalchemy.types.DateTime(), nullable=True)
    
    def __unicode__(self):
        return self.name
    
    def __str__(self):
        return self.name
      
    class Admin(EntityAdmin):
        verbose_name = _('Country')
        verbose_name_plural = _('Countries')
        list_display = ['code', 'name']
  
class Function_(Entity):
    using_options(tablename='res_partner_function')
    name = schema.Column(sqlalchemy.types.Unicode(64), nullable=False)
    code = schema.Column(sqlalchemy.types.Unicode(8), nullable=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    class Admin(EntityAdmin):
        verbose_name = _('Function')
        verbose_name_plural = _('Functions')
        list_display = ['code', 'name']
        
    def __unicode__(self):
        return self.name
