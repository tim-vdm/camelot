import datetime
from decimal import Decimal as D
import operator

import test_dossier

from sqlalchemy import orm, sql

from camelot.core.exception import UserException
from camelot.test.action import MockModelContext

from vfinance.model.bank.entry import Entry, EntryPresence, TickSession
from vfinance.model.bank.visitor import CustomerBookingAccount
from vfinance.model.hypo.akte import Akte
from vfinance.model.hypo.beslissing import GoedgekeurdBedrag, Beslissing
from vfinance.model.hypo.dossier import Dossier, Factuur
from vfinance.model.hypo.periodieke_verichting import (Periode,
                                                       Vervaldag,
                                                       AppendToDirectDebitBatch,
                                                       CancelInvoiceItem,
                                                       CreateRepayments,
                                                       CreateDossierRepayments,
                                                       BookInvoiceItem,
                                                       UnbookInvoiceItem,
                                                       RevertInvoiceItem,
                                                       RemoveRepayments,
                                                       BookRepayments,
                                                       UnbookRepayments)
from vfinance.model.bank.direct_debit import DirectDebitBatch, DirectDebitItem
from vfinance.model.hypo.visitor import AbstractHypoVisitor

periode_data = dict( startdatum = datetime.date(2007,6,1),
                     einddatum = datetime.date(2007,6,30) )

from ...import app_admin, test_case

