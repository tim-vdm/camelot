# -*- coding: utf-8 -*-

import os
import logging
logger = logging.getLogger('spreadsheet.pdf')

import base
import string
import time
import datetime
from html import HtmlSpreadsheet

class PdfSpreadsheet(HtmlSpreadsheet):
    
  def __init__(self, filename=None, format='html'):
    super(PdfSpreadsheet, self).__init__(filename=filename, format=format)
  
  def generate_worksheet(self, worksheet_name):
    """Generate a reportlab table object"""
    import decimal
    from reportlab.platypus import Table
    cells = list(list(rows) for rows in self.generate(worksheet_name))
    
    def cell_to_data(cell):
      if cell:
        if isinstance(cell.value, base.Expression):
          value = cell.evaluate(self)
        else:
          value = cell.value
        return unicode(value)
      return u''
    
    data = [[cell_to_data(cell) for cell in row] for row in cells]
    
    style = []
    for i,row in enumerate(cells):
      for j,cell in enumerate(row):
        if cell:
          if isinstance(cell.value, base.Expression):
            value = cell.evaluate(self)
          else:
            value = cell.value     
          if isinstance(value, (float, int, decimal.Decimal)):
            style.append(('ALIGN', (j,i), (j,i), 'RIGHT'))

    
    table = Table(data, style=style)
    return table
    
  def generate_pdf(self, filename):
    """started from example code found at http://www.magitech.org/2006/05/05/getting-started-with-reportlab/"""
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.pagesizes import A4, landscape, portrait
    # Our container for 'Flowable' objects
    elements = []
    # A basic document for us to write to 
    doc = SimpleDocTemplate(filename)
    doc.pagesize = landscape(A4)
    for worksheet_name in self._worksheets:
      table = self.generate_worksheet(worksheet_name)
      elements.append(table)
    # Write the document to disk
    doc.build(elements)
    