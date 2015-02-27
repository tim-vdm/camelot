from datetime import date
from decorator import decorator
import calendar
import os
import csv
import logging
from cStringIO import StringIO

from camelot.core.resources import resource_string

logger = logging.getLogger('kapcontract.contract_business')

@decorator
def rounding_decorator(oldfun, *args, **kwargs):
  old_result = None
  try:
    old_result = oldfun(*args, **kwargs)
    return round(old_result, 2)
  except TypeError,e:
    logger.error('Type error %s %s %s'%(str(oldfun), str(type(old_result)), str(old_result)), exc_info=True)
    logger.error(str(args)+str(kwargs))
    raise e

class LazyTable(dict):
  
  def __init__(self, name):
    self._name = name
    super(LazyTable, self).__init__()

  def __getitem__(self, requested_key):
    if not len(self):
      table_file = StringIO( resource_string( 'vfinance', os.path.join( 'art', 'tables', self._name ) ) )
      afkoopfactor_file = csv.DictReader( table_file )
      for line in afkoopfactor_file:
        d = lambda x:float(x.replace('.','').replace(',','.'))
        aantal_maanden = int(line['Maand'])
        for key in line.keys():
          if key!='Maand' and line[key]!='':
            super(LazyTable, self).__setitem__((aantal_maanden,int(key)), d(line[key]))
    return super(LazyTable, self).__getitem__(requested_key)

afkoopwaardes = LazyTable('afkoopwaardes.csv')
mathematische_reserves = LazyTable('mathematische_reserves.csv')
reductiewaardes = LazyTable('reductiewaardes.csv')
theoretische_waardes = LazyTable('theoretische_waardes.csv')

ACCOUNT_PREFIX = '14213' # used to be 1743

def business_to_tiny(b_function):
  """Transform a business function to a tiny function"""
  
  from inspect import getargspec
  args = getargspec(b_function)[0]
  
  def t_function(self, cr, uid, ids, *a, **ka):
    result = {}
    for record in self.read(cr, uid, ids, args):
      result[record['id']] = b_function( *[record[arg] for arg in args] )
    return result

  return t_function

@rounding_decorator
def afkoop_waarde(state, looptijd, aantal_maanden, kapitaal, aantal_maanden_reductie):
  if 'reduced' in state and ((aantal_maanden + aantal_maanden_reductie)>=looptijd*12):
    return reductie_waarde(looptijd, aantal_maanden, kapitaal)
  key = (aantal_maanden, looptijd)
  if aantal_maanden==0:
    return 0  
  if aantal_maanden >= looptijd*12:
    return kapitaal
  try:
    return kapitaal * afkoopwaardes[key]/1000
  except KeyError:
    logger.error('geen afkoopwaardes voor %s'%str(key))
    logger.error('mogelijkheden zijn : %s'%str(afkoopwaardes.keys()))
  return None

def aantal_verlopen_maanden(today, status, afkoop_datum, reductie_datum, start_datum, looptijd):
  if status in ['draft', 'complete', 'approved','canceled']:
    return 0
  eind_datum = today
  if reductie_datum and reductie_datum<today:
    eind_datum = reductie_datum
  elif afkoop_datum and afkoop_datum<today:
    eind_datum = afkoop_datum
  return min(looptijd * 12, months_between_dates(start_datum, eind_datum))

@rounding_decorator
def theoretisch_saldo(today, status, afkoop_datum, reductie_datum, start_datum, looptijd, betalings_interval, premie):
  virtual_state = state_at(today, status, afkoop_datum, reductie_datum, start_datum)
  if 'buyout' in virtual_state:
    return 0.0
  aantal_maanden = aantal_verlopen_maanden(today, virtual_state, afkoop_datum, reductie_datum, start_datum, looptijd)
  ab = aantal_betalingen(virtual_state, aantal_maanden, betalings_interval, looptijd)  
  if ('reduced' in virtual_state) and ab<betalings_interval:
    return 0.0
  return ab * premie

def state_at(datum, current_state, afkoop_datum, reductie_datum, start_datum):
  if current_state in ['draft', 'complete', 'approved','canceled']:
    return current_state
  if afkoop_datum and afkoop_datum<=datum and 'buyout' in current_state:
    return 'buyout'
  if (reductie_datum and reductie_datum<=datum) and 'reduced' in current_state:
    return 'reduced'
  return 'processed'

def aantal_maanden_reductie(today, afkoop_datum, reductie_datum, betaal_datum):
  if today > betaal_datum:
    today = betaal_datum
  if afkoop_datum and afkoop_datum<today:
    today = afkoop_datum
  if reductie_datum and reductie_datum<today:
    return months_between_dates(reductie_datum, today)
  return 0
  
