import copy
import datetime
import sys
import threading

from sqlalchemy import sql, exc

from ..test_case import SessionCase
from ..test_model.test_bank import  test_rechtspersoon

from vfinance.connector.accounting import (InternalAccounting,
                                           CreateSalesDocumentRequest,
                                           CreatePurchaseDocumentRequest,
                                           RemoveDocumentRequest,
                                           FreezeDocumentRequest,
                                           UpdateDocumentRequest,
                                           CreateSupplierAccountRequest,
                                           CreateCustomerAccountRequest,
                                           CreateAccountRequest,
                                           PartyRequest,
                                           LineRequest,
                                           AccountingSingleton,
                                           DocumentNumbers)
from vfinance.connector.venice.accounting import VeniceAccounting
from vfinance.model.bank.entry import Entry, EntryPresence
from vfinance.model.bank.customer import SupplierAccount, CustomerAccount
from vfinance.process import WorkerPool, WorkerProcess

from camelot.core.exception import UserException
from camelot.core.orm import Session

from integration.venice import mock as venice_mock

# customers/suppliers created by this test should not be in the range of other tests
test_range = 100000

class BookingWorker(WorkerProcess):
    """Helper class to test bookings in subprocesses"""

    def handle_work(self, accounting_request):
        accounting = AccountingSingleton()
        session = Session()
        #
        # retry if the transaction fails, probably due to rows that are locked
        #
        max_tries = 10
        while True:
            try:
                with accounting.begin(session):
                    accounting.register_request(accounting_request)
            except exc.OperationalError:
                max_tries -= 1
                if max_tries <= 0:
                    raise
            else:
                break
        yield accounting_request


