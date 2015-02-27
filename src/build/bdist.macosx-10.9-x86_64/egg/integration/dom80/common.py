'''
Created on Sep 9, 2009

@author: tw55413
'''
  
class Opdrachten(object):
  def __init__(self):
    self.begin = {}
    self.gegevens = []
    self.eind = ''
  def __unicode__(self):
    return unicode(self.begin)
  
line128 = lambda x:'%-128s\r\n'%x.strip('\n')

def write_date(pythondate):
  return '%02i%02i%02i'%(pythondate.day, pythondate.month, (pythondate.year-2000))

def structure_to_line(structure_definition, structure_data):
  
  components = []
  for length, type, name in structure_definition:
    data = str(structure_data[name])
    if type=='N':
      if not data.isdigit():
        raise Exception('%s is not a digit : %s'%(name, data))
      data = '%0*i'%(length, int(data))        
    else:
      data = '%-*s'%(length, data[0:length])
    if len(data)!=length:
      raise Exception('%s is not of length %s : %s'%(name, length, data))
    components.append(data)
  return line128(''.join(components))
