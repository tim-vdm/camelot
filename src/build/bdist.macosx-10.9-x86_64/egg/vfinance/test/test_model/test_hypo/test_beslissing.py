# coding=utf-8
import os
from decimal import Decimal as D

from camelot.test.action import MockModelContext

from . import test_hypotheek
from .test_product import variabiliteit_historiek_data
from ..test_bank.test_index import index_feb_2007

from vfinance.model.hypo.summary.decision_document import DecisionDocument
from vfinance.admin.jinja2_filters import date as format_date
from vfinance.model.financial.notification.utils import generate_qr_code
from vfinance.test import test_documents

from ... import test_case


class BeslissingCase(test_documents.TestDocument, test_case.SessionCase):

    @classmethod
    def setUpClass(cls):
        test_case.SessionCase.setUpClass()
        cls.request_case = test_hypotheek.AanvraagformulierCase('setUp')
        cls.request_case.setUpClass()

    def setUp(self):
        test_documents.TestDocument.setUp(self)
        test_case.SessionCase.setUp(self)
        self.request_case.setUp()
        self.hypotheek = self.request_case.hypotheek
        self.test_person_1 = self.request_case.test_person_1
        self.variability_case = self.request_case.variability_case
        self.beslissing = self.request_case.test_complete()
        self.model_context = MockModelContext()
        self.model_context.obj = self.beslissing
        
    def testBeslissingTeNemen(self):
        self.assertEqual(self.beslissing.state, 'te_nemen')
        self.assertEqual(self.beslissing.borrower_1_name, self.test_person_1.name)
        
    def testBeslissingMaakVoorstel(self):
        self.beslissing.button_maak_voorstel()
        goedgekeurd_bedrag = list(self.beslissing.goedgekeurd_bedrag)[0]
        self.assertEqual(goedgekeurd_bedrag.bedrag.type_vervaldag, 'akte')
        self.assertEqual(goedgekeurd_bedrag.type, 'nieuw')
        for k,v in variabiliteit_historiek_data.items():
            setattr(goedgekeurd_bedrag, 'voorgestelde_%s'%k, v)
        self.session.flush()
        #self.assertEqual(goedgekeurd_bedrag.voorgesteld_index_type.id, self.variability_case.index_case.index_type.id)
        #self.assertEqual(goedgekeurd_bedrag.voorgestelde_eerste_herziening, self.variability_case.product.eerste_herziening)
        #self.assertEqual(goedgekeurd_bedrag.voorgestelde_volgende_herzieningen, self.variability_case.product.volgende_herzieningen)
        #self.assertEqual(D(goedgekeurd_bedrag.voorgestelde_referentie_index), D(index_feb_2007))
        #self.assertEqual(goedgekeurd_bedrag.voorgestelde_minimale_afwijking, variabiliteit_historiek_data['minimale_afwijking'])
        self.assertEqual(self.beslissing.nodige_schuldsaldo[0].dekkingsgraad_schuldsaldo, 70)
        self.assertEqual(self.beslissing.nodige_schuldsaldo[0].schuldsaldo_voorzien, True)
        
    def testBeslissingApprove(self):
        self.testBeslissingMaakVoorstel()
        goedgekeurd_bedrag = list(self.beslissing.goedgekeurd_bedrag)[0]
        self.beslissing.button_approved()
        self.assertEqual(goedgekeurd_bedrag.state, 'approved')
        self.assertEqual(goedgekeurd_bedrag.goedgekeurd_index_type.id, self.variability_case.index_case.index_type.id)
        self.assertEqual(goedgekeurd_bedrag.goedgekeurde_eerste_herziening, 3*12)
        self.assertEqual(D(goedgekeurd_bedrag.goedgekeurde_referentie_index), D(index_feb_2007) )
        self.assertEqual(goedgekeurd_bedrag.goedgekeurde_minimale_afwijking, variabiliteit_historiek_data['minimale_afwijking'])
        self.assertEqual(goedgekeurd_bedrag.goedgekeurd_type_vervaldag, 'akte')
        self.assertEqual(goedgekeurd_bedrag.goedgekeurde_intrest_a, '0.0417' )
        self.session.expire_all()
        self.assertEqual(goedgekeurd_bedrag.bedrag.goedgekeurd_bedrag, goedgekeurd_bedrag.goedgekeurd_bedrag)
        self.assertEqual(goedgekeurd_bedrag.bedrag.beslissing_state, 'approved')
        return goedgekeurd_bedrag
    
    def testBeslissingIncomplete(self):
        self.beslissing.button_incomplete()
        self.assertEqual( self.hypotheek.state, 'incomplete' )
        
    def testBeslissingDisapproved(self):
        self.beslissing.button_disapproved()
        self.assertEqual( self.hypotheek.state, 'disapproved' )
        
    def testUndoBeslissing(self):
        self.beslissing.button_maak_voorstel()
        goedgekeurd_bedrag = list(self.beslissing.goedgekeurd_bedrag)[0]
        self.beslissing.button_approved()
        self.assertEqual(goedgekeurd_bedrag.state, 'approved')
        self.beslissing.button_undo_beslissing()
        self.assertEqual(goedgekeurd_bedrag.state, 'draft')
        self.assertEqual(self.beslissing.state, 'te_nemen')

    def test_decision_document(self):

        self.testBeslissingApprove()

        def _string_replacements():
            replacements = []
            # print format_datetime(self.aanvaarding.beslissing.datum)
            replacements.append((self.beslissing.full_number, '123-01-00111-11'))
            qr_base64 = generate_qr_code(self.beslissing.full_number)
            test_qr_base64 = generate_qr_code('123-01-00111-11')
            replacements.append((format_date(self.beslissing.datum),
                                 format_date(test_documents.REFERENCE_DATETIME)))
            replacements.append((qr_base64, test_qr_base64))
            return replacements

        action = DecisionDocument()
        context = action.context(self.beslissing)
        self._verify_document(os.path.join('hypo',
                                           'decision.html'),
                              context,
                              string_replacements=_string_replacements())

    def _verify_document(self, template, context, string_replacements):
        self.verify_document(template,
                             context,
                             string_replacements=string_replacements)
