# -*- coding: utf-8 -*-

"""
http://www.ecma-international.org/news/TC45_current_work/TC45_available_docs.htm
"""

import logging
import base

logger = logging.getLogger('spreadsheet compose xlsx')

class XlsxSpreadsheet(base.Spreadsheet):
  def __init__(self):
    super(XlsxSpreadsheet, self).__init__()
    self._column_width = {}
    self._row_height = {}
    self._orientation = 'portrait'
  def group(self, range_spec):
    #@todo: store and display grouping information
    pass
  def insert_row(self, range_spec):
    #@todo: shift all other cells down
    pass
  def show_outline(self, **kw):
    #@todo: store and display outline level
    pass
  def set_column_width(self, range_spec, width):
    pass
  def set_row_height(self, range_spec, height):
    pass
  def set_orientation(self, orientation='portrait'):
    pass
  def named_range_coord(self, name):
    pass
    #return self._cell_named_range_coord(name)
  def finalize(self):
    pass
  def _cell_render(self, cell):
    pass
  def set_column_width(self, range_spec, width):
    for cell in range_spec.generate_cells(self):
      self._column_width[cell.col] = width
  def set_row_height(self, range_spec, height):
    for cell in range_spec.generate_cells(self):
      self._row_height[cell.row] = height
  def named_range_coord(self, name):
    pass
