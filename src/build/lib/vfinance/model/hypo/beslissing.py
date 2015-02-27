import calendar
import datetime
from decimal import Decimal as D
import logging
import math
import os


import sqlalchemy.types
from sqlalchemy import sql, orm, schema
from sqlalchemy.ext import hybrid

from camelot.core.orm import ( Entity, OneToMany, ManyToOne, 
                               using_options, ColumnProperty )
from camelot.admin.entity_admin import EntityAdmin
from camelot.admin.action import CallMethod, list_filter
from camelot.view.controls import delegates
from camelot.view import forms
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import transaction
import camelot.types

from mortgage_table import hoogste_aflossing
from summary.decision_document import DecisionDocument
from ..bank.financial_functions import ONE_MILLIONTH
from ..bank.product import Product
from ..bank.schedule import ScheduleMixin
from .constants import hypo_terugbetaling_intervallen, hypo_types_aflossing
from .hypotheek import Bedrag, Hypotheek, HypoApplicationMixin
from vfinance.admin.vfinanceadmin import VfinanceAdmin

logger = logging.getLogger('vfinance.model.hypo.beslissing')

modaliteiten1 = ['rente', 'opname_periode', 'opname_schijven', 'reserverings_provisie', 'aflossing', 'intrest_a', 'intrest_b', 'jaarrente']
modaliteiten2 = ['terugbetaling_start', 'bedrag']
modaliteiten3 = ['looptijd']
modaliteiten4 = ['type_aflossing', 'type_vervaldag', 'terugbetaling_interval']
variabiliteit_type_modaliteiten = [('eerste_herziening', 'Eerste herziening na (maanden)'), ('volgende_herzieningen', 'Daarna herzieningen om de (maanden)'), ('eerste_herziening_ristorno', 'Eerste herziening ristorno na (maanden)'), ('volgende_herzieningen_ristorno', 'Daarna herzieningen ristorno om de (maanden)')]
#  create_get_rente_wijziging
variabiliteit_historiek_modaliteiten = [('referentie_index', 'Referentie index'), ('minimale_afwijking', 'Minimale afwijking'), ('maximale_stijging', 'Maximale stijging'), ('maximale_daling', 'Maximale daling'), ('maximale_spaar_ristorno', 'Maximale spaar ristorno'), ('maximale_product_ristorno', 'Maximale ristorno gebonden producten'), ('maximale_conjunctuur_ristorno', 'Maximale conjunctuur ristorno')]

