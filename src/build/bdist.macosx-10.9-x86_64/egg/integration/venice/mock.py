"""Some venice mockup classes to run unittests without having Venice running"""

#
# A list of (desc_file_content, data_file_content) venice imports, to be able to unit test
# the importing
#
_venice_imports_ = []

def get_last_import(index=-1):
    """
    :return: a tuple (desc_file_content, data_file_content) of the last imported file in venice
    """
    return _venice_imports_[index]

_unique_id_ = None

def get_next_unique_id():
    global _unique_id_
    import random
    if _unique_id_ is None:
        # max 32bit signed int with room for increasing it
        _unique_id_ = random.randint( 1, 2**30 - 1)
    _unique_id_ += 1
    return _unique_id_

def set_next_unique_id(next_unique_id):
    global _unique_id_
    _unique_id_ = next_unique_id

class mock_pytime(object):
    
  def __init__(self, dt):
      """:param dt: python datetime object"""
      self.__dt = dt
      
  def __getattr__( self, name ):
      return getattr( self.__dt, name )

  def Format(self, fmt):
      dt = self.__dt
      return "%s/%s/%s %s:%s:%s"%(dt.day, dt.month, dt.year, dt.hour, dt.month, dt.second)
  
class mock_venice_class(object):
  
  def __init__(self, name):
    self.__name = name
    self.__fields = dict()
    self.__prepare = False
    #
    # when used within jinja templates
    #
    self.jinja_allowed_attributes = None
    self.__set_numbers()
    
  def __set_numbers(self, book='MockBook'):
    self.__id = get_next_unique_id()
    self.pNumber = self.__id
    self.pSysNum = self.__id
    self.pDocNum = self.__id
    self.pBook = book
      
  def __getattr__(self, attr):
    if attr.startswith('__'):
      return object.__getattribute__(self, attr)
    if attr in ['GetNext',]:
      return lambda:False
    if 'Date' in attr:
      # assume an attribute of type PyDate was requested
      # http://docs.activestate.com/activepython/2.4/pywin32/PyTime.html
      from datetime import datetime
      now = datetime.now()
      class FakePyDate(datetime):
        
        def Format(self, format):
          return self.strftime(format)
        
      return FakePyDate(now.year, now.month, now.day)
    
    elif attr.startswith('p') or attr.startswith('s'):
      # an attribute was requested, let's assume it was a number
      return 0        
    else:
      return mock_venice_class(attr)
  
  def Init(self, *args):
    self.__set_numbers()
    
  def GetFieldVal(self, field_id):
    if field_id in self.__fields:
      return self.__fields[field_id]
    if field_id in [0, 1]:
      return self.__id
    return 0

  def Import(self, description, data, a, b, c, d):
    import os
    if os.path.exists(description) and os.path.exists(data):
      self.__set_numbers()
      _venice_imports_.append( (open(description).read(), open(data).read()) )
      return True, 1, 'import success'
    return False, 0, 'files not found'
      
  def GetFieldID(self, field_name):
    field_ids = dict(
      Number = 0,
      SysNum = 1,
    )
    return field_ids.get(field_name, 2)
  
  def PrepareDocument( self, prepare ):
      self.__prepare = prepare
      
  def SetFilter(self, filter, *args):
      return False
  
  def GetDetail(self, _index):
#      if not self.__prepare:
#          raise Exception('PrepareDocument must be called first')
      return (True, 
              0, 
              0, 
              0, 
              '1234', 
              'remark', 
              'text', 
              0, 
              'EUR', 
              1 )
      
  def SetFieldVal(self, field_id, value):
    self.__fields[field_id] = value

  def SeekByDocNum(self, eSeekMode, sYear, bsBook, *args):
      self.__set_numbers(bsBook)
      return True

  def GetDBStatus(self):
      return 0

  def __call__(self, *args, **kwargs):
    return mock_venice_class(self.__name+'(%s)'%str(args))
  
  def __repr__(self):
    return 'mock_venice_class(%s)'%(self.__name)

class mock_venice_balan_class(mock_venice_class):
  
  def GetBalance(self, account, period):
    return 0.0

