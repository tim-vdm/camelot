import unittest
from flask import json
from ws_server import create_app

class WsTestCase(unittest.TestCase):
    def setUp(self):
        app = create_app()
        self.app = app.test_client()

    # @unittest.skip('refactoring')
    def test_001_calculate_proposal_bad_content_type(self):
        response = self.app.post('/api/v0.1/calculate_proposal')
        self.assertEqual(response.status_code, 400)

        content = json.loads(response.data)
        self.assertEqual(content['message'], 'Content-Type is not setted')

        response = self.app.post(
            '/api/v0.1/calculate_proposal', 
            headers={'content-type': 'application/xml'}
        )
        self.assertEqual(response.status_code, 400)

        content = json.loads(response.data)
        self.assertEqual(content['message'], "Content-Type is not 'application/json'")

    def test_002_calculate_proposal_bad_content(self):
        response = self.app.post('/api/v0.1/calculate_proposal',
            headers={'content-type': 'application/json'},
            data="This is a bad content"
        )
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)
        self.assertEqual(content['message'], "Invalid JSON message")

    def test_010_calculate_proposal(self):
        response = self.app.post('/api/v0.1/calculate_proposal',
            headers={'content-type': 'application/json'},
            data=json.dumps({})
        )
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        print "content: %r" % (content,)
        self.assertEqual(content['amount'], "1.0")

    def test_020_create_agreement_code(self):
        response = self.app.post('/api/v0.1/create_agreement_code', headers={'content-type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertEqual(content['code'], '000/0000/00000')

if __name__ == '__main__':
    unittest.main(verbosity=2)