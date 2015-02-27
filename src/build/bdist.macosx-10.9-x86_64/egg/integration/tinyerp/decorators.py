
import operator

class dict2object(object):
  def __init__(self, d):
    self.__dict__.update(d)
      
def transform_query(query, key='value', id='id', default=0):
  """Transform an sql query to a tinyerp getter
  @param query: the sql query or a callable that returns the sql query, the query string will be interpolated
  with the requested ids. eg. : 'select * from hypo_hypotheek where hypo_hypotheek in (%s)' 
  @param key: the key to be used to get the relevant data from the result  
  if the query is callable, it will be called with the sargument of the returned function.
  use this to declare queries that need properties of the object to be build, like _table
  @param id: the id to select on, eg : hypo_hypotheek.id
  @param default: the default value to return if the query did not return a result for a requested id
  """ 
  
  def newfun(self, cr, uid, ids, prop, unknow_none, context):
    result = dict((i,default) for i in ids)
    ids_string = ','.join([str(i) for i in ids])
    if callable(query):
      complete_query = query(self, cr, uid, ids, prop, unknow_none, context)%ids_string
    else:
      complete_query = query%ids_string
    cr.execute(complete_query)
    res = cr.dictfetchall()
    result.update(dict((row[id],row[key]) for row in res))
    return result
  
  return newfun
      
def transform_browse(meth):
  def newfun(self, cr, uid, ids, prop, unknow_none, context):
    return dict( [ (record.id, meth(self, cr, uid, record)) for record in self.browse(cr, uid, ids, context) ] )
  return newfun

def transform_browse_to_button(meth):
  def newfun(self, cr, uid, ids, *args):
    for record in self.browse(cr, uid, ids, *args):
      meth(self, cr, uid, record)
    return True
  return newfun

def transform_read_to_button(fields=None):
  if fields != None and not 'id' in fields: fields = [ 'id' ] + fields
  def decorator(meth):
    def newfun(self, cr, uid, ids, *args, **kwargs):
      return dict( [ (record['id'], meth(self, cr, uid, dict2object(record))) for record in self.read(cr, uid, ids, fields) ] )
    return newfun
  return decorator

def transform_read(fields=None):
  if fields != None and not 'id' in fields: fields = [ 'id' ] + fields
  def decorator(meth):
    def newfun(self, cr, uid, ids, *args, **kwargs):
      return dict( [ (record['id'], meth(self, cr, uid, dict2object(record))) for record in self.read(cr, uid, ids, fields) ] )
    return newfun
  return decorator

def transform_read_with_arguments(fields=None):
  if fields != None and not 'id' in fields: fields = [ 'id' ] + fields
  def decorator(meth):
    def newfun(self, cr, uid, ids, *args, **kwargs):
      return dict( [ (record['id'], meth(self, cr, uid, dict2object(record), *args, **kwargs)) for record in self.read(cr, uid, ids, fields) ] )
    return newfun
  return decorator

def transform_read_to_constraint(fields=None):
  if fields != None and not 'id' in fields: fields = [ 'id' ] + fields
  def decorator(meth):
    def newfun(self, cr, uid, ids):
      for record in self.read(cr, uid, ids, fields):
        if meth(self, cr, uid, dict2object(record))==False:
          return False
      return True
    return newfun
  return decorator

def transform_stub(stub_value):
  def decorator(meth):
    def newfun(self, cr, uid, ids, prop, unknow_none, context):
      return dict([ (id, stub_value) for id in ids ])
    return newfun
  return decorator

def constraint_browse(meth):
  def newfun(self, cr, uid, ids):
    return reduce(operator.and_, [ meth(record) for record in self.browse(cr, uid, ids) ] )
  return newfun

def error_condition(*args):
  def decorator(meth):
    def newfun(self, cr, uid, ids, *args, **kw):
      result = self.search(cr, uid, [ ('id', 'in', ids) ] + args)
      if len(result) > 0:
        raise Exception('bewerking niet toegelaten')
      return meth(self, cr, uid, ids, *args, **kw)
    return newfun
  return decorator
