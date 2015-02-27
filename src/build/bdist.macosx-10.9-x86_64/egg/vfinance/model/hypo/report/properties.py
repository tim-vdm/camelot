import logging

from integration.spreadsheet.base import Cell

from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import Session
from camelot.view.action_steps import UpdateProgress

LOGGER = logging.getLogger('vfinance.model.hypo.report.properties')
  
from ...bank.report.abstract import AbstractReport
from .. import hypotheek, beslissing, dossier

from sqlalchemy import sql

class PropertiesReport( AbstractReport ):
    """Overzicht van het gehypothekeerde vastgoed
    """
  
    name = _('Gehypothekeerde goeden')
    
    def fill_sheet( self, sheet, offset, options ):
        session = Session()
        states_description = dict(dossier.dossier_statussen)

        sheet.render(Cell('A', offset, 'Dossier id'))
        sheet.render(Cell('B', offset, 'Status'))
        sheet.render(Cell('C', offset, 'Dossier' ))
        sheet.render(Cell('D', offset, 'Borrower 1'))
        sheet.render(Cell('E', offset, 'Borrower 2'))
        sheet.render(Cell('F', offset, 'Application'))
        sheet.render(Cell('G', offset, 'Ontleend bedrag'))
        sheet.render(Cell('H', offset, 'Periodieke intrest'))
        sheet.render(Cell('I', offset, 'Looptijd'))
        sheet.render(Cell('J', offset, 'Type'))
        sheet.render(Cell('K', offset, 'Property id'))
        sheet.render(Cell('L', offset, 'Kadaster'))
        sheet.render(Cell('M', offset, 'Vrijwillige verkoop'))
        sheet.render(Cell('N', offset, 'Gedwongen verkoop'))
        sheet.render(Cell('O', offset, 'Ontleend bedrag'))
        sheet.render(Cell('P', offset, 'City code'))
        sheet.render(Cell('Q', offset, 'City'))
        sheet.render(Cell('J', offset, 'Street'))
        offset += 1

        query = session.query(hypotheek.TeHypothekerenGoed,
                              hypotheek.GoedAanvraag,
                              hypotheek.Hypotheek,
                              hypotheek.Bedrag,
                              beslissing.GoedgekeurdBedrag,
                              dossier.Dossier)
        
        query = query.filter( sql.and_( hypotheek.TeHypothekerenGoed.id == hypotheek.GoedAanvraag.te_hypothekeren_goed_id,
                                        hypotheek.GoedAanvraag.hypotheek_id == hypotheek.Hypotheek.id,
                                        hypotheek.Hypotheek.id==hypotheek.Bedrag.hypotheek_id_id,
                                        hypotheek.Bedrag.id==beslissing.GoedgekeurdBedrag.bedrag_id,
                                        beslissing.GoedgekeurdBedrag.id==dossier.Dossier.goedgekeurd_bedrag_id) )
        
        row = offset
        count = query.count()
        for i, (real_property, _rpa, application, bedrag, goedgekeurd_bedrag, hypo_dossier) in enumerate(query.yield_per(10)):
            if i%10 == 0:
                yield UpdateProgress(i, count, hypo_dossier.full_number)
            sheet.render(Cell('A', row, hypo_dossier.id))
            sheet.render(Cell('B', row, states_description[hypo_dossier.state]))
            sheet.render(Cell('C', row, hypo_dossier.full_number ))
            sheet.render(Cell('D', row, hypo_dossier.borrower_1_name ))
            sheet.render(Cell('E', row, hypo_dossier.borrower_2_name ))
            sheet.render(Cell('F', row, application.full_number ))
            sheet.render(Cell('G', row, goedgekeurd_bedrag.goedgekeurd_bedrag ))
            sheet.render(Cell('H', row, goedgekeurd_bedrag.goedgekeurde_rente ))
            sheet.render(Cell('I', row, goedgekeurd_bedrag.goedgekeurde_looptijd ))
            sheet.render(Cell('J', row, bedrag.type_aflossing ))
            sheet.render(Cell('K', row, real_property.id ))
            sheet.render(Cell('L', row, real_property.kadaster ))
            sheet.render(Cell('M', row, real_property.vrijwillige_verkoop ))
            sheet.render(Cell('N', row, real_property.gedwongen_verkoop ))
            sheet.render(Cell('O', row, real_property.postcode ))
            sheet.render(Cell('P', row, real_property.gemeente ))
            sheet.render(Cell('Q', row, real_property.straat ))
            row += 1
        