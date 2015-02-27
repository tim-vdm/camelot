"""Indexen die gebruikt worden om leningen met variabele
rentevoeten aan te passen
"""
import csv
import datetime
from decimal import Decimal as D
import urllib

import sqlalchemy.types
from sqlalchemy import orm, schema

from camelot.core.orm import Entity, OneToMany, ManyToOne, using_options
from camelot.core.exception import UserException
from camelot.admin.action import Action
from camelot.admin.entity_admin import EntityAdmin
from camelot.admin.object_admin import ObjectAdmin
from camelot.view.controls import delegates
from camelot.view import forms, action_steps
from camelot.core.utils import ugettext_lazy as _
import camelot.types

from vfinance.admin.vfinanceadmin import VfinanceAdmin

from .constants import index_url_types

class Options( object ):
    
    def __init__( self ):
        self.from_url = False
        self.filename = None
        
    class Admin( ObjectAdmin ):
        list_display = ['from_url', 'filename']
        field_attributes = {'from_url':{'delegate':delegates.BoolDelegate,
                                        'editable':True},
                            'filename':{'delegate':delegates.LocalFileDelegate,
                                        'editable':lambda o:o.from_url==False}}
        
class Belgostat( csv.excel ):
    delimiter = ';'
    
class ReadIndex( Action ):
    
    verbose_name = _('Import history')
    
    def model_run( self, model_context ):
        options = Options()
        for index in model_context.get_selection():
            yield action_steps.ChangeObject( options )
            if options.from_url:
                lines = urllib.urlopen( index.url )
            else:
                lines = open( options.filename )
            reader = csv.reader( lines, dialect = Belgostat() )
            headers = None
            for i, row in enumerate(reader):
                if i==4:
                    headers = row
                elif i > 4:
                    from_date = datetime.date( *(int(c) for c in row[0].split('-')) )
                    for value,header in zip( row, headers ):
                        header_parts = header.split(' ')
                        if value and len(header_parts)>1 and header_parts[1] == 'jaar':
                            duration = int( header_parts[0] ) * 12
                            history = model_context.session.query( IndexHistory ).filter( IndexHistory.described_by == index,
                                                                                          IndexHistory.duration == duration,
                                                                                          IndexHistory.from_date == from_date ).first()
                            if not history:
                                history = IndexHistory( described_by = index,
                                                        duration = duration,
                                                        from_date = from_date )
                            history.value = D(value.replace(',','.'))
            yield action_steps.FlushSession( model_context.session )
                    
class IndexType(Entity):
    using_options(tablename='hypo_index_type')
    description = schema.Column(sqlalchemy.types.Unicode(200), nullable=True)
    name = schema.Column(sqlalchemy.types.Unicode(25), nullable=False)
    url = schema.Column(sqlalchemy.types.Unicode(255))
    url_described_by = schema.Column(camelot.types.Enumeration(index_url_types))
    history = OneToMany('vfinance.model.bank.index.IndexHistory', inverse='described_by')

    def get_interpolated_value( self, from_date, duration ):
        """Get the linear interpolated index value known at a specific date
        
        :param from_date: the latest date for which an index value can
            be taken
        :param duration: the number of months for which an index value should
            be taken.  if no value is found for a specific duration, the value
            is interpolated between the closest durations
        """
        history_query = orm.object_session( self ).query( IndexHistory )
        history_query = history_query.filter( IndexHistory.described_by == self )
        history_query = history_query.filter( IndexHistory.from_date <= from_date )
        history_query = history_query.order_by( IndexHistory.from_date.desc() )
        
        from_value = history_query.filter( IndexHistory.duration <= duration ).order_by( IndexHistory.duration.desc() ).first()
        thru_value = history_query.filter( IndexHistory.duration > duration ).order_by( IndexHistory.duration.asc() ).first()
        
        if from_value==None and thru_value==None:
            raise UserException(u'No known index %s at %s with duration %s'%(self, from_date, duration))
        if from_value == None:
            return thru_value.value
        if thru_value == None:
            return from_value.value
        delta_duration = D( duration - from_value.duration )
        from_to_thru_duration = D( thru_value.duration - from_value.duration )
        return from_value.value + (thru_value.value-from_value.value) * delta_duration / from_to_thru_duration
        
    def __unicode__(self):
        return self.name

    class Admin(VfinanceAdmin):
        verbose_name = _('Index Type')
        list_display =  ['name', 'description']
        form_display =  forms.Form([ 'name','description',
                                     'url','url_described_by', 
                                     'history', ] )
        form_actions = [ReadIndex()]
        field_attributes = {
                            'description':{'editable':True, 'name':_('Beschrijving')},
                            'name':{'editable':True, 'name':_('Type')},
                            'history':{'editable':True, 'name':_('Historiek')},
                           }

def index_volgens_terugbetaling_interval(jaarlijkse_index, terugbetaling_interval):
    return '%.4f'%((((1+D(jaarlijkse_index)/100)**(1/D(terugbetaling_interval)))-1)*100)
  
class IndexHistory(Entity):
    """De index op een bepaalde periode in de tijd"""
    using_options(tablename='hypo_index_historiek')
    from_date = schema.Column(sqlalchemy.types.Date(), nullable=False)
    value = schema.Column( sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False)
    duration  =  schema.Column(sqlalchemy.types.Integer())
    type_id  =  schema.Column(sqlalchemy.types.Integer(), name='type', nullable=False, index=True)
    described_by  =  ManyToOne('vfinance.model.bank.index.IndexType', field=type_id)
    
    @property
    def monthly_value(self):
        """De index voor dossiers met mensualiteiten"""
        if self.value != None:
            return index_volgens_terugbetaling_interval(self.value, 12)

    def __unicode__(self):
        if self.from_date and self.described_by and self.value:
            return u'%s from %s : %s'%( self.described_by.name, self.from_date, self.value)
        return ''

    class Admin(EntityAdmin):
        verbose_name = _('Index History')
        list_display =  ['from_date', 'duration', 'value', 'monthly_value']
        form_display =  forms.Form(list_display, columns=2)
        field_attributes = {
                            'value':{'editable':True, 'name':_('Index')},
                            'from_date':{'editable':True, 'name':_('Aanvangsdatum')},
                            'duration':{'delegage':delegates.MonthsDelegate},
                            'type':{'editable':True, 'name':_('Index type')},
                            'monthly_value':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Voor mensualiteiten')},
                           }
