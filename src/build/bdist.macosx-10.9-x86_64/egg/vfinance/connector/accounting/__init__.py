"""
The accounting module registers bookings in the internal database as well as in
external applications.  They operate on a less abstract level than the visitors.
The accounting modules have no knowledge of product data or the meaning of the
bookings they register.
"""

import datetime
import itertools
import logging
import threading

from sqlalchemy import sql, types

from camelot.core.exception import UserException

from ...model.bank.account import Account
from ...model.bank.customer import SupplierAccount, CustomerAccount
from ...model.bank.entry import Entry
from ...model.bank.natuurlijke_persoon import NatuurlijkePersoon
from ...model.bank.rechtspersoon import Rechtspersoon
from ...sql import year_part

LOGGER = logging.getLogger('vfinance.connector.accounting')

class AccountingSingleton(object):
    """
    Singleton class for an accounting connector.  Upon construction, this class
    returns the appropriate connector for the given context.
    """

    accounting_connector = None
    document_numbers = None

    @classmethod
    def set_document_numbers(cls, document_numbers):
        """Calling this method invalidates the current accounting connector"""
        cls.document_numbers = document_numbers
        cls.accounting_connector = None

    def __new__(cls):
        from ..venice.accounting import VeniceAccounting
        if cls.document_numbers is None:
            cls.document_numbers = DocumentNumbers(dict(), threading.RLock())
        if cls.accounting_connector is None:
            cls.accounting_connector = VeniceAccounting(cls.document_numbers)
        return cls.accounting_connector

class AccountingRequest(object):
    """
    All requests to the accounting system should subclass this class, to signal
    they are a request to the accounting system.
    """
    pass

class DocumentRequest(AccountingRequest):
    """
    Base class for all requests that involve a document
    """

    __slots__ = ['book_date', 'document_date', 'document_number', 'book', 'lines', 'book_type']
    verbose_request_type = u''
    
    def __init__(self, **kwargs):
        kwargs.setdefault('document_number', None)
        kwargs.setdefault('lines', [])
        for k,v in kwargs.items():
            setattr(self, k, v)

    def __unicode__(self):
        return u'{1.verbose_request_type} {0.year}-{0.month:02d}-{0.day:02d} : {1.book} {1.document_number} {1.amount}'.format(self.book_date, self)
    
    @property
    def amount(self):
        """The amount of the first line in the document"""
        for line in self.lines:
            return line.amount

    @property
    def remark(self):
        """The remark of the first line in the document"""
        for line in self.lines:
            return line.remark

    @property
    def account(self):
        """The account of the first line in the document"""
        for line in self.lines:
            return line.account

    @property
    def first_line_number(self):
        """The account of the first line in the document, or `None` if there
        are no lines"""
        if len(self.lines):
            return min(line.line_number for line in self.lines)

    @property
    def last_line_number(self):
        """The account of the first line in the document, or `None` if there
        are no lines"""
        if len(self.lines):
            return max(line.line_number for line in self.lines)

class FreezeDocumentRequest(DocumentRequest):
    """
    A request to freeze a document in the accounting system, this means no future
    modifications are allowed.
    """

    verbose_request_type = u'Freeze'

class CreateSalesDocumentRequest(DocumentRequest):
    """
    A request to register a sales document in the accounting system.
    """

    verbose_request_type = u'Create sales'

    def __init__(self, **kwargs):
        super(CreateSalesDocumentRequest, self).__init__(book_type='V', **kwargs)

class CreatePurchaseDocumentRequest(DocumentRequest):
    """
    A request to register a purchase document in the accounting system.
    """

    verbose_request_type = u'Create purchase'

    def __init__(self, **kwargs):
        super(CreatePurchaseDocumentRequest, self).__init__(book_type='A', **kwargs)

class UpdateDocumentRequest(DocumentRequest):
    """
    A request to update a document in the accounting system.
    """

    verbose_request_type = u'Update'

class RemoveDocumentRequest(DocumentRequest):
    """
    A request to remove a document from the accounting system
    """

    verbose_request_type = u'Remove'

