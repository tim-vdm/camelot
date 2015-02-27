# -*- coding: utf-8 -*-

import logging
import string
import itertools
import operator

logger = logging.getLogger('spreadsheet base')

DEFAULT_WORKSHEET = 'Sheet1'

class Spreadsheet(object):
  def __init__(self):
    # list with worksheets in order of appearance
    self._worksheets = []
    # a sparse matrix mapping cell coordinates on cell values for each worksheet
    self._rendered_worksheets = dict()
  def render(self, *cells):
    for cell in cells:
      if isinstance(cell, tuple) or isinstance(cell, list):
        self.render(*cell)
      elif isinstance(cell, dict):
        self.render(*cell.values())
      else:
        # Named cells don't have a row and a coll, so we don't know where to put them
        if hasattr(cell,'row') and hasattr(cell,'col'):
          if cell.worksheet not in self._worksheets:
            self._worksheets.append(cell.worksheet)
          row_dict = self._rendered_worksheets.setdefault(cell.worksheet, {}).setdefault(cell.row, {})
          row_dict[cell.col] = cell
          self._cell_render(cell)
        else:
          self._cell_render(cell)
  def has_cell(self, col, row, worksheet=DEFAULT_WORKSHEET):
    if row in self._rendered_worksheets[worksheet]:
      row_dict = self._rendered_worksheets[worksheet][row]
      if col in row_dict:
        return True
    return False
  def get_cell(self, col, row, worksheet=DEFAULT_WORKSHEET):
    try:
      row_dict = self._rendered_worksheets[worksheet][row]
      return row_dict[col]
    except KeyError:
      raise Exception('cell %s%s was not rendered in this spreadsheet'%(col,row))
    
  def get_value(self, col, row):
    return self.get_cell(col, row).value
  
  def evaluate(self, col, row):
    cell = self.get_cell(col, row)
    return cell.evaluate( self )
  
  def group(self, range_spec):
    raise NotImplementedError()
  def set_column_width(self, range_spec, width):
    raise NotImplementedError()
  def set_row_height(self, range_spec, height):
    raise NotImplementedError()
  def set_orientation(self, orientation='portrait'):
    raise NotImplementedError()  
  def insert_row(self, range_spec):
    raise NotImplementedError()
  def show_outline(self, **kw):
    raise NotImplementedError()
  def finalize(self):
    raise NotImplementedError()
  def _cell_render(self, cell):
    raise NotImplementedError()

# een expressie, komt overeen met een formule in excel
class Expression(object):
  def __init__(self, *args):
    self.args = args
    if (len(args) == 1) and (isinstance(args[0], list) or isinstance(args[0], tuple)):
      self.args = args[0]
  def _value(self, x, spreadsheet):
    """return the value of x, if x is a cell or an expression, evaluate it
    and return the result"""
    if isinstance(x, (int, float, str, unicode)):
      return x
    return x.evaluate(spreadsheet)
  def __unicode__(self):
    return u' '.join([unicode(arg) for arg in self.args])
  def __str__(self):
    return self.__unicode__()
  def evaluate(self, spreadsheet):
    return eval(self.__unicode__())

# een referentie naar een andere cell
class Reference(Expression):
  def __unicode__(self):
    return unicode(self.args[0])
  def evaluate(self, spreadsheet):
    return self.args[0].evaluate(spreadsheet)

# een bewerking op cellen
class Operator(Expression):
  

  
  def __unicode__(self):
    args = filter(lambda x: bool(len(x.strip())) , map(unicode, self.args))
    if len(args) == 0: return u''
    if len(args) == 1: return args[0]
    return u'(%s)' % self.operator.join(args)

class Add(Operator):
  def __init__(self, *a, **kw):
    super(Add, self).__init__(*a, **kw)
    self.operator = u'+'
  def evaluate(self, spreadsheet):
    return reduce(operator.add, (self._value(cell, spreadsheet) for cell in self.args), 0)

class Eq(Operator):
  def __init__(self, *a, **kw):
    super(Eq, self).__init__(*a, **kw)
    self.operator = u'='
  
  def evaluate(self, spreadsheet):
    if len(self.args):
      return self.args[0].evaluate( spreadsheet )
      
class Sub(Operator):
  def __init__(self, *a, **kw):
    super(Sub, self).__init__(*a, **kw)
    self.operator = u'-'
  def evaluate(self, spreadsheet):
    values = [cell.evaluate(spreadsheet) for cell in self.args]
    if None in values:
      return None
    return reduce(operator.sub, values)
  
class Mul(Operator):
  def __init__(self, *a, **kw):
    super(Mul, self).__init__(*a, **kw)
    self.operator = u'*'
  def evaluate(self, spreadsheet):
    return reduce(operator.mul, (self._value(cell, spreadsheet) for cell in self.args), 1)    

class Pow(Operator):
  def __init__(self, *a, **kw):
    super(Pow, self).__init__(*a, **kw)
    self.operator = u'^'
  def evaluate(self, spreadsheet):
    return reduce(operator.pow, (cell.evaluate(spreadsheet) for cell in self.args), 1)
  
