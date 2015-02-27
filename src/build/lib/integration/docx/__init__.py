"""Some code to handle docx files

  References:
  1) http://www.ecma-international.org/publications/standards/Ecma-376.htm
     Part 3 contains the primer
"""

import logging
logger = logging.getLogger('integration.docx')

class DocxManipulator(object):
  """Base docx manipulator class 
  Takes docx file from the input stream, and writes a new one
  to the output stream on which the manipulate function has
  been applied
  """
  
  schema = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
  bookmark_start = '{%s}bookmarkStart'%schema
  bookmark_end = '{%s}bookmarkEnd'%schema
  
  def manipulate(self, document):
    """Manipulate the xml tree from the document
    @param document: the root element from the document
    @type documet: an elementtree element"""
    raise NotImplemented()  
  
  def find_bookmark(self, element, bookmark):
    """Find the element that references the bookmark and return the element and
    the position of the bookmark start on this element,
    return (None,0), if no such bookmark found"""
    for i,child in enumerate(element.getchildren()):
      if child.tag==self.bookmark_start:
        name = child.attrib['{%s}name'%self.schema]
        if name==bookmark:
          return element, i
      else:
        found, position = self.find_bookmark(child, bookmark)
        if found:
          return found, position
    return None, 0
            
  def find_and_replace_bookmarks(self, element, bookmarks):
    """Find all bookmarks within an element, and replace them
    @param element: an ElementTree element
    @param bookmarks: a dictionay with as key the name of the bookmark and
    as value a string specifying the new content between the start and end
    bookmark tags.  every newline in the string will be replaced with a break.
    """ 
    from xml.etree import ElementTree
    childs_to_remove = []
    for i,child in enumerate( element ):
      if child.tag==self.bookmark_start:
        name = child.attrib['{%s}name'%self.schema]
        try:
          value = bookmarks[name]
          if element.tag=='{%s}p'%self.schema:
# This breaks rappel brieven
#            # remove the content of the paragraph until the end of the bookmark
#            for k in range(i+1,len(element)):
#              element_after_bookmark = element[k]
#              if element_after_bookmark.tag!=self.bookmark_end:
#                childs_to_remove.append(element_after_bookmark)
#              else:
#                continue
            r = ElementTree.Element('{%s}r'%self.schema)
            element.insert(i+1, r)
            lines = unicode(value).split('\n')
            for j,text in enumerate(lines):
              t = ElementTree.SubElement(r, '{%s}t'%self.schema)
              t.text = text
              if j<len(lines)-1:
                ElementTree.SubElement(r, '{%s}br'%self.schema)
          else:
            logger.warn('Could not replace bookmark %s : dont know how to handle tag %s'%(name, element.tag))
        except KeyError,e:
          pass            
      else:
        self.find_and_replace_bookmarks(child, bookmarks)
#    for child in childs_to_remove:
#      if child in element:
#        element.remove(child)
    
  def __call__(self, input_stream, output_stream):
    import zipfile  
    input_zip = zipfile.ZipFile(input_stream, 'r', zipfile.ZIP_DEFLATED)
    output_zip = zipfile.ZipFile(output_stream, 'w')
    for path in input_zip.namelist():
      if path=='word/document.xml':
        from xml.etree import ElementTree
        document = ElementTree.fromstring(input_zip.read(path))
        self.manipulate(document)
        output_zip.writestr(path, ElementTree.tostring(document, 'utf-8'))
      else:  
        output_zip.writestr(path, input_zip.read(path))
    output_zip.close()
    input_zip.close() 
  
class DocxBookmarkReplacer(DocxManipulator):
  """Takes docx file from the input stream, and writes a new one
  to the output stream where the bookmarks have been replaced
  with the values of the bookmarks dictionary.
  
  the values of the bookmarks dictionary are expected to be unicode
  objects.
  """
    
  def __init__(self, bookmarks={}):
    super(DocxBookmarkReplacer, self).__init__()
    self.bookmarks = bookmarks
    
  def manipulate(self, document):
    self.find_and_replace_bookmarks(document, self.bookmarks)
    
def replace_bookmarks(input_stream, output_stream, bookmarks={}):
  """Convenience function as a shorthand for the DocxBookmarkReplacer"""
  manipulator = DocxBookmarkReplacer(bookmarks)
  return manipulator(input_stream, output_stream)
  
  
