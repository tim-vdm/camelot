import os
import sys
import logging
import tempfile
from datetime import *
from decimal import *

logger = logging.getLogger('venice')
logger.debug('venice module is loaded')

if sys.platform.startswith( 'win' ):
    import pywintypes
else:
    
    class pywintypes( object ):
        
        @classmethod
        def Time( cls, time_struct ):
            return time_struct
        
class VeniceException(Exception):
    pass

class VeniceConnectException(VeniceException):
    """Exception thrown when no connection could be made with Venice"""
    pass

def create_import_files(desc_header, desc_line, data_header, data_line, dict_header, dicts_line):
  """Creeer import bestanden voor venice
  @param desc_header template voor de header van het beschrijvingsbestand
  @param desc_line template voor de lijnen van het beschrijvingsbestand
  @param data_header template voor header data bestand
  @param data_line template voor lijnen van het data bestand
  @param dict_header dictionary met velden voor data_header template
  @param dict_line lijst met dictionary met velden voor data_line template
  De velden in de desc templates hebben de naam van de velden in de data template, maar met
  _length er achteraan geplakt
  @return tuple met (naam data bestand, naam beschrijvingsbestand)
  """
  (invoice_data, name_data) = tempfile.mkstemp('.data', 'venice-import-', text=True)
  (invoice_desc, name_desc) = tempfile.mkstemp('.cli', 'venice-import-', text=True)
  invoice_data = os.fdopen(invoice_data, 'w')
  invoice_desc = os.fdopen(invoice_desc, 'w')
  
  #transformeer alles naar ascii
  for k,v in dict_header.items():
    if isinstance(v, unicode):
      dict_header[k] = v.encode('ascii', 'ignore')
      
  #maak header
  dict_header_length = dict( ('%s_length'%k,len(str(v))) for k,v in dict_header.items() )
  invoice_desc.write(str(desc_header)%dict_header_length)
  invoice_data.write(str(data_header)%dict_header)
  
  #filter lege velden uit lijnen en vervang ze door ''
  for dict_line in dicts_line:
    dict_line.update( dict((k,'') for k,v in dict_line.items() if v==None ) )
            
  #maak lijnen
  #bepaal maximimum lengte van de verschillende velden
  dict_line_length = dict( ('%s_length'%k, max(len(str(d[k])) for d in dicts_line ) ) for k in dicts_line[0].keys())
  invoice_desc.write(desc_line%dict_line_length)
  for dict_line in dicts_line:
    dict_line_ljust = dict( (k,str(v).ljust(dict_line_length['%s_length'%k])) for k,v in dict_line.items() )
    invoice_data.write(data_line%dict_line_ljust)
  
  invoice_desc.close()
  invoice_data.close()
  logger.debug('data in %s'%name_data)
  logger.debug('beschrijving in %s'%name_desc)
  return (name_data, name_desc)
  
