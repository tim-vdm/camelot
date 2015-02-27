
import calendar
from datetime import date
import logging

logger = logging.getLogger('convenience')

def fun_if(condition, if_func, else_func=None):
  if condition:
    return if_func()
  else:
    if else_func:
      return else_func()
      
class dict_as_obj(object):
  
  def __init__(self, d):
    self._d = d
  
  def __getattribute__(self, attr):
    if attr.startswith('_'):
      return object.__getattribute__(self, attr)
    return self._d[attr]
  
def selection(keys, exceptions={}):
  """Generate key,value pairs for the construction field.selection object,
  based on a list with keys and a dictionary with exceptions.
  """
  d = dict( (k, k.replace('_',' ').capitalize()) for k in keys)
  d.update(exceptions)
  return [ i for i in d.items() ]

def language_context(arg):
  """Create a context object for languages"""
  d = {'fr':'fr_FR'}
  lang = 'nl'
  if arg in d:
    lang = d[arg]
  return {'lang':lang}

def bool_to_text(value, context):
  d = {'nl':{True:'ja', False:'nee'},
       'fr_FR':{True:'oui', False:'non'} }
  if 'lang' in context:
    if context['lang'] in d:
      lang = context['lang']
  else:
    lang = 'nl'
  return d[lang][value]

def d2t(str_date):
  if str_date:
    return '%04i-%02i-%02i'%(str_date.year, str_date.month, str_date.day)
  return ''

def t2d(tiny_date, default=None):
  if tiny_date:
    year, month, day = tiny_date.split('-')
    try:
      return date(int(year), int(month), int(day))
    except Exception, e:
      logger.error('received illegal date : "%s"'%tiny_date)
      raise e
  return default

def ftd(tiny_date):
  """Format tiny date for insertion in text"""
  if tiny_date:
    year, month, day = tiny_date.split('-')
    return u'%s/%s/%s' % (day, month, year)
  return u''

def t2e(t):
  """Convert a tiny date to a string, usable in excel"""
  d = t2d(t)
  if d == None:
    return ''
  return '%s-%s-%s'%(d.day, d.month, d.year)

def add_months_to_date(start_date, months):
  """the return type should be the same as the type of start_date"""
  year, month = map(sum, zip((start_date.year, 1), divmod(start_date.month + months - 1, 12)))
  weekday_, numdays = calendar.monthrange(year, month)
  return type(start_date)(year, month, min(numdays, start_date.day))

def months_between_dates(start_date, end_date):
  return (end_date.year - start_date.year) * 12 + end_date.month - start_date.month

def translate(tiny, source, context):
  if 'lang' in context:
    ids = tiny('ir.translation', 'search', [('src','=',source), ('lang','=',context['lang'])])
    if len(ids):
      return tiny('ir.translation', 'read', ids, ['value'])[0]['value'].decode('utf-8')
  return source

class remote_tiny_object(object):
  def __init__(self, tiny, type, id, cache={}, prefetch=[], context={}):
    self._type = type
    self._id = id
    self._tiny = tiny
    self._cache = cache
    # context seems to be no possible kwarg for some tiny instances, see overzicht_aanvragen.py
    self._context = context
    if type in cache:
      self._fields = cache[type]
    else:
      self._fields = tiny(type, 'fields_get')
      cache[type] = self._fields
    if len(prefetch):
      self._prefetched = self._tiny(self._type, 'read', [id], prefetch)[0]
    else:
      self._prefetched = {}
  def delete(self):
    if 'state' in self._fields:
      self.state='deletable'
    self._tiny(self._type, 'unlink', [self._id])
    self._id = None
  def __setattr__(self, attr, value):
    if attr.startswith('_'):
      return object.__setattr__(self, attr, value)
    self._tiny(self._type, 'write', [self._id], {attr:value})
  def __getattribute__(self, attr):
    if attr=='id':
      return self._id
    if attr.startswith('_') or attr=='delete':
      return object.__getattribute__(self, attr)
    if attr not in self._fields:
      # the requested attribute was no field, so it could be a method
      def create_remote_method(remote_object, method):
        
        def remote_method(*args):
          result = remote_object._tiny(remote_object._type, method, [remote_object._id], *args)
          remote_object._prefetched = {}
          return result
        
        return remote_method
      
      return create_remote_method(self, attr)
    value = self._prefetched.get(attr, None)
    if not value:
      value = self._tiny(self._type, 'read', [self._id], [attr], self._context)[0][attr]
    if value==False:
      return value
    if self._fields[attr]['type'] == 'many2one':
      if not (isinstance(value, tuple) or isinstance(value, list)):
        value = (value, '')
      return remote_tiny_object(self._tiny, self._fields[attr]['relation'], value[0], cache=self._cache, context=self._context)
    if self._fields[attr]['type'] in ('one2many', 'many2many'):
      return [ remote_tiny_object(self._tiny, self._fields[attr]['relation'], id, cache=self._cache, context=self._context) for id in value ]
    return value
  def __getitem__(self, attr):
    """Make it compatible with dictionairies generated with read"""
    return self.__getattribute__(attr)
  def __str__(self):
    return 'remote_tiny_object %s %i'%(self._type, self._id)

class unicode_remote_tiny_object(object):
  """Remote tiny object decorator"""
  
  def __init__(self, remote_tiny_object):
    self._rto = remote_tiny_object
    
  def __getattribute__(self, attr):
    if attr.startswith('__'):
      return object.__getattribute__(self, attr)
    rto = object.__getattribute__(self, '_rto')
    value = rto.__getattribute__(attr) 
    if isinstance(value, basestring):
      return unicode(value, 'utf-8')
    if isinstance(value, remote_tiny_object):
      return unicode_remote_tiny_object(value)
    if isinstance(value, list):
      return [unicode_remote_tiny_object(o) for o in value]
    return value

  def __getitem__(self, attr):
    """Make it compatible with dictionairies generated with read"""
    return self.__getattribute__(attr)
    
def remote_tiny_objects(tiny, type, ids, cache={}, prefetch=[], context={}):
  for id in ids:
    yield remote_tiny_object(tiny, type, id, cache, prefetch, context={})

def rounding_decorator(oldfun):
  
  def new_fun(*args, **kwargs):
    return round(oldfun(*args, **kwargs), 2)
  
  return new_fun

#
# py 2.5 compatible ordered set
#

def unique(inlist, keepstr=True):
  typ = type(inlist)
  if not typ == list:
    inlist = list(inlist)
  i = 0
  while i < len(inlist):
    try:
      del inlist[inlist.index(inlist[i], i + 1)]
    except:
      i += 1
  if not typ in (str, unicode):
    inlist = typ(inlist)
  else:
    if keepstr:
      inlist = ''.join(inlist)
  return inlist
      

