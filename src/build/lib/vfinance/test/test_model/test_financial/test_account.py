# ! encoding: utf-8

import datetime
import unittest

from camelot.test.action import MockModelContext

from vfinance.application_admin import FinanceApplicationAdmin
from vfinance.model.financial.account import FinancialAccountChange
from vfinance.model.bank import direct_debit

class FinancialAccountCase( unittest.TestCase ):

    @classmethod
    def setUpClass(cls):
        from vfinance.test.test_branch_21 import Branch21Case
        cls.branch_21_case = Branch21Case('setUp')
        cls.branch_21_case.setUpClass()

    def setUp( self ):
        self.branch_21_case.setUp()
        self.app_admin = FinanceApplicationAdmin()
        self.premium_schedule = self.branch_21_case.test_agreed_to_applied_premium_schedule()[0]
        self.financial_account = self.premium_schedule.financial_account
        self.model_context = MockModelContext()
        self.model_context.obj = self.financial_account
        self.model_context.admin = self.app_admin
    
    def test_account_change( self ):
        change_action = FinancialAccountChange()
        for i, step in enumerate( change_action.model_run( self.model_context ) ):
            if i == 0:
                options = step.get_object()
                options.change = 'broker_relation'
                options.from_date = datetime.date( 2012, 1, 1 )
                options.new_broker_relation = self.branch_21_case.rechtspersoon_case.broker_relation

    def test_addressees(self):
        addressees = self.financial_account.get_notification_addressees(datetime.date( 2012, 1, 1 ))
        self.assertEqual(len(addressees), 1)
        self.assertEqual(len(addressees[0].persons), 1)
        self.assertEqual(addressees[0].organization, None)
        self.assertEqual(addressees[0].persons[0].personal_title, u'Ms.')
        self.assertEqual(addressees[0].persons[0].first_name, u'Celie')
        self.assertEqual(addressees[0].persons[0].last_name, u'Dehaen')
        self.assertEqual(addressees[0].street1, u'Teststraat 12b')
        self.assertEqual(addressees[0].street2, None)
        self.assertEqual(addressees[0].city_code, u'2222')
        self.assertEqual(addressees[0].city, u'Testergem Cité')
        self.assertEqual(addressees[0].country_code, u'BE')
        self.assertEqual(addressees[0].country, u'Belgium')

    def test_direct_debit_mandates_editability_on_status(self):
        adm = self.app_admin.get_related_admin(direct_debit.DirectDebitMandate)
        self.financial_account.change_status('delayed')
        attribute = getattr(self.financial_account, 'direct_debit_mandates')
        self.assertNotEqual([], attribute)
        for entr in attribute:
            attribs = adm.get_dynamic_field_attributes(entr, adm.list_display)
            self.assertNotEqual([], attribs)
            for attr in attribs:
                if(attr['editable']):
                    break
            else:
                self.fail("No editable fields despite status 'delayed'")
        self.financial_account.change_status('active')
        for entr in attribute:
            attribs = adm.get_dynamic_field_attributes(entr, adm.list_display)
            for attr in attribs:
                self.assertFalse(attr['editable'])