#    return self._cell_named_range_coord(name)
  def set_orientation(self, orientation='portrait'):
    self._orientation = orientation
  def generate_xlsx(self):
    """Generator function that returns xlsx data"""
    import cStringIO
    import zipfile
    import datetime
    import decimal
    from pkg_resources import resource_string
    template_files = ['[Content_Types].xml',
                      '_rels/.rels',
                      'docProps/core.xml',
                      'docProps/app.xml',
                      'xl/printerSettings/printerSettings1.bin',
                      'xl/theme/theme1.xml',
                      ]
    output = cStringIO.StringIO()
    zip = zipfile.ZipFile(output, 'w')
    for filename in template_files:
      zip.writestr(filename, resource_string(__name__, 'templates/xlsx/' + filename))
      
    class unique_objects(object):
      
      def __init__(self):
        self.objects = {}
        self.count = 0
        
      def checkout(self, o):
        self.count += 1
        try:
          return self.objects[o]
        except KeyError:
          i = len(self.objects)
          self.objects[o] = i
          return i
        
      @property
      def uniqueCount(self):
        return len(self.objects)
      
      def ordered_list(self):
        ordered = [''] * self.uniqueCount
        for o,i in self.objects.items():
          ordered[i] = o
        return ordered

    begin_of_times = datetime.date(year=1899, month=12, day=30)
    shared_strings = unique_objects()
    number_formats = unique_objects()
    master_formatting = unique_objects() 
    
    def to_utf8(generator):
      for line in generator:
        yield line.encode('utf-8', 'ignore')
        
    def generate_sheet_xml_rels():
      yield u"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/printerSettings" Target="../printerSettings/printerSettings1.bin"/>
                </Relationships>"""
                      
    def generate_workbook_xml(worksheets):
      yield """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <workbook
                  xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                  <fileVersion appName="xl" lastEdited="4" lowestEdited="4" rupBuild="4506" />
                  <workbookPr defaultThemeVersion="124226" />
                  <bookViews>
                    <workbookView xWindow="480" yWindow="375" windowWidth="24615" windowHeight="11970" />
                  </bookViews>
                  <sheets>"""                  
      for i,name in enumerate(worksheets):
        yield """<sheet name="%s" sheetId="%i" r:id="rId%i"/>"""%(name, i+1, i+5)
      yield """
                  </sheets>
                  <definedNames>
                    <definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">
                      Sheet1!$A$1:$M$5931
                    </definedName>
                  </definedNames>
                  <calcPr calcId="0" calcMode="auto" iterate="1"/>
                </workbook>"""
                 
    def generate_workbook_xml_rels(worksheets):
      yield u"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"""
      yield u"""<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                   <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
                   <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>                   
                   <!-- <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/calcChain" Target="calcChain.xml"/> -->
                   <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>"""
      for i in range(len(worksheets)):
        yield """  <Relationship Id="rId%i" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%i.xml"/>"""%(i+5, i+1)
      yield """</Relationships>"""
                
    def generate_shared_strings():
      yield u"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n"""
      yield u"""<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="%i" uniqueCount="%i">"""%(shared_strings.count, shared_strings.uniqueCount)
      for o in shared_strings.ordered_list():
        # use CDATA because of < > & characters which might be into strings, alternative would be to
        # detect those and replase them with something urlencoded
        yield u"  <si><t><![CDATA[%s]]></t></si>\n"%o
      yield u"""</sst>"""
      
    NUMFMT_OFFSET = 165
    CELLXFS_OFFSET = 6
    
    def generate_styles_xml():
      yield u"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <styleSheet
                  xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                  <numFmts count="%i">
                    <numFmt numFmtId="164" formatCode="d/mm/yyyy;@" />
              """%(1+number_formats.uniqueCount)
      for i,o in enumerate(number_formats.ordered_list()):
        yield u'   <numFmt numFmtId="%i" formatCode="%s" />'%(NUMFMT_OFFSET+i, o)
      yield u""" </numFmts>
                
                  <fonts count="18">
                    <font>
                      <sz val="11" />
                      <color theme="1" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <sz val="11" />
                      <color theme="1" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <b />
                      <sz val="18" />
                      <color theme="3" />
                      <name val="Cambria" />
                      <family val="2" />
                      <scheme val="major" />
                    </font>
                    <font>
                      <b />
                      <sz val="15" />
                      <color theme="3" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <b />
                      <sz val="13" />
                      <color theme="3" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <b />
                      <sz val="11" />
                      <color theme="3" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <sz val="11" />
                      <color rgb="FF006100" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <sz val="11" />
                      <color rgb="FF9C0006" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <sz val="11" />
                      <color rgb="FF9C6500" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <sz val="11" />
                      <color rgb="FF3F3F76" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <b />
                      <sz val="11" />
                      <color rgb="FF3F3F3F" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <b />
                      <sz val="11" />
                      <color rgb="FFFA7D00" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <sz val="11" />
                      <color rgb="FFFA7D00" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <b />
                      <sz val="11" />
                      <color theme="0" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <sz val="11" />
                      <color rgb="FFFF0000" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <i />
                      <sz val="11" />
                      <color rgb="FF7F7F7F" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <b />
                      <sz val="11" />
                      <color theme="1" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                    <font>
                      <sz val="11" />
                      <color theme="0" />
                      <name val="Calibri" />
                      <family val="2" />
                      <scheme val="minor" />
                    </font>
                  </fonts>
                  <fills count="33">
                    <fill>
                      <patternFill patternType="none" />
                    </fill>
                    <fill>
                      <patternFill patternType="gray125" />
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor rgb="FFC6EFCE" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor rgb="FFFFC7CE" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor rgb="FFFFEB9C" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor rgb="FFFFCC99" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor rgb="FFF2F2F2" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor rgb="FFA5A5A5" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor rgb="FFFFFFCC" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="4" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="4" tint="0.79998168889431442" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="4" tint="0.59999389629810485" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="4" tint="0.39997558519241921" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="5" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="5" tint="0.79998168889431442" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="5" tint="0.59999389629810485" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="5" tint="0.39997558519241921" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="6" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="6" tint="0.79998168889431442" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="6" tint="0.59999389629810485" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="6" tint="0.39997558519241921" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="7" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="7" tint="0.79998168889431442" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="7" tint="0.59999389629810485" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="7" tint="0.39997558519241921" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="8" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="8" tint="0.79998168889431442" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="8" tint="0.59999389629810485" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="8" tint="0.39997558519241921" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="9" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="9" tint="0.79998168889431442" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="9" tint="0.59999389629810485" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                    <fill>
                      <patternFill patternType="solid">
                        <fgColor theme="9" tint="0.39997558519241921" />
                        <bgColor indexed="65" />
                      </patternFill>
                    </fill>
                  </fills>
                  <borders count="10">
                    <border>
                      <left />
                      <right />
                      <top />
                      <bottom />
                      <diagonal />
                    </border>
                    <border>
                      <left />
                      <right />
                      <top />
                      <bottom style="thick">
                        <color theme="4" />
                      </bottom>
                      <diagonal />
                    </border>
                    <border>
                      <left />
                      <right />
                      <top />
                      <bottom style="thick">
                        <color theme="4" tint="0.499984740745262" />
                      </bottom>
                      <diagonal />
                    </border>
                    <border>
                      <left />
                      <right />
                      <top />
                      <bottom style="medium">
                        <color theme="4" tint="0.39997558519241921" />
                      </bottom>
                      <diagonal />
                    </border>
                    <border>
                      <left style="thin">
                        <color rgb="FF7F7F7F" />
                      </left>
                      <right style="thin">
                        <color rgb="FF7F7F7F" />
                      </right>
                      <top style="thin">
                        <color rgb="FF7F7F7F" />
                      </top>
                      <bottom style="thin">
                        <color rgb="FF7F7F7F" />
                      </bottom>
                      <diagonal />
                    </border>
                    <border>
                      <left style="thin">
                        <color rgb="FF3F3F3F" />
                      </left>
                      <right style="thin">
                        <color rgb="FF3F3F3F" />
                      </right>
                      <top style="thin">
                        <color rgb="FF3F3F3F" />
                      </top>
                      <bottom style="thin">
                        <color rgb="FF3F3F3F" />
                      </bottom>
                      <diagonal />
                    </border>
                    <border>
                      <left />
                      <right />
                      <top />
                      <bottom style="double">
                        <color rgb="FFFF8001" />
                      </bottom>
                      <diagonal />
                    </border>
                    <border>
                      <left style="double">
                        <color rgb="FF3F3F3F" />
                      </left>
                      <right style="double">
                        <color rgb="FF3F3F3F" />
                      </right>
                      <top style="double">
                        <color rgb="FF3F3F3F" />
                      </top>
                      <bottom style="double">
                        <color rgb="FF3F3F3F" />
                      </bottom>
                      <diagonal />
                    </border>
                    <border>
                      <left style="thin">
                        <color rgb="FFB2B2B2" />
                      </left>
                      <right style="thin">
                        <color rgb="FFB2B2B2" />
                      </right>
                      <top style="thin">
                        <color rgb="FFB2B2B2" />
                      </top>
                      <bottom style="thin">
                        <color rgb="FFB2B2B2" />
                      </bottom>
                      <diagonal />
                    </border>
                    <border>
                      <left />
                      <right />
                      <top style="thin">
                        <color theme="4" />
                      </top>
                      <bottom style="double">
                        <color theme="4" />
                      </bottom>
                      <diagonal />
                    </border>
                  </borders>
                  <cellStyleXfs count="42">
                    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" />
                    <xf numFmtId="0" fontId="2" fillId="0" borderId="0"
                      applyNumberFormat="0" applyFill="0" applyBorder="0"
                      applyAlignment="0" applyProtection="0" />
                    <xf numFmtId="0" fontId="3" fillId="0" borderId="1"
                      applyNumberFormat="0" applyFill="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="4" fillId="0" borderId="2"
                      applyNumberFormat="0" applyFill="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="5" fillId="0" borderId="3"
                      applyNumberFormat="0" applyFill="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="5" fillId="0" borderId="0"
                      applyNumberFormat="0" applyFill="0" applyBorder="0"
                      applyAlignment="0" applyProtection="0" />
                    <xf numFmtId="0" fontId="6" fillId="2" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="7" fillId="3" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="8" fillId="4" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="9" fillId="5" borderId="4"
                      applyNumberFormat="0" applyAlignment="0" applyProtection="0" />
                    <xf numFmtId="0" fontId="10" fillId="6" borderId="5"
                      applyNumberFormat="0" applyAlignment="0" applyProtection="0" />
                    <xf numFmtId="0" fontId="11" fillId="6" borderId="4"
                      applyNumberFormat="0" applyAlignment="0" applyProtection="0" />
                    <xf numFmtId="0" fontId="12" fillId="0" borderId="6"
                      applyNumberFormat="0" applyFill="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="13" fillId="7" borderId="7"
                      applyNumberFormat="0" applyAlignment="0" applyProtection="0" />
                    <xf numFmtId="0" fontId="14" fillId="0" borderId="0"
                      applyNumberFormat="0" applyFill="0" applyBorder="0"
                      applyAlignment="0" applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="8" borderId="8"
                      applyNumberFormat="0" applyFont="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="15" fillId="0" borderId="0"
                      applyNumberFormat="0" applyFill="0" applyBorder="0"
                      applyAlignment="0" applyProtection="0" />
                    <xf numFmtId="0" fontId="16" fillId="0" borderId="9"
                      applyNumberFormat="0" applyFill="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="9" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="10" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="11" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="12" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="13" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="14" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="15" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="16" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="17" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="18" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="19" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="20" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="21" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="22" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="23" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="24" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="25" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="26" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="27" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="28" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="29" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="30" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="1" fillId="31" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                    <xf numFmtId="0" fontId="17" fillId="32" borderId="0"
                      applyNumberFormat="0" applyBorder="0" applyAlignment="0"
                      applyProtection="0" />
                  </cellStyleXfs>
                  <cellXfs count="%i">
                    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" />
                    <xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0"
                      applyNumberFormat="1" />
                    <xf numFmtId="1" fontId="0" fillId="0" borderId="0" xfId="0"
                      applyNumberFormat="1" />
                    <xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0"
                      applyNumberFormat="1" />
                    <xf numFmtId="10" fontId="0" fillId="0" borderId="0" xfId="0"
                      applyNumberFormat="1" />
                    <xf numFmtId="9" fontId="0" fillId="0" borderId="0" xfId="0"
                      applyNumberFormat="1" />"""%(master_formatting.uniqueCount+CELLXFS_OFFSET)
                      
      for i,o in enumerate(master_formatting.ordered_list()):
        yield u'   <xf numFmtId="%i" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'%(o+NUMFMT_OFFSET)                  
      yield u""" </cellXfs>
                  <cellStyles count="42">
                    <cellStyle name="20% - Accent1" xfId="19" builtinId="30"
                      customBuiltin="1" />
                    <cellStyle name="20% - Accent2" xfId="23" builtinId="34"
                      customBuiltin="1" />
                    <cellStyle name="20% - Accent3" xfId="27" builtinId="38"
                      customBuiltin="1" />
                    <cellStyle name="20% - Accent4" xfId="31" builtinId="42"
                      customBuiltin="1" />
                    <cellStyle name="20% - Accent5" xfId="35" builtinId="46"
                      customBuiltin="1" />
                    <cellStyle name="20% - Accent6" xfId="39" builtinId="50"
                      customBuiltin="1" />
                    <cellStyle name="40% - Accent1" xfId="20" builtinId="31"
                      customBuiltin="1" />
                    <cellStyle name="40% - Accent2" xfId="24" builtinId="35"
                      customBuiltin="1" />
                    <cellStyle name="40% - Accent3" xfId="28" builtinId="39"
                      customBuiltin="1" />
                    <cellStyle name="40% - Accent4" xfId="32" builtinId="43"
                      customBuiltin="1" />
                    <cellStyle name="40% - Accent5" xfId="36" builtinId="47"
                      customBuiltin="1" />
                    <cellStyle name="40% - Accent6" xfId="40" builtinId="51"
                      customBuiltin="1" />
                    <cellStyle name="60% - Accent1" xfId="21" builtinId="32"
                      customBuiltin="1" />
                    <cellStyle name="60% - Accent2" xfId="25" builtinId="36"
                      customBuiltin="1" />
                    <cellStyle name="60% - Accent3" xfId="29" builtinId="40"
                      customBuiltin="1" />
                    <cellStyle name="60% - Accent4" xfId="33" builtinId="44"
                      customBuiltin="1" />
                    <cellStyle name="60% - Accent5" xfId="37" builtinId="48"
                      customBuiltin="1" />
                    <cellStyle name="60% - Accent6" xfId="41" builtinId="52"
                      customBuiltin="1" />
                    <cellStyle name="Accent1" xfId="18" builtinId="29"
                      customBuiltin="1" />
                    <cellStyle name="Accent2" xfId="22" builtinId="33"
                      customBuiltin="1" />
                    <cellStyle name="Accent3" xfId="26" builtinId="37"
                      customBuiltin="1" />
                    <cellStyle name="Accent4" xfId="30" builtinId="41"
                      customBuiltin="1" />
                    <cellStyle name="Accent5" xfId="34" builtinId="45"
                      customBuiltin="1" />
                    <cellStyle name="Accent6" xfId="38" builtinId="49"
                      customBuiltin="1" />
                    <cellStyle name="Bad" xfId="7" builtinId="27" customBuiltin="1" />
                    <cellStyle name="Calculation" xfId="11" builtinId="22"
                      customBuiltin="1" />
                    <cellStyle name="Check Cell" xfId="13" builtinId="23"
                      customBuiltin="1" />
                    <cellStyle name="Explanatory Text" xfId="16" builtinId="53"
                      customBuiltin="1" />
                    <cellStyle name="Good" xfId="6" builtinId="26"
                      customBuiltin="1" />
                    <cellStyle name="Heading 1" xfId="2" builtinId="16"
                      customBuiltin="1" />
                    <cellStyle name="Heading 2" xfId="3" builtinId="17"
                      customBuiltin="1" />
                    <cellStyle name="Heading 3" xfId="4" builtinId="18"
                      customBuiltin="1" />
                    <cellStyle name="Heading 4" xfId="5" builtinId="19"
                      customBuiltin="1" />
                    <cellStyle name="Input" xfId="9" builtinId="20"
                      customBuiltin="1" />
                    <cellStyle name="Linked Cell" xfId="12" builtinId="24"
                      customBuiltin="1" />
                    <cellStyle name="Neutral" xfId="8" builtinId="28"
                      customBuiltin="1" />
                    <cellStyle name="Normal" xfId="0" builtinId="0" />
                    <cellStyle name="Note" xfId="15" builtinId="10"
                      customBuiltin="1" />
                    <cellStyle name="Output" xfId="10" builtinId="21"
                      customBuiltin="1" />
                    <cellStyle name="Title" xfId="1" builtinId="15"
                      customBuiltin="1" />
                    <cellStyle name="Total" xfId="17" builtinId="25"
                      customBuiltin="1" />
                    <cellStyle name="Warning Text" xfId="14" builtinId="11"
                      customBuiltin="1" />
                  </cellStyles>
                  <dxfs count="0" />
                  <tableStyles count="0" defaultTableStyle="TableStyleMedium9"
                    defaultPivotStyle="PivotStyleLight16" />
                </styleSheet>"""
      
    def generate_worksheet(worksheet_name, rendered_cells):
      rows = rendered_cells.keys()
      max_col = max( max(base.column_index(key) for key in row_dict.keys()) for row_dict in rendered_cells.values() )
      yield """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
               <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                 <dimension ref="A1:M5935"/>
                 <sheetViews>
                   <sheetView tabSelected="1" workbookViewId="0">
                     <selection activeCell="I5933" sqref="I5933"/>
                   </sheetView>
                 </sheetViews>
                 <sheetFormatPr defaultRowHeight="15"/>
                 <cols>
                 """
      for col in range(1, max_col + 2):
        colname = base.column_name(col-1)
        yield """    <col min="%i" max="%i" width="%s" customWidth="1"/>\n"""%(col, col, self._column_width.get(colname, 25))
      yield """  </cols>
                 <sheetData>
                 """
      for row in range(min(rows),max(rows)+1):
        if row in rendered_cells:
          row_dict = rendered_cells[row]
          cols = row_dict.keys()
          cols.sort()
          if row in self._row_height:
            yield """ <row ht="%s" r="%i" spans="%i:%i">\n"""%(self._row_height[row], row, 1, max_col)
          else:
            yield """ <row r="%i" spans="%i:%i">\n"""%(row, 1, max_col)
          for col in range(0, max_col+1):
            colname = base.column_name(col)
            if colname in row_dict:
              yield """  <c r="%s%i" """%(colname, row)
              cell = row_dict[colname]
              value = cell.value
              if cell.format:
                format_id = number_formats.checkout(cell.format)
                master_formatting_id = master_formatting.checkout(format_id)
              if isinstance(value, int):
                if cell.format:
                  yield 's="%i"'%(CELLXFS_OFFSET+master_formatting_id)
                yield ">\n"
                yield """    <v>%i</v>"""%value
              elif isinstance(value, float):
                if cell.format:
                  yield 's="%i"'%(CELLXFS_OFFSET+master_formatting_id)                
                yield ">\n"
                yield """    <v>%f</v>"""%value
              elif isinstance(value, (decimal.Decimal, long)):
                if cell.format:
                  yield 's="%i"'%(CELLXFS_OFFSET+master_formatting_id)                
                yield ">\n"
                yield """    <v>%s</v>"""%str(value)                
              elif isinstance(value, str) or isinstance(value, unicode):
                yield """t="s">\n"""
                yield """    <v>%i</v>"""%(shared_strings.checkout(value))
              elif isinstance(value, datetime.date):
                yield """s="1">\n"""
                # a datetime is a date instance as well
                # s="7" indicates that the 7th (zero-based) <xf> definition of <cellXfs>
                yield """    <v>%i</v>"""%((datetime.date(value.year, value.month, value.day)-begin_of_times).days)
              elif isinstance(value, base.Expression):
                if cell.format:
                  yield 's="%i"'%(CELLXFS_OFFSET+master_formatting_id)                
                yield ">\n"
                yield """    <f>%s</f>"""%(unicode(value).replace(';', ','))  
              elif value == None:
                yield ">\n"
              else:
                logger.warn('unhandled type in cell %s%s : %s'%(colname, row, type(value)))
                yield ">\n"
                yield """    <v>0</v>"""
              yield """\n  </c>\n"""
          yield """ </row>\n"""

      yield """  </sheetData>
                 <pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
                 <pageSetup paperSize="9" orientation="%s" r:id="rId1"/>
               </worksheet>
               """%(self._orientation)
               
    zip.writestr('xl/workbook.xml', ''.join(list(generate_workbook_xml(self._worksheets))))
    zip.writestr('xl/_rels/workbook.xml.rels', ''.join(list(generate_workbook_xml_rels(self._worksheets))))
    for i,worksheet_name in enumerate(self._worksheets):
      zip.writestr('xl/worksheets/sheet%i.xml'%(i+1), ''.join(list(generate_worksheet(worksheet_name, self._rendered_worksheets[worksheet_name]))))
      zip.writestr('xl/worksheets/_rels/sheet%i.xml.rels'%(i+1), ''.join(list(generate_sheet_xml_rels())))
    zip.writestr('xl/sharedStrings.xml', ''.join(list(to_utf8(generate_shared_strings()))))
    
    zip.writestr('xl/styles.xml', ''.join(list(generate_styles_xml())))

    zip.close()
    return output.getvalue()