import unittest

import voluptuous
from voluptuous import Required, Schema, In, Coerce
from decimal import Decimal

from ..ws import validation_message

def date_new(year, month, day):
    return {
        'year': year,
        'month': month,
        'day': day
    }

class DocumentValidationTestCase(unittest.TestCase):
    def setUp(self):
        self.validator = voluptuous.Schema(validation_message.DATE_SCHEMA)

    def test_010_date_schema(self):
        document = date_new(2015, 3, 1)
        doc = self.validator(document)
        self.assertIn('month', doc)
        self.assertEqual(doc['month'], 3)

        self.assertIn('year', doc)
        self.assertEqual(doc['year'], 2015)

        self.assertIn('day', doc)
        self.assertEqual(doc['day'], 1)

    def test_011_date_schema_wrong(self):
        with self.assertRaises(voluptuous.MultipleInvalid):
            document = date_new(2015, 13, -1)
            self.validator(document)

    def test_012_schema_sex(self):
        schema = {
            Required('sex'): In(['M', 'F'])
        }
        validator = Schema(schema)
        validator({'sex': 'M'})
        validator({'sex': 'F'})

        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({})
        self.assertIsInstance(ex.exception.errors[0], voluptuous.RequiredFieldInvalid)

        with self.assertRaises(voluptuous.MultipleInvalid) as ex:
            validator({'sex': 'I'})
        self.assertIsInstance(ex.exception.errors[0], voluptuous.InInvalid)

    def test_013_schema(self):
        schema = {
            Required('amount'): Coerce(Decimal)
        }

        validator = Schema(schema)
        document = validator({'amount': "10.5"})
        self.assertIsInstance(document['amount'], Decimal)