def venice_import(veniceObject, description, data, constants, exclusive=False):
  """Importeer een verkoopfactuur in venice
  @param veniceObject object in dewelke moet geimporteerd worden voor boekjaar
  @param description file name met factuur beschrijving
  @param data file name met factuur data
  @param exclusive import requires exclusive access to Venice files, needed for ticking
  @return het factuur nummer van de geimporteerde factuur
  """ 
  oldSysNum = 0; 
  if veniceObject.SeekBySysNum(constants.smLast, 0):
    oldSysNum = int(veniceObject.pSysNum)
  logger.debug('last number before import : %i'%oldSysNum)
  try:
    success, items, message = veniceObject.Import(description, data, 0, True, True, exclusive)
  except Exception, e:
    logger.error('error during import : description and data file :', exc_info=e)
    logger.error('data file %s'%data)
    logger.error('description file %s'%description)
    for line in open(description).readlines():
      logger.error(line)
    for line in open(data).readlines():
      logger.error(line)
    raise e
  if not success:
    logger.error( 'Could not import data' )
    logger.error( ' error code : %s'%success )
    logger.error( ' error message : %s'%message )
    logger.error( ' description file : %s'%description )
    for line in open( description ).readlines():
        logger.error( '   ' + line )
    logger.error( ' data file : %s'%data )
    for line in open( data ).readlines():
        logger.error( '   ' + line )
    raise Exception(message)
  newSysNum = 0; 
  newDocNum = 0;
  if veniceObject.SeekBySysNum(constants.smLast, 0):
    newSysNum = int(veniceObject.pSysNum)
    newDocNum = int(veniceObject.pDocNum)
  # Now go to the first object, to release this one
  veniceObject.SeekBySysNum(constants.smFirst, 0)
  logger.debug('last number after import : %i'%newSysNum)    
  if newSysNum!=oldSysNum+1:
    logger.warning('multiple documents imported at once, cannot determine document numbers')
  #os.remove(description)
  #os.remove(data)
  #go to other object, in order not to keep this one open ??
  veniceObject.SeekBySysNum(constants.smFirst, 0)
  return (newSysNum, newDocNum)

_com_object_cache_ = {}
_dossier_cache_ = {}

def clear_com_object_cache():
    global _com_object_cache_
    global _dossier_cache_
    logger.info('clear %s dossiers'%(len(_dossier_cache_)))
    for k,v in _dossier_cache_.items():
        logger.debug(' delete %s'%str(k))
        v[0].clear_cache()
    _dossier_cache_.clear()
    logger.info('clear %s venice objects'%(len(_com_object_cache_)))
    _com_object_cache_.clear()

# is this line causing null pointer exceptions ??
#atexit.register(clear_com_object_cache)
  
def get_com_object(version=None, secure=False, initials=False, user=False, password=False, dialog=False, cache=True, current=False, app_name='python'):
  """Create a venice com object, or get one from cache for a certain venice
  version.  If secure=True password should be supplied, otherwise initials
  should be supplied.  If no user is supplied, try logon with dialog.
  
  return (venice,constants) a wrapper around the venice object to do safe
  multithreading, and the venice constants relevant to this specific version
  
  :param dialog: connect to Venice using the GUI
  
  """
  try:
    import settings
    secure, initials, user, password = settings.VENICE_LOGON
  except Exception, e:
    pass
  
  global _com_object_cache_
  
  class VeniceWrapper(object):
    def __init__(self, version=None, secure=False, initials=False, user=False, password=False):
      if (version=='MOCK') or (not sys.platform.startswith('win')):
        import mock
        venice = mock.mock_venice_com_object('mock venice com')
        constants = mock.mock_venice_class('mock venice constants')
      else:
        import pythoncom
        import win32com
        import win32com.client
        pythoncom.CoInitialize()
        self._venice = None
        try:
            venice = win32com.client.gencache.EnsureDispatch("ClSdk.Venice")
        except pythoncom.com_error, (hr, msg, _exc, _arg):
            logger.error('Could not connect to Venice %s : %s'%(hr, msg))
            raise VeniceConnectException('Could not connect to Venice, make sure Venice is installed on this computer.\n%s : %s'%(hr, msg))
        access_mode = venice.GetAccessMode()
        constants = win32com.client.constants
        logger.info('dispatch ok, access mode %s'%access_mode)
        logger.info('venice version %s with registration %s'%(str(venice.vVeniceVersion), str(venice.vRegNumber)))
        version = str(venice.vVeniceVersion)
        logger.info('logging in with version %s'%str(version))
        if current == True:
            try:
              version = version.split('_')[0] # in case a service pack was installed: ignore this part, this is in format e.g. "9.30_ SP3"
              venice.LogonCurrent(version,
                                  app_name,
                                  user)
            except Exception as e:
              raise VeniceConnectException('Trying to connect with version %s - type:%s - Venice version: %s.\nException: %s'%(version, type(version), venice.vVeniceVersion, e))
        elif user and dialog==False:
          if secure:
            venice.LogonSecure(version, 'python', constants.lngNld, False, user, password)
          else:
            venice.Logon(version, 'python', constants.lngNld, False, initials, user, '')
        else:
          venice.LogonDialog(version, 'python')
        logger.info('login ok')      
      self._venice = venice
      self._constants = constants
      self._version = version
    def __getattribute__(self, attr):
      if attr in ['_venice', '_constants', '_version']:
        return object.__getattribute__(self, attr)
      else:
        return getattr(self._venice, attr)

  key = (version,secure,initials,user,password)
  if cache:
      if key not in _com_object_cache_:
        wrapper = VeniceWrapper(*key)
        _com_object_cache_[key] = (wrapper, wrapper._constants)
      return _com_object_cache_[key]
  else:
      wrapper = VeniceWrapper(*key)
      return wrapper._venice, wrapper._constants

