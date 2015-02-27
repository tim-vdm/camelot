import itertools
import logging
from sqlalchemy import sql

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

LOGGER = logging.getLogger('vfinance.model.hypo.report.overzicht_afkopen')
  
from ...bank.report.abstract import AbstractReport

from vfinance.model.hypo.terugbetaling import Terugbetaling
from vfinance.model.hypo.wijziging import Wijziging

class RedemptionReport( AbstractReport ):
    
    name = _('Overzicht afkopen')

    def fill_sheet( self, sheet, offset, options ):
        from integration.spreadsheet.base import Cell
    
        startdatum = options.from_document_date
        einddatum = options.thru_document_date
    
        columns = {'A':'type', 'B':'nummer', 'C':'ontlener_1', 'D':'ontlener_2', 'E':'dossier', 'F':'datum', 'G':'bedrag', 
                   'H':'startdatum', 'I':'looptijd', 'J':'opmerking', 'K':'broker', 'L':'master_broker', 'M':'agent' }
        
        for column, attribute in columns.items():
            sheet.render(Cell(column, offset, attribute.capitalize()))
        offset += 1
        
        terugbetaling_query = Terugbetaling.query.filter( sql.and_( Terugbetaling.state.in_(['processed', 'ticked']),
                                                                    Terugbetaling.datum_terugbetaling >= startdatum,
                                                                    Terugbetaling.datum_terugbetaling <= einddatum,
                                                                    ) ).yield_per( 10 )
        
        wijziging_query = Wijziging.query.filter( sql.and_( Wijziging.state.in_(['processed', 'ticked']),
                                                            Wijziging.datum_wijziging >= startdatum,
                                                            Wijziging.datum_wijziging <= einddatum,
                                                            ) ).yield_per( 10 )
                                                              
        class afkoop(object):
          
            def __init__(self, dossier):
                self.broker = None
                self.master_broker = None
                self.agent = None
                self.ontlener_1 = dossier.borrower_1_name
                self.ontlener_2 = dossier.borrower_2_name
                self.nummer = dossier.full_number
                broker = dossier.get_broker_at(options.thru_document_date)
                if broker is not None:
                    if broker.broker_relation is not None:
                        self.master_broker = broker.broker_relation.from_rechtspersoon.name
                        self.broker = broker.broker_relation.name
                    if broker.broker_agent is not None:
                        self.agent = broker.broker_agent.name
                
            @property
            def looptijd(self):
              return (self.datum - self.startdatum).days/30
            
            @property
            def opmerking(self):
              return {False:'', True:'%s binnen 6 maanden na startdatum'%(self.type.capitalize())}[self.looptijd<=6]
            
        def generate_afkopen_from_terugbetalingen():
          
          class afkoop_from_terugbetaling(afkoop):
            def __init__(self, t):
              super(afkoop_from_terugbetaling,self).__init__(t.dossier)
              self.type = 'terugbetaling'
              self.name = t.dossier.name
              self.dossier = t.dossier.nummer
              self.datum = t.datum_terugbetaling
              self.bedrag = t.openstaand_kapitaal
              self.startdatum = t.dossier.originele_startdatum
                
          for t in terugbetaling_query.all():
              yield afkoop_from_terugbetaling(t)
                
        def generate_afkopen_from_wijzigingen():
          
          class afkoop_from_wijziging(afkoop):
            def __init__(self, w):
              super(afkoop_from_wijziging,self).__init__(w.dossier)
              self.type = 'wijziging'
              self.name = w.dossier.name
              self.dossier = w.dossier.nummer
              self.datum = w.datum_wijziging
              self.bedrag = w.huidig_bedrag-w.nieuw_bedrag
              self.startdatum = w.dossier.originele_startdatum 
                
          for wijziging in wijziging_query.all():
              if wijziging.huidig_bedrag > wijziging.nieuw_bedrag:
                  yield afkoop_from_wijziging(wijziging)
        
        for i, afkoop_data in enumerate( itertools.chain(generate_afkopen_from_terugbetalingen(),generate_afkopen_from_wijzigingen()) ):
            if i % 10 == 0:
                yield UpdateProgress( text = unicode( afkoop_data.dossier ) )
            for column, attribute in columns.items():
                sheet.render(Cell(column, offset+i, getattr(afkoop_data, attribute)))
    