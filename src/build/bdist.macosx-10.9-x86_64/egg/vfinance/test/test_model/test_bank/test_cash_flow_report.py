# coding=UTF-8
import logging
import unittest
import shutil

from camelot.view import action_steps

logger = logging.getLogger('vfinance.test.test_bank.test_cash_flow_report')

class CashFlowReportCase( unittest.TestCase ):

    @classmethod
    def setUpClass(cls):
        from ..test_hypo import test_dossier
        unittest.TestCase.setUpClass()
        cls.dossier_case = test_dossier.DossierCase('setUp')
        cls.dossier_case.setUpClass()

    def setUp( self ):
        self.dossier_case.setUp()

    def test_cash_flow_report( self ):
        from vfinance.model.bank.cashflow_report import CashFlowReport
        from camelot.test.action import MockModelContext
        model_context = MockModelContext()
        report = CashFlowReport()
        for step in report.model_run( model_context ):
            if isinstance( step, action_steps.OpenString ):
                shutil.copy( step.path, 'cash-flow.xlsx' )
        
    def tearDown( self ):
        self.dossier_case.tearDown()
        