import unittest

from flask import json
from flask import url_for

from ws_server import create_app


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

    # @unittest.skip('refactoring')
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
        DOCUMENT = {
            "agent_official_number_fsma": "128Char",
            "agreement_date": {"month": 3, "year": 2015, "day": 2},
            "duration": 10,
            "from_date": {"month": 3, "year": 2015, "day": 1},
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
            "premium_schedules_coverage_level_type": "fixed_amount",
            "premium_schedules_coverage_limit": "5000",
            "premium_schedules_payment_duration": 10,
            "premium_schedules_period_type": "single",
            "premium_schedules_premium_rate_1": "20"
        }

        response = self.post_json('calculate_proposal', data=DOCUMENT)

        self.assertEqual(response.status_code, 200)
        # content = json.loads(response.data)
        # self.assertEqual(content['premium_schedule__1__amount'], "1.0")
        # self.assertEqual(content['premium_schedule__2__amount'], None)

    def test_011_calculate_proposal_missing_fields(self):
        DOCUMENT = {}

        response = self.post_json('calculate_proposal', data=DOCUMENT)

        message = json.loads(response.data)

        self.assertIn('package_id', message)
        self.assertEqual(message['package_id']['message'], 'Required')

        self.assertEqual(response.status_code, 400)

    @unittest.skip("bouh")
    def test_012_calculate_proposal_bad_values(self):
        DOCUMENT = {
            "agent_official_number_fsma": "128Char",
            "agreement_date": {"month": 3, "year": 2015, "day": 29},
            "duration": 10,
            "from_date": {"month": 3, "year": 2015, "day": 1},
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
            "premium_schedules_coverage_level_type": "fixed_amount",
            "premium_schedules_coverage_limit": "5000",
            "premium_schedules_payment_duration": 10,
            "premium_schedules_period_type": "single",
            "premium_schedules_premium_rate_1": "20"
        }

        response = self.post_json('calculate_proposal', data=DOCUMENT)

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)
        self.assertIn('agreement_date/day', content)

    def test_020_create_agreement_code(self):
        DOCUMENT = {
            "agent_official_number_fsma": "128Char",
            "agreement_date": {"month": 3, "year": 2015, "day": 29},
            "duration": 10,
            "from_date": {"month": 3, "year": 2015, "day": 1},
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
            "premium_schedules_coverage_level_type": "fixed_amount",
            "premium_schedules_coverage_limit": "5000",
            "premium_schedules_payment_duration": 10,
            "premium_schedules_period_type": "single",
            "premium_schedules_premium_rate_1": "20",
            "origin": "BIA:10",
        }

        response = self.post_json('create_agreement_code', data=DOCUMENT)
        self.assertEqual(response.status_code, 200)

        content = json.loads(response.data)

        self.assertEqual(content['code'], '000/0000/00000')

    def test_021_create_agreement_code_wrong_values(self):
        DOCUMENT = {
            "agent_official_number_fsma": "128Char",
            "agreement_date": {"month": 3, "year": 2015, "day": 29},
            "duration": 10,
            "from_date": {"month": 3, "year": 2015, "day": 1},
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
            "premium_schedules_coverage_level_type": "fixed_amount",
            "premium_schedules_coverage_limit": "5000",
            "premium_schedules_payment_duration": 10,
            "premium_schedules_period_type": "single",
            "premium_schedules_premium_rate_1": "20",
            "origin": "BIA:10",
            "insured_party__1__nationality_code": "qwertyuio",
        }
        response = self.post_json('create_agreement_code', data=DOCUMENT)
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)

        self.assertIn('insured_party__1__nationality_code', content)

    def test_030_create_proposal(self):
        response = self.post_json('create_proposal')
        self.assertEqual(response.status_code, 501)

    def test_040_modify_proposal(self):
        response = self.post_json('modify_proposal')
        self.assertEqual(response.status_code, 501)

    def test_050_cancel_proposal(self):
        response = self.post_json('cancel_proposal')
        self.assertEqual(response.status_code, 501)

    def test_060_proposal_to_managed(self):
        response = self.post_json('proposal_to_managed')
        self.assertEqual(response.status_code, 501)

    def test_070_get_proposal_pdf(self):
        response = self.post_json('get_proposal_pdf')
        self.assertEqual(response.status_code, 501)

if __name__ == '__main__':
    unittest.main(verbosity=2)
