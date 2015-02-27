from decimal import Decimal as D
import logging

from sqlalchemy import sql

from integration.spreadsheet import Cell, Sub, Mul

from vfinance.model.hypo.beslissing import GoedgekeurdBedrag
from ...bank.report.abstract import AbstractReport

from camelot.core.utils import ugettext, ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

logger = logging.getLogger('vfinance.model.hypo.report.overzicht_beslissingen')

class BeslissingReport( AbstractReport ):
  
    name = _('Overzicht beslissingen')
    
    def fill_sheet( self, sheet, offset, options ):
        
        startdatum = options.from_document_date
        einddatum = options.thru_document_date
      
        offset += 1
        sheet.render( Cell( 'A', offset, ugettext('Status') ) )
        sheet.render( Cell( 'B', offset, ugettext('Aanvraag') ) )
        sheet.render( Cell( 'C', offset, ugettext('Ontlener 1') ) )
        sheet.render( Cell( 'D', offset, ugettext('Ontlener 2') ) )
        sheet.render( Cell( 'E', offset, ugettext('Datum') ) )
        sheet.render( Cell( 'F', offset, ugettext('Gevraagd bedrag') ) )
        sheet.render( Cell( 'G', offset, ugettext('Goedgekeurd bedrag') ) )
        sheet.render( Cell( 'H', offset, ugettext('Jaarlijkse kosten') ) )
        sheet.render( Cell( 'I', offset, ugettext('Periodiciteit') ) )
        sheet.render( Cell( 'J', offset, ugettext('Looptijd') ) )
        sheet.render( Cell( 'K', offset, ugettext('Quotiteit') ) )
        sheet.render( Cell( 'L', offset, ugettext('Terugbetalingsratio') ) )
        sheet.render( Cell( 'M', offset, ugettext('Aflossing') ) )
        sheet.render( Cell( 'N', offset, ugettext('Waarborgen') ) )
        sheet.render( Cell( 'O', offset, ugettext('Inkomsten') ) )
        sheet.render( Cell( 'P', offset, ugettext('Bruto inkomsten') ) )
        sheet.render( Cell( 'Q', offset, ugettext('Master broker') ) )
        sheet.render( Cell( 'R', offset, ugettext('Broker') ) )
        sheet.render( Cell( 'S', offset, ugettext('Agent') ) )
            
        for gb in GoedgekeurdBedrag.query.filter( sql.and_( GoedgekeurdBedrag.datum >= startdatum,
                                                            GoedgekeurdBedrag.datum <= einddatum,
                                                            GoedgekeurdBedrag.beslissing_state.in_( ['approved', 'ticked'] ) ) ).all():
            if offset % 10 == 0:
                yield UpdateProgress( text = unicode( gb ) )
            
            offset += 1
            sheet.render( Cell( 'A', offset, gb.beslissing.state ) )
            hypotheek = gb.bedrag.hypotheek_id
            sheet.render( Cell( 'A', offset, gb.beslissing.state ) )
            sheet.render( Cell( 'B', offset, hypotheek.full_number ) )
            sheet.render( Cell( 'C', offset, hypotheek.borrower_1_name ) )
            sheet.render( Cell( 'D', offset, hypotheek.borrower_2_name ) )
            sheet.render( Cell( 'E', offset, gb.beslissing.datum ) )
            sheet.render( Cell( 'F', offset, gb.gevraagd_bedrag ) )
            goedgekeurd_bedrag = Cell( 'G', offset, gb.goedgekeurd_bedrag or 0 )
            sheet.render( goedgekeurd_bedrag )
            sheet.render( Cell( 'H', offset, D(gb.goedgekeurde_jaarlijkse_kosten or 0) ) )
            sheet.render( Cell( 'I', offset, gb.goedgekeurd_terugbetaling_interval ) )
            looptijd = Cell( 'J', offset, gb.looptijd )
            sheet.render( looptijd )
            sheet.render( Cell( 'K', offset, gb.beslissing.quotiteit ) )
            sheet.render( Cell( 'L', offset, gb.beslissing.goedgekeurde_terugbetalingsratio ) )
            maandelijkse_aflossing = Cell( 'M', offset, gb.maandelijkse_goedgekeurde_aflossing or 0 )
            sheet.render( maandelijkse_aflossing )
            sheet.render( Cell( 'N', offset, gb.beslissing.waarborgen ) )
            totaal_inkomsten = Mul( maandelijkse_aflossing, looptijd )
            sheet.render( Cell( 'O', offset, totaal_inkomsten ) )
            sheet.render( Cell( 'P', offset, Sub( totaal_inkomsten, goedgekeurd_bedrag ) ) )
            if hypotheek.broker_relation is not None:
                sheet.render(Cell('Q', offset, hypotheek.broker_relation.from_rechtspersoon.name))
                sheet.render(Cell('R', offset, hypotheek.broker_relation.name))
            if hypotheek.broker_agent is not None:
                sheet.render(Cell('S', offset, hypotheek.broker_agent.name))
