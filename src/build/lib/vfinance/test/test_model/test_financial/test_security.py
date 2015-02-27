import datetime

from camelot.model.fixture import Fixture

from vfinance.model.financial import security

from ...test_case import SessionCase

class MixinFinancialSecurityCase(object):

    @classmethod
    def set_up_funds(cls):
        cls.fund_1 = Fixture.insert_or_update_fixture(
            security.FinancialFund,
            fixture_key='test_1',
            fixture_class='unittest',
            values = dict(
                name=u'Test 1', 
                isin=u'TST1',
                order_lines_from = datetime.date(2000, 1, 1),
                transfer_revenue_account = u'771',
                purchase_delay = 5,
                sales_delay = 4))
        cls.fund_2 = Fixture.insert_or_update_fixture(
            security.FinancialFund,
            fixture_key='test_2',
            fixture_class='unittest',
            values = dict(
                name=u'Test 2', 
                isin=u'TST2',
                order_lines_from = datetime.date(2000, 1, 1),
                transfer_revenue_account = u'772',
                purchase_delay = 5,
                sales_delay = 4))
        cls.fund_3 = Fixture.insert_or_update_fixture(
            security.FinancialFund,
            fixture_key='test_3',
            fixture_class='unittest',
            values = dict(
                name=u'Test 3', 
                isin=u'TST3',
                order_lines_from = datetime.date(2000, 1, 1),
                transfer_revenue_account = u'771',
                purchase_delay = 5,
                sales_delay = 4))

class FinancialSecurityCase(SessionCase, MixinFinancialSecurityCase):

    @classmethod
    def setUpClass(cls):
        SessionCase.setUpClass()
        MixinFinancialSecurityCase.set_up_funds()

    def test_security_quotation(self):
        quotation = security.FinancialSecurityQuotation(financial_security=self.fund_1,
                                                        from_datetime=datetime.datetime(2013,5,20),
                                                        value=10)
        self.assertEqual( security.default_purchase_date( quotation ), datetime.date(2013,5,15) )
        self.assertEqual( security.default_sales_date( quotation ), datetime.date(2013,5,16) )
        self.assertFalse( quotation.note )
        quotation.sales_date = datetime.date(2013,5,21)
        self.assertTrue( quotation.note)
