import logging

from integration.spreadsheet import Cell, Sum, Range

from camelot.core.utils import ugettext_lazy as _
from camelot.view import action_steps

LOGGER = logging.getLogger('vfinance.model.hypo.report.fiscal_certificate')
  
from ...bank.report.abstract import AbstractReport
from ..notification.fiscal_certificate import FiscalCertificate as FiscalCertificateNotification
from vfinance.model.hypo.dossier import Dossier, dossier_statussen

class FiscalCertificateReport( AbstractReport ):
    """Overzicht van de inhoud van de fiscale attestend
    """
  
    name = _('Fiscal certificates')
    
    def fill_sheet( self, sheet, offset, options ):
        yield action_steps.UpdateProgress(text=self.name)
        states_description = dict(dossier_statussen)
        
        notification = FiscalCertificateNotification()
        options.notification_date = options.thru_document_date
        
        row = offset
        row += 1
        total_row = row
        row += 1
        sheet.render(Cell('A', row, 'Status'))
        sheet.render(Cell('B', row, 'Nummer'))
        sheet.render(Cell('C', row, 'Ontlener 1'))
        sheet.render(Cell('D', row, 'Ontlener 2'))
        sheet.render(Cell('E', row, 'Aktedatum'))
        sheet.render(Cell('F', row, 'Ontleend bedrag'))
        sheet.render(Cell('G', row, 'Openstaand kapitaal'))
        sheet.render(Cell('H', row, 'Betaald kapitaal'))
        sheet.render(Cell('I', row, 'Betaalde intrest'))
        sheet.render(Cell('J', row, 'Terugbetaald kapitaal'))
        sheet.render(Cell('K', row, 'Datum terugbetaling'))

        row += 1
        top_cells, bottom_cells = [], []
        dossier_query = Dossier.query.filter(Dossier.originele_startdatum<=options.thru_document_date)
        total = dossier_query.count()
        for i,dossier in enumerate( dossier_query.order_by( Dossier.nummer ).yield_per(10).all() ):
            sheet.render(Cell('A', row, states_description[dossier.state]))
            sheet.render(Cell('B', row, dossier.full_number ))
            sheet.render(Cell('C', row, dossier.borrower_1_name ))
            sheet.render(Cell('D', row, dossier.borrower_2_name ))
            context = notification.get_context(dossier, options)
            sheet.render(Cell('E', row, context['aktedatum']))
            numbers = [
                Cell('F', row, context['origineel_bedrag']),
                Cell('G', row, context['openstaand_kapitaal']),
                Cell('H', row, context['betaald_kapitaal']),
                Cell('I', row, context['betaalde_intrest']),
                Cell('J', row, context['terugbetaald_kapitaal']),
            ]
            sheet.render(*numbers)
            sheet.render(Cell('K', row, context['terugbetalingsdatum']))
            if i==0:
                top_cells = numbers
            else:
                bottom_cells = numbers
            row += 1
            if i % 10 == 0:
                yield action_steps.UpdateProgress( i, total, unicode( dossier ) )
           
        for top_cell, bottom_cell in zip(top_cells, bottom_cells):
            sheet.render( Cell(top_cell.col, total_row, Sum(Range(top_cell, bottom_cell)) ) )