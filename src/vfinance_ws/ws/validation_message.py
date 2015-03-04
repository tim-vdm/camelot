#!/usr/bin/env python
import json
from decimal import Decimal
import datetime
from functools import wraps

import voluptuous
from voluptuous import (
    All,
    Any,
    Coerce,
    Length,
    Optional,
    Required,
)


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
    Required("agent_official_number_fsma"): All(basestring, Length(max=128)),
    Required("agreement_date"): DATE_SCHEMA,
    Required("duration"): int,
    # voluptuous.Range(min=1, max=10),
    Required("from_date"): DATE_SCHEMA,
    Required("insured_party__1__birthdate"): DATE_SCHEMA,
    Required("insured_party__1__sex"): voluptuous.In(["M", "F", 'm', 'f']),
    Required("package_id"): int,
    Required("premium_schedule__1__premium_fee_1"): Coerce(Decimal),
    Required("premium_schedule__1__product_id"): int,
    Required("premium_schedule__2__product_id"): voluptuous.Any(None, int),
    Required("premium_schedule__1__coverage_level_type"):
        voluptuous.In(["fixed_amount", "decreasing_amount"]),
    Required("premium_schedule__2__coverage_level_type"):
        voluptuous.Any(None, 'decreasing_amount'),
    Required("premium_schedules_coverage_limit"): Coerce(Decimal),
    Required("premium_schedules_payment_duration"): int,
    Required("premium_schedules_period_type"):
        voluptuous.In(["single", "yearly"]),
    Required("premium_schedules_premium_rate_1"): Coerce(Decimal),
}

CREATE_AGREEMENT_CODE_SCHEMA = dict(CALCULATE_PROPOSAL_SCHEMA)
CREATE_AGREEMENT_CODE_SCHEMA.update({
    Required("origin"): Length(max=32),
    Optional('insured_party__1__last_name'): All(basestring, Length(max=30)),
    Optional('insured_party__1__first_name'): All(basestring, Length(max=30)),
    Optional('insured_party__1__language'): All(basestring, Length(max=5)),
    Optional('insured_party__1__nationality_code'): All(basestring, Length(max=2)),
    Optional('insured_party__1__social_security_number'): Any(None, Length(max=12)),
    Optional('insured_party__1__passport_number'): Any(None, Length(max=20)),
    Optional('insured_party__1__dangerous_hobby'): Any(None, Length(max=20)),
    Optional('insured_party__1__dangerous_profession'): Any(None, Length(max=20)),
    Optional('insured_party__1__street_1'): All(basestring, Length(max=128)),
    Optional('insured_party__1__city_code'): All(basestring, Length(max=10)),
    Optional('insured_party__1__city_name'): All(basestring, Length(max=40)),
    Optional('insured_party__1__country_code'): All(basestring, Length(max=2)),
    Optional('pledgee_name'): Any(None, Length(max=30)),
    Optional('pledgee_tax_id'): Any(None, Length(max=20)),
    Optional('pledgee_reference'): Any(None, Length(max=30)),
})

SEND_AGREEMENT_SCHEMA = dict(CREATE_AGREEMENT_CODE_SCHEMA)
SEND_AGREEMENT_SCHEMA.update({
    Required("signature"): All(basestring, Length(max=64)),
    Required("premium_schedule__1__amount"): Coerce(Decimal),
    Required("premium_schedule__2__amount"): Any(None, Coerce(Decimal)),
    Required("code"): All(basestring, Length(max=32)),
})


def validation_calculate_proposal(document):
    FIELDS_DATE = (
        ['agreement_date'],
        ['from_date'],
        ['insured_party__1__birthdate'],
    )

    return validate_document(
        document,
        CALCULATE_PROPOSAL_SCHEMA,
        FIELDS_DATE
    )


def validation_create_agreement_code(document):
    FIELDS_DATE = (
        ['agreement_date'],
        ['from_date'],
        ['insured_party__1__birthdate'],
    )

    return validate_document(
        document,
        CREATE_AGREEMENT_CODE_SCHEMA,
        FIELDS_DATE
    )


def validation_send_agreement(document):
    FIELDS_DATE = (
        ['agreement_date'],
        ['from_date'],
        ['insured_party__1__birthdate'],
    )

    return validate_document(
        document,
        SEND_AGREEMENT_SCHEMA,
        FIELDS_DATE
    )


if __name__ == '__main__':

    document = """{
        "insured_party__1__last_name": "FALK",
        "insured_party__1__first_name": "JULES",
        "insured_party__1__birthdate": {
                        "year": 1980,
                        "month": 2,
                        "day": 7
        },
        "insured_party__1__sex": "M",
        "insured_party__1__language": "fr_BE",
        "insured_party__1__nationality_code": "BE",
        "insured_party__1__social_security_number": "80020705175",
        "insured_party__1__passport_number": null,
        "insured_party__1__dangerous_hobby": null,
        "insured_party__1__dangerous_profession": null,
        "insured_party__1__street_1": "HAUTE-HEZ 76",
        "insured_party__1__city_code": {
                        "year": 4000,
                        "month": 1,
                        "day": 1
        },
        "insured_party__1__city_name": "GLAIN",
        "insured_party__1__country_code": "BE",
        "premium_schedules_coverage_limit": "5602.00",
        "premium_schedules_payment_duration": 42,
        "duration": 42,
        "from_date": {
                        "year": 2015,
                        "month": 2,
                        "day": 26
        },
        "premium_schedule__2__product_id": 68,
        "premium_schedules_coverage_level_type": "decreasing_amount",
        "premium_schedules_premium_rate_1": "40.00",
        "premium_schedule__1__premium_fee_1": "50.00",
        "pledgee_name": "DHB BANK",
        "pledgee_tax_id": "BE 0464.655.437",
        "pledgee_reference": "350130145",
        "premium_schedules_period_type": "single",
        "package_id": 64,
        "premium_schedule__1__product_id": 67,
        "agreement_date": {
                        "year": 2015,
                        "month": 2,
                        "day": 26
        },
        "agent_official_number_fsma": "12345",
        "origin": "BIA:1234"
        }
    """
    document = json.loads(document)
    # with open('calculate_proposal.json') as jsonfile:
    #     document = json.load(jsonfile)
    #     validated_document, errors = validation_calculate_proposal(document)
    validator = voluptuous.Schema(CREATE_AGREEMENT_CODE_SCHEMA)  # , extra=voluptuous.ALLOW_EXTRA)
    validated_document = validator(document)


