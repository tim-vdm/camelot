import unittest
from decimal import Decimal as D

from flask import json
from flask import url_for

from camelot.core.orm import Session

from vfinance.model.financial.agreement import FinancialAgreement

from vfinance_ws.ws_server import create_app

try:
    from nose.tools import set_trace
except ImportError:
    set_trace = lambda: None

import os
DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'demo')
print DEMO_DIR

def load_demo_json(fname):
    with open(os.path.join(DEMO_DIR, "%s.json" % (fname,))) as infile:
        return json.load(infile)

from base64 import b64encode

class WebServiceVersion11TestCase(unittest.TestCase):
    def setUp(self):
        app = create_app()
        self.app = app
        self.client = self.app.test_client()

    def post_json(self, endpoint, headers=None, data=None):
        with self.app.test_request_context():
            url = url_for('api_v11.%s' % endpoint)

        h = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + b64encode("{0}:{1}".format("1234567890", "secret"))
        }

        if headers is None:
            headers = {}

        headers.update(h)

        if isinstance(data, dict):
            data = json.dumps(data)
            
        return self.client.post(url, headers=headers, data=data)

    def test_001_calculate_proposal_bad_content_type(self):
        with self.app.test_request_context():
            url = url_for('api_v01.calculate_proposal')

        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)

        content = json.loads(response.data)
        self.assertEqual(content['message'], 'Content-Type is not setted')

        response = self.client.post(
            url,
            headers={'content-type': 'application/xml'}
        )
        self.assertEqual(response.status_code, 400)

        content = json.loads(response.data)
        self.assertEqual(
            content['message'],
            "Content-Type is not 'application/json'"
        )

    def test_002_calculate_proposal_bad_content(self):
        response = self.post_json(
            'calculate_proposal',
            data="This is a bad content"
        )
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)
        self.assertEqual(content['message'], "Invalid JSON message")

    def test_010_calculate_proposal(self):
        document = load_demo_json('calculate_proposal')
        response = self.post_json('calculate_proposal', data=document)
        self.assertEqual(response.status_code, 200)

    def test_011_calculate_proposal_two_products(self):
        document = load_demo_json('calculate_proposal')
        document['premium_schedule__2__product_id'] = 68
        document['premium_schedule__2__coverage_level_type'] = 'decreasing_amount'
        response = self.post_json('calculate_proposal', data=document)
        self.assertEqual(response.status_code, 200)

    def test_012_calculate_proposal_missing_fields(self):
        response = self.post_json('calculate_proposal', data={})

        message = json.loads(response.data)

        self.assertIn('package_id', message)
        self.assertEqual(message['package_id']['message'], 'required key not provided')

        self.assertEqual(response.status_code, 400)

    def test_013_calculate_proposal_bad_values(self):
        document = load_demo_json('calculate_proposal')
        document['agreement_date']['month'] = 2
        document['agreement_date']['day'] = 29

        response = self.post_json('calculate_proposal', data=document)

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)
        self.assertIn('agreement_date/day', content)

    def test_014_calculate_various_proposals_select_plus(self):
        document = load_demo_json('calculate_proposal_select_plus')
        self.calculate_proposal_check_amount(document, '1727.37')
        # Laagste studieniveau -> 2129,91
        document['insured_party__1__educational_level'] = 'no_schooling'
        self.calculate_proposal_check_amount(document, '2129.91')
        # Laagste inkomen -> 2552,31
        document['insured_party__1__net_earnings_of_employment'] = '300.0'
        self.calculate_proposal_check_amount(document, '2552.31')
        # Roker -> 3591,15
        document['insured_party__1__smoking_habit'] = 'regular'
        self.calculate_proposal_check_amount(document, '3591.15')
        # Niet sporter -> 3864,78
        document['insured_party__1__fitness_level'] = 'sedentary'
        self.calculate_proposal_check_amount(document, '3864.78')
        # Looptijd 120 maanden -> 1637,62
        document['duration'] = 120
        self.calculate_proposal_check_amount(document, '1637.62')
        # Betaling jaarlijks -> 429.99 
        document['duration'] = 240
        document['premium_schedules_period_type'] = 'yearly'
        self.calculate_proposal_check_amount(document, '429.99')
        # Type betaling bullet -> 761,50
        document['loan_type_of_payments'] = 'bullet'
        self.calculate_proposal_check_amount(document, '761.50')

    def calculate_proposal_check_amount(self, document, schedule__1__amount=None, schedule__2__amount=None):
        response = self.post_json('calculate_proposal', data=document)
        content = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(content.get('premium_schedule__1__amount'), schedule__1__amount)
        self.assertEqual(content.get('premium_schedule__2__amount'), schedule__2__amount)

    def test_020_create_agreement_code(self):
        document = load_demo_json('create_minimalist_agreement_code')
        response = self.post_json('create_agreement_code', data=document)
        self.assertEqual(response.status_code, 200)

    def test_021_create_agreement_code_wrong_values(self):
        document = load_demo_json('create_agreement_code')
        document.update({
            'insured_party__1__nationality_code': 'qwertyuio'
        })
        response = self.post_json('create_agreement_code', data=document)
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)

        self.assertIn('insured_party__1__nationality_code', content)

    def test_070_get_proposal_pdf(self):
        response = self.post_json('get_proposal_pdf')
        self.assertEqual(response.status_code, 501)

    def test_080_send_agreement(self):
        # from camelot.core.conf import settings
        # class TestSettings(object):
        #     MOCK = True
        # settings.append(TestSettings())

        document = load_demo_json('send_agreement')
        response = self.post_json('send_agreement', data=document)

        # set_trace()
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertEqual(len(content), 0)

    def test_090_get_packages(self):
        document = load_demo_json('get_packages')
        response = self.post_json('get_packages', data=document)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)
        self.assertIn('packages', content)

    def test_create_agreement(self):
        document = load_demo_json('create_agreement_code_2')
        response = self.post_json('create_agreement_code', data=document)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)
        agreement_code = content.get('code')
        session = Session
        agreement = session.query(FinancialAgreement).filter(FinancialAgreement.code == agreement_code).first()
        self.assertEqual(agreement.code, agreement_code)
        features = []
        for role in agreement.roles:
            for feature in role.features:
                self.assertTrue(feature.described_by not in features)
                if feature.described_by == 'net_earnings_of_employment':
                    self.assertEqual(feature.value, D('1400.00'))
                features.append(feature.described_by)




    def test_create_agreement_code_polapp(self):
        document = load_demo_json('polapp_agreement_code_v11')
        response = self.post_json('create_agreement_code', data=document)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)

if __name__ == '__main__':
    unittest.main(verbosity=2)
