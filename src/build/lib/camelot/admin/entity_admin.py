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

import inspect
import itertools
import logging
logger = logging.getLogger('camelot.admin.entity_admin')

from camelot.admin.action import list_filter
from camelot.admin.object_admin import ObjectAdmin
from camelot.admin.validator.entity_validator import EntityValidator
from camelot.core.memento import memento_change
from camelot.core.orm import Session
from camelot.core.orm.entity import entity_to_dict
from camelot.types import PrimaryKey
from camelot.core.qt import Qt

import six

from sqlalchemy import orm, schema, sql
from sqlalchemy.ext import hybrid
from sqlalchemy.orm.attributes import instance_state

class EntityAdmin(ObjectAdmin):
    """Admin class specific for classes that are mapped by sqlalchemy.
This allows for much more introspection than the standard
:class:`camelot.admin.object_admin.ObjectAdmin`.

It has additional class attributes that customise its behaviour.

**Filtering**

.. attribute:: list_filter

    A list of fields that should be used to generate filters for in the table
    view.  If the field named is a one2many, many2one or many2many field, the
    field name should be followed by a field name of the related entity ::

        class Project( Entity ):
            oranization = OneToMany( 'Organization' )
            name = Column( Unicode(50) )

          class Admin( EntityAdmin ):
              list_display = ['organization']
              list_filter = ['organization.name']

    .. image:: /_static/filter/group_box_filter.png

**Copying**

.. attribute:: copy_deep

    A dictionary of fields that will be deep copied when the user presses the copy
    button.  This is useful for OneToMany fields.  The key in the dictionary should
    be the name of the field, and the value is a new dictionary :: 

       copy_deep = {'addresses':{}}

    This dictionary can contain fields in the related object that need to be deep 
    copied as well ::

       copy_deep = {'addresses':{'city':{}}}


.. attribute:: copy_exclude

    A list of fields that should not be copied when the user presses the copy button::

        copy_exclude = ['name']

    The fields that form the primary key of the object will be excluded by default.

To further customize the copy process without additional user interaction,
:meth:`camelot.admin.object_admin.EntityAdmin.copy` method can be overwritten.

If the user interaction during the copy process needs to be customized as well, the
:class:`camelot.admin.action.list_action.DuplicateSelection` class can be subclassed
and used as a custom action.


    """

    copy_deep = {}
    copy_exclude = []
    validator = EntityValidator

    def __init__(self, app_admin, entity):
        super(EntityAdmin, self).__init__(app_admin, entity)
        from sqlalchemy.orm.exc import UnmappedClassError
        from sqlalchemy.orm.mapper import _mapper_registry
        try:
            self.mapper = orm.class_mapper(self.entity)
        except UnmappedClassError as exception:
            mapped_entities = [six.text_type(m) for m in six.iterkeys(_mapper_registry)]
            logger.error(u'%s is not a mapped class, configured mappers include %s'%(self.entity, u','.join(mapped_entities)),
                         exc_info=exception)
            raise exception
        # caching
        self._search_fields = None

    @classmethod
    def get_sql_field_attributes( cls, columns ):
        """Returns a set of default field attributes based on introspection
        of the SQLAlchemy columns that form a field

        :param: columns a list of :class:`sqlalchemy:sqlalchemy.schema.Column`
            objects.
        :return: a dictionary with field attributes

        By default this method looks at the first column that defines the
        field and derives a delegate and other field attributes that make
        sense.
        """
        from camelot.view.field_attributes import _sqlalchemy_to_python_type_
        sql_attributes = dict()
        for column in columns:
            column_type = column.type
            sql_attributes['python_type'] = ''
            sql_attributes['doc'] = ''
            # PrimaryKey is not in _sqlalchemy_to_python_type_, but its
            # implementation class probably is
            if isinstance(column_type, PrimaryKey):
                column_type = column_type.load_dialect_impl(None)
            for base_class in inspect.getmro( type( column_type ) ):
                fa = _sqlalchemy_to_python_type_.get( base_class,
                                                      None )
                if fa is not None:
                    sql_attributes.update( fa( column_type ) )
                    break
            if isinstance( column, (schema.Column) ):
                sql_attributes['nullable'] = column.nullable
                sql_attributes['default'] = column.default
                sql_attributes['doc'] = column.doc or ''
                editable = (column.primary_key is False)
                # if these fields are editable, they are validated when a form
                # is closed, while at that time the field is not yet filled
                # because the foreign key column is only filled after the flush
                if len(column.foreign_keys):
                    editable = False
                sql_attributes['editable'] = editable
            field_admin = getattr(column, '_field_admin', None)
            if field_admin != None:
                sql_attributes.update(field_admin.get_field_attributes())
            break
        return sql_attributes

    def get_query(self):
        """:return: an sqlalchemy query for all the objects that should be
        displayed in the table or the selection view.  Overwrite this method to
        change the default query, which selects all rows in the database.
        """
        return Session().query( self.entity )

    def get_verbose_identifier(self, obj):
        if obj:
            primary_key = self.mapper.primary_key_from_instance(obj)
            if not None in primary_key:
                primary_key_representation = u','.join([six.text_type(v) for v in primary_key])
                if hasattr(obj, '__unicode__'):
                    return u'%s %s : %s' % (
                        six.text_type(self.get_verbose_name() or ''),
                        primary_key_representation,
                        six.text_type(obj)
                    )
                else:
                    return u'%s %s' % (
                        self.get_verbose_name() or '',
                        primary_key_representation
                    )
        return self.get_verbose_name()

    def get_search_identifiers(self, obj):
        search_identifiers = {}

        search_identifiers[Qt.DisplayRole] = u'%s' % (six.text_type(obj))
        search_identifiers[Qt.EditRole] = obj
        search_identifiers[Qt.ToolTipRole] = u'id: %s' % (self.primary_key(obj))

        return search_identifiers                

    def get_descriptor_field_attributes(self, field_name):
        """Returns a set of default field attributes based on introspection
        of the descriptor of a field.
        """
        from camelot.view.proxy.queryproxy import QueryTableProxy
        from camelot.view.controls import delegates
        attributes = super(EntityAdmin, self).get_descriptor_field_attributes(field_name)
        #
        # Field attributes forced by the field_attributes property
        #
        forced_attributes = self.field_attributes.get(field_name, {})
        #
        # Get the default field_attributes trough introspection if the
        # field is a mapped field
        #
        from sqlalchemy import orm
        from sqlalchemy.exc import InvalidRequestError
        #
        # See if there is a sqlalchemy descriptor
        #
        for cls in self.entity.__mro__:
            descriptor = cls.__dict__.get(field_name, None)
            if descriptor is not None:
                if isinstance(descriptor, hybrid.hybrid_property):
                    attributes['editable'] = (descriptor.fset is not None)
                    if (descriptor.expr is None) or (descriptor.expr == descriptor.fget):
                        # the descriptor has no expression, stop the introspection
                        break
                    # dont try to get the expression from the descriptor, but use
                    # the 'appropriate' way to get it from the class.  Getting it
                    # from the descriptor seems to manipulate  the actual descriptor
                    class_attribute = getattr(self.entity, field_name)
                    if class_attribute is not None:
                        if isinstance(class_attribute, sql.Select):
                            for k, v in six.iteritems(self.get_sql_field_attributes(class_attribute.columns)):
                                # the defaults or the nullable status of the column
                                # does not need to be the default or the nullable
                                # of the hybrid property
                                if k in ['default', 'nullable']:
                                    continue
                                attributes[k] = v
                break
        # @todo : investigate if the property can be fetched from the descriptor
        #         instead of going through the mapper
        try:
            property = self.mapper.get_property(
                field_name
            )
            if isinstance(property, orm.properties.ColumnProperty):
                columns = property.columns
                sql_attributes = self.get_sql_field_attributes( columns )
                attributes.update( sql_attributes )
            elif isinstance(property, orm.properties.RelationshipProperty):
                target = forced_attributes.get( 'target',
                                                property.mapper.class_ )

                attributes.update( target = target,
                                   editable = property.viewonly==False,
                                   nullable = True)
                foreign_keys = list( property._user_defined_foreign_keys )
                foreign_keys.extend( list(property._calculated_foreign_keys) )

                if property.direction == orm.interfaces.ONETOMANY:
                    attributes.update( direction = 'onetomany' )
                elif property.direction == orm.interfaces.MANYTOONE:
                    attributes.update(
                        #
                        # @todo: take into account all foreign keys instead
                        # of only the first one
                        #
                        nullable = foreign_keys[0].nullable,
                        direction = 'manytoone',
                    )
                elif property.direction == orm.interfaces.MANYTOMANY:
                    attributes.update( direction = 'manytomany' )
                else:
                    raise Exception('RelationshipProperty has unknown direction')

                if property.direction in (orm.interfaces.ONETOMANY,
                                          orm.interfaces.MANYTOMANY):
                    if property.lazy == 'dynamic':
                        attributes.update(proxy=QueryTableProxy)

                if property.uselist == True:
                    attributes.update(
                        delegate = delegates.One2ManyDelegate,
                        python_type = list,
                        create_inline = False,
                    )
                else:
                    attributes.update(
                        delegate = delegates.Many2OneDelegate,
                        python_type = str,
                    )

        except InvalidRequestError:
            #
            # If the field name is not a property of the mapper, then use
            # the default stuff
            #
            pass
        return attributes

    def _expand_field_attributes(self, field_attributes, field_name):
        """Given a set field attributes, expand the set with attributes
        derived from the given attributes.
        """
        #
        # In case of a text 'target' field attribute, resolve it
        #
        from sqlalchemy.orm.mapper import _mapper_registry
        target = field_attributes.get('target', None)
        if isinstance(target, six.string_types):
            for mapped_class in six.iterkeys(_mapper_registry):
                if mapped_class.class_.__name__ == target:
                    field_attributes['target'] = mapped_class.class_
                    break
            else:
                raise Exception('No mapped class found for target %s'%target)
        super(EntityAdmin, self)._expand_field_attributes(field_attributes, field_name)

    def get_dynamic_field_attributes(self, obj, field_names):
        """Takes the dynamic field attributes from through the ObjectAdmin its
        get_dynamic_field_attributes and make relational fields not editable
        in case the object is not yet persisted.
        """
        directions = ('onetomany', 'manytomany' )
        persistent = self.is_persistent( obj )
        iter1, iter2 = itertools.tee( field_names )
        attributes_iterator = super(EntityAdmin, self).get_dynamic_field_attributes( obj, iter1 )
        for attributes, field_name in zip( attributes_iterator, iter2 ):
            if not persistent:
                all_attributes = self.get_field_attributes( field_name )
                if all_attributes.get('direction', False) in directions:
                    attributes['editable'] = False
            yield attributes

    def get_filters( self ):
        """Returns the filters applicable for these entities each filter is

        :return: [filter, filter, ...]
        """

        def filter_generator():
            for structure in self.list_filter:
                if not isinstance(structure, list_filter.Filter):
                    structure = list_filter.GroupBoxFilter(structure)
                yield structure

        return list(filter_generator())

    def primary_key( self, obj ):
        """Get the primary key of an object
        :param obj: the object to get the primary key from
        :return: a tuple with with components of the primary key, or none
            if the object has no primary key yet or any more.
        """
        if not self.is_persistent( obj ):
            return None
        # this function is called on compound objects as well, so the
        # mapper might be different from the mapper related to this admin
        mapper = orm.object_mapper(obj)
        return mapper.primary_key_from_instance( obj )

    def get_modifications( self, obj ):
        """Get the modifications on an object since the last flush.
        :param obj: the object for which to get the modifications
        :return: a dictionary with the changed attributes and their old
           value
        """
        from sqlalchemy import orm
        from sqlalchemy.orm.exc import UnmappedClassError
        state = orm.attributes.instance_state( obj )
        dict_ = state.dict
        modifications = dict()
        for attr in state.manager.attributes:
            if not hasattr( attr.impl, 'get_history' ):
                continue
            (added, unchanged, deleted) = \
                attr.impl.get_history( state, dict_ )
            if added or deleted:
                old_value = None
                if deleted:
                    old_value = deleted[0]
                    #
                    # in case of relations, get the primary key of the object
                    # instead of the object itself
                    #
                    try:
                        mapper = orm.class_mapper( type( old_value ) )
                        old_value = mapper.primary_key_from_instance( old_value )
                    except UnmappedClassError:
                        pass
                modifications[ attr.key ] = old_value
        return modifications

    def add( self, obj ):
        """Adds the entity instance to the default session, if it is not
        yet attached to a session"""
        session = Session.object_session( obj )
        if session == None:
            Session().add( obj )

    def delete(self, entity_instance):
        """Delete an entity instance"""
        session = Session.object_session( entity_instance )
        #
        # new and deleted instances cannot be deleted
        #
        if session:
            if entity_instance in session.new:
                session.expunge(entity_instance)
            elif entity_instance not in session.deleted:
                #
                # only if we know the primary key, we can keep track of its history
                #
                primary_key = self.primary_key( entity_instance )
                if not None in primary_key:
                    # save the state before the update
                    memento = self.get_memento()
                    if memento != None:
                        modifications = entity_to_dict( entity_instance )
                        change = memento_change( model = six.text_type( self.entity.__name__ ),
                                                 memento_type = 'before_delete',
                                                 primary_key = primary_key,
                                                 previous_attributes = modifications )
                        memento.register_changes( [change] )
                session.delete( entity_instance )
                session.flush()

    def expunge(self, entity_instance):
        """Expunge the entity from the session"""
        session = orm.object_session( entity_instance )
        if session:
            objects_to_expunge = set([entity_instance])
            self._expand_compounding_objects( objects_to_expunge )
            for obj in objects_to_expunge:
                if obj in session:
                    session.expunge( obj )

    def _expand_compounding_objects( self, objs ):
        """
        Given a set of objects, expand this set with all compounding objects.
        :param objs: a `set` of objects
        """
        assert isinstance( objs, set )
        additional_objects = set(objs)
        while additional_objects:
            objs.update( additional_objects )
            additional_objects.clear()
            for obj_to_flush in objs:
                related_admin = self.get_related_admin( type(obj_to_flush ) )
                for compounding_object in related_admin.get_compounding_objects( obj_to_flush ):
                    if compounding_object not in objs:
                        additional_objects.add( compounding_object )

    def flush(self, entity_instance):
        """Flush the pending changes of this entity instance to the backend"""
        from sqlalchemy.orm.session import Session
        session = Session.object_session( entity_instance )
        if session:
            objects_to_flush = set([entity_instance])
            self._expand_compounding_objects( objects_to_flush )
            #
            # Create a list of changes
            #
            changes = []
            for obj_to_flush in objects_to_flush:
                if obj_to_flush in session.dirty:
                    modifications = {}
                    try:
                        modifications = self.get_modifications( obj_to_flush )
                    except Exception as e:
                        # todo : there seems to be a bug in sqlalchemy that causes the
                        #        get history to fail in some cases
                        logger.error( 'could not get modifications from object', exc_info = e )
                    primary_key = self.primary_key( obj_to_flush )
                    if modifications and (None not in primary_key):
                        change = memento_change( model = six.text_type(type(obj_to_flush).__name__),
                                                 memento_type = 'before_update',
                                                 primary_key = primary_key,
                                                 previous_attributes = modifications )
                        changes.append( change )
            session.flush( objects_to_flush )
            #
            # If needed, track the changes
            #
            memento = self.get_memento()
            if changes and memento != None:
                memento.register_changes( changes )

    def refresh(self, entity_instance):
        """Undo the pending changes to the backend and restore the original
        state"""
        session = orm.object_session( entity_instance )
        if session:
            objects_to_refresh = set([entity_instance])
            self._expand_compounding_objects( objects_to_refresh )
            for obj in objects_to_refresh:
                if obj in session:
                    state = instance_state( obj )
                    if state.has_identity:
                        session.refresh( obj )
                    else:
                        session.expunge( obj )

    def is_persistent(self, obj):
        """:return: True if the object has a persisted state, False otherwise"""
        from sqlalchemy.orm.session import Session
        session = Session.object_session( obj )
        if session:
            if obj in session.new:
                return False
            if obj in session.deleted:
                return False
            return True
        return False

    def is_deleted(self, obj):
        """
        :return: True if the object has been deleted from the persistent
            state, False otherwise"""
        state = instance_state( obj )
        if state != None and state.deleted:
            return True
        return False

    def get_expanded_search_filters(self):
        """
        :return: a list of tuples of type [(field_name, field_attributes)]
        """
        if self.expanded_list_search == None:
            field_list = self.get_table().get_fields()
        else:
            field_list = self.expanded_list_search
        return [list_filter.EditorFilter(field_name) for field_name in field_list]

    def get_all_fields_and_attributes(self):
        """In addition to all the fields that are defined in the views
        or through the field_attributes, this method returns all the fields
        that have been mapped.
        """
        fields = super(EntityAdmin, self).get_all_fields_and_attributes()
        for mapper_property in self.mapper.iterate_properties:
            if isinstance(mapper_property, orm.properties.ColumnProperty):
                field_name = mapper_property.key
                fields[field_name] = self.get_field_attributes( field_name )
        return fields

    def get_search_fields(self, substring):
        """
        Generate a list of fields in which to search.  By default this method
        returns the fields in the `list_search` attribute as well as the 
        properties that are mapped to a column in the database.  Any property that
        is not a simple Column might result in very slow searches, so those should
        be put explicitly in the `list_search` attribute.

        :param substring: that part of the complete search string for which
           the search fields are requested.  This allows analysis of the search
           string to improve the search behavior

        :return: a list with the names of the fields in which to search
        """
        if self._search_fields is None:
            self._search_fields = list(self.list_search)
            for field_name, col_property in self.mapper.column_attrs.items():
                if isinstance(col_property.expression, schema.Column):
                    self._search_fields.append(field_name)
        return self._search_fields

    def copy(self, obj, new_obj=None):
        """Duplicate an object.  If no new object is given to copy to, a new
        one will be created.  This function will be called every time the
        user presses a copy button.

        :param obj: the object to be copied from
        :param new_obj: the object to be copied to, defaults to None
        :return: the new object

        This function takes into account the deep_copy and the copy_exclude
        attributes.  It tries to recreate relations with a minimum of side
        effects.
        """
        from sqlalchemy import orm
        if not new_obj:
            new_obj = obj.__class__()
        #
        # serialize the object to be copied
        #
        serialized = obj.to_dict(deep=self.copy_deep, exclude=[c.name for c in self.mapper.primary_key]+self.copy_exclude)
        #
        # make sure we don't move duplicated OneToMany relations from the
        # old object to the new, but instead duplicate them, by manipulating
        # the serialized structure
        #
        # @todo: this should be recursive
        for relationship_property in self.mapper.relationships:
            if relationship_property.direction == orm.interfaces.ONETOMANY:
                target = relationship_property.mapper.class_
                for relation in serialized.get(relationship_property.key, []):
                    relation_mapper = orm.class_mapper(target)
                    for primary_key_field in relation_mapper.primary_key:
                        # remove the primary key field, since setting it
                        # to None might overwrite a value set at object
                        # construction time
                        relation.pop(primary_key_field.name, None)
        #
        # deserialize into the new object
        #
        new_obj.from_dict( serialized )
        #
        # recreate the ManyToOne relations
        #
        for relationship_property in self.mapper.relationships:
            if relationship_property.direction == orm.interfaces.MANYTOONE:
                setattr( new_obj,
                         relationship_property.key,
                         getattr( obj, relationship_property.key ) )
        return new_obj

