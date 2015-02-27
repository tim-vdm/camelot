import sqlalchemy.types
import os

from sqlalchemy import sql, orm, schema, func

from camelot.core.conf import settings
from camelot.core.orm import (Entity, OneToMany, ManyToOne, 
                              using_options, ColumnProperty)
from camelot.admin.action import list_filter
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.view import action_steps
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _
from camelot.core.exception import UserException
import camelot.types

import logging
logger = logging.getLogger( 'vfinance.model.hypo.akte' )

from vfinance.model.hypo.hypotheek import Hypotheek, GoedAanvraag
from vfinance.model.hypo.beslissing import Beslissing

from dossier import Dossier
from state import ChangeState
from .notification.mortgage_table import MortgageTable
from .notification.deed_proposal import DeedProposal
from .summary.notary_settlement import NotarySettlement
from .visitor.abstract import AbstractHypoVisitor
from ...connector.accounting import AccountingSingleton, CreateAccountRequest
from vfinance.admin.vfinanceadmin import VfinanceAdmin

akte_header_desc = """[$Global]
CliVersion=2

[$Import.SND]
@SND.BookDate=%(snd_bookdate_length)s;1;DMYY
@SND.Remark=%(snd_remark_length)s;1
@SND.Book=%(snd_book_length)s;1

"""

akte_header_data = """%(snd_bookdate)s;%(snd_remark)s;%(snd_book)s\n"""

akte_line_desc = """
[$Import.ENT]
@ENT.AmountDocC=%(ent_amountdocc_length)s;1;2
@ENT.Account=%(ent_account_length)s;1
@ENT.Remark=%(ent_remark_length)s;1
"""

akte_line_data = """%(ent_amountdocc)s;%(ent_account)s;%(ent_remark)s\n"""

class Cancel( ChangeState ):
    
    def __init__( self ):
        super( Cancel, self ).__init__( _('Cancel'), 'canceled', ['pending', 'valid'] )

class Payed( ChangeState ):
    
    def __init__( self ):
        super( Payed, self ).__init__( _('Betaald aan notaris'), 'payed', ['valid'] )
    
class Valid( ChangeState ):    
    
    def __init__( self ):
        super( Valid, self ).__init__( _('Juridisch goedgekeurd'), 'valid', ['pending'] )
    
class Pending( ChangeState ):
    
    def __init__( self ):
        super( Pending, self ).__init__( _(u'Wachtend'), 'pending', ['valid', 'payed', 'canceled']  )
                         
class CreateDossiers( ChangeState ):
    """Create the Dossier, the CustomerAccount and the SupplierAccounts.
    All in one nifty transaction to make sure both VF and Venice are in
    a consistent state.
    """
    
    def __init__( self ):
        super( CreateDossiers, self ).__init__( _('Maak dossier'), 'processed', ['payed'] )
        
    def change_state( self, model_context, akte ):

        if not akte.datum_verlijden:
            raise UserException('Datum verlijden van akte moet ingevuld zijn')
        
        accounting = AccountingSingleton()
        session = model_context.session
        visitor = AbstractHypoVisitor()

        with accounting.begin(session):
            dossier_step = int( settings.HYPO_DOSSIER_STEP )
            hypotheek = akte.beslissing.hypotheek
            rank = hypotheek.rank
            company_id = hypotheek.company_id
            if dossier_step != 0:
                last_dossier_nummer = session.query( sql.func.max( Dossier.nummer ) ).filter(Dossier.company_id==company_id).scalar() or 0
                dossier_number = last_dossier_nummer + dossier_step
            else:
                dossier_number = hypotheek.nummer
            #
            # create dossier, customer and account
            #
            for i, goedgekeurd_bedrag in enumerate(akte.beslissing.goedgekeurd_bedrag):
                if goedgekeurd_bedrag.state != 'processed':
                    goegekeurd_bedrag_dossier_number = dossier_number + i*dossier_step
                    dossier = goedgekeurd_bedrag.create_dossier(akte.datum_verlijden, dossier_nummer=goegekeurd_bedrag_dossier_number, dossier_rank=rank)
                    roles = list(hypotheek.get_roles_at(hypotheek.aanvraagdatum, 'borrower'))
                    customer_request = visitor.create_customer_request(goedgekeurd_bedrag, roles)
                    accounting.register_request(customer_request)
                    account_number = int(visitor.get_full_account_number_at(goedgekeurd_bedrag, akte.datum_verlijden))
                    account_name = u'%s %s %s'%(hypotheek.borrower_1_name or '',
                                                hypotheek.borrower_2_name or '',
                                                dossier.full_number)
                    accounting.register_request(CreateAccountRequest(from_number=account_number,
                                                                     thru_number=account_number,
                                                                     name=account_name))
            #
            # create suppliers
            #
            for schedule in akte.beslissing.goedgekeurd_bedrag:
                broker_relation = schedule.dossier.get_broker_at(akte.datum_verlijden)
                for supplier_type in ['broker', 'master_broker']:
                    supplier_request = visitor.create_supplier_request(schedule, broker_relation, supplier_type)
                    if supplier_request is not None:
                        accounting.register_request(supplier_request)
            for step in super( CreateDossiers, self ).change_state( model_context, akte ):
                yield step
            yield action_steps.FlushSession(session)
            
