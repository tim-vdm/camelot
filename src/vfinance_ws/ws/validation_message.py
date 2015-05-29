#!/usr/bin/env python
from decimal import Decimal
import datetime

from voluptuous import (
    All,
    Any,
    Coerce,
    In,
    Invalid,
    Length,
    Optional,
    Range,
    Required,
    Schema,
    Upper,
)


def lookup(dic, key, *keys):
    if keys:
        return lookup(dic.get(key, {}), *keys)
    return dic.get(key)


def ValidateDate(v):
    try:
        datetime.date(month=v['month'], year=v['year'], day=v['day'])
    except ValueError, error:
        if 'month must be' in error.message:
            raise Invalid(error.message, path=['month'])
        elif 'day is out of' in error.message:
            raise Invalid(error.message, path=['day'])
    return v

def String(**kwargs):
    return All(basestring, Length(**kwargs))

DATE_SCHEMA = {
    Required("month"): Range(min=1, max=12),
    Required("year"): Range(min=1900, max=2400),
    Required("day"): Range(min=1, max=31),
}
Date = All(DATE_SCHEMA, ValidateDate)
Boolean = In([True, False])
Sex = In(["M", "F"])
RowType = Schema(String(max=20))


PERSON_SCHEMA = {
    Required("first_name"): String(max=40),
    Required("last_name"): String(max=40),
    Required("social_security_number"): String(max=12),
    Required("passport_number"): String(max=20),
    Required("passport_expiry_date"): Date,
    Required("smoker"): Boolean,
    Required("sex"): Sex,
    Required("street_1"): String(max=40),
    Required("city_code"): String(max=5),
    Required("city_name"): String(max=40),
    Required("language"): String(max=5),
    Optional("birth_date"): Date,
    Optional("middle_name"): String(max=40),
    Optional("personal_title"): String(max=10),
    Optional("suffix"): String(max=3),
    Optional("nationality_code"): String(max=2),
    Optional("country_code"): String(max=2)
}

ORGANIZATION_SCHEMA = {
    Required("name"): String(max=40),
}


PARTY_SCHEMA = {
    Required("row_type"): RowType,
    Required("party_data"): Any(PERSON_SCHEMA, ORGANIZATION_SCHEMA),
}

ROLE_SCHEMA = {
    Required("described_by"): String(max=30),
    Required("rank"): int,
    Required("total_income"): String(max=12), # Decimal als string, role-feature
    Required("party"): PARTY_SCHEMA
}

Roles = Schema([ROLE_SCHEMA])

CALCULATE_PROPOSAL_SCHEMA = {
    Required("agent_official_number_fsma"): String(max=128),
    Required("agreement_date"): Date,
    Required("duration"): int,
    Required("from_date"): Date,
    Required("insured_party__1__birthdate"): Date,
    Required("insured_party__1__sex"): All(Upper, In(['M', 'F'])),
    Required("package_id"): int,
    Required("premium_schedule__1__premium_fee_1"): Coerce(Decimal),
    Required("premium_schedule__1__product_id"): int,
    Required("premium_schedule__2__product_id"): Any(None, int),
    Required("premium_schedule__1__coverage_level_type"): In(["fixed_amount", "decreasing_amount"]),
    Required("premium_schedule__2__coverage_level_type"): Any(None, 'decreasing_amount'),
    Required("premium_schedules_coverage_limit"): Coerce(Decimal),
    Required("premium_schedules_payment_duration"): int,
    Required("premium_schedules_period_type"): In(["single", "yearly"]),
    Required("premium_schedules_premium_rate_1"): Coerce(Decimal),
}

CREATE_AGREEMENT_CODE_SCHEMA = dict(CALCULATE_PROPOSAL_SCHEMA)
CREATE_AGREEMENT_CODE_SCHEMA.update({
    Required("origin"): Length(max=32),
    Optional('insured_party__1__last_name'): String(max=30),
    Optional('insured_party__1__first_name'): String(max=30),
    Optional('insured_party__1__language'): String(max=5),
    Optional('insured_party__1__nationality_code'): String(max=2),
    Optional('insured_party__1__social_security_number'): Any(None, Length(max=12)),
    Optional('insured_party__1__passport_number'): Any(None, Length(max=20)),
    Optional('insured_party__1__dangerous_hobby'): Any(None, Length(max=20)),
    Optional('insured_party__1__dangerous_profession'): Any(None, Length(max=20)),
    Optional('insured_party__1__street_1'): String(max=128),
    Optional('insured_party__1__city_code'): String(max=10),
    Optional('insured_party__1__city_name'): String(max=40),
    Optional('insured_party__1__country_code'): String(max=2),
    Optional('pledgee_name'): Any(None, Length(max=30)),
    Optional('pledgee_tax_id'): Any(None, Length(max=20)),
    Optional('pledgee_reference'): Any(None, Length(max=30)),
})

CREATE_AGREEMENT_CODE_2_SCHEMA = {
    Required('origin'): Length(max=32),
    Required('agent_official_number_fsma'): String(max=128),
    Required('agreement_date'): Date,
    Required('from_date'): Date,
    Required('package_id'): int,
    Required('roles'): Roles,
    Required('row_type'): RowType
}

SEND_AGREEMENT_SCHEMA = dict(CREATE_AGREEMENT_CODE_SCHEMA)
SEND_AGREEMENT_SCHEMA.update({
    Required("signature"): String(max=64),
    Required("premium_schedule__1__amount"): Coerce(Decimal),
    Required("premium_schedule__2__amount"): Any(None, Coerce(Decimal)),
    Required("code"): String(max=32),
})

GET_PACKAGES_SCHEMA = {
    Required("agent_official_number_fsma"): String(max=128),
}



def validate_document(document, schema):
    validator = Schema(schema)
    return validator(document)


def validation_calculate_proposal(document):
    return validate_document(document, CALCULATE_PROPOSAL_SCHEMA)


def validation_create_agreement_code(document):
    return validate_document(document, CREATE_AGREEMENT_CODE_SCHEMA)


def validation_send_agreement(document):
    return validate_document(document, SEND_AGREEMENT_SCHEMA)


def validation_get_packages(document):
    return validate_document(document, GET_PACKAGES_SCHEMA)

def validation_create_agreement_code_2(document):
    return validate_document(document, CREATE_AGREEMENT_CODE_2_SCHEMA)
