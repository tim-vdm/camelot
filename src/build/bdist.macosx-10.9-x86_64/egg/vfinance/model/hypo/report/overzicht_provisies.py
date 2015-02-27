import logging
import operator

logger = logging.getLogger('vfinance.model.hypo.report.overzicht_provisies')

from integration.spreadsheet import Cell, Sum, Range

from camelot.core.orm import Session
from camelot.core.utils import ugettext_lazy as _
from camelot.view import action_steps

from ...bank.report.abstract import AbstractReport
from ..dossier import Dossier, dossier_statussen
from ..visitor import AbstractHypoVisitor
from ...bank.visitor import CustomerBookingAccount

class ProvisieReport( AbstractReport ):

    name = _('Overzicht provisies')

    def fill_sheet( self, sheet, offset, options ):
        states_description = dict(dossier_statussen)

        visitor = AbstractHypoVisitor()

        row = offset
        row += 1
        total_row = row
        row += 1
        sheet.render(Cell('A', row, 'Status'))
        sheet.render(Cell('B', row, 'Nummer'))
        sheet.render(Cell('C', row, 'Ontlener 1'))
        sheet.render(Cell('D', row, 'Ontlener 2'))
        sheet.render(Cell('E', row, 'Startdatum'))
        sheet.render(Cell('F', row, 'Aanvraagdatum'))
        sheet.render(Cell('G', row, 'Ontleend bedrag'))
        sheet.render(Cell('H', row, 'Openstaand kapitaal'))
        sheet.render(Cell('I', row, 'Openstaand klant'))
        sheet.render(Cell('J', row, 'Totaal openstaand'))
        sheet.render(Cell('K', row, 'Waarborgen'))
        sheet.render(Cell('L', row, 'Initieel tekort'))
        sheet.render(Cell('M', row, 'Provisie'))
        sheet.render(Cell('N', row, 'Te boeken'))
        sheet.render(Cell('O', row, 'Openstaande vervaldagen'))
        sheet.render(Cell('P', row, 'Eerste openstaande vervaldag'))
        sheet.render(Cell('Q', row, 'Periodiciteit'))
        sheet.render(Cell('R', row, 'Wettelijk kader'))

        session = Session()
        dossier_query = session.query( Dossier ).order_by( Dossier.nummer )
        dossier_count = dossier_query.count()

        top_cells, bottom_cells = [], []
        for i, dossier in enumerate( dossier_query.yield_per( 10 ) ):
            row += 1
            yield action_steps.UpdateProgress( i, dossier_count, dossier.full_number )
            loan_schedule = dossier.goedgekeurd_bedrag
            sheet.render( Cell( 'A', row, states_description[dossier.state] ) )
            sheet.render( Cell( 'B', row, dossier.full_number ) )
            sheet.render( Cell( 'C', row, dossier.borrower_1_name ) )
            sheet.render( Cell( 'D', row, dossier.borrower_2_name ) )
            sheet.render( Cell( 'E', row, dossier.originele_startdatum ) )
            sheet.render( Cell( 'F', row, dossier.aanvraag.aanvraagdatum) )

            # @todo : haal openstaand kapitaal uit database ipv uit Venice
            openstaand_kapitaal = dossier.get_openstaand_kapitaal_at(options.thru_document_date)
            # @todo : bepaal openstaande verrichtingen op datum ipv nu
            # naamgeving is hier nt goed, di de staat vd klant rekening,
            # en niet uitsluitend de betalingen

            open_repayments = list(visitor.get_entries(loan_schedule,
                                                       thru_document_date=options.thru_document_date,
                                                       fulfillment_types=['repayment', 'reservation'],
                                                       conditions=[('open_amount', operator.ne, 0)],
                                                       account=CustomerBookingAccount()))
            
            open_repayments.sort(key=lambda repayment:repayment.doc_date)
            number_of_open_repayments = len(open_repayments)
            first_open_repayment_doc_date = None
            if number_of_open_repayments>0:
                first_open_repayment_doc_date = open_repayments[0].doc_date
            
            openstaande_betalingen = dossier.get_som_openstaande_verrichtingen()
            waarborgen = dossier.waarborgen
            totaal_openstaand = openstaand_kapitaal + openstaande_betalingen
            initieel_tekort = max( 0, loan_schedule.goedgekeurd_bedrag - waarborgen )
            provisie = max( 0, totaal_openstaand - waarborgen )
            if waarborgen > totaal_openstaand:
                te_boeken = 0
            else:
                te_boeken = min( provisie, max( totaal_openstaand - loan_schedule.goedgekeurd_bedrag, 0 ) )

            numbers = [
                Cell( 'G', row, loan_schedule.goedgekeurd_bedrag ),
                Cell( 'H', row, openstaand_kapitaal ),
                Cell( 'I', row, openstaande_betalingen ),
                Cell( 'J', row, totaal_openstaand ),
                Cell( 'K', row, waarborgen ),
                Cell( 'L', row, initieel_tekort ),
                Cell( 'M', row, provisie ),
                Cell( 'N', row, te_boeken ),
                Cell( 'O', row, number_of_open_repayments ),
            ]
            sheet.render( *numbers )
            sheet.render( Cell( 'P', row, first_open_repayment_doc_date ) )
            sheet.render( Cell( 'Q', row, dossier.goedgekeurd_terugbetaling_interval ) )
            sheet.render( Cell( 'R', row, dossier.aanvraag.wettelijk_kader ) )

            if i==0:
                top_cells = numbers
            else:
                bottom_cells = numbers

        for top_cell, bottom_cell in zip(top_cells, bottom_cells):
            sheet.render( Cell(top_cell.col, total_row, Sum(Range(top_cell, bottom_cell)) ) )