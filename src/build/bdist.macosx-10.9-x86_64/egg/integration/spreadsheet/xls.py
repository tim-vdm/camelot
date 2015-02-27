# -*- coding: utf-8 -*-

import logging
logger = logging.getLogger('spreadsheet.xls')

import base
import string
import xlwt
import datetime
import collections

from base import column_index

class XlsSpreadsheet(base.Spreadsheet):

  def __init__(self):
    super(XlsSpreadsheet, self).__init__()
    # column width and height by sheet
    self._column_width = collections.defaultdict(dict)
    self._row_height = collections.defaultdict(dict)
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
    for cell in range_spec.generate_cells(self):
      self._column_width[cell.worksheet][cell.col] = width
  def set_row_height(self, range_spec, height):
    for cell in range_spec.generate_cells(self):
      self._row_height[cell.worksheet][cell.row] = height
  def set_orientation(self, orientation='portrait'):
    pass
  def named_range_coord(self, name):
    return self._cell_named_range_coord(name)
  def finalize(self):
    pass
  
  def generate_xls(self, filename):
    import decimal
    w = xlwt.Workbook()
    for worksheet_name in self._worksheets:
      rendered_cells = self._rendered_worksheets[worksheet_name]
      ws = w.add_sheet(worksheet_name)
      
      cellFont = xlwt.Font()
      cellFont.name = 'Arial'
      cellFont.bold = False           # Setting cell font to bold
      cellFont.height = 220           # 10*20 = 240 Font Size
  
      cellStyle = xlwt.XFStyle()
      cellStyle.font = cellFont
  
      date_format =  'dd-MM-yyyy'
      int_format = '0'
      float_format =  '0.00'
      
      for col,width in self._column_width[worksheet_name].items():
        ws.col( column_index(col) ).width = width*400
        
      for row, row_dict in rendered_cells.items():
        row_index = row-1
        for col, cell in row_dict.items():
          col_index = column_index(col)
          
          if isinstance(cell.value, base.Expression):
            value = cell.evaluate(self)
          else:
            value = cell.value
            
          #value = cell.value

          if isinstance(value, (float,decimal.Decimal)):
            value = float(value)
            cellStyle.num_format_str = float_format
          elif isinstance(value, (int)):
            cellStyle.num_format_str = int_format
          elif isinstance(value, (datetime.datetime)):
            value = value.date()
            cellStyle.num_format_str = date_format
          elif isinstance(value, (datetime.date)):
            cellStyle.num_format_str = date_format
          elif value == None:
            value = ''
          else:
            value = unicode(value)
          ws.write(row_index , col_index, value, cellStyle)
        
    w.save(filename)