class CreateMortgage( ChangeState ):
    
    def __init__( self ):
        super( CreateMortgage, self ).__init__( _('Boek lening'), 'booked', ['processed'] )
        
    def change_state( self, model_context, akte ):
        from integration.venice.venice import d2v
        from vfinance.model.bank.venice import get_dossier_bank
        visitor = AbstractHypoVisitor()
        venice, constants = get_dossier_bank()

        with model_context.session.begin(): 
            a = akte
            for step in super( CreateMortgage, self ).change_state( model_context, akte ):
                yield step
    
            name = a.name.encode( 'ascii', errors='ignore' )
            remark = 'verlijden %s'%name
            logger.info( remark )
            header_dict = { 'snd_bookdate':d2v( a.datum_verlijden ),
                            'snd_remark': remark.encode( 'ascii', errors='ignore' ),
                            'snd_book':'NewHy' }
            line_dicts = []
            for i, gb in enumerate( akte.beslissing.goedgekeurd_bedrag ):
                product = gb.product
                customer = visitor.get_customer_at( gb, a.datum_verlijden )
                full_account_number = visitor.get_full_account_number_at( gb, a.datum_verlijden )
                customer_account = customer.full_account_number
                line_dicts.append(dict(ent_amountdocc=gb.goedgekeurd_bedrag, ent_remark=remark, ent_account=full_account_number))
                if i==0:
                  bedrag = gb.goedgekeurd_bedrag + (a.ontvangen_voorschot or 0) - (a.dossierkosten or 0) - (a.schattingskosten or 0) - (a.verzekeringskosten or 0)
                  line_dicts.append(dict(ent_amountdocc=(a.ontvangen_voorschot), ent_remark='voorschot %s'%name, ent_account=product.get_account_at('ontvangen_voorschot', a.datum_verlijden) ))
                  line_dicts.append(dict(ent_amountdocc=(a.dossierkosten*-1), ent_remark='dossierkosten %s'%name, ent_account=product.get_account_at('dossierkosten', a.datum_verlijden) ))
                  line_dicts.append(dict(ent_amountdocc=(a.schattingskosten*-1), ent_remark='schattingskosten %s'%name, ent_account=product.get_account_at('schattingskosten', a.datum_verlijden) ))
                  line_dicts.append(dict(ent_amountdocc=(a.verzekeringskosten*-1), ent_remark='verzekeringskosten %s'%name, ent_account=customer_account))
                else:
                  bedrag = gb.goedgekeurd_bedrag
                line_dicts.append(dict(ent_amountdocc=(bedrag*-1), ent_remark=remark.encode( 'ascii', errors='ignore' ), ent_account=customer_account))
            (name_data, name_desc) = venice.create_files(akte_header_desc, akte_line_desc, akte_header_data, akte_line_data, header_dict, line_dicts)
            context = venice.CreateYearContext( a.datum_verlijden.year )
            sndry = context.CreateSndry( True )
            sys_num, doc_num = 0, 0
            sys_num, doc_num = venice.import_files(sndry, name_desc, name_data)
            logger.info('geboekt met sys_num : %s'%sys_num) 
            akte.venice_id = sys_num
            akte.venice_doc = doc_num
            yield action_steps.FlushSession( model_context.session )
        