class FunctionCache(object):
  def __init__(self, dossier, constants, function_name):
    self._dossier = dossier
    self._constants = constants
    self._function_name = function_name
    self._cache = {}
  def __call__(o, *args):
    if args not in o._cache:
      logger.debug('%s(%s)'%(o._function_name, str(args)))
      result = getattr(o._dossier, o._function_name)(*args)
      if 'Create' in o._function_name:
        result = DossierWrapper(result, o._constants, str(args))
      o._cache[args] = result
    return o._cache[args]
  def clear_cache(self):
    logger.debug('clear function cache %s'%self._function_name)
    for _k,v in self._cache.items():
      if hasattr(v, 'clear_cache'):
        v.clear_cache()
    self._cache.clear()

  def __unicode__(self):
    return self._function_name
          
class DossierWrapper(object):
  def __init__(self, dossier, constants, name=None):
    self._dossier = dossier
    self._constants = constants
    self._cache = {}
    self._name = name
  def __getattribute__(self, attr):
    if attr in ['_dossier', '_constants', '_cache', '_name', 'create_files', 'import_files', 'clear_cache']:
      return object.__getattribute__(self, attr)
    elif 'Create' in attr:
      if attr not in self._cache:
        self._cache[attr] = FunctionCache(self._dossier, self._constants, attr)
      return self._cache[attr]
    else:
      return getattr(self._dossier, attr)
  
  create_import_files=create_import_files
  
  def create_files(self, *args, **kwargs):
    return create_import_files(*args, **kwargs)
  
  def import_files(self, veniceObject, description, data, exclusive=False):
    return venice_import(veniceObject, description, data, self._constants, exclusive)
  
  def clear_cache(self):
    logger.debug('clear dossier cache %s'%str(self._name))
    for _k,v in self._cache.items():
      v.clear_cache()
    self._cache.clear()

  def __unicode__(self):
    return u'Venice Dossier %s'%(self._name)
         
def get_dossier_context(version, secure, initials, user, password, folder, dossier):
  """returns (dossier_context, constants)"""
  
  global _dossier_cache_
  
  key = (version, secure, initials, user, password, folder, dossier)    
  if key not in _dossier_cache_:
    venice, constants = get_com_object(version, secure, initials, user, password)
    context = DossierWrapper( venice.CreateDossierContext(folder, dossier), constants, str(key))
    _dossier_cache_[key] = context, constants
  return _dossier_cache_[key]
 
def d2v(d):
  """Convert a python date object into a string that can be fed to venice as a date"""
  return '%s/%s/%s'%(('%s'%d.day).rjust(2,'0'),('%s'%d.month).rjust(2,'0'),d.year)

book_date_compare = lambda x,y:cmp(x.book_date, y.book_date)

def venice_type_to_python_type(venice_value):
  if hasattr(venice_value, 'year'): #isinstance does not work on these win32 things, so check if it quacks like a datetime
    if venice_value.year < 1900:
      return None
    venice_value = datetime (
      year=venice_value.year,
      month=venice_value.month,
      day=venice_value.day,
      hour=venice_value.hour,
      minute=venice_value.minute,
      second=venice_value.second
    )
  return venice_value