class Beslissing(Entity, HypoApplicationMixin):
    using_options(tablename='hypo_beslissing')
    goedgekeurde_dossierkosten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True)
    datum  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    opmerkingen  =  schema.Column(camelot.types.RichText(), nullable=True)
    datum_voorwaarde  =  schema.Column(sqlalchemy.types.Date(), nullable=True)
    goedgekeurd_bedrag  =  OneToMany('vfinance.model.hypo.beslissing.GoedgekeurdBedrag', inverse='beslissing', order_by='id')
    beslissingsdocument  =  schema.Column(camelot.types.File(upload_to=os.path.join('hypo.beslissing', 'beslissingsdocument')), nullable=True)
    #replaced with backref akte  =  OneToMany('vfinance.model.hypo.akte.Akte', inverse='beslissing')
    nodige_schuldsaldo  =  OneToMany('vfinance.model.hypo.beslissing.NodigeSchuldsaldo', inverse='beslissing')
    state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False)
    hypotheek_id  =  schema.Column(sqlalchemy.types.Integer(), name='hypotheek', nullable=False, index=True)
    hypotheek  =  ManyToOne(Hypotheek, field=hypotheek_id)
    aanvaarding  =  OneToMany('vfinance.model.hypo.aanvaarding.Aanvaarding', inverse='beslissing')
    correctie_dossierkosten  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=True, default=0)

    @property
    def company_id(self):
        if self.hypotheek is not None:
            return self.hypotheek.company_id

    @property
    def nummer(self):
        if self.hypotheek is not None:
            return self.hypotheek.nummer
        
    @property
    def rank(self):
        if self.hypotheek is not None:
            return self.hypotheek.rank

    @property
    def borrower_1_name(self):
        if self.hypotheek is not None:
            return self.hypotheek.borrower_1_name

    @property
    def borrower_2_name(self):
        if self.hypotheek is not None:
            return self.hypotheek.borrower_2_name

    @property
    def name(self):
        if self.hypotheek is not None:
            return self.hypotheek.name

    @property
    def voorgestelde_dossierkosten(self):
        from dossierkosten import DossierkostHistoriek
        if self.datum_voorwaarde:
            return DossierkostHistoriek.dossierkost_from_beslissing_and_datum( self, self.datum_voorwaarde )

    @property
    def terugbetalingscapaciteit(self):
        return (self.totaal_inkomsten or 0) - (self.totaal_lasten or 0) - (self.levensonderhoud or 0) - (self.correctie_levensonderhoud or 0) - (self.maandlast_lopend_krediet or 0)

    @property
    def maandelijkse_basis_aflossing(self):
        return sum( gb.maandelijkse_basis_aflossing for gb in self.goedgekeurd_bedrag )

    @property
    def goedgekeurde_aflossing(self):
        return sum( gb.goedgekeurde_aflossing for gb in self.goedgekeurd_bedrag )

    @property
    def maandelijkse_voorgestelde_aflossing(self):
        return sum( gb.maandelijkse_voorgestelde_aflossing for gb in self.goedgekeurd_bedrag )
    
    @property
    def maandelijkse_goedgekeurde_aflossing(self):
        return sum( (gb.maandelijkse_goedgekeurde_aflossing or 0) for gb in self.goedgekeurd_bedrag )

    @property
    def goedgekeurd_totaal(self):
        return sum( gb.goedgekeurd_bedrag for gb in self.goedgekeurd_bedrag )

    @property
    def terugbetalingsratio(self):
        return {True:lambda self:100, False:lambda self:100*self.maandelijkse_basis_aflossing/self.terugbetalingscapaciteit}[self.terugbetalingscapaciteit==0](self)

    @property
    def voorgestelde_terugbetalingsratio(self):
        return {True:lambda self:100, False:lambda self:100*self.maandelijkse_voorgestelde_aflossing/D(self.terugbetalingscapaciteit)}[self.terugbetalingscapaciteit==0](self)

    @property
    def goedgekeurde_terugbetalingsratio(self):
        return {True:lambda self:100, False:lambda self:100*self.maandelijkse_goedgekeurde_aflossing/self.terugbetalingscapaciteit}[self.terugbetalingscapaciteit==0](self)

    
    @property
    def quotiteit(self):
        if self.goedgekeurd_totaal != None and self.waarborgen != None:
            return {True:lambda self:100, False:lambda self:100*(self.goedgekeurd_totaal/self.waarborgen)}[self.waarborgen==0](self)

    @property
    def dossierkosten(self):
        return (self.voorgestelde_dossierkosten or 0) + (self.correctie_dossierkosten or 0)

    @property
    def saldo(self):
        return self.goedgekeurd_totaal + self.ontvangen_voorschot - self.dossierkosten - self.schattingskosten - self.verzekeringskosten - self.achterstal

    def __unicode__(self):
        if self.hypotheek:
            return unicode(self.hypotheek)
        return ''

    @transaction
    def button_maak_voorstel(self):
        self.maak_voorstel()
        
    def maak_voorstel(self):
        from ..bank.index import IndexHistory
        b = self
        logger.debug('maak voorstel voor hypotheek %s'%b.name)
        if b.hypotheek:
            for gevraagd_bedrag in b.hypotheek.gevraagd_bedrag:
                logger.debug('evalueer gevraagd bedrag %s'%gevraagd_bedrag.bedrag)
                gekoppeld = False
                for gb in b.goedgekeurd_bedrag:
                    if gb.bedrag.id==gevraagd_bedrag.id:
                        logger.debug('reeds gekoppeld')
                        gekoppeld = True
                if not gekoppeld:
                    logger.debug('koppel nieuw goedgekeurd bedrag')
                    gb_data = {'bedrag_id':gevraagd_bedrag.id,
                               'goedgekeurd_bedrag':gevraagd_bedrag.bedrag,
                               'beslissing':b,
                               'type':'nieuw',
                               'product':gevraagd_bedrag.product}
                    product = gevraagd_bedrag.product
                    for attr,_desc in variabiliteit_type_modaliteiten:
                        feature = gevraagd_bedrag.get_applied_feature_at(
                            b.datum_voorwaarde,
                            b.hypotheek.aktedatum,
                            gevraagd_bedrag.bedrag,
                            attr)
                        if feature.value != None:
                            gb_data['voorgestelde_%s'%attr] = feature.value
                    product_index = product.get_index_type_at(b.datum_voorwaarde, 'interest_revision')
                    if product_index is not None:
                        gb_data['voorgesteld_index_type'] = product_index
                        index_delta = 2
                        index_datum = b.datum_voorwaarde
                        index_datum = datetime.date(day=1,
                                                    month=index_datum.month-index_delta+{True:12,False:0}[index_datum.month<=index_delta],
                                                    year=index_datum.year-{True:index_delta,False:0}[index_datum.month<=index_delta])
                        index = IndexHistory.query.filter( sql.and_( IndexHistory.described_by == gb_data['voorgesteld_index_type'],
                                                                     IndexHistory.from_date <= index_datum) ).order_by( IndexHistory.from_date.desc() ).first()
                        gb_data['voorgestelde_referentie_index'] = '%.5f'%index.value #@todo: this should all be decimal
                    logger.debug('create gb : %s'%str(gb_data))
                    gb = GoedgekeurdBedrag( **gb_data )
                    gb.flush()
            for aanvrager in b.hypotheek.get_roles_at(b.hypotheek.aanvraagdatum, 'borrower'):
                logger.debug('koppel nieuwe nodige schuldsaldo' )
                if aanvrager.natuurlijke_persoon:
                    gekoppeld = False
                    for ss in b.nodige_schuldsaldo:
                        if ss.natuurlijke_persoon.id==aanvrager.natuurlijke_persoon.id:
                            gekoppeld = True
                    if not gekoppeld:
                        nodige_schuldsaldo = NodigeSchuldsaldo(natuurlijke_persoon = aanvrager.natuurlijke_persoon,
                                                               schuldsaldo_voorzien = ((aanvrager.company_coverage_limit or 0) > 0),
                                                               dekkingsgraad_schuldsaldo = (aanvrager.company_coverage_limit or 0) + (aanvrager.person_coverage_limit or 0),
                                                               beslissing = b )
                        nodige_schuldsaldo.flush()

    @transaction
    def button_incomplete(self):
        return self.beslis('incomplete')

    @transaction
    def button_approved(self):
        self.approve()
    
    def approve(self, at=None):
        """
        :param at: the date at which the decision is approved
        :return: de aanvaardingsbrief
        """
        from aanvaarding import Aanvaarding
        for gb in self.goedgekeurd_bedrag:
            gb.keur_goed()
        aanvaarding = Aanvaarding(beslissing=self, state='to_send')
        self.goedgekeurde_dossierkosten = self.dossierkosten
        self.beslis('approved', at)
        return aanvaarding

    @transaction
    def button_undo_beslissing(self):
        from aanvaarding import Aanvaarding
        from akte import Akte
        for gb in self.goedgekeurd_bedrag:
            gb.undo_beslissing()
        self.hypotheek.state = 'complete'
        self.state = 'te_nemen'
        self.datum = datetime.date.today()
        self.goedgekeurde_dossierkosten = 0
        for aanvaarding in Aanvaarding.query.filter_by(beslissing_id=self.id).all():
            aanvaarding.delete()
        for akte in Akte.query.filter_by(beslissing_id=self.id).all():
            akte.delete()
        return True

    @transaction
    def button_disapproved(self):
        for gb in self.goedgekeurd_bedrag:
            gb.keur_af()
        return self.beslis('disapproved')

    def beslis(self, state, at=None):
        self.hypotheek.state = state
        self.state = state
        self.datum = at or datetime.date.today()
        return True
    
    class Admin(VfinanceAdmin):
        verbose_name = _('Beslissing')
        verbose_name_plural = _('Beslissingen')
        list_display =  ['datum', 'state', 'full_number', 'borrower_1_name', 'borrower_2_name', 'opmerkingen']
        list_filter = ['state', list_filter.ComboBoxFilter('hypotheek.company_id', verbose_name=_('Maatschappij'))]
        list_search = ['hypotheek.aanvraagnummer', 'hypotheek.roles.natuurlijke_persoon.name', 'hypotheek.roles.rechtspersoon.name']
        list_actions = [DecisionDocument()]
        form_display =  forms.Form([forms.TabForm([(_('Beslissing'), forms.Form([forms.GroupBoxForm(_('Aanvraag'),
                                                                                                    ['hypotheek','full_number','datum','datum_voorwaarde','wettelijk_kader',], columns=2),
                                                                                 'goedgekeurd_bedrag',
                                                                                 'nodige_schuldsaldo',
                                                                                 forms.GroupBoxForm(_('Beslissing'),['opmerkingen','state', 'beslissingsdocument',], columns=2),
                                                                                 ])),
                                                   (_('Dossierkosten'), forms.Form(['voorgestelde_dossierkosten','correctie_dossierkosten','dossierkosten','goedgekeurde_dossierkosten',], columns=2)),
                                                   (_('Evaluatie'), forms.Form([forms.GroupBoxForm(_('Terugbetalingscapaciteit'),
                                                                                                   ['totaal_inkomsten','totaal_lasten','maandlast_lopend_krediet','levensonderhoud',
                                                                                                    'correctie_levensonderhoud','terugbetalingscapaciteit','maandelijkse_voorgestelde_aflossing',
                                                                                                    'voorgestelde_terugbetalingsratio',], columns=2),
                                                                                forms.GroupBoxForm(_('Waarborgen'),
                                                                                                   ['gedwongen_verkoop','vrijwillige_verkoop','bestaande_inschrijvingen','saldo_bestaande_inschrijvingen',
                                                                                                    'waarborg_bijkomend_waarde','waarborgen','goedgekeurd_totaal','quotiteit',], columns=2),], columns=2)),],
                                                    position=forms.TabForm.WEST)], columns=2)
        form_size = (900,600)
        form_state = 'maximized'
        form_actions = [CallMethod(_('Maak voorstel'), lambda o:o.button_maak_voorstel(), enabled=lambda o:(o is not None) and (o.state in ['proef','te_nemen'])),
                        CallMethod(_('Goedgekeurd'), lambda o:o.button_approved(), enabled=lambda o:(o is not None) and (o.state=='te_nemen')),
                        CallMethod(_('Afgekeurd'), lambda o:o.button_disapproved(), enabled=lambda o:(o is not None) and (o.state=='te_nemen')),
                        CallMethod(_('Ongedaan maken'), lambda o:o.button_undo_beslissing(), enabled=lambda o:(o is not None) and (o.state in ['approved', 'disapproved'])),
                        CallMethod(_('Onvolledig'), lambda o:o.button_incomplete(), enabled=lambda o:(o is not None) and (o.state=='te_nemen')),
                        DecisionDocument(), ]
                        
        field_attributes = {
                            'goedgekeurde_dossierkosten':{'editable':False, 'name':_('Goedgekeurde dossierkosten')},
                            'datum':{'editable':False, 'name':_('Beslissingsdatum')},
                            'nummer':{'editable':False, 'delegate':delegates.IntegerDelegate, 'name':_('Aanvraagnummer')},
                            'opmerkingen':{'editable':True, 'name':_('Opmerkingen')},
                            'schattingskosten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Schattingskosten')},
                            'waarborgen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('In aanmerking te nemen waarborgen')},
                            'ontvangen_voorschot':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Ontvangen voorschot')},
                            'maandelijkse_voorgestelde_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Maandelijkse voorgestelde aflossing')},
                            'dossierkosten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Dossierkosten')},
                            'datum_voorwaarde':{'editable':True, 'name':_('Datum van voorwaarden')},
                            'quotiteit':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Quotiteit')},
                            'levensonderhoud':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Levensonderhoud')},
                            'borrower_1_name':{'editable':False, 'minimal_column_width':30, 'name':_('Naam eerste ontlener')},
                            'borrower_2_name':{'editable':False, 'minimal_column_width':30, 'name':_('Naam tweede ontlener')},
                            'bestaande_inschrijvingen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Bestaande inschrijvingen')},
                            'goedgekeurd_bedrag':{'editable':True, 'name':_('Goedgekeurde bedragen')},
                            'name':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Naam')},
                            'vrijwillige_verkoop':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Waarde bij vrijwillige verkoop')},
                            'beslissingsdocument':{'editable':True, 'name':_('Ondertekend beslissingsdocument')},
                            'goedgekeurd_totaal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurd totaal')},
                            'related_constraints':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Opmerkingen')},
                            'gedwongen_verkoop':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Waarde bij gedwongen verkoop')},
                            'verzekeringskosten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Verzekeringskosten')},
                            'goedgekeurde_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde aflossing')},
                            'voorgestelde_dossierkosten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Voorgestelde dossierkosten')},
                            'totaal_lasten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totaal lasten')},
                            'terugbetalingscapaciteit':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Terugbetalingscapaciteit')},
                            'achterstal_rekening':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Rekening achterstal')},
                            'akte':{'editable':False, 'name':_('Akte')},
                            'nodige_schuldsaldo':{'editable':True, 'name':_('Nodige schuldsaldoverzekering')},
                            'achterstal':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Achterstal')},
                            'state':{'editable':False, 'name':_('Status'), 'choices':[('proef', 'Proef'), 
                                                                                      ('te_nemen', 'Te nemen'), 
                                                                                      ('incomplete', 'Onvolledig'), 
                                                                                      ('approved', 'Goedgekeurd'), 
                                                                                      ('disapproved', 'Afgekeurd'),
                                                                                      ('ticked', 'Afgepunt'),]},
                            'saldo_bestaande_inschrijvingen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Saldo bestaande inschrijvingen')},
                            'hypotheek':{'editable':False, 'name':_('Hypotheek')},
                            'voorgestelde_terugbetalingsratio':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Terugbetalingsratio')},
                            'maandlast_lopend_krediet':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Maandlast lopende kredieten')},
                            'maandelijkse_basis_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Maandelijkse aflossing na rente vermeerdering')},
                            'saldo':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Saldo te betalen')},
                            'totaal_inkomsten':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Totaal inkomsten')},
                            'aanvaarding':{'editable':False, 'name':_('Aanvaardingsbrief')},
                            'correctie_dossierkosten':{'editable':True, 'name':_('Correctie dossierkosten')},
                            'correctie_levensonderhoud':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Correctie Levensonderhoud')},
                            'terugbetalingsratio':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Terugbetalingsratio')},
                            'waarborg_bijkomend_waarde':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Waarde bijkomende waarborgen')},
                            'wettelijk_kader':{'editable':False, 'name':_('Wettelijk kader')},
                            'aanvraagdatum':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Datum van aanvraag')},
                            'company_id':{'name': _('Maatschappij')},
                           }

        def get_query(self, *args, **kwargs):
            query = VfinanceAdmin.get_query(self, *args, **kwargs)
            query = query.options(orm.joinedload('hypotheek'))
            query = query.options(orm.joinedload('hypotheek.roles'))
            query = query.options(orm.undefer('hypotheek.roles.name'))
            
            return query