class LineRequest(object):
    """
    Either a line within a create request, or a request to modify an existing line
    within an update request.
    """

    __slots__ = ['account', 'remark', 'amount', 'quantity', 'line_number']

    def __init__(self, **kwargs):
        self.line_number = None
        kwargs.setdefault('line_number', None)
        kwargs.setdefault('remark', u'')
        for k,v in kwargs.items():
            setattr(self, k, v)

    def __unicode__( self ):
        return u'  {0.account:15s} {0.amount:15.2f} {0.remark}'.format(self)

class AccountRequest(AccountingRequest):
    """
    Base class for all requests that involve a booking account
    """

    __slots__ = ['name', 'from_number', 'thru_number', 'step', 'accounting_number']
    described_by = u''

    def __init__(self, **kwargs):
        kwargs.setdefault('step', 1)
        for k in self.__slots__:
            setattr(self, k, kwargs.get(k))

    def __unicode__(self):
        return u'{0.described_by} account in range {0.from_number}-{0.thru_number} : {0.name}'.format(self)

class CreateAccountRequest(AccountRequest):
    """
    Create a general account
    """

    __slots__ = AccountRequest.__slots__
    described_by = u'General'

class PartyRequest(object):
    """A party within an account request"""
    
    __slots__ = ['person_id', 'organization_id']

    def __init__(self, **kwargs):
        for k in self.__slots__:
            setattr(self, k, kwargs.get(k))

class CreateSupplierAccountRequest(AccountRequest):
    """
    Request a supplier account
    """

    __slots__ = AccountRequest.__slots__ + PartyRequest.__slots__
    described_by = u'Supplier'

class CreateCustomerAccountRequest(AccountRequest):
    """
    Create a customer account
    """
    
    __slots__ = AccountRequest.__slots__ + ['parties']
    described_by = u'Customer'

class DocumentNumbers(object):
    """
    Helper class to assign document numbers and keep track of them

    :param last_document_numbers: a ditionary with the last document numbers used
    :param document_numbers_lock: a lock that should be hold before modifying the
       last_document_numbers dictionary.
    """

    def __init__(self,
                 last_document_numbers,
                 document_numbers_lock):
        self._last_document_numbers = last_document_numbers
        self._document_numbers_lock = document_numbers_lock

    def set_minimum_document_number(self, key, value):
        """Make sure the next document number is larger then the given value"""
        with self._document_numbers_lock:
            last_document_number = self._last_document_numbers.get(key, 0)
            self._last_document_numbers[key] = max(value, last_document_number)

    def get_next_document_number(self, key, step=1):
        """Get the next document number for a given value, and increase the
        value for the next caller.
        Raises a KeyError if no `set_minimum_document_number` has been called for
        this key.
        """
        with self._document_numbers_lock:
            last_document_number = self._last_document_numbers[key] + step
            self._last_document_numbers[key] = last_document_number
            return last_document_number

    @property
    def lock(self):
        """
        A `Lock` that can be used to prevent access to the documents
        from different processes.
        """
        return self._document_numbers_lock

