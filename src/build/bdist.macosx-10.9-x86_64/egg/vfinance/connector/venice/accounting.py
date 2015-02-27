import logging
import sys

from sqlalchemy import sql

from ..accounting import (InternalAccounting, UpdateDocumentRequest, AccountRequest,
                          CreateSalesDocumentRequest, CreatePurchaseDocumentRequest,
                          CreateSupplierAccountRequest, CreateCustomerAccountRequest,
                          FreezeDocumentRequest, RemoveDocumentRequest,
                          CreateAccountRequest)
from ...model.bank.customer import SupplierAccount
from ...model.bank.entry import EntryPresence
from ...model.bank.venice import get_dossier_bank

from camelot.core.conf import settings
from camelot.core.exception import UserException

from integration.venice import venice

LOGGER = logging.getLogger('vfinance.connector.venice')
LOGGER.setLevel(logging.DEBUG)

no_book_year = object()

"""
It might be that ctypes or related things are faster here than using
pywin32 :

from ctypes import windll
windll.Ole32.OleInitialize(None)

"""

class Pervasive(object):

    success = 0
    invalid_position = 8
    end_of_file = 9

class VeniceAccounting(InternalAccounting):
    """
    Accounting module that uses venice to register its accounting documents
    """

    def __init__(self, *args, **kwargs):
        super(VeniceAccounting, self).__init__(*args, **kwargs)
        self._settings = settings
        self._venice_requests = None
        ep_c = EntryPresence.__table__.columns
        ep_select = sql.select([ep_c.venice_active_year])
        ep_select = ep_select.order_by(ep_c.venice_active_year.desc())
        p = sql.bindparam
        self.entry_presence_select = ep_select.where(ep_c.entry_id==p('r_entry_id'))
        ep_delete = EntryPresence.__table__.delete()
        self.entry_presence_delete = ep_delete.where(ep_c.entry_id==p('r_entry_id'))
        self._reset_venice_objects()
        with self.document_numbers.lock:
            self.dossier, self.constants = get_dossier_bank(self._settings)

    def _reset_venice_objects(self):
        self._year_objects = dict()
        #
        # Because each Venice object has its own transaction
        #
        self._document_objects = dict()

    def _get_venice_year(self, year):
        try:
            return self._year_objects[year]
        except KeyError:
            year_object = self.dossier.CreateYearContext(year)
            self._year_objects[year] = year_object
        return self._year_objects[year]

    def _get_venice_object(self, year, object_type):
        key = (year, object_type)
        try:
            return self._document_objects[key]
        except KeyError:
            if object_type == 'sales':
                document_object = self._get_venice_year(year).CreateSales(True)
            elif object_type == 'purch':
                document_object = self._get_venice_year(year).CreatePurch(True)
            elif object_type == 'suppl':
                document_object = self.dossier.CreateSuppl(True)
            elif object_type == 'custm':
                document_object = self.dossier.CreateCustm(True)
            elif object_type == 'accnt':
                document_object = self.dossier.CreateAccnt(True)
            elif object_type == 'finan':
                document_object = self._get_venice_year(year).CreateFinan(True)
            elif object_type == 'sndry':
                document_object = self._get_venice_year(year).CreateSndry(True)
            else:
                raise Exception('Unknown Venice document object')
            # get the uncached object, to be able to set attributes
            self._document_objects[key] = document_object._dossier
        return document_object
            
    def get_last_document_number(self, book_year, book):
        # last internal number is slow, so only ask the last number from Venice
        #last_internal_number = super(VeniceAccounting, self).get_last_document_number(book_year, book)
        self._check_transaction()
        #
        # Work out Venice document number
        #
        venice_sales = self._get_venice_object(str(book_year), 'sales')
        last_venice_sales_number, last_venice_purch_number = 0, 0
        if venice_sales.SeekByDocNum(self.constants.smLess,
                                     book_year,
                                     book,
                                     sys.maxint):
            db_status = venice_sales.GetDBStatus()
            if (db_status == Pervasive.success) and (venice_sales.pBook.lower()==book.lower()):
                last_venice_sales_number = venice_sales.pDocNum
            else:
                LOGGER.warn('last venice sales status : {0}'.format(db_status))
        LOGGER.info('last venice sales document number for book {0} {1} : {2}'.format(book, book_year, last_venice_sales_number))
        venice_purch = self._get_venice_object(str(book_year), 'purch')
        if venice_purch.SeekByDocNum(self.constants.smLess,
                                     book_year,
                                     book,
                                     sys.maxint):
            db_status = venice_purch.GetDBStatus()
            if (db_status == Pervasive.success) and (venice_purch.pBook.lower()==book.lower()):
                last_venice_purch_number = venice_purch.pDocNum
            else:
                LOGGER.warn('last venice purchase status : {0}'.format(db_status))
        LOGGER.info('last venice purchase document number for book {0} {1} : {2}'.format(book, book_year, last_venice_purch_number))
        return max(last_venice_sales_number, last_venice_purch_number)
        #return max(last_venice_number, last_internal_number)

    def get_last_supplier_numbers(self, from_number, thru_number):
        last_supplier_numbers = super(VeniceAccounting, self).get_last_supplier_numbers(from_number, thru_number)
        venice_supplier = self._get_venice_object(no_book_year, 'suppl')
        venice_supplier.SeekBySupNum(self.constants.smLast, 0, 0 )
        if venice_supplier.SetFilter('@SUP.Number >= {0} && @SUP.Number <= {1}'.format(from_number, thru_number), True):
            while venice_supplier.GetNext():pass
            last_supplier_numbers['venice'] = venice_supplier.pNumber
        # having filters when terminating objects causes Venice crashes
        venice_supplier.SetFilter('', True)
        return last_supplier_numbers

    def get_last_customer_numbers(self, from_number, thru_number):
        last_customer_numbers = super(VeniceAccounting, self).get_last_customer_numbers(from_number, thru_number)
        venice_customer = self._get_venice_object(no_book_year, 'custm')
        venice_customer.SeekByCstNum( self.constants.smLast, 0, 0 )
        if venice_customer.SetFilter( '@CST.Number >= {0} && @CST.Number <= {1}'.format( from_number, thru_number ), True):
            while venice_customer.GetNext():pass
            last_customer_numbers['venice'] = venice_customer.pNumber
        # having filters when terminating objects causes Venice crashes
        venice_customer.SetFilter('', True)
        return last_customer_numbers

    def assign_line_numbers(self, sales_document):
        vat_offset = 2 # Venice will create 2 dummy entries for VAT right after the first sales entry
        line_number = 1
        for sales_line in sales_document.lines:
            sales_line.line_number = line_number
            if line_number == 1:
                line_number += vat_offset
            line_number += 1

    def _seek_document(self, document_type, document_object, book, document):
        if document_type == 'finan':
            return document_object.SeekByBook(self.constants.smEqual,
                                              book,
                                              document)
        elif document_type == 'sndry':
            return document_object.SeekByDocNum(self.constants.smEqual,
                                                book,
                                                document)
        else:
            raise Exception('Unhandled document type')

    def _extract_requested_book_year(self, accounting_request):
        """
        Find out the Venice book year for the request
        """
        if isinstance(accounting_request, (CreateSalesDocumentRequest,
                                           CreatePurchaseDocumentRequest)):
            requested_book_year = str(accounting_request.book_date.year)
        elif isinstance(accounting_request, UpdateDocumentRequest):
            connection = self._connection()
            for line_request in accounting_request.lines:
                kwargs = self._entry_condition_kwargs(accounting_request,
                                                      line_request)
                entry_id = connection.execute(self.entry_select, kwargs).scalar()
                entry_years = [ep[0] for ep in connection.execute(
                    self.entry_presence_select,
                    r_entry_id=entry_id)]
                if not len(entry_years):
                    raise Exception('Dont know in which Venice year to look')
                entry_years.sort()
                requested_book_year = entry_years[-1]
                break
            else:
                raise Exception('UpdateDocumentRequest has no lines')
        elif isinstance(accounting_request, (AccountRequest,
                                             FreezeDocumentRequest)):
            requested_book_year = no_book_year
        else:
            raise Exception('Unhandled accounting request')
        return requested_book_year

    def register_request(self, accounting_request):
        with self.document_numbers.lock:
            if isinstance(accounting_request, RemoveDocumentRequest):
                connection = self._connection()
                kwargs = self._document_condition_kwargs(accounting_request)
                entry_ids = [r['id'] for r in connection.execute(self.document_select, kwargs)]
                if not len(entry_ids):
                    raise Exception('No entry found for document to remove')
                entry_years = set()
                for entry_id in entry_ids:
                    for row in connection.execute(self.entry_presence_select,
                                                  r_entry_id=entry_id):
                        entry_years.add(row['venice_active_year'])
                if not len(entry_years):
                    # fallback for entries for which no entry presence has been
                    # written
                    entry_years.add(str(accounting_request.book_date.year))
                    #raise Exception('Dont know in which Venice year to look')
                if len(entry_years) > 1:
                    raise UserException(text = 'Cannot remove transferred booking',
                                        detail = 'Booking {0.book} {0.document_number} with book date {0.book_date}'.format(accounting_request),
                                        resolution = 'Verify this booking in the accounting system' )
                requested_book_year = entry_years.pop()
                for entry_id in entry_ids:
                    connection.execute(self.entry_presence_delete,
                                       r_entry_id=entry_id)
            else:
                requested_book_year = self._extract_requested_book_year(accounting_request)
            #
            # Mark the document objects for which a transaction should be started,
            # the request got in the queue
            #
            registered = super(VeniceAccounting, self).register_request(accounting_request)
            if registered == True:
                for previous_requested_book_year, previous_request in self._venice_requests:
                    if previous_requested_book_year != requested_book_year:
                        raise UserException('No requests for different book years can be passed to Venice')
                if isinstance(accounting_request, CreateSalesDocumentRequest):
                    self._get_venice_object(requested_book_year, 'sales')
                elif isinstance(accounting_request, CreatePurchaseDocumentRequest):
                    self._get_venice_object(requested_book_year, 'purch')
                elif isinstance(accounting_request, UpdateDocumentRequest):
                    self._get_venice_object(requested_book_year, 'sndry')
                    self._get_venice_object(requested_book_year, 'finan')
                elif isinstance(accounting_request, CreateSupplierAccountRequest):
                    self._get_venice_object(requested_book_year, 'suppl')
                elif isinstance(accounting_request, CreateCustomerAccountRequest):
                    self._get_venice_object(requested_book_year, 'custm')
                elif isinstance(accounting_request, CreateAccountRequest):
                    self._get_venice_object(requested_book_year, 'accnt')
                elif isinstance(accounting_request, RemoveDocumentRequest):
                    if accounting_request.book_type == 'V':
                        self._get_venice_object(requested_book_year, 'sales')
                    elif accounting_request.book_type == 'A':
                        self._get_venice_object(requested_book_year, 'purch')
                    else:
                        raise Exception('Unhandled book type')
                else:
                    raise Exception('Unhandled accounting request')
                self._venice_requests.append((requested_book_year,
                                              accounting_request))
            return registered

    def begin(self, session):
        context = super(VeniceAccounting, self).begin(session)
        self._venice_requests = []
        return context

    def rollback(self):
        with self.document_numbers.lock:
            super(VeniceAccounting, self).rollback()
            self._reset_venice_objects()

    def commit(self):
        LOGGER.debug('acquire document lock')
        with self.document_numbers.lock:
            self._check_transaction()
            pending_requests = len(self.uncommitted_documents)
            if pending_requests:
                # make sure no unflushed data can cause an exception later on
                self._session.flush()
                LOGGER.debug('start venice stransactions')
                for document_object in self._document_objects.values():
                    document_object.SetTransMode(self.constants.tmBegin)
                    db_status = document_object.GetDBStatus()
                    if db_status not in (Pervasive.success, Pervasive.end_of_file):
                        LOGGER.error('Venice status when trying to start a transaction : {0}'.format(db_status))
                        raise UserException('Venice database error', detail='Database has status {0} when trying to start a transaction'.format(db_status))
                try:
                    LOGGER.debug('start registration of {0} requests'.format(pending_requests))
                    for requested_book_year, document_request in self._venice_requests:
                        if isinstance(document_request, CreateSalesDocumentRequest):
                            self._handle_create_sales_document(requested_book_year, document_request)
                        elif isinstance(document_request, CreatePurchaseDocumentRequest):
                            self._handle_create_purchase_document(requested_book_year, document_request)
                        elif isinstance(document_request, UpdateDocumentRequest):
                            self._handle_update_document(requested_book_year, document_request)
                        elif isinstance(document_request, CreateSupplierAccountRequest):
                            self._handle_create_supplier(requested_book_year, document_request)
                        elif isinstance(document_request, CreateCustomerAccountRequest):
                            self._handle_create_customer(requested_book_year, document_request)
                        elif isinstance(document_request, CreateAccountRequest):
                            self._handle_create_account(requested_book_year, document_request)
                        elif isinstance(document_request, RemoveDocumentRequest):
                            self._handle_remove_document(requested_book_year, document_request)
                        else:
                            raise Exception('Unhandled accounting request')
                    LOGGER.info('Commit venice transactions of {0} requests'.format(pending_requests))
                    for document_object in self._document_objects.values():
                        document_object.SetTransMode(self.constants.tmCommit)
                    LOGGER.debug('Finished registration')
                except Exception, e:
                    LOGGER.error('Rollback venice transaction', exc_info=e)
                    for document_object in self._document_objects.values():
                        document_object.SetTransMode(self.constants.tmRollBack)
                    raise
            self._session.commit()
            self._session = None
            self._reset_venice_objects()

    # dont create new document objects when handling the requests, as those
    # new objects might not be in a transactional state
    
    def _handle_update_document(self, requested_book_year, document_request):
        LOGGER.info(u'Update Venice document {0.book} {0.document_number} in year {1}'.format(document_request, requested_book_year))
        for document_type in ('finan', 'sndry'):
            document_object = self._document_objects[(requested_book_year, document_type)]
            if self._seek_document(document_type,
                                   document_object,
                                   document_request.book,
                                   document_request.document_number):
                break
        else:
            raise Exception('document not found')
    
        document_object.PrepareDocument(self.constants.paUpdate)
        for line_request in document_request.lines:
            (exists, 
             det_amount_docc, 
             det_quantity, 
             det_value1, 
             det_account, 
             det_remark, 
             det_text1, 
             det_amount_detc, 
             det_detc, 
             det_tick ) = document_object.GetDetail( line_request.line_number - 1 )
            if not exists:
                document_object.CancelDocument()
                raise Exception('Document detail %s %s line %s does not exist'%(document_request.book, document_request.document_number, line_request.line_number))
            document_object.UpdateDetail( line_request.line_number - 1, 
                                          det_amount_docc, 
                                          det_quantity, 
                                          det_value1, 
                                          line_request.account, 
                                          det_remark,
                                          det_text1,
                                          det_amount_detc,
                                          det_detc,
                                          det_tick )
        document_object.WriteDocument(self.constants.rmNoReport)

    def _handle_remove_document(self, requested_book_year, document_request):
        LOGGER.info(u'Remove Venice document {0.book} {0.document_number} in year {1}'.format(document_request, requested_book_year))
        venice_doc = self._document_objects[(requested_book_year, {'V': 'sales',
                                                                   'A': 'purch'}[document_request.book_type])]
        if venice_doc.SeekByDocNum(self.constants.smEqual, document_request.book_date.year, document_request.book, document_request.document_number):
            try:
                venice_doc.Delete(self.constants.dmNoReport)
            except Exception, e:
                raise UserException(text = u'Could not remove document {0.book} {0.document_number} in {1}'.format(document_request, requested_book_year),
                                    detail = unicode(e),
                                    resolution = u'Resolve the issue with this document in Venice and then try again')
            # reset the venice object, to set the status of the database
            # back to 0, since it will be 8 after deleting the record
            venice_doc.SeekBySysNum(self.constants.smFirst, 0)
        else:
            LOGGER.warn(' document not found in venice')

    def _handle_create_sales_document(self, requested_book_year, sales_document):
        LOGGER.info(u'Create Venice sales document {0.book} {0.document_number} in year {1}'.format(sales_document, requested_book_year))
        venice_sales = self._document_objects[(requested_book_year, 'sales')]
        total_amount = sales_document.amount
        if total_amount < 0:
            doctype = self.constants.slsCreditnote
        else:
            doctype = self.constants.slsInvoice
        #
        # Sales header
        #
        venice_sales.PrepareDocument(self.constants.paInsert)
        db_status = venice_sales.GetDBStatus()
        if db_status != Pervasive.success:
            LOGGER.error('Venice sales status after document preparation : {0}'.format(db_status))
            raise UserException('Venice database error', detail='sales database of {0} has status {1}'.format(requested_book_year, db_status))
        try:
            venice_sales.Init()
            customer_number = int(sales_document.account) - int(self._settings.get('HYPO_ACCOUNT_KLANT'))
            venice_sales.pExpDate = venice.to_venice_date(sales_document.document_date)
            venice_sales.pRemark = (sales_document.remark or '')[:50]
            venice_sales.pBook = sales_document.book
            venice_sales.pBookDate = venice.to_venice_date(sales_document.book_date)
            venice_sales.pDocNum = sales_document.document_number
            venice_sales.pDocDate = venice.to_venice_date(sales_document.document_date)
            venice_sales.pDocType = doctype
            venice_sales.pCstNum = customer_number
            venice_sales.pTotalDocC = float(total_amount)
            venice_sales.pBaseNotSubmitDocC = float(total_amount)
            venice_sales.pVatDedNormDocC = 0.0
            venice_sales.pVatDueNormDocC = 0.0

            #
            # Sales lines
            #
            for sales_line in sales_document.lines:
                venice_sales.InsertDetail(
                    sales_line.line_number,
                    float(sales_line.amount),
                    float(sales_line.quantity),
                    0.0,
                    sales_line.account,
                    (sales_line.remark or '')[:50],
                    ''
                )
            venice_sales.WriteDocument(self.constants.rmNoReport)
            db_status = venice_sales.GetDBStatus()
            if db_status != Pervasive.success:
                LOGGER.error('Venice sales status after writing document {0}'.format(db_status))
                raise UserException('Venice database error', detail='sales database of {0} has status {1}'.format(requested_book_year, db_status))
        except:
            LOGGER.error('Cancel writing of venice sales document {0.document_number}'.format(sales_document))
            venice_sales.CancelDocument()
            raise

    def _handle_create_purchase_document(self, requested_book_year, purchase_document):
        LOGGER.info(u'Create Venice purch document {0.book} {0.document_number} in year {1}'.format(purchase_document, requested_book_year))
        venice_purch = self._document_objects[(requested_book_year, 'purch')]
        total_amount = purchase_document.amount
        if total_amount < 0:
            doctype = self.constants.prcInvoice
        else:
            doctype = self.constants.prcCreditnote
        #
        # Purchase header
        #
        venice_purch.PrepareDocument(self.constants.paInsert)
        try:
            venice_purch.Init()
            supplier_number = int(purchase_document.account) - int(self._settings.get('BANK_ACCOUNT_SUPPLIER'))
            venice_purch.pAutoPay = True
            venice_purch.pExpDate = venice.to_venice_date(purchase_document.document_date)
            venice_purch.pPayApproval = True
            venice_purch.pRemark = (purchase_document.remark or '')[:50]
            venice_purch.pBook = purchase_document.book
            venice_purch.pBookDate = venice.to_venice_date(purchase_document.book_date)
            venice_purch.pSupNum = supplier_number
            venice_purch.pDocDate = venice.to_venice_date(purchase_document.document_date)
            venice_purch.pDocType = doctype
            venice_purch.pNormalDetail1DocC = float(total_amount)
            vat = 0
            venice_purch.pTotalDocC = float(total_amount + vat)
            if total_amount < 0:
                venice_purch.pVatDedInvNormDocC = float(vat)
            else:
                # opm : hier zit een asymetrie in properties, cf de
                # de voorbeeld import bestanden
                venice_purch.pVatDueCreNormDocC = float(vat)
            #
            # Purchase lines
            #
            for purchase_line in purchase_document.lines:
                if purchase_line.line_number == 1:
                    continue
                venice_purch.InsertDetail(
                    purchase_line.line_number,
                    float(purchase_line.amount),
                    float(purchase_line.quantity),
                    0.0,
                    purchase_line.account,
                    (purchase_line.remark or '')[:50],
                    ''
                )
            venice_purch.WriteDocument(self.constants.rmNoReport)
        except:
            LOGGER.error('Cancel writing of venice purch document {0.document_number}'.format(purchase_document))
            venice_purch.CancelDocument()
            raise

        
    def _handle_create_supplier(self, requested_book_year, supplier_request):
        LOGGER.info(u'Create Venice supplier with number {0.accounting_number} and name {0.name}'.format(supplier_request))
        venice_supplier = self._document_objects[(requested_book_year, 'suppl')]
        venice_supplier.Init()
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('Name'), supplier_request.name)
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('Number'), supplier_request.accounting_number)
        supplier_account = self._session.query(SupplierAccount).filter(SupplierAccount.accounting_number==supplier_request.accounting_number).first()
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('Language'), {'nl':'Nld', 'fr':'Fra'}.get(supplier_account.language, 'Nld'))
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('Street'), supplier_account.street or '')
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('PostalCode'), supplier_account.zipcode or '')
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('City'), supplier_account.city or '')
        if supplier_account.country is not None:
            venice_supplier.SetFieldVal( venice_supplier.GetFieldID('CountryCode'), supplier_account.country.code or '')
            venice_supplier.SetFieldVal( venice_supplier.GetFieldID('CountryName'), supplier_account.country.name or '')
        if supplier_account.rechtspersoon is not None:
            for official_number in supplier_account.rechtspersoon.official_numbers:
                if official_number.type == 'cbfa':
                    venice_supplier.SetFieldVal( venice_supplier.GetFieldID('CstNum'), official_number.number or '')
            venice_supplier.SetFieldVal( venice_supplier.GetFieldID('LegalForm'), supplier_account.rechtspersoon.vorm or '')
            if supplier_account.rechtspersoon.ondernemingsnummer:
                venice_supplier.SetFieldVal( venice_supplier.GetFieldID('VatNum'), supplier_account.rechtspersoon.ondernemingsnummer)
            else:
                venice_supplier.SetFieldVal( venice_supplier.GetFieldID('VatLiable'), False)
            vertegenwoordiger = supplier_account.rechtspersoon.vertegenwoordiger
            if vertegenwoordiger is not None:
                venice_supplier.SetFieldVal( venice_supplier.GetFieldID('Contact'), vertegenwoordiger.name or '')
                venice_supplier.SetFieldVal( venice_supplier.GetFieldID('AddressForm'), vertegenwoordiger.titel or '')
                #customer.SetFieldVal( customer.GetFieldID('PolitePhrase'), False )
        else:
            venice_supplier.SetFieldVal( venice_supplier.GetFieldID('VatLiable'), False)
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('TelType1'), self.constants.tltTelephone )
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('Tel1'), supplier_account.phone or '')
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('TelType2'), self.constants.tltMobile )
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('Tel2'), supplier_account.mobile or '')
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('TelType3'), self.constants.tltFax )
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('Tel3'), supplier_account.fax or '')
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('Email'), supplier_account.email or '')
        #customer.SetFieldVal( customer.GetFieldID('WWW'), None )
        venice_supplier.SetFieldVal( venice_supplier.GetFieldID('Commission'), True)
        for bank_account in supplier_account.bank_accounts:
            if (bank_account.iban is not None) and (bank_account.bank_identifier_code is not None):
                venice_supplier.SetFieldVal( venice_supplier.GetFieldID('BankAccount1'), bank_account.iban or '')
                venice_supplier.SetFieldVal( venice_supplier.GetFieldID('SwiftCode'), bank_account.bank_identifier_code.code or '')
                break
        if supplier_account.natuurlijke_persoon is not None:
            venice_supplier.SetFieldVal( venice_supplier.GetFieldID('VatNum'), supplier_account.natuurlijke_persoon.tax_number or '')
            venice_supplier.SetFieldVal( venice_supplier.GetFieldID('TypePerson'), self.constants.etpPhysical )
            venice_supplier.SetFieldVal( venice_supplier.GetFieldID('NatNum'), supplier_account.natuurlijke_persoon.social_security_number or '')
            venice_supplier.SetFieldVal( venice_supplier.GetFieldID('LastName'), supplier_account.natuurlijke_persoon.first_name or '')
            venice_supplier.SetFieldVal( venice_supplier.GetFieldID('FirstName'), supplier_account.natuurlijke_persoon.last_name or '')
        else:
            venice_supplier.SetFieldVal( venice_supplier.GetFieldID('TypePerson'), self.constants.etpLegal )
        venice_supplier.Insert(self.constants.imNoReport)

    def _handle_create_customer(self, requested_book_year, customer_request):
        LOGGER.info(u'Create Venice customer with number {0.accounting_number} and name {0.name}'.format(customer_request))
        venice_customer = self._document_objects[(requested_book_year, 'custm')]
        venice_customer.Init()
        venice_customer.SetFieldVal( venice_customer.GetFieldID('Name'), customer_request.name )
        venice_customer.SetFieldVal( venice_customer.GetFieldID('Number'), customer_request.accounting_number )
        venice_customer.SetFieldVal( venice_customer.GetFieldID('VatLiable'), False )
        venice_customer.Insert(self.constants.imNoReport)

    def _handle_create_account(self, requested_book_year, account_request):
        LOGGER.info(u'Create Venice account with number {0.accounting_number} and name {0.name}'.format(account_request))
        venice_account = self._document_objects[(requested_book_year, 'accnt')]
        description = account_request.name[:250]
        venice_account.Init()
        venice_account.SetFieldVal( venice_account.GetFieldID('Number'), str(account_request.accounting_number) )
        venice_account.SetFieldVal( venice_account.GetFieldID('DescrNld'), description )
        venice_account.SetFieldVal( venice_account.GetFieldID('DescrFra'), description )
        venice_account.SetFieldVal( venice_account.GetFieldID('DescrEng'), description )
        venice_account.SetFieldVal( venice_account.GetFieldID('DescrDeu'), description )
        venice_account.Insert(self.constants.imNoReport)
