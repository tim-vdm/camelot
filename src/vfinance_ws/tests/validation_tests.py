import unittest
from decimal import Decimal

import voluptuous

from ..ws import validation_message


def date_new(year, month, day):
    return {
        'year': year,
        'month': month,
        'day': day
    }


class DocumentValidationTestCase(unittest.TestCase):
    def test_010_schema_date(self):
        validator = voluptuous.Schema(validation_message.DATE_SCHEMA)
        document = date_new(None, 3, 1)
        with self.assertRaises(voluptuous.MultipleInvalid):
            doc = validator(document)

        document = date_new(2015, 3, 1)
        doc = validator(document)
        self.assertIn('month', doc)
        self.assertEqual(doc['month'], 3)

        self.assertIn('year', doc)
        self.assertEqual(doc['year'], 2015)

        self.assertIn('day', doc)
        self.assertEqual(doc['day'], 1)

    def test_011_schema_date_wrong(self):
        validator = voluptuous.Schema(validation_message.DATE_SCHEMA)

        with self.assertRaises(voluptuous.MultipleInvalid):
            document = date_new(2015, 13, -1)
            validator(document)

    def test_012_schema_sex(self):
        schema = {
            voluptuous.Required('sex'): voluptuous.All(voluptuous.Upper, voluptuous.In(['M', 'F']))
        }

        validator = voluptuous.Schema(schema)
        doc = validator({'sex': 'M'})
        self.assertEqual(doc['sex'], 'M')
        doc = validator({'sex': 'm'})
        self.assertEqual(doc['sex'], 'M')
        doc = validator({'sex': 'F'})
        self.assertEqual(doc['sex'], 'F')
        doc = validator({'sex': 'f'})
        self.assertEqual(doc['sex'], 'F')

        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({})
        self.assertIsInstance(ex.exception.errors[0], voluptuous.RequiredFieldInvalid)

        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({'sex': 'I'})
        self.assertIsInstance(ex.exception.errors[0], voluptuous.InInvalid)

    def test_013_schema_decimal(self):
        schema = {
            voluptuous.Required('amount'): voluptuous.Coerce(Decimal)
        }

        validator = voluptuous.Schema(schema)

        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({'amount': None})
        self.assertIsInstance(ex.exception.errors[0], voluptuous.CoerceInvalid)

        document = validator({'amount': "10.5"})
        self.assertIsInstance(document['amount'], Decimal)

    def test_allow_none(self):
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

    def test_not_none_string(self):
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

    def test_duration(self):
        schema = {
            voluptuous.Required('duration'): voluptuous.All(voluptuous.Coerce(int), voluptuous.Range(min=1)),
        }

        validator = voluptuous.Schema(schema)
        with self.assertRaises(voluptuous.MultipleInvalid):
            validator({'duration': None})

        doc = validator({'duration': "10"})
        self.assertEqual(doc, {'duration':10})

        with self.assertRaises(voluptuous.MultipleInvalid):
            doc = validator({'duration': -1})
    


class CalculateProposalSchemaTestCase(unittest.TestCase):
    def setUp(self):
        self.validator = voluptuous.Schema(validation_message.CALCULATE_PROPOSAL_SCHEMA)

    def test_01_minimal_schema(self):
        document = {
            'agent_official_number_fsma': "fsma",
            'agreement_date': date_new(2015, 3, 1),
            'duration': 10,
            'from_date': date_new(2015, 3, 2),
            'insured_party__1__birthdate': date_new(1980, 9, 15),
            'insured_party__1__sex': 'M',
            'package_id': 10,
            'premium_schedule__1__coverage_level_type': 'fixed_amount',
            'premium_schedule__1__premium_fee_1': "10.0",
            'premium_schedule__1__product_id': 10,
            'premium_schedule__2__coverage_level_type': None,
            'premium_schedule__2__product_id': None,
            'premium_schedules_coverage_limit': "10.0",
            'premium_schedules_payment_duration': 10,
            'premium_schedules_period_type': "single",
            'premium_schedules_premium_rate_1': "10.0",
        }

        self.validator(document)

