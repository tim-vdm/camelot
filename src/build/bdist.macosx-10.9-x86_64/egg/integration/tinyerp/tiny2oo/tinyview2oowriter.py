import string
import logging

from currency import *
from logging_functions import *
#from elementtree import ElementTree
import oo_doc_layout

try:
  from elementtree import ElementTree
except:
  import xml.etree.cElementTree as ElementTree

# logger type
logger = logging.getLogger('tinyview2oowriter')

# helper function
ParseCellName = lambda pos: '%s%i' % (string.uppercase[pos[0]], (pos[1]+1))
utf8_decoder = lambda x: unicode(x, encoding='utf-8', errors='replace')

# tiny_view_2_oo_writer class
class tiny_view_2_oo_writer(object):
  """Class with helper methods to put Tiny Erp objects into an
  Open Office Writer document by using the views available in 
  Tiny Erp to layout the document
  
  All insert functions return the new cell names of the bottom left
  and the bottom right corner originating from the cell at which the
  content was inserted.
  """


  def __init__(self, tiny, doc, createStruct, context={}, decoder=utf8_decoder):
    """
      @param tiny a function that can be called to invoke methods on tiny erp objects
      @param doc an open office document in which we will be writing tiny erp objects
      @param createStruct a function to create oo objects by calling the
      function with the name of the object as its argument
    """

    self.tiny = tiny
    self.doc = doc
    self.txt = doc.Text
    self.createStruct = createStruct
    self.prefered_views = {}
    self.context = context
    self.decoder = decoder
    self.layout = oo_doc_layout.oo_doc_layout()
    
    # apply default styles
    self.layout.table_heading(self.doc)
    self.layout.table_content(self.doc)

  def _insert_field_name(self, tbl, tblcsr, field):
    """Insert the name of a field in a table, at the cursor position
    @param tbl OO text table
    @param tblcsr cursor in the text table at which to insert the field
    @param field the field definition
    @return (bl,br) cell name of the bottom left and bottom right corner
    """
    cellname = tblcsr.getRangeName()
    celltxt = tbl.getCellByName(cellname)
    end = celltxt.getEnd()
    end.setString( self.decoder('%s' % field['string']) )
    return (cellname, cellname) 
    
  def _insert_field_into_text(self, tbl, tblcsr, key, field, value):
    """
      Internal function to insert the value of a field into a
      Text object, overwrite this to modify how a specific field
      is handled
      @param tbl OO text table
      @param tblcsr cursor in text table
      @param key name of the field
      @param field field definition
      @param value value of the field
      @return (bl,br) cell name of the bottom left and bottom right corner
    """
  
    # get name attribute and log
    log_create(logger, 'field', key)
    cellname = tblcsr.getRangeName()
    celltxt = tbl.getCellByName(cellname)    

    def no_split(method):
      """Decorator for field insert functions that don't change the cell
      in which they insert content"""
      def new_method():
        txtrange = celltxt.getEnd()
        self.layout.field_element(txtrange)
        method()
        return cellname, cellname
      return new_method
    
    # field handlers picked with locals
    @no_split
    def char_field():
      celltxt.setString( self.decoder('%s'%value ) )

    @no_split
    def text_field():
      celltxt.setString(self.decoder('%s'%value ))

    @no_split
    def boolean_field():
      txtcsr = celltxt.getEnd()
      self.layout.center_align(txtcsr)
      if value == True:
        self.layout.boolean_true(txtcsr)
      else:
        self.layout.boolean_false(txtcsr)

    # currency must be horizontally right-aligned
    @no_split
    def float_field():
      txtcsr = celltxt.getEnd()
      self.layout.align_right(txtcsr)
      txtcsr.setString('%s' % euro(value))

    @no_split
    def integer_field():
      txtcsr = celltxt.getEnd()
      self.layout.align_right(txtcsr)
      txtcsr.setString('%s'%value)
      
    @no_split
    def selection_field():
      d = dict( i for i in field['selection'] )
      try:
        celltxt.setString(self.decoder('%s'%d[value] ))
      except KeyError, e:
        logger.error('Could not find value for key %s in for selection field %s'%(value, field['string']), exc_info=e)
        logger.error(unicode(d))

    @no_split
    def date_field():
      (year, month, day) = value.split('-')
      celltxt.getEnd().setString('%s/%s/%s' % (day, month, year))

    @no_split
    def many2one_field():
      celltxt.setString(self.decoder('%s'%value[1]))

    def one2many_field():
      return self.insert_tree_into_text(tbl, tblcsr, field['relation'], value)

    def many2many_field():
      return one2many_field()

    field_handlers = locals()

    # handle the field with defined function or log unhandled field
    if '%s_field' % field['type'] in field_handlers:
      if value != False or field['type']=='boolean':
        return field_handlers['%s_field' % field['type']]()
    else:
      log_unhandled_field(logger, key, field['type'])     
    return cellname,cellname

  def insert_tree_into_text(self, tbl, tblcsr, object_name, object_ids, view_id=None):

    """
      insert a tree view (or table) into a text object
      @param tbl OO texttable instance
      @param tblcsr OO texttablecursor instance
      @param txt an Open Office text object
      @param object_name the TinyErp name of the object
      @param object_ids a list of id's of objects to put in the table
    """
    if view_id == None:
      view_id = ''

    form = self.tiny(object_name, 'fields_view_get', view_id, 
        'tree', self.context, False )

    tinylayout = ElementTree.XML(form['arch'])
    keys = [ n.attrib['name'] for n in [ e for e in tinylayout if 'name' in e.attrib ] ]

    fields = form['fields']

    # query the tiny object
    rows = self.tiny(object_name, 'read', object_ids, fields.keys())

    # if the table is empty, we still want an empty row in the table
    nRows = max(1, len(rows))
    nCells = len(fields)
    
    if nRows:
      # split horizontally
      # we should have substracted one from the nRows because the first
      # parameter of splitRange really means split "this row this many times"
      # but we always need one row for the title
      tblcsr.splitRange(nRows, True)
      
    # split vertically
    if nCells > 1:
      tblcsr.splitRange(nCells - 1, False)
    
    for ki, key in enumerate(keys):
      cellname = tblcsr.getRangeName()
      celltxt = tbl.getCellByName(cellname)
      self.layout.tree_element_heading(celltxt.getEnd())
      self._insert_field_name(tbl, tblcsr, fields[key])
      if ki+1<len(keys):
        tblcsr.goRight(1, False)
      bottom_right = tblcsr.getRangeName()
    
    # rewind to first cell
    if len(keys)>1:
      tblcsr.goLeft(len(keys)-1, False)
    bottom_left = tblcsr.getRangeName()

    # insert content in cells
    for row in rows:
      tblcsr.goDown(1, False)
      # split vertically
      if nCells > 1:
        tblcsr.splitRange(nCells - 1, False)
      for ki, key in enumerate(keys):
        cellname = tblcsr.getRangeName()
        if ki==0:
          bottom_left, bottom_right = self._insert_field_into_text(tbl, tblcsr, key, fields[key], row[key])
        else:
          not_needed, bottom_right = self._insert_field_into_text(tbl, tblcsr, key, fields[key], row[key])
        if ki+1<len(keys):
          tblcsr.goRight(1, False)
      if len(keys)>0:
        tblcsr.goLeft(len(keys)-1, False)
        
    #if the table was empty, insert an empty row
    if len(rows)==0:
      tblcsr.goDown(1, False)
      bottom_left = tblcsr.getRangeName()
      if nCells > 1:
        tblcsr.splitRange(nCells - 1, False)
        tblcsr.goRight(nCells-1, False)
        bottom_right = tblcsr.getRangeName()
      
    return bottom_left, bottom_right

  def insert_forms_into_text(self, tbl, tblcsr, object_name, object_ids,
      view_id = None):
    """insert many forms into a text document"""

    nRows = len(object_ids)
    if nRows>1:
      tblcsr.splitRange(nRows-1, True)
      
    bottom_left, bottom_right = tblcsr.getRangeName(),tblcsr.getRangeName() 
    
    if len(object_ids):
      for i,object_id in enumerate(object_ids):
        bottom_left, bottom_right = self.insert_form_into_text(tbl, tblcsr, object_name, object_id, view_id)
        tblcsr = tbl.createCursorByCellName(bottom_left)
        if i+1<len(object_ids):
          tblcsr.goDown(1, False)
    else:
      bottom_left, bottom_right = self._insert_field_into_text(tbl, tblcsr, 'dummy', {'type':'char'}, 'nihil')
      
    return bottom_left, bottom_right

  def insert_table(self, cursor):
    """
    insert a table in the text document
    @param cursor at which to insert the table
    @return (table, cursor) the inserted table and a cursor in cell A1
    """
    table = self.doc.createInstance('com.sun.star.text.TextTable')
    table.initialize(1, 1)
    self.txt.insertTextContent(cursor.getEnd(), table, True)
    return table, table.createCursorByCellName('A1')
    
  def _page_element(self, page, tbl, tblcsr, fields, values, max_columns=4):
    """
      parse a page xml node
      @param page is a page node
      @param tbl OO table in which to insert the page
      @param tblcsr Cursor in table at position in which to insert the page
      @param fields are the fields
      @param values are the fields' values
    """

    # log and get node name attribute
    page_name = page.attrib.get('string', '')
    log_create(logger, 'page', page_name + ' in cell %s'%tblcsr.getRangeName())
    bottom_left, bottom_right = tblcsr.getRangeName(),tblcsr.getRangeName()
    
    def fill_page_name(cursor):
      cellname = cursor.getRangeName()
      txt = tbl.getCellByName(cellname)    
      range = txt.getEnd()
      range.setString('%s'%page_name)
      self.layout.page_element_label(range)
      return cellname, cellname
         
    def fill_name_function(e):
      """Curry a function to fill a cell with the name of a field"""
      name = e.attrib['name']
      return lambda cursor:self._insert_field_name(tbl, cursor, fields[name])
    
    def fill_value_function_field(e):
      """Curry a function to fill a cell with the value of a field"""
      name = e.attrib['name']
      return lambda cursor:self._insert_field_into_text(tbl, cursor, name, fields[name], values[name])
    
    def fill_value_function_group(e):
      """Curry a function to fill a cell with a group"""
      col = int(e.attrib.get('col', '2'))
      return lambda cursor:self._page_element(e, tbl, cursor, fields, values, col*2)

    # determine the number of rows in the page, and the number of columns
    # per row, and for each column the span and a function to fill its content
    rows = [[]]
    
    def append_columns_to_last_row(additional_columns):
        if sum(c[0] for c in (rows[-1] + additional_columns)) > max_columns:
          rows.append([])
        rows[-1].extend(additional_columns)      

    if len(page_name):
      append_columns_to_last_row([(max_columns, page_name, fill_page_name)])
              
    for e in page:
      if e.tag=='newline':
        rows.append([])
      else:
        colspan = max(int(e.attrib.get('colspan', '1')), 1)
        additional_columns = []
        if e.tag=='field':
          name = e.attrib['name']
          nolabel = e.attrib.get('nolabel', '0')
          field = fields[name]
          #for one2many or many2many fields, always put the label on the form
          if nolabel!='1' or field['type']=='one2many' or field['type']=='many2many':
            additional_columns.append((1, name, fill_name_function(e)))
            # for one2many or many2many, put field below label instead of next
            # to it 
            if field['type']=='one2many' or field['type']=='many2many':
              rows.append([])
              append_columns_to_last_row(additional_columns)
              additional_columns = []
              rows.append([])
        if e.tag=='field':
          additional_columns.append( (colspan, values[name], fill_value_function_field(e)) )
        elif e.tag=='group':
          additional_columns.append( (colspan, 'group %s'%e.attrib.get('string', 'noname'), fill_value_function_group(e)) )
        append_columns_to_last_row(additional_columns)
    rows = filter( lambda x:len(x)!=0, rows )

    #create text of the view, for debugging purpose
    for row in rows:
      logger.debug(' | '.join( '%s (span=%s)'%(c[1],c[0]) for c in row ))
          
    #split the cell in this number of rows
    if len(rows)>1:
      logger.debug('split %s in %s vertical'%(tblcsr.getRangeName(), len(rows)-1))
      tblcsr.splitRange(len(rows)-1, True)
    
    bottom_left, bottom_right = tblcsr.getRangeName(),tblcsr.getRangeName() 
    #write the structure into the current cell
    for ri, row in enumerate(rows):
      if len(row)>1:
        logger.debug('split %s in %s horizontal'%(tblcsr.getRangeName(), len(rows)-1))
        tblcsr.splitRange(len(row) - 1, False)
      for i,column in enumerate(row):
        if i==0:
          bottom_left, bottom_right = column[2](tblcsr)
        else:
          not_needed, bottom_right = column[2](tblcsr)
        if i+1<len(row):
          tblcsr = tbl.createCursorByCellName(bottom_right)
          tblcsr.goRight(1, False)
      tblcsr = tbl.createCursorByCellName(bottom_left)
      if ri+1<len(rows):
        tblcsr.goDown(1, False)
        
    return bottom_left, bottom_right

  def insert_form_into_text(self, tbl, tblcsr, object_name, object_id,
      view_id=None):

    """
      insert a form view into a text object
      @param tbl an Open Office text table
      @param tblcsr a cursor in the table
      @param object_name the TinyErp name of the object
      @param object_id id of objects to put in the table
      @view_id the view to use to display the object
      @filter_pages only display certain pages inside a notebook view
    """

    # log each form insertion view its type
    type = "%(object_name)s:%(object_id)s" % locals() 
    log_insert(logger, 'form', type)
    bottom_left, bottom_right = tblcsr.getRangeName(),tblcsr.getRangeName()

    if object_name in self.prefered_views:
      logger.info('load prefered view for %s:%s'%(object_name, self.prefered_views[object_name]))
      view_id = self.prefered_views[object_name]
      
    if view_id != None:
      # search criteria
      s = [('name', '=', view_id), ('model', '=', 'ir.ui.view')] 
      model_data_ids = self.tiny('ir.model.data', 'search', s)

      # query tiny object
      result = self.tiny('ir.model.data', 'read', model_data_ids, ['res_id'])
      view_id = result[0]['res_id']
    else:
      view_id = ''

    # query form
    form = self.tiny(object_name, 'fields_view_get', view_id, 'form', self.context, False )
    tinylayout = ElementTree.XML( form['arch'] )
    fields = form['fields']

    if object_id != False:
      values = self.tiny(object_name, 'read', [object_id], fields.keys(), self.context)[0]
    else:
      values = dict((k, False) for k in fields.keys())      

    def notebook_element(e, tbl, tblcsr):
      log_create(logger, 'notebook')
      bottom_left, bottom_right = tblcsr.getRangeName(),tblcsr.getRangeName()
      #For each page in the notebook, create a row in the table
      nRows = len([c for c in e])
      tblcsr.splitRange(nRows-1, True)
      for c in e:
        bottom_left, bottom_right = self._page_element(c, tbl, tblcsr, fields, values)
        tblcsr = tbl.createCursorByCellName(bottom_left)
        tblcsr.goDown(1, False)
      return bottom_left, bottom_right

    # if first node is "notebook" walk the all page 
    # children nodes, else parse single page node
    if tinylayout[0].tag == 'notebook':
      for c in tinylayout:
        bottom_left, bottom_right = notebook_element(c, tbl, tblcsr)
    else:
      return self._page_element(tinylayout, tbl, tblcsr, fields, values)
    return bottom_left, bottom_right

  def insert_at_bookmarks(self, valuedict):
    bookmarks = self.doc.getBookmarks()
    for k, v in valuedict.items():
      if k in bookmarks.getElementNames():
        kobj = self.doc.getBookmarks().getByName(k)
        kobj.getAnchor().setString( self.decoder('%s'%v) )

  def insert_and_process_at_bookmarks(self, valuedict):
    def ipol(template, *items):
      result = map(process, items)
      if (len(result) == 1) and isinstance(result[0], dict):
        return template % result[0]
      return template % tuple(result)
    def join(glue, items): return glue.join(map(process, items))
    ops = dict(ipol=ipol, join=join)
    def process_tuple(value): return ops[value[0]](*value[1:])
    def process_dict(value): return dict([ (key, process(val)) for key, val in value.items() ])
    def process_str(value): return self.decoder(value) # unicode(value, encoding='utf-8', errors='replace')
    type_handler = { tuple : process_tuple, dict : process_dict, str : process_str }
    def process(value):
      for tp in (tuple, dict, str):
        if isinstance(value, tp):
          return type_handler[tp](value)
      return value
    bookmarks = self.doc.getBookmarks()
    for k, v in valuedict.items():
      if k in bookmarks.getElementNames():
        kobj = self.doc.getBookmarks().getByName(k)
        kobj.getAnchor().setString( process(v) )

  def collect_bookmarks(self):
    bookmarks = self.doc.getBookmarks()
    keys = bookmarks.getElementNames()
    value = lambda k: bookmarks.getByName(k).getAnchor().getString()
    return dict(zip(keys, map(value, keys)))

class t2o_expand_tree(tiny_view_2_oo_writer):
  """Tiny view to oo writer that expands all trees to forms"""
  def insert_tree_into_text(self, tbl, tblcsr, object_name, object_ids, view_id=None):
    return self.insert_forms_into_text(tbl, tblcsr, object_name, object_ids, view_id)
