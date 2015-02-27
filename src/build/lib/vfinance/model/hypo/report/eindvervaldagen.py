import logging

from integration.spreadsheet import Cell

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

LOGGER = logging.getLogger('vfinance.model.hypo.report.eindvervaldagen')
  
from ...bank.report.abstract import AbstractReport
from vfinance.model.hypo.dossier import Dossier, dossier_statussen

from integration.tinyerp.convenience import add_months_to_date

class Expired( AbstractReport ):
    """Rapport met de dossiers die vervallen zijn of waarvan de eindvervaldag
    naderd.
    """
  
    name = _('Eindvervaldagen')
    
    def fill_sheet( self, sheet, offset, options ):
        from_doc_date = options.from_document_date
        thru_doc_date = options.thru_document_date
        
        if from_doc_date == thru_doc_date:
            thru_doc_date = add_months_to_date( from_doc_date, 2 )
              
        states_description = dict( dossier_statussen )
          
        row = offset
        row += 1
        sheet.render(Cell('A', row, 'Status'))
        sheet.render(Cell('B', row, 'Nummer'))
        sheet.render(Cell('C', row, 'Ontlener 1'))
        sheet.render(Cell('D', row, 'Ontlener 2'))
        sheet.render(Cell('E', row, 'Wettelijk kader'))
        sheet.render(Cell('F', row, 'Type Aflossing'))
        sheet.render(Cell('G', row, 'Goedgekeurd bedrag'))
        sheet.render(Cell('H', row, 'Waarborgen'))
        sheet.render(Cell('I', row, 'Originele startdatum'))
        sheet.render(Cell('J', row, 'Startdatum'))
        sheet.render(Cell('K', row, 'Looptijd'))
        sheet.render(Cell('L', row, 'Verwachtte einddatum'))
        sheet.render(Cell('M', row, 'Einddatum'))
        sheet.render(Cell('N', row, 'Master broker'))
        sheet.render(Cell('O', row, 'Broker'))
        sheet.render(Cell('P', row, 'Agent'))
        row += 1

        query = Dossier.query.filter( Dossier.state != 'ended' )
        total = query.count()
        for i,dossier in enumerate( query.order_by( Dossier.nummer ).yield_per(10).all() ):
            
            einddatum = dossier.einddatum
            if einddatum:
                if einddatum < from_doc_date:
                    continue
                if einddatum > thru_doc_date:
                    continue
            
            verwachtte_einddatum = dossier.goedgekeurd_bedrag.einddatum
            if verwachtte_einddatum > thru_doc_date:
                continue

            goedgekeurd_bedrag = dossier.goedgekeurd_bedrag
            aanvraag = dossier.aanvraag
            
            sheet.render(Cell('A', row, states_description[dossier.state]))
            sheet.render(Cell('B', row, dossier.full_number ))
            sheet.render(Cell('C', row, dossier.borrower_1_name ))
            sheet.render(Cell('D', row, dossier.borrower_2_name ))
            sheet.render(Cell('E', row, aanvraag.wettelijk_kader ))
            sheet.render(Cell('F', row, goedgekeurd_bedrag.goedgekeurd_type_aflossing ))
            sheet.render(Cell('G', row, goedgekeurd_bedrag.goedgekeurd_bedrag ))
            sheet.render(Cell('H', row, dossier.waarborgen))
            sheet.render(Cell('I', row, dossier.originele_startdatum))
            sheet.render(Cell('J', row, dossier.startdatum))
            sheet.render(Cell('K', row, dossier.goedgekeurd_bedrag.goedgekeurde_looptijd))
            sheet.render(Cell('L', row, dossier.goedgekeurd_bedrag.einddatum))
            sheet.render(Cell('M', row, dossier.einddatum))
            broker = dossier.get_broker_at(options.thru_document_date)
            if broker is not None:
                if broker.broker_relation is not None:
                    sheet.render( Cell( 'N', row, broker.broker_relation.from_rechtspersoon.name ) )
                    sheet.render( Cell( 'O', row, broker.broker_relation.name ) )
                if broker.broker_agent is not None:
                    sheet.render( Cell( 'P', row, broker.broker_agent.name ) )
            
            row += 1
            
            if i % 10 == 0:
                yield UpdateProgress( i, total, unicode( dossier ) )
