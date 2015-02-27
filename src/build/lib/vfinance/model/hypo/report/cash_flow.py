import datetime
import logging
from vfinance.model.hypo.mortgage_table import aflossingen_van_bedrag

from integration.spreadsheet import Cell, column_name, column_index
from integration.tinyerp.convenience import add_months_to_date

logger = logging.getLogger('vfinance.model.hypo.report.cashflow')

from camelot.core.utils import ugettext, ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from ...bank.report.abstract import AbstractReport
from vfinance.model.hypo.dossier import Dossier

class CashFlowReport( AbstractReport ):
    """Rapport cash flow vd lopende kredieten
    """
  
    name = _('Cashflow')
    
    def fill_sheet( self, sheet, offset, options ):
        
        title_offset = offset
        sheet.render(Cell('A', title_offset, ugettext('Nummer')))
        sheet.render(Cell('B', title_offset, ugettext('Status')))
        sheet.render(Cell('C', title_offset, ugettext('Terug te betalen kapitaal')))
        sheet.render(Cell('D', title_offset, ugettext('Type')))
        offset += 1
        
        def date_to_month(dt):
            return dt.year*12 + dt.month
        
        before_start_date = options.from_document_date - datetime.timedelta(days=1)
        start_month = date_to_month(options.from_document_date)
        start_column = column_index('E')
        # max 20 year because of limit in excel columns
        thru_month = start_month + 12*20
        
        def date_to_column(dt):
            month = date_to_month(dt)
            return column_name(start_column+month-start_month)
        
        dossier_count = Dossier.query.count()
        max_date = options.from_document_date
        for i, dossier in enumerate(Dossier.query.yield_per(10).all()):
            yield UpdateProgress(i, dossier_count, ugettext('Dossier {0.full_number}').format(dossier))
            gb = dossier.get_goedgekeurd_bedrag_at( options.from_document_date )
            if gb == None:
                continue
            if dossier.state=='ended' and dossier.einddatum<options.from_document_date:
                continue
            else:
                logger.debug('calculating cash flow for hypo %s'%dossier.full_number)
                sheet.render(Cell('A', offset, dossier.full_number))
                sheet.render(Cell('B', offset, dossier.state))                
                sheet.render(Cell('C', offset+1, 0))
                sheet.render(Cell('D', offset, 'Kapitaal'))
                sheet.render(Cell('D', offset+1, 'Intrest'))
                aanvangsdatum = gb.aanvangsdatum
                if gb.goedgekeurde_opname_periode:
                    sheet.render(Cell('C', offset, 0))
                    # schuif aanvangsdatum op met opnameperiode, en geef negatief cashflow event
                    # op einddatum opnameperiode
                    aanvangsdatum = add_months_to_date(aanvangsdatum, gb.goedgekeurde_opname_periode)
                    if aanvangsdatum >= options.from_document_date:
                        yield sheet.render(Cell(date_to_column(aanvangsdatum), offset, -1*gb.goedgekeurd_bedrag))
                        max_date = max(max_date, aanvangsdatum)
                else:
                    openstaand_kapitaal = dossier.get_theoretisch_openstaand_kapitaal_at(before_start_date)
                    sheet.render(Cell('C', offset, openstaand_kapitaal))
                for a in aflossingen_van_bedrag(gb,aanvangsdatum):
                    if (a.datum>=options.from_document_date) and (date_to_month(a.datum)<thru_month):
                        sheet.render(Cell(date_to_column(a.datum), offset, float(a.kapitaal)))
                        sheet.render(Cell(date_to_column(a.datum), offset+1, float(a.rente)))
                        max_date = max(max_date, a.datum)
                offset += 2
        column_date = options.from_document_date
        while column_date < max_date:
            sheet.render(Cell(date_to_column(column_date), title_offset, '{0.year}-{0.month}'.format(column_date)))
            column_date = add_months_to_date(column_date, 1)
