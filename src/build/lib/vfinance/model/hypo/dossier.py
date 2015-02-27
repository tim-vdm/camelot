import calendar
import datetime
from datetime import timedelta, date
from decimal import Decimal as D
import logging
import math
import operator

import sqlalchemy.types
from sqlalchemy import sql, orm, schema

from camelot.admin.action import Action, list_filter
from camelot.admin.object_admin import ObjectAdmin
from camelot.core.exception import UserException
from camelot.core.orm import ( Entity, Field, ManyToOne, using_options,
                               OneToMany, ManyToMany)
from camelot.model.authentication import end_of_times
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.view import forms, action_steps
from camelot.core.utils import ugettext, ugettext_lazy as _
from camelot.core.conf import settings
import camelot.types

from .hypotheek import HypoAbstractRole, HypoApplicationMixin
from .notification.mortgage_table import MortgageTable
from .notification.rappel_sheet import DossierSheet
from .constants import (hypo_functional_settings, hypo_group_by_functional_setting, 
                        hypo_features, reminder_levels, request_role_choices)
from .visitor import AbstractHypoVisitor
from .summary import DossierSummary
from ..bank.dual_person import DualPerson
from ..bank.natuurlijke_persoon import NatuurlijkePersoon
from ..bank.rechtspersoon import Rechtspersoon
from ..bank.dossier import AbstractDossierBroker
from ..bank.invoice import InvoiceItem
from ..bank.direct_debit import DirectDebitMandate
from ..bank.visitor import CustomerBookingAccount
from vfinance.admin.vfinanceadmin import VfinanceAdmin

dossier_statussen = [('opnameperiode', 'In opname periode'), ('running', 'Lopende'), ('ended', 'Beeindigd')]
korting_types = [('per_aflossing', 'Per aflossing'),('per_jaar','Per jaar'),('pret_jeunes','Pret Jeunes')]

from vfinance.model.bank.venice import get_dossier_bank

#from .hypotheek import HypoAbstractRole

logger = logging.getLogger('vfinance.model.hypo.dossier')

class SyncVenice( Action ):

  verbose_name = _('Sync')

  def model_run( self, model_context ):
      from vfinance.model.bank.entry import Entry
      logger.debug('synchroniseer dossier met Venice')
      for dossier in model_context.get_selection():
          yield action_steps.UpdateProgress( text = ugettext('Sync {0}').format( unicode(dossier) ) )
          customer_accounts = set()
          for loan_schedule in dossier.loan_schedules:
              customer = AbstractHypoVisitor.get_customer_at(loan_schedule, dossier.startdatum)
              customer_accounts.add(customer.full_account_number)
          for customer_account in customer_accounts:
              Entry.sync_venice(accounts=customer_account)
          yield action_steps.FlushSession(model_context.session)
          yield action_steps.UpdateObject(dossier)

class CreateReminder(Action):
    """Creeer een rappel brief voor een dossier op een bepaalde datum"""
    
    verbose_name = _('Maak rappel')
    
    class ReminderOptions(object):
        
        def __init__(self, dossier=None, model_context=None):
            from rappel_brief import RappelBrief
            self.doc_date = datetime.date.today()
            self.level = 1
            if dossier is not None and model_context is not None:
                rappel_query = model_context.session.query(RappelBrief)
                rappel_query = rappel_query.filter(RappelBrief.status=='send')
                rappel_query = rappel_query.filter(RappelBrief.dossier==dossier)
                rappel_query = rappel_query.order_by(RappelBrief.doc_date.desc(), RappelBrief.id.desc())
                last_rappel = rappel_query.first()
                if last_rappel is not None:
                    self.level = last_rappel.rappel_level
            else:
                raise UserException('No account selected')

        class Admin(ObjectAdmin):
            list_display = ['doc_date', 'level']
            field_attributes = {'doc_date': {'editable': True,
                                             'nullable': False,
                                             'delegate': delegates.DateDelegate},
                                'level': {'editable': True,
                                          'nullable': False,
                                          'delegate': delegates.ComboBoxDelegate,
                                          'choices': reminder_levels}
                                }
            
    def model_run(self, model_context):
        from rappel_brief import (RappelOpenstaandeVervaldag, 
                                  RappelOpenstaandeBetaling, RappelBrief)
        for dossier in model_context.get_selection():
            options = self.ReminderOptions(dossier, model_context)
            yield action_steps.ChangeObject(options)
            rappel_query = model_context.session.query(RappelBrief)
            rappel_query = rappel_query.filter(RappelBrief.status!='canceled')
            rappel_query = rappel_query.filter(RappelBrief.dossier==dossier)
            rappel_query = rappel_query.filter(RappelBrief.doc_date<=options.doc_date)
            if rappel_query.filter(RappelBrief.status=='to_send').count():
                raise UserException('Previous letters are not send or canceled yet')
            with model_context.session.begin():
                eerdere_brieven = list(rappel_query.all())
                kosten_eerdere_brieven = 0
                for reminder in eerdere_brieven:
                    if reminder.open_amount:
                        kosten_eerdere_brieven += reminder.open_amount
                n = len(eerdere_brieven)
                letter = RappelBrief(doc_date = options.doc_date,
                                     dossier = dossier,
                                     status = 'to_send',
                                     amount =  D(settings.get('HYPO_RAPPEL_KOST', 4.82)),
                                     rappel_level = options.level,
                                     kosten_rappelbrieven = kosten_eerdere_brieven,
                                     item_description = ('Dossier {0.nummer} : rappel {1}'.format(dossier,n+1))[:140]
                                     )
                for ov in dossier.get_openstaande_vervaldagen(options.doc_date):
                    RappelOpenstaandeVervaldag(related_to=ov.vervaldag,
                                               doc_date = options.doc_date,
                                               item_description=ov.vervaldag.item_description,
                                               modifier_of=letter,
                                               te_betalen=ov.te_betalen,
                                               amount=ov.intrest_a+ov.intrest_b,
                                               intrest_a=ov.intrest_a,
                                               intrest_b=ov.intrest_b,
                                               afpunt_datum=ov.afpunt_datum,
                                               dossier=dossier)
                for entry in dossier.openstaande_betaling:
                    RappelOpenstaandeBetaling(modifier_of = letter,
                                              doc_date = entry.doc_date,
                                              item_description = (entry.remark or '')[:140],
                                              dossier = dossier,
                                              amount = -1*entry.open_amount)
                model_context.session.flush()
            model_context.session.expire(dossier)
            yield action_steps.UpdateObject(dossier)
            yield action_steps.OpenFormView([letter], model_context.admin.get_related_admin(RappelBrief))

