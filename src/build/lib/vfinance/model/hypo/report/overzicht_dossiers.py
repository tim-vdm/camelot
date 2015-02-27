import logging

from integration.spreadsheet import Cell, Sum, Range, Sub

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

LOGGER = logging.getLogger('vfinance.model.hypo.report.overzicht_dossiers')
  
from ...bank.report.abstract import AbstractReport
from ..dossier import Dossier, dossier_statussen
from ..mortgage_table import capital_due_according_to_schedule

class DossierReport( AbstractReport ):
    """Rapport met de lopende dossiers, hun theoretisch openstaand kapitaal, en
    hun werkelijk openstaand kapitaal.
    """
  
    name = _('Overzicht dossiers')
    
    def fill_sheet( self, sheet, offset, options ):
        thru_document_date = options.thru_document_date
        states_description = dict(dossier_statussen)
          
        row = offset
        total_row = row
        sheet.render(Cell('C', row, 'Totaal'))
        row += 1
        sheet.render(Cell('E', row, 'Openstaand kapitaal'))
        row += 1
        sheet.render(Cell('A', row, 'Status'))
        sheet.render(Cell('B', row, 'Nummer'))
        sheet.render(Cell('C', row, 'Ontlener 1'))
        sheet.render(Cell('D', row, 'Ontlener 2'))
        sheet.render(Cell('E', row, 'Vervaldag'))
        sheet.render(Cell('F', row, 'Boekhouding'))
        sheet.render(Cell('G', row, 'Theoretisch'))
        sheet.render(Cell('H', row, 'Verschil'))
        sheet.render(Cell('I', row, 'Wettelijk kader'))
        sheet.render(Cell('J', row, 'Waarborgen'))
        sheet.render(Cell('K', row, 'Type staatswaarborg'))
        sheet.render(Cell('L', row, 'Bedrag staatswaarborg'))
        sheet.render(Cell('M', row, 'Originele startdatum'))
        sheet.render(Cell('N', row, 'Startdatum'))
        sheet.render(Cell('O', row, 'Looptijd'))
        sheet.render(Cell('P', row, 'Verwachtte einddatum'))
        sheet.render(Cell('Q', row, 'Einddatum'))
        sheet.render(Cell('R', row, 'Jaarlijkse kosten'))
        sheet.render(Cell('S', row, 'Master broker'))
        sheet.render(Cell('T', row, 'Broker'))
        sheet.render(Cell('U', row, 'Agent'))
        sheet.render(Cell('V', row, 'Ontleend bedrag'))
        sheet.render(Cell('W', row, 'Goedgekeurde periodieke intrest'))
        sheet.render(Cell('X', row, 'Goedgekeurde periodiciteit'))
        row += 1
        top_cells, bottom_cells = [], []
        total = Dossier.query.count()
        for i,dossier in enumerate( Dossier.query.order_by( Dossier.nummer ).yield_per(10).all() ):
            schedule = dossier.get_goedgekeurd_bedrag_at(thru_document_date)
            if schedule is None:
                # the dossier was not yet active at the thru document date
                continue
            sheet.render(Cell('A', row, states_description[dossier.state]))
            sheet.render(Cell('B', row, dossier.full_number ))
            sheet.render(Cell('C', row, dossier.borrower_1_name ))
            sheet.render(Cell('D', row, dossier.borrower_2_name ))
            theoretisch_openstaand_kapitaal = Cell('E', row, dossier.get_theoretisch_openstaand_kapitaal_at(thru_document_date) )
            openstaand_kapitaal = Cell('F', row, dossier.get_openstaand_kapitaal_at(thru_document_date))
            sheet.render(Cell('G', row, capital_due_according_to_schedule(
                thru_document_date,
                schedule,
                dossier
                )))
            verschil = Cell('H', row, Sub(theoretisch_openstaand_kapitaal, openstaand_kapitaal))
            sheet.render(Cell('I', row, dossier.aanvraag.wettelijk_kader))
            waarborgen = Cell('J', row, dossier.waarborgen)
            sheet.render(Cell('K', row, dossier.get_functional_setting_description_at(thru_document_date, 'state_guarantee') or ''))
            sheet.render(Cell('L', row, dossier.get_applied_feature_value_at(thru_document_date, 'state_guarantee', 0)))
            numbers = [theoretisch_openstaand_kapitaal, openstaand_kapitaal, verschil, waarborgen]
            sheet.render(Cell('M', row, dossier.originele_startdatum))
            sheet.render(Cell('N', row, dossier.startdatum))
            sheet.render(Cell('O', row, schedule.goedgekeurde_looptijd))
            sheet.render(Cell('P', row, schedule.einddatum))
            sheet.render(Cell('Q', row, dossier.einddatum))
            sheet.render(Cell('R', row, schedule.goedgekeurde_jaarlijkse_kosten or 0))
            broker = dossier.get_broker_at(options.thru_document_date)
            if broker is not None:
                if broker.broker_relation is not None:
                    sheet.render( Cell( 'S', row, broker.broker_relation.from_rechtspersoon.name ) )
                    sheet.render( Cell( 'T', row, broker.broker_relation.name ) )
                if broker.broker_agent is not None:
                    sheet.render( Cell( 'U', row, broker.broker_agent.name ) )
            sheet.render(Cell('V', row, dossier.goedgekeurd_bedrag.goedgekeurd_bedrag))
            sheet.render(Cell('W', row, dossier.goedgekeurd_bedrag.goedgekeurde_rente))
            sheet.render(Cell('X', row, dossier.goedgekeurd_bedrag.goedgekeurd_terugbetaling_interval))
            sheet.render(*numbers)
            if i==0:
                top_cells = numbers
            else:
                bottom_cells = numbers
            row += 1
            if i % 10 == 0:
                yield UpdateProgress( i, total, unicode( dossier ) )
           
        for top_cell, bottom_cell in zip(top_cells, bottom_cells):
            sheet.render( Cell(top_cell.col, total_row, Sum(Range(top_cell, bottom_cell)) ) )
