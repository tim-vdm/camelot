import datetime

import test_period

from ... import test_case
from vfinance.model.hypo import wijziging

wijziging_data = dict( datum_wijziging = datetime.date(2007, 6, 2),
                       nieuw_bedrag = 250000 )

from camelot.test.action import MockModelContext

class WijzigingCase(test_case.SessionCase):
  
    def setUp(self):
        super(WijzigingCase, self).setUp()
        self.period_case = test_period.PeriodiekeVerichtingCase('setUp')
        self.period_case.setUp()        
        self.wijziging = wijziging.Wijziging( dossier = self.period_case.dossier_case.dossier, 
                                              **wijziging_data )
        self.model_context = MockModelContext()
        self.model_context.obj = self.wijziging
        self.session.flush()
        
    def test_wijziging(self):
        self.assertEqual( self.wijziging.state, 'draft' )
        self.wijziging.button_maak_voorstel()
        self.wijziging.button_wederbeleggingsvergoeding
        self.wijziging.button_approve()
        self.assertEqual( self.wijziging.state, 'approved' )
        self.wijziging.button_process()
        self.assertEqual( self.wijziging.state, 'processed' )
        self.wijziging.button_remove()
        self.assertEqual( self.wijziging.state, 'draft' )
        self.wijziging.button_cancel()
        self.assertEqual( self.wijziging.state, 'canceled' )
        
    def tearDown(self):
        self.period_case.tearDown()
