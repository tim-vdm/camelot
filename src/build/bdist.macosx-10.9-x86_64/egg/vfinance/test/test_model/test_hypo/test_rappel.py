# coding=utf-8
import datetime
from decimal import Decimal as D

import test_period

from camelot.core.conf import settings
from camelot.core.exception import UserException
from camelot.view import action_steps
from camelot.test.action import MockModelContext

from vfinance.model.hypo.notification.rappel_sheet import RappelSheet, DossierSheet
from vfinance.model.hypo.notification.rappel_letter import RappelLetter
from vfinance.model.hypo.dossier import (SyncVenice, CreateReminder)
from vfinance.model.hypo.periodieke_verichting import (BookInvoiceItem,
                                                       UnbookInvoiceItem,
                                                       CancelInvoiceItem,
                                                       SendInvoiceItem)
from vfinance.model.hypo.rappel_brief import AppendToDirectDebitBatch

from ...import app_admin, test_case

class RappelCase(test_case.SessionCase):

    @classmethod
    def setUpClass(cls):
        test_case.SessionCase.setUpClass()
        cls.period_case = test_period.PeriodiekeVerichtingCase('setUp')
        cls.period_case.setUpClass()

    def setUp(self):
        super(RappelCase, self).setUp()
        self.period_case.setUp()
        self.dossier_case = self.period_case.dossier_case
        self.dossier_context = MockModelContext()
        self.dossier_context.obj = self.dossier_case.dossier
        self.dossier_context.admin = app_admin
        self.period_case.close_all_batches()

    def test_dossier_sheet(self):
        dossier_sheet_action = DossierSheet()
        list(dossier_sheet_action.model_run(self.dossier_context))
        
    def test_rappel_brief(self):
        reminder_action = CreateReminder()
        rappel_sheet_action = RappelSheet()
        rappel_letter_action = RappelLetter()
        self.period_case.test_create_repayments_dossier()
        # create generic booking actions
        book_action = BookInvoiceItem()
        unbook_action = UnbookInvoiceItem()
        cancel_action = CancelInvoiceItem()
        send_action = SendInvoiceItem()
        # setup a model context
        reminder_context = MockModelContext()
        reminder_context.admin = app_admin
        # aanmaak 2 rappel brieven opdate kosten vorige brief ook in nieuwe
        # brief komen te staan
        for step in reminder_action.model_run(self.dossier_context):
            if isinstance(step, action_steps.ChangeObject):
                step.get_object().doc_date = datetime.date(2007,8,1)
        # creating the second letter fails when first is not yet processed
        with self.assertRaises(UserException):
            list(reminder_action.model_run(self.dossier_context))
        reminder_context.obj = list(self.dossier_case.dossier.rappelbrief)[-1]
        list(send_action.model_run(reminder_context))
        # after sending the first letter, the second can be created
        for step in reminder_action.model_run(self.dossier_context):
            if isinstance(step, action_steps.ChangeObject):
                step.get_object().doc_date = datetime.date(2007,9,1)
        self.dossier_case.assertEqual(len(list(self.dossier_case.dossier.rappelbrief)), 2)
        rappel = list(self.dossier_case.dossier.rappelbrief)[-1]
        self.assertEqual(rappel.status, 'to_send')
        self.assertEqual(rappel.open_amount, D(settings.HYPO_RAPPEL_KOST))
        self.assertEqual(rappel.kosten_rappelbrieven, D(settings.HYPO_RAPPEL_KOST))
        reminder_context.obj = rappel
        list(send_action.model_run(reminder_context))
        self.assertEqual(rappel.status, 'send')
        openstaande_vvd = list(rappel.openstaande_vervaldag)
        self.assertEqual(len(openstaande_vvd), 1)
        ovvd = openstaande_vvd[0]
        self.assertTrue(ovvd.intrest_a)
        self.assertTrue(ovvd.intrest_b)
        self.assertEqual(ovvd.open_amount, ovvd.intrest_a + ovvd.intrest_b)
        # test book/unbook of repayment reminder
        repayment_reminder_context = MockModelContext()
        repayment_reminder_context.obj = ovvd
        repayment_reminder_context.admin = app_admin
        list(book_action.model_run(repayment_reminder_context))
        self.assertTrue(len(ovvd.bookings))
        self.assertEqual(ovvd.bookings[0].entry_book, 'HyRa')
        list(unbook_action.model_run(repayment_reminder_context))
        self.assertFalse(len(ovvd.bookings))
        # test book/unbook of complete reminder
        reminder_context.obj = rappel
        list(book_action.model_run(reminder_context))
        self.assertTrue(len(rappel.bookings))
        self.assertEqual(rappel.bookings[0].entry_book, 'HyRa')
        # ovvd is only booked by default when a payment has been made
        #self.assertTrue(ovvd.entry_document)
        #self.assertEqual(ovvd.entry_book, 'HyRa')
        list(unbook_action.model_run(reminder_context))
        self.assertFalse(len(rappel.bookings))
        self.assertFalse(len(ovvd.bookings))
        # test cancel of complete reminder
        list(cancel_action.model_run(reminder_context))
        self.assertEqual(rappel.status, 'canceled')
        self.assertEqual(ovvd.status, 'canceled')
        # test send of complete reminder
        list(send_action.model_run(reminder_context))
        self.assertEqual(rappel.status, 'send')
        self.assertEqual(ovvd.status, 'send')
        list( rappel_sheet_action.model_run( reminder_context ) )
        rappel.rappel_level = 1
        for step in rappel_letter_action.model_run( reminder_context ):
            if isinstance(step, action_steps.PrintJinjaTemplate):
                self.assertTrue(u'Ms. Celie Dehaen' in step.html)
                self.assertTrue(u'Correspondentielaan 33' in step.html)
                self.assertTrue(u'Correspondentegem' in step.html)
                self.assertTrue(u'AANGETEKEND' in step.html)
                # dont test next letter
                break
        rappel.rappel_level = 2
        for step in rappel_letter_action.model_run( reminder_context ):
            if isinstance(step, action_steps.PrintJinjaTemplate):
                self.assertTrue(u'Ms. Celie Dehaen' in step.html)
                self.assertTrue(u'Correspondentielaan 33' in step.html)
                self.assertTrue(u'Correspondentegem' in step.html)
                self.assertTrue(u'AANGETEKEND' in step.html)
                self.assertTrue(u'ondanks onze vorige aanmaning' in step.html)
                # dont test next letter
                break
        rappel.rappel_level = 3
        for step in rappel_letter_action.model_run( reminder_context ):
            if isinstance(step, action_steps.PrintJinjaTemplate):
                self.assertTrue(u'Ms. Celie Dehaen' in step.html)
                self.assertTrue(u'Correspondentielaan 33' in step.html)
                self.assertTrue(u'Correspondentegem' in step.html)
                self.assertTrue(u'AANGETEKENDE INGEBREKESTELLING' in step.html)
                # dont test next letter
                break
        rappel.rappel_level = 4
        for step in rappel_letter_action.model_run( reminder_context ):
            if isinstance(step, action_steps.PrintJinjaTemplate):
                self.assertTrue(u'Ms. Celie Dehaen' in step.html)
                self.assertTrue(u'Correspondentielaan 33' in step.html)
                self.assertTrue(u'Correspondentegem' in step.html)
                self.assertTrue(u'AANGETEKEND – OPZEGGING KREDIET' in step.html)
                # dont test next letter
                break
        return rappel

    def test_direct_debit_of_reminder(self):
        reminder = self.test_rappel_brief()
        self.period_case.close_all_batches()
        reminder_context = MockModelContext()
        reminder_context.obj = reminder
        reminder_context.admin = app_admin
        append_to_direct_debit = AppendToDirectDebitBatch()
        self.assertFalse(reminder.laatste_domiciliering)
        for repayment_reminder in reminder.openstaande_vervaldag:
            self.assertFalse(repayment_reminder.laatste_domiciliering)
        total_direct_debit = 0
        for step in append_to_direct_debit.model_run(reminder_context ):
            if isinstance(step, action_steps.ChangeObjects):
                proposals = step.get_objects()
                # expect 2 letters, 1 repayment and 1 repayment reminder
                self.assertEqual(len(proposals), 4)
                total_direct_debit = sum((p.direct_debit_amount for p in proposals), 0)
        self.assertEqual(total_direct_debit, reminder.openstaand_saldo)
        # verifieer of rappel zaken in domicil zitten
        self.assertTrue(reminder.laatste_domiciliering)
        for repayment_reminder in reminder.openstaande_vervaldag:
            self.assertTrue(repayment_reminder.laatste_domiciliering)

    def test_sync_venice( self ):
        sync_venice = SyncVenice()
        self.test_rappel_brief()
        list( sync_venice.model_run( self.dossier_case.model_context ) )
