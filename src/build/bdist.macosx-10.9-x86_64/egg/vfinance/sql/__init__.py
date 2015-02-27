"""
 Custom Sqlalchemy expressions to have code portable between postgres and
 sqlite

 https://groups.google.com/forum/?fromgroups#!topic/sqlalchemy/a9vwZdLf7vM

 Postgres tips and hints :

 http://thebuild.com/presentations/not-my-job-djangocon-us.pdf
"""

from sqlalchemy import sql, types as sqltypes
from sqlalchemy.ext import compiler

class date_sub( sql.expression.FunctionElement ):
    """Subtract an integer number of days from a date"""
    type = sqltypes.Date()
    name = 'date_sub'

@compiler.compiles(date_sub, 'postgresql')
def _pg_date_sub( element, compiler, **kw ):
    return "(%s::date - integer '%s')" % (
        compiler.process(element.clauses.clauses[0]),
        compiler.process(element.clauses.clauses[1]),
    )

@compiler.compiles(date_sub, 'sqlite')
def _sqlite_date_sub(element, compiler, **kw):
    return "date(%s, '-' || %s || ' day')" % (
            compiler.process(element.clauses.clauses[0], **kw),
            compiler.process(element.clauses.clauses[1], **kw),
        )

class datetime_to_date( sql.expression.FunctionElement ):
    """Convert a datetime expression to a date"""
    type = sqltypes.Date()
    name = 'datetime_to_date'

@compiler.compiles(datetime_to_date, 'postgresql')
def _pg_datetime_to_date( element, compiler, **kw ):
    return "cast( date_trunc( 'day', %s ) as date )" % (
        compiler.process(element.clauses.clauses[0]),
    )

@compiler.compiles(datetime_to_date, 'sqlite')
def _sqlite_datetime_to_date( element, compiler, **kw ):
    return "date( %s )" % (
        compiler.process(element.clauses.clauses[0], **kw),
    )

class year_part( sql.expression.FunctionElement ):
    """Return the year part from a date column"""
    type = sqltypes.Text()
    name = 'year_part'

    # a table attribute or property is needed for certain SQLA generated
    # queries when a refresh of the session takes place
    @property
    def table(self):
        for c in self.clauses:
            return c.table

    @property
    def key(self):
        for c in self.clauses:
            return c.key

@compiler.compiles(year_part)
def _default_year_part( element, compiler, **kw ):
    return "date_part('year', %s)" % (
        compiler.process(element.clauses.clauses[0]),
    )

@compiler.compiles(year_part, 'postgresql')
def _pg_year_part( element, compiler, **kw ):
    return "date_part('year', %s)" % (
        compiler.process(element.clauses.clauses[0]),
    )

@compiler.compiles(year_part, 'sqlite')
def _sqlite_year_part( element, compiler, **kw ):
    return "strftime('%%Y', %s)" % (
        compiler.process(element.clauses.clauses[0], **kw),
    )

class greatest( sql.expression.FunctionElement ):
    """Return the greatest of two numers"""
    type = sqltypes.Numeric()
    name = 'greatest'

@compiler.compiles(greatest, 'postgresql')
def _pg_greatest( element, compiler, **kw ):
    return "greatest(%s, %s)" % (
        compiler.process(element.clauses.clauses[0]),
        compiler.process(element.clauses.clauses[1]),
    )

@compiler.compiles(greatest, 'sqlite')
def _sqlite_greatest( element, compiler, **kw ):
    return "max(%s, %s)" % (
        compiler.process(element.clauses.clauses[0], **kw),
        compiler.process(element.clauses.clauses[1], **kw),
    )

class bool_or( sql.expression.FunctionElement ):
    """Aggregate function that returns True if one of
    the aggregated values was True"""
    type = sqltypes.Boolean()
    name = 'bool_or'

@compiler.compiles(bool_or, 'postgresql')
def _pg_bool_or( element, compiler, **kw ):
    return "bool_or(%s)" % (
        compiler.process(element.clauses.clauses[0]),
    )

@compiler.compiles(bool_or, 'sqlite')
def _sqlite_bool_or( element, compiler, **kw ):
    return "max(%s)" % (
        compiler.process(element.clauses.clauses[0], **kw),
    )

class explain( sql.expression.Executable, sql.expression.ClauseElement):
    """Explain and analyze a query"""

    name = 'explain'

    def __init__( self, clause ):
        self.clause = clause

@compiler.compiles(explain)
def default_greatest(element, compiler, **kw):
    return compiler.process(element.clause)

@compiler.compiles(explain, 'postgresql')
def _pg_explain( element, compiler, **kw ):
    return "explain analyze %s" % element.clause

@compiler.compiles(explain, 'sqlite')
def _sqlite_explain( element, compiler, **kw ):
    return "explain query plan %s" % element.clause


