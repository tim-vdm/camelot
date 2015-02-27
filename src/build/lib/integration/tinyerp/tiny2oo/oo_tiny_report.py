from report import custom
import netsvc
import tempfile
import os
import logging
import traceback

logger = logging.getLogger('oo_tiny_report')

from integration.openoffice import oo_template

class oo_tiny_report(custom.report_custom):
  """An open office report ready for integration into
  tiny erp.
  
  Inherit this class and modify the fill_document method
  to create a custom report.
  """
  def __init__(self, name, return_type):
    """@param name name of the tiny object, ex : 'report.hypo.rappel_sheet'
       @param template path to the oo template document
       @param return_type extension of the generated document, ex : pdf, xls, doc
    """
    custom.report_custom.__init__(self, name)
    self._return_type = return_type
  def create(self, cr, uid, ids, datas, context={}):
    service = netsvc.LocalService('object_proxy')
    tiny = lambda *a, **ka:service.execute(cr.dbname, uid, *a, **ka)
    try:
      name = self.template_name(tiny, ids)
      sheet = oo_template.oo_template_doc( name )
      self.fill_document(sheet, tiny, ids, datas)
      return sheet.readContent(self._return_type)
    except Exception, e:
      logger.error('Error creating %s for dossier %s : %s'%(self.name, ids, e))
      from inspect import trace
      stacktrace = 'stack trace : \n' + traceback.format_exc()
      logger.error(stacktrace)
      return (stacktrace, 'txt')
  def fill_document(self, doc, tiny, ids, datas):
    raise Exception('fill_document not implemented')
  def template_name(self, tiny, ids):
    raise Exception('template_name not implemented')