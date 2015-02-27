from decimal import Decimal as D
import logging

from integration.spreadsheet import Cell

from sqlalchemy import sql

from camelot.admin.object_admin import ObjectAdmin
from camelot.core.utils import ugettext_lazy as _
from camelot.view import action_steps
from camelot.view.controls import delegates

LOGGER = logging.getLogger('vfinance.model.hypo.report.overzicht_dossiers')
  
from ...bank.report.abstract import AbstractReport
from ..akte import Akte
from ..wijziging import Wijziging
from ..beslissing import GoedgekeurdBedrag
from ..mortgage_table import present_en_future_value_van_bedrag
from ...bank.varia import Postcodes

class ValueOptions( object ):
    
    def __init__( self ):
        self.present_value_rate = D(6)
        self.future_value_rate = D(4)
        
    class Admin( ObjectAdmin ):
        list_display = ['present_value_rate', 'future_value_rate']
        field_attributes = { 'present_value_rate':{'editable':True,
                                                   'delegate':delegates.FloatDelegate,
                                                   'decimal':True},
                             'future_value_rate':{'editable':True,
                                                   'delegate':delegates.FloatDelegate,
                                                   'decimal':True}, }
        
class ProductieReport( AbstractReport ):
    """Rapport met nieuwe dossiers.
    """
  
    name = _('Overzicht productie')
    
    def add_goedgekeurd_bedrag( self, sheet, row, value_options, options, gb ):
        """Generate goedgekeurd_bedrag like objects containing information on the
        produced hypotheken. + some additional attributes : aflossingen, present_value, future_value, 
        datum, ..."""
        
        dossier = gb.dossier
        sheet.render( Cell( 'B', row, dossier.full_number ) )
        sheet.render( Cell( 'C', row, dossier.borrower_1_name ) )
        sheet.render( Cell( 'D', row, dossier.borrower_2_name ) )
        aanvraag = dossier.aanvraag
        sheet.render( Cell( 'E', row, aanvraag.aanvraagdatum) )
        sheet.render( Cell( 'L', row, dossier.beslissing_nieuw.quotiteit ) )
        gewest = 'Onbekend'
        sheet.render( Cell('K', row, aanvraag.waarborgen ) )
        if gb.type=='nieuw':
            datum = dossier.originele_startdatum
            sheet.render( Cell('F', row, gb.goedgekeurd_bedrag ) )
        elif gb.type=='wijziging':
            datum = gb.wijziging.datum_wijziging
            sheet.render( Cell('F', row, gb.goedgekeurd_bedrag - gb.wijziging.huidig_bedrag ) )
        else:
            raise Exception('onbekend type goedgekeurd bedrag')
        sheet.render( Cell('J', row, datum ) )
        sheet.render( Cell('H', row, gb.goedgekeurd_terugbetaling_interval ) )
        sheet.render( Cell('I', row, gb.looptijd ) )
        sheet.render( Cell('G', row, D(gb.goedgekeurde_jaarlijkse_kosten or 0) ) )
        present_value, future_value = present_en_future_value_van_bedrag( gb, 
                                                                          datum, 
                                                                          datum, 
                                                                          value_options.present_value_rate, 
                                                                          value_options.future_value_rate )
        sheet.render( Cell('M', row, present_value ) )
        sheet.render( Cell('N', row, future_value ) )            
        for aanvrager in dossier.get_roles_at(dossier.originele_startdatum, 'borrower'):
            postcode = Postcodes.get_by( postcode = aanvrager.postcode )
            if postcode:
                gewest = postcode.gewest
            continue
        sheet.render(Cell('O', row, gewest))
        broker = dossier.get_broker_at(options.thru_document_date)
        if broker is not None:
            if broker.broker_relation is not None:
                sheet.render( Cell( 'P', row, broker.broker_relation.from_rechtspersoon.name ) )
                sheet.render( Cell( 'Q', row, broker.broker_relation.name ) )
            if broker.broker_agent is not None:
                sheet.render( Cell( 'R', row, broker.broker_agent.name ) )

        sheet.render(Cell('S', row, dossier.get_functional_setting_description_at(datum, 'state_guarantee') or ''))
        sheet.render(Cell('T', row, dossier.get_applied_feature_value_at(datum, 'state_guarantee', 0)))
        for goed_aanvraag in aanvraag.gehypothekeerd_goed:
            te_hypothekeren_goed = goed_aanvraag.te_hypothekeren_goed
            sheet.render(Cell('U', row, u'{0.postcode} {0.gemeente}'.format(te_hypothekeren_goed)))
            sheet.render(Cell('V', row, te_hypothekeren_goed.straat))
            sheet.render(Cell('W', row, te_hypothekeren_goed.venale_verkoopwaarde))
            break
        sheet.render(Cell('X', row, aanvraag.kosten_verzekering or 0))
        sheet.render(Cell('Y', row, aanvraag.aankoopprijs or 0))
        sheet.render(Cell('Z', row, aanvraag.kosten_bouwwerken or 0))
        sheet.render(Cell('AA', row, aanvraag.saldo_lopend_krediet or 0))

    def fill_sheet( self, sheet, offset, options ):
        startdatum = options.from_document_date
        einddatum = options.thru_document_date
        
        value_options = ValueOptions()
        yield action_steps.ChangeObject( value_options )
        
        row = offset
        row += 1
        sheet.render(Cell('A', row, 'Type'))
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
        sheet.render(Cell('S', row, 'Type staatswaarborg'))
        sheet.render(Cell('T', row, 'Bedrag staatswaarborg'))
        sheet.render(Cell('U', row, 'Stad pand'))
        sheet.render(Cell('V', row, 'Straat pand'))
        sheet.render(Cell('W', row, 'Venale verkoopwaarde'))
        sheet.render(Cell('X', row, 'Verzekeringskosten'))
        sheet.render(Cell('Y', row, 'Aankoopprijs'))
        sheet.render(Cell('Z', row, 'Bestek bouwwerken'))
        sheet.render(Cell('AA', row, 'Saldo over te nemen kredieten'))
        
        row += 1
                    
        for akte in Akte.query.filter( sql.and_( Akte.state == 'booked',
                                                 Akte.datum_verlijden >= startdatum,
                                                 Akte.datum_verlijden <= einddatum ) ).all():
             beslissing = akte.beslissing
             for goedgekeurd_bedrag in GoedgekeurdBedrag.query.filter( sql.and_( GoedgekeurdBedrag.type == 'nieuw',
                                                                                 GoedgekeurdBedrag.state.in_(['processed', 'ticked']),
                                                                                 GoedgekeurdBedrag.beslissing == beslissing ) ).all():
                 row += 1
                 sheet.render( Cell( 'A', row, goedgekeurd_bedrag.type ) )
                 self.add_goedgekeurd_bedrag( sheet, row, value_options, options, goedgekeurd_bedrag )
                 yield action_steps.UpdateProgress()
             
        for wijziging in Wijziging.query.filter( sql.and_( Wijziging.state.in_( ['processed','ticked'] ),
                                                           Wijziging.datum_wijziging >= startdatum,
                                                           Wijziging.datum_wijziging <= einddatum ) ).all():
            for goedgekeurd_bedrag in GoedgekeurdBedrag.query.filter( sql.and_( GoedgekeurdBedrag.type == 'wijziging',
                                                                                GoedgekeurdBedrag.wijziging == wijziging ) ).all():
                row += 1
                sheet.render( Cell( 'A', row, goedgekeurd_bedrag.type ) )
                self.add_goedgekeurd_bedrag( sheet, row, value_options, options, goedgekeurd_bedrag )
                yield action_steps.UpdateProgress()
