import datetime
from decimal import Decimal as D
import logging

from integration.spreadsheet import Cell, Sub, column_name, Eq

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

LOGGER = logging.getLogger('vfinance.model.hypo.report.evolutie_report')
  
from ...bank.report.abstract import AbstractReport
from vfinance.model.hypo.dossier import Dossier
from vfinance.model.hypo.wijziging import Wijziging
from vfinance.model.hypo.constants import wettelijke_kaders
        
class EvolutieReport( AbstractReport ):
    """Evolutie van de portefeuille over verschillende jaren
    """
  
    name = _('Evolutie dossiers')
    
    def fill_sheet( self, sheet, offset, options ):
        years = list( range( options.from_document_date.year, options.thru_document_date.year + 1 ) )

        openstaand_kapitaal = dict( (y,0) for y in years )
        kaders = dict(wettelijke_kaders).keys()
        openstaand_kapitaal_per_kader = dict( (y,dict((kader,0) for kader in kaders )) for y in years )
        openstaand_kapitaal_per_akte_jaar = dict( (y,dict((akte_y,0) for akte_y in years)) for y in years )
        productie = dict( (str(y),{'totaal':0, 'aantal':0, 'looptijd':0, 'intrest':0}) for y in years )
        akte_years = set()
        yield UpdateProgress( 1, 4, 'Wijzigingen' )
        for wijziging in Wijziging.query.filter( Wijziging.state.in_( ['processed','ticked'] ) ).all():
          if wijziging.huidig_bedrag<wijziging.nieuw_bedrag:
            startdatum = wijziging.datum_wijziging
            productie_startyear = productie.setdefault(str(startdatum.year), {'totaal':0, 'aantal':0, 'looptijd':0, 'intrest':0})
            bedrag = wijziging.nieuw_bedrag - wijziging.huidig_bedrag
            gb = wijziging.nieuw_goedgekeurd_bedrag
            productie_startyear['totaal'] += bedrag
            productie_startyear['aantal'] += 1
            productie_startyear['looptijd'] += gb.goedgekeurde_looptijd * bedrag
            productie_startyear['intrest'] += D(gb.goedgekeurde_rente) * gb.goedgekeurd_terugbetaling_interval * bedrag   
        yield UpdateProgress( 2, 4, 'Dossiers' )
        for dossier in Dossier.query.all():
          startdatum = dossier.originele_startdatum   
          if startdatum:
            productie_startyear = productie.setdefault(str(startdatum.year), {'totaal':0, 'aantal':0, 'looptijd':0, 'intrest':0})
            bedrag = dossier.goedgekeurd_bedrag_nieuw.goedgekeurd_bedrag
            productie_startyear['totaal'] += bedrag
            productie_startyear['aantal'] += 1
            productie_startyear['looptijd'] += dossier.goedgekeurde_looptijd * bedrag
            productie_startyear['intrest'] += D(dossier.goedgekeurde_rente) * dossier.goedgekeurd_bedrag_nieuw.goedgekeurd_terugbetaling_interval * bedrag
            for year in years:
              if int(year)>=int(startdatum.year):
                #saldo = D( balances[year].GetBalance(str(accounts.accountVordering.account), 0) )
                #@todo : replace this with visitor logic, once the visitors are implemented
                saldo = dossier.get_openstaand_kapitaal_at(datetime.date(year, 12, 31))
                openstaand_kapitaal[year] += saldo
                openstaand_kapitaal_per_kader[year][dossier.aanvraag.wettelijk_kader] += saldo
                akte_years.add(startdatum.year)
                openstaand_kapitaal_per_akte_jaar.setdefault(str(year), {}).setdefault(str(startdatum.year), 0)
                openstaand_kapitaal_per_akte_jaar[str(year)][str(startdatum.year)] += saldo
        for p in productie.values():
          if p['totaal']:
            p['looptijd'] = p['looptijd'] / p['totaal']
            p['intrest'] = p['intrest'] / p['totaal']
        offset += 1
        sheet.render( Cell( 'A', offset, 'Openstaand kapitaal' ) )
        offset += 1
        for i,(year, kapitaal) in enumerate(openstaand_kapitaal.items()):
            sheet.render( Cell( 'A', offset, year ) )
            sheet.render( Cell( 'B', offset, kapitaal ) )
            offset += 1
        offset += 2
        sheet.render( Cell( 'A', offset, 'Openstaand kapitaal volgens kader' ) )
        offset += 1
        for j,kader in enumerate(kaders):
            sheet.render( Cell( column_name(1+j), offset, kader ) )
        offset += 1
        for i,(year, kapitaal) in enumerate(openstaand_kapitaal_per_kader.items()):
            sheet.render( Cell( 'A', offset, year ) )
            for j,kader in enumerate(kaders):
                sheet.render( Cell( column_name(1+j), offset, kapitaal[kader] ) )
            offset += 1
        offset += 2
        yield UpdateProgress( 3, 4, 'Productie' )
        sheet.render( Cell( 'A', offset, 'Productie' ) )
        offset += 1
        productie_items = list( productie.items() )
        productie_items.sort( key = lambda pi:int(pi[0]) )
        for i,(year, p) in enumerate(productie_items):
          sheet.render( Cell( column_name(0),offset, year))
          sheet.render( Cell( column_name(1),offset, p['totaal']))
          sheet.render( Cell( column_name(2),offset, p['aantal']))
          sheet.render( Cell( column_name(3),offset, p['looptijd']/12))
          sheet.render( Cell( column_name(4),offset, p['intrest']/100))
          offset += 1
        offset += 2
        yield UpdateProgress( 4, 4, 'Terugbetaling' )
        sheet.render( Cell( 'A', offset, 'Terugbetaling' ) )
        offset += 1
        akte_years = [int(akte_year) for akte_year in akte_years]
        akte_years.sort()
        for i,akte_year in enumerate(akte_years):
          sheet.render( Cell( column_name(2+i),offset, akte_year))
          initieel_openstaand_kapitaal = Cell( column_name(2+i),offset+1, productie[str(akte_year)]['totaal'])
          sheet.render( initieel_openstaand_kapitaal )
          vorig_jaar_terugbetaald = None
          for j,year in enumerate(years[1:]):
            sheet.render( Cell( column_name(1),offset+2+3*j, 'Openstaand kapitaal') )
            sheet.render( Cell( column_name(0),offset+2+3*j, year ) )
            openstaand_kapitaal = Cell( column_name(2+i),offset+2+3*j, openstaand_kapitaal_per_akte_jaar.get(str(year),{}).get(str(akte_year),0) )
            sheet.render( openstaand_kapitaal )
            sheet.render( Cell( column_name(1),offset+3+3*j, 'Terugbetaald kapitaal') )
            if int(year) >= int(akte_year):
                terugbetaald = Cell( column_name(2+i),offset+3+3*j,  Sub( initieel_openstaand_kapitaal, openstaand_kapitaal ) )
            else:
                terugbetaald = Cell( column_name(2+i),offset+3+3*j, 0)
            sheet.render( terugbetaald )
            sheet.render( Cell( column_name(1),offset+4+3*j, 'Terugbetaald in %s'%year) )
            if j==0:
              sheet.render( Cell( column_name(2+i),offset+4+3*j, Eq( terugbetaald ) ) )
            else:
              sheet.render( Cell( column_name(2+i),offset+4+3*j, Sub( terugbetaald, vorig_jaar_terugbetaald ) ) )
            vorig_jaar_terugbetaald = terugbetaald
