
import tempfile
import logging
import os
import sys

if sys.platform == 'win32':
  from win32com.client.dynamic import Dispatch
  import pythoncom

logger = logging.getLogger('integration.oo_report')
logger.setLevel(logging.DEBUG)

#
# http://puno.ayun.web.id/2009/08/php-ooo-in-microsoft-windows-environment/
#
# to activate uno on windows, modify the env vars to :
#
#>c:\Program Files\OpenOffice.org 3\program\python.exe       #2 - Open the OO version of python.
#>>>import os
#>>>print(os.environ['URE_BOOTSTRAP'])                              #3
#vnd.sun.star.pathname:c:\Program Files\OpenOffice.org 3\program\fundamental.ini
#>>>print(os.environ['UNO_PATH'])                                       #4
#c:\Program Files\OpenOffice.org 3\program\
#>>>print(os.environ['PATH'])                                               #5
#c:\Program Files\OpenOffice.org 3\\URE\bin;c:\Program Files\OpenOffice.org 3\Basis\program;C:\WINDOWS\system32;C:\WINDOWS;C:\WINDOWS\System32\Wbem
    
class oo_template_doc(object):
  """Open an open office document as a template, ready to be modified and saved
  to another file format.  One should call the 'load' function before the .doc
  attribute becomes available
  """
  
  extensions = {
    'pdf':'writer_pdf_Export',
    'xls':'MS Excel 97',
    'doc':'MS Word 97'
  }
  
  def __init__(self, filename, hidden=True):
    """@param filename the name of the file to open as a template
    """
    import sys
    if 'win' in sys.platform:
      # we're on winblows, try the com way to access oo
      pythoncom.CoInitialize()
      logger.debug('get oo service manager')
      self.ooService = Dispatch('com.sun.star.ServiceManager')
      logger.debug('got oo service manager')
      self.ooService._FlagAsMethod('Bridge_GetStruct')
      self.ooDesk = self.ooService.createInstance('com.sun.star.frame.Desktop')
    else:
      # use the uno bridge, oo should be running for this to work
      # soffice -headless -nofirststartwizard "-accept=socket,host=localhost,port=2002;urp;"
      import uno
      # get the uno component context from the PyUNO runtime
      localContext = uno.getComponentContext()
      # create the UnoUrlResolver
      resolver = localContext.ServiceManager.createInstanceWithContext(
              "com.sun.star.bridge.UnoUrlResolver", localContext )
      # connect to the running office
      ctx = resolver.resolve( "uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext" )
      self.ooService = ctx.ServiceManager
      # get the central desktop object
      self.ooDesk = self.ooService.createInstanceWithContext( "com.sun.star.frame.Desktop",ctx)
    self._filename = filename
    self.doc = None
    self._hidden = hidden
    logger.debug('created desktop instance')
  def create_struct(self, strTypeName):
    import sys
    if 'win' in sys.platform:
      return self.ooService.Bridge_GetStruct(strTypeName)
    else:
      import uno
      return uno.createUnoStruct(strTypeName)
  def load(self, language=None):
    """Load the oo document in a specified language, after calling this method, the self.doc
    attribute will be available.
    
    If the language attribute is given, the filename used to initialize will be modified to
    contain the language, so if language = 'fr' : my_template.odt becomes my_template_fr.odt
    """
    if self._hidden:
      openProperty = self.create_struct("com.sun.star.beans.PropertyValue")
      openProperty.Name = 'Hidden'
      openProperty.Value = True
      properties = (openProperty,)
    else:
      properties = tuple()
    if language:
      #Do magic to put the language into the filename
      filename = '.'.join(self._filename.split('.')[:-1]) + '_%s.'%language + self._filename.split('.')[-1]
    else:
      filename = self._filename
    empty_path = filename.replace('\\','/')
    logger.debug('use %s as a starting document '%empty_path)
    self.doc = self.ooDesk.loadComponentFromURL('file:///%s'%empty_path, '_blank', 0, properties)
    # Save document as tempfile, in case the file was readonly, and to prevent
    # mess up of original file
    self._temp = self.saveAs()
  def saveAs(self, name=None, extension=None, storeAs=True):
    """Save the document as another file and/or file type, and return the name of the 
    saved file.  If None is passed as value for name, a temporary file is created.
    
    If storeAs is False, only a copy is saved to the filename, the document itslef remains
    at its original location.
    """
    if not name:
      (handle, name) = tempfile.mkstemp('.%s'%extension, 'oo_template_')
      os.close(handle)
    ooname = name.replace('\\','/')
    logger.debug('store oo template as : %s'%ooname)
    if extension:
      saveProperty = self.create_struct('com.sun.star.beans.PropertyValue')
      saveProperty.Name = 'FilterName'
      saveProperty.Value = self.extensions[extension]
      properties = (saveProperty,)
    else:
      properties = tuple()
    if storeAs:
      self.doc.storeAsURL('file:///%s'%ooname, properties)
    else:
      self.doc.storeToURL('file:///%s'%ooname, properties)
    return name
  def readContent(self, extension):
    """Get the content of the file as a binary stream, ready to send to the client side,
    @param extension the file format of the stream
    @return (content, extension)
    """
    name = self.saveAs(None, extension, False)
    file = open(name,'rb')
    content = file.read()
    file.close()
    os.remove(name)
    return (content, extension)  
  def __del__(self):
    if 'win' in sys.platform:
      self.doc.Close(False)
      pythoncom.CoUninitialize()
    os.remove(self._temp)
