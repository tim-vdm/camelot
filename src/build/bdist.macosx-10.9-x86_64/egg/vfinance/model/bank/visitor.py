import collections
import logging
import operator
import types
from decimal import Decimal as D
import decimal

LOGGER = logging.getLogger('vfinance.model.bank.visitor')

from sqlalchemy import sql, orm
from sqlalchemy.sql.compiler import SQLCompiler

from camelot.core.conf import settings
from camelot.core.exception import UserException
from camelot.core.orm import Session
from camelot.core.utils import ugettext
from camelot.model.authentication import end_of_times

from ...connector.accounting import (CreateSalesDocumentRequest,
                                     CreatePurchaseDocumentRequest,
                                     RemoveDocumentRequest,
                                     LineRequest,
                                     CreateSupplierAccountRequest,
                                     CreateCustomerAccountRequest,
                                     PartyRequest)
from ...sql import date_sub
from .entry import tick_date_query
from .constants import commission_receivers
from .financial_functions import ONE_HUNDREDTH, ONE_MILLIONTH

bindparam = sql.bindparam
        
#
# lightweight data structures to represent Entry and FinancialAccountPremiumFulfillment object,
# to avoid going through the ORM in performance critical situation
#
entry_data = collections.namedtuple('entry_data',
                                    'id, book_date, document, book, line_number, doc_date, account, amount, quantity, fulfillment_type, associated_to_id, creation_date, within_id')

#
# Sqlalchemy operators that have no Python equivalent
#
class DummyOperator( object ):

    def __init__( self, name ):
        self.name = name
        
    def __call__( self, a, b ):
        return getattr( a, self.name )( b )

in_ = DummyOperator( 'in_' )

class BookingAccount( object ):
    """Base class for all accounts on which can be booked"""
    
    #
    # custom comparison for query caching and others
    #   
    def __eq__( self, other):
        if self.__class__ == other.__class__:
            return hash( self ) == hash( other )
        return False
    
    def __hash__( self ):
        return hash( self.account_type )
    
    def __cmp__( self, other ):
        return cmp( hash( self ), hash( other ) )

    def account_type_before_distribution(self):
        """
        :return: the account type that had been used if the booking was not
            distributed among the commission receivers.
        """
        for _i, commission_receiver in commission_receivers:
            if self.account_type.endswith(commission_receiver):
                return self.account_type[:-1*(len(commission_receiver)+1)]
        return self.account_type

class CustomerBookingAccount( BookingAccount ):

    account_type = 'customer'

class SupplierBookingAccount( BookingAccount ):

    account_type = 'supplier'

    def __init__(self, supplier_type):
        self.supplier_type = supplier_type

    def __hash__( self ):
        return hash( (self.account_type, self.supplier_type) )
    
    def __unicode__( self ):
        return '{0.account_type} {0.supplier_type}'.format(self)

class ProductBookingAccount( BookingAccount ):
    """An account configured in a product on which can be booked"""
    
    def __init__( self, account_type, suffix='', alternative_account_type=None):
        """
        :param alternative_account_type: the account type to use when `account_type`
            is unavailable for a specific booking
        """
        #assert account_type in self.accounts_by_type
        self.account_type = account_type
        self.suffix = suffix
        self.alternative_account_type = alternative_account_type
        
    def __hash__( self ):
        return hash( (self.account_type, self.suffix) )
    
    def __unicode__( self ):
        return self.account_type

    def booking_account_number_at( self, premium_schedule, book_date ):
        account_number = premium_schedule.product.get_account_at(self.account_type, book_date)
        if (account_number == '') and (self.alternative_account_type is not None):
            account_number = premium_schedule.product.get_account_at(self.alternative_account_type, book_date)
        return account_number + self.suffix
    
    def booking_account_numbers( self, premium_schedule ):
        return premium_schedule.product.get_accounts( self.account_type )

class FulfilledSalesLine(LineRequest):

    __slots__ = LineRequest.__slots__ + ['fulfillment_type',
                                         'associated_to_id',
                                         'within_id',
                                         'booking_of_id']

    def __str__( self ):
        return unicode( self ).encode( 'ascii', 'ignore' )

    def __repr__( self ):
        return '<%s>'%str( self )

