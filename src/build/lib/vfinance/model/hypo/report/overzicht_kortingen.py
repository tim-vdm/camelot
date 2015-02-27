import logging

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

LOGGER = logging.getLogger('vfinance.model.hypo.report.overzicht_kortingen')
  
from ...bank.report.abstract import AbstractReport

from vfinance.model.hypo.dossier import Korting

class ReductionReport( AbstractReport ):
    
    name = _('Overzicht kortingen')
    
    def fill_sheet( self, sheet, offset, options ):
        from integration.spreadsheet.base import Cell

        sheet.render(Cell('A', offset, 'Nummer'))
        sheet.render(Cell('B', offset, 'Name'))
        sheet.render(Cell('C', offset, 'Oorspronkelijk bedrag'))
        sheet.render(Cell('D', offset, 'Huidig bedrag'))
        sheet.render(Cell('E', offset, 'Start datum'))
        sheet.render(Cell('F', offset, 'Datum wijziging'))
        sheet.render(Cell('F', offset, 'Datum wijziging'))
        sheet.render(Cell('G', offset, 'Korting type'))
        sheet.render(Cell('H', offset, 'Korting start'))
        sheet.render(Cell('I', offset, 'Korting einde'))
        sheet.render(Cell('J', offset, 'Korting rente'))
        sheet.render(Cell('K', offset, 'Opmerking'))
        sheet.render(Cell('L', offset, 'Status'))
    
        offset += 1
        
        for i, korting in enumerate( Korting.query.yield_per(10).all() ):
            dossier = korting.dossier
            sheet.render(Cell('A', i+offset, dossier.full_number ))
            sheet.render(Cell('B', i+offset, dossier.name ))
            sheet.render(Cell('C', i+offset, dossier.goedgekeurd_bedrag_nieuw.goedgekeurd_bedrag ))
            sheet.render(Cell('D', i+offset, dossier.goedgekeurd_bedrag.goedgekeurd_bedrag ))
            sheet.render(Cell('E', i+offset, dossier.originele_startdatum) )
            sheet.render(Cell('F', i+offset, dossier.startdatum) )
            sheet.render(Cell('G', i+offset, korting.type) )
            sheet.render(Cell('H', i+offset, korting.valid_date_start) )
            sheet.render(Cell('I', i+offset, korting.valid_date_end) )
            sheet.render(Cell('J', i+offset, korting.rente) )
            sheet.render(Cell('K', i+offset, korting.comment) )
            sheet.render(Cell('L', i+offset, dossier.state) )
                             
            if i % 10 == 0:
                yield UpdateProgress( text = unicode( dossier ) )
