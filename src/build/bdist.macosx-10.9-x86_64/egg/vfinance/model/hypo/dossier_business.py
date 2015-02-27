import datetime

from vfinance.model.bank.financial_functions import round_up
from decimal import Decimal as D

start_euro = datetime.date(year=2002, month=1, day=1)

def korting_op_vervaldag(originele_startdatum, valid_date_start, valid_date_end, rente, type, datum, openstaand_kapitaal):
  """De korting die van toepassing is op een vervaldag uit een dossier met bepaalde originele startdatum
  @param vervaldag: een vervaldag object
  """
  korting = D(0)
  if valid_date_start<=datum and valid_date_end>=datum:
    if type=='per_aflossing':
      korting = round_up( rente*openstaand_kapitaal/D(100) )
    elif type=='per_jaar':
        korting = round_up( rente*openstaand_kapitaal/(12*D(100)) )
    elif type=='pret_jeunes':
      if originele_startdatum<start_euro:
        korting =  D('49.58')
      else:
        korting =  D(50)
    elif type=='mijnwerker':
        korting = D(0)
    else:
      raise Exception('Onbekend korting type')
            
  return korting
