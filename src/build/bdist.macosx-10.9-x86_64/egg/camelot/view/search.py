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
Helper functions to search through a collection of entities
"""
import datetime
import decimal
import logging

LOGGER = logging.getLogger('camelot.view.search')

import six

from camelot.types import virtual_address
from sqlalchemy import sql

import camelot.types

def create_entity_search_query_decorator( admin, text ):
    """create a query decorator to search through a collection of entities
    :param admin: the admin interface of the entity
    :param text: the text to search for
    :return: a function that can be applied to a query to make the query filter
    only the objects related to the requested text or None if no such decorator
    could be build
    """
    from camelot.view import utils

    if len(text.strip()):
        # arguments for the where clause
        args = []
        # join conditions : list of join entities
        joins = []

        def append_column( c, text, args ):
            """add column c to the where clause using a clause that
            is relevant for that type of column"""
            arg = None
            try:
                python_type = c.type.python_type
            except NotImplementedError:
                return
            # @todo : this should use the from_string field attribute, without
            #         looking at the sql code
            if issubclass(c.type.__class__, camelot.types.Color):
                pass
            elif issubclass(c.type.__class__, camelot.types.File):
                pass
            elif issubclass(c.type.__class__, camelot.types.Enumeration):
                pass
            elif issubclass(c.type.__class__, camelot.types.Code):
                codes = [u'%%%s%%'%s for s in text.split(c.type.separator)]
                codes = codes + ['%']*(len(c.type.parts) - len(codes))
                arg = c.like( codes )
            elif issubclass(python_type, virtual_address):
                arg = c.like(virtual_address('%', '%'+text+'%'))
            elif issubclass(c.type.__class__, camelot.types.Image):
                pass
            elif issubclass(python_type, bool):
                try:
                    arg = (c==utils.bool_from_string(text))
                except ( Exception, utils.ParsingError ):
                    pass
            elif issubclass(python_type, int):
                try:
                    arg = (c==utils.int_from_string(text))
                except ( Exception, utils.ParsingError ):
                    pass
            elif issubclass(python_type, datetime.date):
                try:
                    arg = (c==utils.date_from_string(text))
                except ( Exception, utils.ParsingError ):
                    pass
            elif issubclass(python_type, datetime.timedelta):
                try:
                    days = utils.int_from_string(text)
                    arg = (c==datetime.timedelta(days=days))
                except ( Exception, utils.ParsingError ):
                    pass
            elif issubclass(python_type, (float, decimal.Decimal)):
                try:
                    float_value = utils.float_from_string(text)
                    precision = c.type.precision
                    if isinstance(precision, (tuple)):
                        precision = precision[1]
                    delta = 0.1**( precision or 0 )
                    arg = sql.and_(c>=float_value-delta, c<=float_value+delta)
                except ( Exception, utils.ParsingError ):
                    pass
            elif issubclass(python_type, six.string_types):
                arg = sql.operators.ilike_op(c, '%'+text+'%')

            if arg is not None:
                arg = sql.and_(c != None, arg)
                args.append(arg)

        for t in text.split(' '):
            subexp = []
            for column_name in admin.get_search_fields(t):
                path = column_name.split('.')
                target = admin.entity
                related_admin = admin
                for path_segment in path:
                    # use the field attributes for the introspection, as these
                    # have detected hybrid properties
                    fa = related_admin.get_descriptor_field_attributes(path_segment)
                    instrumented_attribute = getattr(target, path_segment)
                    if fa.get('target', False):
                        joins.append(instrumented_attribute)
                        target = fa['target']
                        related_admin = related_admin.get_related_admin(target)
                    else:
                        append_column(instrumented_attribute, t, subexp)

            args.append(subexp)

        def create_query_decorator(joins, args):
            """Bind the join and args to a query decorator function"""

            def query_decorator(query):
                """The actual query decorator, call this function with a query
                as its first argument and it will return a query with a where
                clause for searching the resultset of the original query"""
                for join in joins:
                    query = query.outerjoin(join)

                subqueries = (sql.or_(*arg) for arg in args)
                query = query.filter(sql.and_(*subqueries))

                return query

            return query_decorator

        return create_query_decorator(joins, args)

