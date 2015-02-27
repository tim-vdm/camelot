"""Utility function to map python objects on an OO sheet"""

import string
import datetime

def map_objects_as_table(range, map, data, formula_start_row=4):
  """Put a list of objects on a sheet as a table
  
  @param range a range on a sheet on which to map the data
  @param map dictionary with column numbers and name of the attribute of the object to put there
  @param data list of objects to be mapped on the sheet
  
  """
  
  column_names = {}
  column_positions = {}
  
  for k,v in map.items():
    if isinstance(v,tuple):
      name = v[0]
    else:
      name = v
    column_names[name] = string.lowercase[k]
    column_positions[name] = k
    
  for title,col in column_positions.items():
    range.getCellByPosition(col,0).setString(str(title).replace('_', ' ').capitalize())
  for i,o in enumerate(data):
    for col,key in map.items():
      if isinstance(key, tuple):
        formula = key[1]
        name = key[0]
        cell_names = dict( (name,'%s%i'%(key, i+formula_start_row)) for name,key in column_names.items() )
        range.getCellByPosition(col,i+1).setFormula(formula%cell_names)
      else:
        value = getattr(o, key)
        if isinstance(value, float) or isinstance(value, int):
          range.getCellByPosition(col,i+1).setValue(value)
        elif isinstance(value, datetime.date):
          range.getCellByPosition(col,i+1).setString('%s-%s-%s'%(value.day, value.month, value.year))
        else:
          range.getCellByPosition(col,i+1).setString(value.decode('utf8'))
