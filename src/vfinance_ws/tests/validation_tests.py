import unittest
import os
from decimal import Decimal
import json

import voluptuous

from ..ws import validation_message


DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'demo')


def load_demo_json(fname):
    with open(os.path.join(DEMO_DIR, "%s.json" % (fname,))) as infile:
        return json.load(infile)


def date_new(year, month, day):
    return {
        'year': year,
        'month': month,
        'day': day
    }

class ValidationTestCase(unittest.TestCase):
    def test_01(self):
        schema = {
            'date': voluptuous.All(validation_message.DATE_SCHEMA, validation_message.ValidateDate)
        }
        document = {
            'date': {
                'month': 2,
                'year': 2015,
                'day': 29
            }
        }
        doc, errors = validation_message.validate_document(document, schema)

        self.assertEqual(errors, {
            'date/day': {
                'message': 'day is out of range for month', 
                'value': 29
            }
        })


class DocumentValidationTestCase(unittest.TestCase):
    def test_010_schema_date(self):
        validator = voluptuous.Schema(validation_message.DATE_SCHEMA)
        document = date_new(None, 3, 1)
        with self.assertRaises(voluptuous.MultipleInvalid):
            doc = validator(document)

        document = date_new(2015, 3, 1)
        doc = validator(document)
        self.assertEqual(doc, {'day': 1, 'month': 3, 'year': 2015})

    def test_011_schema_date_wrong(self):
        validator = voluptuous.Schema(validation_message.DATE_SCHEMA)

        with self.assertRaises(voluptuous.MultipleInvalid):
            document = date_new(2015, 13, -1)
            validator(document)

    def test_012_validation_date(self):
        schema = {
            'date': voluptuous.All(validation_message.DATE_SCHEMA, validation_message.ValidateDate)
        }

        validator = voluptuous.Schema(schema)
        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({'date': {'month': 2, 'year': 2015, 'day': 29}})
        self.assertEqual(ex.exception.msg, 'day is out of range for month')


    def test_013_schema_sex(self):
        schema = {
            voluptuous.Required('sex'): voluptuous.All(voluptuous.Upper, voluptuous.In(['M', 'F']))
        }

        validator = voluptuous.Schema(schema)
        doc = validator({'sex': 'M'})
        self.assertEqual(doc, {'sex': 'M'})

        doc = validator({'sex': 'm'})
        self.assertEqual(doc, {'sex': 'M'})

        doc = validator({'sex': 'F'})
        self.assertEqual(doc, {'sex': 'F'})

        doc = validator({'sex': 'f'})
        self.assertEqual(doc, {'sex': 'F'})

        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({})
        self.assertIsInstance(ex.exception.errors[0], voluptuous.RequiredFieldInvalid)

        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({'sex': 'I'})
        self.assertIsInstance(ex.exception.errors[0], voluptuous.InInvalid)

    def test_014_schema_decimal(self):
        schema = {
            voluptuous.Required('amount'): voluptuous.Coerce(Decimal)
        }

        validator = voluptuous.Schema(schema)

        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({'amount': None})
        self.assertIsInstance(ex.exception.errors[0], voluptuous.CoerceInvalid)

        document = validator({'amount': "10.5"})
        self.assertIsInstance(document['amount'], Decimal)

    def test_015_allow_none(self):
        schema = {
            voluptuous.Required('product_id') : voluptuous.Any(None, voluptuous.Coerce(long))
        }

        validator = voluptuous.Schema(schema)

        doc = validator({'product_id': None})
        self.assertEqual(doc, {'product_id': None})

        doc = validator({'product_id': 10})
        self.assertEqual(doc, {'product_id': 10})

        doc = validator({'product_id': "10"})
        self.assertEqual(doc, {'product_id': 10})

    def test_016_not_none_string(self):
        schema = {
            'name': voluptuous.All(basestring, voluptuous.Length(min=2, max=10)),
        }

        validator = voluptuous.Schema(schema)
        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({'name': None})
        self.assertIsInstance(ex.exception.errors[0], voluptuous.TypeInvalid)

        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({'name': 'H'})
        self.assertIsInstance(ex.exception.errors[0], voluptuous.LengthInvalid)

    def test_017_duration(self):
        schema = {
            voluptuous.Required('duration'): voluptuous.All(voluptuous.Coerce(int), voluptuous.Range(min=1)),
        }

        validator = voluptuous.Schema(schema)
        with self.assertRaises(voluptuous.MultipleInvalid):
            validator({'duration': None})

        doc = validator({'duration': "10"})
        self.assertEqual(doc, {'duration': 10})

        with self.assertRaises(voluptuous.MultipleInvalid):
            doc = validator({'duration': -1})
    

class CalculateProposalSchemaTestCase(unittest.TestCase):
    def setUp(self):
        self.validator = voluptuous.Schema(validation_message.CALCULATE_PROPOSAL_SCHEMA)

    def test_01_calculate_proposal_correct(self):
        document = load_demo_json('calculate_proposal')
        self.validator(document)


class CreateAgreementCodeSchemaTestCase(unittest.TestCase):
    def setUp(self):
        self.validator = voluptuous.Schema(validation_message.CREATE_AGREEMENT_CODE_SCHEMA)

    def test_01_create_agreement_code_correct(self):
        document = load_demo_json('create_agreement_code')
        self.validator(document)


class SendAgreementTestCase(unittest.TestCase):
    def setUp(self):
        self.validator = voluptuous.Schema(validation_message.SEND_AGREEMENT_SCHEMA)

    def test_01_send_agreement_correct(self):
        document = load_demo_json('send_agreement')
        self.validator(document)