class InternalAccountingCase(SessionCase):

    @classmethod
    def setUpClass(cls):
        SessionCase.setUpClass()
        cls.rechtspersoon_case = test_rechtspersoon.RechtspersoonCase('setUp')
        cls.rechtspersoon_case.setUpClass()
        cls.natuurlijke_persoon_case = cls.rechtspersoon_case.natuurlijke_persoon_case

    def setUp(self):
        super(InternalAccountingCase, self).setUp()
        self.document_numbers = DocumentNumbers(dict(), threading.RLock())
        self.accounting = InternalAccounting(self.document_numbers)
        self.rechtspersoon_case.setUp()
        # a new workerpool is created for each test, because creating a workerpool
        # might trigger random errors and we want to maximize our chances of
        # triggering these kind of errors
        self.pool = WorkerPool(BookingWorker)
        self.pool.__enter__()

    def tearDown(self):
        self.pool.__exit__(None, None, None)
        super(InternalAccountingCase, self).tearDown()
        # increase the unique id in the venice mock to prevent clashes in future
        # unittests
        if venice_mock._unique_id_ is not None:
            venice_mock._unique_id_ = venice_mock._unique_id_ + 10000

    def create_sales_document(self, book='AcTest', book_date=datetime.date(2014,7,1)):
        return CreateSalesDocumentRequest(
            book_date=book_date,
            document_date=datetime.date(2013,6,3),
            book=book,
            lines = [
                LineRequest(account='1111', remark='test first line', amount=5, quantity=1),
                LineRequest(account='2222', remark='test second line', amount=-5, quantity=-1),
                ]
            )

    def create_purchase_document(self, book='AcTest'):
        return CreatePurchaseDocumentRequest(
            book_date=datetime.date(2014,8,1),
            document_date=datetime.date(2013,7,3),
            book=book,
            lines = [
                LineRequest(account='3333', remark='test first line', amount=5, quantity=1),
                LineRequest(account='4444', remark='test second line', amount=-5, quantity=-1),
                ]
            )

    def create_update_document(self, created_document):
        assert created_document.document_number
        created_line = created_document.lines[0]
        assert created_line.line_number
        update_line = LineRequest(account='3333',
                                  line_number=created_line.line_number,
                                  remark=created_line.remark,
                                  amount=created_line.amount,
                                  quantity=created_line.quantity)
        return UpdateDocumentRequest(book_date=created_document.book_date,
                                     document_date=created_document.document_date,
                                     document_number=created_document.document_number,
                                     book=created_document.book,
                                     lines=[update_line])

    def assertDocumentRequest(self, document_request):
        """
        Assert that a document request is written to the Entry table
        """
        for sales_line in document_request.lines:
            entry = self.session.query(Entry).filter(sql.and_(Entry.venice_doc==document_request.document_number,
                                                              Entry.book_date==document_request.book_date,
                                                              Entry.line_number==sales_line.line_number)).first()
            self.assertTrue(entry)
            self.assertEqual(entry.amount, sales_line.amount)
            self.assertEqual(entry.quantity, sales_line.quantity)
            self.assertEqual(entry.account, sales_line.account)

    def test_session_synchronisation(self):
        # the accouting system should operate in sync
        # with the orm transactions
        # exceptions should be raised when trying to do something without a
        # transaction
        with self.assertRaises(Exception):
            self.accounting.register_request(CreateSalesDocumentRequest())
        with self.assertRaises(Exception):
            self.accounting.commit()
        with self.assertRaises(Exception):
            self.accounting.rollback()
        with self.assertRaises(Exception):
            self.accounting.get_last_document_number(2014, 'AcTest')
        # the session transaction and the accounting transaction should
        # be in sync
        self.assertFalse(self.session.is_active)
        self.accounting.begin(self.session)
        self.assertTrue(self.session.is_active)
        self.accounting.commit()
        self.assertFalse(self.session.is_active)
        self.accounting.begin(self.session)
        self.assertTrue(self.session.is_active)
        self.accounting.rollback()
        self.assertFalse(self.session.is_active)

    def assert_valid_document_number(self, accounting_last_number, expected_last_number):
        self.assertEqual(accounting_last_number, expected_last_number)

    def test_commit_sales_document(self):
        # sales documents registered in the accounting system should
        # get a number and be visible in the database within the current transaction
        sales_document_1 = self.create_sales_document()
        with self.accounting.begin(self.session):
            last_number = self.accounting.get_last_document_number(sales_document_1.book_date.year, sales_document_1.book)
        self.accounting.begin(self.session)
        self.accounting.register_request(sales_document_1)
        self.assertTrue(sales_document_1.document_number)
        for sales_line in sales_document_1.lines:
            self.assertTrue(sales_line.line_number)
        sales_document_2 = self.create_sales_document(book=sales_document_1.book.upper())
        self.accounting.register_request(sales_document_2)
        self.assert_valid_document_number(sales_document_2.document_number, sales_document_1.document_number + 1)
        self.assertDocumentRequest(sales_document_1)
        self.assertDocumentRequest(sales_document_2)
        self.accounting.commit()
        self.assertDocumentRequest(sales_document_1)
        self.assertDocumentRequest(sales_document_2)
        self.accounting.begin(self.session)
        self.assert_valid_document_number(self.accounting.get_last_document_number(sales_document_1.book_date.year, sales_document_1.book), last_number + 2)
        self.accounting.commit()
        return sales_document_1

    def create_remove_document(self, document):
        return RemoveDocumentRequest(
            book_date = document.book_date,
            document_date = document.document_date,
            document_number = document.document_number,
            book = document.book)

    def test_remove_sales_document(self):
        sales_document = self.test_commit_sales_document()
        remove_document_1 = self.create_remove_document(sales_document)
        remove_document_2 = copy.copy(remove_document_1)
        self.assertFalse(remove_document_1.first_line_number)
        self.assertFalse(remove_document_1.last_line_number)
        with self.accounting.begin(self.session):
            self.accounting.register_request(remove_document_1)
            self.assertEqual(remove_document_1.book_type, 'V')
            self.assertTrue(remove_document_1.first_line_number)
            self.assertTrue(remove_document_1.last_line_number)
            with self.assertRaises(Exception):
                self.accounting.register_request(remove_document_2)

    def test_remove_purchase_document(self):
        purchase_document = self.test_commit_purchase_document()
        remove_document_1 = self.create_remove_document(purchase_document)
        with self.accounting.begin(self.session):
            self.accounting.register_request(remove_document_1)
            self.assertEqual(remove_document_1.book_type, 'A')

    def test_remove_frozen_document(self):
        document = self.test_commit_sales_document()
        remove_document = self.create_remove_document(document)
        freeze_document = FreezeDocumentRequest(
            book_date = document.book_date,
            document_date = document.document_date,
            document_number = document.document_number,
            book = document.book)
        with self.accounting.begin(self.session):
            self.accounting.register_request(freeze_document)
            with self.assertRaises(UserException):
                self.accounting.register_request(remove_document)

    def test_commit_purchase_document(self):
        purchase_document = self.create_purchase_document()
        with self.accounting.begin(self.session):
            self.accounting.register_request(purchase_document)
        self.assertDocumentRequest(purchase_document)
        return purchase_document

    def test_rollback_sales_document(self):
        self.accounting.begin(self.session)
        sales_document_1 = self.create_sales_document()
        last_document_number = self.accounting.get_last_document_number(sales_document_1.book_date.year, sales_document_1.book)
        self.accounting.register_request(sales_document_1)
        self.assertDocumentRequest(sales_document_1)
        self.accounting.rollback()
        self.assertFalse(sales_document_1.document_number)
        self.accounting.begin(self.session)
        self.assert_valid_document_number(self.accounting.get_last_document_number(sales_document_1.book_date.year, sales_document_1.book), last_document_number)
        self.accounting.commit()

    def test_commit_update_document(self):
        created_document = self.test_commit_sales_document()
        update_document = self.create_update_document(created_document)
        with self.accounting.begin(self.session):
            self.accounting.register_request(update_document)
        self.assertDocumentRequest(update_document)

    def test_rollback_update_document(self):
        created_document = self.test_commit_sales_document()
        update_document = self.create_update_document(created_document)
        self.accounting.begin(self.session)
        self.accounting.register_request(update_document)
        self.accounting.rollback()
        self.assertDocumentRequest(created_document)

    def test_accounting_singleton(self):
        accounting_1 = AccountingSingleton()
        accounting_2 = AccountingSingleton()
        self.assertTrue(accounting_1 is accounting_2)

    def create_create_supplier_account_request(self, person, organization, from_number, thru_number):
        account_request = CreateSupplierAccountRequest(from_number=from_number,
                                                       thru_number=thru_number)
        if person is not None:
            account_request.person_id = person.id
            account_request.name = person.name
        elif organization is not None:
            account_request.organization_id = organization.id
            account_request.name = organization.name
        else:
            raise Exception('organization or person should be set')
        return account_request

    def create_party_request(self, person=None, organization=None):
        party_request = PartyRequest()
        if person is not None:
            party_request.person_id = person.id
        elif organization is not None:
            party_request.organization_id = organization.id
        return party_request
            
    def create_create_customer_account_request(self, person, organization, from_number, thru_number):
        parties = [self.create_party_request(person, organization)]
        account_request = CreateCustomerAccountRequest(from_number=from_number,
                                                       thru_number=thru_number,
                                                       parties=parties)
        if person is not None:
            account_request.name = person.name
        elif organization is not None:
            account_request.name = organization.name

        return account_request

    def get_max_supplier(self):
        return (self.session.execute(sql.select([sql.func.max(SupplierAccount.accounting_number)])).scalar() or 0) + test_range

    def test_create_supplier(self):
        max_supplier = self.get_max_supplier()
        for person, organization in [(self.natuurlijke_persoon_case.create_natuurlijke_persoon(), None),
                                           (None, self.rechtspersoon_case.rechtspersoon_1)]:
            with self.accounting.begin(self.session):
                account_request = self.create_create_supplier_account_request(person, organization, max_supplier+1, max_supplier+10)
                supplier_1 = SupplierAccount.find_by_dual_person(person, organization, account_request.from_number, account_request.thru_number)
                self.assertFalse( supplier_1 )
                self.accounting.register_request(account_request)
                self.assertTrue(account_request.accounting_number)
                supplier_1 = SupplierAccount.find_by_dual_person(person, organization, account_request.from_number, account_request.thru_number)
                self.assertTrue(supplier_1)
                self.assertTrue(account_request.from_number<=supplier_1.accounting_number<=account_request.thru_number)
                self.assertTrue(supplier_1.accounting_number)
                
                account_request = self.create_create_supplier_account_request(person, organization, max_supplier+11, max_supplier+20)
                self.accounting.register_request(account_request)
                supplier_2 = SupplierAccount.find_by_dual_person(person, organization, account_request.from_number, account_request.thru_number)
                self.assertTrue(account_request.from_number<=supplier_2.accounting_number<=account_request.thru_number)
                self.assertEqual(supplier_2.accounting_number, account_request.accounting_number)
                self.assertNotEqual(supplier_1.id, supplier_2.id)
                
                account_request.accounting_number = None
                self.accounting.register_request(account_request)
                self.assertEqual(account_request.accounting_number, supplier_2.accounting_number)

            return supplier_1

    def get_max_customer(self):
        return (self.session.execute(sql.select([sql.func.max(CustomerAccount.accounting_number)])).scalar() or 0) + test_range

    def test_create_customer(self):
        max_customer = self.get_max_customer()
        person = self.natuurlijke_persoon_case.create_natuurlijke_persoon()
        party_request = self.create_party_request(person, None)
        from_customer, thru_customer = max_customer+1, max_customer+10
        customer_1 = CustomerAccount.find_by_dual_persons( [party_request], from_customer, thru_customer )
        self.assertFalse(customer_1)
        with self.accounting.begin(self.session):
            account_request = self.create_create_customer_account_request(person, None, from_customer, thru_customer)
            self.accounting.register_request(account_request)
            self.assertTrue(account_request.accounting_number)        
            self.assertTrue(from_customer<=account_request.accounting_number<=thru_customer)
        customer_1 = CustomerAccount.find_by_dual_persons( [party_request], from_customer, thru_customer )
        self.assertTrue(customer_1)
        self.assertEqual(customer_1.state, 'aangemaakt')
        self.assertTrue( customer_1.full_account_number )
        from_customer, thru_customer = max_customer+11, max_customer+20
        with self.accounting.begin(self.session):
            account_request = self.create_create_customer_account_request(person, None, from_customer, thru_customer)
            self.accounting.register_request(account_request)        
        customer_2 = CustomerAccount.find_by_dual_persons( [party_request], from_customer, thru_customer )
        self.assertTrue(from_customer<=customer_2.accounting_number<=thru_customer)
        self.assertNotEqual(customer_1.id, customer_2.id)
        return customer_1

    def test_create_same_customer(self):
        max_customer = self.get_max_customer()
        person = self.natuurlijke_persoon_case.create_natuurlijke_persoon()
        from_customer, thru_customer = max_customer+1, max_customer+10
        with self.accounting.begin(self.session):
            account_request_1 = self.create_create_customer_account_request(person, None, from_customer, thru_customer)
            account_request_2 = self.create_create_customer_account_request(person, None, from_customer, thru_customer)
        self.assertEqual(account_request_2.accounting_number, account_request_1.accounting_number)

    def test_create_account(self):
        account_request = CreateAccountRequest(name='Test account')
        with self.accounting.begin(self.session):
            last_number = self.accounting.get_last_account_number(from_number=0, thru_number=sys.maxint) or 0
            account_request.from_number = last_number + 1
            account_request.thru_number = last_number + 5
            self.accounting.register_request(account_request)

    #
    # Test the creation of documents/customers/suppliers from multiple
    # process to make sure the numbers are unique and consistent
    #
    def test_distinct_document_numbers(self):
        accounting_documents = [self.create_sales_document() for _i in range(100)]
        document_numbers = list(response.document_number for response in self.pool.submit(accounting_documents))
        # make sure there is no overlap
        self.assertEqual(len(document_numbers), len(set(document_numbers)))
        # make sure there are no gaps
        min_doc = min(document_numbers)
        max_doc = max(document_numbers)
        self.assertEqual(max_doc, min_doc + len(document_numbers) - 1)

    def test_distinct_customer_numbers(self):
        max_customer = self.get_max_customer()
        customer_requests = []
        data = copy.copy(self.natuurlijke_persoon_case.natuurlijke_personen_data[1])
        voornaam = data['voornaam']
        for i in range(100):
            data['voornaam'] = voornaam + unicode(i)
            customer_requests.append(
                self.create_create_customer_account_request(
                    self.natuurlijke_persoon_case.create_natuurlijke_persoon(data),
                    None, 
                    max_customer,
                    sys.maxint,
                    )
                )
        customer_numbers = list(response.accounting_number for response in self.pool.submit(customer_requests))
        # make sure there is no overlap
        self.assertEqual(len(customer_numbers), len(set(customer_numbers)))
        # make sure there are no gaps
        min_doc = min(customer_numbers)
        max_doc = max(customer_numbers)
        self.assertEqual(max_doc, min_doc + len(customer_numbers) - 1)

    def test_unique_customer_numbers(self):
        max_customer = self.get_max_customer()
        customer_requests = []
        data = copy.copy(self.natuurlijke_persoon_case.natuurlijke_personen_data[1])
        voornaam = data['voornaam']
        for i in range(25):
            data['voornaam'] = voornaam + unicode(i)
            person = self.natuurlijke_persoon_case.create_natuurlijke_persoon(data)
            for j in range(4):
                customer_requests.append(
                    self.create_create_customer_account_request(
                        person,
                        None, 
                        max_customer,
                        sys.maxint,
                        )
                    )
        customer_numbers = list(response.accounting_number for response in self.pool.submit(customer_requests))
        # make sure there is no overlap
        self.assertEqual(len(customer_numbers), 100)
        self.assertEqual(len(set(customer_numbers)), 25)
        # make sure there are no gaps
        min_doc = min(customer_numbers)
        max_doc = max(customer_numbers)
        self.assertEqual(max_doc, min_doc + 25 - 1)

    def test_distinct_supplier_numbers(self):
        max_supplier = self.get_max_supplier()
        supplier_requests = []
        data = copy.copy(self.natuurlijke_persoon_case.natuurlijke_personen_data[1])
        voornaam = data['voornaam']
        for i in range(100):
            data['voornaam'] = voornaam + unicode(i)
            supplier_requests.append(
                self.create_create_supplier_account_request(
                    self.natuurlijke_persoon_case.create_natuurlijke_persoon(data),
                    None, 
                    max_supplier,
                    sys.maxint,
                    )
                )
        supplier_numbers = list(response.accounting_number for response in self.pool.submit(supplier_requests))
        # make sure there is no overlap
        self.assertEqual(len(supplier_numbers), len(set(supplier_numbers)))
        # make sure there are no gaps
        min_doc = min(supplier_numbers)
        max_doc = max(supplier_numbers)
        self.assertEqual(max_doc, min_doc + len(supplier_numbers) - 1)

    def test_unique_supplier_number(self):
        max_supplier = self.get_max_supplier()
        supplier_requests = []
        data = copy.copy(self.natuurlijke_persoon_case.natuurlijke_personen_data[1])
        voornaam = data['voornaam']
        for i in range(25):
            data['voornaam'] = voornaam + unicode(i)
            person = self.natuurlijke_persoon_case.create_natuurlijke_persoon(data)
            for _j in range(4):
                supplier_requests.append(
                    self.create_create_supplier_account_request(
                        person,
                        None, 
                        max_supplier,
                        sys.maxint,
                        )
                    )
        supplier_numbers = list(response.accounting_number for response in self.pool.submit(supplier_requests))
        # make sure there is no overlap
        self.assertEqual(len(supplier_numbers), 100)
        self.assertEqual(len(set(supplier_numbers)), 25)
        # make sure there are no gaps
        min_doc = min(supplier_numbers)
        max_doc = max(supplier_numbers)
        self.assertEqual(max_doc, min_doc + 25 - 1)

