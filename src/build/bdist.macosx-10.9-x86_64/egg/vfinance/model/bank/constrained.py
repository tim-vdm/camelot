import sqlalchemy.types
from sqlalchemy import schema

from camelot.admin.entity_admin import EntityAdmin
from camelot.core.orm import Entity, using_options
from camelot.core.utils import ugettext_lazy as _
from camelot.view.controls import delegates
from camelot.admin.object_admin import ObjectAdmin

def constraint_background_color(constraint):
    from camelot.view.art import ColorScheme
    return ColorScheme.VALIDATION_ERROR
    
class Constraint(Entity):
    using_options(tablename='bank_constraint')
    object_name = schema.Column(sqlalchemy.types.Unicode(40), index=True, nullable=False)
    object_id = schema.Column(sqlalchemy.types.Integer(), index=True, nullable=False)
    constraint_id = schema.Column(sqlalchemy.types.Integer(), index=True, nullable=False)
    message = schema.Column(sqlalchemy.types.Unicode(100))
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    class Admin(EntityAdmin):
        list_display = ['object_name', 'message',]
        field_attributes = {'object_name':{'minimal_column_width':40, 
                                           'name':'Name',
                                           'background_color':constraint_background_color,
                                           'editable':True},
                            'message':{'minimal_column_width':40},
                            'state':{'delegate':delegates.BoolDelegate}}
  
class ConstrainedDocument(object):
    """Abstract base class to attach constraints to classes"""
   
    def constraints(self):
        return []
    
    def constraint_key(self):
        """object_name and object_id used to store constraints related to this
        object into the constraint table """
        #
        # convert current table name to old tiny erp object name
        #
        object_name = self.table.name
        index = object_name.index('_')
        object_name = object_name[:index] + '.' + object_name[index+1:]
        return (object_name, self.id)
            
    def constraint_generator(self, passed):
        """Generate tuples with record and constraint
        for a record of a specific object"""
        key = self.constraint_key()
        if key not in passed:
            passed.add(key)
            object_name, object_id = key
            for constraint_id, constraint_name, constraint_state in self.constraints():
                constraint = Constraint.query.filter_by( object_name=object_name,
                                                         object_id=object_id,
                                                         constraint_id=constraint_id).first()
                if (not constraint) and (object_id!=None):
                    constraint = Constraint(object_name=object_name, object_id=object_id, constraint_id=constraint_id)
                setattr(constraint, 'name', u'%s : %s'%(constraint_name, unicode(self)))
                setattr(constraint, 'state', constraint_state)
                yield constraint
                  
    @property
    def related_constraints(self):
        passed = set()
        if not self.id:
            return []
        return [c for c in self.constraint_generator(passed)]
    
    class Admin(ObjectAdmin):
        field_attributes = {'related_constraints': {'name':_('Opmerkingen'),
                                                    'editable':False,
                                                    'python_type':list,
                                                    'delegate':delegates.One2ManyDelegate,
                                                    'admin':Constraint.Admin,
                                                    'target':Constraint} }