class HypoDossierRole(DualPerson, HypoAbstractRole):

  __tablename__ = 'hypo_dossier_role'
  __table_args__ = ( schema.CheckConstraint( 'natuurlijke_persoon is not null or rechtspersoon is not null', 
                                             name='hypo_dossier_role_persoon_fk'), )
  
  from_date = schema.Column(sqlalchemy.types.Date(), nullable=False)
  natuurlijke_persoon = orm.relationship(NatuurlijkePersoon)
  rechtspersoon  = orm.relationship(Rechtspersoon)
  dossier = ManyToOne('Dossier', 
                      nullable=False, 
                      ondelete='cascade', onupdate='cascade',
                      backref=orm.backref('roles', cascade='all, delete, delete-orphan'))
  
  class Admin(EntityAdmin):
      list_display = ['described_by', 'rank', 'natuurlijke_persoon', 'rechtspersoon', 'from_date', 'thru_date', 'telefoon']
      field_attributes = {'described_by': {'choices': request_role_choices},
                          }

class HypoDossierBroker(Entity, AbstractDossierBroker):
    using_options(tablename='hypo_dossier_broker')
    dossier = ManyToOne('vfinance.model.hypo.dossier.Dossier', required = True, ondelete = 'cascade', onupdate = 'cascade')
    broker_relation = ManyToOne('CommercialRelation', required=False, ondelete = 'restrict', onupdate = 'cascade')
    broker_agent = ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon')

    class Admin(EntityAdmin):
        list_display = ['broker_relation', 'broker_agent', 'from_date', 'thru_date']

class DossierFunctionalSettingApplication(Entity):
    using_options(tablename='hypo_dossier_functional_setting_application')
    applied_on = ManyToOne('vfinance.model.hypo.dossier.Dossier', required = True, ondelete = 'restrict', onupdate = 'cascade')
    described_by = schema.Column( camelot.types.Enumeration(hypo_functional_settings), nullable=False, default='direct_debit_batch_1')
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    clause = schema.Column(camelot.types.RichText())

    class Admin(EntityAdmin):
        verbose_name = _('Hypo Dossier Setting')
        verbose_name_plural = _('Hypo Dossier Settings')
        list_display = ['described_by', 'from_date', 'thru_date']
        form_display = list_display + ['clause']
        field_attributes = {'described_by':{'name':_('Description')},}

class DossierFeatureApplication(Entity):
    using_options(tablename='hypo_dossier_feature_application')
    applied_on = ManyToOne('vfinance.model.hypo.dossier.Dossier', required = True, ondelete = 'restrict', onupdate = 'cascade')
    described_by = schema.Column( camelot.types.Enumeration(hypo_features), nullable=False, default='initial_approved_amount')
    value = Field( sqlalchemy.types.Numeric(precision=17, scale=5), required=True, default=D(0))
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    comment = schema.Column( camelot.types.RichText() )

    class Admin( EntityAdmin ):
        verbose_name = _('Hypo Dossier Feature')
        verbose_name_plural = _('Hypo Dossier Features')
        list_display = ['described_by', 'value', 'from_date', 'thru_date']
        form_display = list_display + ['comment']
        field_attributes = {'described_by':{'name':_('Description')},}

class Dekking(Entity):
    """Hypotheek die als dekking gebruikt wordt voor andere producten"""
    using_options(tablename='hypo_dekking')
    dossier_id  =  schema.Column(sqlalchemy.types.Integer(), name='dossier', nullable=True, index=True)
    dossier  =  ManyToOne('vfinance.model.hypo.dossier.Dossier', field=dossier_id, backref='dekking')
    valid_date_start  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    type  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__(self):
        return self.type

    class Admin(EntityAdmin):
        verbose_name = _('Dekkinswaarde')
        verbose_name_plural = _('Dekkingswaardes')
        list_display =  ['valid_date_start', 'type']
        form_display =  forms.Form(['valid_date_start','type',], columns=2)
        field_attributes = {
                            'dossier':{},
                            'dossier':{'editable':False, 'name':_('Dossier')},
                            'valid_date_start':{'editable':True, 'name':_('Start datum')},
                            'type':{'editable':True, 'name':_('Type'), 'choices':[('kapitalisatiebon', 'Kapitalisatiebonnen'), ('obligatie', 'Obligaties')]},
                           }
rappel_levels = ['Normaal', 'Streng', 'Ingebrekestelling', 'Opzegging krediet']
dekking_types = [('kapitalisatiebon', 'Kapitalisatiebonnen'), ('obligatie', 'Obligaties')]

class AkteDossier(Entity):
    """Relatie tussen een verleden akte en een hypotheek dossier"""
    using_options(tablename='hypo_akte_dossier')
    dossier_id  =  schema.Column(sqlalchemy.types.Integer(), name='dossier', nullable=False, index=True)
    dossier  =  ManyToOne('vfinance.model.hypo.dossier.Dossier', field=dossier_id, backref='aktes', cascade='all')
    from_date  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    akte_id  =  schema.Column(sqlalchemy.types.Integer(), name='akte', nullable=False, index=True)
    akte  =  ManyToOne('vfinance.model.hypo.akte.Akte', field=akte_id, backref='dossiers')
    thru_date  =  schema.Column(sqlalchemy.types.Date(), nullable=False, default=end_of_times)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__(self):
        if self.dossier:
          return unicode( self.dossier )

    class Admin(EntityAdmin):
        list_display =  ['akte', 'dossier', 'from_date', 'thru_date']
        form_display =  forms.Form(['akte','from_date','thru_date',], columns=2)
        field_attributes = {
                            'dossier':{},
                            'dossier':{'editable':True, 'name':_('Dossier')},
                            'from_date':{'editable':True, 'name':_('Vanaf')},
                            'akte':{},
                            'akte':{'editable':True, 'name':_('Akte')},
                            'thru_date':{'editable':True, 'name':_('Tot en met')},
                           }

