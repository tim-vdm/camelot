"""
The accounting module is an abstraction of the accounting system used
by V-Finance.

It contains tables to specify how documents are transfered to the accounting
system
"""

import datetime
import logging

import sqlalchemy.types
from sqlalchemy import sql, schema

from camelot.admin.entity_admin import EntityAdmin
from camelot.model.authentication import end_of_times
from camelot.core.exception import UserException
from camelot.core.orm import Entity, using_options
from camelot.core.utils import ugettext, ugettext_lazy as _

logger = logging.getLogger('vfinance.model.bank.accounting')

class AccountingPeriod( Entity ):
    using_options( tablename = 'accounting_period' )
    from_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    from_book_date = schema.Column( sqlalchemy.types.Date(), nullable=False )
    thru_book_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False )
    from_doc_date = schema.Column( sqlalchemy.types.Date(), nullable=False )
    thru_doc_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False )
    
    def validate_dates( self, book_date, doc_date ):
        """raise an exception when the book or dac date fall outside this
        accounting period"""
        if doc_date > self.thru_doc_date:
            raise UserException( 'Document %s date passed accounting period at %s'%( doc_date, self.thru_doc_date ) )
        if doc_date < self.from_doc_date:
            raise UserException( 'Document %s date before accounting period at %s'%( doc_date, self.from_doc_date ) )   
        if book_date > self.thru_book_date:
            raise UserException( 'Book date %s passed accouting period at %s'%( book_date, self.thru_book_date ) )
        if book_date < self.from_book_date:
            raise UserException( 'Book date %s before accouting period at %s'%( book_date, self.from_book_date ) )  
        
    @classmethod
    def get_accounting_period_at( cls, valid_date = None ):
        """Raises an exception if no period is found
        
        :param valid_date: the date at which to lookup the accounting period, 
            use `today` if `None` is given
        """
        if valid_date == None:
            valid_date = datetime.date.today()
        accounting_period = cls.query.filter( sql.and_( cls.from_date <= valid_date,
                                                        cls.thru_date >= valid_date ) ).order_by( cls.id ).first()
        if not accounting_period:
            raise UserException( text = ugettext('No accounting period found at %s')%valid_date,
                                 resolution = ugettext('Add an accounting period where %s is between the from date and the thru date')%valid_date )
        return accounting_period
    
    class Admin( EntityAdmin ):
        verbose_name = _('Accounting Period')
        list_display = ['from_date', 'thru_date', 'from_book_date', 'thru_book_date', 'from_doc_date', 'thru_doc_date' ]

