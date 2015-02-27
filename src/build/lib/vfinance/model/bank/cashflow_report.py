from datetime import date
import logging
import calendar
import datetime
import itertools

from sqlalchemy import sql

from camelot.admin.object_admin import ObjectAdmin
from camelot.admin.action import Action
from camelot.core.exception import UserException
from camelot.core.sql import metadata
from camelot.view.action_steps import ChangeObject, UpdateProgress, OpenString
from camelot.view.controls import delegates

from integration.spreadsheet.xlsx import XlsxSpreadsheet

from vfinance.model.bond.mathematische_reserve import product_aantal_query
from vfinance.model.bond.product_business import eind_datum, coupon, coupon_data
from vfinance.model.kapcontract.contract import Contract
from vfinance.model.kapbon.product import Kapbon

logger = logging.getLogger('vfinance.model.bank.cashflow_report')
  
class buckets(dict):
    """container in which we put cash flow events, ordered a certain key"""
    
    def __init__(self, key_generator=lambda event:(event.date.year, event.date.month)):
        self.key_generator = key_generator
        dict.__init__(self)
      
    def append(self, event):
        self.setdefault(self.key_generator(event), []).append(event)
      
    def extend(self, events):
        for event in events:
            self.append(event)
        
class cash_event(object):
  def __init__(self, date, change, annotations):
    self.date = date
    self.change = change
    self.annotations = annotations
  def __str__(self):
    return '%s\t%.2f\t%s'%(self.date,self.change, '\t'.join([str(v) for v in self.annotations.values()] ) )