class Akte( Entity ):
    """
    Eenmaal een beslissing genomen wordt gewacht tot wanneer de akte wordt verleden, na het verlijden
    van de akte stuurt de notaris de grosse (samenvatting met bewijskracht) naar de hypotheeknemer
    """
    
    def __getattr__( self, name ):
        if name in ['datum', 'name', 'ontvangen_voorschot', 'schattingskosten', 'verzekeringskosten', 'achterstal', 'achterstal_rekening', 'goedgekeurd_totaal', 'dossierkosten', 'saldo']:
            if self.beslissing == None:
                return None
            return getattr( self.beslissing, name )
        raise AttributeError( name )
    
    using_options(tablename = 'hypo_akte')
    beslissing_id  =  schema.Column(sqlalchemy.types.Integer(), name='beslissing', nullable=True, index=True)
    beslissing  =  ManyToOne('vfinance.model.hypo.beslissing.Beslissing', field=beslissing_id, backref='akte')
    
    samenvatting  =  schema.Column(camelot.types.File(upload_to=os.path.join('hypo.akte', 'samenvatting')), nullable=True)
    juridische_goedkeuring  =  schema.Column(camelot.types.File(upload_to=os.path.join('hypo.akte', 'juridische_goedkeuring')), nullable=True)
    datum_verlijden  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    datum_grossen  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    venice_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    venice_doc  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True, default=unicode('pending'))
    handlichting  =  OneToMany('vfinance.model.hypo.akte.Handlichting', inverse='akte')
    hypothecaire_rente = schema.Column(sqlalchemy.types.Numeric(precision=5, scale=4)) # source: HY_HypothecaireRente from HypoSoft Lening table
    kantoor = schema.Column(sqlalchemy.types.Unicode(30)) # source: HY_Kantoor from HypoSoft Lening table
    boek = schema.Column(sqlalchemy.types.Unicode(15)) # source: HY_Boek from HypoSoft Lening table
    nummer = schema.Column(sqlalchemy.types.Unicode(15)) # source: HY_Nummer from HypoSoft Lening table
    rang = schema.Column(sqlalchemy.types.Integer(), nullable=False, default=1)

    def __unicode__(self):
        return self.name

    @property
    def full_number(self):
        if self.beslissing is not None:
            return self.beslissing.full_number

    @property
    def borrower_1_name(self):
        if self.beslissing is not None:
            return self.beslissing.borrower_1_name
                           
    @property
    def borrower_2_name(self):
        if self.beslissing is not None:
            return self.beslissing.borrower_2_name

    class Admin(VfinanceAdmin):
        verbose_name = _('Akte')
        verbose_name_plural = _('Aktes')
        list_display =  ['datum_verlijden',
                         'state',
                         'full_number',
                         'borrower_1_name',
                         'borrower_2_name',
                         'goedgekeurd_totaal',
                         'ontvangen_voorschot',
                         'gehypothekeerd_totaal',
                         'gemandateerd_totaal']
        list_filter = ['state', list_filter.ComboBoxFilter('beslissing.hypotheek.company_id', verbose_name=_('Maatschappij'))]
        list_search = ['beslissing.hypotheek.aanvraagnummer', 'beslissing.hypotheek.roles.natuurlijke_persoon.name', 'beslissing.hypotheek.roles.rechtspersoon.name']
        form_state = 'maximized'
        form_actions = [ Cancel(), Payed(), Valid(), Pending(), 
                         CreateDossiers(), 
                         CreateMortgage(), 
                         MortgageTable(),
                         DeedProposal(),
                         NotarySettlement(), ]        
        list_actions = [NotarySettlement()]
        form_display =  forms.Form([forms.TabForm([(_('Aanvragers'), forms.Form(['beslissing','datum_verlijden','juridische_goedkeuring','samenvatting','datum_grossen',
                                                                                 forms.GroupBoxForm(_('Hypotheek'),['gehypothekeerd_totaal','gemandateerd_totaal',], columns=2),
                                                                                 forms.GroupBoxForm(_('Boeking'),[forms.GroupBoxForm(_('Debet'),['goedgekeurd_totaal','ontvangen_voorschot',], columns=2),
                                                                                                                  forms.GroupBoxForm(_('Credit'),['dossierkosten','schattingskosten','verzekeringskosten',
                                                                                                                                                  'achterstal','achterstal_rekening',], columns=2),], columns=2),
                                                                                 forms.GroupBoxForm(_('Status'),['state',], columns=2),
                                                                                 forms.GroupBoxForm(_('Venice'),['venice_id','venice_doc',], columns=2),], columns=2)),
                                                   (_('Handlichting'), forms.Form(['handlichting',], columns=2)),
                                                   (_('Hypotheek'), forms.Form(['hypothecaire_rente',
                                                                                'kantoor',
                                                                                'boek',
                                                                                'nummer',
                                                                                'rang'], columns=2)), 
                                                   (_('Dossiers'), forms.Form(['dossiers',], columns=2)),], position=forms.TabForm.WEST)], columns=2)
        field_attributes = {'juridische_goedkeuring':{'editable':True, 'name':_('Goedkeuring door notaris')},
                            'beslissing':{'editable':False, 'name':_('Hypotheek beslissing')},
                            'handlichting':{'editable':True, 'name':_('Handlichtingen')},
                            'gehypothekeerd_totaal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Gehypothekeerd totaal'), 'precision':2},
                            'datum_grossen':{'editable':True, 'name':_('Grosse ontvangen op')},
                            'samenvatting':{'editable':True, 'name':_('Grosse')},
                            'saldo':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Saldo te betalen')},
                            'achterstal_rekening':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Rekening achterstal')},
                            'schattingskosten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Schattingskosten')},
                            'verzekeringskosten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Verzekeringskosten')},
                            'venice_doc':{'editable':False, 'name':_('Document Nummer Venice')},
                            'dossierkosten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Dossierkosten')},
                            'name':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Naam')},
                            'state':{'editable':False, 'name':_('Status'), 'choices':[('pending', 'Wachtend'), 
                                                                                      ('valid', 'Juridisch goedgekeurd'), 
                                                                                      ('payed', 'Betaald'), 
                                                                                      ('processed', 'Dossiers aangemaakt'), 
                                                                                      ('booked', 'Verleden'), 
                                                                                      ('canceled', 'Geannulleerd')]},
                            'datum':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Beslissingsdatum')},
                            'achterstal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Achterstal')},
                            'datum_verlijden':{'editable':True, 'name':_('Datum verlijden')},
                            'gemandateerd_totaal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Gemandateerd totaal')},
                            'ontvangen_voorschot':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Ontvangen voorschot')},
                            'dossiers':{'editable':False, 'name':_('Dossiers')},
                            'goedgekeurd_totaal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurd totaal')},
                            'venice_id':{'editable':False, 'name':_('Systeem Nummer Venice')},
                            'borrower_1_name':{'editable':False, 'minimal_column_width':30, 'name':_('Naam eerste ontlener')},
                            'borrower_2_name':{'editable':False, 'minimal_column_width':30, 'name':_('Naam tweede ontlener')},}

        def get_query(self, *args, **kwargs):
            query = VfinanceAdmin.get_query(self, *args, **kwargs)
            query = query.options(orm.joinedload('beslissing'))
            query = query.options(orm.joinedload('beslissing.hypotheek'))
            query = query.options(orm.joinedload('beslissing.hypotheek.roles'))
            query = query.options(orm.joinedload('beslissing.goedgekeurd_bedrag'))
            query = query.options(orm.undefer('beslissing.hypotheek.roles.name'))
            return query
        
