import logging
from vfinance.model.hypo.mortgage_table import aflossingen_van_bedrag

from integration.spreadsheet import Cell

logger = logging.getLogger('vfinance.model.hypo.report.overzicht_prorata')

from camelot.core.utils import ugettext, ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from ...bank.report.abstract import AbstractReport
from vfinance.model.hypo.dossier import Dossier

class ProrataReport( AbstractReport ):
    """Generate a sheet with prorata van lopende dossiers
    """
  
    name = _('Overzicht prorata')
   
    def fill_sheet( self, sheet, offset, options ):
        
        cutoff_date = options.thru_document_date
    
        offset += 1
        sheet.render( Cell( 'A', offset, ugettext('Nummer') ) )
        sheet.render( Cell( 'B', offset, ugettext('Naam') ) )
        sheet.render( Cell( 'C', offset, ugettext('Laatste vervaldag') ) )
        sheet.render( Cell( 'D', offset, ugettext('Eerstvolgende vervaldag') ) )
        sheet.render( Cell( 'E', offset, ugettext('Rente') ) )
        sheet.render( Cell( 'F', offset, ugettext('Prorata') ) )
        sheet.render( Cell( 'G', offset, ugettext('Openstaand kapitaal')))
        
        offset += 1
        totaal = 0
        row = 0
        for i, dossier in enumerate( Dossier.query.filter_by( state = 'running' ).order_by( Dossier.nummer ).all() ):
            row = i + offset
            if row % 10 == 0:
                yield UpdateProgress( text = dossier.full_number )
            sheet.render( Cell( 'A', row, dossier.full_number ) )
            sheet.render( Cell( 'B', row, unicode( dossier ) ) )
            laatste_vervaldag = dossier.startdatum
            if laatste_vervaldag <= cutoff_date:
                eerstvolgende_vervaldag = None
                rente = None
                bedrag = dossier.goedgekeurd_bedrag
                for aflossing in aflossingen_van_bedrag( bedrag, laatste_vervaldag ):
                    if aflossing.datum > cutoff_date:
                        eerstvolgende_vervaldag = aflossing.datum
                        rente = aflossing.rente
                        sheet.render( Cell( 'D', row, eerstvolgende_vervaldag ) )
                        sheet.render( Cell( 'E', row, rente ) )
                        sheet.render(Cell('G', row, aflossing.capital_due + aflossing.capital))
                        break
                    laatste_vervaldag = aflossing.datum
                sheet.render( Cell( 'C', row, laatste_vervaldag ) )
                if eerstvolgende_vervaldag:
                    prorata = rente*(cutoff_date-laatste_vervaldag).days/(eerstvolgende_vervaldag-laatste_vervaldag).days
                    sheet.render( Cell( 'F', row, prorata ) )
                    totaal += prorata
              
        row = row + 1
        sheet.render( Cell( 'E', row, 'Totaal' ) )
        sheet.render( Cell( 'F', row, totaal ) )