class mock_venice_entry_class(mock_venice_class):
    
    def __init__(self, year):
        super( mock_venice_entry_class, self).__init__( str(year) )
        from datetime import datetime
        # list of fake entries that can be traversed
        self._entries = []
        self._entry_index = 0
        self.__year = year
        self.pAccount = '12345'
        self.pBookDateOrg = mock_pytime(  datetime(2010, 12, 31) )
        self.pBookDate = mock_pytime(  datetime(2010, 12, 31) )
        self.pAmountDosC = 100 
        self.pOpenDosC  = 100
        self.pTickStatus = 2
        self.pDocDateOrg = mock_pytime(  datetime(2010, 12, 31) )
        self.pDocDate = mock_pytime(  datetime(2010, 12, 31) ) 
        self.pDocNumOrg = 5
        self.pDocNum = 1
        self.pBookOrg = 'ORGBOOK'
        self.pBook = 'BOOK'
        self.pRemark = 'a remark way too long to be decently stored if not chopped : the quick brown fox jumps over the lazy dog'
        self.pLineNumOrg = 1
        self.vLineNum = 1
        self.pSysNum = 30
        self.pQuantity = 0
        
    def SetFilter(self, filter, *args):
        """Make sure the returned entries satisfy the requested ones"""
        for op in ['^^', '==']:
            if op in filter:
                _key, value = filter.split(op)
                value = value.replace('"','').strip()
                self.pAccount = value
        if len( self._entries ):
            self._entry_index = 0
            self.GetNext()
            return True
        return False
    
    def GetNext( self ):
        if self._entry_index >= len( self._entries ):
            return False
        for k,v in self._entries[self._entry_index].items():
            if ('Date' in k) and (v != None):
                v = mock_pytime( v )
            setattr( self, k, v )
        self._entry_index += 1
        return True
        
    def GetLastTickInfo(self):
        from datetime import datetime
        return [1, 1, 1, mock_pytime(datetime.now()), 'fons', 100, 100, [1]]
        
class mock_venice_year_context(mock_venice_class):
  
  def __init__(self, dossier, year):
      from datetime import datetime
      super(mock_venice_year_context, self).__init__('YearContext(%s %s)'%(str(dossier), year))
      self.__dossier = dossier
      self.__year = year
      self.vBegin = mock_pytime( datetime(int(year), 1, 1) )
      self.vEnd = mock_pytime( datetime(int(year), 12, 31) )
      self.vCurrency = 'Euro'
      
  def CreateBalan(self, *args, **kwargs):
      return mock_venice_balan_class('Balan(%s)'%str(args))

  def CreateEntry(self, *args, **kwargs):
      return mock_venice_entry_class(self.__year)      

class mock_venice_firm_class(mock_venice_class):
    
    def __init__(self, dossier):
        super(mock_venice_firm_class, self).__init__('venice firm %s'%(dossier.vName))
        self.pVatNum = 'BE 0878.000.000'
        self.pTradeReg = 'BE 0878.000.000'
        self.pName = dossier.vName
        self.pCountryName = 'Belgium'
        self.pCountryCode = 'BE'
        self.pPostalCode = '1000'
        self.pCity = 'Brussel'
        self.pStreet = 'Belliardstraat 3'
        self.pEmail = 'info@testco.be'
        self.pTel1 = '32 587 89 03'
        self.pTel2 = None
        self.pTel3 = None
        self.pTel4 = None
          
class mock_venice_dossier_class(mock_venice_class):
      
  def __init__(self, cabinet, name):
      super(mock_venice_dossier_class, self).__init__('venice dossier %s %s'%(cabinet, name))
      self.vName = name
      self.vDirectory = name
      self.vCurrency = 'Euro'
      self._years = ['2006', '2007', '2008']
      
  def CreateFirm(self, *args, **kwargs):
      return mock_venice_firm_class(self)
  
  def CreateYearContext(self, year, *args, **kwargs):
    return mock_venice_year_context(self, year)
    
  def GetYears(self):
    return self._years
  
  def create_files(self, *args, **kwargs):
    return ('path_to_data_file', 'path_to_desc_file')
  
  def import_files(self, *args, **kwargs):
    unique_number = get_next_unique_id()
    return unique_number, unique_number
  
class mock_venice_com_object(mock_venice_class):
  
  def CreateDossierContext(self, cabinet, name):
    return mock_venice_dossier_class(cabinet, name)

  def GetCabinets(self):
    return [r'/tmp/']

  def GetDossiers(self, cabinet):
    return ['Test1', 'Test2', 'Test3']