class Korting(Entity):
    """Kortingen die worden toegepast op het lopende dossier"""
    using_options(tablename='hypo_korting')
    comment  =  schema.Column(sqlalchemy.types.Unicode(250), nullable=True)
    valid_date_start  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    rente  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False)
    dossier_id  =  schema.Column(sqlalchemy.types.Integer(), name='dossier', nullable=True, index=True)
    dossier  =  ManyToOne('vfinance.model.hypo.dossier.Dossier', field=dossier_id, backref='korting')
    type  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False)
    datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    valid_date_end  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    origin  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__(self):
        return self.type

    class Admin(EntityAdmin):
        list_display =  ['type', 'valid_date_start', 'valid_date_end', 'rente']
        form_display =  forms.Form(['datum','type','valid_date_start','valid_date_end','rente',], columns=2)
        field_attributes = {
                            'comment':{'editable':True, 'name':_('Opmerking')},
                            'valid_date_start':{'editable':True, 'name':_('Start datum')},
                            'rente':{'editable':True, 'name':_('Rente')},
                            'dossier':{},
                            'dossier':{'editable':False, 'name':_('Dossier')},
                            'type':{'editable':True, 'name':_('Type'), 'choices':[('per_aflossing', 'Per aflossing'),
                                                                                  ('per_jaar', 'Per jaar'),
                                                                                  ('pret_jeunes', 'Pret Jeunes'),
                                                                                  ('mijnwerker', 'Mijnwerkerskrediet')]},
                            'datum':{'editable':True, 'name':_('Datum')},
                            'valid_date_end':{'editable':True, 'name':_('Eind datum')},
                            'origin':{'editable':True, 'name':_('Origin')},
                           }
waarborg_types = [('vlaams', 'Vlaams gewest'), ('waals', 'Waals gewest'), ('brussels', 'Brussels gewest')]
#  dossier_ontleners
#  korting_rekeningen

class Factuur(Entity):
    """Facturen die dienen te worden voorgelegd alvorens kapitaal wordt uitbetaald"""
    using_options(tablename='hypo_factuur')
    administratiekost  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    dossier_id  =  schema.Column(sqlalchemy.types.Integer(), name='dossier', nullable=True, index=True)
    dossier  =  ManyToOne('vfinance.model.hypo.dossier.Dossier', field=dossier_id, backref='factuur')
    datum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    beschrijving  =  schema.Column(sqlalchemy.types.Unicode(120), nullable=False)
    bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__( self ):
      return ''

    class Admin(EntityAdmin):
        list_display =  ['datum', 'beschrijving', 'bedrag', 'administratiekost']
        form_display =  forms.Form(['datum','beschrijving','bedrag','administratiekost',], columns=2)
        field_attributes = {
                            'administratiekost':{'editable':True, 'name':_('Administratiekost')},
                            'dossier':{},
                            'dossier':{'editable':False, 'name':_('Dossier')},
                            'datum':{'editable':True, 'name':_('Datum')},
                            'state':{'editable':False, 'name':_('Status'), 'choices':[('new', 'Nieuw')]},
                            'beschrijving':{'editable':True, 'name':_('Beschrijving')},
                            'bedrag':{'editable':True, 'name':_('Gevraagd bedrag')},
                           }

class BijkomendeWaarborgDossier(Entity):
    """Relatie tussen een bijkomende waarborg en een hypotheek dossier"""
    using_options(tablename='hypo_bijkomende_waarborg_dossier')
    dossier_id  =  schema.Column(sqlalchemy.types.Integer(), name='dossier', nullable=False, index=True)
    dossier  =  ManyToOne('vfinance.model.hypo.dossier.Dossier', field=dossier_id, backref='bijkomende_waarborgen')
    from_date  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    bijkomende_waarborg_id  =  schema.Column(sqlalchemy.types.Integer(), name='bijkomende_waarborg', nullable=False, index=True)
    bijkomende_waarborg  =  ManyToOne('vfinance.model.hypo.hypotheek.BijkomendeWaarborg', field=bijkomende_waarborg_id)
    thru_date  =  schema.Column(sqlalchemy.types.Date(), nullable=False, default=end_of_times)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    def __unicode__(self):
        if self.bijkomende_waarborg:
          return unicode( self.bijkomende_waarborg )

    class Admin(EntityAdmin):
        list_display =  ['bijkomende_waarborg', 'dossier', 'from_date', 'thru_date']
        form_display =  forms.Form(['bijkomende_waarborg','from_date','thru_date',], columns=2)
        field_attributes = {
                            'dossier':{},
                            'dossier':{'editable':True, 'name':_('Dossier')},
                            'from_date':{'editable':True, 'name':_('Vanaf')},
                            'bijkomende_waarborg':{},
                            'bijkomende_waarborg':{'editable':True, 'name':_('Bijkomende waarborg')},
                            'thru_date':{'editable':True, 'name':_('Tot en met')},
                           }

class CreateCustomer(Action):
  
    verbose_name = _('Create customer and account')
    
    def model_run(self, model_context):
        visitor = AbstractHypoVisitor()
        for i, dossier in enumerate(model_context.get_selection()):
            visitor.get_customer_at(dossier.goedgekeurd_bedrag, datetime.date.today(), state='draft')
            visitor.get_full_account_number_at(dossier.goedgekeurd_bedrag, datetime.date.today())
            yield action_steps.UpdateProgress(i, model_context.selection_count)

class AbstractDossier(HypoApplicationMixin):
  
    @property
    def customer_number(self):
      product = self.goedgekeurd_bedrag.product
      return int('%0*i%0*i'%(product.company_number_digits,
                             self.company_id,
                             product.account_number_digits,
                             self.nummer))
    
