# coding=utf-8
import datetime
import test_aanvaarding

from sqlalchemy import orm

from camelot.model.authentication import end_of_times
from camelot.test.action import MockModelContext

from vfinance.model.hypo import akte
from vfinance.model.hypo.notification.mortgage_table import MortgageTable
from vfinance.model.hypo.notification.deed_proposal import DeedProposal
from vfinance.model.hypo.summary.notary_settlement import NotarySettlement

from ... import test_case

akte_data_datum_verlijden = datetime.date(2007, 5, 2)
handlichting_data = dict(datum_verlijden=datetime.date(2009,5,2), bedrag=10000)

class AkteCase(test_case.SessionCase):

    @classmethod
    def setUpClass(cls):
        test_case.SessionCase.setUpClass()
        cls.aanvaarding_case = test_aanvaarding.AanvaardingCase('setUp')
        cls.aanvaarding_case.setUpClass()

    def setUp(self):
        super(AkteCase, self).setUp()
        from vfinance.model.bank.accounting import AccountingPeriod
        self.aanvaarding_case.setUp()
        self.aanvaarding = self.aanvaarding_case.aanvaarding
        self.aanvaarding.button_send()
        self.aanvaarding.button_received()
        self.beslissing = self.aanvaarding.beslissing
        self.akte = list(self.beslissing.akte)[-1]
        self.model_context = MockModelContext()
        self.model_context.obj = self.akte
        if AccountingPeriod.query.count() == 0:
            accounting_period = AccountingPeriod( from_date = datetime.date( 2000, 1, 1 ),
                                                  thru_date = end_of_times(),
                                                  from_book_date = datetime.date( 2000, 1, 1 ),
                                                  thru_book_date = end_of_times(),
                                                  from_doc_date = datetime.date( 2000, 1, 1 ),
                                                  thru_doc_date = end_of_times() )
            orm.object_session( accounting_period ).flush()        
        
    def test_deed_proposal( self ):
        action = DeedProposal()
        list( action.model_run( self.model_context ) )
        
    def test_notary_settlement( self ):
        action = NotarySettlement()
        for step in action.model_run( self.model_context ):
            self.assertTrue(u'Evest Belgium NV' in step.html)
            self.assertTrue(u'Am Hock 2' in step.html)
            self.assertTrue(u'9991' in step.html)
            self.assertTrue(u'Weiswampach' in step.html)
        
    def test_mortgage_table( self ):
        action = MortgageTable()
        for step in action.model_run( self.model_context ):
            self.assertTrue(u'Ms. Celie Dehaen, M. Alain François, Signor Cårlø Márcø' in step.html)
            self.assertTrue(u'Correspondentielaan 33' in step.html)
            self.assertTrue(u'Correspondentegem' in step.html)
        
    def test_juridisch_goedgekeurd_en_betaald_aan_notaris(self):
        self.assertEqual(self.akte.state, 'pending')
        list( akte.Valid().model_run( self.model_context ) )
        self.assertEqual(self.akte.state, 'valid')
        list( akte.Payed().model_run( self.model_context ) )
        self.assertEqual(self.akte.state, 'payed')
        
    def test_voer_door(self):
        self.test_juridisch_goedgekeurd_en_betaald_aan_notaris()
        self.akte.datum_verlijden = akte_data_datum_verlijden
        list( akte.CreateDossiers().model_run( self.model_context ) )
        list( akte.CreateMortgage().model_run( self.model_context ) )
        
    def test_handlichting(self):
        from vfinance.model.hypo.akte import Handlichting
        self.test_voer_door()
        self.assertEqual(self.akte.gehypothekeerd_totaal, 50000)
        self.assertEqual(self.akte.gemandateerd_totaal, 50000)
        handlichting = Handlichting() 
        handlichting.akte = self.akte
        handlichting.set( **handlichting_data )
        Handlichting.query.session.flush()
        self.assertEqual(self.akte.gehypothekeerd_totaal, 40000)
