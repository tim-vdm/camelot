# -*- coding: utf-8 -*-

import logging
import base
import string
import decimal

logger = logging.getLogger('spreadsheet compose html')

import locale

def format_as_excel(value, format):
  if isinstance(value, (int, float, decimal.Decimal)):
      if format:
        return locale.currency(value, grouping=True, symbol=False)
  return value

def text_to_html(value, format):
  if isinstance(value, str) or isinstance(value, unicode):
    return value.replace(' ','&nbsp;').replace('\n','<br/>')
  return format_as_excel(value, format)

class HtmlSpreadsheet(base.Spreadsheet):
    
  def __init__(self, filename=None, format='html', formatter=format_as_excel):
    """Optionally give a filename and a format (html or txt) to save the file
    on finalize
    :param formatter: function that formats the content of a cell
    """
    super(HtmlSpreadsheet, self).__init__()
    self._filename = filename
    self._format = format
    self._formatter = formatter
    
  def _cell_render(self, cell):
    pass
  def group(self, range_spec):
    #@todo: store and display grouping information
    pass
  def insert_row(self, range_spec):
    #@todo: shift all other cells down
    pass
  def show_outline(self, **kw):
    #@todo: store and display outline level
    pass
  def set_column_width(self, range_spec, width):
    pass
  def set_row_height(self, range_spec, height):
    pass
  def set_orientation(self, orientation='portrait'):
    pass
  def named_range_coord(self, name):
    return self._cell_named_range_coord(name)

  def finalize(self):
    import codecs
    if self._filename:
        file = open(self._filename, 'w')
        file.write( codecs.BOM_UTF8 )
        for line in self.generate_html():
            file.write(line.encode('utf-8'))
            file.write('\n')
  
  def generate(self, worksheet_name):
    """Generator that yields for each row in the table a tuple with all the cells in that row
    and None if there is no such cell"""
    rendered_cells = self._rendered_worksheets[worksheet_name]
    rows = rendered_cells.keys()
    max_col = string.uppercase.index(max( max(row_dict.keys()) for row_dict in rendered_cells.values() ))
    for row in range(min(rows),max(rows)+1):
      row_values = [None] * (max_col + 1)
      if row in rendered_cells:
        row_dict = rendered_cells[row]
        cols = row_dict.keys()
        cols.sort()    
        for col in range(0, max_col+1):
          colname = string.uppercase[col]
          if colname in row_dict:
            cell = row_dict[colname]
            row_values[col] = cell
      yield row_values
      
  def generate_text(self, column_formats={}, default_format='%10s'):
    """Generate each line in the table as text
    @param column_width: a dictionary containing for each column its format in the text tabel, eg {'A':'%-20s'} 
    """
    for worksheet_name in self._worksheets:
      for row in self.generate(worksheet_name):
  
        def cell_to_unicode(cell,col):
          if cell:
            return column_formats.get(col,default_format)%(unicode(self._formatter(cell.evaluate(self), cell.format)))
          return column_formats.get(col,default_format)%''
        
        yield ''.join([cell_to_unicode(cell,col) for col,cell in zip(string.uppercase,row)])
    
  def generate_html(self, reveal_formulas=False, **table_kwargs):
    """Generator function that yields strings forming an html representation
    of this table"""
    for worksheet_name in self._worksheets:
      rendered_cells = self._rendered_worksheets[worksheet_name]
      rows = rendered_cells.keys()
      max_col = string.uppercase.index(max( max(row_dict.keys()) for row_dict in rendered_cells.values() ))
      yield u'<table %s>\n'%(' '.join('%s="%s"'%(k,v) for k,v in table_kwargs.items()))
      for row in range(min(rows),max(rows)+1):
        yield u'  <tr>\n   '
        if row in rendered_cells:
          row_dict = rendered_cells[row]
          cols = row_dict.keys()
          cols.sort()    
          for col in range(0, max_col+1):
            colname = string.uppercase[col]
            if colname in row_dict:
              cell = row_dict[colname]
              if reveal_formulas:
                if isinstance(cell.value, base.Expression):
                  if cell.style:
                    yield u'<td align="%s" class="%s">%s</td>'%(cell.align, cell.style, unicode(cell.contents))
                  else:
                    yield u'<td align="%s">%s</td>'%(cell.align, unicode(cell.contents))
                else:
                  if cell.style:
                    yield u'<td align="%s" class="%s">%s</td>'%(cell.align, cell.style, unicode((self._formatter(cell.value, cell.format))))
                  else:
                    yield u'<td align="%s">%s</td>'%(cell.align, unicode((self._formatter(cell.value, cell.format))))
              else:
                if cell.style:
                  yield u'<td align="%s" class="%s">%s</td>'%(cell.align, cell.style, unicode((self._formatter(cell.evaluate(self), cell.format))))
                else:
                  yield u'<td align="%s">%s</td>'%(cell.align, unicode((self._formatter(cell.evaluate(self), cell.format))))
            else:
              yield u'<td></td>'
        else:
          for col in range(0, max_col+1):
            yield u'<td></td>'
        yield u'\n  </tr>\n'
      yield u'</table>\n'