def venice_date(original_date):
#  incoming objects are of type PyTime : http://docs.activestate.com/activepython/2.4/pywin32/PyTime.html

  if not original_date:
      return None
  
  year = original_date.year
  if year < 100:
      year = 2000 + year

  return datetime( year = year,
                   month = original_date.month,
                   day = original_date.day,
                   hour = original_date.hour,
                   minute = original_date.minute,
                   second = original_date.second )

def to_venice_date( python_date ):
    """:return: a PyTime object, to be used through the SDK api"""
    return pywintypes.Time( python_date.timetuple() )
 
class entry_wrapper(object):
  """Convert a Venice Entry object to a python object with these conversions :
  - dates are converted to python date types
  - book, doc_number, document_date, book_date and line_number are those from the
    original entry, in case the entry is transfered from another financial year, 
    otherwise they are those as is in the current year
  """
  def __str__(self):
    bd = '%s/%s/%s'%(self.book_date.day, self.book_date.month, self.book_date.year)
    return '%s %s %s %8s %s (%s %s)'%(self.account, self.book, self.doc_number, bd, self.amount, self.book_org, self.doc_number_current )
  def __init__(self, entry):
    if entry.pAccYearOrg:
      # het betreft een overdracht vh vorige boekjaar
      self.book = entry.GetFieldStr( entry.GetFieldID('BookOrg') )
      self.doc_number = entry.pDocNumOrg
      self.document_date = venice_date( entry.pDocDateOrg )
      self.book_date = venice_date( entry.pBookDateOrg )
      self.line_number = entry.pLineNumOrg
    else:
      # het betreft een boeking vh huidige boekjaar
      self.book = entry.GetFieldStr( entry.GetFieldID('Book') )
      self.doc_number = entry.pDocNum
      self.document_date = venice_date( entry.pDocDate )
      self.book_date = venice_date( entry.pBookDate )
      self.line_number = entry.vLineNum
    self.account = entry.GetFieldStr( entry.GetFieldID('Account') )
    self.book_org = entry.GetFieldStr( entry.GetFieldID('BookOrg') )
    self.remark = entry.pRemark
    #Reverse engineered waarde van pBookDateOrg
    #als deze niet gelijk is aan een 30-12-1899, dan is die
    #verschillend van pBookDate of zoiets
    self.amount = entry.pAmountDosC 
    self.open_amount = entry.pOpenDosC 
    #Reverse engineered waarde pTickStatus:
    # 0 : bedrag staat nog volledig open
    # 1 : bedrag staat nog gedeeltelijk open
    # 2 : bedrag is volledig afgepunt
    self.ticked = entry.pTickStatus==2
    self.doc_number_org = entry.pDocNumOrg
    self.doc_number_current = entry.pDocNum
    self.sys_number = entry.pSysNum
    self.tick_sys_number = entry.pTickSysNum
           