def cashflow( start_date ):
  
  before_start_date = start_date - datetime.timedelta(days=1)
        
  def bond_events():
    for i,product in enumerate( metadata.bind.execute( product_aantal_query ) ):
      product_eind_datum = eind_datum(product.coupon_datum, product.looptijd_maanden)
      belegd_bedrag = product.coupure * product.number_of_bonds
      product_coupon = coupon(product.coupure, product.rente) * product.number_of_bonds 
      #
      # De terugbetaling vh kapitaal
      #
      if product_eind_datum>=start_date:
        yield cash_event(product_eind_datum, -1*belegd_bedrag, annotations={'bron':'bond_kapitaal', 'nummer':product.code})
      #
      # De periodieke coupons
      #
      for coupon_date in coupon_data(product.coupon_datum, product.periodiciteit, product.looptijd_maanden):
        if coupon_date>=start_date:
          yield cash_event(coupon_date, -1*product_coupon, annotations={'bron':'bond_rente', 'nummer':product.code})
        
  def kapbon_events():
    query = Kapbon.query.filter( sql.and_( Kapbon.state != 'draft',
                                           sql.or_( Kapbon.betaal_datum == None,
                                                    Kapbon.betaal_datum >= start_date ),
                                            ) )
    for kapbon in query.yield_per(100):
      if kapbon.datum_start > start_date:
          continue
      if kapbon.datum_einde >= start_date:
        logger.debug('calculating cash flow for kapbon : %s'%kapbon.nummer)
        yield cash_event( kapbon.datum_einde, -1*kapbon.coupure, {'bron':'kapbon_kapitaal', 'nummer':kapbon.nummer})
        yield cash_event( kapbon.datum_einde, -1*(kapbon.te_betalen_op_vervaldag-kapbon.coupure), {'bron':'kapbon_rente', 'nummer':kapbon.nummer})
      else:
        logger.debug('reeds vervallen, nog niet betaalde kapbon : %s'%kapbon.nummer)
        yield cash_event( before_start_date, -1*kapbon.coupure, {'bron':'kapbon_kapitaal', 'nummer':kapbon.nummer})
        yield cash_event( before_start_date, -1*(kapbon.te_betalen_op_vervaldag-kapbon.coupure), {'bron':'kapbon_rente', 'nummer':kapbon.nummer})        
            
  def kapcontracten_events():
    
    def kapcontract_events(contract):
      """Deze query moet in principe overeenkomen met de query in kapcontract/overzicht_vervallen_contracten.py
      
      merk op dat sommige te betalen rente events een positieve waarde kunnen hebben, di omdat er contracten
      zijn waarbij de reductiewaarde kleiner is dan het gestort kapitaal.
      """
      # neem alle contracten die nog nt afgekocht zijn op start_date
      if (contract.state in ['processed', 'reduced']) or ( contract.afkoop_datum and contract.afkoop_datum >= start_date):
        if 'reduced' in contract.state and not contract.reductie_datum:
            raise UserException('Contract {0.nummer} heeft geen reductie datum'.format(contract),
                                resolution='Voer de reductie datum in in TinyERP',
                                detail='{0.nummer} : status {0.state}, afgekocht op {0.afkoop_datum}'.format(contract))
        # diegenen die zullen moeten worden betaald na start_date
        if contract.betaal_datum >= start_date:
          if 'reduced' in contract.state and (contract.reductie_datum < start_date):
            # men moet minstens een jaar ah betalen zijn vooraleer in reductie te gaan, anders vervalt de waarde vh ontvangen kapitaal
            if contract.aantal_betalingen >= contract.betalings_interval:
              yield cash_event( contract.betaal_datum, -1*contract.ontvangen, {'bron':'kapcontract_kapitaal', 'nummer':contract.nummer})
              yield cash_event( contract.betaal_datum, -1*(contract.reductie_waarde-contract.ontvangen), {'bron':'kapcontract_rente', 'nummer':contract.nummer})
          else:
            start = contract.start_datum
            aantal_betalingen = contract.looptijd*contract.betalings_interval
            #de eerste betaling valt op de start datum
            if start >= start_date:
              yield cash_event(start, contract.premie, {'bron':'kapcontract', 'nummer':contract.nummer})
            #nu de overige aantal_betalingen - 1
            for i in range(1,aantal_betalingen):
              dyear, month = divmod(start.month+i*(12/contract.betalings_interval)-1,12)
              year = start.year + dyear
              month = month + 1
              first_day, max_day = calendar.monthrange(year, month)
              vervaldag_datum = date(year, month, min(start.day,max_day))
              if vervaldag_datum >= start_date:
                yield cash_event(vervaldag_datum, contract.premie, {'bron':'kapcontract', 'nummer':contract.nummer})
            ontvangen_op_betaal_datum = aantal_betalingen * contract.premie
            yield cash_event( contract.betaal_datum, -1*ontvangen_op_betaal_datum, {'bron':'kapcontract_kapitaal', 'nummer':contract.nummer})
            yield cash_event( contract.betaal_datum, -1*(contract.kapitaal-ontvangen_op_betaal_datum), {'bron':'kapcontract_rente', 'nummer':contract.nummer})
        # diegene die reeds betaald hadden moeten zijn, maar nog niet afgekocht
        else:
          if 'reduced' in contract.state and (contract.reductie_datum < start_date):
            # men moet minstens een jaar ah betalen zijn vooraleer in reductie te gaan, anders vervalt de waarde vh ontvangen kapitaal
            if contract.aantal_betalingen >= contract.betalings_interval:            
              yield cash_event(before_start_date, -1*contract.ontvangen, {'bron':'kapcontract_kapitaal', 'nummer':contract.nummer})
              yield cash_event(before_start_date, -1*(contract.reductie_waarde-contract.ontvangen), {'bron':'kapcontract_rente', 'nummer':contract.nummer})          
          else:
            aantal_betalingen = contract.looptijd * contract.betalings_interval
            ontvangen_op_betaal_datum = aantal_betalingen * contract.premie
            yield cash_event(before_start_date, -1*ontvangen_op_betaal_datum, {'bron':'kapcontract_kapitaal', 'nummer':contract.nummer})
            yield cash_event(before_start_date, -1*(contract.kapitaal-ontvangen_op_betaal_datum), {'bron':'kapcontract_rente', 'nummer':contract.nummer})
    
    for contract in Contract.query.yield_per( 100 ):
      logger.debug('calculating cash flow for contract %s'%contract.nummer)
      for e in kapcontract_events(contract):
        yield e
       
  for event in itertools.chain( bond_events(), 
                                kapbon_events(), 
                                kapcontracten_events() ):
    yield event
  
