import unittest
import datetime
from decimal import Decimal as D

from flask import json
from flask import url_for

from camelot.core.orm import Session

from vfinance.model.financial.agreement import FinancialAgreement
from vfinance.model.financial.package import FinancialPackage
from vfinance.model.hypo.hypotheek import Hypotheek
from vfinance.connector.json_ import  JsonImportAction

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

def set_new_agreement_code(session, json_path):
    json_structure = json.load(open(json_path))
    package = session.query(FinancialPackage).get(long(json_structure['package_id']))
    new_agreement_code = FinancialAgreement.next_agreement_code(package, session)
    json_structure['code'] = new_agreement_code
    json.dump(json_structure, open(json_path, 'w'), indent=3)

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
            'Authorization': 'Basic ' + b64encode("{0}:{1}".format("04f3debc-85b4-4fb3-9de1-88642557764b", "secret"))
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
        document = load_demo_json('v11_calculate_proposal_stc')
        response = self.post_json('calculate_proposal', data=document)
        self.assertEqual(response.status_code, 200)


    def test_011_calculate_proposal_two_products(self):
        document = load_demo_json('v11_calculate_proposal_stc')
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
        document = load_demo_json('v11_calculate_proposal_stc')
        document['agreement_date']['month'] = 2
        document['agreement_date']['day'] = 29

        response = self.post_json('calculate_proposal', data=document)

        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)
        self.assertIn('agreement_date/day', content)

    def test_014_calculate_various_proposals_select_plus(self):
        document = load_demo_json('v11_calculate_proposal_select_plus')
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

    def test_get_proposal_select_plus(self):
        document = load_demo_json('v11_get_proposal_select_plus')
        response = self.post_json('get_proposal', data=document)
        self.assertEqual(response.status_code, 200)
        self.assertIn('1.727,37', response.data)

    def test_calculate_proposal_hypo_secure_affinity(self):
        document = load_demo_json('v11_calculate_proposal_hypo_secure_affinity')
        self.calculate_proposal_check_amount(document, '298.79')

    def test_get_proposal_hypo_secure_affinity(self):
        document = load_demo_json('v11_get_proposal_hypo_secure_affinity')
        response = self.post_json('get_proposal', data=document)
        self.assertEqual(response.status_code, 200)


    def test_calculate_proposal_hypo_secure_family(self):
        document = load_demo_json('v11_calculate_proposal_hypo_secure_family')
        self.calculate_proposal_check_amount(document, '342.51')

    def test_get_proposal_hypo_secure_family(self):
        document = load_demo_json('v11_get_proposal_hypo_secure_family')
        response = self.post_json('get_proposal', data=document)
        self.assertEqual(response.status_code, 200)



    def test_020_create_agreement_code(self):
        document = load_demo_json('v11_create_minimalist_agreement_code')
        response = self.post_json('create_agreement_code', data=document)
        self.assertEqual(response.status_code, 200)

    def test_021_create_agreement_code_wrong_values(self):
        document = load_demo_json('v11_create_agreement_code')
        document.update({
            'insured_party__1__nationality_code': 'qwertyuio'
        })
        response = self.post_json('create_agreement_code', data=document)
        self.assertEqual(response.status_code, 400)
        content = json.loads(response.data)

        self.assertIn('insured_party__1__nationality_code', content)

    #def test_070_get_proposal_pdf(self):
    #    document = load_demo_json('v11_get_proposal_pdf')
    #    response = self.post_json('get_proposal_pdf', data=document)
    #    self.assertEqual(response.status_code, 200)

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
        document = load_demo_json('v11_create_agreement_code')
        response = self.post_json('create_agreement_code', data=document)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)
        agreement_code = content.get('code')
        session = Session
        agreement = session.query(FinancialAgreement).filter(FinancialAgreement.code == agreement_code).first()
        self.assertEqual(agreement.code, agreement_code)
        for role in agreement.roles:
            for feature in role.features:
                features = []
                self.assertTrue(feature.described_by not in features)
                if feature.described_by == 'net_earnings_of_employment':
                    if role.described_by == 'borrower':
                        self.assertEqual(feature.value, D('1400.00'))
                    if role.described_by == 'owner':
                        self.assertEqual(feature.value, D('1500.00'))
                features.append(feature.described_by)


    def test_create_agreement_code_wrong_coverage_level(self):
        document = load_demo_json('v11_create_agreement_code_select_plus')
        document['schedules'][0]['coverage_for'] = 'wrong_coverage'
        response = self.post_json('create_agreement_code', data=document)

        content = json.loads(response.data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(content.get('message'), 'Coverage of type wrong_coverage is not available')

    def test_create_agreement_code_loansmanager(self):
        document = load_demo_json('v11_create_agreement_code_loansmanager')
        response = self.post_json('create_agreement_code', data=document)
        session = Session

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)

        json_path = content.get('json_path')
        set_new_agreement_code(session, json_path)
        import_action = JsonImportAction()
        imported_agreement = list(import_action.import_file(session,
                                                            FinancialAgreement,
                                                            json_path))[0]

        self.assertIsNotNone(imported_agreement)


    def test_create_agreement_code_polapp(self):
        document = load_demo_json('v11_polapp_agreement_code')
        response = self.post_json('create_agreement_code', data=document)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)

    def test_create_agreement_code_stc(self):
        document = load_demo_json('v11_create_agreement_code_stc')
        response = self.post_json('create_agreement_code', data=document)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)


    def test_create_agreement_code_polapp_stc(self):
        document = load_demo_json('v11_create_agreement_code_polapp_stc')
        response = self.post_json('create_agreement_code', data=document)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)


    def test_create_agreement_code_polapp_select_plus(self):
        document = load_demo_json('v11_create_agreement_code_polapp_select_plus')
        response = self.post_json('create_agreement_code', data=document)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)


    def test_create_agreement_code_duplicate_roles(self):
        # This test should be adapted when we know about the agreement where
        # the income of both roles was the same.
        document = load_demo_json('v11_create_agreement_code_duplicate_roles')
        response = self.post_json('create_agreement_code', data=document)
        session = Session

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)
        json_path = content.get('json_path')
        set_new_agreement_code(session, json_path)
        import_action = JsonImportAction()
        imported_agreement = list(import_action.import_file(session,
                                                            FinancialAgreement,
                                                            json_path))[0]
        self.assertIsNotNone(imported_agreement)
        self.assertEqual(imported_agreement.origin, 'BIA:12000')
        roles = {'{r.described_by}_{r.rank}'.format(r=role): role for role in imported_agreement.roles}
        insured_party = roles.get('insured_party_1')
        self.assertEqual(insured_party.smoking_habit, 1)
        self.assertEqual(insured_party.natuurlijke_persoon.sex, 'M')
        self.assertEqual(insured_party.natuurlijke_persoon.last_name, 'aezr')
        self.assertEqual(insured_party.natuurlijke_persoon.first_name, 'azer')
        self.assertEqual(insured_party.natuurlijke_persoon.identity_number, '900101')
        self.assertEqual(insured_party.net_earnings_of_employment, D('1234.56'))
        insured_party_2 = roles.get('insured_party_2')
        self.assertEqual(insured_party_2.net_earnings_of_employment, None)
        self.assertEqual(insured_party_2.smoking_habit, 2)
        premium_schedule = imported_agreement.invested_amounts[0]
        self.assertEqual(premium_schedule.amount, D('230000.00'))
        self.assertEqual(premium_schedule.insured_duration, 240)
        agreed_features = {agreed_feature.described_by: agreed_feature.value for agreed_feature in premium_schedule.agreed_features}
        self.assertEqual(100, agreed_features.get('premium_fee_1'))
        self.assertEqual(20, agreed_features.get('premium_rate_1'))
        self.assertEqual(100, agreed_features.get('coverage_limit'))
        self.assertEqual(3, agreed_features.get('premium_taxation_physical_person'))

    def test_create_agreement_code_select_plus(self):
        document = load_demo_json('v11_create_agreement_code_select_plus')
        response = self.post_json('create_agreement_code', data=document)
        session = Session

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data)
        self.assertIsInstance(content, dict)
        json_path = content.get('json_path')
        set_new_agreement_code(session, json_path)
        import_action = JsonImportAction()
        imported_agreement = list(import_action.import_file(session,
                                                            FinancialAgreement,
                                                            json_path))[0]
        self.assertIsNotNone(imported_agreement)
        self.assertEqual(imported_agreement.origin, 'BIA:12000')
        roles = {role.described_by: role for role in imported_agreement.roles}
        insured_party = roles.get('insured_party')
        direct_debit_mandate_be = imported_agreement.direct_debit_mandates[0]
        direct_debit_mandate_nl = imported_agreement.direct_debit_mandates[1]
        self.assertEqual(insured_party.smoking_habit, 1)
        self.assertEqual(insured_party.natuurlijke_persoon.sex, 'M')
        self.assertEqual(insured_party.natuurlijke_persoon.last_name, 'Delaruelle')
        self.assertEqual(insured_party.natuurlijke_persoon.first_name, 'Pieter-Jan')
        self.assertEqual(insured_party.natuurlijke_persoon.identity_number, '900102')
        self.assertEqual(insured_party.natuurlijke_persoon.place_of_birth.name, 'Wilrijk')
        self.assertEqual(insured_party.natuurlijke_persoon.place_of_birth.country.code, 'BE')
        self.assertEqual(insured_party.natuurlijke_persoon.origin, 'BIA:12000')
        self.assertEqual(insured_party.fitness_level, D('1'))
        self.assertEqual(insured_party.fitness_level_reference, 'Judo, Ippon v.z.w. Diest')
        self.assertEqual(insured_party.height, D('188.0'))
        self.assertEqual(insured_party.weight, D('90.0'))
        self.assertEqual(insured_party.dangerous_hobby, D('3'))
        self.assertEqual(insured_party.dangerous_profession, D('4'))
        self.assertEqual(insured_party.medical_condition, D('2'))
        self.assertEqual(insured_party.medical_procedure, D('2'))
        self.assertEqual(insured_party.medical_test_deviation, D('1'))
        self.assertEqual(insured_party.currently_disabled, D('2'))
        self.assertEqual(insured_party.natuurlijke_persoon.passport_expiry_date, datetime.date(2020, 1, 1))
        self.assertEqual(insured_party.date_previous_disability, datetime.date(year=1995,
                                                                               month=4,
                                                                               day=7))
        self.assertEqual(insured_party.date_previous_medical_procedure, datetime.date(year=1995,
                                                                                      month=2,
                                                                                      day=6))
        subscriber = roles.get('subscriber')
        self.assertEqual(subscriber.natuurlijke_persoon.sex, 'M')
        premium_schedule = imported_agreement.invested_amounts[0]
        self.assertEqual(premium_schedule.amount, D('230000.00'))
        self.assertEqual(premium_schedule.insured_duration, 240)
        insured_loan = premium_schedule.coverage_amortization
        self.assertEqual(insured_loan.loan_amount, D('100000'))
        self.assertEqual(insured_loan.interest_rate, D('5.0'))
        self.assertEqual(insured_loan.number_of_months, 360)
        self.assertEqual(insured_loan.payment_interval, 1)
        agreed_features = {agreed_feature.described_by: agreed_feature.value for agreed_feature in premium_schedule.agreed_features}
        self.assertEqual(100, agreed_features.get('premium_fee_1'))
        self.assertEqual(20, agreed_features.get('premium_rate_1'))
        self.assertEqual(100, agreed_features.get('coverage_limit'))
        self.assertEqual(3, agreed_features.get('premium_taxation_physical_person'))
        fiscal_regime = None
        for agreed_functional_setting in imported_agreement.agreed_functional_settings:
            if agreed_functional_setting.group is not None and agreed_functional_setting.group.name == 'fiscal_regime':
                fiscal_regime = agreed_functional_setting.described_by
        self.assertEqual('retirement_savings', fiscal_regime)
        self.assertEqual(direct_debit_mandate_be._iban, 'BE48 6511 4362 0327')
        self.assertEqual(direct_debit_mandate_be.bank_identifier_code, 'KEYTBEBB')
        self.assertEqual(direct_debit_mandate_nl._iban, 'NL91 ABNA 0417 1643 00')
        self.assertEqual(direct_debit_mandate_nl.bank_identifier_code, 'ABNANL2AXXX')


        items = [item for item in imported_agreement.agreed_items]
        self.assertEqual(len(items), 2)
        for item in items:
            if item.rank == 1:
                self.assertIn('personen die de volle eigendom of het vruchtgebruik van de woning', item.shown_clause)
            if item.rank == 2:
                self.assertIn('De begunstigden', item.shown_clause)


if __name__ == '__main__':
    unittest.main(verbosity=2)
