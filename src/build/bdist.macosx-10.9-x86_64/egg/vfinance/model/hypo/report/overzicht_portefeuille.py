import logging

logger = logging.getLogger('vfinance.model.hypo.report.overzicht_portefeuille')

from camelot.core.orm import Session
from camelot.core.utils import ugettext_lazy as _
from camelot.view import action_steps

from integration.spreadsheet import Cell

from sqlalchemy import sql

from ..dossier import Dossier, dossier_statussen
from overzicht_productie import ValueOptions, ProductieReport

dossier_statussen = dict(dossier_statussen)


# todo, cf mail Jelle van 5/3/2014
# dossiers met een wijziging later dan thru date vh rapport, vallen
# uit het rapport
#
# Ik heb rapport bijgevoegd in bijlage. De nummers 3195, 3439, 3572, 3673, 3682 en 
# 3777 zijn hieruit verdwenen, terwijl ze nog lopende zijn. 3439 en 3572 zijn volgens 
# mij wentelkredieten maar deze kredieten worden niet op 1/1 verlengd. Bij de andere 
# zijn er wijzingen doorgevoerd op het schema. Kan je mij vertellen waarom ze uit 
# het portfeuille overzicht zijn geslopen op 1/1/2014?

class PortefeuilleReport( ProductieReport ):
    """Rapport alle dossiers.
    """
  
    name = _('Overzicht portefeuille')
    
    def fill_sheet( self, sheet, offset, options ):        
        value_options = ValueOptions()
        yield action_steps.ChangeObject( value_options )
        
        row = offset
        row += 1
        sheet.render(Cell('A', row, 'Status'))
        sheet.render(Cell('B', row, 'Dossier'))
        sheet.render(Cell('C', row, 'Ontlener 1'))
        sheet.render(Cell('D', row, 'Ontlener 2'))
        sheet.render(Cell('E', row, 'Aanvraagdatum'))
        sheet.render(Cell('F', row, 'Goedgekeurd bedrag'))
        sheet.render(Cell('G', row, 'Jaarlijkse kosten'))
        sheet.render(Cell('H', row, 'Periodiciteit'))
        sheet.render(Cell('I', row, 'Looptijd'))
        sheet.render(Cell('J', row, 'Datum'))
        sheet.render(Cell('K', row, 'Waarborgen'))
        sheet.render(Cell('L', row, 'Quotiteit'))
        sheet.render(Cell('M', row, 'Present value'))
        sheet.render(Cell('N', row, 'Future value'))
        sheet.render(Cell('O', row, 'Gewest'))
        sheet.render(Cell('P', row, 'Master broker'))
        sheet.render(Cell('Q', row, 'Broker'))
        sheet.render(Cell('R', row, 'Agent'))
        row += 1
        
        session = Session()
        dossier_query = session.query( Dossier ).filter( sql.and_( Dossier.state.in_( ['opnameperiode','running'] ),
                                                                   Dossier.startdatum <= options.thru_document_date ) ).order_by( Dossier.nummer )
        dossier_count = dossier_query.count()
        for i, dossier in enumerate( dossier_query.yield_per( 10 ) ):
            yield action_steps.UpdateProgress( i, dossier_count, unicode( dossier ) )
            gb = dossier.goedgekeurd_bedrag
            sheet.render( Cell( 'A', row, dossier_statussen[dossier.state] ) )
            self.add_goedgekeurd_bedrag( sheet, row, value_options, options, gb )
            row += 1
