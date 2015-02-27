import logging

import sqlalchemy.types
from sqlalchemy import sql, schema

from camelot.core.orm import Entity, OneToMany, ManyToOne, using_options
from camelot.admin.entity_admin import EntityAdmin
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _

from vfinance.admin.vfinanceadmin import VfinanceAdmin

from rentevoeten import tarief_voorwaarden_evaluators

logger = logging.getLogger('vfinance.model.hypo.dossierkosten')

class DossierkostHistoriek(Entity):
     """De dossierkost op een bepaalde periode in de tijd"""
     using_options(tablename='hypo_dossierkost_historiek')
     basis_bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False)
     basis_percentage  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False)
     staffel  =  OneToMany('vfinance.model.hypo.dossierkosten.DossierkostStaffel', inverse='historiek')
     start_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
     name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=True)

     def __unicode__(self):
          if self.start_datum:
               return 'From %s'%self.start_datum
          
     @classmethod
     def historiek_from_datum( cls, datum ):
          """Zoek de passende historiek voor een bedrag, dwz de
          eerste historiek die start na datum, return None als zo geen gevonden
          """
          logger.debug('zoek dossierkost historiek in voor datum %s'%(datum))
          return cls.query.filter( cls.start_datum <= datum ).order_by( cls.start_datum.desc() ).first()
     
     @classmethod
     def dossierkost_from_beslissing_and_datum( cls, beslissing, datum ):
          """
          @param beslissing: browseable beslissing object
          @param datum: datum in tiny format
          
          @return: dossierkost, or 0 if none found
          """
          historiek = cls.historiek_from_datum( datum )
          if historiek != None:
              goedgekeurd_totaal = beslissing.goedgekeurd_totaal
              dossierkost = historiek.basis_bedrag + historiek.basis_percentage*goedgekeurd_totaal/100
              staffel = DossierkostStaffel.staffel_from_historiek_and_goedgekeurd_totaal( historiek, goedgekeurd_totaal )
              if staffel:
                  dossierkost += staffel.wijziging_bedrag + staffel.wijziging_percentage*goedgekeurd_totaal/100
                  for wijziging in staffel.verminderingen:
                      wijziging_bedrag, wijziging_percentage = wijziging.geldig_voor_beslissing( beslissing )
                      dossierkost -= (wijziging_bedrag + wijziging_percentage*goedgekeurd_totaal/100)
                  for wijziging in staffel.vermeerderingen:
                      wijziging_bedrag, wijziging_percentage = wijziging.geldig_voor_beslissing( beslissing )
                      dossierkost += (wijziging_bedrag + wijziging_percentage*goedgekeurd_totaal/100)
              return max(dossierkost, 0)
          return 0

     class Admin(VfinanceAdmin):
          verbose_name = _('Dossierkost')
          verbose_name_plural = _('Dossierkosten')
          list_display =  ['start_datum', 'basis_bedrag', 'basis_percentage']
          form_display =  forms.Form(['start_datum','basis_bedrag','basis_percentage','staffel',], columns=2)
          field_attributes = {
                              'basis_bedrag':{'editable':True, 'name':_('Basis bedrag')},
                              'basis_percentage':{'editable':True, 'name':_('Basis percentage')},
                              'staffel':{'editable':True, 'name':_('Staffel')},
                              'start_datum':{'editable':True, 'name':_('Aanvangsdatum')},
                              'name':{'editable':True, 'name':_('Naam')},
                             }
tarief_voorwaarden = [ ('quotiteit_klein', 'Quotitiet < x% verkoopwaarde'), 
                       ('woonsparen', 'Woonsparen'), 
                       ('aflossing_klein', 'Maandelijkse aflossing < x% maandinkomen'), 
                       ('quotiteit_groter', 'Quotitiet > x% verkoopwaarde'), 
                       ('handelsdoeleinden', 'Gebouw voor handelsdoeleinden'), 
                       ('eerdere_rang', 'Hypotheek in tweede rang'), 
                       ('inkomsten_niet_bewezen', 'Beroepsinkomsten niet bewezen'), 
                       ('investeringskrediet', 'Investeringskrediet')]

