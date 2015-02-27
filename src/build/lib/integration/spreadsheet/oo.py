
import traceback
import logging

from base import Spreadsheet
from libraries.integration.openoffice import oo_template

logger = logging.getLogger('excel compose oo')

class OpenOfficeSpreadsheet(Spreadsheet):
  def __init__(self, sheet_name, template, outputfile):
    self.doc = oo_template.oo_template_doc(filename, hidden=True)
    self.doc.load()
    self.sheet = self.doc.doc.getSheets().getByName(sheet_name)
    self.cursor = self.sheet.createCursor()
  def group(self, range_spec):
    raise NotImplementedError()
  def insert_row(self, range_spec):
    raise NotImplementedError()
  def show_outline(self, **kw):
    raise NotImplementedError()
  def finalize(self):
    raise NotImplementedError()
  def _cell_render(self, cell):
    raise NotImplementedError()
#  def _cell_simple_range(self, cell):
#    return self.cursor.getCellByPosition(cell.col, cell.row) # sheet.Cells(self.row, self.col)
#  def _cell_named_range(self, cell):
#    return self.cursor.getCellRangeByName(cell.name) # sheet.Range(self.name)