def create_property(relation_field, field):
    
    def property_getter( obj ):
        relation = getattr(obj, relation_field)
        if relation != None:
            return getattr( relation, field )
        
    return property( property_getter )

for field in ['waarborgen', 'totaal_inkomsten', 'totaal_lasten', 'levensonderhoud', 'correctie_levensonderhoud', 'maandlast_lopend_krediet',
              'gedwongen_verkoop', 'vrijwillige_verkoop', 'bestaande_inschrijvingen', 'saldo_bestaande_inschrijvingen',
              'waarborg_bijkomend_waarde', 'ontvangen_voorschot', 'schattingskosten', 'verzekeringskosten',
              'achterstal', 'achterstal_rekening', 'wettelijk_kader', 'aanvraagdatum']:
    setattr( Beslissing, field, create_property( 'hypotheek', field ) )

class GoedgekeurdBedrag( Entity, ScheduleMixin ):
    using_options(tablename='hypo_goedgekeurd_bedrag')
    product = ManyToOne(Product, required=True, ondelete='restrict', onupdate='cascade' )
    goedgekeurde_referentie_index  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    goedgekeurd_type_vervaldag  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    beslissing_id  =  schema.Column(sqlalchemy.types.Integer(), name='beslissing', index=True)
    beslissing  =  ManyToOne('vfinance.model.hypo.beslissing.Beslissing', field=beslissing_id)
    voorgestelde_maximale_conjunctuur_ristorno  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    voorgestelde_maximale_spaar_ristorno  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    goedgekeurde_minimale_afwijking  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    voorgestelde_reserveringsprovisie  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True, default=unicode('0.0025'))
    voorgestelde_eerste_herziening_ristorno  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    bedrag_id  =  schema.Column(sqlalchemy.types.Integer(), name='bedrag', nullable=False, index=True)
    bedrag  =  ManyToOne(Bedrag, field=bedrag_id)
    waarborgen  =  property(lambda self:self.getter())
    goedgekeurde_maximale_conjunctuur_ristorno  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    goedgekeurd_terugbetaling_interval  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    goedgekeurde_rente  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
    goedgekeurde_eerste_herziening_ristorno  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    voorgestelde_maximale_product_ristorno  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    goedgekeurde_maximale_stijging  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    voorgestelde_maximale_daling  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    voorgestelde_volgende_herzieningen_ristorno  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    state  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=False, default=unicode('draft'))
    goedgekeurde_maximale_product_ristorno  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    goedgekeurde_looptijd  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    goedgekeurde_opname_periode  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    voorgestelde_minimale_afwijking  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    goedgekeurde_maximale_spaar_ristorno  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    goedgekeurde_eerste_herziening  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    type = schema.Column(sqlalchemy.types.Unicode(50), nullable=False, default=unicode('nieuw'))
    goedgekeurde_maximale_daling  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    rente_vermeerdering  =  property(lambda self:self.get_rente_wijziging())
    rente_vermindering  =  property(lambda self:self.get_rente_wijziging())
    commerciele_wijziging  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True, default=0)
    venice_doc  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    wijziging_id  =  schema.Column(sqlalchemy.types.Integer(), name='wijziging', nullable=True, index=True)
    # this causes a circular dependency
    wijziging = ManyToOne('vfinance.model.hypo.wijziging.Wijziging', field=wijziging_id ) #, inverse='nieuw_goedgekeurd_bedrag')
    voorgestelde_referentie_index  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    goedgekeurd_bedrag  =  schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2))
    goedgekeurde_intrest_b  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
    voorgesteld_index_type_id  =  schema.Column(sqlalchemy.types.Integer(), name='voorgesteld_index_type', nullable=True, index=True)
    voorgesteld_index_type  =  ManyToOne('vfinance.model.bank.index.IndexType', field=voorgesteld_index_type_id)
    voorgestelde_eerste_herziening  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    goedgekeurde_intrest_a  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
    goedgekeurd_terugbetaling_start  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    goedgekeurde_reserverings_provisie  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
    goedgekeurde_opname_schijven  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    goedgekeurd_type_aflossing  =  schema.Column(sqlalchemy.types.Unicode(50), nullable=True)
    voorgestelde_volgende_herzieningen  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    goedgekeurde_volgende_herzieningen  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    voorgestelde_maximale_stijging  =  schema.Column(sqlalchemy.types.Unicode(7), nullable=True)
    goedgekeurde_jaarrente  =  schema.Column(sqlalchemy.types.Unicode(12), nullable=True)
    goedgekeurde_volgende_herzieningen_ristorno  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    venice_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    goedgekeurd_index_type_id  =  schema.Column(sqlalchemy.types.Integer(), name='goedgekeurd_index_type', nullable=True, index=True)
    goedgekeurd_index_type  =  ManyToOne('vfinance.model.bank.index.IndexType', field=goedgekeurd_index_type_id)
    # goedgekeurd vast gedeelte vd aflossing, het kapitaal, of de totale aflossing,
    # afhankelijk van het aflossing type, voor overname portefeuilles waarbij er
    # numerieke verschillen zitten op de aflossing zelf.
    goedgekeurd_vast_bedrag = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2))

    @hybrid.hybrid_property
    def history_of_id(self):
        return self.id

    @ColumnProperty
    def datum(self):
        return sql.select( [Beslissing.datum],
                           Beslissing.id==self.beslissing )
    
    
    @ColumnProperty
    def beslissing_state(self):
        return sql.select( [Beslissing.state],
                           Beslissing.id==self.beslissing )

    @property
    def borrower_1_name(self):
        if self.beslissing is not None:
            return self.beslissing.borrower_1_name
                           
    @property
    def borrower_2_name(self):
        if self.beslissing is not None:
            return self.beslissing.borrower_2_name

    @property
    def product_name(self):
        if self.product is not None:
            return self.product.name

    @property
    def rente_vermeerdering(self):
        # @todo : implement rente vermeerdering
        return 0

    @property
    def rente_vermindering(self):
        # @todo : implement rente vermindering
        return 0

    @property
    def wijziging(self):
        from wijziging import Wijziging
        if self.wijziging_id:
            return Wijziging.get( self.wijziging_id )
            
    @property
    def dossier(self):
        from wijziging import Wijziging
        if self.type == 'wijziging':
            if not self.wijziging:
                raise Exception('Inconsistent data, goedgekeurd bedrag %s type wijziging heeft geen wijziging'%self.id)
            return self.wijziging.dossier
        elif self.type == 'nieuw':
            # als het nog nt doorgevoerd is, is er nog geen dossier aan gekoppeld
            if self.state not in ('processed', 'ticked'):
                return None
            else:
                # Als het nieuw goedgekeurd bedrag nog actief is, zit het in dossier
                if self.huidige_dossier is not None:
                    return self.huidige_dossier
                # anders moeten we in de wijzigingen gaan zoeken
                else:
                    wijziging = Wijziging.query.filter( sql.and_( Wijziging.vorig_goedgekeurd_bedrag == self,
                                                                  Wijziging.state.in_( ['processed','ticked'] ) ) ).first()
                    if wijziging:
                        return wijziging.dossier
            raise Exception('Inconsistent data: goedgekeurd bedrag %s heeft type nieuw en komt nt voor in dossier nog in wijziging'%self.id)
        raise Exception('Inconsistent data, goedgekeurd bedrag %s heeft onbekend type'%self.id)
    
    @property
    def full_number(self):
        """The full number of the dossier, not that of the agreement"""
        dossier = self.dossier
        if dossier is not None:
            return dossier.full_number

    @property
    def gevraagd_bedrag(self):
        if self.bedrag:
            return self.bedrag.bedrag

    @property
    def basis_rente(self):
        if self.bedrag:
            return self.bedrag.basis_rente

    @property
    def looptijd(self):
        if self.bedrag:
            return self.bedrag.looptijd

    @property
    def type_aflossing(self):
        if self.bedrag:
            return self.bedrag.type_aflossing

    @property
    def aktedatum(self):
        if self.bedrag:
            return self.bedrag.aktedatum

    @property
    def doelen(self):
        if self.bedrag:
            return self.bedrag.doelen

    @property
    def voorgestelde_rente(self):
        components = {'basis_rente':1, 'rente_vermeerdering':1, 'rente_vermindering':-1, 'commerciele_wijziging':1 }
        return str(sum( D(getattr(self,key) or 0)*value for key,value in components.items()) )

    @property
    def aantal_aflossingen(self):
        if self.bedrag:
            return int(math.ceil(self.bedrag.looptijd * self.bedrag.terugbetaling_interval / 12))

    @property
    def goedgekeurd_aantal_aflossingen(self):
        if self.bedrag:
            return int(math.ceil(((self.goedgekeurde_looptijd or self.bedrag.looptijd) * (self.goedgekeurd_terugbetaling_interval or self.bedrag.terugbetaling_interval) / 12)))

    @property
    def basis_aflossing(self):
        if self.bedrag:
            return hoogste_aflossing((D(self.basis_rente)+D(self.rente_vermeerdering)), self.bedrag.type_aflossing, self.goedgekeurd_bedrag, self.aantal_aflossingen, (12/self.bedrag.terugbetaling_interval))

    @property
    def maandelijkse_basis_aflossing(self):
        if self.bedrag:
            return self.basis_aflossing/(12/self.bedrag.terugbetaling_interval)

    @property
    def voorgestelde_aflossing(self):
        if self.bedrag:
            return hoogste_aflossing(D(self.voorgestelde_rente), self.bedrag.type_aflossing, self.goedgekeurd_bedrag, self.aantal_aflossingen, (12/self.bedrag.terugbetaling_interval), None)

    @property
    def maandelijkse_voorgestelde_aflossing(self):
        if self.bedrag:
            return self.voorgestelde_aflossing/(12/self.bedrag.terugbetaling_interval)

    @property
    def goedgekeurde_aflossing(self):
        if self.goedgekeurde_looptijd:
            return hoogste_aflossing(D(self.goedgekeurde_rente or 0), self.goedgekeurd_type_aflossing, self.goedgekeurd_bedrag, self.goedgekeurd_aantal_aflossingen, (12/self.goedgekeurd_terugbetaling_interval), jaar_rente=D(self.goedgekeurde_jaarrente or 0)*100)
        else:
            return 0
        
    @property
    def maandelijkse_goedgekeurde_aflossing(self):
        if self.goedgekeurde_aflossing and self.goedgekeurd_terugbetaling_interval:
            return self.goedgekeurde_aflossing/(12/self.goedgekeurd_terugbetaling_interval)

    @property
    def agreement_code( self ):
        return str( self.bedrag.hypotheek_id.aanvraagnummer )
    
    @property
    def name(self):
        return self.bedrag.hypotheek_id.name

    # in feite de equivalente jaarlijkse rente
    @property
    def voorgestelde_jaarlijkse_kosten(self):
        if self.bedrag:
            return (((1+D(self.voorgestelde_rente or 0)/100)**(self.bedrag.terugbetaling_interval or 1)- 1)*100).quantize(ONE_MILLIONTH)

    @property
    def goedgekeurde_jaarlijkse_kosten(self):
        return (((1+D(self.goedgekeurde_rente or 0)/100)**(self.goedgekeurd_terugbetaling_interval or 1) - 1)*100).quantize(ONE_MILLIONTH)

    def get_niet_te_betalen_intresten( self, dossier, from_date ):
        gefactureerd_voor_periode = sum( (f.bedrag for f in dossier.factuur if f.datum < from_date), 0 )
        if self.goedgekeurde_opname_schijven:
          # Voor dossiers met opname schijven (cfr Automat), trek de rente op het nog nt opgenomen bedrag af 
          # van de te betalen aflossing
          nog_te_betalen_schijven = self.goedgekeurd_bedrag - gefactureerd_voor_periode
          niet_te_betalen_intresten = nog_te_betalen_schijven * D(self.goedgekeurde_rente) / 100
          logger.debug( 'opname schijven, %s nog te betalen met rente %s -> intrest vermindering van %s'%( nog_te_betalen_schijven,
                                                                                                           self.goedgekeurde_rente,
                                                                                                           niet_te_betalen_intresten ) )
        else:
          niet_te_betalen_intresten = 0
        return gefactureerd_voor_periode, niet_te_betalen_intresten
          
    def __unicode__(self):
        return self.name

    def undo_beslissing(self):
        """Maak een goed of afkeuring ongedaan"""

        if self.state=='approved' or self.state=='disapproved':
            reset_data = {
              'goedgekeurde_jaarrente':0,
              'goedgekeurde_rente':0,
              'goedgekeurde_looptijd':0,
              'goedgekeurd_terugbetaling_start':0,
              'goedgekeurde_opname_periode':0,
              'goedgekeurde_opname_schijven':0,
              'goedgekeurde_intrest_a': '',
              'goedgekeurde_intrest_b': '',
              'goedgekeurd_type_vervaldag': '',
              'goedgekeurde_reserverings_provisie':0,
              'state':'draft',
              'goedgekeurd_index_type':None,
            }
            for key, _name in variabiliteit_type_modaliteiten:
                reset_data['goedgekeurde_%s'%key]=0
            for key, _name in variabiliteit_historiek_modaliteiten:
                reset_data['goedgekeurde_%s'%key]='0.0'
            self.from_dict(reset_data)
        else:
            raise Exception('Kan beslissing niet ongedaan maken, want dossier is reeds aangemaakt, gelieve het dossier te wijzigen.')

    def keur_goed(self):
        goedgekeurde_intrest_a = '%.4f'%(0.5 / self.bedrag.terugbetaling_interval)
        approve_data = {
          'goedgekeurde_rente':self.voorgestelde_rente,
          'goedgekeurde_looptijd':self.bedrag.looptijd,
          'goedgekeurd_type_aflossing':self.bedrag.type_aflossing,
          'goedgekeurd_terugbetaling_interval':self.bedrag.terugbetaling_interval,
          'goedgekeurd_terugbetaling_start':self.bedrag.terugbetaling_start,
          'goedgekeurde_opname_periode':self.bedrag.opname_periode,
          'goedgekeurd_type_vervaldag':self.bedrag.type_vervaldag,
          'goedgekeurde_opname_schijven': self.bedrag.opname_schijven or 0,
          'goedgekeurde_intrest_a': goedgekeurde_intrest_a,
          'goedgekeurde_intrest_b': '%f'%(D(self.voorgestelde_rente) + D(goedgekeurde_intrest_a) ),
          'goedgekeurde_reserverings_provisie':self.voorgestelde_reserveringsprovisie,
          'goedgekeurde_referentie_index':self.voorgestelde_referentie_index,
          'state':'approved',
          'goedgekeurd_index_type':self.voorgesteld_index_type,
        }
        if self.bedrag.type_aflossing == 'vaste_annuiteit':
            approve_data['goedgekeurde_jaarrente'] = '%f'%(D(self.voorgestelde_rente)/100)
            approve_data['goedgekeurd_type_aflossing'] = 'vaste_aflossing'
        for key, _name in variabiliteit_type_modaliteiten:
            approve_data['goedgekeurde_%s'%key]=getattr(self, 'voorgestelde_%s'%key)
        for key, _name in variabiliteit_historiek_modaliteiten:
            approve_data['goedgekeurde_%s'%key]=getattr(self, 'voorgestelde_%s'%key)
        self.from_dict(approve_data)

    def keur_af(self):
        self.state = 'disapproved'

    def create_dossier( self, aktedatum, dossier_nummer, dossier_rank, notifications=True ):
        """Create a dossier and change the state to `processed`.  Does not flush the
        session.
        
        :param notifications: create the needed notifications to involved persons and
            authorities when a new dossier is created

        :return: a :class:`vfinance.model.hypo.dossier.Dossier` object
        """
        from .dossier import ( Dossier, AkteDossier, BijkomendeWaarborgDossier, 
                               HypoDossierRole, HypoDossierBroker,
                               DossierFunctionalSettingApplication,
                               DossierFeatureApplication)
        from .melding_nbb import MeldingNbb
        
        beslissing = self.beslissing
        #
        # Aanmaken dossier
        #
        logger.info('nieuw dossier nummer : %s'%dossier_nummer)
        state = 'running'
        if self.goedgekeurde_opname_periode > 0:
            state = 'opnameperiode'
        if self.goedgekeurd_type_vervaldag == 'maand':
            startdatum = aktedatum
            startdatum = datetime.date(day=2, month=startdatum.month, year=startdatum.year)
        else:
            startdatum = aktedatum
        hypotheek = beslissing.hypotheek
        dossier = Dossier( goedgekeurd_bedrag = self,
                           startdatum = startdatum,
                           originele_startdatum = startdatum,
                           nummer = dossier_nummer,
                           rank = dossier_rank,
                           company_id = self.bedrag.hypotheek_id.company_id,
                           state = state,
                           domiciliering = len(hypotheek.direct_debit_mandates)>0,
                           aanvraag = hypotheek )
        akte_dossier = AkteDossier() 
        akte_dossier.dossier = dossier
        akte_dossier.from_date = startdatum
        akte_dossier.akte = beslissing.akte[0]
        # Aanmaken roles
        for role in hypotheek.roles:
            HypoDossierRole( dossier = dossier,
                             described_by = role.described_by,
                             from_date = aktedatum,
                             thru_date = role.thru_date,
                             rank = role.rank,
                             rechtspersoon = role.rechtspersoon,
                             natuurlijke_persoon = role.natuurlijke_persoon )
        # Aanmaker broker relation
        if hypotheek.broker_relation or hypotheek.broker_agent:
            HypoDossierBroker(dossier=dossier,
                              broker_relation=hypotheek.broker_relation,
                              broker_agent=hypotheek.broker_agent,
                              from_date=hypotheek.aanvraagdatum)
        #
        # Koppeling waarborgen aan dossier
        #
        for bijkomende_waarborg_hypotheek in hypotheek.bijkomende_waarborg:
            BijkomendeWaarborgDossier( dossier = dossier,
                                       from_date = startdatum,
                                       bijkomende_waarborg = bijkomende_waarborg_hypotheek.bijkomende_waarborg )
        #
        # Koppeling direct debit mandates aan dossier
        #
        for mandate in hypotheek.direct_debit_mandates:
            dossier.direct_debit_mandates.append(mandate)
        #
        # Apply functional settings
        #
        for functional_setting in hypotheek.agreed_functional_settings:
            DossierFunctionalSettingApplication(applied_on=dossier,
                                                from_date=startdatum,
                                                described_by=functional_setting.described_by)
        #
        # Apply features
        #
        for feature in self.bedrag.agreed_features:
            DossierFeatureApplication(applied_on=dossier,
                                      from_date=startdatum,
                                      described_by=feature.described_by,
                                      value=feature.value,
                                      comment=feature.comment)
        #
        # Aanmaken uit te voeren meldingen bij de nationale bank
        #
        if notifications == True:
            MeldingNbb( dossier=dossier, state='todo', 
                        datum_melding = None, 
                        type = 'eerste_positieve_melding', 
                        registratienummer = dossier_nummer )
            for hypotheeknemer in beslissing.hypotheek.get_roles_at(beslissing.hypotheek.aanvraagdatum, 'borrower'):
                if hypotheeknemer.natuurlijke_persoon:
                    MeldingNbb( dossier = dossier, 
                                state = 'todo', 
                                datum_melding = None, 
                                type = 'bijvoegen_kredietnemer',
                                kredietnemer = hypotheeknemer.natuurlijke_persoon )
        self.venice_doc = dossier_nummer
        self.state = 'processed'
        return dossier

    @property
    def aanvangsdatum( self ):
        """De datum waarop het goedgekeurd bedrag aktief word, ih geval van een nieuw
        dossier is dit de aktedatum, ih geval ve wijziging is dit de datum van wijziging, 
        None indien dit goedgekeurd bedrag nog niet aktief is"""
        if self.wijziging and self.wijziging.state in ['processed', 'ticked']:
            return self.wijziging.datum_wijziging
        elif self.beslissing and self.beslissing.state in ['processed', 'ticked', 'approved'] and self.state in ['processed', 'ticked']:
            originele_startdatum = self.dossier.originele_startdatum
            if not originele_startdatum:
                raise Exception('Invalid data in database, dossier %s has no originele startdatum'%(self.dossier.nummer))
            return originele_startdatum
        else:
            return False
        
    @property
    def einddatum( self ):
        """De datum waarop dit goedgekeurd bedrag theoretisch inactief
        wordt, None indien het nog nt actief is"""
        aanvangsdatum = self.aanvangsdatum
        if aanvangsdatum:
          dyear, month = divmod(aanvangsdatum.month+self.goedgekeurde_looptijd-1,12)
          year = aanvangsdatum.year + dyear
          month = month + 1
          first_day, max_day = calendar.monthrange(year, month)
          day = min(aanvangsdatum.day,max_day)  
          return datetime.date( year, month, day )

    class Admin(VfinanceAdmin):
        verbose_name = _('Goedgekeurd bedrag')
        verbose_name_plural = _('Goedgekeurde bedragen')
        list_display =  ['product', 'gevraagd_bedrag', 'goedgekeurd_bedrag', 'looptijd', 'type_aflossing', 'voorgestelde_rente', 'voorgestelde_aflossing', 'goedgekeurde_rente', 'goedgekeurde_looptijd', 'goedgekeurd_type_aflossing']
        form_actions = [] # actions will be appended to this list in other modules
        form_display =  forms.Form([forms.TabForm([(_('Modaliteiten'), forms.Form(['bedrag',
                                                                                   'doelen',
                                                                                   forms.GroupBoxForm(_('Voorgesteld'),
                                                                                                      ['basis_rente','rente_vermeerdering','basis_aflossing','rente_vermindering',
                                                                                                       'commerciele_wijziging','voorgestelde_rente','voorgestelde_aflossing',
                                                                                                       'voorgestelde_jaarlijkse_kosten','voorgestelde_reserveringsprovisie',], columns=2),
                                                                                   forms.GroupBoxForm(_('Goedgekeurd'),['goedgekeurd_bedrag','goedgekeurde_rente','goedgekeurde_aflossing',
                                                                                                                        'goedgekeurde_jaarlijkse_kosten','goedgekeurde_intrest_a','goedgekeurde_intrest_b',
                                                                                                                        'goedgekeurde_reserverings_provisie','goedgekeurde_opname_periode',
                                                                                                                        'goedgekeurde_opname_schijven','goedgekeurde_looptijd',
                                                                                                                        'goedgekeurd_type_aflossing','goedgekeurd_terugbetaling_interval',
                                                                                                                        'goedgekeurd_type_vervaldag','goedgekeurd_terugbetaling_start',], columns=2),], columns=2)),
                                                   (_('Variabiliteit'), forms.Form([forms.GroupBoxForm(_('Voorgesteld'),
                                                                                                       ['voorgesteld_index_type','voorgestelde_referentie_index','voorgestelde_eerste_herziening',
                                                                                                        'voorgestelde_volgende_herzieningen','voorgestelde_minimale_afwijking',
                                                                                                        'voorgestelde_maximale_daling','voorgestelde_maximale_stijging',], columns=2),
                                                                                    forms.GroupBoxForm(_('Goedgekeurd'),['goedgekeurd_index_type','goedgekeurde_referentie_index',
                                                                                                                         'goedgekeurde_eerste_herziening','goedgekeurde_volgende_herzieningen',
                                                                                                                         'goedgekeurde_minimale_afwijking','goedgekeurde_maximale_daling',
                                                                                                                         'goedgekeurde_maximale_stijging',], columns=2),], columns=2)),
                                                   (_('Ristorno'), forms.Form([forms.GroupBoxForm(_('Voorgesteld'),['voorgestelde_maximale_spaar_ristorno','voorgestelde_maximale_product_ristorno',
                                                                                                                    'voorgestelde_maximale_conjunctuur_ristorno','voorgestelde_eerste_herziening_ristorno',
                                                                                                                    'goedgekeurde_volgende_herzieningen_ristorno',], columns=1),
                                                                               forms.GroupBoxForm(_('Goedgekeurd'),['goedgekeurde_maximale_spaar_ristorno','goedgekeurde_maximale_product_ristorno',
                                                                                                                    'goedgekeurde_maximale_conjunctuur_ristorno','goedgekeurde_eerste_herziening_ristorno',
                                                                                                                    'goedgekeurde_volgende_herzieningen_ristorno',], columns=1),], columns=2)),],
                                                   position=forms.TabForm.WEST)], columns=2)
        form_size = (1100,700)
        field_attributes = {
                            'goedgekeurde_referentie_index':{'editable':False, 'name':_('Goedgekeurde Referentie index')},
                            'goedgekeurd_type_vervaldag':{'editable':False, 'name':_('Vervaldag valt op'), 'choices':[('maand', '1e van de maand'), ('akte', 'vervaldag lening')]},
                            'beslissing':{'editable':True, 'name':_('Hypotheek beslissing')},
                            'voorgestelde_maximale_conjunctuur_ristorno':{'editable':True, 'name':_('Voorgestelde Maximale conjunctuur ristorno')},
                            'voorgestelde_maximale_spaar_ristorno':{'editable':True, 'name':_('Voorgestelde Maximale spaar ristorno')},
                            'goedgekeurde_minimale_afwijking':{'editable':False, 'name':_('Goedgekeurde Minimale afwijking')},
                            'voorgestelde_reserveringsprovisie':{'editable':True, 'name':_('Voorgestelde reserveringsprovisie')},
                            'voorgestelde_eerste_herziening_ristorno':{'editable':True, 'name':_('Voorgestelde Eerste herziening ristorno na (maanden)')},
                            'bedrag':{'editable':False, 'name':_('Aangevraagd bedrag')},
                            'waarborgen':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('In aanmerking te nemen waarborgen')},
                            'goedgekeurde_maximale_conjunctuur_ristorno':{'editable':False, 'name':_('Goedgekeurde Maximale conjunctuur ristorno')},
                            'goedgekeurd_terugbetaling_interval':{'editable':False, 'name':_('Terugbetaling'), 'choices':hypo_terugbetaling_intervallen},
                            'goedgekeurde_rente':{'editable':False, 'name':_('Goedgekeurde rente')},
                            'maandelijkse_voorgestelde_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Maandelijkse voorgestelde aflossing')},
                            'goedgekeurde_eerste_herziening_ristorno':{'editable':False, 'name':_('Goedgekeurde Eerste herziening ristorno na (maanden)')},
                            'basis_rente':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Basis rente')},
                            'voorgestelde_maximale_product_ristorno':{'editable':True, 'name':_('Voorgestelde Maximale ristorno gebonden producten')},
                            'goedgekeurde_maximale_stijging':{'editable':False, 'name':_('Goedgekeurde Maximale stijging')},
                            'voorgestelde_maximale_daling':{'editable':True, 'name':_('Voorgestelde Maximale daling')},
                            'voorgestelde_volgende_herzieningen_ristorno':{'editable':True, 'name':_('Voorgestelde Daarna herzieningen ristorno om de (maanden)')},
                            'aktedatum':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Aktedatum')},
                            'state':{'editable':True, 'name':_('Status'), 'choices':[('draft', 'Draft'), ('approved', 'Goedgekeurd'), ('disapproved', 'Afgekeurd'), ('processed', 'Doorgevoerd'), ('ticked', 'Afgepunt')]},
                            'goedgekeurde_maximale_product_ristorno':{'editable':False, 'name':_('Goedgekeurde Maximale ristorno gebonden producten')},
                            'goedgekeurde_looptijd':{'editable':False, 'name':_('Goedgekeurde looptijd (maanden)')},
                            'looptijd':{'editable':False, 'delegate':delegates.IntegerDelegate, 'name':_('Looptijd (maanden)')},
                            'goedgekeurde_opname_periode':{'editable':False, 'name':_('Opname periode (maanden)')},
                            'aanvangsdatum':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Aanvangsdatum')},
                            'voorgestelde_minimale_afwijking':{'editable':True, 'name':_('Voorgestelde Minimale afwijking')},
                            'goedgekeurde_maximale_spaar_ristorno':{'editable':False, 'name':_('Goedgekeurde Maximale spaar ristorno')},
                            'goedgekeurde_eerste_herziening':{'editable':False, 'name':_('Goedgekeurde Eerste herziening na (maanden)')},
                            'type_aflossing':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Aflossing')},
                            'type':{'editable':True, 'name':_('Type goedkeuring'), 'choices':[('nieuw', 'Nieuw'), ('wijziging', 'Wijziging')]},
                            'goedgekeurde_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Goedgekeurde aflossing')},
                            'goedgekeurde_maximale_daling':{'editable':False, 'name':_('Goedgekeurde Maximale daling')},
                            'rente_vermeerdering':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Rente vermeerdering')},
                            'rente_vermindering':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Rente vermindering')},
                            'commerciele_wijziging':{'editable':True, 'name':_('Commerciele rente wijziging')},
                            'name':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Naam')},
                            'venice_doc':{'editable':False, 'name':_('Document Nummer Venice')},
                            'maandelijkse_basis_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Maandelijkse aflossing na rente vermeerdering')},
                            'basis_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Aflossing na rente vermeerdering')},
                            'goedgekeurd_aantal_aflossingen':{'editable':False, 'delegate':delegates.IntegerDelegate, 'name':_('Goedgekeurd aantal aflossingen')},
                            'aantal_aflossingen':{'editable':False, 'delegate':delegates.IntegerDelegate, 'name':_('Aantal aflossingen')},
                            'goedgekeurde_jaarlijkse_kosten':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Goedgekeurd jaarlijks kostenpercentage')},
                            'wijziging':{'editable':True, 'name':_('Wijziging')},
                            'gevraagd_bedrag':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Gevraagd bedrag')},
                            'voorgestelde_referentie_index':{'editable':True, 'name':_('Voorgestelde Referentie index')},
                            'goedgekeurd_bedrag':{'editable':True, 'name':_('Goedgekeurd bedrag')},
                            'goedgekeurde_intrest_b':{'editable':False, 'name':_('Intrest b')},
                            'voorgesteld_index_type':{'editable':True, 'name':_('Type index')},
                            'voorgestelde_eerste_herziening':{'editable':True, 'name':_('Voorgestelde Eerste herziening na (maanden)')},
                            'goedgekeurde_intrest_a':{'editable':False, 'name':_('Intrest a')},
                            'goedgekeurd_terugbetaling_start':{'editable':False, 'name':_('Uitstel Betaling')},
                            'goedgekeurde_reserverings_provisie':{'editable':False, 'name':_('Goedgekeurde reserveringsprovisie')},
                            'goedgekeurde_opname_schijven':{'editable':False, 'name':_('Opname schijven (maanden)')},
                            'goedgekeurd_type_aflossing':{'editable':False, 'name':_('Goedgekeurd type aflossing'), 'choices':hypo_types_aflossing},
                            'einddatum':{'editable':False, 'delegate':delegates.DateDelegate, 'name':_('Einddatum')},
                            'voorgestelde_rente':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Voorgestelde rente')},
                            'voorgestelde_volgende_herzieningen':{'editable':True, 'name':_('Voorgestelde Daarna herzieningen om de (maanden)')},
                            'voorgestelde_jaarlijkse_kosten':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Voorgestelde jaarlijks kostenpercentage')},
                            'dossier':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Dossier')},
                            'goedgekeurde_volgende_herzieningen':{'editable':False, 'name':_('Goedgekeurde Daarna herzieningen om de (maanden)')},
                            'voorgestelde_maximale_stijging':{'editable':True, 'name':_('Voorgestelde Maximale stijging')},
                            'voorgestelde_aflossing':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Voorgestelde aflossing')},
                            'goedgekeurde_jaarrente':{'editable':False, 'name':_('Goedgekeurde rente')},
                            'goedgekeurde_volgende_herzieningen_ristorno':{'editable':False, 'name':_('Goedgekeurde Daarna herzieningen ristorno om de (maanden)')},
                            'venice_id':{'editable':False, 'name':_('Systeem Nummer Venice')},
                            'goedgekeurd_index_type':{'editable':False, 'name':_('Type index')},
                            'doelen':{'editable':False, 'delegate':delegates.PlainTextDelegate, 'name':_('Doelen')},
                           }

