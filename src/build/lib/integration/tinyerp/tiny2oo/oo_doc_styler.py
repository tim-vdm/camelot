
import sys

if sys.platform == 'win32':
  from win32com.client.dynamic import Dispatch

  # get access to the service manager
  ooService = Dispatch('com.sun.star.ServiceManager')

  # get access to the Bridge_GetStruct function which
  # will help us send valid OpenOffice structs to 
  # OpenOffice's UNO functions that require struct
  ooService._FlagAsMethod('Bridge_GetStruct')
  createStruct = lambda str: ooService.Bridge_GetStruct(str)  

class oo_doc_styler(object):
    """This class is intended to provide styling operations for
    an OO document via OLE [or COM] objects services. WIN32 only.
    Methods in this class are declared static methods"""
    
    @staticmethod    
    def format(object, dict=[]):
        """Automatic formatting method for characters, paragraphs...
        This method does not work with any kind of object 
        @param service is the name of the object
        @param dict contain property/value pairs [well, I hope]"""
        
        for key in dict:
            object.setPropertyValue(key, dict[key])

    @staticmethod
    def getline(dict = {}):
        """styling for a table cell edge line"""

        line = createStruct('com.sun.star.table.BorderLine')
        # default settings
        # http://api.openoffice.org/docs/common/ref/com...
        # .../sun/star/table/BorderLine.html
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
 
    @staticmethod
    def getborders(dict):
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
      


        

