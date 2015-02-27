"""Meldingen die worden doorgegeven aan de NBB ivm het krediet"""
import sqlalchemy.types
from sqlalchemy import orm, schema

from camelot.admin.action import list_filter
from camelot.core.orm import Entity, ManyToOne, using_options
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _

from .hypotheek import HypoApplicationMixin
from vfinance.admin.vfinanceadmin import VfinanceAdmin


melding_types = [('eerste_negatieve_melding', 'Eerste negatieve melding'), 
                 ('evolutie', 'Evolutie van de debettoestand'), 
                 ('regularisatie', 'Regularisatie'), 
                 ('niet_opeisbaar', 'Niet opeisbaar'), 
                 ('opeisbaar', 'Opeisbaar'), 
                 ('schrapping', 'Schrapping van het negatief luik'), 
                 ('eerste_positieve_melding', 'Eerste positieve melding'), 
                 ('bijvoegen_kredietnemer', 'Bijvoegen kredietnemer'), 
                 ('wijzigen_kredietovereenkomst', 'Wijzigen kredietovereenkomst'), 
                 ('overdracht_kredietovereenkomst', 'Overdracht kredietovereenkomst'), 
                 ('schrapping_kredietnemer', 'Schrapping kredietnemer'),
                 (None, '') ]

def kredietnemers( melding_nbb ):
     dossier = melding_nbb.dossier
     result = [(None, '')]
     if dossier:
          for person in dossier.get_roles_at(None, 'borrower'):
               if person.natuurlijke_persoon:
                    result.append( (person.natuurlijke_persoon, person.natuurlijke_persoon.name ) )
     return result
          
class MeldingNbb(Entity, HypoApplicationMixin):
     """Meldingen ivm kredieten en wanbetalingen wanbetalingen"""
     using_options(tablename='hypo_melding_nbb')
     datum_betaling  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
     comment  =  schema.Column(sqlalchemy.types.Unicode(250), nullable=True)
     state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False, default=unicode('todo'))
     bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
     registratienummer  =  schema.Column(sqlalchemy.types.Unicode(25), nullable=True)
     eenheidnummer  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     dossier_id  =  schema.Column(sqlalchemy.types.Integer(), name='dossier', nullable=False, index=True)
     dossier  =  ManyToOne('vfinance.model.hypo.dossier.Dossier', field=dossier_id, backref='melding_nbb')
     kredietnemer_id  =  schema.Column(sqlalchemy.types.Integer(), name='kredietnemer', nullable=True, index=True)
     kredietnemer  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=kredietnemer_id)
     type  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False)
     datum_melding  =  schema.Column(sqlalchemy.types.Date(), nullable=True)

     @property
     def full_number(self):
         if self.dossier is not None:
             return self.dossier.full_number
        
     @property
     def company_code(self):
         if self.dossier is not None:
             return self.dossier.goedgekeurd_bedrag.product.get_company_code()
         return None

     def __unicode__(self):
          if self.dossier:
               return u'%s %s'%( self.type, unicode(self.dossier) )

     class Admin(VfinanceAdmin):
          verbose_name = _('Melding Nationale Bank')
          verbose_name_plural = _('Meldingen Nationale Bank')
          list_display =  ['full_number',
                           'registratienummer',
                           'kredietnemer',
                           'datum_melding',
                           'type']
          list_filter = ['type','state', list_filter.ComboBoxFilter('dossier.company_id', verbose_name=_('Maatschappij'))]
          form_display =  forms.Form(['dossier',
                                      'registratienummer',
                                      'kredietnemer',
                                      'datum_melding',
                                      'type','bedrag',
                                      'datum_betaling',
                                      'comment',
                                      'eenheidnummer',
                                      'state',
                                      'company_code'] )
          field_attributes = {
                              'datum_betaling':{'editable':True, 'name':_('Datum van (wan)betaling')},
                              'comment':{'editable':True, 'name':_('Opmerking')},
                              'state':{'editable':True, 'name':_('Status'), 'choices':[('todo', 'Te doen'), ('done', 'Uitgevoerd')]},
                              'bedrag':{'editable':True, 'name':_('Bedrag van (wan)betaling')},
                              'registratienummer':{'editable':True, 'name':_('Registratienummer')},
                              'eenheidnummer':{'editable':True, 'name':_('Bijwerkingseenheidnr')},
                              'full_number':{'name': _('Dossier nummer')},
                              'dossier':{'editable':True, 'name':_('Dossier')},
                              'kredietnemer':{},
                              'kredietnemer':{'choices':kredietnemers, 'name':_('Kredietnemer')},
                              'type':{'editable':True, 'name':_('Type'), 'choices':melding_types},
                              'datum_melding':{'editable':True, 'name':_('Datum van melding')},
                             }

          def get_query(self, *args, **kwargs):
              query = VfinanceAdmin.get_query(self, *args, **kwargs)
              query = query.options(orm.joinedload('kredietnemer'))
              query = query.options(orm.joinedload('dossier'))
              query = query.options(orm.joinedload('dossier.goedgekeurd_bedrag'))
              query = query.options(orm.joinedload('dossier.roles'))
              query = query.options(orm.undefer('kredietnemer.name'))
            
              return query