nieuw_goedgekeurd_bedrag_clause = sql.and_(Bedrag.id==GoedgekeurdBedrag.bedrag_id,
                                           GoedgekeurdBedrag.state.in_(('approved', 'processed', 'ticked')),
                                           GoedgekeurdBedrag.type=='nieuw',
                                           )

Bedrag.goedgekeurd_bedrag = orm.column_property(
    sql.select([sql.func.sum(GoedgekeurdBedrag.goedgekeurd_bedrag)]).where(nieuw_goedgekeurd_bedrag_clause),
    deferred=True,
)

Bedrag.beslissing_state = orm.column_property(
    sql.select([Beslissing.state]).where(sql.and_(nieuw_goedgekeurd_bedrag_clause,
                                                  Beslissing.id==GoedgekeurdBedrag.beslissing_id)).order_by(Beslissing.id.desc()).limit(1),
    deferred = True,
    )

#  beslissing_document

class NodigeSchuldsaldo(Entity):

    __tablename__ = 'hypo_nodige_schuldsaldo'

    beslissing_id  =  schema.Column(sqlalchemy.types.Integer(), name='beslissing', nullable=True, index=True)
    beslissing  =  ManyToOne('vfinance.model.hypo.beslissing.Beslissing', field=beslissing_id)
    natuurlijke_persoon_id  =  schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon', nullable=False, index=True)
    natuurlijke_persoon  =  ManyToOne('vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id)
    dekkingsgraad_schuldsaldo  =  schema.Column(sqlalchemy.types.Integer(), nullable=True)
    schuldsaldo_voorzien  =  schema.Column(sqlalchemy.types.Boolean(), nullable=True)

    def __unicode__(self):
        if self.beslissing:
            return unicode(self.beslissing)
        return ''

    class Admin(EntityAdmin):
        list_display =  ['natuurlijke_persoon', 'dekkingsgraad_schuldsaldo', 'schuldsaldo_voorzien']
        form_display =  forms.Form(['natuurlijke_persoon','dekkingsgraad_schuldsaldo','schuldsaldo_voorzien',], columns=2)
        field_attributes = {
                            'beslissing':{},
                            'beslissing':{'editable':True, 'name':_('Hypotheek beslissing')},
                            'natuurlijke_persoon':{},
                            'natuurlijke_persoon':{'editable':True, 'name':_('Persoon')},
                            'bedrag_dekking':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Bedrag dekking')},
                            'dekkingsgraad_schuldsaldo':{'editable':True, 'name':_('Voorziene dekkingsgraad schuldsaldo')},
                            'schuldsaldo_voorzien':{'editable':True, 'name':_('Schuldsaldo via Patronale')},
                           }
#  bepaal_dossierkosten