class Dossier( Entity, AbstractDossier ):
    """Een hypotheek dossier is een hypotheek die in de boekhouding verwerkt zit en waarop dus aflossingen
    periodiek moeten geboekt worden"""
    using_options(tablename='hypo_dossier', order_by=['nummer'])
    #roles = OneToMany(HypoDossierRole, cascade='all, delete, delete-orphan' )
    origin  =  schema.Column(sqlalchemy.types.Unicode(15), nullable=True)
    domiciliering  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    originele_startdatum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    kredietcentrale_update  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    brokers = OneToMany(HypoDossierBroker, cascade='all, delete, delete-orphan' )
    #replaced with backref korting  =  OneToMany('vfinance.model.hypo.dossier.Korting', inverse='dossier')
    #@todo: melding_nbb  =  OneToMany('vfinance.model.hypo.MeldingNbb', inverse='dossier')
    som_openstaande_verrichtingen  =  property(lambda self:self.get_som_openstaande_verrichtingen())
    startdatum  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    #replaced with backref aktes  =  OneToMany('vfinance.model.hypo.dossier.AkteDossier', inverse='dossier')
    goedgekeurd_bedrag_id  =  schema.Column(sqlalchemy.types.Integer(), name='goedgekeurd_bedrag', nullable=False, index=True)
    goedgekeurd_bedrag  =  ManyToOne('vfinance.model.hypo.beslissing.GoedgekeurdBedrag', field=goedgekeurd_bedrag_id,
                                     backref=orm.backref('huidige_dossier', uselist=False))
    bijkomende_waarborgen_deprecated  =  property(lambda self:self.get_bijkomende_waarborgen())
    aanvraag_id  =  schema.Column(sqlalchemy.types.Integer(), name='aanvraag', nullable=True, index=True)
    aanvraag  =  ManyToOne('vfinance.model.hypo.hypotheek.Hypotheek', field=aanvraag_id)
    theoretische_einddatum  =  property(lambda self:self.get_theoretische_einddatum())
    openstaand_kapitaal  =  property(lambda self:self.get_openstaand_kapitaal())
    #replaced with backref dekking  =  OneToMany('vfinance.model.hypo.dossier.Dekking', inverse='dossier')
    rappel_datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    bedrag  =  property(lambda self:self.getter())
    einddatum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    borgsteller_deprecated  =  property(lambda self:self.get_borgstellers())
    akte_deprecated  =  property(lambda self:self.get_akte_deprecated())
    #replaced with backref bijkomende_waarborgen  =  OneToMany('vfinance.model.hypo.dossier.BijkomendeWaarborgDossier', inverse='dossier')
    #replaced with backref borgstellers  =  OneToMany('vfinance.model.hypo.dossier.BorgstellerDossier', inverse='dossier')
    maatschappij  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    # replaced with backref vervaldag  =  OneToMany('vfinance.model.hypo.periodieke_verichting.Vervaldag', inverse='dossier')
    kredietcentrale_gesignaleerd  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)
    #@todo: rappelbrief  =  OneToMany('vfinance.modelhypo.RappelBrief', inverse='dossier')
    nummer  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
    company_id = schema.Column(sqlalchemy.types.Integer(), nullable=False)
    rank = schema.Column(sqlalchemy.types.Integer(), nullable=False)
    #replaced with backref dossier_kost  =  OneToMany('vfinance.model.hypo.dossier.DossierKost', inverse='dossier')
    rappel_level  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    direct_debit_mandates = ManyToMany(DirectDebitMandate, tablename='hypo_dossier_direct_debit_mandate', backref='dossiers')
    applied_functional_settings = OneToMany('DossierFunctionalSettingApplication', cascade='all, delete, delete-orphan')
    applied_features = OneToMany('DossierFeatureApplication', cascade='all, delete, delete-orphan')
    text = Field( camelot.types.RichText, deferred = True )

    __table_args__ = ( schema.UniqueConstraint(company_id, nummer, rank), )
        
    #@todo: wijziging  =  OneToMany('vfinance.model.hypo.wijziging.Wijziging', inverse='dossier')

    @property
    def borrower_1_name(self):
        borrowers = self.get_roles_at(datetime.date.today(), 'borrower')
        if len(borrowers) > 0:
            return borrowers[0].name

    @property
    def borrower_2_name(self):
        borrowers = self.get_roles_at(datetime.date.today(), 'borrower')
        if len(borrowers) > 1:
            return borrowers[1].name

    @property
    def current_status(self):
        return self.state


    def __getattr__(self, attribute):
        if attribute in ['waarborgen', 'waarborgen_venale_verkoop', 'waarborg_bijkomend_waarde', 'hypothecaire_waarborgen', 'wettelijk_kader']:
            if self.aanvraag == None:
                return None
            return getattr( self.aanvraag, attribute )
        if attribute in [ 'goedgekeurde_rente','goedgekeurde_reserverings_provisie','goedgekeurde_looptijd','goedgekeurd_type_aflossing',
                          'goedgekeurd_terugbetaling_interval','goedgekeurd_terugbetaling_start','goedgekeurde_opname_periode',
                          'goedgekeurde_aflossing', 'goedgekeurde_opname_schijven' ]:
            if self.goedgekeurd_bedrag == None:
                return None
            return getattr( self.goedgekeurd_bedrag, attribute )
        logger.error( 'no attribute %s found on Dossier'%attribute )
        raise AttributeError(attribute)

    def get_applied_functional_settings_at( self,
                                            application_date,
                                            functional_setting_group ):
        functional_settings = []
        for functional_setting in self.applied_functional_settings:
            if functional_setting.from_date <= application_date and functional_setting.thru_date >= application_date:
                if hypo_group_by_functional_setting[functional_setting.described_by] == functional_setting_group:
                    functional_settings.append(functional_setting)
        return functional_settings
                  
    def get_applied_feature_value_at( self,
                                      application_date,
                                      feature_description,
                                      default = None ):
        """
        :param application_date: the date at which the features will be used, eg to book a premium
        :param feature_description: the name of the feature
        :param default: what will be returned in case no feature is found (distinction between None and 0)
        :return: the value of the applicable feature, or the default value in no such feature applicable
        """
        assert isinstance( application_date, (datetime.date,) )
        for feature in self.applied_features:
            if feature.described_by == feature_description:
              if feature.from_date <= application_date and feature.thru_date >= application_date:
                return feature.value
        return default

    def get_reductions_at(self, doc_date, openstaand_kapitaal):
        """Lijst met (korting_type, korting_bedrag) geldig voor deze vervaldag"""
        from dossier_business import korting_op_vervaldag

        for korting in self.korting:
            if korting.valid_date_start <= doc_date and korting.valid_date_end >= doc_date:
              amount = korting_op_vervaldag(self.originele_startdatum,
                                            korting.valid_date_start,
                                            korting.valid_date_end,
                                            korting.rente,
                                            korting.type,
                                            doc_date,
                                            openstaand_kapitaal)
              yield korting.type, amount

    @property
    def beslissing_nieuw( self ):
        try:
          if self.goedgekeurd_bedrag.type == 'nieuw':
            return self.goedgekeurd_bedrag.beslissing
          for wijziging in self.wijziging:
              if wijziging.vorig_goedgekeurd_bedrag:
                  if wijziging.vorig_goedgekeurd_bedrag.type == 'nieuw':
                      return wijziging.vorig_goedgekeurd_bedrag.beslissing
        except Exception, e:
          logger.error( 'Could not get beslissing nieuw', exc_info=e )
        logger.error( 'Inconsistent data, dossier %s heeft geen goedgekeurd bedrag type nieuw'%self.name )
        raise Exception('Inconsistent data, dossier %s heeft geen goedgekeurd bedrag type nieuw'%self.name)

    @property
    def goedgekeurd_bedrag_nieuw( self ):
      if self.goedgekeurd_bedrag.type == 'nieuw':
        return self.goedgekeurd_bedrag
      for wijziging in self.wijziging:
          if wijziging.vorig_goedgekeurd_bedrag:
              if wijziging.vorig_goedgekeurd_bedrag.type == 'nieuw':
                  return wijziging.vorig_goedgekeurd_bedrag
      logger.error( 'Inconsistent data, dossier %s heeft geen goedgekeurd bedrag type nieuw'%self.name )
      raise Exception('Inconsistent data, dossier %s heeft geen goedgekeurd bedrag type nieuw'%self.name)

    @property
    def wijziging( self ):
      from wijziging import Wijziging
      return Wijziging.query.filter( Wijziging.dossier_id == self.id ).all()

    def get_openstaande_vervaldagen( self, close_date, tolerantie = 14, payment_thru_date = None ):
      """Genereer een lijst met openstaande vervaldagen, hun nalatigheidsintresten op de close_date en
      de datum waarop ze zouden kunnen zijn afgepunt, indien het afpunten nog niet gebeurd is.  
      
      :param tolerantie: is het aantal dagen dat een vervaldag onbetaald mag blijven vooraleer er
          intresten worden aangerekend.
      
      :param payment_thru_date: upto this date, payments are used, this equals the close date if `None`
          is given
      """
      from periodieke_verichting import Vervaldag
      from vfinance.model.bank.entry import Entry
      logger.debug('get_openstaande_vervaldagen %s'%self.id)

      if self.nummer == None:
          return []
        
      if payment_thru_date is None:
          payment_thru_date = close_date

      over_te_nemen_velden = ['doc_date','kapitaal','amount','openstaand_kapitaal', 'rente',]
      account_klant = int( settings.get( 'HYPO_ACCOUNT_KLANT', 400000000000 ) )
      logger.debug('dossier : %s'%self.id)
      gb = self.goedgekeurd_bedrag
      goedgekeurde_intrest_a = D( gb.goedgekeurde_intrest_a or 0)
      goedgekeurde_intrest_b = D( gb.goedgekeurde_intrest_b or 0)
      goedgekeurde_jaarrente = D( gb.goedgekeurde_jaarrente or 0)
      #Uitzondering voor oude leningen met jaarrente
      if goedgekeurde_jaarrente != 0:
        goedgekeurde_intrest_b = goedgekeurde_intrest_b / 4
      #Einde uitzondering
      goedgekeurd_terugbetaling_interval = int(gb.goedgekeurd_terugbetaling_interval)
      vervaldagen = []
      #Lees de openstaande betalingen, om datum te kunnen bepalen waarop aflossingen zouden kunnen
      #zijn afgepunt, hou enkel rekening met betaling van voor de close date
      betalingen = Entry.query.filter( sql.and_( Entry.account == str(account_klant+self.nummer),
                                                 Entry.open_amount < 0,
                                                 Entry.book_date <= payment_thru_date,
                                                 Entry.venice_book != 'NewHy')).all()
      #Loop over de openstaande aflossigen om de mogelijke afpunt datum te bepalen en de nalatigheids
      #intresten
      gebruikteOpenstaandeBetalingen = 0
      vorigeVervaldagVirtuallyTicked  = True
      
      visitor = AbstractHypoVisitor()
      vervaldag_ids = set()
      for loan_schedule in self.loan_schedules:
          for entry in visitor.get_entries(loan_schedule,
                                           fulfillment_types=['repayment', 'reservation'],
                                           conditions=[('open_amount', operator.ne, 0)],
                                           account=CustomerBookingAccount()):
              vervaldag_ids.add(entry.booking_of_id)
      vervaldag_query = orm.object_session(self).query(Vervaldag)
      vervaldag_query = vervaldag_query.filter(Vervaldag.id.in_(vervaldag_ids))
      vervaldag_query = vervaldag_query.filter(Vervaldag.status != 'canceled')
      vervaldag_query = vervaldag_query.order_by(Vervaldag.doc_date, Vervaldag.nummer)
      openstaande_vervaldagen = list(vervaldag_query.all())
      logger.debug('openstaande vervaldagen : %s'%openstaande_vervaldagen)
      for openstaande_vervaldag in openstaande_vervaldagen:
        vervaldag_datum = openstaande_vervaldag.doc_date
        #vervaldag_datum = datetime(year=vervaldag_datum.year, month=vervaldag_datum.month, day=vervaldag_datum.day)
        # Enkel vervaldagen die voorbij de afsluitdatum liggen komen in aanmerking als zijnde openstaand
        if close_date >= vervaldag_datum:

          def intrest_a(mogelijke_afpunt_datum):
            """waarde van de rappel intrest a, afhankelijk van de laatste dag waarop de aflossing als openstaand
            kan worden beschouwd"""
            if not(close_date >= (vervaldag_datum + timedelta(days=tolerantie))):
              return 0
            if mogelijke_afpunt_datum < vervaldag_datum:
              return 0
            return (goedgekeurde_intrest_a * openstaande_vervaldag.openstaand_kapitaal)/100
          def intrest_b(mogelijke_afpunt_datum):
            """waarde van de rappel intrest b, afhankelijk van de laatste dag waarop de aflossing als openstaand
            kan worden beschouwd"""
            if not(close_date >= (vervaldag_datum + timedelta(days=tolerantie))):
              return 0
            if mogelijke_afpunt_datum < vervaldag_datum:
              return 0
            overtijd = int( math.ceil(D((mogelijke_afpunt_datum - vervaldag_datum).days)/(365/goedgekeurd_terugbetaling_interval)) )
            return (goedgekeurde_intrest_b * openstaande_vervaldag.kapitaal * overtijd )/100
          def intrest_a_b(mogelijke_afpunt_datum):
            """totaal van vervalintresten"""
            return intrest_a(mogelijke_afpunt_datum) + intrest_b(mogelijke_afpunt_datum)
          def open_value(mogelijke_afpunt_datum):
            """Waarde van de aflossing op de laatste dag waarop de aflossing als openstaand kan worden beschouwd, dit
            is hat kapitaal inclusief intresten en verwijlintresten"""
            return openstaande_vervaldag.amount + intrest_a_b(mogelijke_afpunt_datum)

          vervaldag = dict( (k, getattr(openstaande_vervaldag, k)) for k in over_te_nemen_velden )
          vervaldag['vervaldag'] = openstaande_vervaldag
          #Bepaal eerst de mogelijke afpunt datum
          accumulated_value = gebruikteOpenstaandeBetalingen * -1
          mogelijke_afpunt_datum = close_date
          if vorigeVervaldagVirtuallyTicked:
            vorigeVervaldagVirtuallyTicked = False
            for b in betalingen:
              accumulated_value -= D( b.open_amount )
              value = D( open_value((b.book_date)) )
              if accumulated_value >= value:
                mogelijke_afpunt_datum = (b.book_date)
                gebruikteOpenstaandeBetalingen += value
                vorigeVervaldagVirtuallyTicked = True
                break
          #Bepaal nu de nalatigheidsintresten
          vervaldag['related_doc_date'] = openstaande_vervaldag.doc_date
          vervaldag['aflossing'] = openstaande_vervaldag.amount
          vervaldag['intrest_a'] = intrest_a(mogelijke_afpunt_datum)
          vervaldag['intrest_b'] = intrest_b(mogelijke_afpunt_datum)
          vervaldag['amount'] = vervaldag['intrest_a'] + vervaldag['intrest_b']
          vervaldag['te_betalen'] = open_value(mogelijke_afpunt_datum)
          if mogelijke_afpunt_datum<close_date:
            vervaldag['afpunt_datum'] = mogelijke_afpunt_datum
          else:
            vervaldag['afpunt_datum'] = None
          vervaldag_object = type('openstaande_vervaldag', (object,), vervaldag)
          vervaldagen.append(vervaldag_object)
          logger.debug('vervaldag : %s'%vervaldag)
      logger.debug('finished')
      return vervaldagen

    def get_facturen_voor_periode( self, periode ):
      return list( Factuur.query.filter( sql.and_( Factuur.dossier_id == self.id,
                                                   Factuur.datum < periode.startdatum ) ).all() )

    def get_theoretische_einddatum(self):
      startdatum = (self.startdatum)
      dyear, month = divmod(startdatum.month+self.goedgekeurde_looptijd,12)
      year = startdatum.year + dyear
      month = month + 1
      _first_day, max_day = calendar.monthrange(year, month)
      return date(year, month, min(startdatum.day,max_day))

    def get_theoretisch_openstaand_kapitaal(self):
      return self.get_theoretisch_openstaand_kapitaal_at(None)

    @property
    def theoretisch_openstaand_kapitaal(self):
        try:
          return self.get_theoretisch_openstaand_kapitaal_at(None)
        except Exception, e:
          logger.error( 'could not get theoretisch openstaand kapitaal', exc_info = e )

    def get_theoretisch_openstaand_kapitaal_at(self, datum=None):
        from periodieke_verichting import Vervaldag
        if not datum:
          datum = date.today()

        logger.debug('get theoretisch openstaand kapitaal dossier %i'%self.id)
        # bij beeindigd dossier zou er geen vordering meer mogen zijn
        if self.state=='ended' and (self.einddatum)<=(datum):
          return 0
        gb = self.get_goedgekeurd_bedrag_at(datum)
        # als er geen goedgekeurd bedrag is, was het dossier nog nt actief op
        # die datum
        if gb == None:
          return 0
        # zolang dossier in opnameperiode is, is de vordering het origineel
        # goedgekeurd bedrag
        if self.state=='opnameperiode':
          return gb.goedgekeurd_bedrag
        # zoek laatst geboekte vervaldag, als shortcut om vervaldagen niet opnieuw
        # te liggen uitrekenen, om openstaand saldo te bekomen
        laatste_vervaldag = Vervaldag.query.filter( sql.and_( Vervaldag.dossier == self,
                                                              Vervaldag.status != 'canceled',
                                                              Vervaldag.nummer > 0,
                                                              Vervaldag.doc_date <= datum ) ).order_by( Vervaldag.doc_date.desc() ).first()
        # wanneer er geen vervaldag te vinden is kan dit 2 mogelijkheden hebben
        if laatste_vervaldag == None:
          logger.debug('geen laatste vervaldag')
          # ofwel is dit dossier in principe al afgesloten, en vinden we geen vervaldag omdat die
          # historische info nt beschikbaar is
          if (self.theoretische_einddatum)<(datum):
            return 0
          # ofwel is er nog geen vervaldag geboekt, waardoor het openstaand saldo dus het originele bedrag is
          return gb.goedgekeurd_bedrag
        else:
          # als er wel een vervaldag is, kan dit de het openstaand kapitaal bevatten
          # tenzij de datum van de vervaldag voor of op de startdatum ligt, in dat geval is de vervaldag van voor
          # een aanpassing vh dossier.  de aanpassing gebeurt normaliter op de laatste vervaldag vh dossier
          if gb.aanvangsdatum >= laatste_vervaldag.doc_date:
            logger.debug('vervaldag dateert van voor startdatum')
            return gb.goedgekeurd_bedrag
          else:
            return laatste_vervaldag.openstaand_kapitaal - laatste_vervaldag.kapitaal

    def get_openstaand_kapitaal(self):
      return self.get_openstaand_kapitaal_at(None)

    @property
    def openstaand_saldo( self ):
        if self.nummer:
          return self.get_openstaand_kapitaal() - D( self.som_openstaande_betalingen )

    @property
    def loan_schedules(self):
        gbs = []
        for wijziging in self.wijziging:
          if wijziging.state in ['processed', 'ticked']:
            gbs.append(wijziging.vorig_goedgekeurd_bedrag)
        # voeg huidige gb laatst toe, aangezien een vorige dezelfde startdatum kan hebben
        gbs = [gb for gb in gbs if ((gb.state != 'draft') and ((gb.wijziging is not None) or (gb.beslissing is not None)))]
        gbs.append(self.goedgekeurd_bedrag)
        logger.debug('dossier %s gbs : %s'%(self.id,gbs))
        gbs.sort(key=lambda x:x.aanvangsdatum)
        return gbs

    def get_goedgekeurd_bedrag_at_as_objects(self, datum):
      """De id vh goedgekeurd bedrag dat actief was/is op een bepaalde datum of actief
      geworden is op die dag, return None als het dossier nog niet actief was op die
      datum, indien er meerdere zijn, return het laatste"""
      gbs = [gb for gb in self.loan_schedules if gb.aanvangsdatum and (gb.aanvangsdatum) <= datum ]
      logger.debug('filtered and sorted gbs : %s'%str(gbs))
      if not len(gbs):
        return None
      else:
        return gbs[-1]

    def get_goedgekeurd_bedrag_at(self, datum):
      gbs = self.get_goedgekeurd_bedrag_at_as_objects(datum)
      return gbs

    def get_einddatum_at(self, datum):
      gb = self.get_goedgekeurd_bedrag_at(datum)
      if gb:
          return gb.einddatum

    def get_openstaand_kapitaal_at(self, datum=None):
      # deze functie w gebruikt ih provisie rapport
      from .visitor import AbstractHypoVisitor
      vd, constants = get_dossier_bank()
      visitor = AbstractHypoVisitor()

      if datum == None:
        datum = datetime.date.today()

      year_context = vd.CreateYearContext(datum.year)
      balan = year_context.CreateBalan(False)

      nummer =  visitor.get_full_account_number_at( self.goedgekeurd_bedrag, datum )
      balance = sum( balan.GetBalance(nummer, month) for month in range(1, datum.month+1))
      # Venice might return numbers such as 1e-12

      return  D('%.2f'%balance)

    @property
    def som_openstaande_betalingen(self):
      return sum(((b.open_amount or 0) for b in self.openstaande_betaling), 0 )

    def get_akte_deprecated(self):
      beslissing = self.beslissing_nieuw
      return beslissing.akte[0].id

    @property
    def aktedatum_deprecated( self ):
        beslissing = self.beslissing_nieuw
        return beslissing.akte[0].datum_verlijden

    @property
    def betaling(self):
      """Zoek alle betalingen ivm dit dossier"""
      from vfinance.model.bank.entry import Entry
      if self.nummer == None:
          return []
      account_klant = int(settings.get( 'HYPO_ACCOUNT_KLANT', 400000000000 ) )
      return list( Entry.query.filter( Entry.account == str(account_klant+self.customer_number) ).all() )

    @property
    def openstaande_betaling(self):
      from vfinance.model.bank.entry import Entry
      if self.nummer == None:
          return []
      account_klant = int(settings.get( 'HYPO_ACCOUNT_KLANT', 400000000000 ) )
      return list( Entry.query.filter( sql.and_( Entry.account == str(account_klant+self.customer_number),
                                                 Entry.open_amount < 0,
                                                 Entry.venice_book != 'NewHy' ) ).all() )

    def get_som_openstaande_verrichtingen(self):
      return sum( (b.open_amount for b in self.betaling), 0 )

    def get_bijkomende_waarborgen(self):
      ids = [self.id]
      query = """select hypo_dossier.id as id,
                        hypo_bijkomende_waarborg.id as waarborg_id
      from hypo_bijkomende_waarborg
      join hypo_bijkomende_waarborg_hypotheek on (hypo_bijkomende_waarborg_hypotheek.bijkomende_waarborg=hypo_bijkomende_waarborg.id)
      join hypo_dossier on (hypo_dossier.aanvraag=hypo_bijkomende_waarborg_hypotheek.hypotheek)
      where hypo_dossier.id in (%s)
      """%(','.join(list(str(id) for id in ids)))
      result = []
      for row in orm.object_session( self ).execute( sql.text( query ) ):
        result.append(row.waarborg_id)
      return result

    @property
    def name(self):
        return unicode(self.nummer) + ' ' + ', '.join([n for n in [self.borrower_1_name, self.borrower_2_name] if n is not None])

    @property
    def wettelijk_kader( self ):
        return self.aanvraag.wettelijk_kader

    class Admin(VfinanceAdmin):
        list_display =  ['full_number', 'borrower_1_name', 'borrower_2_name',
                         'startdatum', 'state', 'rappel_level']
        list_filter = ['state', list_filter.ComboBoxFilter('company_id')]
        list_search = ['nummer', 'roles.natuurlijke_persoon.name', 'roles.rechtspersoon.name']
        list_actions = [SyncVenice(), DossierSummary(), CreateReminder(), CreateCustomer()]
        form_state = 'maximized'
        form_actions = [ SyncVenice(),
                         CreateReminder(),
                         DossierSummary(),
                         DossierSheet(),
                         MortgageTable(),
                         ]
        form_display =  forms.Form([forms.TabForm([(_('Algemeen'), forms.Form(['name',
                                                                               'goedgekeurd_bedrag',
                                                                               'aanvraag',
                                                                               'startdatum',
                                                                               'originele_startdatum',
                                                                               'einddatum',
                                                                               'state','openstaand_saldo','waarborgen','wijziging','roles',forms.GroupBoxForm(_('Nationale bank'),['kredietcentrale_gesignaleerd','kredietcentrale_update',], columns=2),'origin',], columns=2)),
                                                   (_('Vervaldagen'), forms.Form(['repayments','openstaande_betaling',], columns=2)),
                                                   (_('Rappel brieven'), forms.Form(['text', 'rappelbrief','melding_nbb'], columns=2)),
                                                   (_('Facturen'), forms.Form(['factuur',], columns=2)),(_('Kosten'), forms.Form(['dossier_kost',], columns=2)),
                                                   (_('Verichtingen'), forms.Form(['betaling',], columns=2)),
                                                   (_('Commercieel'), forms.Form(['korting', 'brokers'], columns=2)),
                                                   (_('Waarborgen'), forms.Form(['aktes','bijkomende_waarborgen'], columns=2)),
                                                   (_('Settings'), forms.Form(['dekking','domiciliering','direct_debit_mandates','applied_functional_settings', 'applied_features'], columns=2)),
#                                                   (_('Deprecated'), forms.Form(['bijkomende_waarborgen_deprecated','borgsteller_deprecated',], columns=2)),
                                                   ], position=forms.TabForm.WEST)], columns=2)
        field_attributes = {'full_number': {'editable':False, 'name':_('Dossier')},
                            'origin':{'editable':True, 'name':_('Originele dossier nummer')},
                            'applied_functional_settings':{'name':_('Settings')},
                            'applied_features':{'name':_('Features')},
                            'company_id':{'name': _('Maatschappij')},
                            'domiciliering':{'editable':True, 'name':_('Gebruik domiciliering')},
                            'originele_startdatum':{'editable':False, 'name':_('Originele start datum')},
                            'goedgekeurde_rente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde rente')},
                            'kredietcentrale_update':{'editable':True, 'name':_('Laatste update van signalisatie')},
                            'taal':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Taal')},
                            'korting':{'editable':True, 'name':_('Kortingen')},
                            'beslissing_nieuw':{'editable':False, 'delegate':delegates.Many2OneDelegate, 'name':_('Beslissing')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'melding_nbb':{'editable':True, 'name':_('Meldingen Nationale Bank')},
                            'aktedatum_deprecated':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Aktedatum')},
                            'openstaande_betaling':{'editable':False,
                                                    'delegate':delegates.One2ManyDelegate,
                                                    'python_type':list,
                                                    'target':'Entry',
                                                    'name':_('Openstaande betalingen')},
                            'goedgekeurde_opname_periode':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opname periode (maanden)')},
                            'som_openstaande_verrichtingen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Openstaande verrichtingen')},
                            'goedgekeurde_reserverings_provisie':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde reserveringsprovisie')},
                            'startdatum':{'editable':False, 'name':_('Start datum')},
                            'aktes':{'editable':True, 'name':_('Aktes')},
                            'goedgekeurd_bedrag':{'editable':False, 'name':_('Goedgekeurd bedrag')},
                            'factuur':{'editable':True, 'name':_('Facturen')},
                            'bijkomende_waarborgen_deprecated':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Bijkomende waarborgen')},
                            'goedgekeurd_terugbetaling_start':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Uitstel Betaling (maanden)')},
                            'aanvraag':{'editable':False, 'name':_('Aanvraag document')},
                            'theoretische_einddatum':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Theoretische einddatum')},
                            'openstaand_kapitaal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Openstaand kapitaal')},
                            'theoretisch_openstaand_kapitaal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Theoretisch openstaand kapitaal')},
                            'goedgekeurd_type_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurd type aflossing')},
                            'waarborg_derden':{'editable':True, 'name':_('Gewaarborgd door derden')},
                            'waarborgen_venale_verkoop':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Waarborg bij vrijwillige verkoop')},
                            'som_openstaande_betalingen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Openstaande betalingen')},
                            'betaling':{'editable':False,
                                        'delegate':delegates.One2ManyDelegate,
                                        'python_type':list,
                                        'target':'Entry',
                                        'name':_('Betalingen')},
                            'goedgekeurd_bedrag_nieuw':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurd bedrag')},
                            'goedgekeurde_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde aflossing')},
                            'dekking':{'editable':True, 'name':_('Dekkingen')},
                            'rappel_datum':{'editable':True, 'name':_('Datum rappel')},
                            'hypothecaire_waarborgen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Hypothecaire waarborgen')},
                            'wettelijk_kader':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Wettelijk kader')},
                            'bedrag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Ontleend bedrag')},
                            'goedgekeurd_terugbetaling_interval':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Terugbetaling')},
                            'goedgekeurde_looptijd':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde looptijd (maanden)')},
                            'einddatum':{'editable':False, 'name':_('Einddatum')},
                            'state':{'editable':False, 'name':_('Status'), 'choices':[('opnameperiode', 'In opname periode'), ('running', 'Lopende'), ('ended', 'Beeindigd')]},
                            'waarborgen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('In aanmerking te nemen waarborgen')},
                            'borgsteller_deprecated':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Borgstellers')},
                            'akte_deprecated':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Akte')},
                            'bijkomende_waarborgen':{'editable':True, 'name':_('Bijkomende waarborgen')},
                            'borgstellers':{'editable':True, 'name':_('Borgstellers')},
                            'maatschappij':{'editable':False, 'name':_('Maatschappij')},
                            'vervaldag':{'editable':True, 'name':_('Vervaldagen')},
                            'kredietcentrale_gesignaleerd':{'editable':True, 'name':_('Gesignaleerd bij Kredietcentrale')},
                            'rappelbrief':{'editable':True, 'name':_('Rappelbrieven')},
                            'nummer':{'editable':False, 'name':_('Dossier nummer')},
                            'goedgekeurde_opname_schijven':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opname schijven (maanden)')},
                            'domiciliering_code':{'editable':True, 'name':_('Code voor domiciliering')},
                            'dossier_kost':{'editable':True, 'name':_('Kosten')},
                            'waarborg_bijkomend_waarde':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Waarde bijkomende waarborgen')},
                            'rappel_level':{'editable':True, 'name':_('Rappel niveau'), 'choices':[(1, 'Normaal'), (2, 'Streng'), (3, 'Ingebrekestelling'), (4, 'Opzegging krediet')]},
                            'openstaand_saldo':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Openstaand saldo')},
                            'wijziging':{ 'editable':True,
                                          'name':_('Wijzigingen'),
                                          'python_type':list,
                                          'delegate':delegates.One2ManyDelegate,
                                          'target':'Wijziging' },
                            'ontlener_name_1':{'name':_('Eerste ontlener')},
                            'ontlener_name_2':{'name':_('Tweede ontlener')},
                           }
        
        def get_query(self, *args, **kwargs):
          query = VfinanceAdmin.get_query(self, *args, **kwargs)
          query = query.options(orm.subqueryload('roles'))
          query = query.options(orm.subqueryload('roles.natuurlijke_persoon'))
          query = query.options(orm.subqueryload('roles.rechtspersoon'))
          
          return query

Dossier.repayments = orm.relationship(InvoiceItem,
                                      order_by=[InvoiceItem.id],
                                      primaryjoin=sql.and_(orm.foreign(InvoiceItem.dossier_id)==Dossier.id,
                                                            sql.or_(InvoiceItem.row_type=='repayment',
                                                                    InvoiceItem.row_type=='reservation')))

Dossier.rappelbrief = orm.relationship(InvoiceItem,
                                       order_by=[InvoiceItem.id],
                                       primaryjoin=sql.and_(orm.foreign(InvoiceItem.dossier_id)==Dossier.id,
                                                            InvoiceItem.row_type=='reminder'))

Dossier.dossier_kost = orm.relationship(InvoiceItem,
                                        order_by=[InvoiceItem.id],
                                        primaryjoin=sql.and_(orm.foreign(InvoiceItem.dossier_id)==Dossier.id,
                                                             InvoiceItem.row_type=='invoice_item'))

#  ROUND_HALF_EVEN
#  ROUND_HALF_UP
korting_types = [('per_aflossing', 'Per aflossing'), ('per_jaar', 'Per jaar'), ('pret_jeunes', 'Pret Jeunes')]
#  ROUND_HALF_DOWN
#  ROUND_05UP
