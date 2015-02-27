#  ============================================================================
#
#  Copyright (C) 2007-2013 Conceptive Engineering bvba. All rights reserved.
#  www.conceptive.be / info@conceptive.be
#
#  This file is part of the Camelot Library.
#
#  This file may be used under the terms of the GNU General Public
#  License version 2.0 as published by the Free Software Foundation
#  and appearing in the file license.txt included in the packaging of
#  this file.  Please review this information to ensure GNU
#  General Public Licensing requirements will be met.
#
#  If you are unsure which license is appropriate for your use, please
#  visit www.python-camelot.com or contact info@conceptive.be
#
#  This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
#  WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#
#  For use of this library in commercial applications, please contact
#  info@conceptive.be
#
#  ============================================================================
"""
This module provides support for defining properties on your entities. It both
provides, the `Property` class which acts as a building block for common
properties such as fields and relationships (for those, please consult the
corresponding modules), but also provides some more specialized properties,
such as `ColumnProperty` and `Synonym`. It also provides the GenericProperty
class which allows you to wrap any SQLAlchemy property, and its DSL-syntax
equivalent: has_property_.

`has_property`
--------------
The ``has_property`` statement allows you to define properties which rely on
their entity's table (and columns) being defined before they can be declared
themselves. The `has_property` statement takes two arguments: first the name of
the property to be defined and second a function (often given as an anonymous
lambda) taking one argument and returning the desired SQLAlchemy property. That
function will be called whenever the entity table is completely defined, and
will be given the .c attribute of the entity as argument (as a way to access
the entity columns).

Here is a quick example of how to use ``has_property``.

.. sourcecode:: python

    class OrderLine(Entity):
        has_field('quantity', Float)
        has_field('unit_price', Float)
        has_property('price',
                     lambda c: column_property(
                         (c.quantity * c.unit_price).label('price')))
"""
from sqlalchemy import orm, schema

import six

from . statements import ClassMutator
from . import options

class CounterMeta(type):
    '''
    A simple meta class which adds a ``_counter`` attribute to the instances of
    the classes it is used on. This counter is simply incremented for each new
    instance.
    '''
    counter = 0

    def __call__(self, *args, **kwargs):
        instance = type.__call__(self, *args, **kwargs)
        instance.counter = CounterMeta.counter
        CounterMeta.counter += 1
        return instance

class EntityBuilder(six.with_metaclass(CounterMeta)):
    """
    Abstract base class for all entity builders. An Entity builder is a class
    of objects which can be added to an Entity (usually by using special
    properties or statements) to "build" that entity. Building an entity,
    meaning to add columns to its "main" table, create other tables, add
    properties to its mapper, ... To do so an EntityBuilder must override the
    corresponding method(s). This is to ensure the different operations happen
    in the correct order (for example, that the table is fully created before
    the mapper that use it is defined).
    """

    def __init__(self, *args, **kwargs):
        self.entity = None
        self.name = None

    def __lt__(self, builder):
        return self.counter < builder.counter
    
    def attach( self, entity, name ):
        """Attach this property to its entity, using 'name' as name.

        Properties will be attached in the order they were declared.
        """
        self.entity = entity
        self.name = name

    def __repr__(self):
        return "EntityBuilder(%s, %s)" % (self.name, self.entity)
    
    def create_pk_cols(self):
        pass

    def create_non_pk_cols(self):
        pass

    def before_table(self):
        pass

    def create_tables(self):
        '''
        Subclasses may override this method to create tables.
        '''

    def after_table(self):
        pass

    def create_properties(self):
        '''
        Subclasses may override this method to add properties to the involved
        entity.
        '''

    def before_mapper(self):
        pass

    def after_mapper(self):
        pass

    def finalize(self):
        pass
    
class PrimaryKeyProperty( EntityBuilder ):
    
    def create_pk_cols(self):
        from camelot.types import PrimaryKey
        setattr( self.entity,
                 self.name,
                 schema.Column( self.name, PrimaryKey(), 
                                **options.DEFAULT_AUTO_PRIMARYKEY_KWARGS) )
    
class DeferredProperty( EntityBuilder ):
    """Abstract base class for all properties of an Entity that are not 
    handled by Declarative but should be handled after a mapper was
    configured"""
        
    def _setup_reverse( self, key, rel, target_cls ):
        """Setup bidirectional behavior between two relationships."""

        reverse = self.kw.get( 'reverse' )
        if reverse:
            reverse_attr = getattr( target_cls, reverse )
            if not isinstance( reverse_attr, DeferredProperty ):
                reverse_attr.property._add_reverse_property( key )
                rel._add_reverse_property( reverse )
        
class GenericProperty( DeferredProperty ):
    '''
    Generic catch-all class to wrap an SQLAlchemy property.

    .. sourcecode:: python

        class OrderLine(Entity):
            quantity = Field(Float)
            unit_price = Field(Numeric)
            price = GenericProperty(lambda c: column_property(
                             (c.quantity * c.unit_price).label('price')))
    '''
    
    process_order = 4
    
    def __init__( self, prop, *args, **kwargs ):
        super( GenericProperty, self ).__init__()
        self.prop = prop
        self.args = args
        self.kwargs = kwargs
        
    def create_properties( self ):
        table = orm.class_mapper( self.entity ).local_table
        if hasattr( self.prop, '__call__' ):
            prop_value = self.prop( table.c )
        else:
            prop_value = self.prop
        prop_value = self.evaluate_property( prop_value )
        setattr( self.entity, self.name, prop_value )

    def evaluate_property( self, prop ):
        if self.args or self.kwargs:
            raise Exception('superfluous arguments passed to GenericProperty')
        return prop
    
    def _config( self, cls, mapper, key ):
        if hasattr(self.prop, '__call__'):
            prop_value = self.prop( mapper.local_table.c )
        else:
            prop_value = self.prop
        setattr( cls, key, prop_value )
        
class ColumnProperty( GenericProperty ):
    """A specialized form of the GenericProperty to generate SQLAlchemy
    ``column_property``'s.

    It takes a function (often given as an anonymous lambda) as its first
    argument. Other arguments and keyword arguments are forwarded to the
    column_property construct. That first-argument function must accept exactly
    one argument and must return the desired (scalar-returning) SQLAlchemy
    ClauseElement.

    The function will be called whenever the entity table is completely
    defined, and will be given
    the .c attribute of the table of the entity as argument (as a way to
    access the entity columns). The ColumnProperty will first wrap your
    ClauseElement in an
    "empty" label (ie it will be labelled automatically during queries),
    then wrap that in a column_property.

    .. sourcecode:: python

        class OrderLine(Entity):
            quantity = Field(Float)
            unit_price = Field(Numeric)
            price = ColumnProperty(lambda c: c.quantity * c.unit_price,
                                   deferred=True)

    Please look at the `corresponding SQLAlchemy
    documentation <http://docs.sqlalchemy.org/en/rel_0_7/orm/mapper_config.html#sql-expressions-as-mapped-attributes>`_ 
    for details."""

    def evaluate_property( self, prop ):
        return orm.column_property( prop.label( None ), *self.args, **self.kwargs )

class has_property( ClassMutator ):
    
    def process( self, entity_dict, name, prop, *args, **kwargs ):
        entity_dict[ name ] = GenericProperty( prop, *args, **kwargs )