class Div(Operator):
  def __init__(self, *a, **kw):
    super(Div, self).__init__(*a, **kw)
    self.operator = u'/'
  def evaluate(self, spreadsheet):
    return reduce(operator.div, (cell.evaluate(spreadsheet) for cell in self.args))

# Sum is een bewerking op een Range
class Sum(Expression):
  def evaluate(self, spreadsheet):
    sum = 0
    for range in self.args:
      for cell in range.generate_cells(spreadsheet):
        sum = cell.evaluate(spreadsheet) + sum
    return sum
  def __unicode__(self):
    args = filter(lambda x: bool(len(x.strip())) , map(unicode, self.args))
    if len(args) == 0: return u''
    return u'SUM(%s)' % u';'.join(args)
  
class If(Expression):
  def __unicode__(self):
    args = filter(lambda x: bool(len(x.strip())) , map(unicode, self.args))
    if len(args) == 0: return u''
    return u'IF(%s)' % u';'.join(args)
  
class Round(Operator):
  def __init__(self, number, count):
    super(Round, self).__init__(number, count)
    
  def evaluate(self, spreadsheet):
    return round( self._value(self.args[0], spreadsheet),  self._value(self.args[1], spreadsheet) )
    
  def __unicode__(self):
    args = filter(lambda x: bool(len(x.strip())) , map(unicode, self.args))
    return u'ROUND(%s)' % u';'.join(args)
    
class Min(Expression):
  def __unicode__(self):
    args = filter(lambda x: bool(len(x.strip())) , map(unicode, self.args))
    if len(args) == 0: return u''
    return u'MIN(%s)' % u';'.join(args)
   
class Max(Expression):
  def __unicode__(self):
    args = filter(lambda x: bool(len(x.strip())) , map(unicode, self.args))
    if len(args) == 0: return u''
    return u'MAX(%s)' % u';'.join(args) 
    
class BaseCell(object):
  def __init__(self, value=None, tip=None, format=None, align='left', style=None):
    self.value = value
    self.comment = tip
    self.format = format
    self.align = align
    self.style = style
  def evaluate(self, spreadsheet):
    value = spreadsheet.get_value(self.col, self.row)
    if isinstance(value, Expression):
      return value.evaluate(spreadsheet)
    return value
  def __unicode__(self):
    raise NotImplementedError()
  def __str__(self):
    return self.__unicode__()
  def __location(self):
    return str(self)
  location = property(__location)
  def __contents(self):
    if isinstance(self.value, Expression):
      return u'=%s' % unicode(self.value)
    return unicode(self.value)
  contents = property(__contents)

class Cell(BaseCell):
  def __init__(self, col, row, value=None, tip=None, format=None, align='left', style=None, worksheet=DEFAULT_WORKSHEET, **kw):
    BaseCell.__init__(self, value, tip, format, align, style, **kw)
    self.col = col
    self.row = row
    self.worksheet = worksheet
  def __unicode__(self):
    return u'%s%d' % (self.col, self.row)

class NamedCell(BaseCell):
  def __init__(self, name, *a, **kw):
    BaseCell.__init__(self, *a, **kw)
    self.name = name
  def __unicode__(self):
    return unicode(self.name)

class Range(object):
  
  def __init__(self, *args):
    cells = args
    if (len(args) == 1) and (isinstance(args[0], list) or isinstance(args[0], tuple)):
      cells = args[0] 
    cols = [ cell.col for cell in cells if hasattr(cell,'col')]
    rows = [ cell.row for cell in cells if hasattr(cell,'row')]
    worksheets = [ cell.worksheet for cell in cells if hasattr(cell,'worksheet')]
    if len(worksheets):
      self.worksheet = worksheets[0]
    else:
      self.worksheet = DEFAULT_WORKSHEET
    if len(cells):
      self.min = (min(cols), min(rows))
      self.max = (max(cols), max(rows))
    else:
      self.min = None
      self.max = None
      
  def generate_cells(self, spreadsheet):
    """Generate all cells within this range in a spreadsheet"""
    for row in range(self.min[1], self.max[1]+1):
      for col in range( column_index(self.min[0]), column_index(self.max[0])+1 ):
        if spreadsheet.has_cell( column_name( col ), row, self.worksheet):
          yield spreadsheet.get_cell( column_name( col ), row, self.worksheet)
          
  def __unicode__(self):
    if self.min and self.max:
      return u'%s%d:%s%d'%tuple( x for x in itertools.chain(self.min, self.max) )
    else:
      return u'' 

def column_name(i):
    """Create a column name starting from an index starting at 0
    eg : i=0 -> column_name='A'
    """
    if (i >= 0 and i <= 25):
        return string.uppercase[i];
    elif (i > 25):
        return column_name(i/26 - 1) + column_name(i%26)
    raise Exception('Invallid column number %s'%i)

def column_index(name):
    """Create a column index from a column name, where 'A' has index 0"""
    i = 0
    for position,letter in enumerate(reversed(name)):
        letter_index = string.uppercase.index(letter)
        i += (letter_index+1) * 26**position
    return i-1