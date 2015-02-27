# -*- coding: utf-8 -*-

import os
import logging
import traceback
import win32com.client
import pythoncom
import base

logger = logging.getLogger('excel compose ms')
logger.setLevel(logging.INFO)

class MicrosoftSpreadsheet(base.Spreadsheet):
  def __init__(self, sheet_name, template=None, outputfile=None, interactive=False):
    super(MicrosoftSpreadsheet, self).__init__()
    self.interactive = interactive
    self.app = None
    self.sheet = None
    try:
      pythoncom.CoInitialize()
      # using gencache seems not to work any more after passing through py2exe
      self.app = win32com.client.gencache.EnsureDispatch("Excel.Application")
      #self.app = win32com.client.Dispatch("Excel.Application")
      if not self.interactive:
        self.app.Visible = False
        self.app.ScreenUpdating = False
      else:
        self.app.Visible = True
        self.app.ScreenUpdating = True       
      if template == None:
        self.app.Workbooks.Add()
      else:
        self.app.Workbooks.Add(template)
      if outputfile:
        if os.path.exists(outputfile):
          os.remove(outputfile)
        self.app.ActiveWorkbook.SaveAs(outputfile) #, FileFormat=win32com.client.constants.xlExcel9795)
      self.sheet = self.app.ActiveWorkbook.Sheets(1)
      self.sheet.Application.Calculation = win32com.client.constants.xlCalculationManual #-4135  xlCalculationManual or xlCalculationAutomatic
    except:
      logger.exception('init failed')
      self.finalize()
      raise
  def group(self, range_spec):
    self.sheet.Range(range_spec).Group()
  def insert_row(self, range_spec):
    range = self.sheet.Range(range_spec)
    range.EntireRow.Insert()
  def show_outline(self, **kw):
    self.sheet.Outline.ShowLevels(**kw)
  def named_range_coord(self, name):
    return self._cell_named_range_coord(name)
  def finalize(self):
    if self.sheet:
      try:
        self.sheet.Application.Calculation = win32com.client.constants.xlCalculationAutomatic #-4105 
      except:
        if self.app.ActiveWorkbook:
          self.app.ActiveWorkbook.Close()
    if self.app:
      try:
        self.app.ScreenUpdating = True
        self.app.Visible = True
        if self.app.ActiveWorkbook:
          self.app.ActiveWorkbook.Save()
      except:
        if self.app.ActiveWorkbook:
          self.app.ActiveWorkbook.Close()
        raise
  def _cell_render(self, cell):
    logger.debug('render cell %s with %s and tip %s' % tuple(map(unicode, (cell.location, cell.contents, cell.comment))))
    range = self._cell_range(cell)
    range.Value = unicode(cell.contents)
    if cell.comment != None:
      if range.Comment == None:
        range.AddComment(Text=cell.comment)
      else:
        range.Comment.Text(Text=cell.comment)
    if cell.format != None:
      range.NumberFormat = cell.format
  def _cell_range(self, cell):
    if isinstance(cell, base.NamedCell):
      return self._cell_named_range(cell)
    elif isinstance(cell, base.Cell):
      return self._cell_simple_range(cell)
    else:
      raise NotImplementedError()
  def _cell_simple_range(self, cell):
    return self.sheet.Cells(cell.row, cell.col)
  def _cell_named_range(self, cell):
    return self.sheet.Range(cell.name)
  def _range_range(self, range):
    return self.sheet.Range(range.location)
  def _cell_named_range_coord(self, name):
    range = self.sheet.Range(name)
    return range.Row, range.Column
