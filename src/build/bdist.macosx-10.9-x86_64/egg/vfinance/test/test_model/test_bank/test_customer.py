import logging
import unittest

from vfinance.model.bank.summary import CustomerSummary

from ...test_connector import test_accounting

logger = logging.getLogger('vfinance.test.test_bank.test_customer')


class CustomerCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        unittest.TestCase.setUpClass()
        cls.accounting_case = test_accounting.InternalAccountingCase('setUp')
        cls.accounting_case.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.accounting_case.tearDownClass()

    def setUp(self):
        super(CustomerCase, self).setUp()
        self.accounting_case.setUp()

    def tearDown(self):
        super(CustomerCase, self).tearDown()
        self.accounting_case.tearDown()

    def test_summary( self ):
        from camelot.test.action import MockModelContext
        model_context = MockModelContext()
        model_context.obj = self.accounting_case.test_create_customer()
        summary = CustomerSummary()
        list( summary.model_run( model_context ) )

