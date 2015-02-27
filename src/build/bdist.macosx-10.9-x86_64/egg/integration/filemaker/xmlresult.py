import logging

logger = logging.getLogger('integration.xmlresult')

xml_template_header = """
<?xml version="1.0" encoding="UTF-8"?>
<FMPXMLRESULT xmlns="http://www.filemaker.com/fmpxmlresult">
   <ERRORCODE>0</ERRORCODE> 
   <PRODUCT BUILD="5/23/2002" NAME="FileMaker Pro" VERSION="7.0"/>
   <DATABASE DATEFORMAT="MM/dd/yy" LAYOUT="summary" NAME="Employees.fp7" RECORDS="23" TIMEFORMAT="hh:mm:ss"/>
   <METADATA>
%s
   </METADATA>
   <RESULTSET FOUND="2">
"""

xml_template_footer = """
   </RESULTSET>
</FMPXMLRESULT>
"""

meta_template = '<FIELD EMPTYOK="NO" MAXREPEAT="1" NAME="%(name)s" TYPE="%(type)s"/>'
row_template = '<ROW MODID="47" RECORDID="34">\n%(cols)s\n</ROW>'
col_template = '  <COL><DATA>%(field)s</DATA></COL>'
comment_template = '<!-- %(comment)s -->'
commented_col_template = col_template + '  ' + comment_template

def create_xmlresult(attributes, results):
  """generator for strings that form a valid filemaker xml file
  @param attributes a dictionary with as keys the field names to return and as value their type (either 'NUMBER' or 'TEXT')
  @param results a list or a generator of dictionaries with the resulting records.  the keys are the field names, and the values the content of the fields
  """
  
  logger=logging.getLogger('integration.xmlresult.create_xmlresult')  
  keys = attributes.keys()
  keys.sort()
  meta = '\n'.join([ meta_template % dict(name=key,type=attributes[key]) for key in keys ])
  yield (xml_template_header%meta).strip('\n')

  def row_generator():
    for result in results:
      
      def col_generator():
        for key in keys:
          value = unicode(result[key])
          # All the ASCII control code characters are prohibited in XML - of the values below 0x20, only 0x9, 
          # 0xA, and 0xD are allowed (tab, newline, and cr - not necessarily in that order).
          #
          # To make this an XML document you'll need to remove these characters from the data.
          #
          # The better alternative here would be to create a custom code for utf xml files
          value = value.encode('utf-8').replace(chr(0xB),'')
          if '\n' in value or '\r' in value or '<' in value or '>' in value or '&' in value:
            value = value.replace('\n', '\r')
            value = value.replace('\r\r', '\r')
            value = '<![CDATA[%s]]>' % value
          yield commented_col_template % dict(field=value, comment=key) 
        
      yield row_template % {'cols':'\n'.join([c for c in col_generator()])}
      logger.info('rij gegenereerd')
      
  for row in row_generator():
    yield row+'\n'
  
  yield xml_template_footer.strip('\n')
