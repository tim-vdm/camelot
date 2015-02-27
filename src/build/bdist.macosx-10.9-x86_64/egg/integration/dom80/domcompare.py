origin = 'C:\\Documents and Settings\\Erik Janssens\\Mijn documenten\\patronale\\src\\libraries\\integration\\dom80\\origineel-november-07.txt'
test = 'C:\\Documents and Settings\\Erik Janssens\\Mijn documenten\\patronale\\src\\libraries\\integration\\dom80\\test-november-07.txt'

from dom80 import read

origin = read(open(origin))
test = read(open(test))

origin_gegevens = dict( (g['dommicilieringsnummer'],g) for g in origin.gegevens )
test_gegevens = dict( (g['dommicilieringsnummer'],g) for g in test.gegevens )

equal = 0
different = 0

for key,og in origin_gegevens.items():
  if key in test_gegevens:
    tg = test_gegevens[key]
    if abs(int(og['bedrag'])-int(tg['bedrag']))>1:
      different += 1
      print og['bedrag'], tg['bedrag'], og['dommicilieringsnummer'], og['mededeling2']
    else:
      equal += 1
      
print 'length original : ', len(origin_gegevens)
print 'missing in test : '
for k,g in origin_gegevens.items():
  if k not in test_gegevens:
    print g
print 'length test : ', len(test.gegevens)
print 'missing in original : '
for k,g in test_gegevens.items():
  if k not in origin_gegevens:
    print g
print 'equal', equal
print 'different', different
