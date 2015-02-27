import logging
logger = logging.getLogger('integration.tinyerp.tiny2oo.oo_doc_layout')

try:
  from win32com.client.dynamic import Dispatch
  
  # get access to the service manager
  ooService = Dispatch('com.sun.star.ServiceManager')
  
  # get access to the Bridge_GetStruct function which
  # will help us send valid OpenOffice structs to 
  # OpenOffice's UNO functions that require struct
  ooService._FlagAsMethod('Bridge_GetStruct')
  createStruct = lambda str: ooService.Bridge_GetStruct(str)
except:
  logger.error('Could not connect to OpenOffice, not all reports will be available')
  

class oo_doc_layout(object):
  """
    This class is intended to provide styling operations for
    an OO document via OLE [or COM] objects services. WIN32 only.
    Methods in this class are declared static methods
  """

  def _format(self, object, dict=[]):
    """
      Formatting method for characters, paragraphs...
      This method does not work with any kind of object 
      @param service is the name of the object
      @param dict contain property/value pairs [well, I hope]
    """

    for key in dict:
      object.setPropertyValue(key, dict[key])

  def _getline(self, dict = {}):
    """styling for a table cell edge line"""

    line = createStruct('com.sun.star.table.BorderLine')
    # default settings
    line.Color = 0x000000
    line.InnerLineWidth = 0
    line.OuterLineWidth = 1
    line.LineDistance = 0

    if "Color" in dict.keys():
      line.Color = dict['Color']
    if "InnerLineWidth" in dict.keys():
      line.InnerLineWidth = dict['InnerLineWidth']
    if "OuterLineWidth" in dict.keys():
      line.OuterLineWidth = dict['OuterLineWidth']
    if "LineDistance" in dict.keys():
      line.LineDistance = dict['LineDistance']

    return line

  def _getborders(self, dict):
    """set table border line side/line pairs"""

    b = createStruct('com.sun.star.table.TableBorder') 

    for opt in ['Top', 'Bottom', 'Left', 'Right', 
                'Horizontal', 'Vertical', 'Distance']:
      if opt in dict.keys():
        if opt == 'Distance':
          b.__setattr__('Distance', dict[opt])
          b.__setattr__('IsDistanceValid', True)
        else:
          b.__setattr__('%sLine' % opt, dict[opt])
          b.__setattr__('Is%sLineValid' % opt, True)

    return b

  def table_heading(self, doc):
    """layout table heading of an OO writer document"""

    oFamilies = doc.StyleFamilies
    paraStyles = oFamilies.getByName('ParagraphStyles')
    
    tblhdg = paraStyles.getByName('Table Heading')
    
    self._format(tblhdg, {'ParaAdjust': 0, 'CharWeight': 100.00,
                          'CharHeight': 10.0, 'CharFontName':'Arial' })

  def table_content(self, doc):
    """layout table content of an OO writer document"""

    oFamilies = doc.StyleFamilies
    paraStyles = oFamilies.getByName('ParagraphStyles')

    tblcnt = paraStyles.getByName('Table Contents')
    
    self._format(tblcnt, {'ParaAdjust': 0, 'CharWeight': 100.00,
                          'CharHeight': 10.0, 'CharFontName':'Arial' })

  def page_element_label(self, txtrange):
    """layout a page element label"""

    self._format(txtrange, {'CharWeight': 150.0})
    
  def field_element(self, txtrange):
    self._format(txtrange, {'CharPosture':2})

  def tree_element_heading(self, txtrange):
    """layout a tree element heading"""

    #self._format(txtrange, {'CharWeight': 150.0})

  def group_element_heading(self, txtrange):
    """layout a group element heading"""

    self._format(txtrange, {'CharWeight': 150.0})
  
  def align_right(self, txtrange):
    """oo object align right"""

    self._format(txtrange, {'ParaAdjust': 1})

  def center_align(self, txtrange):
    """oo object align right"""

    self._format(txtrange, {'ParaAdjust': 3})

  def boolean_true(self, txtrange):
    """provide ways of displaying a boolean"""

    # unicode for check mark
    txtrange.setString(u'\u2714')

  def boolean_false(self, txtrange):
    """provide ways of displaying a boolean"""
    pass

    # table borders
    #singleline = layout.getline({'InnerLineWidth': 1, 'OuterLinewidth})

    #params = {'Top': singleline, 'Bottom': singleline,
    #          'Left': singleline, 'Right': singleline,
    #          'Horizontal': noline, 'Vertical': noline}

    #bstyling = layout.getborders(params)
    #layout.format(table, {'TableBorder': bstyling})

# short hand :D
layout = oo_doc_layout()

