import calendar
import datetime

DEFAULT_BOND_ACCOUNT_BONDS = '1711000'

def bond_nummer(account_bonds, code, serie_nummer):
  return str((int(account_bonds) + int(code))*1000000 + int(serie_nummer))
  
def add_months_to_date(start_date, months):
  year, month = map(sum, zip((start_date.year, 1), divmod(start_date.month + months - 1, 12)))
  weekday, numdays = calendar.monthrange(year, month)
  return datetime.date(year, month, min(numdays, start_date.day))

def roerende_voorheffing():
  return 0.15

def periodiciteit():
  return 1

def product_name(beschrijving_name, start_datum, rente):
  return ' %s, %s (%s)' % (beschrijving_name, start_datum, rente)

def eind_datum(coupon_datum, looptijd_maanden):
  return add_months_to_date(coupon_datum, looptijd_maanden)

def coupon_data(coupon_datum, periodiciteit, looptijd_maanden):
  for i in range(1, (looptijd_maanden*periodiciteit/(12))+1 ):
    yield add_months_to_date(coupon_datum, i*12/periodiciteit)
    
def eerste_coupon_datum(coupon_datum, periodiciteit):
  return add_months_to_date(coupon_datum, 12/periodiciteit)
  
def dagrente(coupure, rente):
  return coupure * rente / (100.0 * 365.0)

def coupon(coupure, rente):
  return coupure * rente / 100.0

def coupon_te_betalen(coupure, rente):
  coupon_bruto = coupon(coupure, rente)
  coupon_netto = coupon_bruto - round(coupon_bruto * roerende_voorheffing(), 2)
  return float('%.2f'%coupon_netto)

def laatste_coupon_datum(coupon_datum, looptijd_maanden, aankoop_datum):
  """Laatste coupon datum voor aankoop datum, als aankoop_datum < coupon_datum, dan
  is het resultaat coupon_datum"""
  product_eind_datum = eind_datum(coupon_datum, looptijd_maanden)
  aankoop_datum = aankoop_datum
  coupon_datum = coupon_datum    
  if aankoop_datum > product_eind_datum:
    return product_eind_datum
  if aankoop_datum > coupon_datum:
    weekday, numdays = calendar.monthrange(aankoop_datum.year, coupon_datum.month)
    coupon_datum_in_aankoop_jaar = datetime.date(aankoop_datum.year,
                                                 month=coupon_datum.month, 
                                                 day=min(numdays, coupon_datum.day))
    if aankoop_datum >= coupon_datum_in_aankoop_jaar:
      laatste_coupon_datum = coupon_datum_in_aankoop_jaar
    else:
      weekday, numdays = calendar.monthrange(aankoop_datum.year-1, coupon_datum.month)
      laatste_coupon_datum = datetime.date(aankoop_datum.year-1, month=coupon_datum.month, day=min(numdays, coupon_datum.day))
  else:
    laatste_coupon_datum = coupon_datum
  return laatste_coupon_datum

def verlopen_dagen(coupon_datum, looptijd_maanden, aankoop_datum):
  """Aantal dagen tussen laatste coupon datum en aankoop_datum, wanneer de aankoop_datum
  samenvalt met een coupon_datum is het aantal verlopen dagen 0, ook wanneer de aankoop_datum
  na de einddatum valt is het aantal verlopen dagen 0"""
  product_eind_datum = eind_datum(coupon_datum, looptijd_maanden)
  if aankoop_datum and coupon_datum:
    if aankoop_datum <= product_eind_datum:
      product_laatste_coupon_datum = laatste_coupon_datum(coupon_datum, looptijd_maanden, aankoop_datum)
      return (aankoop_datum-product_laatste_coupon_datum).days
    else:
      return 0
  return 0

def verlopen_rente(coupure, rente, coupon_datum, looptijd_maanden, aankoop_datum):
  """Verlopen rente op aankoop_datum"""
  product_dagrente = dagrente(coupure, rente)
  product_verlopen_dagen = verlopen_dagen(coupon_datum, looptijd_maanden, aankoop_datum)
  return product_dagrente * product_verlopen_dagen
