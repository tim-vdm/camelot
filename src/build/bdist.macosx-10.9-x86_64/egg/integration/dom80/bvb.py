'''
Created on Sep 9, 2009

@author: tw55413
'''

from common import line128, write_date, structure_to_line

default_begin = {
     'identificatie':'0',
     'clearing':'0',
     'voorbehouden':'0',
     'voorwerp':'00',
     'opmaak':'',
     'instelling':'',
     'toepassing':'01',
     'uitvoering':'',
     'duplicaat':' ',
     'nullen':'000',
     'rekeningnummer':'',
     'naam_opdrachtgever':'',
     'adres_opdrachtgever':'',
     'postcode_opdrachtgever':'',
     'gemeente_opdrachtgever':'',
     'taal':'1',
     'referentie':'',
     'versie':'5',                 
}

default_opdracht = {
     'identificatie':'1',
     'volgnummer':'0001',
     'referte':'',
     'blanco':' '*10,
     'rekeningnummer':'',
     'bedrag':'',
     'naam':'',
     'taal':'1',
     'begin_mededeling':'',
     'vervolg_mededeling':' '*41,
     'aard':'3',
     'aanspreektitel':'0',
     'adres_begunstigde':'',
     'postcode_begunstigde':'',
     'gemeente_begunstigde':'',
     'tweede_vervolg_mededeling':'',
     'kosten':'0',
     'blanco2':'',     
}

default_eind = {
     'identificatie':'9',
     'aantal_gegevens':'',
     'aantal_betalingsopdrachten':'',
     'totaal_bedragen':'',
     'totaal_rekeningnummers':'',
     'afgever':'',
     'referte':'',
     'blanco':' '*49,
     'voorbehouden':' '*20,
  }

def write(opdrachten, stream):
  
  from copy import copy
  
  begin = copy(opdrachten.begin)
  begin['opmaak'] = write_date(begin['opmaak'])
  begin['uitvoering'] = write_date(begin['uitvoering'])
  
  begin_structure_definition = [
     (   1,  'N',  'identificatie'),
     (   1,  'N',  'clearing'),
     (   1,  'AN', 'voorbehouden'),
     (   2,  'N',  'voorwerp'),
     (   6,  'N',  'opmaak'),
     (   3,  'N',  'instelling'),
     (   2,  'N',  'toepassing'),
     (   6,  'N',  'uitvoering'),
     (   1,  'AN', 'duplicaat'),
     (   3,  'N',  'nullen'),
     (  12,  'N',  'rekeningnummer'),
     (  26,  'AN', 'naam_opdrachtgever'),
     (  26,  'AN', 'adres_opdrachtgever'),
     (   4,  'AN', 'postcode_opdrachtgever'),
     (  22,  'AN', 'gemeente_opdrachtgever'),
     (   1,  'N',  'taal'),
     (  10,  'AN', 'referentie'),
     (   1,  'AN', 'versie'),
  ]
  
  opdracht_1_structure_definition = [
     (   1,  'N',  'identificatie'),
     (   4,  'N',  'volgnummer'),
     (   8,  'AN', 'referte'),
     (  10,  'AN', 'blanco'),
     (  12,  'N',  'rekeningnummer'),
     (  12,  'N',  'bedrag'),
     (  26,  'AN', 'naam'),
     (   1,  'N',  'taal'),
     (  12,  'AN', 'begin_mededeling'),
     (  41,  'AN', 'vervolg_mededeling'),
     (   1,  'N',  'aard'),
  ]

  opdracht_2_structure_definition = [  
     (   1,  'N',  'identificatie'),
     (   4,  'N',  'volgnummer'),
     (   1,  'N',  'aanspreektitel'),
     (  26,  'AN', 'adres_begunstigde'),
     (   4,  'AN', 'postcode_begunstigde'),
     (  22,  'AN', 'gemeente_begunstigde'),
     (  53,  'AN', 'tweede_vervolg_mededeling'),
     (   1,  'N',  'kosten'),
     (  16,  'AN', 'blanco2'),
  ]
 
  eind_structure_definition = [
     (   1,  'N',  'identificatie'),
     (   4,  'N',  'aantal_gegevens'),
     (   4,  'N',  'aantal_betalingsopdrachten'),
     (  12,  'N',  'totaal_bedragen'),
     (  15,  'N',  'totaal_rekeningnummers'),
     (  11,  'N',  'afgever'),
     (  12,  'AN', 'referte'),
     (  49,  'AN', 'blanco'),
     (  20,  'AN', 'voorbehouden'),
  ]
      
  stream.write( structure_to_line(begin_structure_definition, begin ) )
  aantal_gegevens = 0
  aantal_betalingsopdrachten = 0
  totaal_bedragen = 0
  totaal_rekeningnummers = 0
  for i, gegevens in enumerate(opdrachten.gegevens):
    gegevens = copy(gegevens)
    aantal_gegevens += 2
    aantal_betalingsopdrachten += 1
    totaal_bedragen += gegevens['bedrag']
    totaal_rekeningnummers = (totaal_rekeningnummers + int(gegevens['rekeningnummer']))%1000000000000000
    gegevens.update({'volgnummer':i+1})
    stream.write( structure_to_line(opdracht_1_structure_definition, gegevens) )
    gegevens['identificatie'] = 2
    stream.write( structure_to_line(opdracht_2_structure_definition, gegevens) )
    
  eind = copy(opdrachten.eind)
  aantal_gegevens = aantal_gegevens % 10000
  aantal_betalingsopdrachten = aantal_betalingsopdrachten % 10000
  eind.update({'aantal_gegevens':aantal_gegevens, 'aantal_betalingsopdrachten':aantal_betalingsopdrachten,
               'totaal_bedragen':totaal_bedragen, 'totaal_rekeningnummers':totaal_rekeningnummers,
               'referte':begin['referentie']})
  stream.write( structure_to_line(eind_structure_definition ,eind) )
  
  return True
