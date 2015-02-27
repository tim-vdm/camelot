
from base import *
#from oo import OpenOfficeSpreadsheet


logger = logging.getLogger('excel compose')

def make_spreadsheet(implementation, *a, **kw):
  
  from ms import MicrosoftSpreadsheet
  implementations = {
#    'oo-calc' : OpenOfficeSpreadsheet,
    'msexcel' : MicrosoftSpreadsheet,
  }
  imp = implementations.get(implementation)
  if imp == None:
    raise NotImplementedError()
  return imp(*a, **kw)

def test():
  from excelerator import ExceleratorSpreadsheet
  #ss = make_spreadsheet('msexcel', sheet_name='Offerte', template=None, outputfile='output.xls')
  ss = ExceleratorSpreadsheet(sheet_name='Offerte', outputfile='test.xls')
  #ss.finalize()
  b2 = Cell('B', 2, 3, tip='cell b2', format='0,00')
  c2 = Cell('C', 2, 7, tip='cell c2', format='0,00')
  d2 = Cell('D', 2, Mul(b2, c2), tip='cell d2', format='0,00')
  d3 = Cell('D', 3, Reference(d2), tip='cell d3', format='0,00')
  ss.render(b2, c2, d2, d3)
  b4 = Cell('B', 4, 13, tip='cell b4', format='0,00')
  c4 = Cell('C', 4, 19, tip='cell c4', format='0,00')
  d4 = Cell('D', 4, Mul(Add(b2, c2), Add(b4, c4)), tip='cell d4', format='0,00')
  ss.render(b4, c4, d4)
  ss.finalize()

if __name__ == '__main__':
  print 'run test'
  test()