class CashFlowReport( Action ):
  
    verbose_name = 'Cash Flow Report'
  
    class Options(object):
        
        def __init__(self):
            self.from_document_date = datetime.date.today()
            
        class Admin(ObjectAdmin):
            form_display = ['from_document_date']
            field_attributes = {'from_document_date':{'delegate':delegates.DateDelegate, 
                                                      'nullable':False,
                                                      'editable':True},}
            
    def model_run( self, model_context ):
        options = self.Options()
        yield ChangeObject( options )
        sheet = XlsxSpreadsheet()
        for step in self.fill_sheet( sheet, options ):
            yield step
        yield OpenString( sheet.generate_xlsx(), suffix='.xlsx')
        
    def fill_sheet( self, sheet, options ):
        from integration.spreadsheet.base import Cell, Sum, Range, Add
        from string import uppercase
        WORKSHEET = 'Cash flow'
        datum = options.from_document_date
        sheet.render( Cell('A', 1, 'Cashflow report', worksheet=WORKSHEET ) )
        sheet.render( Cell('A', 2, datum, worksheet=WORKSHEET ) )
        # Fill cash flow sheet
        
        date_buckets = buckets()
        nummer_buckets = buckets(lambda event:event.annotations['nummer'])
        for i, event in enumerate( cashflow( datum ) ):
            date_buckets.append( event )
            nummer_buckets.append( event )
            if i % 10 == 0:
                yield UpdateProgress( text = ', '.join( list( unicode(v) for v in event.annotations.values() ) ) )

        yield UpdateProgress( text = 'Sort Cashflow' )
        periods = date_buckets.keys()
        periods.sort()
        cumulatieve_cashflow = 0
        sheet.render( Cell('A', 3, 'Periode', worksheet=WORKSHEET) )
        sheet.render( Cell('B', 3, 'Hypotheken Kapitaal', worksheet=WORKSHEET) )
        sheet.render( Cell('C', 3, 'Hypotheken Rente', worksheet=WORKSHEET) )
        sheet.render( Cell('D', 3, 'Hypotheken Uit', worksheet=WORKSHEET) )
        sheet.render( Cell('E', 3, 'Obligaties Kapitaal', worksheet=WORKSHEET) )
        sheet.render( Cell('F', 3, 'Obligaties Rente', worksheet=WORKSHEET) )    
        sheet.render( Cell('G', 3, 'Contracten In', worksheet=WORKSHEET) )
        sheet.render( Cell('H', 3, 'Contracten Kapitaal', worksheet=WORKSHEET) )
        sheet.render( Cell('I', 3, 'Contracten Rente', worksheet=WORKSHEET) )
        sheet.render( Cell('J', 3, 'Kapbonnen In', worksheet=WORKSHEET) )
        sheet.render( Cell('K', 3, 'Kapbonnen Kapitaal', worksheet=WORKSHEET) )
        sheet.render( Cell('L', 3, 'Kapbonnen Rente', worksheet=WORKSHEET) )
        sheet.render( Cell('M', 3, 'Totaal', worksheet=WORKSHEET) )
        sheet.render( Cell('N', 3, 'Cumulatief Totaal', worksheet=WORKSHEET) )
        j = 0
        cell_kwargs = {'format':'#,##0.00', 'worksheet':WORKSHEET}
        yield UpdateProgress( text = 'Fill spreadsheet' )
        for j,p in enumerate(periods):
          v = date_buckets[p]
          name                    = Cell('A', 4+j, '%i/%i'%(p[1], p[0]), worksheet=WORKSHEET)
          hypotheek_kapitaal      = Cell('B', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='hypotheek_kapitaal')]), **cell_kwargs )
          hypotheek_rente         = Cell('C', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='hypotheek_rente')]), **cell_kwargs )
          hypotheek               = Cell('D', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='hypotheek')]), **cell_kwargs )
          oblig_kapitaal          = Cell('E', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='bond_kapitaal')]), **cell_kwargs )
          oblig_rente             = Cell('F', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='bond_rente')]), **cell_kwargs )      
          kapcontract             = Cell('G', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='kapcontract') ]), **cell_kwargs )
          kapcontract_kapitaal    = Cell('H', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='kapcontract_kapitaal') ]), **cell_kwargs )
          kapcontract_rente       = Cell('I', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='kapcontract_rente') ]), **cell_kwargs )
          kapbon                  = Cell('J', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='kapbon') ]), **cell_kwargs )
          kapbon_kapitaal         = Cell('K', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='kapbon_kapitaal') ]), **cell_kwargs )
          kapbon_rente            = Cell('L', 4+j, sum( [e.change for e in v if (e.annotations['bron']=='kapbon_rente') ]), **cell_kwargs )
          totaal_cashflow         = Cell('M', 4+j, Sum(Range(hypotheek_kapitaal, kapbon_rente)), **cell_kwargs )
          cumulatieve_cashflow    = Cell('N', 4+j, Add(totaal_cashflow, cumulatieve_cashflow), **cell_kwargs )
          sheet.render(*[name, hypotheek_kapitaal, hypotheek_rente, hypotheek, kapcontract, kapcontract_kapitaal, kapcontract_rente,
                         kapbon, kapbon_kapitaal, kapbon_rente, totaal_cashflow, cumulatieve_cashflow, oblig_kapitaal, oblig_rente])
        for i in range(uppercase.index('B'), uppercase.index('M') + 1):
          sheet.render( Cell(uppercase[i], 1, 
                             Sum(Range(Cell(uppercase[i],4, worksheet=WORKSHEET), Cell(uppercase[i], j+4, worksheet=WORKSHEET))), 
                             **cell_kwargs ) )
        # Fill contracten sheet
        CONTRACTEN_WORKSHEET='Contracten'
        sheet.render( Cell('B', 3, 'Contracten In', worksheet=CONTRACTEN_WORKSHEET) )
        sheet.render( Cell('C', 3, 'Contracten Kapitaal', worksheet=CONTRACTEN_WORKSHEET) )
        sheet.render( Cell('D', 3, 'Contracten Rente', worksheet=CONTRACTEN_WORKSHEET) )
        HYPOTHEKEN_WORKSHEET='Hypotheken'
        sheet.render( Cell('B', 3, 'Hypotheken Kapitaal', worksheet=HYPOTHEKEN_WORKSHEET) )
        sheet.render( Cell('C', 3, 'Hypotheken Rente', worksheet=HYPOTHEKEN_WORKSHEET) )
        sheet.render( Cell('D', 3, 'Hypotheken Uit', worksheet=HYPOTHEKEN_WORKSHEET) )    
        BONNEN_WORKSHEET='Bonnen'
        sheet.render( Cell('B', 3, 'Bonnen In', worksheet=BONNEN_WORKSHEET) )
        sheet.render( Cell('C', 3, 'Bonnen Kapitaal', worksheet=BONNEN_WORKSHEET) )
        sheet.render( Cell('D', 3, 'Bonnen Rente', worksheet=BONNEN_WORKSHEET) )    
        OBLIGATIE_WORKSHEET='Obligaties'
        sheet.render( Cell('B', 3, 'Obligaties Kapitaal', worksheet=OBLIGATIE_WORKSHEET) )
        sheet.render( Cell('C', 3, 'Obligaties Rente', worksheet=OBLIGATIE_WORKSHEET) )
        sheet.render( Cell('D', 3, 'Obligaties In', worksheet=OBLIGATIE_WORKSHEET) )     
        nummers = nummer_buckets.keys()
        nummers.sort()
        contracten_count = 0
        hypotheken_count = 0
        bonnen_count = 0
        obligaties_count = 0
        for nummer in nummers:
          bucket = nummer_buckets[nummer]
          contracten_events = [e for e in bucket if 'kapcontract' in e.annotations['bron']]
          if contracten_events:
            sheet.render( Cell('A', 4+contracten_count, nummer, worksheet=CONTRACTEN_WORKSHEET ) )
            sheet.render( Cell('B', 4+contracten_count, sum( [e.change for e in contracten_events if (e.annotations['bron']=='kapcontract') ]), worksheet=CONTRACTEN_WORKSHEET ) )
            sheet.render( Cell('C', 4+contracten_count, sum( [e.change for e in contracten_events if (e.annotations['bron']=='kapcontract_kapitaal') ]), worksheet=CONTRACTEN_WORKSHEET ) )
            sheet.render( Cell('D', 4+contracten_count, sum( [e.change for e in contracten_events if (e.annotations['bron']=='kapcontract_rente') ]), worksheet=CONTRACTEN_WORKSHEET ) )
            contracten_count += 1
          hypotheken_events = [e for e in bucket if 'hypotheek' in e.annotations['bron']]
          if hypotheken_events:
            sheet.render( Cell('A', 4+hypotheken_count, nummer, worksheet=HYPOTHEKEN_WORKSHEET ) )
            sheet.render( Cell('B', 4+hypotheken_count, sum( [e.change for e in hypotheken_events if (e.annotations['bron']=='hypotheek_kapitaal') ]), worksheet=HYPOTHEKEN_WORKSHEET ) )
            sheet.render( Cell('C', 4+hypotheken_count, sum( [e.change for e in hypotheken_events if (e.annotations['bron']=='hypotheek_rente') ]), worksheet=HYPOTHEKEN_WORKSHEET ) )
            sheet.render( Cell('D', 4+hypotheken_count, sum( [e.change for e in hypotheken_events if (e.annotations['bron']=='hypotheek') ]), worksheet=HYPOTHEKEN_WORKSHEET ) )
            hypotheken_count += 1
          bonnen_events = [e for e in bucket if 'kapbon' in e.annotations['bron']]
          if bonnen_events:
            sheet.render( Cell('A', 4+bonnen_count, nummer, worksheet=BONNEN_WORKSHEET ) )
            sheet.render( Cell('B', 4+bonnen_count, sum( [e.change for e in bonnen_events if (e.annotations['bron']=='kapbon') ]), worksheet=BONNEN_WORKSHEET ) )
            sheet.render( Cell('C', 4+bonnen_count, sum( [e.change for e in bonnen_events if (e.annotations['bron']=='kapbon_kapitaal') ]), worksheet=BONNEN_WORKSHEET ) )
            sheet.render( Cell('D', 4+bonnen_count, sum( [e.change for e in bonnen_events if (e.annotations['bron']=='kapbon_rente') ]), worksheet=BONNEN_WORKSHEET ) )
            bonnen_count += 1
          obligatie_events = [e for e in bucket if 'bond' in e.annotations['bron']]
          if obligatie_events:
            sheet.render( Cell('A', 4+obligaties_count, nummer, worksheet=OBLIGATIE_WORKSHEET ) )
            sheet.render( Cell('B', 4+obligaties_count, sum( [e.change for e in obligatie_events if (e.annotations['bron']=='bond_kapitaal') ]), worksheet=OBLIGATIE_WORKSHEET ) )
            sheet.render( Cell('C', 4+obligaties_count, sum( [e.change for e in obligatie_events if (e.annotations['bron']=='bond_rente') ]), worksheet=OBLIGATIE_WORKSHEET ) )
            sheet.render( Cell('D', 4+obligaties_count, 0.0, worksheet=OBLIGATIE_WORKSHEET ) )
            obligaties_count += 1        
        for worksheet,count in zip([CONTRACTEN_WORKSHEET, HYPOTHEKEN_WORKSHEET, BONNEN_WORKSHEET, OBLIGATIE_WORKSHEET],[contracten_count, hypotheken_count, bonnen_count, obligaties_count]):                
          for col in range(1,4):
            sheet.render( Cell(uppercase[col], 1,
                               Sum( Range( Cell(uppercase[col], 3, worksheet=worksheet),
                                           Cell(uppercase[col], 3+count, worksheet=worksheet ) ) ), worksheet=worksheet ) )
