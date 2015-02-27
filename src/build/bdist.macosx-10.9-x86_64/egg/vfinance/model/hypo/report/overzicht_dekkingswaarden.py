import logging
from sqlalchemy import sql

from camelot.core.orm import Session
from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

LOGGER = logging.getLogger('vfinance.model.hypo.report.overzicht_dekkingswaarden')
  
from ...bank.report.abstract import AbstractReport
from vfinance.model.hypo.dossier import Dossier, Dekking

class CoverageReport( AbstractReport ):
    
    name = _('Overzicht dekkingswaarden')
    
    def fill_sheet( self, sheet, _offset, options ):
        date = options.thru_document_date
        session = Session()
        #
        # Er zitten dossiers id database waarbij de einddatum is ingevuld, maar die toch nog
        # running zijn.
        #       
        query = session.query( Dossier, Dekking ).filter( sql.and_( sql.or_(Dossier.einddatum==None,
                                                                            Dossier.einddatum>=date,
                                                                            Dossier.state=='running' ),
                                                                    Dekking.valid_date_start <= date,
                                                                    Dekking.dossier_id == Dossier.id ) )
        query = query.order_by( Dossier.nummer, Dekking.valid_date_start.desc() )
        query = query.distinct( Dossier.nummer )
                        
        # query = """select id from hypo_dossier 
        #           where (einddatum is null or einddatum>='%s' or state='running') and
        #             (select hypo_dekking.type from hypo_dekking where 
        #              hypo_dekking.dossier=hypo_dossier.id and
        #              valid_date_start<='%s' order by valid_date_start desc limit 1)='%s'
        #           order by hypo_dossier.nummer
        #              """%(date, date, dekking_type)
        
        from integration.spreadsheet.base import Cell, Add, Min, Mul, Sum, Range
        sheet.render(Cell('A', 1, 'Dekkingswaarden'))
        sheet.render(Cell('A', 2, 'Datum'))
        sheet.render(Cell('B', 2, date))
      
        offset = 4
        top_cells, bottom_cells = [], []
        sheet.render(Cell('A', offset, 'Totaal'))
        total_row = offset
        offset += 1
        sheet.render(Cell('A', offset, 'Dossier'))
        sheet.render(Cell('B', offset, 'Name'))
        sheet.render(Cell('C', offset, 'Oorspronkelijk bedrag'))
        sheet.render(Cell('D', offset, 'Huidig bedrag'))
        sheet.render(Cell('E', offset, 'Start datum'))
        sheet.render(Cell('F', offset, 'Datum wijziging'))
        sheet.render(Cell('G', offset, 'Hypotheckaire waarb.'))
        sheet.render(Cell('H', offset, 'Venale waarb.'))
        sheet.render(Cell('I', offset, 'Andere waarborgen'))
        sheet.render(Cell('J', offset, 'Openstaand kapitaal'))
        sheet.render(Cell('K', offset, 'Waarborg'))
        sheet.render(Cell('L', offset, 'Dekkingswaarde'))
        sheet.render(Cell('M', offset, 'Jkp'))
        sheet.render(Cell('N', offset, 'Type Dekking'))
        sheet.render(Cell('O', offset, 'Start Dekking'))
        offset += 1
        
        for i, (dossier, dekking) in enumerate( query.yield_per(10).all() ):
            sheet.render(Cell('A', i+offset, dossier.full_number ))
            sheet.render(Cell('B', i+offset, dossier.name ))
            sheet.render(Cell('C', i+offset, dossier.goedgekeurd_bedrag_nieuw.goedgekeurd_bedrag ))
            sheet.render(Cell('D', i+offset, dossier.goedgekeurd_bedrag.goedgekeurd_bedrag ))
            sheet.render(Cell('E', i+offset, dossier.originele_startdatum) )
            sheet.render(Cell('F', i+offset, dossier.startdatum) )
            
            hyp_waarb     = Cell('G', i+offset, dossier.hypothecaire_waarborgen )
            ven_waarde    = Cell('H', i+offset, dossier.waarborgen_venale_verkoop )
            bijk_waarb    = Cell('I', i+offset, dossier.waarborg_bijkomend_waarde )
            open_kap      = Cell('J', i+offset, dossier.get_openstaand_kapitaal_at( date ) )
            waarb         = Cell('K', i+offset, Add(Min(hyp_waarb, Mul(0.75, ven_waarde)), bijk_waarb) )
            dek_waarde    = Cell('L', i+offset, Min(open_kap, waarb))
            jkp           = Cell('M', i+offset, dossier.goedgekeurd_bedrag.goedgekeurde_jaarlijkse_kosten )
            dekking_type  = Cell('N', i+offset, dekking.type )
            start_dekking = Cell('O', i+offset, dekking.valid_date_start )
            
            numbers = [hyp_waarb, ven_waarde, bijk_waarb, open_kap, waarb, dek_waarde, jkp, dekking_type, start_dekking]
            sheet.render(numbers)
            
            if i==0:
                top_cells = numbers
            else:
                bottom_cells = numbers
                
            if i % 10:
                yield UpdateProgress( text = unicode( dossier ) )
                
        for top_cell, bottom_cell in zip(top_cells, bottom_cells):
            sheet.render(Cell(top_cell.col, total_row, Sum(Range(top_cell, bottom_cell))))