class VeniceAccountingCase(InternalAccountingCase):

    def setUp(self):
        super(VeniceAccountingCase, self).setUp()
        self.accounting = VeniceAccounting(self.document_numbers)

    def assert_valid_document_number(self, accounting_last_number, expected_last_number):
        # Venice numbers might increase due to other users (or the mock)
        self.assertTrue(accounting_last_number >= expected_last_number)

    def create_entry_presence_lines(self, created_document, accounting_year):
        for line_request in created_document.lines:
            kwargs = self.accounting._entry_condition_kwargs(created_document,
                                                             line_request)
            result = self.session.execute(self.accounting.entry_select,
                                          params=kwargs)
            entry_id = result.scalar()
            EntryPresence(venice_active_year=accounting_year,
                          venice_id=5,
                          entry_id=entry_id)
        self.session.flush()

    def create_update_document(self, created_document):
        self.create_entry_presence_lines(created_document, str(created_document.book_date.year))
        return super(VeniceAccountingCase, self).create_update_document(created_document)

    def create_remove_document(self, created_document):
        self.create_entry_presence_lines(created_document, str(created_document.book_date.year))
        return super(VeniceAccountingCase, self).create_remove_document(created_document)

    def test_remove_transfered_document(self):
        document = self.test_commit_sales_document()
        remove_document = self.create_remove_document(document)
        self.create_entry_presence_lines(document, str(document.book_date.year+1))
        with self.accounting.begin(self.session):
            with self.assertRaises(UserException):
                self.accounting.register_request(remove_document)

    def test_mixed_accounting_years(self):
        with self.assertRaises(UserException):
            with self.accounting.begin(self.session):
                self.accounting.register_request(self.create_sales_document(book_date=datetime.date(2014,1,1)))
                self.accounting.register_request(self.create_sales_document(book_date=datetime.date(2015,1,1)))