@rounding_decorator
def mathematische_reserve(today, status, afkoop_datum, reductie_datum, start_datum, betaal_datum, looptijd, kapitaal):
  am = aantal_verlopen_maanden(today, status, afkoop_datum, reductie_datum, start_datum, looptijd)
  if afkoop_datum and afkoop_datum<today:
    return 0
  if reductie_datum and reductie_datum<today:
    if today > betaal_datum:
      return reductie_waarde(looptijd, am, kapitaal)
    tw = theoretische_waarde(looptijd, am, kapitaal)
    amr = aantal_maanden_reductie(today, afkoop_datum, reductie_datum, betaal_datum)
    return tw + tw*amr/300
  key = (am, looptijd)
  if am > looptijd*12:
    return kapitaal
  if am==0:
    return 0
  try:
    return kapitaal * mathematische_reserves[key]/1000
  except KeyError:
    pass
  return 0

@rounding_decorator
def reductie_waarde(looptijd, aantal_maanden, kapitaal):
  key = (aantal_maanden, looptijd)
  if aantal_maanden > looptijd*12:
    return kapitaal
  if aantal_maanden==0:
    return 0  
  try:
    return kapitaal * reductiewaardes[key]/1000
  except KeyError:
    pass
  return None

@rounding_decorator
def theoretische_waarde(looptijd, aantal_maanden, kapitaal):
  key = (aantal_maanden, looptijd)
  if aantal_maanden > looptijd*12:
    return kapitaal
  if aantal_maanden==0:
    return 0
  try:
    return kapitaal * theoretische_waardes[key]/1000
  except KeyError:
    pass
  return None

attrs = lambda object, *a: [ getattr(object, attr) for attr in a ] # extract attributes

def months_between_dates(start_date, end_date):
  (sy, sm, sd), (ey, em, ed) = [ attrs(d, 'year', 'month', 'day') for d in (start_date, end_date) ]
  correction = 0.0
  if start_date.day > end_date.day: # still not correct but anyway
    sdpm, edpm = [ calendar.monthrange(y, m)[1] for y, m in ((sy,sm), (ey,em)) ] # days per month for start and end date
    correction = float(ed) / edpm - float(sd) / sdpm
  return int((ey - sy) * 12 + em - sm - correction)

def betaaldatum(start_contract, looptijd_contract):
  year = start_contract.year + looptijd_contract
  month = start_contract.month
  day = min( calendar.monthrange(year, month)[1], start_contract.day )
  return date(day=day, year=year, month=month)

def vervaldag_in_periode(start_periode, eind_periode, start_contract, looptijd_contract, betalings_interval):
  if start_periode>=betaaldatum(start_contract, looptijd_contract):
    return False
  tussen_2_betalingen = 12/betalings_interval
  for i in range(looptijd_contract * betalings_interval):
    dyear, month = divmod(start_contract.month+i*tussen_2_betalingen-1,12)
    year = start_contract.year + dyear
    month = month + 1
    day = min( calendar.monthrange(year, month)[1], start_contract.day )
    vervaldag = date(day=day, year=year, month=month)
    if vervaldag>=start_periode and vervaldag<eind_periode:
      return True
  return False

def contract_mededeling(nummer):
  mod97 = nummer % 97
  if mod97==0:
    mod97 = 97
  return '000-%s-%02i'%(nummer, mod97)

def aantal_betalingen(state, aantal_maanden, betalings_interval, looptijd):
  """De startdatum zelf is reeds een betaling, dus na 1 maand zijn er 2 betalingen,
  bij maandelijkse betaling"""
  interval = 12 / betalings_interval # freq -> interval
  if state=='processed' and (aantal_maanden<looptijd*12):
    return aantal_maanden/interval + 1
  else:
    return aantal_maanden/interval

@rounding_decorator
def ontvangen(aantal_betalingen, premie):
  return aantal_betalingen * premie

@rounding_decorator
def afkoop_intrest(afkoop_waarde, ontvangen):
  if afkoop_waarde==0:
    return 0
  return afkoop_waarde - ontvangen

flip_date = date(year=2004, month=1, day=1)

gt = lambda value: lambda f: lambda *a, **kw: max(value, f(*a, **kw))

@gt(0)
@rounding_decorator
def afkoop_roerende_voorheffing(afkoop_intrest, afkoop_datum):
  if afkoop_intrest==0:
    return 0
  if afkoop_datum>flip_date:
    return 0.15 * afkoop_intrest
  return 0.25 * afkoop_intrest

@rounding_decorator
def afkoop_te_betalen(afkoop_waarde, afkoop_roerende_voorheffing):
  return afkoop_waarde - afkoop_roerende_voorheffing

@rounding_decorator
def kapitaal_betaal_datum(state, looptijd, aantal_maanden, kapitaal):
  if 'buyout' in state:
    return 0
  if 'reduced' in state:
    return reductie_waarde(looptijd, aantal_maanden, kapitaal)
  return kapitaal
