import unittest

from camelot.core.orm import Session
from camelot.test.action import MockModelContext

from vfinance.model.bank import statusmixin
from ...import app_admin

class StatusCase(unittest.TestCase):
    
    def setUp(self):
        from vfinance.test.test_branch_21 import Branch21Case
        self.branch_21_case = Branch21Case('setUp')
        self.branch_21_case.setUp()
        self.session = Session()
        
    def test_force_status(self):
        agreement = self.branch_21_case.create_agreement()
        model_context = MockModelContext()
        model_context.obj = agreement
        model_context.admin = app_admin.get_related_admin(agreement.__class__)
        force_status = statusmixin.ForceStatus()
        generator = force_status.model_run(model_context)
        for i, step in enumerate(generator):
            if i == 0:
                generator.send('verified')
        self.assertEqual(agreement.current_status, 'verified')