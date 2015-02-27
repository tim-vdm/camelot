from datetime import date
from copy import copy

from common import Opdrachten, line128, write_date, structure_to_line

gegevensopname_structure_definition = [
     (   1,  'N',   'identificatie'),
     (   4,  'N',   'volgnummer'),
     (   12, 'N',   'dommicilieringsnummer'),
     (   1,  'N',   'aard'),
     (   12, 'N',   'bedrag'),
     (   26, 'AN',  'schuldeiser'),
     (   15, 'AN',  'mededeling1'),
     (   15, 'AN',  'mededeling2'),
     (   12, 'N',   'referte'),
]

def read(stream):
  
  o = Opdrachten()
  
  def parse_date(datestring):
    return date(day=int(datestring[0:2]), month=int(datestring[2:4]), year=int(datestring[4:6])+2000)
  
  def parse_beginopname(line):
    #'00000%(opmaak)s%(instelling)03s02%(referentie)10s%(afgever)011i%(schuldeiser)011i%(rekeningnummer)-12s%(versie)s %(spildatum)s'
    opmaak = parse_date(line[5:11])
    instelling = line[11:14]
    referentie = line[16:26]
    afgever = int(line[26:37])
    schuldeiser = int(line[37:48])
    rekeningnummer = line[48:60]
    versie = line[60:61]
    spildatum = parse_date(line[62:68])
    gegevens = locals()
    del gegevens['line']
    del gegevens['parse_date']
    del gegevens['o']
    o.begin = gegevens
  
  def parse_eindopname(line):
    o.eind = line
  
  def parse_gegevensopname(line):
    volgnummer = int(line[1:5])
    dommicilieringsnummer = long(line[5:17])
    aard = {0:'invordering', 1:'terugbetaling'}[int(line[17])]
    bedrag = int(line[18:30])
    schuldeiser = line[30:56]
    mededeling1 = line[56:71]
    mededeling2 = line[71:86]
    referte = int(line[86:98])
    gegevens = locals()
    del gegevens['line']
    del gegevens['o']
    o.gegevens.append(gegevens)
  
  parsers = {0:parse_beginopname, 1:parse_gegevensopname, 9:parse_eindopname}
  
  for line in stream:
    identificatie = int(line[0])
    parsers[identificatie](line)
    
  return o

def write(opdrachten, stream):

  begin = copy(opdrachten.begin)
  begin['opmaak'] = write_date(begin['opmaak'])
  begin['spildatum'] = write_date(begin['spildatum'])
  begin['versie'] = '5'
  line = '00000%(opmaak)s%(instelling)03s02%(referentie)10s%(afgever)011i%(schuldeiser)011i%(rekeningnummer)-12s%(versie)s %(spildatum)s'%(begin)
  stream.write( line128(str(line)) )
  
  aantal_invorderingen = 0
  aantal_terugbetalingen = 0
  totaal_invorderingen = 0
  totaal_terugbetalingen = 0
  totaal_nummers_invorderingen = 0
  totaal_nummers_terugbetalingen = 0
  for i,gegevens in enumerate(opdrachten.gegevens):
    if gegevens['aard']=='invordering':
      aantal_invorderingen += 1
      totaal_invorderingen += gegevens['bedrag']
      totaal_nummers_invorderingen = (totaal_nummers_invorderingen + gegevens['dommicilieringsnummer'])%1000000000000000
    elif gegevens['aard']=='terugbetaling':
      aantal_terugbetalingen += 1
      totaal_terugbetalingen += gegevens['bedrag']
      totaal_nummers_terugbetalingen = (totaal_nummers_terugbetalingen + gegevens['dommicilieringsnummer'])%1000000000000000
    else:
      raise Exception('onbekende aard van verrichting : %s'%gegevens['aard'])
    gegevens.update( { 'volgnummer':i+1, 
                       'aard':{'invordering':0, 'terugbetaling':1}[gegevens['aard']],
                       'identificatie':1 } )
    stream.write( structure_to_line(gegevensopname_structure_definition, gegevens ) )
  aantal_invorderingen = aantal_invorderingen % 10000
  aantal_terugbetalingen = aantal_terugbetalingen % 10000
  eind = '9%(aantal_invorderingen)04i%(totaal_invorderingen)012i%(totaal_nummers_invorderingen)015i'%locals()
  eind += '%(aantal_terugbetalingen)04i%(totaal_terugbetalingen)012i%(totaal_nummers_terugbetalingen)015i'%locals()
  stream.write( line128(eind) )
  return line128(eind)
  
if __name__== '__main__':
  #origin = 'C:\\Documents and Settings\\Erik Janssens\\Mijn documenten\\patronale\\src\\libraries\\integration\\dom80\\DOM-augustus-08.txt'
  #dest = 'C:\\Documents and Settings\\Erik Janssens\\Mijn documenten\\patronale\\src\\libraries\\integration\\dom80\\DOM-augustus-08-checksum.txt'
  origin = 'februari_2011.txt'
  dest = 'maart_2011.txt'
  #testfile = 'C:\\Documents and Settings\\Erik Janssens\\Bureaublad\\DOM80229.txt'
  #testfile = 'C:\\DOM-juni-08-no-checksum.txt'
  opdrachten = read(open(origin))
  #for g in opdrachten.gegevens:
  #  print g
  opdrachten.begin['spildatum'] = date(2011,3,1)
  opdrachten.begin['opmaak'] = date(2011,3,1)
  print opdrachten.begin
  print write(opdrachten, open(dest,'w'))
    
