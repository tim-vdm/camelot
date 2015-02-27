'''
Created on Jun 26, 2010

@author: tw55413
'''
import warnings
from sqlalchemy.exc import SADeprecationWarning
warnings.simplefilter( action='ignore',
                       category=SADeprecationWarning )

import logging

from xml.etree import ElementTree

from camelot.test import ModelThreadTestCase
from sqlalchemy.orm import object_session
from sqlalchemy import func, sql

from integration.venice.mock import set_next_unique_id
from vfinance.application_admin import FinanceApplicationAdmin
from vfinance.connector.accounting import (CreateSalesDocumentRequest,
                                           LineRequest)
from vfinance.model.bank import entry
from vfinance.model.financial.admin import RunAgreementForward
from vfinance.model.financial.notification.environment import setup_templates
from vfinance.model.bank.entry import Entry
from vfinance.model.financial.visitor.account_attribution import AccountAttributionVisitor
from vfinance.model.financial.visitor.supplier_attribution import SupplierAttributionVisitor

logger = logging.getLogger('vfinance.test.test_financial')

from test_case import SessionCase, test_data_folder
from .test_model.test_financial import FinancialMixinCase
from .test_model.test_bank import test_rechtspersoon

class AbstractFinancialCase(ModelThreadTestCase, SessionCase, FinancialMixinCase):
    """Some useful functions to create financial test cases"""

    @classmethod
    def setUpClass(cls):
        SessionCase.setUpClass()
        cls.test_data_folder = test_data_folder
        # set the next document number to be used by the venice mock to one that
        # is not in the database
        entry_table = entry.Entry.__table__
        entry_c = entry_table.columns
        max_doc_num = sql.func.max(entry_c.venice_doc)
        last_numbers_select = sql.select([max_doc_num.label('entry_doc')])
        for row in cls.session.execute(last_numbers_select):
            set_next_unique_id(row.entry_doc)
        setup_templates()
        cls.rechtspersoon_case = test_rechtspersoon.RechtspersoonCase('setUp')
        cls.rechtspersoon_case.setUpClass()
        cls.natuurlijke_persoon_case = cls.rechtspersoon_case.natuurlijke_persoon_case
        cls.setup_bic()

    def setUp(self):
        ModelThreadTestCase.setUp(self)
        SessionCase.setUp(self)
        self.setup_accounting_period()
        self._bic = self.bic_1
        self._bic2 = self.bic_2
        self.account_attribution_visitor = AccountAttributionVisitor()
        self.supplier_attribution_visitor = SupplierAttributionVisitor()
        self.visitor = self.account_attribution_visitor
        self.app_admin = FinanceApplicationAdmin()
        self.rechtspersoon_case.setUp()
    
    def button_agreement_forward(self, obj):
        """
        Simulate pressing run forward on the agreement
        """
        self.button(obj, RunAgreementForward())

    def button_complete(self, obj):
        """
        Simulate pressing the complete button
        """
        self.button(obj, self.status_complete)

    def button_draft(self, obj):
        """
        Simulate pressing the draft button
        """
        self.button(obj, self.status_draft)

    def button_incomplete(self, obj):
        """
        Simulate pressing the draft button
        """
        self.button(obj, self.status_incomplete)
        
    def button_verified(self, obj):
        """
        Simulate pressing the verified button
        """
        self.button(obj, self.status_verified)

    def button_cancel(self, obj):
        """
        Simulate pressing the cancel button
        """
        self.button(obj, self.status_cancel)
        
    def next_account_number_prefix(self):
        from vfinance.model.financial.product import FinancialProduct
        q = FinancialProduct.query.session.query( func.max(FinancialProduct.account_number_prefix) )
        max = q.scalar() or 0
        return max + 1
    
    def create_agreement(self, code=None):
        from vfinance.model.financial.agreement import FinancialAgreement
        from vfinance.model.financial.agreement import FinancialAgreementAssetUsage
        from vfinance.model.hypo.hypotheek import TeHypothekerenGoed
        from vfinance.test.test_model.test_hypo.test_waarborg import onroerend_goed_data
        asset_usage = TeHypothekerenGoed(**onroerend_goed_data)
        asset = FinancialAgreementAssetUsage(asset_usage=asset_usage)
        agreement = FinancialAgreement( package = self._package,
                                        code = code or self.next_agreement_code(),
                                        agreement_date = self.t0,
                                        from_date = self.t1,
                                        assets = [asset] )
        object_session( agreement ).flush()
        agreement.change_status('draft')
        return agreement

    def account_from_agreement(self, agreement):
        self.complete_agreement( agreement )
        for invested_amount in agreement.invested_amounts:
            self.fulfill_agreement( agreement, amount = invested_amount.amount )
        self.button_complete(agreement)
        self.button_verified(agreement)
        self.button_agreement_forward(agreement)
        return agreement.account

    def verify_last_notification_from_account(self, account, expected_type, index=-1, strings_present=None):
        """Generates the last notification for an account and
        verifies if the message is of an expected type and if it
        is valid xml.

        :return: the last notification, for further inspection
        """
        self.assertTrue( len(account.notifications) > 0 )
        notifications = list(account.notifications)
        notifications.sort(key=lambda n:n.date)
        notification = notifications[index]
        self.assertEqual( notification.application_of.notification_type, expected_type )
        notification.create_message()
        message = notification.message
        self.assertTrue( message )
        xml_stream = message.storage.checkout_stream( message )
        ElementTree.parse( xml_stream )
        xml = unicode( message.storage.checkout_stream( message ).read(), 'utf-8' )
        #logger.debug('XML: %s' % xml)
        if strings_present:
            self._assert_generated_string( xml, strings_present )
        return notification

    def _assert_generated_string( self, generated_string, strings_present ):
        """Assert the presence of a list of strings in a generated string"""
        for string_present in strings_present:
            string_present = unicode( string_present )
            logger.debug(u'testing string _{0}_'.format(string_present))
            if string_present not in generated_string:
                open('text_faulty.txt', 'wb').write( generated_string.encode('utf-8') )
                for i, line in enumerate(generated_string.split('\n')):
                    logger.error(u'line %04i : '%i + line )
                logger.error('String not found : %s'%string_present)            
            self.assertTrue( string_present in generated_string )
        # open('text_correct.txt', 'wb').write( generated_string.encode('utf-8') )
            
    def _assert_generated_document(self, doc, strings_present):
        logger.debug( 'inspecting generated document : %s'%doc )
        self.assertTrue(doc)
        self.assertTrue(strings_present)
        doc_content = unicode(open(doc, 'rb').read(), 'utf-8')
        self._assert_generated_string( doc_content, strings_present )
        # ElementTree.parse(doc_content)
        # TODO Check out http://doc.qt.nokia.com/4.7/qtxml.html for more useful parsing
        # ideally just return lineno of xml error


    def assert_generated_transaction_document(self, doc, strings_present):
        self._assert_generated_document(doc, strings_present)

    def assert_generated_account_movements_document(self, doc, strings_present):
        self._assert_generated_document(doc, strings_present)

    def assert_valid_transaction_document_context( self, context ):
        security_out_amount = sum( security_out_entry.amount for security_out_entry in context['security_out_entries'] )
        security_in_amount = sum( security_in_entry.amount for security_in_entry in context['security_in_entries'] )
        transaction_revenue = sum((transaction_revenue.amount for transaction_revenue in context['transaction_revenues']), 0)
        settlements = sum((settlement.amount for settlement in context['settlements']), 0)
        payments = sum((payment.amount for payment in context['payments']), 0)
        # Change the sign back to what it was here.
        # More info: Original sign change was done in the context, because it is more logical to show the \
        # numbers form the client's perspective \
        # (security_out_amount is what he loses, security_in_amount is what he gains) \
        # instead of the company's bookkeeping perspective of the numbers.
        result = sum([(security_out_amount * -1), (security_in_amount * -1), transaction_revenue, settlements, payments])
        expected = context['customer_attribution']
        self.assertEqual( result, expected )

    def assert_valid_account_movements_document_context( self, context ):
        from_value = context['from_value']
        thru_value = context['thru_value']
        delta = sum( (account_movement.amount for account_movement in context['account_movements']), 0 )
        self.assertEqual( from_value + delta, thru_value )
        funds_total = 0
        for ps_state in context['premium_schedule_states']:
            for fund_data in ps_state.funds_data:
                funds_total += fund_data.amount
        uninvested = 0
        for ps_state in context['premium_schedule_states']:
            uninvested += ps_state.uninvested
        self.assertEqual( thru_value, funds_total + uninvested )

    def get_last_sales_document(self):
        last_entry = self.session.query(Entry).filter(Entry.venice_book_type=='V').order_by(Entry.id.desc()).first()
        if last_entry is None:
            raise Exception('no last entry found')
        entries = last_entry.same_document
        entries.sort(key=lambda e:e.line_number)
        lines = [LineRequest(account=entry.account, 
                             remark=entry.remark,
                             amount=entry.amount,
                             quantity=entry.quantity,
                             line_number=entry.line_number) for entry in entries]
        return CreateSalesDocumentRequest(
            book_date = entry.book_date,
            document_date = entry.doc_date,
            document_number = entry.venice_doc,
            book = entry.venice_book,
            lines = lines)
