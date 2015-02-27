"""Create custom methods to replace the default osv.orm object methods"""

from osv import osv, fields
import logging
logger = logging.getLogger('integration.tinyerp.custom_osv')

def create_custom_search(showed_states=[]):
  """Create a search function for an osv.orm object which returns
  no objects, if no search condition is given or if the search 
  condition is only a certain state.
  @param showed_states list of states in which the search results should
                       not be hidden
  """
  
  def no_empty_search(self, cr, uid, conditions, offset=0, limit=None, order=None, context=None, count=False):
    """Cannot search without a condition, to prevent DOS"""
    if len(conditions) or limit:
      if limit or (not conditions[0][0]=='state') or (conditions[0][2] in showed_states) or limit or len(conditions)>1:
        return osv.osv.search(self, cr, uid, conditions, offset, limit, order)
    return osv.osv.search(self, cr, uid, conditions, offset=0, limit=5, order='write_date desc')
  
  return no_empty_search

def create_custom_unlink(deletable_states=[]):
  """Create an unlink function for an osv.orm object which throws
  an exeption when you try to delete a row that is not in a deletable state.
  @param deltetable_states list of states in which a row can be deleted
  
  this method requires the object on which it is used to have a 'name'
  attributed, so 'user friendly exceptions' can be thrown
  """
  
  def protected_unlink(self, cr, uid, ids, context={}):
    """Cannot delete rows which are not in a deletable state"""
    for row in self.read(cr, uid, ids, ['state']):
      if row['state'] not in deletable_states and row['state']!='deletable':
        row = self.read(cr, uid, [row['id']], ['state', 'name'])[0]
        raise Exception('%s kan niet worden verwijderd in status %s'%(row['name'], row['state']))
    return osv.osv.unlink(self, cr, uid, ids, context)
  
  return protected_unlink

def create_fcnt_search(fcnt):

  import operator
  import convenience
  
  def fcnt_search(self, cr, uid, obj, name, args):
    
    def ilike(x, y):
      return min(x.count(y), 1)
    
    operators = {'=':operator.eq, '<':operator.lt, '<=':operator.le, '>':operator.gt, 
                 '>=':operator.ge, '!=':operator.ne, 'ilike':ilike,
                 'in':lambda x,y:x in y}
    ids = []
    if self._columns[name]._type=='date':
      conversion = convenience.t2d
    elif self._columns[name]._type=='char':
      conversion = lambda x:(x or '').lower()
    else:
      conversion = lambda x:x
    for id,value in fcnt(self, cr, uid, self.search(cr, uid, [('id','>',0)])).items():
      
      value = conversion(value)
      if sum(operators[arg[1]](value,conversion(arg[2])) for arg in args)==len(args):
        ids.append(id)
    return [('id', 'in', ids)]

  return fcnt_search

def add_related_field(columns, relation, related_class, field, new_name=None, new_string=None):
  """Helper function to add a related field on an object (same concept as FileMaker)
  @param the columns definition of the object on which we want to add a related field
  @param relation the field name in which te related object is stored
  @param related_class the class of the related object
  @param field the name of the field on the related object
  @param new_name the name of the field on the current object, none if it should be
  the same as field
  """
  logger = logging.getLogger('custom_osv.add_related_field')
  logger.debug('add_related_field.%s'%related_class._name)
  if new_string==None:
    new_string=related_class._columns[field].string
  if new_name==None:
    new_name = field
    
  related_type = related_class._columns[field]._type
    
  def getter(self, cr, uid, ids, prop, unknown_none, context):
    result = dict((id,None) for id in ids)
    related_object = self.pool.get(related_class._name)
    ids_and_related_ids = self.read(cr, uid, ids, [relation])
    ids_from_related_ids = dict((id_and_related_id[relation][0],id_and_related_id['id'])
                                for id_and_related_id in ids_and_related_ids if id_and_related_id[relation])
    related_fields = related_object.read(cr, uid, ids_from_related_ids.keys(), [field] )
    result.update(dict( (ids_from_related_ids[related_field['id']], related_field[field]) for related_field in related_fields ))
    return result
  
  if related_type=='selection':
    related = fields.function(getter, method=True, type=related_type, string=new_string, selection=related_class._columns[field].selection)
  else:
    related = fields.function(getter, method=True, type=related_type, string=new_string)
  columns[new_name]=related
  
def add_related_sum(columns, relation, related_class, field, new_name=None, new_string=None):
  
  import itertools
  
  if new_string==None:
    new_string=related_class._columns[field].string
  if new_name==None:
    new_name = field  
    
  def getter(self, cr, uid, ids, prop, unknown_none, context):
    result = dict((id,None) for id in ids)
    related_object = self.pool.get(related_class._name)
    ids_and_related_ids = self.read(cr, uid, ids, [relation])
    related_ids = list(set(itertools.chain(*(id_and_related_ids[relation] for id_and_related_ids in ids_and_related_ids))))
    related_ids_and_fields = dict((r['id'],r[field]) for r in related_object.read(cr, uid, related_ids, [field] ))
    related_sums = dict((id_and_related_ids['id'], sum(related_ids_and_fields[related_id] for related_id in id_and_related_ids[relation])) \
                         for id_and_related_ids in ids_and_related_ids)
    result.update(related_sums)
    return result
    
  related = fields.function(getter, method=True, type=related_class._columns[field]._type, string=new_string)
  columns[new_name]=related 