Akte.gemandateerd_totaal = orm.column_property(
    sql.select([func.sum(GoedAanvraag.hypothecair_mandaat)],
               sql.and_(Akte.beslissing_id==Beslissing.id,
                        Beslissing.hypotheek_id==Hypotheek.id,
                        Hypotheek.id==GoedAanvraag.hypotheek_id)
               ), 
    deferred=True
    )

    
class Handlichting(Entity):
    """
    Volledige of partiele handlichting kan worden gegeven op een verleden akte, dit wijzigd het
    gehypotheceerd totaal.  Handlichting wordt enkel gegeven op de hypothecaire inschrijving, niet op
    het hypothecair mandaat
    """
    
    using_options(tablename = 'hypo_handlichting')
    akte_id  =  schema.Column(sqlalchemy.types.Integer(), name='akte', nullable=False, index=True)
    akte  =  ManyToOne('vfinance.model.hypo.akte.Akte', field=akte_id)
    datum_verlijden  =  schema.Column(sqlalchemy.types.Date(), nullable=False)
    bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False)
    document  =  schema.Column(camelot.types.File(upload_to=os.path.join('hypo.handlichting', 'document')), nullable=True)

    def __getattr__(self, name):
        if name in ['name']:
            return getattr(self.akte, name)
        raise AttributeError()
    
    def __unicode__(self):
        return self.name

    class Admin(EntityAdmin):
        verbose_name = _('Handlichting')
        verbose_name_plural = _('Handlichtingen')
        list_display =  ['name', 'datum_verlijden', 'bedrag']
        form_display =  forms.Form(['akte','datum_verlijden','bedrag','document',], columns=2)
        field_attributes = {
                            'datum_verlijden':{'editable':True, 'name':_('Datum verlijden')},
                            'bedrag':{'editable':True, 'name':_('Bedrag')},
                            'akte':{'editable':True, 'name':_('Akte')},
                            'name':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Naam')},
                            'document':{'editable':True, 'name':_('Document')},
                           }
        
def query_gehypothekeerd_totaal(self, AK):
    
    return sql.select([func.sum(GoedAanvraag.hypothecaire_inschrijving)
                        - func.coalesce((sql.select([func.sum(Handlichting.bedrag)], Handlichting.akte_id==AK.id).as_scalar()), 0.0)
                    ],
                    sql.and_(AK.beslissing_id==Beslissing.id,
                             Beslissing.hypotheek_id==Hypotheek.id,
                             GoedAanvraag.hypotheek_id==Hypotheek.id,
                             AK.id==self.id)
                   ).group_by(AK.id)

Akte.gehypothekeerd_totaal = ColumnProperty(lambda cls: query_gehypothekeerd_totaal(cls, orm.aliased(Akte)), deferred=True)