class PeriodiekeVerichtingCase(test_case.SessionCase):

    @classmethod
    def setUpClass(cls):
        test_case.SessionCase.setUpClass()
        cls.dossier_case = test_dossier.DossierCase('setUp')
        cls.dossier_case.setUpClass()

    def setUp(self):
        super(PeriodiekeVerichtingCase, self).setUp()
        self.dossier_case.setUp()
        self.periode = Periode( **periode_data )
        self.dossier = self.dossier_case.dossier
        self.session.flush()

    def close_all_batches(self):
        for item in self.session.query(DirectDebitItem).filter(DirectDebitItem.status=='pending'):
            item.status = 'accepted'
        for batch in self.session.query(DirectDebitBatch).all():
            batch.change_status('closed')
        self.session.flush()

    def test_opname_schijven(self):
        create_repayments_action = CreateRepayments()
        beslissing = Beslissing(state='processed')
        beslissing.akte.append(Akte(datum_verlijden=datetime.date(2012,5,22)))
        goedgekeurd_bedrag = GoedgekeurdBedrag(goedgekeurde_rente='0.287',
                                               goedgekeurd_bedrag=D('20281.99'),
                                               goedgekeurde_looptijd=120,
                                               goedgekeurde_opname_schijven=12,
                                               goedgekeurd_terugbetaling_interval=12,
                                               goedgekeurd_type_vervaldag='maand',
                                               beslissing=beslissing,
                                               goedgekeurd_type_aflossing='vaste_aflossing',
                                               type='nieuw',
                                               state='processed')
        dossier = Dossier(originele_startdatum=datetime.date(2012,5,2),
                          goedgekeurd_bedrag=goedgekeurd_bedrag)

        Factuur(dossier=dossier, datum=datetime.date(2012, 5,22),  bedrag=D('281.99'))
        Factuur(dossier=dossier, datum=datetime.date(2012, 5,23), bedrag=D('8490'))
        Factuur(dossier=dossier, datum=datetime.date(2012, 8, 1),  bedrag=D('780'))
        Factuur(dossier=dossier, datum=datetime.date(2012,10, 8), bedrag=D('2276'))
        Factuur(dossier=dossier, datum=datetime.date(2012,10,10), bedrag=D('2859'))
        Factuur(dossier=dossier, datum=datetime.date(2012,11,28), bedrag=D('1051'))
        Factuur(dossier=dossier, datum=datetime.date(2012,12, 5), bedrag=D('1816'))
        
        from_date = datetime.date(2012,12, 1)
        thru_date = datetime.date(2012,12,31)
        steps = list(create_repayments_action.create_repayments(dossier, goedgekeurd_bedrag, from_date, thru_date))
        self.assertEqual( len(steps), 1 )
        repayment = steps[0].get_object()
        self.assertEqual( repayment.nummer,   7 )
        self.assertEqual( repayment.kapitaal, D('144.28') )
        self.assertEqual( repayment.rente,     D('39.99') )
        self.assertEqual( repayment.doc_date, datetime.date(2012,12,1) )
    
    def test_opname_schijven_eerste_vervaldag(self):
        create_repayments_action = CreateRepayments()
        beslissing = Beslissing(state='processed')
        beslissing.akte.append(Akte(datum_verlijden=datetime.date(2012,10,8)))
        goedgekeurd_bedrag = GoedgekeurdBedrag(goedgekeurde_rente='0.315',
                                               goedgekeurd_bedrag=D('13487.44'),
                                               goedgekeurde_looptijd=180,
                                               goedgekeurde_opname_schijven=12,
                                               goedgekeurd_terugbetaling_interval=12,
                                               goedgekeurd_type_vervaldag='maand',
                                               beslissing=beslissing,
                                               goedgekeurd_type_aflossing='vaste_aflossing',
                                               type='nieuw',
                                               state='processed')
        dossier = Dossier(originele_startdatum=datetime.date(2012,10,2),
                          goedgekeurd_bedrag=goedgekeurd_bedrag)

        Factuur(dossier=dossier, datum=datetime.date(2012,12,3),  bedrag=D('268.00'))
        Factuur(dossier=dossier, datum=datetime.date(2012,11,20), bedrag=D('2056.00'))
        Factuur(dossier=dossier, datum=datetime.date(2012,10,11), bedrag=D('4004.00'))
        Factuur(dossier=dossier, datum=datetime.date(2012,10,8),  bedrag=D('987.44'))
        
        from_date = datetime.date(2012,12, 1)
        thru_date = datetime.date(2012,12,31)
        steps = list(create_repayments_action.create_repayments(dossier, goedgekeurd_bedrag, from_date, thru_date))
        self.assertEqual( len(steps), 1 )
        repayment = steps[0].get_object()
        self.assertEqual( repayment.nummer,   2 )
        self.assertEqual( repayment.kapitaal, D('111.76') )
        self.assertEqual( repayment.rente,     D('28.76') ) # 28.71 volgens Hyposoft
        self.assertEqual( repayment.doc_date, datetime.date(2012,12,1) )
    
    def test_opname_schrijven_zonder_betaling(self):
        # dossier 2771 van eigen huis
        create_repayments_action = CreateRepayments()
        beslissing = Beslissing(state='processed')
        beslissing.akte.append(Akte(datum_verlijden=datetime.date(2013,7,3)))
        goedgekeurd_bedrag = GoedgekeurdBedrag(goedgekeurde_rente='0.3050',
                                               goedgekeurd_bedrag=D('20000'),
                                               goedgekeurde_looptijd=120,
                                               goedgekeurde_opname_schijven=12,
                                               goedgekeurd_terugbetaling_interval=12,
                                               goedgekeurd_type_vervaldag='maand',
                                               beslissing=beslissing,
                                               goedgekeurd_type_aflossing='vaste_aflossing',
                                               type='nieuw',
                                               state='processed')
        dossier = Dossier(originele_startdatum=datetime.date(2013,7,2),
                          goedgekeurd_bedrag=goedgekeurd_bedrag)

        from_date = datetime.date(2013,9, 1)
        thru_date = datetime.date(2013,9,30)
        steps = list(create_repayments_action.create_repayments(dossier, goedgekeurd_bedrag, from_date, thru_date))
        self.assertEqual( len(steps), 1 )
        repayment = steps[0].get_object()
        self.assertEqual( repayment.nummer,   2 )
        self.assertEqual( repayment.kapitaal, D('276.96') )
        self.assertEqual( repayment.rente,      D('0') )
        self.assertEqual( repayment.doc_date, datetime.date(2013,9,1) )

    #def test_opname_schijven_te_veel_betaling(self):
        ## dossier WMH 159-01-01925-34
        ## er werden meer schijven uitbetaald dan voorzien in de oorspronkelijke
        ## aflossingstabel
        #create_repayments_action = CreateRepayments()
        #beslissing = Beslissing(state='processed')
        #beslissing.akte.append(Akte(datum_verlijden=datetime.date(2010,12,2)))
        #goedgekeurd_bedrag = GoedgekeurdBedrag(goedgekeurde_rente='0.21',
                                               #goedgekeurd_bedrag=D('83125.40'),
                                               #goedgekeurde_looptijd=117,
                                               #goedgekeurde_opname_schijven=21,
                                               #goedgekeurd_terugbetaling_interval=12,
                                               #goedgekeurd_type_vervaldag='maand',
                                               #beslissing=beslissing,
                                               #goedgekeurd_type_aflossing='vaste_aflossing',
                                               #type='nieuw',
                                               #state='processed')
        #dossier = Dossier(originele_startdatum=datetime.date(2010,12,2),
                          #goedgekeurd_bedrag=goedgekeurd_bedrag)
        #Factuur(dossier=dossier, datum=datetime.date(2011,12,22),  bedrag=D('85000.00'))
        #from_date = datetime.date(2014,1, 1)
        #thru_date = datetime.date(2014,1,31)
        #steps = list(create_repayments_action.create_repayments(dossier, goedgekeurd_bedrag, from_date, thru_date))
        #self.assertEqual( len(steps), 1 )
        #repayment = steps[0].get_object()

    def test_tick_date(self):
        model_context = MockModelContext()
        model_context.obj = self.periode
        create_repayments_action = CreateRepayments()
        book_repayments_action = BookRepayments()
        list(create_repayments_action.model_run(model_context))
        list(book_repayments_action.model_run(model_context))
        visitor = AbstractHypoVisitor()
        loan_schedule = self.dossier.goedgekeurd_bedrag
        customer_account = CustomerBookingAccount()
        # at first, there should be no payment
        ticked_entries = visitor.get_entries(loan_schedule,
            account=customer_account, conditions=[('tick_date', operator.ge, self.periode.startdatum)])
        self.assertEqual(len(list(ticked_entries)), 0)
        # fake the payments for the repayment
        for entry in visitor.get_entries(loan_schedule,
                                         account=customer_account,
                                         from_document_date=self.periode.startdatum,
                                         thru_document_date=self.periode.einddatum):
            payment_date = entry.doc_date + datetime.timedelta(days=2)
            active_year = str(entry.book_date.year)
            EntryPresence(entry_id=entry.id,
                          venice_active_year=active_year,
                          venice_id=entry.id)
            TickSession(venice_tick_session_id=entry.id,
                        venice_active_year=active_year,
                        venice_id=entry.id)
            payment = Entry(line_number=1,
                            open_amount=0,
                            ticked=True,
                            remark='payment',
                            venice_active_year=active_year,
                            venice_doc=sql.select([sql.func.max(Entry.venice_doc)+1]),
                            account=entry.account,
                            amount=entry.amount * -1,
                            book_date=payment_date,
                            datum=payment_date,
                            venice_id=sql.select([sql.func.max(Entry.venice_doc)+1]),
                            venice_book='KBCHypot')
            model_context.session.flush()
            EntryPresence(entry_id=payment.id,
                          venice_active_year=active_year,
                          venice_id=payment.id)
            TickSession(venice_tick_session_id=entry.id,
                        venice_active_year=active_year,
                        venice_id=payment.id)
            entry = model_context.session.query(Entry).filter(Entry.id==entry.id).first()
            entry.open_amount = 0
            model_context.session.flush()
        # now, all repayments should be ticked
        ticked_entries = visitor.get_entries(loan_schedule,
            account=customer_account, conditions=[('tick_date', operator.ge, self.periode.startdatum)])
        self.assertNotEqual(len(list(ticked_entries)), 0)
        # while no entries are ticked in the past
        ticked_entries = visitor.get_entries(loan_schedule,
            account=customer_account, conditions=[('tick_date', operator.lt, self.periode.startdatum)])
        self.assertEqual(len(list(ticked_entries)), 0)
        
    def test_create_repayments_period(self):
        self.assertTrue(self.dossier.domiciliering, True)
        # create generic booking actions
        book_action = BookInvoiceItem()
        unbook_action = UnbookInvoiceItem()
        revert_action = RevertInvoiceItem()
        create_repayments_action = CreateRepayments()
        book_repayments_action = BookRepayments()
        unbook_repayments_action = UnbookRepayments()
        remove_repayments_action = RemoveRepayments()
        # test the execution of the actions
        model_context = MockModelContext()
        model_context.obj = self.periode
        list(remove_repayments_action.model_run(model_context))
        list(create_repayments_action.model_run(model_context))
        self.assertEqual(len(list(self.dossier.repayments)), 1)
        vervaldag = list(self.dossier.repayments)[-1]
        self.assertTrue( unicode( vervaldag ) )
        self.assertFalse( vervaldag.laatste_domiciliering )
        self.assertEqual(vervaldag.nummer, 1)
        self.assertEqual(vervaldag.doc_date, datetime.date(2007,6,1) )
        self.assertEqual(len(vervaldag.bookings), 0)
        # test book/unbook/revert of repayment
        repayment_context = MockModelContext()
        repayment_context.obj = vervaldag
        repayment_context.admin = app_admin
        list(book_action.model_run(repayment_context))
        self.assertTrue(vervaldag.booked_amount)
        self.assertTrue(revert_action.get_state(repayment_context).enabled)
        list(unbook_action.model_run(repayment_context))
        self.assertEqual(vervaldag.booked_amount, 0)
        self.assertFalse(revert_action.get_state(repayment_context).enabled)
        list(book_action.model_run(repayment_context))
        self.assertTrue(vervaldag.booked_amount)
        list(revert_action.model_run(repayment_context))
        self.assertEqual(vervaldag.booked_amount, 0)
        # a reverted booking can no longer be unbooked
        list(unbook_action.model_run(repayment_context))
        self.assertTrue(len(vervaldag.bookings))
        # test book/unbook of complete period
        period_context = MockModelContext()
        period_context.obj = self.periode
        period_context.admin = app_admin
        list(unbook_repayments_action.model_run(period_context))
        bookings_after_unbooking = len(vervaldag.bookings)
        list(book_repayments_action.model_run(period_context))
        bookings_after_booking = len(vervaldag.bookings)
        self.assertNotEqual(bookings_after_booking, 0)
        self.assertTrue(bookings_after_booking > bookings_after_unbooking)
        list(unbook_action.model_run(repayment_context))
        self.assertTrue(len(vervaldag.bookings) < bookings_after_booking)
        # repayment cannot be deleted, as there are still related bookings/reverted
        # bookings
        with self.assertRaises(UserException):
            app_admin.get_related_admin(Vervaldag).delete(vervaldag)
        # test appending of repayments to direct debit batch
        # refetch vervaldag, as the previous one was deleted
        self.close_all_batches()
        self.assertFalse(vervaldag.laatste_domiciliering)
        append_to_direct_debit = AppendToDirectDebitBatch()
        list(append_to_direct_debit.model_run(model_context))
        self.assertTrue(vervaldag.laatste_domiciliering)

    def test_create_repayments_dossier(self):
        book_action = BookInvoiceItem()
        # test repayments on dossier level
        dossier_context = MockModelContext()
        dossier_context.obj = self.dossier
        dossier_context.admin = app_admin
        orm.object_session( self.dossier ).expire( self.dossier )
        create_dossier_repayments_action = CreateDossierRepayments()
        self.assertEqual(len(list(self.dossier.repayments)), 0 )
        list(create_dossier_repayments_action.model_run(dossier_context))
        orm.object_session( self.dossier ).expire( self.dossier )
        repayments_in_period = [r for r in self.dossier.repayments if (r.doc_date <= self.periode.startdatum and r.doc_date >= self.periode.startdatum)]
        self.assertEqual(len(repayments_in_period), 1)
        # vvd w doorgevoerd, zodanig dat subsequent tests er gebruik kunnen
        # van maken
        repayment_context = MockModelContext(session=self.session)
        repayment_context.selection = self.dossier.repayments
        repayment_context.admin = app_admin
        list(book_action.model_run(repayment_context))

    def test_cancel_repayments(self):
        # if past repayments are wrong, they should be canceled, and correct
        # repayments should be created
        dossier_context = MockModelContext()
        dossier_context.obj = self.dossier
        dossier_context.admin = app_admin
        create_dossier_repayments_action = CreateDossierRepayments()
        repayments_query = orm.object_session(self.dossier).query(Vervaldag)
        repayments_query = repayments_query.filter(Vervaldag.dossier_id == self.dossier.id)
        repayments_query = repayments_query.filter(Vervaldag.doc_date <= self.periode.startdatum)
        repayments_query = repayments_query.filter(Vervaldag.doc_date >= self.periode.startdatum)
        # create the repayments
        self.assertEqual(repayments_query.count(), 0)
        list(create_dossier_repayments_action.model_run(dossier_context))
        self.assertEqual(repayments_query.count(), 1)
        # book the repayment
        repayment_model_context = MockModelContext()
        repayment_model_context.obj = repayments_query.first()
        book_repayment = BookInvoiceItem()
        list(book_repayment.model_run(repayment_model_context))
        for repayment in repayments_query.all():
            self.assertTrue(repayment.booked_amount)
        # cancel should not work
        cancel_repayment = CancelInvoiceItem()
        with self.assertRaises(UserException):
            list(cancel_repayment.model_run(repayment_model_context))
        # revert the invoice item
        revert_repayment = RevertInvoiceItem()
        list(revert_repayment.model_run(repayment_model_context))
        # cancel should work now
        list(cancel_repayment.model_run(repayment_model_context))
        # booking should no longer work
        with self.assertRaises(UserException):
            list(book_repayment.model_run(repayment_model_context))
        for repayment in repayments_query.all():
            self.assertFalse(repayment.booked_amount)
        # re-create the repayments
        list(create_dossier_repayments_action.model_run(dossier_context))
        self.assertEqual(repayments_query.count(), 2)

