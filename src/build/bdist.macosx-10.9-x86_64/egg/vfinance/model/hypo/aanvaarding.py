import os
from datetime import datetime

import sqlalchemy.types
from sqlalchemy import orm, schema, sql

from camelot.core.orm import Entity, ManyToOne, using_options
from camelot.view import forms
from camelot.core.orm import transaction
from camelot.admin.action import CallMethod, list_filter
from camelot.core.utils import ugettext_lazy as _
import camelot.types

from .notification.aanvaardingsbrief import AanvaardingsBrief
from .notification.mortgage_table import MortgageTable
from .beslissing import Beslissing, nieuw_goedgekeurd_bedrag_clause, GoedgekeurdBedrag
from .hypotheek import Bedrag, HypoApplicationMixin
from vfinance.admin.vfinanceadmin import VfinanceAdmin

class Aanvaarding(Entity, HypoApplicationMixin):
    """
    Eenmaal een beslissing genomen wordt, wordt een aanvaardingsbrief opgestuurd, die ondertekend dient
    terug te komen
    """    
    using_options(tablename='hypo_aanvaarding')
    beslissing_id  =  schema.Column(sqlalchemy.types.Integer(), name='beslissing', nullable=False, index=True)
    beslissing  =  ManyToOne(Beslissing, field=beslissing_id)
    datum_verstuurd  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False)
    aanvaardingsbrief  =  schema.Column(camelot.types.File(upload_to=os.path.join('hypo.aanvaarding', 'aanvaardingsbrief')), nullable=True)
    datum_ontvangst  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    def __unicode__(self):
        if self.beslissing:
            return unicode(self.beslissing)
        return u''

    @property
    def company_id(self):
        if self.beslissing is not None:
            return self.beslissing.company_id

    @property
    def nummer(self):
        if self.beslissing is not None:
            return self.beslissing.nummer
        
    @property
    def rank(self):
        if self.beslissing is not None:
            return self.beslissing.rank

    @property
    def borrower_1_name(self):
        if self.beslissing is not None:
            return self.beslissing.borrower_1_name
                           
    @property
    def borrower_2_name(self):
        if self.beslissing is not None:
            return self.beslissing.borrower_2_name
    
    @transaction
    def button_cancel(self):
        self.state = 'canceled'
        return True
        
    @transaction
    def button_send(self):
        self.send(datetime.today())
    
    def send(self, at):
        self.datum_verstuurd = at
        self.state = 'send'
        return True
        
    @transaction
    def button_received(self):
        self.receive(datetime.today()) # Incorrect
        
    def receive(self, at):
        from akte import Akte
        self.datum_ontvangst = at 
        self.state = 'received'
        return Akte(beslissing = self.beslissing, state = 'pending')

    class Admin(VfinanceAdmin):
        verbose_name = _('Aanvaardingsbrief')
        verbose_name_plural = _('Aanvaardingsbrieven')
        list_display =  ['state', 'full_number', 'borrower_1_name', 'borrower_2_name', 'datum_verstuurd', 'datum_ontvangst']
        list_filter = ['state', list_filter.ComboBoxFilter('beslissing.hypotheek.company_id', verbose_name=_('Maatschappij'))]
        list_search = ['beslissing.hypotheek.aanvraagnummer', 'beslissing.hypotheek.roles.natuurlijke_persoon.name', 'beslissing.hypotheek.roles.rechtspersoon.name']
        list_actions = [AanvaardingsBrief(), MortgageTable()]
        form_state = 'maximized'
        form_actions = [CallMethod( _('Verstuurd'), 
                                    lambda o:o.button_send(), 
                                    enabled=lambda o:(o is not None) and (o.state=='to_send' )),
                        CallMethod( _('Ondertekend ontvangen'), 
                                    lambda o:o.button_received(), 
                                    enabled=lambda o:(o is not None) and (o.state=='send' )),
                        CallMethod( _('Annuleer'), 
                                    lambda o:o.button_cancel(), 
                                    enabled=lambda o:(o is not None) and (o.state in ('to_send', 'send') )),
                        ] + list_actions
        form_display =  forms.Form(['beslissing', 'full_number', 'aanvaardingsbrief','datum_verstuurd','datum_ontvangst',
                                    forms.GroupBoxForm(_('Status'),['state',], columns=2),], columns=2)
        field_attributes = {
                            'datum_verstuurd':{'editable':False, 'name':_('Datum versturen')},
                            'state':{'editable':False, 'name':_('Status'), 'choices':[('to_send', 'Te versturen'), ('send', 'Verstuurd'), ('received', 'Ondertekend ontvangen'), ('canceled', 'Geannuleerd')]},
                            'beslissing':{},
                            'beslissing':{'editable':False, 'name':_('Hypotheek beslissing')},
                            'aanvaardingsbrief':{'editable':True, 'name':_('Ondertekende aanvaardingsbrief')},
                            'datum_ontvangst':{'editable':True, 'name':_('Datum ontvangst')},
                            'borrower_1_name':{'editable':False, 'minimal_column_width':30, 'name':_('Naam eerste ontlener')},
                            'borrower_2_name':{'editable':False, 'minimal_column_width':30, 'name':_('Naam tweede ontlener')},
                            'company_id':{'name': _('Maatschappij')},
                           }
        

        def get_query(self, *args, **kwargs):
            query = VfinanceAdmin.get_query(self, *args, **kwargs)
            query = query.options(orm.subqueryload('beslissing'))
            query = query.options(orm.subqueryload('beslissing.hypotheek'))
            query = query.options(orm.subqueryload('beslissing.hypotheek.roles'))
            query = query.options(orm.undefer('beslissing.hypotheek.roles.name'))
            
            return query

Bedrag.aanvaarding_state = orm.column_property(
    sql.select( [Aanvaarding.state] ).where( sql.and_(nieuw_goedgekeurd_bedrag_clause,
                                                      Aanvaarding.beslissing_id==Beslissing.id,
                                                      Beslissing.id==GoedgekeurdBedrag.beslissing_id) ).order_by(Aanvaarding.id.desc()).limit(1),
    deferred=True,
    )
