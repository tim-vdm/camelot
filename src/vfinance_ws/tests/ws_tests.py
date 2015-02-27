import unittest

from flask import json
from flask import url_for

from ws_server import create_app

try:
    from nose.tools import set_trace
except ImportError:
    set_trace = lambda: None

class WsTestCase(unittest.TestCase):
    def setUp(self):
        app = create_app()
        self.app = app
        self.client = self.app.test_client()

    def post_json(self, endpoint, headers=None, data=None):
        with self.app.test_request_context():
            url = url_for('api_v01.%s' % endpoint)

        h = {'content-type': 'application/json'}

        if headers is None:
            headers = {}

        headers.update(h)

        if isinstance(data, dict):
            data = json.dumps(data)
        return self.client.post(url, headers=headers, data=data)

    def create_calculate_proposal_document(self, **kwargs):
        document = {
            "agent_official_number_fsma": "Agent Official Number FSMA",
            "agreement_date": {
                "month": 3,
                "year": 2015,
                "day": 2
            },
            "duration": 10,
            "from_date": {
                "month": 3,
                "year": 2015,
                "day": 1
            },
            "insured_party__1__birthdate": {
                "month": 9,
                "year": 1980,
                "day": 15
            },
            "insured_party__1__sex": "M",
            "package_id": 64,
            "premium_schedule__1__premium_fee_1": "2.00",
            "premium_schedule__1__product_id": 67,
            "premium_schedule__2__product_id": None,
            "premium_schedule__1__coverage_level_type": "fixed_amount",
            "premium_schedule__2__coverage_level_type": None,
            "premium_schedules_coverage_limit": "5000",
            "premium_schedules_payment_duration": 10,
            "premium_schedules_period_type": "single",
            "premium_schedules_premium_rate_1": "20"
        }
        document.update(**kwargs)
        return document

    def create_agreement_code_document(self, **kwargs):
        return self.create_calculate_proposal_document(origin='BIA:10', **kwargs)


    # @unittest.skip("")
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

    # @unittest.skip("")
    def test_002_calculate_proposal_bad_content(self):
        response = self.post_json(
            'calculate_proposal',
            data="This is a bad content"
        )
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)
        self.assertEqual(content['message'], "Invalid JSON message")

    # @unittest.skip("")
    def test_010_calculate_proposal(self):
        document = self.create_calculate_proposal_document()
        response = self.post_json('calculate_proposal', data=document)
        self.assertEqual(response.status_code, 200)

    def test_010_calculate_proposal_two_products(self):
        document = self.create_calculate_proposal_document()
        document['premium_schedule__2__product_id'] = 68
        document['premium_schedule__2__coverage_level_type'] = 'decreasing_amount'
        response = self.post_json('calculate_proposal', data=document)
        self.assertEqual(response.status_code, 200)

    # @unittest.skip("")
    def test_011_calculate_proposal_missing_fields(self):
        DOCUMENT = {}
        response = self.post_json('calculate_proposal', data=DOCUMENT)

        message = json.loads(response.data)

        self.assertIn('package_id', message)
        self.assertEqual(message['package_id']['message'], 'Required')

        self.assertEqual(response.status_code, 400)

    # @unittest.skip("")
    def test_012_calculate_proposal_bad_values(self):
        document = self.create_calculate_proposal_document()
        document['agreement_date']['month'] = 2
        document['agreement_date']['day'] = 29

        response = self.post_json('calculate_proposal', data=document)

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)
        self.assertIn('agreement_date/day', content)

    # @unittest.skip("")
    def test_020_create_agreement_code(self):
        document = self.create_agreement_code_document()

        response = self.post_json('create_agreement_code', data=document)
        print response.data
        self.assertEqual(response.status_code, 200)

    # @unittest.skip("")
    def test_021_create_agreement_code_wrong_values(self):
        document = self.create_agreement_code_document()
        document.update({
            'insured_party__1__nationality_code': 'qwertyuio'
        })
        response = self.post_json('create_agreement_code', data=document)
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)

        self.assertIn('insured_party__1__nationality_code', content)

    # @unittest.skip("")
    def test_030_create_proposal(self):
        response = self.post_json('create_proposal')
        self.assertEqual(response.status_code, 501)

    # @unittest.skip("")
    def test_040_modify_proposal(self):
        response = self.post_json('modify_proposal')
        self.assertEqual(response.status_code, 501)

    # @unittest.skip("")
    def test_050_cancel_proposal(self):
        response = self.post_json('cancel_proposal')
        self.assertEqual(response.status_code, 501)

    # @unittest.skip("")
    def test_060_proposal_to_managed(self):
        response = self.post_json('proposal_to_managed')
        self.assertEqual(response.status_code, 501)

    # @unittest.skip("")
    def test_070_get_proposal_pdf(self):
        response = self.post_json('get_proposal_pdf')
        self.assertEqual(response.status_code, 501)

if __name__ == '__main__':
    unittest.main(verbosity=2)
