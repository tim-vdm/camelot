# -*- coding: utf-8 -*-

import collections
import datetime
import logging
import os

from sqlalchemy import sql

from camelot.admin.action import Action, ListActionModelContext, FormActionModelContext
from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import (UpdateProgress,
                                       OpenFile)

LOGGER = logging.getLogger('vfinance.model.hypo.notification.mortgage_table')

goedgekeurd_bedrag_data = collections.namedtuple( 'goedgekeurd_bedrag_data',
                                                  ( 'number', 'goedgekeurd_bedrag', 'jaren', 'totaal_te_betalen', 'totaal_rente', 'totaal_kapitaal', 'totaal_korting' ) )

aflossing_data = collections.namedtuple( 'aflossing_data',
                                         ( 'nummer', 'datum', 'te_betalen', 'rente', 'kapitaal', 'saldo', 'korting' ) )

from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.view.action_steps.print_preview import PrintJinjaTemplateVFinance


class MortgageTable( Action ):

    verbose_name = _('Aflossingstabel')

    def mortgage_table(self,
                       goedgekeurde_bedragen,
                       datum,
                       full_number,
                       aktedatum=None,
                       kortingen=[],
                       number_label=None,
                       options=None):
        from ..dossier_business import korting_op_vervaldag
        from ..mortgage_table import aflossingen_van_bedrag
        from vfinance.model.financial.notification.utils import get_recipient, generate_qr_code

        context = dict()
        
        taal = 'nl'
        for bedrag in goedgekeurde_bedragen:
            hypotheek = bedrag.bedrag.hypotheek_id
            taal = hypotheek.taal
        if kortingen: 
            originele_startdatum = kortingen[0].dossier.originele_startdatum
        else:
            originele_startdatum = None
        with TemplateLanguage( taal ) as translations:            
            context['goedgekeurde_bedragen'] = []
            context['now'] = datetime.datetime.now()
            context['title'] = translations.ugettext('Aflossingen')
            context['datum'] = datum
            context['full_number'] = full_number
            context['recipient'] = get_recipient(hypotheek.get_roles_at(hypotheek.aanvraagdatum, 'borrower'))
            # TODO fill in if simulating or something that invalidates the document
            context['invalidating_text'] = u''
            context['number_label'] = number_label
            #
            # Per goedgekeurd bedrag een aflossingstabel
            for j,bedrag in enumerate(goedgekeurde_bedragen):
                #
                # Sheet met aflossingen per jaar
                #
                aflossingen_per_jaar = collections.defaultdict( list )
                for a in aflossingen_van_bedrag( bedrag, datum, aktedatum ):
                    aflossingen_per_jaar.setdefault(a.datum.year, []).append(a)
                jaren = list( aflossingen_per_jaar.keys() )
                jaren.sort()
                totale_aflossing = 0
                totale_rente = 0
                totaal_kapitaal = 0
                totale_korting = 0
                sheets = []
                for jaar in jaren:
                    sheet = []
                    for i,a in enumerate(aflossingen_per_jaar[jaar]):
                        totale_aflossing += a.aflossing
                        totale_rente += a.rente
                        totaal_kapitaal += a.kapitaal
                        bedrag_korting = 0
                        for korting in kortingen:
                            bedrag_korting += korting_op_vervaldag( originele_startdatum, 
                                                                    korting.valid_date_start, 
                                                                    korting.valid_date_end,
                                                                    korting.rente,
                                                                    korting.type,
                                                                    a.datum, 
                                                                    a.saldo+a.kapitaal)
                        totale_korting += bedrag_korting
                        values = [a.nummer, a.datum, a.aflossing-bedrag_korting, a.rente, a.kapitaal, a.saldo]
                        if kortingen:
                            values.insert(-1, bedrag_korting)
                        sheet.append( aflossing_data( nummer = a.nummer, 
                                                      datum = a.datum, 
                                                      te_betalen = a.aflossing-bedrag_korting , 
                                                      rente = a.rente, 
                                                      kapitaal = a.kapitaal, 
                                                      saldo = a.saldo, 
                                                      korting = bedrag_korting ) )
                    sheets.append( sheet )   
                context['goedgekeurde_bedragen'].append( goedgekeurd_bedrag_data( number = j + 1,
                                                                                  goedgekeurd_bedrag = bedrag, 
                                                                                  jaren = sheets,
                                                                                  totaal_te_betalen = totale_aflossing, 
                                                                                  totaal_rente = totale_rente, 
                                                                                  totaal_kapitaal = totaal_kapitaal, 
                                                                                  totaal_korting = totale_korting ) )
                context['qr_base64'] = generate_qr_code(full_number)

            if options is not None:
                pjt = PrintJinjaTemplateVFinance('hypo/mortgage_table.html',
                                                 context=context)
                if options.output_type == 0:
                    yield pjt
                else:
                    pjt.get_pdf(filename=os.path.join(options.output_dir, '{0}'.format(full_number, '.pdf')))
            else:
                yield PrintJinjaTemplateVFinance('hypo/mortgage_table.html',
                                                 context=context)

    def generate_documents(self, context, options):
        from ..dossier import Dossier

        if isinstance(context, (ListActionModelContext, FormActionModelContext)):
            dossiers = context.get_selection()
            dossier_count = context.selection_count
        else:
            dossiers = Dossier.query.filter(sql.and_(sql.or_(Dossier.einddatum >= options.from_document_date,
                                                             Dossier.einddatum == None),
                                                     Dossier.originele_startdatum <= options.thru_document_date))
            dossier_count = dossiers.count()


        for i, dossier in enumerate(dossiers):
            try:
                if options.wettelijk_kader not in (None, dossier.wettelijk_kader):
                    continue

                goedgekeurde_bedragen = []
                kortingen = []
                aktedatum = datetime.date.today()
                full_number = dossier.full_number
                datum = dossier.startdatum
                number_label = 'dossier'
                goedgekeurde_bedragen.append( dossier.goedgekeurd_bedrag )
                kortingen.extend([korting for korting in dossier.korting])
                if dossier.goedgekeurd_bedrag_id == dossier.goedgekeurd_bedrag_nieuw.id:
                    aktedatum = dossier.aktedatum_deprecated

                for step in self.mortgage_table(goedgekeurde_bedragen,
                                                datum,
                                                full_number,
                                                aktedatum,
                                                kortingen=kortingen,
                                                number_label=number_label,
                                                options=options):
                    yield step

                yield UpdateProgress(i, dossier_count, unicode(dossier))
            except Exception, e:
                yield UpdateProgress(i, dossier_count, unicode(dossier), detail=str(e))

        yield UpdateProgress(detail='Finished', blocking=True)

        output_dir = options.output_dir
        if output_dir is not None:
            yield OpenFile(output_dir)


    def model_run( self, model_context):
        from .. aanvaarding import Aanvaarding
        from .. akte import Akte
        from .. wijziging import Wijziging
        from .. dossier import Dossier
        
        for obj in model_context.get_selection():
            goedgekeurde_bedragen = []
            kortingen = []
            aktedatum = datetime.date.today()
            datum = aktedatum            
            full_number = ''
            number_label = None

            if isinstance( obj, Aanvaarding ):    
                aanvaarding = obj
                full_number = aanvaarding.full_number
                number_label = 'application'
                if aanvaarding.beslissing.hypotheek.aktedatum:
                    aktedatum = aanvaarding.beslissing.hypotheek.aktedatum
                    datum = aktedatum
                for bedrag in aanvaarding.beslissing.goedgekeurd_bedrag:
                    goedgekeurde_bedragen.append( bedrag )
                    if bedrag.goedgekeurd_type_vervaldag == 'maand':
                        datum = datetime.date( day=2, month=datum.month, year=datum.year )   
                
            elif isinstance( obj, Akte ):
                akte = obj
                full_number = akte.full_number
                number_label = 'application'
                if akte.datum_verlijden:
                    aktedatum = akte.datum_verlijden
                    datum = aktedatum
                for bedrag in akte.beslissing.goedgekeurd_bedrag:
                    goedgekeurde_bedragen.append( bedrag )
                    if bedrag.goedgekeurd_type_vervaldag=='maand':
                        datum = datetime.date(day=2, month=datum.month, year=datum.year)
            
            elif isinstance( obj, Wijziging ):
                wijziging = obj
                full_number = wijziging.full_number
                aktedatum = None
                datum = wijziging.datum_wijziging
                number_label = 'application'
                goedgekeurde_bedragen.append( wijziging.nieuw_goedgekeurd_bedrag )
                kortingen.extend([korting for korting in wijziging.dossier.korting])
            
            elif isinstance( obj, Dossier ):
                aktedatum = None
                dossier = obj
                full_number = dossier.full_number
                datum = dossier.startdatum
                number_label = 'dossier'
                goedgekeurde_bedragen.append( dossier.goedgekeurd_bedrag )
                kortingen.extend([korting for korting in dossier.korting])
                if dossier.goedgekeurd_bedrag_id == dossier.goedgekeurd_bedrag_nieuw.id:
                    aktedatum = dossier.aktedatum_deprecated
                    
            for step in self.mortgage_table(goedgekeurde_bedragen,
                                            datum,
                                            full_number,
                                            aktedatum,
                                            kortingen,
                                            number_label):
                yield step
