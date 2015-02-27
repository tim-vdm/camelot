# encoding: utf-8
import os

import test_beslissing, test_product

from camelot.test.action import MockModelContext

from vfinance.model.hypo.notification.aanvaardingsbrief import AanvaardingsBrief
from vfinance.model.hypo.notification.mortgage_table import MortgageTable
from vfinance.test.test_documents import TestDocument, REFERENCE_DATETIME
from vfinance.admin.jinja2_filters import date as format_date


class AanvaardingCase(TestDocument):

    @classmethod
    def setUpClass(cls):
        TestDocument.setUpClass()
        cls.beslissing_case = test_beslissing.BeslissingCase('setUp')
        cls.beslissing_case.setUpClass()

    def setUp(self):
        super(AanvaardingCase, self).setUp()
        self.beslissing_case.setUp()
        self.beslissing = self.beslissing_case.beslissing
        self.beslissing.button_maak_voorstel()
        for goedgekeurd_bedrag in self.beslissing.goedgekeurd_bedrag:
            for k,v in test_product.variabiliteit_historiek_data.items():
                setattr(goedgekeurd_bedrag, 'voorgestelde_%s'%k, v)
        self.beslissing.button_approved()
        self.session = self.beslissing_case.session
        self.aanvaarding = list(self.beslissing.aanvaarding)[-1]
        self.model_context = MockModelContext()
        self.model_context.obj = self.aanvaarding

    def test_aanvaarding_verstuurd_en_ontvangen(self):
        self.assertEqual(self.aanvaarding.state, 'to_send')
        self.aanvaarding.button_send()
        self.assertEqual(self.aanvaarding.state, 'send')
        self.aanvaarding.button_received()
        self.assertEqual(self.aanvaarding.state, 'received')
        self.session.expire_all()
        for bedrag in self.beslissing.hypotheek.gevraagd_bedrag:
            self.assertEqual(bedrag.aanvaarding_state, 'received')

    def test_aanvaardingsbrief(self):
        action = AanvaardingsBrief()
        list(action.model_run(self.model_context))

    def test_aanvaardingsbrief_default(self):

        def _string_replacements():
            replacements = []
            # print format_datetime(self.aanvaarding.beslissing.datum)
            replacements.append((self.aanvaarding.full_number, '123-01-00111-11'))
            replacements.append((format_date(self.aanvaarding.beslissing.datum),
                                 format_date(REFERENCE_DATETIME)))
            return replacements

        action = AanvaardingsBrief()
        context = action.context_from_aanvaarding(self.aanvaarding)
        self._verify_document(os.path.join('hypo',
                                           'acceptance_letter_nl_BE.html'),
                              context,
                              string_replacements=_string_replacements())

    def test_mortgage_table(self):
        action = MortgageTable()
        list(action.model_run(self.model_context))

    def _verify_document(self, template, context, string_replacements):
        self.verify_document(template,
                             context,
                             string_replacements=string_replacements)
