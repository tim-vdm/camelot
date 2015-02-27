import datetime
import unittest

from camelot.core.exception import UserException
from camelot.core.orm import Session
from camelot.test.action import MockModelContext

from vfinance.model.bank.direct_debit import (DirectDebitBatch,
                                              ExportDirectDebitBatch,
                                              CloseDirectDebitBatch,
                                              NewDirectDebitBatch,
                                              direct_debit_status_report)
from vfinance.model.bank.invoice import InvoiceItem

from ... import test_branch_21

class DirectDebitCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.branch_21_case = test_branch_21.Branch21Case('setUp')
        cls.branch_21_case.setUpClass()

    def setUp(self):
        self.branch_21_case.setUp()
        self.premium_schedule = [premium for premium in self.branch_21_case.test_agreed_to_applied_premium_schedule() if premium.period_type=='monthly'][0]
        self.mandate = self.premium_schedule.financial_account.get_direct_debit_mandate_at(self.premium_schedule.valid_from_date)
        self.session = Session()

    def test_get_open_direct_debit_batch(self):
        batch_1 = DirectDebitBatch.get_open_direct_debit_batch(described_by='local')
        self.assertEqual(batch_1.current_status, 'draft')
        self.session.flush()
        batch_2 = DirectDebitBatch.get_open_direct_debit_batch(described_by='core')
        self.assertEqual(batch_1.current_status, 'draft')
        self.session.flush()
        batch_3 = DirectDebitBatch.get_open_direct_debit_batch(described_by='core')
        self.assertEqual(batch_1.current_status, 'draft')
        self.session.flush()
        self.assertNotEqual(batch_1, batch_2)
        self.assertEqual(batch_2, batch_3)

    def test_add_invoice_items(self):
        invoice_item_1 = InvoiceItem(premium_schedule=self.premium_schedule,
                                     doc_date=self.premium_schedule.valid_from_date,
                                     amount=20, item_description='Test invoice item')
        batch_1 = DirectDebitBatch(spildatum=self.premium_schedule.valid_from_date + datetime.timedelta(days=5))
        self.assertEqual(None, batch_1.direct_debit_item_for(invoice_item_1))
        direct_debit_item_1 = batch_1.append_invoice_items(self.mandate, self.premium_schedule.valid_from_date, 'Test direct debit item', [invoice_item_1])
        self.assertEqual(direct_debit_item_1, batch_1.direct_debit_item_for(invoice_item_1))
        self.assertEqual(direct_debit_item_1.sequence_type, 'FRST')
        self.session.flush()
        self.assertEqual(direct_debit_item_1.amount, 20)
        details = list(batch_1.generate_details())
        self.assertEqual(len(details), 1)
        self.assertEqual(sum((d.amount for d in details), 0), 20)
        # other items for the same mandate should end up in the same direct debit
        # item
        invoice_item_2 = InvoiceItem(premium_schedule=self.premium_schedule,
                                     doc_date=self.premium_schedule.valid_from_date,
                                     amount=30, item_description='Test invoice item')
        direct_debit_item_2 = batch_1.append_invoice_items(self.mandate, self.premium_schedule.valid_from_date, 'Test direct debit item', [invoice_item_2])
        self.assertEqual(direct_debit_item_1, direct_debit_item_2)
        direct_debit_item_1.status = 'rejected'
        direct_debit_item_2.status = 'rejected'
        self.session.flush()
        # create a second batch and append new invoice items
        batch_2 = DirectDebitBatch(spildatum=self.premium_schedule.valid_from_date + datetime.timedelta(days=10))
        invoice_item_3 = InvoiceItem(premium_schedule=self.premium_schedule,
                                     doc_date=self.premium_schedule.valid_from_date,
                                     amount=30, item_description='Test invoice item')
        with self.assertRaises(UserException):
            batch_2.append_invoice_items(self.mandate, self.premium_schedule.valid_from_date, 'Test item', [invoice_item_3])
        # after closing the first batch, appending to the second batch should work
        # if the previous item has not been accepted, a FRST item should be created again
        batch_1.change_status('closed')
        self.session.flush()
        direct_debit_item_3 = batch_2.append_invoice_items(self.mandate, self.premium_schedule.valid_from_date, 'Test item', [invoice_item_3])
        self.assertEqual(direct_debit_item_3.sequence_type, 'FRST')
        batch_2.change_status('closed')
        self.session.flush()
        # if the previous item has been accepted, an RCUR item should be created
        self.assertEqual(direct_debit_item_3.status, 'pending')
        direct_debit_item_3.status = 'accepted'
        self.session.flush()
        direct_debit_date = self.premium_schedule.valid_from_date + datetime.timedelta(days=20)
        batch_4 = DirectDebitBatch(spildatum=direct_debit_date)
        direct_debit_item_4 = batch_4.append_invoice_items(self.mandate, direct_debit_date, 'Test item', [invoice_item_3])
        self.assertEqual(direct_debit_item_4.sequence_type, 'RCUR')
        # if the previous item has been rejected, but an accepted FRST exists, the
        # an RCUR item should be created
        direct_debit_item_4.status = 'rejected'
        batch_4.change_status('closed')
        self.session.flush()
        direct_debit_date = self.premium_schedule.valid_from_date + datetime.timedelta(days=30)
        batch_5 = DirectDebitBatch(spildatum=direct_debit_date)
        invoice_item_4 = InvoiceItem(premium_schedule=self.premium_schedule,
                                     doc_date=direct_debit_date,
                                     amount=40, item_description='Test invoice item')
        direct_debit_item_5 = batch_5.append_invoice_items(self.mandate, direct_debit_date, 'Test item', [invoice_item_4])
        self.assertEqual(direct_debit_item_5.sequence_type, 'RCUR')

    def test_export_close_new(self):
        batch = DirectDebitBatch(described_by='core', spildatum=datetime.date.today()+datetime.timedelta(days=3))
        model_context = MockModelContext()
        model_context.obj = batch
        action = ExportDirectDebitBatch()
        self.assertFalse(action.get_state(model_context).enabled)
        self.session.flush()
        # batch should be complete and verified before it can be exported
        with self.assertRaises(UserException):
            list(action.model_run(model_context))
        invoice_item_1 = InvoiceItem(premium_schedule=self.premium_schedule,
                                     doc_date=self.premium_schedule.valid_from_date,
                                     amount=20, item_description='Test invoice item')
        batch.append_invoice_items(self.mandate, self.premium_schedule.valid_from_date, 'Test direct debit item', [invoice_item_1])
        with self.assertRaises(UserException):
            list(action.model_run(model_context))
        batch.change_status('complete')
        self.assertEqual(batch.current_status, 'complete')
        batch.change_status('verified')
        # once complete, it can be exported once
        list(action.model_run(model_context))
        self.assertNotEqual(batch.export, None)
        with self.assertRaises(UserException):
            list(action.model_run(model_context))
        # the batch can be closed
        action = CloseDirectDebitBatch()
        # failure because of pending items
        with self.assertRaises(UserException):
            list(action.model_run(model_context))
        for item in batch.composed_of:
            item.change_status('rejected')
        # failure because of wrong collected amount
        with self.assertRaises(UserException):
            for i, step in enumerate(action.model_run(model_context)):
                if i==0:
                    options = step.get_object()
                    options.collected_amount = 3
        # success after entering the collected amount
        for i, step in enumerate(action.model_run(model_context)):
            if i==0:
                options = step.get_object()
                options.collected_amount = 0
        self.assertEqual(batch.current_status, 'closed')
        # issue a new batch for the rejected items
        action = NewDirectDebitBatch()
        list(action.model_run(model_context))

    def test_rcur_mandate(self):
        self.mandate.sequence_type = 'RCUR'
        self.session.flush()
        batch = DirectDebitBatch(spildatum=self.premium_schedule.valid_from_date + datetime.timedelta(days=5))
        direct_debit_item = batch.append_item(self.mandate, self.mandate.from_date, 'test item')
        self.session.flush()
        self.assertEqual(direct_debit_item.sequence_type, 'RCUR')
        return direct_debit_item

    def test_status_report(self):
        item = self.test_rcur_mandate()
        status_report_1 = direct_debit_status_report(payment_group_id=str(item.part_of_id),
                                                     end_to_end_id=str(item.id),
                                                     amount=item.amount,
                                                     book_date=self.premium_schedule.valid_thru_date,
                                                     result='accepted',
                                                     reason=None)
        # an exception should be raised if the batch is not verified
        with self.assertRaises(UserException):
            list(DirectDebitBatch.handle_status_reports(self.session, [status_report_1]))
        item.part_of.change_status('verified')
        found_item = list(DirectDebitBatch.handle_status_reports(self.session, [status_report_1]))[-1]
        self.assertEqual(found_item.id, item.id)
        self.assertEqual(item.status, 'accepted')
        status_report_2 = direct_debit_status_report(payment_group_id=str(item.part_of_id),
                                                     end_to_end_id=str(item.id),
                                                     amount=item.amount,
                                                     book_date=self.premium_schedule.valid_thru_date,
                                                     result='rejected',
                                                     reason=None)
        list(DirectDebitBatch.handle_status_reports(self.session, [status_report_1, status_report_2]))
        self.assertEqual(item.status, 'rejected')

    def test_set_bic_for_iban(self):
        mandate = self.mandate
        self.assertEqual(mandate.bank_identifier_code.code, u'GEBABEBB')
        # Test if correct bic is set with belgian iban
        mandate._iban = u'BE56 6511 5262 8088'
        self.assertEqual(mandate.bank_identifier_code.code, u'KEYTBEBB')
        self.assertEqual(mandate.bank_identifier_code.name, u'Keytrade Bank')
        mandate._iban = u'be 94-0016-1862-1014'
        self.assertEqual(mandate.bank_identifier_code.code, u'GEBABEBB')
        self.assertEqual(mandate.bank_identifier_code.name, u'BNP Paribas')
        # Test if bic is untouched if non-belgian iban
        mandate._iban = u'NL91 ABNA 04171 64300'
        self.assertEqual(mandate.bank_identifier_code.code, u'GEBABEBB')
