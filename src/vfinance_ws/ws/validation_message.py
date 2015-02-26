#!/usr/bin/env python

import voluptuous
import json
import datetime

from voluptuous import Required, Coerce, Length, Optional, Any
from decimal import Decimal


def IsNone(v):
    if v is not None:
        raise ValueError
    return v


def lookup(dic, key, *keys):
    if keys:
        return lookup(dic.get(key, {}), *keys)
    return dic.get(key)


def check_date_field(dic, *keys):
    date = lookup(dic, *keys)
    try:
        datetime.date(date['year'], date['month'], date['day'])
    except ValueError, ex:
        if 'month must be' in ex.message:
            path = list(keys) + ['month']
            raise voluptuous.Invalid(ex.message, path=path)
        elif 'day is out of' in ex.message:
            path = list(keys) + ['day']
            raise voluptuous.Invalid(ex.message, path=path)


def validate_document(document, schema, fields_date=None):
    validator = voluptuous.Schema(schema)  # , extra=voluptuous.ALLOW_EXTRA)
    if fields_date is None:
        fields_date = []

    errors = {}

    validated_document = None
    # First validation with Voluptuous
    try:
        validated_document = validator(document)
    except voluptuous.MultipleInvalid as ex:
        # from nose.tools import set_trace
        # set_trace()
        # import pdb
        # pdb.set_trace()
        for error in ex.errors:
            if isinstance(error, voluptuous.RequiredFieldInvalid):
                errors[error.path[0].schema] = {
                    u'message': 'Required',
                }
            else:
                path_str = '/'.join(error.path)

                errors[path_str] = {
                    u'message': error.error_message,
                    u'value': lookup(document, *error.path)
                }

    # Second validation for the specific date field (year, month, day)
    if validated_document:
        for date_field in fields_date:
            try:
                check_date_field(validated_document, *date_field)
            except voluptuous.Invalid as error:
                path_str = '/'.join(error.path)
                errors[path_str] = {
                    u'message': error.error_message,
                    u'value': lookup(validated_document, *error.path)
                }
    return validated_document, errors


DATE_SCHEMA = {
    Required("month"): voluptuous.Range(min=1, max=12),
    Required("year"): voluptuous.Range(min=1900, max=2400),
    Required("day"): voluptuous.Range(min=1, max=31),
}


CALCULATE_PROPOSAL_SCHEMA = {
    Required("agent_official_number_fsma"): Length(max=128),
    Required("agreement_date"): DATE_SCHEMA,
    Required("duration"): int,
    # voluptuous.Range(min=1, max=10),
    Required("from_date"): DATE_SCHEMA,
    Required("insured_party__1__birthdate"): DATE_SCHEMA,
    Required("insured_party__1__sex"): voluptuous.Any("M", "F"),
    Required("package_id"): int,
    Required("premium_schedule__1__premium_fee_1"): Coerce(Decimal),
    Required("premium_schedule__1__product_id"): int,
    Required("premium_schedule__2__product_id"): voluptuous.Any(IsNone, int),
    Required("premium_schedules_coverage_level_type"):
        voluptuous.In(["fixed_amount", "decreasing_amount"]),
    Required("premium_schedules_coverage_limit"): Coerce(Decimal),
    Required("premium_schedules_payment_duration"): int,
    Required("premium_schedules_period_type"):
        voluptuous.In(["single", "yearly"]),
    Required("premium_schedules_premium_rate_1"): Coerce(Decimal),
}

CREATE_AGREEMENT_CODE_SCHEMA = dict(CALCULATE_PROPOSAL_SCHEMA)
CREATE_AGREEMENT_CODE_SCHEMA.update({
    Required("origin"): Length(max=32),
    Optional('insured_party__1__last_name'): Length(max=30),
    Optional('insured_party__1__first_name'): Length(max=30),
    Optional('insured_party__1__language'): Length(max=5),
    Optional('insured_party__1__nationality_code'): Length(max=2),
    Optional('insured_party__1__social_security_number'): Length(max=12),
    Optional('insured_party__1__passport_number'): Length(max=20),
    Optional('insured_party__1__dangerous_hobby'): Any(Length(max=20), IsNone),
    Optional('insured_party__1__street_1'): Length(max=128),
    Optional('insured_party__1__city_code'): Length(max=10),
    Optional('insured_party__1__city_name'): Length(max=40),
    Optional('insured_party__1__country_code'): Length(max=2),
    Optional('pledge_name'): Any(IsNone, Length(max=30)),
    Optional('pledge_tax_id'): Any(IsNone, Length(max=20)),
    Optional('pledge_reference'): Any(IsNone, Length(max=30)),
})

def validation_calculate_proposal(document):
    FIELDS_DATE = (
        ['agreement_date'],
        ['from_date'],
        ['insured_party__1__birthdate'],
    )

    return validate_document(document, CALCULATE_PROPOSAL_SCHEMA, FIELDS_DATE)

def validation_create_agreement_code(document):
    FIELDS_DATE = (
        ['agreement_date'],
        ['from_date'],
        ['insured_party__1__birthdate'],
    )

    return validate_document(document, CREATE_AGREEMENT_CODE_SCHEMA, FIELDS_DATE)


if __name__ == '__maine__':
    with open('calculate_proposal.json') as jsonfile:
        document = json.load(jsonfile)
        validated_document, errors = validation_calculate_proposal(document)
