import datetime
import logging
import string

from integration.spreadsheet import Cell, Eq, Sum, Range

from sqlalchemy import sql,orm

from camelot.core.orm import Session
from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

LOGGER = logging.getLogger('vfinance.model.hypo.report.overzicht_aanvragen')
  
from ...bank.report.abstract import AbstractReport
from vfinance.model.hypo.constants import hypotheek_states
from vfinance.model.hypo.hypotheek import Hypotheek, Bedrag

class AanvraagReport( AbstractReport ):
    """Generate a sheet containing the aanvragen, their status and their result
    """
  
    name = _('Overzicht aanvragen')

    def fill_sheet( self, sheet, offset, options ):
    
        startdatum = options.from_document_date
        einddatum  = options.thru_document_date
        hypotheek_states_dict = dict(hypotheek_states)
        
        session = Session()
        query = session.query( Hypotheek, Bedrag ).filter(Hypotheek.id==Bedrag.hypotheek_id_id)
        query = query.filter( sql.and_(Hypotheek.aanvraagdatum>=options.from_document_date,
                                       Hypotheek.aanvraagdatum<=options.thru_document_date) )
        query = query.order_by(Hypotheek.company_id, Hypotheek.aanvraagnummer)
        query = query.options(orm.joinedload(Hypotheek.roles))
        query = query.options(orm.joinedload(Hypotheek.broker_relation))
        query = query.options(orm.joinedload(Hypotheek.broker_agent))
        
        #query = """select hypo_hypotheek.*,
                          #hypo_bedrag.bedrag as gevraagd_bedrag,
                          #coalesce( (select hypo_goedgekeurd_bedrag.goedgekeurd_bedrag
                                     #from hypo_goedgekeurd_bedrag
                                     #where (hypo_goedgekeurd_bedrag.bedrag=hypo_bedrag.id) and
                                           #(hypo_goedgekeurd_bedrag.type='nieuw') and
                                           #(hypo_goedgekeurd_bedrag.state in ('approved', 'processed', 'ticked'))
                                     #order by hypo_goedgekeurd_bedrag.id desc limit 1),
                                    #0.0 ) as goedgekeurd_bedrag,
                          #(select hypo_beslissing.state
                           #from hypo_goedgekeurd_bedrag
                           #join hypo_beslissing on (hypo_beslissing.id=hypo_goedgekeurd_bedrag.beslissing)
                           #where (hypo_goedgekeurd_bedrag.bedrag=hypo_bedrag.id) and
                                 #(hypo_goedgekeurd_bedrag.type='nieuw')
                           #order by hypo_goedgekeurd_bedrag.id desc limit 1) as beslissing_state,
                          #(select hypo_aanvaarding.state
                           #from hypo_goedgekeurd_bedrag
                           #join hypo_beslissing on (hypo_beslissing.id=hypo_goedgekeurd_bedrag.beslissing)
                           #join hypo_aanvaarding on (hypo_beslissing.id=hypo_aanvaarding.beslissing)
                           #where (hypo_goedgekeurd_bedrag.bedrag=hypo_bedrag.id) and
                                 #(hypo_goedgekeurd_bedrag.type='nieuw')                     
                           #order by hypo_aanvaarding.id desc limit 1) as aanvaarding_state                  
                   #from hypo_hypotheek
                   #join hypo_bedrag on (hypo_bedrag.hypotheek_id=hypo_hypotheek.id)
                   #where (hypo_hypotheek.aanvraagdatum>='%s') and
                         #(hypo_hypotheek.aanvraagdatum<='%s')
                   #order by hypo_hypotheek.aanvraagnummer
                      #"""%(d2t(startdatum), d2t(einddatum))
  
        i = 1
        sheet.render(Cell('A', i, 'Overzicht aanvragen'))
        i += 2
        sheet.render(Cell('A', i, 'Start datum'))
        sheet.render(Cell('B', i, startdatum))
        i += 1
        sheet.render(Cell('A', i, 'Eind datum'))
        sheet.render(Cell('B', i, einddatum))
        i += 1
        sheet.render(Cell('A', i, 'Rapport datum'))
        sheet.render(Cell('B', i, datetime.date.today()))    
        i += 2
        totals_row = i
        sheet.render(Cell('D', i, 'Totaal'))  
        i += 1
        sheet.render(Cell('A', i, 'Nummer'))
        sheet.render(Cell('B', i, 'Ontlener 1'))
        sheet.render(Cell('C', i, 'Ontlener 2'))
        sheet.render(Cell('D', i, 'Datum aanvraag'))
        sheet.render(Cell('E', i, 'Voorziene datum akte'))
        sheet.render(Cell('F', i, 'Status'))
        sheet.render(Cell('G', i, 'Draft'))
        sheet.render(Cell('H', i, 'Compleet'))
        sheet.render(Cell('I', i, 'Goedgekeurd'))
        sheet.render(Cell('J', i, 'Aanvaardingsbrief ontvangen'))
        sheet.render(Cell('K', i, 'Betaald'))
        sheet.render(Cell('L', i, 'Verleden'))
        
        sheet.render( Cell( 'M', offset, 'Master broker' ) )
        sheet.render( Cell( 'N', offset, 'Broker' ) )
        sheet.render( Cell( 'O', offset, 'Agent' ) )
        sheet.render( Cell( 'P', offset, 'Origin' ) )
        
        i += 1
        
        top_row, bottom_row = [], []
        for j,(hypotheek, bedrag) in enumerate(query.yield_per(100)):
            yield UpdateProgress(text=hypotheek.full_number)
            sheet.render(Cell('A', i+j, hypotheek.full_number))
            sheet.render(Cell('B', i+j, hypotheek.borrower_1_name))
            sheet.render(Cell('C', i+j, hypotheek.borrower_2_name))
            sheet.render(Cell('D', i+j, hypotheek.aanvraagdatum))
            sheet.render(Cell('E', i+j, hypotheek.aktedatum))
            sheet.render(Cell('F', i+j, hypotheek_states_dict[hypotheek.state]))
            draft = Cell('G', i+j, bedrag.bedrag)
            # waneer er een beslissings document is gemaakt dat niet als incomplete werd beoordeeld
            # is de aanvraag ooit complete geweest
            if bedrag.beslissing_state not in (None, 'proef', 'incomplete'):
              compleet = Cell('H', i+j, Eq(draft))
            else:
              compleet = Cell('H', i+j, 0 )
            # wanneer er een beslissings document is gemaakt dat is goedgekeurd is de aanvraag
            # ooit goedgekeurd geweest
            if bedrag.beslissing_state in ('approved',):
              goedgekeurd = Cell('I', i+j, bedrag.goedgekeurd_bedrag)
            else:
              goedgekeurd = Cell('I', i+j, 0 )
            if bedrag.aanvaarding_state in ('received',):
              aanvaardingsbrief = Cell('J', i+j, Eq(goedgekeurd))
            else:
              aanvaardingsbrief = Cell('J', i+j, 0 )
            if hypotheek.state in ('payed','processed'):
              betaald = Cell('K', i+j, Eq(goedgekeurd))
            else:
              betaald = Cell('K', i+j, 0 )
            if hypotheek.state in ('processed',):
              verleden = Cell('L', i+j, Eq(goedgekeurd))
            else:
              verleden = Cell('L', i+j, 0 )
            cells = (draft, compleet, goedgekeurd, 
                     aanvaardingsbrief, betaald, verleden)
            sheet.render(cells)
            if j==0:
              top_row = cells
            else:
              bottom_row = cells
  
            if hypotheek.broker_relation is not None:
                sheet.render(Cell('M', i+j, hypotheek.broker_relation.from_rechtspersoon.name))
                sheet.render(Cell('N', i+j, hypotheek.broker_relation.name))
            if hypotheek.broker_agent is not None:
                sheet.render(Cell('O', i+j, hypotheek.broker_agent.name))
            sheet.render(Cell('P', i+j, hypotheek.origin))

        for k,(top_cell, bottom_cell) in enumerate(zip(top_row, bottom_row)):
          sheet.render(Cell(string.uppercase[string.uppercase.index('G') + k], 
                            totals_row, 
                            Sum(Range(bottom_cell, top_cell))) )