class VisitorMixin( object ):
    """
    Generic functions shared between the Financial visitors and the Mortgage
    visitors.
    """
    
    dependencies = []
    delta = D('0.01')
    
    def __init__( self,
                  entry_table,
                  fapf_table,
                  valid_at = sql.func.current_date(),
                  session = None ):
        self._accounting_period = None
        self._end_of_times = end_of_times()

        if session == None:
            session = Session()
        
        self._valid_at = valid_at
        self.entry_table = entry_table
        self.fapf_table = fapf_table
        self.associated_fapf_table = sql.alias(fapf_table)
        self.session = session
        self.dialect = session.connection( bind = self.entry_table.metadata.bind ).dialect
        self._settings = settings
        
        def currently_valid( q ):
            """
            :param: a FAPF query
            :return: a query that filters out only FAPFs that are currently valid
            """
            return q.where( sql.and_( fapf_table.c.from_date <= valid_at,
                                      fapf_table.c.thru_date >=valid_at ) )
        
        self._total_amount_at_query = currently_valid( self.entry_sum_query( fapf_table.c, 
                                                                             entry_table.c, ['amount', 'quantity'], ['amount_distribution']) )
        
        self._total_amount_until_query = currently_valid( self.entry_sum_query( fapf_table.c, 
                                                                                entry_table.c, ['amount','quantity'], ['amount_distribution']) )
        
        self._entry_query = currently_valid( sql.select( [ entry_table.c.id.label('id'),
                                                           entry_table.c.book_date.label('book_date'), 
                                                           entry_table.c.creation_date.label('creation_date'), 
                                                           entry_table.c.venice_doc.label('document'), 
                                                           entry_table.c.venice_book.label('book'), 
                                                           entry_table.c.line_number.label('line_number'), 
                                                           entry_table.c.datum.label('doc_date'), 
                                                           entry_table.c.account.label('account'), 
                                                           entry_table.c.amount.label('amount'), 
                                                           entry_table.c.open_amount.label('open_amount'),
                                                           entry_table.c.quantity.label('quantity'), 
                                                           fapf_table.c.id.label('fulfillment_id'),
                                                           fapf_table.c.fulfillment_type.label('fulfillment_type'), 
                                                           fapf_table.c.associated_to_id.label('associated_to_id'),
                                                           fapf_table.c.within_id.label('within_id'),
                                                           fapf_table.c.amount_distribution.label('amount_distribution'),
                                                           fapf_table.c.booking_of_id.label('booking_of_id'),
                                                           ] ).where( self.entry_from_fulfillment_condition( fapf_table.c, entry_table.c ) ) )
        self._entry_queries = dict()
        self._total_amount_at_queries = dict()
        self._total_amount_until_queries = dict()
        
    @staticmethod
    def entry_from_fulfillment_condition( fulfillment_columns, entry_columns ):
        return  sql.and_(fulfillment_columns.entry_book_date == entry_columns.book_date,
                         sql.func.lower( fulfillment_columns.entry_book ) == sql.func.lower( entry_columns.venice_book ), # Venice is case insensitive, so case might change
                         fulfillment_columns.entry_document == entry_columns.venice_doc,
                         fulfillment_columns.entry_line_number == entry_columns.line_number,)      
    
    @classmethod
    def entry_sum_query( cls, fulfillment_columns, entry_columns, entry_field_names, fulfillment_field_names = [] ):
        """
        Create a query to summarize all entries associated with a FinancialAccountPremiumFulfillment
        :param names_and_factor: a list of field names of the Entry object to summarize
        """
        return sql.select( [sql.func.sum(getattr(entry_columns, field_name)) for field_name in entry_field_names] + \
                           [sql.func.sum(getattr(fulfillment_columns, field_name)) for field_name in fulfillment_field_names],
                           cls.entry_from_fulfillment_condition( fulfillment_columns, 
                                                                 entry_columns) )    

    @property
    def accounting_period( self ):
        """Only query for accounting period when needed"""
        from vfinance.model.bank.accounting import AccountingPeriod
        if self._accounting_period == None:
            self._accounting_period = AccountingPeriod.get_accounting_period_at()
        return self._accounting_period

    def entered_book_date(self, document_date, _book_date):
        """ """     
        new_book_date = min( max( self.accounting_period.from_book_date, document_date ), self.accounting_period.thru_book_date )
        self.accounting_period.validate_dates( new_book_date, document_date )
        if document_date != new_book_date:
            LOGGER.debug( 'adapt book date from %s to %s'%( document_date, new_book_date ) )
        return new_book_date

    def _get_supplier_from_broker(self, broker, supplier_type, from_number, thru_number):
        """
        Get a SupplierAccount if it exists, or create a new one
        """
        if broker is None:
            return None
        person, organization = broker.get_dual_person(supplier_type)
        request = CreateSupplierAccountRequest(from_number=from_number,
                                               thru_number=thru_number)
        if person is not None:
            request.person_id = person.id
            request.name = person.name
        elif organization is not None:
            request.organization_id = organization.id
            request.name = organization.name
        else:
            return None
        return request

    def _key_and_params( self, schedule, conditions, fulfillment_types ):
        key = ( schedule.product.id, 
                tuple( (c[0],c[1],type(c[2])) for c in conditions ),
                tuple( c[2] for c in conditions if isinstance( c[2], ProductBookingAccount ) ),
                tuple( fulfillment_types or []) )
        
        params = dict()
        for condition_number, condition in enumerate( conditions ):
            for value in self._param_value( schedule, condition,  ):
                params[str( condition_number )] = value

        return key, params
    
    def _param_value( self, schedule, condition ):
        # None/null cannot be used in queries for which the compilation is cached,
        # since a param value of None changes the operator used in the query and
        # not only the parameter value
        assert condition[2] is not None
        if isinstance( condition[2], ProductBookingAccount ):
            pass
        else:
            yield condition[2]
        
    def _apply_conditions( self, schedule, query, conditions ):
        for i, condition in enumerate(conditions):
            query = self._apply_condition( schedule, query, condition, i )
        return query
    
    def _apply_condition( self, schedule, query, condition, condition_number ):
        (field_name, field_operator, value) = condition
        if (field_name == 'account') and isinstance( value, ProductBookingAccount ):
            account_clauses = []
            account_found = False
            for product_account in value.booking_account_numbers( schedule ):
                account_found = True
                account_clauses.append( sql.and_( field_operator( self.entry_table.c.account, ''.join(product_account.number) + value.suffix ),
                                                  self.entry_table.c.book_date >= product_account.from_date, 
                                                  self.entry_table.c.book_date <= product_account.thru_date ) )
            if account_found == False:
                # if there is no account configured of this type, make sure a condition is still added to the query
                account_clauses.append( field_operator( self.entry_table.c.account, None ) )
            query = query.where( sql.or_( *account_clauses ) )
        elif (field_name == 'account') and isinstance( value, CustomerBookingAccount ):
            query = query.where( self.entry_table.c.account.like( '%s%%'%self._settings.get('HYPO_ACCOUNT_KLANT')[:-9] ) )
        elif field_name in ('id', 'datum', 'book_date', 'line_number', 'creation_date', 'open_amount'):
            rhs = bindparam( str(condition_number) )
            lhs = getattr( self.entry_table.c, field_name )
            query = query.where( field_operator( lhs, rhs ) )
        elif field_name in ('tick_date',):
            rhs = bindparam( str(condition_number) )
            lhs = tick_date_query
            query = query.where( field_operator( lhs, rhs ) )
        elif field_name in ('associated_to_fulfillment_type',):
            lhs = self.associated_fapf_table.c.fulfillment_type
            rhs = bindparam( str(condition_number) )
            query = query.where(self.associated_fapf_table.c.id==self.fapf_table.c.associated_to_id).where( field_operator( lhs, rhs ) )
        else:
            rhs = bindparam( str(condition_number) )
            lhs = getattr( self.fapf_table.c, field_name )
            query = query.where( field_operator( lhs, rhs ) )
        return query

    def _get_entry_query( self, premium_schedule, conditions, fulfillment_types ):
        key, params = self._key_and_params( premium_schedule, conditions, fulfillment_types )
        try:
            query = self._entry_queries[ key ]
        except KeyError:
            query = self._apply_conditions( premium_schedule, self._entry_query, conditions )
            if fulfillment_types != None:
                query = query.where( self.fapf_table.c.fulfillment_type.in_( fulfillment_types ) )
            query = query.order_by( self.entry_table.c.datum, self.entry_table.c.venice_doc )
            query = SQLCompiler( self.dialect, query )
            self._entry_queries[ key ] = query
        return query, params
    
    def _get_total_amount_at_query( self, premium_schedule, conditions ):
        key, params = self._key_and_params( premium_schedule, conditions, [] )
        try:
            query = self._total_amount_at_queries[ key ]
        except KeyError:
            query = self._apply_conditions( premium_schedule, self._total_amount_at_query, conditions )
            query = SQLCompiler( self.dialect, query )
            self._total_amount_at_queries[ key ] = query
        return query, params
    
    def _get_total_amount_until_query( self, premium_schedule, conditions ):
        key, params = self._key_and_params( premium_schedule, conditions, [] )
        try:
            query = self._total_amount_until_queries[ key ]
        except KeyError:
            query = self._apply_conditions( premium_schedule, self._total_amount_until_query, conditions )
            query = SQLCompiler( self.dialect, query )
            self._total_amount_until_queries[ key ] = query
        return query, params    
        
    def get_entries(self, 
                    premium_schedule, 
                    from_document_date=None, thru_document_date=None,
                    from_book_date = None, thru_book_date = None,
                    fulfillment_type=None, 
                    account=None,
                    associated_to_id = None,
                    fulfillment_types = None,
                    within_id = None,
                    from_creation_date = None, 
                    thru_creation_date = None,
                    booking_of_id = None,
                    conditions = []):
        """Yields tuples of (entries, fulfillment_entries) with a document date between 
        from_document_date and thru_document_date
        
        :param fulfillment_types: a list of fulfillment types for which entries
            should be returned.  If None, this parameter is not used
            
        :param account: a :class:`BookingAccount` object
        :param within: a financial transaction premium schedule in which context this
            entry is taking place
        :param booking_of_id: the id of the invoice item which is booked through this
            entry
        :param conditions: tuples of additional conditions to be inserted in the
           query
           
        :return: a generator of (entry, fulfillment) tuples ordered by document date
        """
        assert isinstance( account, (BookingAccount, types.NoneType) )
        
        conditions = conditions + [ ('of_id', operator.eq, premium_schedule.history_of_id) ]
        if from_document_date:
            conditions.append( ('datum', operator.ge, from_document_date) )
        if thru_document_date:
            conditions.append( ('datum', operator.le, thru_document_date) )
        if fulfillment_type:
            conditions.append( ('fulfillment_type', operator.eq, fulfillment_type ) )
        if account:
            conditions.append( ('account', operator.eq, account ) )
        if from_book_date:
            conditions.append( ('book_date', operator.ge, from_book_date ) )
        if thru_book_date:
            conditions.append( ('book_date', operator.le, thru_book_date ) )
        if associated_to_id:
            conditions.append( ('associated_to_id', operator.eq, associated_to_id ) )
        if within_id != None:
            conditions.append( ('within_id', operator.eq, within_id ) )
        if from_creation_date:
            conditions.append( ('creation_date', operator.ge, from_creation_date) )
        if thru_creation_date:
            conditions.append( ('creation_date', operator.le, thru_creation_date) )
        if booking_of_id:
            conditions.append( ('booking_of_id', operator.eq, booking_of_id) )

        query, params = self._get_entry_query( premium_schedule, conditions, fulfillment_types )

        for row in self.session.connection( bind = self.entry_table.metadata.bind ).execute( query, **params ):
            yield row                                                         
                    
    def get_total_amount_at( self, 
                             premium_schedule, 
                             document_date, 
                             thru_book_date=None,
                             fulfillment_type=None, 
                             account=None,
                             associated_to_id = None,
                             within_id = None):
        assert isinstance( account, (BookingAccount, types.NoneType) )
        
        conditions = [ ('of_id', operator.eq, premium_schedule.history_of_id),
                       ('datum', operator.eq, document_date), ]

        if fulfillment_type:
            conditions.append( ('fulfillment_type', operator.eq, fulfillment_type ) )
        if account:
            conditions.append( ('account', operator.eq, account ) )
        if thru_book_date:
            conditions.append( ('book_date', operator.le, thru_book_date ) )
        if associated_to_id:
            conditions.append( ('associated_to_id', operator.eq, associated_to_id ) )
        if within_id:
            conditions.append( ('within_id', operator.eq, within_id ) )

        query, params = self._get_total_amount_at_query( premium_schedule, conditions )
        total = self.session.connection( bind = self.entry_table.metadata.bind ).execute( query, **params ).first()
        
        return D(str(total[0] or 0)).quantize(ONE_HUNDREDTH),  (D(str(total[1] or 0)) / 1000).quantize(ONE_MILLIONTH), D(str(total[2] or 0)).quantize(ONE_HUNDREDTH)
        
    def get_total_amount_until( self, 
                                premium_schedule,
                                thru_document_date=None, 
                                thru_book_date=None, 
                                fulfillment_type=None, 
                                account=None,
                                associated_to_id = None,
                                within_id = None,
                                line_number = None,
                                from_document_date=None, 
                                from_book_date=None, 
                                conditions = []
                                ):
        """
        Get the total amount of booked entries of a certain fulfillment type until
        a certain date.
        
        :param premium_schedule: a FinancialAccountPremiumSchedule
        :param thru_document_date: date until which to get the total amounts
        :param thru_book_date: 
        :param fulfillment_type: the type of fulfillment for which to get the total, if None is given,
        return the total for all fulfillment types.
        :param account: the account for which to get the total, if None is given, return the total for
        all account
        :param within: a financial transaction premium schedule in which context this entry is taking place
        :param line_number: the line number of the entry within a document, this one should actually only
           be used to get the first line of a document, as this is the only one that does not change
           position
        :param conditions: tuples of additional conditions to be inserted in the
           query
        :return: (total_amount, total_quantity) the total_amount and quantity booked
        """
        assert isinstance( account, (BookingAccount, types.NoneType) )
        
        conditions = conditions + [ ('of_id', operator.eq, premium_schedule.history_of_id) ]
        if line_number != None:
            conditions.append( ('line_number', operator.eq, line_number ) )
        if thru_document_date:
            conditions.append( ('datum', operator.le, thru_document_date) )
        if thru_book_date:
            conditions.append( ('book_date', operator.le, thru_book_date ) )
        if fulfillment_type:
            conditions.append( ('fulfillment_type', operator.eq, fulfillment_type ) )
        if account:
            conditions.append( ('account', operator.eq, account ) )
        if associated_to_id:
            conditions.append( ('associated_to_id', operator.eq, associated_to_id ) )
        if within_id:
            conditions.append( ('within_id', operator.eq, within_id ) )
        if from_document_date:
            conditions.append( ('datum', operator.ge, from_document_date) )
        if from_book_date:
            conditions.append( ('book_date', operator.ge, from_book_date ) )
            
        query, params = self._get_total_amount_until_query( premium_schedule, conditions )
        total = self.session.connection( bind = self.entry_table.metadata.bind ).execute( query, **params ).first()

        return D(str(total[0] or 0)).quantize(ONE_HUNDREDTH),  (D(str(total[1] or 0)) / 1000).quantize(ONE_MILLIONTH), D(str(total[2] or 0)).quantize(ONE_HUNDREDTH)

    def distribute_amount(self, amount, distribution, total_target_percentage):
        """
        Distribute an amount in rounded portions.
        
        :param amount: the amount to distribute
        :param distribution: a list of (key, percentage) pairs
        :param total_target_percentage: 100 in case of distributing percentages,
            otherwise an other base
        :return: a (key, amount, percentage) generator
        """
        remaining_amount = amount
        # the same distribution key can appear multiple times in the distribution,
        # but the order of distribution needs to be preserved
        grouped_distributions = collections.OrderedDict()
        for key, percentage in distribution:
            # - if there is only one fund specified, it always counts as 100pct
            # - don't take into account distributions of 0 pct
            if (percentage == 0) and len(distribution) > 1:
                continue
            grouped_distributions.setdefault(key, []).append(percentage)
        for i, (key, percentages) in enumerate(grouped_distributions.iteritems()):
            target_percentage = sum(percentages)
            if i != len(grouped_distributions) - 1:
                distributed_amount = D(amount * target_percentage/total_target_percentage).quantize(ONE_HUNDREDTH, rounding=decimal.ROUND_DOWN)
            else:
                distributed_amount = remaining_amount
            
            remaining_amount = remaining_amount - distributed_amount
            yield key, distributed_amount, target_percentage

    def fulfillment_data_from_entry_data( self, premium_schedule, entry, fulfillment_type, associated_to_id=None, within_id=None, 
                                          from_date=sql.func.current_date(), thru_date=end_of_times(), booking_of_id=None ):
        """Create an FinancialAccountPremiumFulfillment for a premium schedule and an Entry
        :param associated_fulfillment: the newly generated fulfillment will be associated with this
        fulfillment.
        :param from/thru_date: the range of dates in which this fulfillment is valid, defaults to from today till end of times
        """
        insert = self.fapf_table.insert()
        insert = insert.values( of_id = premium_schedule.history_of_id,
                                entry_book_date = entry.book_date,
                                entry_document = entry.document,
                                entry_book = entry.book,
                                entry_line_number = entry.line_number,
                                fulfillment_type = fulfillment_type,
                                associated_to_id = associated_to_id,
                                within_id = within_id,
                                from_date = from_date,
                                thru_date = thru_date,
                                booking_of_id = booking_of_id )
        orm.object_session( premium_schedule ).execute( insert )

    def create_line(self, account, amount, remark, fulfillment_type=None, associated_fulfillment_id=None, quantity=0, within_id=None, booking_of_id=None):
        """Create a line of a sales document that can be fed to the create_sales
        method.
        
        :param account: an object of type :class:`BookingAccount`
        :param within: the financial transaction premium schedule associated to 
        this line
        :param booking_of_id: the id of the invoice item that is booked
        """

        assert isinstance(account, BookingAccount)

        return FulfilledSalesLine(account = account,
                                  amount = amount,
                                  remark = remark,
                                  fulfillment_type = fulfillment_type,
                                  associated_to_id = associated_fulfillment_id,
                                  quantity = quantity,
                                  within_id = within_id,
                                  booking_of_id = booking_of_id)

    def create_customer_request(self, premium_schedule, roles):
        package = premium_schedule.financial_account.package
        party_requests = []
        names = [role.name for role in roles]
        
        for role in roles:
            party_request = PartyRequest()
            if role.person_id is not None:
                party_request.person_id = role.person_id
            elif role.organization_id is not None:
                party_request.organization_id = role.organization_id
            party_requests.append(party_request)
            
        return CreateCustomerAccountRequest(from_number=package.from_customer,
                                            thru_number=package.thru_customer,
                                            parties=party_requests,
                                            name=u', '.join(names))


    def _validate_book(self, book, premium_schedule, fulfillment_type):
        if not book:
            raise UserException( text = ugettext('No book defined for booking'),
                                 resolution = ugettext('''Please complete the product configuration of %s'''
                                                       '''to include a book for bookings of type %s''')%( premium_schedule.product, fulfillment_type ) )

    def _transform_lines(self, lines, premium_schedule, book_date):
        #
        # replace account object in lines with account numbers
        #
        for line in lines:
            booking_number = line.account.booking_account_number_at( premium_schedule, book_date )
            line.account = booking_number
        #
        # filter lines without accounts, to enable the skipping of bookings
        # by not entering account numbers in the product definition
        #
        lines = [line for line in lines if line.account]
        for line in lines:
            assert line.account.isdigit()
        total_line_amount = sum(line.amount for line in lines if line.account)
        return lines, total_line_amount

    def _default_remark(self, remark, premium_schedule):
        if remark is None:
            return ''.join(premium_schedule.agreement_code)
        return remark

    def _insert_fulfillment_data(self, document_request, premium_schedule, from_date, thru_date):
        if not document_request.document_number:
            raise Exception('Document should have a document number')
        fulfillment_data = []
        for sales_line in document_request.lines:
            if sales_line.fulfillment_type != 0:
                fulfillment_data.append(dict(entry_line_number = sales_line.line_number,
                                             fulfillment_type = sales_line.fulfillment_type,
                                             associated_to_id = sales_line.associated_to_id,
                                             within_id = sales_line.within_id,
                                             booking_of_id = sales_line.booking_of_id
                                         ))
        fapf_table = self.fapf_table
        fapf_insert = fapf_table.insert().values(from_date=from_date,
                                                 thru_date=thru_date,
                                                 of_id = premium_schedule.history_of_id,
                                                 entry_book_date = document_request.book_date,
                                                 entry_document = document_request.document_number,
                                                 entry_book = document_request.book)
        LOGGER.debug('insert fulfillment data')
        self.session.connection(bind=fapf_table.metadata.bind ).execute(fapf_insert, fulfillment_data)
        LOGGER.debug('inserted fulfillment data')
        
    def create_purchase(self,
                        premium_schedule,
                        book_date,
                        document_date,
                        lines,
                        purchase_book,
                        fulfillment_type,
                        supplier_type,
                        from_date = sql.func.current_date(),
                        thru_date = end_of_times(),
                        remark = None):
        """
        Create a :class:`vfinance.connector.accounting.CreatePurchaseDocumentRequest
        object.

        :param premium_schedule: a `FinancialAccountPremiumSchedule`
        :param lines: a list of `LineRequest` objects
        :param supplier_type: the type of supplier to use, eg `broker`
        :param fulfillment_type: the fulfillment type of the 0th line in the,
            this can only be None when the amount of the 0th line is 0
        :from_date: the date at which this booking becomes visible to the premium
            schedule
        :thru_date: the data at which this booking stops being visible to the premium
            schedule
        :param remark: the remark to use at the document level

        yields a `CreatePurchaseDocumentRequest` that should be registered in the
        accounting system before continuing the iterator, which will then associate
        de purchase with the given premium schedule.
        """
        self._validate_book(purchase_book, premium_schedule, fulfillment_type)
        book_date = self.entered_book_date(document_date, book_date)
        broker_relation = premium_schedule.financial_account.get_broker_at(document_date)
        if broker_relation is None:
            raise UserException('No broker relation defined at {0}'.format(document_date))
        supplier_request = self.create_supplier_request(premium_schedule, broker_relation, supplier_type)
        yield supplier_request
        lines, total_lines_amount = self._transform_lines(lines, premium_schedule, book_date)
        remark = self._default_remark(remark, premium_schedule)

        first_line = FulfilledSalesLine(
            amount = total_lines_amount * -1,
            remark = remark,
            account = str(int(self._settings.get('BANK_ACCOUNT_SUPPLIER', None)) + supplier_request.accounting_number),
            quantity = 0,
            fulfillment_type = fulfillment_type,
            associated_to_id = None,
            within_id = None,
            booking_of_id = None
        )
        purchase_document = CreatePurchaseDocumentRequest(
            book_date=book_date,
            document_date=document_date,
            book=purchase_book,
            lines=[first_line] + lines
        )
        yield purchase_document
        self._insert_fulfillment_data(purchase_document, premium_schedule, from_date, thru_date)

    def _expand_entries_to_documents(self, connection, premium_schedule, entries):
        """
        expand the entries with associated entries, and other entries in the
        same document.

        :return: an iterator over documents or status updates
        """
        # refetch the entries from the database, since a previous query might have
        # modified them
        entry_ids = set(e.id for e in entries)
        if not len(entry_ids):
            raise StopIteration
        execute = connection.execute
        entry_query = self._entry_query
        entry_query = entry_query.column(self.fapf_table.c.of_id.label('of_id'))
        entry_from_id_query = entry_query.where(self.entry_table.c.id.in_(entry_ids))
        entry_dict = dict()
        for entry in execute(entry_from_id_query):
            entry_dict[entry.id] = entry
        if not len(entry_dict):
            raise StopIteration
        previous_entries_length = 0
        while len(entry_dict) != previous_entries_length:
            previous_entries_length = len(entry_dict)
            fulfillment_ids = list(e.fulfillment_id for e in entry_dict.itervalues())
            new_entry_query = entry_query.where(sql.not_(
                self.fapf_table.c.id.in_(fulfillment_ids)
                ))
            associated_entries = list()
            for entry in entry_dict.itervalues():
                # expand with entries associated to existing entries
                associated_entry_query = new_entry_query.where(
                    self.fapf_table.c.associated_to_id==entry.fulfillment_id
                )
                associated_entries.extend(execute(associated_entry_query))
                # expand with entries in the same document
                same_document_query = new_entry_query.where(sql.and_(
                    self.fapf_table.c.entry_book_date== entry.book_date,
                    sql.func.lower(self.fapf_table.c.entry_book)== entry.book.lower(),
                    self.fapf_table.c.entry_document== entry.document,
                    ))
                associated_entries.extend(execute(same_document_query))
                for associated_entry in associated_entries:
                    if associated_entry.of_id != premium_schedule.history_of_id:
                        raise UserException(
                            text=ugettext('Document cannot be handled because it refers to multiple premium schedules'),
                            detail=ugettext('{0.book_date} {0.book} {0.document} refers to premium schedule {1.history_of_id} and {2.of_id}').format(
                                entry,
                                premium_schedule,
                                associated_entry),
                            resolution=ugettext('Run backward both premium schedules upto the book date before continuing'))
                
            for entry in associated_entries:
                entry_dict[entry.id] = entry

        def document_key(entry):
            return (entry.book_date, entry.book.lower(), entry.document, entry.doc_date)

        #
        # group entries into documents
        #
        documents = collections.defaultdict(list)
        for entry in entry_dict.itervalues():
            documents[document_key(entry)].append(entry)

        #
        # order documents in order of dependency
        #
        def find_document_keys_with_no_associations():
            entries_with_associations = set()
            for entries in documents.itervalues():
                for entry in entries:
                    entries_with_associations.add(entry.associated_to_id)
            for key, entries in documents.iteritems():
                for entry in entries:
                    if entry.fulfillment_id in entries_with_associations:
                        break
                else:
                    yield key

        number_of_documents = None
        while len(documents):
            keys = list(find_document_keys_with_no_associations())
            for key in keys:
                entries = documents.pop(key)
                entries.sort(key=lambda line:line.line_number)
                yield key, entries
            if len(documents) == number_of_documents:
                raise Exception('Could not sort documents in order of dependency')
            number_of_documents = len(documents)

    def create_remove_request(self, premium_schedule, entries):
        """
        Create accounting requests to remove a set of entries from the accounting
        system.
        
        :param premium_schedule: the schedule to which the entries are related
        :param entries: an iterator over entries, as returned by `get_entries`
        
        :return: an iterator over accounting requests or status updates
        """
        connection = self.session.connection(bind=self.fapf_table.metadata.bind )
        documents = self._expand_entries_to_documents(
            connection, premium_schedule, entries)
        fapf_delete = self.fapf_table.delete()
        fapf_c = self.fapf_table.c
        for (book_date, book, document_number, document_date), lines in documents:
            self.accounting_period.validate_dates(book_date, document_date)
            request = RemoveDocumentRequest(book_date = book_date,
                                            document_date = document_date,
                                            document_number = document_number,
                                            book = book)
            yield request
            if not len(request.lines):
                raise UserException(u'Document not found in accounting system',
                                    detail='{0.book_date} {0.document_number}'.format(request),
                                    resolution='Run the accounting audit report to inspect possible inconsistenties between V-Finance and the accounting system')
            document_fapf_delete = fapf_delete.where(sql.and_(
                fapf_c.entry_book_date == request.book_date,
                fapf_c.entry_document == request.document_number,
                sql.func.lower(fapf_c.entry_book) == request.book.lower()
                ))
            connection.execute(document_fapf_delete)

    def create_sales(self, premium_schedule, book_date, document_date, total_amount, lines, sales_book, fulfillment_type, 
                     associated_fulfillment_id=None, within_id=None,
                     from_date = sql.func.current_date(), thru_date = end_of_times(),
                     balance_check = D('0.000000000001'), remark=None, booking_of_id=None):
        """
        Create a sales for the customer associated with the premium schedule.
        
        :param premium_schedule: a `FinancialAccountPremiumSchedule`
        :param total_amount: the total amount to be sold
        :param lines: different lines of the transaction, the first part
            should be the sales.  the lines should be created with the create_line
            method
        :param fulfillment_type: the fulfillment type of the 0th line in the, this can only be None
            when the amount of the 0th line is 0
            booking, being the sales on the customer account
        :param associated_fulfillment: the associated fulfillment of the 0th 
            line
        :param within: the financial transaction premium schedule that causes
            the 0th line
        :param balance_check: the maximal difference between credit and debit,
            can be nonzero to revert old bookings
        :from_date: the date at which this booking becomes visible to the premium
            schedule
        :thru_date: the data at which this booking stops being visible to the premium
            schedule
        :param remark: the remark to use at the document level
        :param booking_of_id: the invoice item that is booked
        
        yields a SalesDocument that should be registered in the accounting system
        before continuing.
        """
        self._validate_book(sales_book, premium_schedule, fulfillment_type)
        book_date = self.entered_book_date(document_date, book_date)
        customer = self.get_customer_at(premium_schedule, document_date)
        transformed_lines, total_line_amount = self._transform_lines(lines, premium_schedule, book_date)
        #
        # debit equals credit check
        #
        if abs(total_line_amount + total_amount)  >= balance_check:
            for line in lines:
                LOGGER.error( unicode( line ) )
            raise Exception('Total of lines different from document total : %s != %s'%(total_line_amount, total_amount) )
        remark = self._default_remark(remark, premium_schedule)

        first_line = FulfilledSalesLine(
            amount = total_amount,
            remark = remark,
            account = customer.full_account_number,
            quantity = 0,
            fulfillment_type = fulfillment_type,
            associated_to_id = associated_fulfillment_id,
            within_id = within_id,
            booking_of_id = booking_of_id
        )
        sales_document = CreateSalesDocumentRequest(
            book_date=book_date,
            document_date=document_date,
            book=sales_book,
            lines=[first_line] + transformed_lines
        )
        yield sales_document
        self._insert_fulfillment_data(sales_document, premium_schedule, from_date, thru_date)


    def get_booking_account(self, premium_schedule, account_number, book_date):
        """This method is called within the `create_revert_request` method, and
        should be implemented in subclasses that want to allow reverting of bookings.
        
        This method should look at an account number and should return the 
        BookingAccount object that corresponds to this account.
        
        :param premium_schedule: a FinancialAccountPremiumSchedule
        :param account_number: the account number on which a booking was made
        :param book_date: the book date of the original sales document
        """
        return None
    
    def create_revert_request(self, premium_schedule, entries):
        """
        Create accounting requests to revert a set of entries from the accounting
        system.
        
        :param premium_schedule: the schedule to which the entries are related
        :param entries: an iterator over entries, as returned by `get_entries`
        
        :return: an iterator over accounting requests or status updates
        """
        connection = self.session.connection(bind=self.entry_table.metadata.bind)
        documents = self._expand_entries_to_documents(
            connection, premium_schedule, entries)
        fapf_columns = self.fapf_table.columns
        thru_date = date_sub( self._valid_at, 1 )
        update_query = self.fapf_table.update().values(thru_date=thru_date)

        for (book_date, book, document_number, document_date), lines in documents:

            reverted_lines = []
            first_line = None
            document_type = None
            document_supplier_type = None

            for entry in lines:
                booking_account = self.get_booking_account(premium_schedule, entry.account, entry.book_date)
                if booking_account is None:
                    raise UserException('Could not revert document due to unknown account',
                                        detail='{0.book_date} {0.book} {0.document} {0.account}'.format(entry),
                                        resolution='Verify the product and package configuration')
                if isinstance(booking_account, CustomerBookingAccount):
                    document_type = 'sales'
                elif isinstance(booking_account, SupplierBookingAccount):
                    document_type = 'purchase'
                    broker_relation = premium_schedule.financial_account.get_broker_at(document_date)
                    accounting_number = int(entry.account[-len(str(premium_schedule.financial_account.package.thru_supplier)):])
                    for supplier_type in ['broker', 'master_broker']:
                        supplier_request = self.create_supplier_request(premium_schedule, broker_relation, supplier_type)
                        if supplier_request is not None:
                            yield supplier_request
                            if supplier_request.accounting_number == accounting_number:
                                document_supplier_type = supplier_type
                                break
                    else:
                        raise Exception('No supplier found at document date')
    
                connection.execute(
                  update_query.where(fapf_columns.id==entry.fulfillment_id)
                )
                if entry.line_number == 1:
                    first_line = entry
                    continue
    
                reverted_lines.append(self.create_line(booking_account,
                                                       entry.amount * -1,
                                                       remark = 'revert {0.book} {0.book_date} {0.document} line {0.line_number}'.format(entry),
                                                       fulfillment_type = entry.fulfillment_type,
                                                       associated_fulfillment_id = entry.associated_to_id,
                                                       quantity = entry.quantity * -1,
                                                       within_id = entry.within_id,
                                                       booking_of_id = entry.booking_of_id))

            if len(reverted_lines):
                if document_type is None:
                    raise UserException('Unknown document type',
                                        detail='{0} {1} {2}'.format(book_date, book, document_number))
                # If there is no first line, the document amount should be 0
                document_amount = 0
                fulfillment_type = None
                associated_fulfillment = None
                within_transaction = None
                booking_of_id = None
                if first_line != None:
                    document_amount = first_line.amount * -1
                    fulfillment_type = first_line.fulfillment_type
                    associated_fulfillment = first_line.associated_to_id
                    within_transaction = first_line.within_id
                    booking_of_id = first_line.booking_of_id
                # old bookings that need to be reverted might have lines
                # with more than 2 digits after the decimal point, resulting in
                # a difference between credit and debit
                if document_type == 'sales':
                    for step in self.create_sales( premium_schedule, 
                                                   book_date, 
                                                   document_date,
                                                   document_amount, 
                                                   reverted_lines,
                                                   book,
                                                   fulfillment_type,
                                                   associated_fulfillment,
                                                   within_transaction,
                                                   thru_date = thru_date,
                                                   balance_check=D('0.01'),
                                                   booking_of_id=booking_of_id):
                        yield step
                elif document_type == 'purchase':
                    for step in self.create_purchase(premium_schedule,
                                                     book_date,
                                                     document_date,
                                                     reverted_lines,
                                                     book,
                                                     fulfillment_type,
                                                     document_supplier_type,
                                                     thru_date=thru_date):
                        yield step
                else:
                    raise Exception('Unhandled document type')