class InternalAccounting(object):
    """
    A connector that emulates an accounting system.  This connector also serves as an
    interface definition for other accounting connectors.
    
    Use the `register_request` method to ask the accounting system to put an
    accounting request in it's queue of requests to handle.
    
    All requests in the queue will be written to disk when the `commit` call is
    finished.
    
    Subclass this connector to connect to a real accounting system.
    """

    def __init__(self,
                 document_numbers,
                 entry_table = None,
                 ):
        self._session = None
        self.document_numbers = document_numbers
        self.uncommitted_documents = None
        if entry_table is None:
            entry_table = Entry.__table__
        self.entry_table = entry_table
        entry_c = entry_table.c
        p = sql.bindparam
        self.entry_insert = self.entry_table.insert(values=dict(
            ticked  =  False,
            accounting_state = 'draft')
        )
        self.entry_condition = Entry.entry_condition(
            entry_c,
            book_date=p('r_book_date'),
            book=p('r_book'),
            document_number=p('r_document_number'),
            line_number=p('r_line_number'),
            )
        self.document_condition = Entry.document_condition(
            entry_c,
            book_date=p('r_book_date'),
            book=p('r_book'),
            document_number=p('r_document_number'),
        )
        entry_update = self.entry_table.update().values(account=p('r_account'))
        self.entry_update = entry_update.where(self.entry_condition)
        entry_select = sql.select([entry_c.id], for_update=True)
        self.entry_select = entry_select.where(self.entry_condition)
        document_select = sql.select([entry_c.id,
                                      entry_c.account,
                                      entry_c.remark,
                                      entry_c.amount,
                                      entry_c.quantity,
                                      entry_c.line_number,
                                      entry_c.accounting_state,
                                      entry_c.venice_book_type],
                                     for_update=True)
        document_select= document_select.order_by(entry_c.line_number.desc())
        self.document_select = document_select.where(self.document_condition)
        document_remove = self.entry_table.delete()
        self.document_remove = document_remove.where(self.document_condition)
        document_freeze = self.entry_table.update()
        document_freeze = document_freeze.values(accounting_state=u'frozen')
        self.document_freeze = document_freeze.where(self.document_condition)

    def begin(self, session):
        """
        Begin a new transaction in the accounting system, synchronized with a session
        transaction.
        
        :param session: a session
        """
        if self._session is not None:
            raise Exception('An accounting transaction has been started before')
        session.begin()
        self._session = session
        self._last_database_document_numbers = dict()
        self.uncommitted_documents = []
        return self

    def _check_transaction(self):
        if self._session is None:
            raise Exception('An accounting transaction has not yet been started')

    def _check_sales_document(self, sales_document):
        if sales_document.document_number is not None:
            raise Exception('Sales document has a document number')
        total_amount = 0
        if not len(sales_document.lines):
            raise Exception('Sales document has no lines')
        for line in sales_document.lines:
            assert isinstance(line.account, basestring)
            if line.line_number is not None:
                raise Exception('Sales document line has a line number')
            total_amount += line.amount
        #if total_amount != 0:
            #raise Exception('Sum of lines in sales document is not zero')

    def _check_update_request(self, update_request):
        if update_request.document_number is None:
            raise Exception('Update request has no document number')
        for line in update_request.lines:
            if line.line_number is None:
                raise Exception('Update request line has no line number')

    def _check_remove_request(self, remove_request):
        if remove_request.document_number is None:
            raise Exception('Remove request has no document number')
        if len(remove_request.lines):
            raise Exception('Remove request should have no lines')

    def _check_account_request(self, account_request):
        if account_request.accounting_number is not None:
            raise Exception('Account request has an accounting number')
        if account_request.name is None:
            raise Exception('Requested account should have a name')
        if account_request.from_number is None:
            raise Exception('Requested account should have a from_number')
        if account_request.thru_number is None:
            raise Exception('Requested account should have a thru_number')
        if account_request.from_number <= 0:
            raise Exception('Start of account range should be larger than 0')
        if account_request.thru_number <= 0:
            raise Exception('End of account range should be larger than 0')

    def _check_create_supplier_account_request(self, account_request):
        self._check_account_request(account_request)
        self._check_party_request(account_request)
    
    def _check_party_request(self, party_request):
        if (party_request.person_id is None) and (party_request.organization_id is None):
            raise Exception('Party request should have a person or an organization')
    
    def _check_create_customer_account_request(self, account_request):
        self._check_account_request(account_request)
        if not len(account_request.parties):
            raise Exception('Customer account should be related to a party')
        for party_request in account_request.parties:
            self._check_party_request(party_request)

    def _connection(self):
        return self._session.connection(bind=self.entry_table.metadata.bind)

    def _entry_condition_kwargs(self, accounting_request, line_request):
        return dict(
            r_account=line_request.account,
            r_book_date = accounting_request.book_date,
            r_document_number = accounting_request.document_number,
            r_book = accounting_request.book,
            r_line_number = line_request.line_number)

    def _document_condition_kwargs(self, accounting_request):
        return dict(
            r_book_date = accounting_request.book_date,
            r_document_number = accounting_request.document_number,
            r_book = accounting_request.book)

    def get_last_document_number(self, book_year, book):
        """
        Get the last document number that was committed or registered to
        the accounting system.
        
        :return: an integer document number or 0 if no number has been registered yet
        """
        self._check_transaction()
        key = (book_year, book.lower())
        try:
            return self._last_database_document_numbers[key]
        except KeyError:
            #
            # get the max doc for all books at once, since this query takes
            # the same amount of time as getting it for a single book
            #
            self._last_database_document_numbers[key] = 0
            book_date = datetime.date(book_year, 1, 1)
            entry_c = self.entry_table.columns
            max_doc_num = sql.func.max(entry_c.venice_doc)
            entry_book_year = year_part(self.entry_table.c.book_date)
            last_numbers_select = sql.select([max_doc_num.label('entry_doc'),
                                              entry_c.venice_book.label('entry_book'),
                                              entry_book_year.label('entry_book_year')])
            last_numbers_select = last_numbers_select.where(entry_book_year==year_part(book_date))
            last_numbers_select = last_numbers_select.group_by(entry_c.venice_book,
                                                               entry_book_year)
            for row in self._connection().execute(last_numbers_select):
                # different rows in the result set might map to the same key,
                # so even if there was no initial data, we need to check this after
                # each new row
                row_key = (int(row.entry_book_year), row.entry_book.lower())
                previous_doc = self._last_database_document_numbers.get(row_key, 0)
                self._last_database_document_numbers[row_key] = max(previous_doc,
                                                                    row.entry_doc)
        return self._last_database_document_numbers[key]

    def get_last_supplier_numbers(self, from_number, thru_number):
        return {'v-finance': self._get_last_internal_accounting_number(SupplierAccount, from_number, thru_number)}

    def get_last_customer_numbers(self, from_number, thru_number):
        return {'v-finance': self._get_last_internal_accounting_number(CustomerAccount, from_number, thru_number)}

    def get_last_account_number(self, from_number, thru_number):
        q = self._session.query( sql.func.max( sql.expression.cast(Account.number, types.BigInteger) ) )
        q = q.filter( sql.expression.cast(Account.number, types.BigInteger) >= from_number )
        q = q.filter( sql.expression.cast(Account.number, types.BigInteger) <= thru_number )
        last_internal_number = q.scalar()
        LOGGER.debug('last database number : {0}'.format(last_internal_number))
        return last_internal_number

    def _get_last_internal_accounting_number(self, cls, from_number, thru_number):
        """
        :return: the last internal number used, or `None`
        """
        max_accounting_number = sql.select([sql.func.max(cls.accounting_number)])
        max_accounting_number = max_accounting_number.where(cls.accounting_number >= from_number)
        max_accounting_number = max_accounting_number.where(cls.accounting_number <= thru_number)
        last_internal_number = self._session.execute(max_accounting_number).scalar()
        LOGGER.debug('last database number : {0}'.format(last_internal_number))
        return last_internal_number

    def _next_number_from_last_numbers(self, number_type, last_numbers, from_number, thru_number, step):
        """
        :param last_numbers: dict with last number in various systems
        """
        key = (number_type, from_number, thru_number)
        try:
            next_number = self.document_numbers.get_next_document_number(key, step=step)
        except KeyError:
            last_number_list = list(v for v in last_numbers.values() if (v is not None))
            last_number_list.append(from_number - step)
            last_number = max(last_number_list)
            self.document_numbers.set_minimum_document_number(key, last_number)
            next_number = self.document_numbers.get_next_document_number(key, step)
        if next_number > thru_number:
            detail = u'<br/>'.join(['{0} : {1}'.format(k,v) for k,v in last_numbers.items()])
            raise UserException('Range between {0} and {1} is exhausted'.format(from_number, thru_number),
                                detail = detail)
        return next_number

    def assign_document_number(self, sales_document):
        """
        Assign a non temporary document number for a sales document.  This number
        becomes the actual number when the transaction is committed.
        """
        
        book_year = sales_document.book_date.year
        book = sales_document.book
        key = (book_year, book.lower())
        try:
            next_document_number = self.document_numbers.get_next_document_number(key)
        except KeyError:
            last_registered_document_number = self.get_last_document_number(book_year, book)
            self.document_numbers.set_minimum_document_number(key, last_registered_document_number)
            next_document_number = self.document_numbers.get_next_document_number(key)
        sales_document.document_number = next_document_number

    def assign_line_numbers(self, sales_document):
        line_counter = itertools.count(1)
        for sales_line in sales_document.lines:
            sales_line.line_number = line_counter.next()

    def commit(self):
        """
        Commit a transaction in the accounting system, synchronized with a
        session transaction.
        """
        self._check_transaction()
        self._session.commit()
        self._session = None

    def rollback(self):
        """
        Rollback a transaction in the accounting system, synchronized with a
        session transaction.
        """
        self._check_transaction()
        self._session.rollback()
        self._session = None
        for request in self.uncommitted_documents:
            if isinstance(request, DocumentRequest):
                request.document_number = None
                for line in request.lines:
                    line.line_number = None
            elif isinstance(request, AccountRequest):
                request.full_account_number = None

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type != None:
            LOGGER.info('rollback accounting transaction',
                         exc_info = (exc_type, exc_val, exc_tb))
            self.rollback()
        else:
            try:
                self.commit()
            except:
                self.rollback()
                raise
        return False

    def register_request(self, accounting_request):
        """
        Register a sales document in the accounting system.
        
        This call will assign a document number to the sales document and line
        numbers to the lines within the sales document
        
        :return: `True` if the request is now pending in the queue, `False` if the
            request is not peding (because there was nothing to do)
        """
        assert isinstance(accounting_request, AccountingRequest)
        with self.document_numbers.lock:
            #
            # though the document number lock is held at this point, this does not mean
            # all concurrent transactions on the tables are committed.  as such rows
            # might still be locked, and thus an operational error might be thrown.
            # this means the current transaction is aborted, as such this error should
            # be handled at a higher level.
            #
            self._check_transaction()
            connection = self._connection()
            if isinstance(accounting_request, (CreateSalesDocumentRequest,
                                               CreatePurchaseDocumentRequest)):
                self._check_sales_document(accounting_request)
                self.assign_document_number(accounting_request)
                self.assign_line_numbers(accounting_request)
                entry_data = []
                for sales_line in accounting_request.lines:
                    entry_data.append(dict(
                        line_number  =  sales_line.line_number,
                        open_amount  =  sales_line.amount,
                        datum  =  accounting_request.document_date,
                        remark  =  sales_line.remark,
                        venice_doc  =  accounting_request.document_number,
                        account  =  sales_line.account,
                        amount  =  sales_line.amount,
                        book_date  =  accounting_request.book_date,
                        venice_book  = accounting_request.book,
                        venice_book_type = accounting_request.book_type,
                        quantity = sales_line.quantity,
                    ))
                connection.execute(self.entry_insert, entry_data)
                return self._append_request(accounting_request)
            elif isinstance(accounting_request, UpdateDocumentRequest):
                self._check_update_request(accounting_request)
                for line_request in accounting_request.lines:
                    kwargs = self._entry_condition_kwargs(accounting_request,
                                                          line_request)
                    count = len(list(connection.execute(self.entry_select, **kwargs)))
                    if count != 1:
                        raise Exception('No entry found to update')
                    connection.execute(self.entry_update, **kwargs)
                return self._append_request(accounting_request)
            elif isinstance(accounting_request, RemoveDocumentRequest):
                self._check_remove_request(accounting_request)
                kwargs = self._document_condition_kwargs(accounting_request)
                for i, row in enumerate(connection.execute(self.document_select,
                                                           **kwargs)):
                    accounting_request.book_type = row.venice_book_type
                    accounting_request.lines.append(LineRequest(account=row.account,
                                                                remark=row.remark,
                                                                amount=row.amount,
                                                                quantity=row.quantity,
                                                                line_number=row.line_number))
                    if row.accounting_state == 'frozen':
                        raise UserException(text = 'Cannot remove frozen booking',
                                            detail = 'Booking {0.book} {0.document_number} with book date {0.book_date} line {1.line_number}'.format(accounting_request, row),
                                            resolution = 'Verify if this booking should be removed')
                connection.execute(self.document_remove, **kwargs)
                return self._append_request(accounting_request)
            elif isinstance(accounting_request, FreezeDocumentRequest):
                self._check_remove_request(accounting_request)
                kwargs = self._document_condition_kwargs(accounting_request)
                connection.execute(self.document_freeze, **kwargs)
            elif isinstance(accounting_request, CreateSupplierAccountRequest):
                self._check_create_supplier_account_request(accounting_request)
                organization = self._session.query(Rechtspersoon).get([accounting_request.organization_id])
                person = self._session.query(NatuurlijkePersoon).get([accounting_request.person_id])
                if (person is None) and (organization is None):
                    raise Exception('Person nor Organization found')
                account = SupplierAccount.find_by_dual_person(person,
                                                              organization,
                                                              accounting_request.from_number,
                                                              accounting_request.thru_number)
                if account is None:
                    # lock the organisation or person when a supplier should be created
                    organization = self._session.query(Rechtspersoon).with_for_update(nowait=True).get([accounting_request.organization_id])
                    person = self._session.query(NatuurlijkePersoon).with_for_update(nowait=True).get([accounting_request.person_id])
                    account = SupplierAccount(rechtspersoon=organization, natuurlijke_persoon=person)
                    last_numbers = self.get_last_supplier_numbers(accounting_request.from_number,
                                                                  accounting_request.thru_number)
                    account.accounting_number = self._next_number_from_last_numbers('supplier',
                                                                                    last_numbers,
                                                                                    accounting_request.from_number,
                                                                                    accounting_request.thru_number,
                                                                                    accounting_request.step)
                    accounting_request.accounting_number = account.accounting_number
                    self._session.flush()
                    return self._append_request(accounting_request)
                else:
                    accounting_request.accounting_number = account.accounting_number
            elif isinstance(accounting_request, CreateCustomerAccountRequest):
                self._check_create_customer_account_request(accounting_request)
                from_customer, thru_customer = accounting_request.from_number, accounting_request.thru_number
                account = CustomerAccount.find_by_dual_persons(accounting_request.parties, from_customer, thru_customer)
                if account is None:
                    # lock the organisations or persons when a customer should be created
                    for party in accounting_request.parties:
                        self._session.query(Rechtspersoon).with_for_update(nowait=True).get([party.organization_id])
                        self._session.query(NatuurlijkePersoon).with_for_update(nowait=True).get([party.person_id])
                    account = CustomerAccount.create_by_dual_persons(accounting_request.parties, from_customer, thru_customer)
                    last_numbers = self.get_last_customer_numbers(accounting_request.from_number,
                                                                  accounting_request.thru_number)
                    account.accounting_number = self._next_number_from_last_numbers('customer',
                                                                                    last_numbers,
                                                                                    accounting_request.from_number,
                                                                                    accounting_request.thru_number,
                                                                                    accounting_request.step)
                    account.state = 'aangemaakt'
                    accounting_request.accounting_number = account.accounting_number
                    self._session.flush()
                    return self._append_request(accounting_request)
                else:
                    accounting_request.accounting_number = account.accounting_number
            elif isinstance(accounting_request, CreateAccountRequest):
                self._check_account_request(accounting_request)
                # since nowhere in the application there is a need to search for the
                # next available account, the from number is used as the next account
                # number.
                account = self._session.query(Account).filter(Account.number==str(accounting_request.from_number)).first()
                if account is not None:
                    raise Exception('Account {0.from_number} exists'.format(accounting_request))
                Account(number=str(accounting_request.from_number), description=accounting_request.name)
                accounting_request.accounting_number = accounting_request.from_number
                self._session.flush()
                return self._append_request(accounting_request)
            else:
                raise Exception('Unknown accounting request')
        
    def _append_request(self, accounting_request):
        self.uncommitted_documents.append(accounting_request)
        return True


class SimulatedAccounting(InternalAccounting):
    """
    Simulates an internal accounting system by never committing the actual session
    """

    def __init__(self):
        # separate these numbers, so they do not increase the global numbers
        simulated_document_numbers = DocumentNumbers(dict(), threading.RLock())
        super(SimulatedAccounting, self).__init__(simulated_document_numbers)

    def begin(self, session):
        
        class SessionDecorator(object):
            """
            Helper object to prevent a session from being committed.
            """
        
            def __init__(self, session):
                self._session = session
        
            def begin(self):
                pass
        
            def commit(self):
                pass
        
            def rollback(self):
                pass
            
            def __getattr__(self, value):
                return getattr(self._session, value)
    
        return super(SimulatedAccounting, self).begin(SessionDecorator(session))


