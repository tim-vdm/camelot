# -*- coding: utf-8 -*-

import os
import logging
logger = logging.getLogger('spreadsheet.pdf')

import base
import locale
import string
import time
import datetime
from html import HtmlSpreadsheet

class DocxSpreadsheet(HtmlSpreadsheet):
  
  schema = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
  
  def add_worksheet(self, element, worksheet_name):
    """Add a worksheet as child of the element
    @type element: an elementtree element
    """
    import decimal
    cells = list(list(rows) for rows in self.generate(worksheet_name))
    
    pct = lambda x:unicode(x*50)
    
    from xml.etree import ElementTree
    tbl = ElementTree.Element('{%s}tbl'%self.schema)
    tblPr = ElementTree.SubElement(tbl, '{%s}tblPr'%self.schema)
    tblPr.append( ElementTree.Element('{%s}tblW'%self.schema, {'{%s}w'%self.schema:pct(100), '{%s}type'%self.schema:'pct'}) )
    
    grid = ElementTree.SubElement(tbl, '{%s}tblGrid'%self.schema)
    if len(cells):
      number_of_cols = len(cells[0])
    else:
      number_of_cols = 1
# These lines cause a messed up layout when opening the file with word 2007, opening it with word 2003 using
# the import filter results in fine files
#    for i in range(number_of_cols):
#      grid.append( ElementTree.Element('{%s}gridCol'%self.schema, {'{%s}w'%self.schema:'10296'}) )
    
    def cell_to_value(cell):
      if cell:
        if isinstance(cell.value, base.Expression):
          value = cell.evaluate(self)
        else:
          value = cell.value
        return value
      return u''

    for row in cells:
      tr = ElementTree.SubElement(tbl, '{%s}tr'%self.schema)
      for cell in row:
        value = cell_to_value(cell)
        tc = ElementTree.SubElement(tr, '{%s}tc'%self.schema)
        tcPr = ElementTree.SubElement(tc, '{%s}tcPr'%self.schema)
        tcW = ElementTree.SubElement(tcPr, '{%s}tcW'%self.schema, {'{%s}w'%self.schema:pct(100.0/number_of_cols), '{%s}type'%self.schema:'pct'})
        p = ElementTree.SubElement(tc, '{%s}p'%self.schema)
        if isinstance(value, (float,decimal.Decimal, int)):
          pPr = ElementTree.SubElement(p, '{%s}pPr'%self.schema)
          jc = ElementTree.SubElement(pPr, '{%s}jc'%self.schema, {'{%s}val'%self.schema:'right'})
        r = ElementTree.SubElement(p, '{%s}r'%self.schema)
        t = ElementTree.SubElement(r, '{%s}t'%self.schema)
        if isinstance(value, (float)):
          value = locale.currency(value, grouping=True, symbol=False)
        elif isinstance(value, (datetime.date)):
          value = '%02i-%02i-%02i'%(value.day, value.month, value.year)
        t.text = unicode(value)
  
    element.append(tbl)
