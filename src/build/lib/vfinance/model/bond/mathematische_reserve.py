import logging
import datetime

from integration.spreadsheet.xls import XlsSpreadsheet
from integration.spreadsheet.base import Cell, Sum, Range, Mul

from camelot.admin.action import Action
from camelot.core.conf import settings
from camelot.core.sql import metadata
from camelot.view import action_steps

import product_business

logger = logging.getLogger('vfinance.model.bond.mathematische_reserve')

product_aantal_query = """
select 1 as periodiciteit, bond_product.id, bond_product.code, count(bond_bond.id) as number_of_bonds, bond_product.rente, bond_product.coupon_datum, bond_product_beschrijving.name, bond_product.start_datum, bond_product_beschrijving.looptijd_maanden, bond_product_beschrijving.coupure from bond_bond 
  join bond_product on (bond_bond.product=bond_product.id) 
  join bond_product_beschrijving on (bond_product.beschrijving=bond_product_beschrijving.id) 
group by bond_product.id, bond_product.code, bond_product.rente, bond_product.coupon_datum, bond_product_beschrijving.name, bond_product.start_datum, bond_product_beschrijving.looptijd_maanden, bond_product_beschrijving.coupure
"""

class MathematischeReserveOptions( object ):
  
  def __init__( self ):
    self.datum = datetime.date.today()
    self.product = None
    
class MathematischeReserve( Action ):
  """Generate a sheet containing the bond mathematische_reserve
  """
  
  verbose_name = 'Mathematische Reserve'
  
  def model_run( self, model_context ):
    
    options = MathematischeReserveOptions()
    yield action_steps.ChangeObject( options )
    
    criteria = ''
    date = options.date
    if options.product:
      criteria = ' and bond_bond.product=%i'%(options.product.id)
    account_bonds = settings.get( 'BOND_ACCOUNT_BONDS', product_business.DEFAULT_BOND_ACCOUNT_BONDS )

    res = metadata.bind.execute( product_aantal_query + criteria )
    
    sheet = XlsSpreadsheet()
    sheet.render(Cell('A', 1, 'Mathematische reserve'))
    sheet.render(Cell('A', 2, 'Datum'))
    sheet.render(Cell('B', 2, date))

    offset = 4
    sheet.render(Cell('A', offset, 'Product code'))
    sheet.render(Cell('B', offset, 'Aanvangsdatum'))
    sheet.render(Cell('C', offset, 'Product'))
    sheet.render(Cell('D', offset, 'Eind datum'))
    sheet.render(Cell('E', offset, 'Periodiciteit'))
    sheet.render(Cell('F', offset, 'Eerste coupon'))
    sheet.render(Cell('G', offset, 'Rente'))
    sheet.render(Cell('H', offset, 'Coupure'))
    sheet.render(Cell('I', offset, 'Coupon'))
    sheet.render(Cell('J', offset, 'Dagrente'))
    sheet.render(Cell('K', offset, 'Laatste coupon datum'))
    sheet.render(Cell('L', offset, 'Verlopen dagen'))
    sheet.render(Cell('M', offset, 'Aantal'))
    sheet.render(Cell('N', offset, 'Belegd bedrag'))
    sheet.render(Cell('O', offset, 'Mathematische reserve'))
    offset += 1
        
    float_kwargs = {'format':'#,##0.00'}
    first_belegd_bedrag, last_belegd_bedrag, first_matres, last_matres = None, None, None, None
    for i,row in enumerate( res ):
      product = object()
      object.__dict__.update( row )
      sheet.render(Cell('A', i+offset, product_business.bond_nummer(account_bonds, product.code, 0) ))
      sheet.render(Cell('B', i+offset, product.coupon_datum ))
      sheet.render(Cell('C', i+offset, product_business.product_name(product.name, product.start_datum, product.rente) ))
      sheet.render(Cell('D', i+offset, product_business.eind_datum(product.coupon_datum, product.looptijd_maanden) ))
      sheet.render(Cell('E', i+offset, product_business.periodiciteit() ))
      sheet.render(Cell('F', i+offset, product_business.eerste_coupon_datum(product.coupon_datum, product_business.periodiciteit() ) ))
      sheet.render(Cell('G', i+offset, product.rente ))
      product_coupure = Cell('H', i+offset, product.coupure, **float_kwargs )
      sheet.render(product_coupure)
      sheet.render(Cell('I', i+offset, product_business.coupon(product.coupure, product.rente), **float_kwargs))
      product_dagrente = Cell('J', i+offset, product_business.dagrente(product.coupure, product.rente), **float_kwargs)
      sheet.render(product_dagrente)
      sheet.render(Cell('K', i+offset, product_business.laatste_coupon_datum(product.coupon_datum, product.looptijd_maanden, date)))
      product_verlopen_dagen = Cell('L', i+offset, product_business.verlopen_dagen(product.coupon_datum, product.looptijd_maanden, date))
      sheet.render(product_verlopen_dagen)
      product_aantal = Cell('M', i+offset, int(product.number_of_bonds))
      sheet.render(product_aantal)
      belegd_bedrag = Cell('N', i+offset, Mul(product_coupure, product_aantal), **float_kwargs)
      sheet.render(belegd_bedrag)
      matres = Cell('O', i+offset, Mul(product_dagrente, product_verlopen_dagen, product_aantal), **float_kwargs)
      sheet.render(matres)
      if i==0:
        first_belegd_bedrag = belegd_bedrag
        first_matres = matres
      last_belegd_bedrag = belegd_bedrag
      last_matres = matres
      
    sheet.render(Cell('N', offset-2, Sum(Range(first_belegd_bedrag, last_belegd_bedrag)), **float_kwargs))
    sheet.render(Cell('O', offset-2, Sum(Range(first_matres, last_matres)), **float_kwargs))
                 
    sheet.generate_xlsx()