class venice_account(object):
      
  def __init__(self, account, dossier, constants):
    self.account = account
    self.dossier = dossier
    self.constants = constants
  def balance(self):
    """Current balance"""
    current_year = self.dossier.CreateYearContext(self.dossier.GetYears()[-1])
    balan = current_year.CreateBalan(False)
    return balan.GetBalance('%s*'%self.account, 0)
  def balance_at(self, dt):
    """balance of the account when all transactions occuring before and at a specified datetime
    have been processed.
    """
    balan = reduce(lambda x,y:x+y.amount, self.entries_upto(dt.year, dt), 0.0 )
    return balan
  def balance_at_end_of_month(self, dt):
    balan = self.dossier.CreateYearContext(dt.year).CreateBalan(False)
    return sum( balan.GetBalance(self.account, month) for month in range(1, dt.month+1))
  def entries_upto(self, year, enddate):
    """generate all entries of a year upto a specified day of enddate"""
    entry = self.dossier.CreateYearContext(year).CreateEntry(False)
    end_day = datetime(enddate.year, enddate.month, enddate.day)
    if entry.SetFilter('@ENT.Account ^^ "%s"'%(self.account), True):      
      while True:
        e = entry_wrapper(entry)
        book_day = datetime(e.book_date.year, e.book_date.month, e.book_date.day)
        if book_day <= end_day and e.account.startswith(self.account):
          yield e
        if not entry.GetNext():
          break  
  def unticked_entries(self, year):
    """generate all entries that have not been ticked yet"""
    entry = self.dossier.CreateYearContext(year).CreateEntry(False)
    if entry.SetFilter('@ENT.Account ^^ "%s" && @ENT.TickStatus<2'%(self.account), True):
      while True:
        e = entry_wrapper(entry)
        if not e.ticked:
          yield e
        if not entry.GetNext():
          break
  def all_entries(self, year):
    """generate all entries"""
    entry = self.dossier.CreateYearContext(year).CreateEntry(False)
    if entry.SetFilter('@ENT.Account ^^ "%s"'%(self.account), True):
      while True:
        e = entry_wrapper(entry)
        yield e
        if not entry.GetNext():
          break          
  def entries_after(self, year, startdate):
    entry = self.dossier.CreateYearContext(year).CreateEntry(False)
    start_day = datetime(startdate.year, startdate.month, startdate.day)
    if entry.SetFilter('@ENT.Account ^^ "%s"'%(self.account), True):
      while True:
        e = entry_wrapper(entry)
        if e.book_date >= start_day and e.account.startswith(self.account):
          yield e
        if not entry.GetNext():
          break
  def filtered_entries(self, year, filter):
    """Directly add a filter to the venice sql query"""
    entry = self.dossier.CreateYearContext(year).CreateEntry(False)
    if entry.SetFilter('@ENT.Account ^^ "%s" && (%s)'%((self.account),filter), True):
      while True:
        e = entry_wrapper(entry)
        yield e
        if not entry.GetNext():
          break         
  def entries_between(self, year, startdate, enddate):
    """generate all entries in a year between a startdate and an enddate, including
    the startdate and the enddate"""
    end_day = datetime(enddate.year, enddate.month, enddate.day)
    for entry in self.entries_after(year, startdate):
      if entry.book_date <= end_day:
        yield entry
  def debit_credit_saldi(self, year, startdate, enddate):
    """returns (debit, credit) saldi for the periode between startdate and enddate,
    including startdate and enddate"""
    debit = 0.0
    credit = 0.0
    for entry in self.entries_between(year, startdate, enddate):
      if entry.amount > 0.0:
        debit += entry.amount
      else:
        credit += entry.amount
    return (debit, credit*-1.0)
  def entry_with_document(self, book, document_number, year):
    """generate entries on this account associated with a specific document id, occuring
    in a specified year"""
    entry = self.dossier.CreateYearContext(year).CreateEntry(False)
    if entry.SetFilter('@ENT.DocNum==%i && @ENT.Book=="%s" && @ENT.Account^^"%s"'%(document_number, book, self.account), True):
      while True:
        e = entry_wrapper( entry )
        yield e
        if not entry.GetNext():
          break    
        
class VeniceConstants( dict ):
    
    def load_from_file( self ):
        from cStringIO import StringIO        
        from camelot.core.resources import resource_string        
        constants_file = StringIO( resource_string( 'integration.venice', os.path.join( 'ClSdkConstants.inc' ) ) )
        for line in constants_file.readlines():
            parts = line.split(' ')
            if len(parts) == 4:
                self[ parts[1] ] = int( parts[-1] )
        
    def __getattr__( self, key ):
        if not len( self ):
            self.load_from_file()
        return self[key]
    
constants = VeniceConstants()
