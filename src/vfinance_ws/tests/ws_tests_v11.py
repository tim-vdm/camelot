import unittest

from flask import json
from flask import url_for

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

# @unittest.skip("Skip")
class Ws2TestCase(unittest.TestCase):
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

    @unittest.skip("No Authentication")
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

    @unittest.skip("No Authentication")
    def test_002_calculate_proposal_bad_content(self):
        response = self.post_json(
            'calculate_proposal',
            data="This is a bad content"
        )
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)
        self.assertEqual(content['message'], "Invalid JSON message")

    @unittest.skip("No Authentication")
    def test_010_calculate_proposal(self):
        document = load_demo_json('calculate_proposal')
        response = self.post_json('calculate_proposal', data=document)
        # from nose.tools import set_trace
        # set_trace()
        self.assertEqual(response.status_code, 200)

    @unittest.skip("No Authentication")
    def test_011_calculate_proposal_two_products(self):
        document = load_demo_json('calculate_proposal')
        document['premium_schedule__2__product_id'] = 68
        document['premium_schedule__2__coverage_level_type'] = 'decreasing_amount'
        response = self.post_json('calculate_proposal', data=document)
        self.assertEqual(response.status_code, 200)

    @unittest.skip("No Authentication")
    def test_012_calculate_proposal_missing_fields(self):
        response = self.post_json('calculate_proposal', data={})

        message = json.loads(response.data)

        self.assertIn('package_id', message)
        self.assertEqual(message['package_id']['message'], 'Required')

        self.assertEqual(response.status_code, 400)

    @unittest.skip("No Authentication")
    def test_013_calculate_proposal_bad_values(self):
        document = load_demo_json('calculate_proposal')
        document['agreement_date']['month'] = 2
        document['agreement_date']['day'] = 29

        response = self.post_json('calculate_proposal', data=document)

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)
        self.assertIn('agreement_date/day', content)

    @unittest.skip("No Authentication")
    def test_020_create_agreement_code(self):
        document = load_demo_json('create_agreement_code')
        response = self.post_json('create_agreement_code', data=document)
        self.assertEqual(response.status_code, 200)

    @unittest.skip("No Authentication")
    def test_021_create_agreement_code_wrong_values(self):
        document = load_demo_json('create_agreement_code')
        document.update({
            'insured_party__1__nationality_code': 'qwertyuio'
        })
        response = self.post_json('create_agreement_code', data=document)
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)

        self.assertIn('insured_party__1__nationality_code', content)

    @unittest.skip("No Authentication")
    def test_070_get_proposal_pdf(self):
        response = self.post_json('get_proposal_pdf')
        self.assertEqual(response.status_code, 501)

    @unittest.skip("No Authentication")
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

    @unittest.skip("No Authentication")
    def test_090_get_packages(self):
        document = load_demo_json('get_packages')
        response = self.post_json('get_packages', data=document)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)
        self.assertIn('packages', content)

    def test_create_agreement(self):
        document = load_demo_json('create_agreement_code')
        response = self.post_json('create_agreement_code', data=document)

        self.assertEqual(response.status_code, 200)
        content = = json.loads(response.data)
        self.assertIsInstance(content, dict)

if __name__ == '__main__':
    unittest.main(verbosity=2)
