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

"""Proxies representing the results of a query"""

import functools
import logging
logger = logging.getLogger('camelot.view.proxy.queryproxy')

import six

from sqlalchemy import orm, sql
from sqlalchemy.exc import InvalidRequestError

from ...core.qt import QtCore, Qt
from ..model_thread import object_thread, post
from .collection_proxy import CollectionProxy

class QueryTableProxy(CollectionProxy):
    """The QueryTableProxy contains a limited copy of the data in the SQLAlchemy
    model, which is fetched from the database to be used as the model for a
    QTableView
    """

    def __init__(self, admin, query=None, max_number_of_rows=10, 
                 cache_collection_proxy=None):
        """@param query_getter: a model_thread function that returns a query, can be None at construction time and set later"""
        logger.debug('initialize query table')
        self._query = query
        self._sort_decorator = None
        self._mapper = admin.mapper
        #the mode set for each filter
        self._filters = dict()
        #rows appended to the table which have not yet been flushed to the
        #database, and as such cannot be a result of the query
        self._appended_rows = []
        super(QueryTableProxy, self).__init__(admin,
                                              max_number_of_rows=max_number_of_rows, 
                                              cache_collection_proxy=cache_collection_proxy)     
        
    def get_query(self):
        """
        :return: the query used to fetch the data, this is not the same as the
            one set by `set_value`, as sorting and filters will modify it
        """
        query = self._query
        if query is None:
            return None
        if self._sort_decorator is None:
            self._set_sort_decorator()
            
        # filters might be changed in the gui thread while being iterated
        for filter_, value in six.iteritems(self._filters.copy()):
            query = filter_.decorate_query(query, value)
        query = self._sort_decorator(query)
        return query
    
    def _update_unflushed_rows( self ):
        """Does nothing since all rows returned by a query are flushed"""
        pass
    
    def _clean_appended_rows(self):
        """Remove those rows from appended rows that have been flushed"""
        flushed_rows = []
        for o in self._appended_rows:
            primary_key = self._mapper.primary_key_from_instance(o)
            if None not in primary_key:
                flushed_rows.append(o)
        for o in flushed_rows:
            self._appended_rows.remove(o)

    def getRowCount(self):
        locker = QtCore.QMutexLocker(self._mutex)
        self._rowcount_requested = False
        locker.unlock()
        self._clean_appended_rows()
        if self._query is None:
            return 0
        # manipulate the query to circumvent the use of subselects and order by
        # clauses
        query = self.get_query()
        mapper = orm.class_mapper(self.admin.entity)
        select = query.order_by(None).as_scalar()
        select = select.with_only_columns([sql.func.count(mapper.primary_key[0])])
        count = query.session.execute(select, mapper=mapper).scalar()
        return count + len(self._appended_rows)

    def set_value(self, query):
        """
        :param query: the `Query` to display
        """
        assert object_thread( self )
        self._query = query
        self.refresh()
            
    def get_value(self):
        return self._query

    def get_collection(self):
        """In case the collection is requested of a QueryProxy, we will return
        a collection getter for a collection that reuses the data already queried by
        the collection proxy, and available in the cache.
         
        We do this to :
        
        1. Prevent an unneeded query when the collection is used to fetch an object already
           fetched by the query proxy (eg when a form is opened on a table view)
           
        2. To make sure the index of an object in the query proxy is the same as the index
           in the returned collection.  Should we do the same query twice (once to fill the
           query proxy, and once to fill the returned collection), the same object might appear
           in a different row.  eg when a form is opened in a table view, the form contains 
           another record than the selected row in the table.
        """
        
        if self._query is None:
            return []
        return self.get_query().all()
    
    def _set_sort_decorator( self, column=None, order=None ):
        """set the sort decorator attribute of this model to a function that
        sorts a query by the given column using the given order.  When no
        arguments are given, use the default sorting, which is according to
        the primary keys of the model.  This to impose a strict ordening of
        the rows in the model.
        """
        
        order_by, join = [], None
        mapper = orm.class_mapper(self.admin.entity)
        #
        # First sort according the requested column
        #
        if None not in (column, order):
            property = None
            field_name = self._columns[column][0]
            class_attribute = getattr(self.admin.entity, field_name)

            #
            # The class attribute of a hybrid property can be an sql clause
            #

            if isinstance(class_attribute, sql.ClauseElement):
                order_by.append((class_attribute, order))

            try:
                property = mapper.get_property(
                    field_name,
                )
            except InvalidRequestError:
                pass
            
            # If the field is a relation: 
            #  If it specifies an order_by option we have to join the related table, 
            #  else we use the foreign key as sort field, without joining
            if property and isinstance(property, orm.properties.RelationshipProperty):
                target = property.mapper
                if target:
                    if target.order_by:
                        join = field_name
                        class_attribute = target.order_by[0]
                    else:
                        class_attribute = list(property._calculated_foreign_keys)[0]
            if property:
                order_by.append((class_attribute, order))
                                
        def sort_decorator(order_by, join, query):
            order_by = list(order_by)
            if join:
                query = query.outerjoin(join)
            # remove existing order clauses, because they might interfer
            # with the requested order from the user, as the existing order
            # clause is first in the list, and put them at the end of the list
            if query._order_by:
                for order_by_column in query._order_by:
                    order_by.append((order_by_column, Qt.AscendingOrder))
            #
            # Next sort according to default sort column if any
            #
            if mapper.order_by:
                for mapper_order_by in mapper.order_by:
                    order_by.append((mapper_order_by, Qt.AscendingOrder))
            #
            # In the end, sort according to the primary keys of the model, to enforce
            # a unique order in any case
            #
            for primary_key_column in mapper.primary_key:
                order_by.append((primary_key_column, Qt.AscendingOrder))
            query = query.order_by(None)
            order_by_columns = set()
            for order_by_column, order in order_by:
                if order_by_column not in order_by_columns:
                    if order == Qt.AscendingOrder:
                        query = query.order_by(order_by_column)
                    else:
                        query = query.order_by(sql.desc(order_by_column))
                    order_by_columns.add(order_by_column)
            return query
        
        self._sort_decorator = functools.partial(sort_decorator,
                                                 order_by, 
                                                 join)
        return self._rows
        
    def sort( self, column, order ):
        """Overwrites the :meth:`QAbstractItemModel.sort` method
        """
        assert object_thread( self )
        post( functools.update_wrapper( functools.partial( self._set_sort_decorator, column, order ), self._set_sort_decorator ), 
              self._refresh_content )

    def set_filter(self, list_filter, value):
        """
        Set the filter mode for a specific filter

        :param list_filter: a :class:`camelot.admin.action.list_filter.Filter` object
        :param value: the value on which to filter
        """
        self._filters[list_filter] = value
        self.refresh()

    def append(self, o):
        """Add an object to this collection, used when inserting a new
        row, overwrite this method for specific behaviour in subclasses"""
        primary_key = self._mapper.primary_key_from_instance(o)
        if None in primary_key:
            self._appended_rows.append(o)

    def remove(self, o):
        if o in self._appended_rows:
            self._appended_rows.remove(o)
        self._rows = self._rows - 1

    def _get_collection_range( self, offset, limit ):
        """Get the objects in a certain range of the collection
        :return: an iterator over the objects in the collection, starting at 
        offset, until limit
        """
        from sqlalchemy import orm
        from sqlalchemy.exc import InvalidRequestError
        
        query = self.get_query().offset(offset).limit(limit)
        #
        # undefer all columns displayed in the list, to reduce the number
        # of queries
        #
        columns_to_undefer = []
        for field_name, _field_attributes in self._columns:
            
            property = None
            try:
                property = self.admin.mapper.get_property(
                    field_name,
                )
            except InvalidRequestError:
                #
                # If the field name is not a property of the mapper
                #
                pass

            if property and isinstance(property, orm.properties.ColumnProperty):
                columns_to_undefer.append( field_name )
                
        if columns_to_undefer:
            options = [ orm.undefer( field_name ) for field_name in columns_to_undefer ]
            query = query.options( *options )
                
        return query.all()
                    
    def _extend_cache(self):
        """Extend the cache around the rows under request"""
        if self._query is not None:
            offset, limit = self._offset_and_limit_rows_to_get()
            if limit:
                columns = self._columns
                #
                # try to move the offset further by looking if the
                # objects are already in the cache.
                #
                # this has the advantage that we might not need a query,
                # and more important, that objects remain at the same row
                # while their position in the query might have been changed
                # since the previous query.
                #
                rows_in_cache = 0
                for row in range(offset, offset + limit):
                    try:
                        cached_obj =  self.edit_cache.get_entity_at_row(row)                        
                        self._add_data( columns, row, cached_obj)
                        rows_in_cache += 1
                    except KeyError:
                        break
                #
                # query the remaining rows
                #
                query_offset = offset + rows_in_cache
                query_limit = limit - rows_in_cache
                if query_limit > 0:
                    for i, obj in enumerate( self._get_collection_range(query_offset, 
                                                                        query_limit) ):
                        row = i + query_offset
                        try:
                            previous_obj = self.edit_cache.get_entity_at_row(row)
                            if previous_obj != obj:
                                continue
                        except KeyError:
                            pass
                        if self._skip_row(row, obj) == False:
                            self._add_data(columns, row, obj)
                rows_in_query = (self._rows - len(self._appended_rows))
                # Verify if rows that have not yet been flushed have been 
                # requested
                if offset+limit >= rows_in_query:
                    for row in range(max(rows_in_query, offset), min(offset+limit, self._rows)):
                        obj = self._get_object(row)
                        self._add_data(columns, row, obj)                
            return (offset, limit)

    def _get_object(self, row):
        """Get the object corresponding to row.  If row is smaller than 0
        (in case of an invalid widget mapper), None is returned as an object"""
        if ( self._rows > 0 ) and  ( self._rows > row >= 0 ):
            self._clean_appended_rows()
            rows_in_query = (self._rows - len(self._appended_rows))
            if row >= rows_in_query:
                return self._appended_rows[row - rows_in_query]
            # first try to get the primary key out of the cache, if it's not
            # there, query the collection_getter
            try:
                return self.edit_cache.get_entity_at_row(row)
            except KeyError:
                pass
            # momentary hack for list error that prevents forms to be closed
            if self._query is not None:
                res = self.get_query().offset(row)
                if isinstance(res, list):
                    res = res[0]
                # @todo: remove this try catch and find out why it 
                # sometimes fails
                try:
                    return res.limit(1).first()
                except:
                    pass

