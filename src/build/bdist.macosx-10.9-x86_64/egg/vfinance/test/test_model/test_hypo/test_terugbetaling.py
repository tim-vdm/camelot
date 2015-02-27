# coding=utf-8
import datetime

import test_period

from vfinance.model.hypo import terugbetaling
from vfinance.test.test_documents import TestDocument
from vfinance.model.hypo.summary.redemption import RedemptionAction

terugbetaling_data = dict( datum_terugbetaling = datetime.date(2007, 7, 2) )

from camelot.test.action import MockModelContext
from camelot.core.orm import Session
session = Session()

class TerugbetalingCase( TestDocument ):

    @classmethod
    def setUpClass(cls):
        TestDocument.setUpClass()
        cls.period_case = test_period.PeriodiekeVerichtingCase('setUp')
        cls.period_case.setUpClass()

    def setUp(self):
        self.period_case.setUp()
        self.terugbetaling = terugbetaling.Terugbetaling( dossier = self.period_case.dossier_case.dossier, 
                                                          **terugbetaling_data )
        self.model_context = MockModelContext()
        self.model_context.obj = self.terugbetaling
        session.flush()

    def test_terugbetaling(self):
        self.terugbetaling.button_maak_voorstel()
        self.terugbetaling.gerechtskosten = 100
        self.terugbetaling.button_process()
        self.assertTrue(self.terugbetaling.venice_doc)
        self.assertTrue(self.terugbetaling.venice_book)
        self.assertTrue(self.terugbetaling.datum)
        self.assertEqual( self.terugbetaling.dossier.state, 'ended' )
        self.assertEqual( self.terugbetaling.state, 'processed' )
        #import sys
        # if 'win' in sys.platform:
        #   report = tiny_report('hypo.terugbetaling_document', [self.terugbetaling.id])
        #   self.assertEqual(report['format'], 'doc')
        action = terugbetaling.OverzichtWederbeleggingsvergoeding()
        list( action.model_run( self.model_context ) )
        self.terugbetaling.button_undo_process()
        self.assertFalse(self.terugbetaling.venice_doc)
        self.assertFalse(self.terugbetaling.venice_book)
        self.assertEqual(self.terugbetaling.state, 'pending')
        self.assertEqual(self.terugbetaling.dossier.state, 'running')
        self.terugbetaling.button_canceled()
    
    def test_redemption_document(self):
        action = RedemptionAction()
        for step in action.model_run( self.model_context ):
            self.assertTrue(u'Ms. Celie Dehaen, M. Alain François' in step.html)
            self.assertTrue(u'Correspondentielaan 33' in step.html)
            self.assertTrue(u'Correspondentegem' in step.html)

    def tearDown(self):
        self.period_case.tearDown()