class DossierkostStaffel(Entity):
     """De dossierkosten naar gelang het totaal ontleend bedrag"""
     using_options(tablename='hypo_dossierkost_staffel')
     name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=True)
     minimum_ontleend_bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
     wijziging_percentage  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
     wijziging_bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
     historiek_id  =  schema.Column(sqlalchemy.types.Integer(), name='historiek', nullable=False, index=True)
     historiek  =  ManyToOne('vfinance.model.hypo.dossierkosten.DossierkostHistoriek', field=historiek_id)

     @classmethod
     def staffel_from_historiek_and_goedgekeurd_totaal( cls, historiek, goedgekeurd_totaal ):
          return cls.query.filter( sql.and_( cls.minimum_ontleend_bedrag <= goedgekeurd_totaal,
                                             cls.historiek == historiek ) ).order_by( cls.minimum_ontleend_bedrag.desc() ).first()

     def __unicode__(self):
          if self.minimum_ontleend_bedrag:
               return unicode( self.minimum_ontleend_bedrag )
          return ''

     class Admin(EntityAdmin):
          list_display =  ['minimum_ontleend_bedrag', 'wijziging_bedrag', 'wijziging_percentage']
          form_display =  forms.Form(['minimum_ontleend_bedrag','wijziging_bedrag','wijziging_percentage','verminderingen','vermeerderingen',], columns=2)
          field_attributes = {
                              'name':{'editable':True, 'name':_('Naam')},
                              'minimum_ontleend_bedrag':{'editable':True, 'name':_('Bedrag >')},
                              'wijziging_percentage':{'editable':True, 'name':_('Wijziging percentage')},
                              'verminderingen':{'editable':True, 'name':_('Verminderingen')},
                              'wijziging_bedrag':{'editable':True, 'name':_('Wijziging bedrag')},
                              'historiek':{'editable':True, 'name':_('Historiek')},
                              'vermeerderingen':{'editable':True, 'name':_('Vermeerderingen')},
                             }

class DossierkostWijziging(Entity):
     using_options(tablename='hypo_dossierkost_wijziging')
     voorwaarde  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
     name  =  schema.Column(sqlalchemy.types.Unicode(100), nullable=True)
     staffel_vermindering_id  =  schema.Column(sqlalchemy.types.Integer(), name='staffel_vermindering', nullable=True, index=True)
     staffel_vermindering  =  ManyToOne('vfinance.model.hypo.dossierkosten.DossierkostStaffel', field=staffel_vermindering_id, backref='verminderingen' )
     staffel_vermeerdering_id  =  schema.Column(sqlalchemy.types.Integer(), name='staffel_vermeerdering', nullable=True, index=True)
     staffel_vermeerdering  =  ManyToOne('vfinance.model.hypo.dossierkosten.DossierkostStaffel', field=staffel_vermeerdering_id, backref='vermeerderingen' )
     wijziging_percentage  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
     wijziging_bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
     x  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)

     def geldig_voor_beslissing( self, beslissing ):
          """Ga na of een bepaalde rente wijziging geldig is voor een bepaalde beslissing
          :param: beslissing een browsable beslissing object
          :return: het bedrag en percentage van wijziging als geldig, (0, 0) als niet geldig
          """
          logger.debug('ga na of rente wijziging %s geldig is voor beslissing %s : %s met x=%s'%(self.id, beslissing.id, self.voorwaarde, self.x))    
          if tarief_voorwaarden_evaluators[self.voorwaarde](self.x, beslissing):
              logger.debug('rentewijziging geldig : %s'%self.voorwaarde)
              return (self.wijziging_bedrag, self.wijziging_percentage)
          return (0, 0)

     def __unicode__(self):
          if self.staffel_vermindering_id:
               return u'Vermindering'
          elif self.staffel_vermeerdering_id:
               return u'Vermeerdering'
          return ''

     class Admin(EntityAdmin):
          list_display =  ['voorwaarde', 'x', 'wijziging_bedrag', 'wijziging_percentage']
          form_display =  forms.Form(['voorwaarde','x','wijziging_bedrag','wijziging_percentage',], columns=2)
          field_attributes = {
                              'voorwaarde':{'editable':True, 'name':_('Voorwaarde'), 'choices':tarief_voorwaarden},
                              'name':{'editable':True, 'name':_('Naam')},
                              'staffel_vermindering':{},
                              'staffel_vermindering':{'editable':True, 'name':_('Historiek')},
                              'staffel_vermeerdering':{},
                              'staffel_vermeerdering':{'editable':True, 'name':_('Historiek')},
                              'wijziging_percentage':{'editable':True, 'name':_('Wijziging percentage')},
                              'wijziging_bedrag':{'editable':True, 'name':_('Wijziging bedrag')},
                              'x':{'editable':True, 'name':_('x')},
                             }
