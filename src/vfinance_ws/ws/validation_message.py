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

ADDRESS_SCHEMA = {
    Required("street_1"): String(max=40),
    Optional("id"): String(max=32),
    Optional("street_2"): String(max=40),
    Required("zip_code"): String(max=5),
    Required("city"): String(max=40),
    Required("country_code"): String(max=2)
}

Address = Schema(ADDRESS_SCHEMA)

HISTORICAL_ADDRESS_SCHEMA = dict(ADDRESS_SCHEMA)
HISTORICAL_ADDRESS_SCHEMA.update({
    Required("described_by"): String(max=40),
    Required("from_date"): Date,
    Optional("thru_date"): Date
})


FEATURE_SCHEMA = {
    Required("described_by"): String(max=40),
    Required("value"): String(max=40)
}

Features = Schema([FEATURE_SCHEMA])

Addresses = Schema([HISTORICAL_ADDRESS_SCHEMA])

CONTACT_MECHANISM_SCHEMA = {
    Required("described_by"): String(max=10),
    Optional("address_type"): String(max=10),
    Required("contact_mechanism"): String(max=30),
    Optional("comment"): String(max=256)
}

ContactMechanisms = Schema([CONTACT_MECHANISM_SCHEMA])

ASSET_SCHEMA = {
    Required("id"): String(max=23),
    Required("described_by"): String(max=40),
    Required("address"): Address
}

Asset = All(ASSET_SCHEMA)


AGREEMENT_ASSET_SCHEMA = {
    Required("used_as"): String(max=40),
    Optional("lien_amount"): String(max=20),
    Optional("conditional_lien_amount"): String(max=20),
    Optional("building_lot_price"): String(max=20),
    Optional("initial_value"): String(max=20),
    Optional("added_value"): String(max=20),
    Optional("building_lot_number"): String(max=20),
    Optional("appraised_value"): String(max=20),
    Optional("selling_value"): String(max=20),
    Optional("forced_selling_value"): String(max=20),
    Optional("habitable_area"): String(max=20),
    Optional("housefront_width"): String(max=20),
    Optional("building_lot_width"): String(max=20),
    Optional("rental_revenues"): String(max=20),
    Required("asset"): Asset
}

Assets = Schema([AGREEMENT_ASSET_SCHEMA])

SCHEDULE_SCHEMA = {
    Required("row_type"): String(max=20),
    Required("product_id"): int,
    Required("amount"): String(max=20),
    Required("duration"): int,
    Required("period_type"): String(max=40),
    Required("direct_debit"): Boolean,
    Required("described_by"): String(max=40),
    Optional("suspension_of_payment"): int,
    Optional("down_payment"): String(max=40),
    Optional("purchase_terrain"): String(max=40),
    Optional("new_housing"): String(max=40),
    Optional("renovation"): String(max=40),
    Optional("refinancing"): String(max=40),
    Optional("centralization"): String(max=40),
    Optional("building_purchase"): String(max=40),
    Optional("bridging_credit"): String(max=40),
    Optional("signing_agent_mortgage"): String(max=40),
    Optional("signing_agent_purchase"): String(max=40),
    Optional("architect_fee"): String(max=40),
    Optional("homeowners_insurance"): String(max=40),
    Optional("mortgage_insurance"): String(max=40),
    Optional("life_insurance"): String(max=40),
    Optional("vat"): String(max=40),
    Optional("registration_fee"): String(max=40),
    Optional("other_costs"): String(max=40)
}

Schedules = Schema([SCHEDULE_SCHEMA])

PERSON_SCHEMA = {
    Required("row_type"): 'person',
    Required("first_name"): String(max=40),
    Required("last_name"): String(max=40),
    Required("social_security_number"): String(max=12),
    Required("passport_number"): String(max=20),
    Required("passport_expiry_date"): Date,
    Required("sex"): Sex,
    Required("language"): String(max=5),
    Required("birth_date"): Date,
    Optional("middle_name"): String(max=40),
    Optional("personal_title"): String(max=10),
    Optional("suffix"): String(max=3),
    Optional("nationality_code"): String(max=2),
    Optional("personal_title"): String(max=10),
    Optional("marital_status"): String(max=50),
    Optional("marital_contract"): String(max=50),
    Optional("occupation"): String(max=50),
    Optional("company_name"): String(max=40),
    Optional("company_since"): Date,
    Optional("activity"): String(max=40),
    Optional("activity_since"): Date,
    Optional("tax_id"): String(max=20),
    Required("addresses"): Addresses,
    Optional("contact_mechanisms"): ContactMechanisms
}

Person = All(PERSON_SCHEMA)

ORGANIZATION_SCHEMA = {
    Required("row_type"): 'organization',
    Required("name"): String(max=40),
    Required("tax_id"): String(max=20)#,
    #Optional("roles"): 
}


PARTY_SCHEMA = Any(PERSON_SCHEMA, ORGANIZATION_SCHEMA)

ROLE_SCHEMA = {
    Required("described_by"): String(max=30),
    Required("rank"): int,
    Optional("net_earnings_of_employment"): String(max=40),
    Optional("net_earnings_of_secondary_activity"): String(max=40),
    Optional("loan_expenses"): String(max=40),
    Optional("net_rent_revenues"): String(max=40),
    Optional("net_alimony_revenues"): String(max=40),
    Optional("net_child_support_revenues"): String(max=40),
    Optional("net_other_revenues"): String(max=40),
    Optional("replacement_income"): String(max=40),
    Optional("net_child_allowance_revenues"): String(max=40),
    Optional("expected_net_additional_revenues"): String(max=40),
    Optional("earnings_documentation"): String(max=40),
    Optional("housing_expenses"): String(max=40),
    Optional("alimony_expenses"): String(max=40),
    Optional("child_support_expenses"): String(max=40),
    Optional("other_expenses"): String(max=40),
    Optional("credit_card_history"): String(max=40),
    Optional("credit_history"): String(max=40),
    Optional("cohabiting_children"): String(max=40),
    Optional("cohabiting_parents"): String(max=40),
    Optional("smoking_habit"): String(max=40),
    Optional("educational_level"): String(max=40),
    Optional("fitness_level"): String(max=40),
    Optional("asset_id"): String(max=32),
    Optional("asset_ownership_percentage"): String(max=40),
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

CI_CREATE_AGREEMENT_CODE_SCHEMA = dict(CALCULATE_PROPOSAL_SCHEMA)
CI_CREATE_AGREEMENT_CODE_SCHEMA.update({
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

CREATE_AGREEMENT_CODE_SCHEMA = {
    Required('origin'): Length(max=32),
    Required('agent_official_number_fsma'): String(max=128),
    Required('row_type'): RowType,
    Required('agreement_date'): Date,
    Required('from_date'): Date,
    Required('package_id'): int,
    Required('roles'): Roles,
    Optional('assets'): Assets,
    Required('schedules'): Schedules
}

SEND_AGREEMENT_SCHEMA = dict(CI_CREATE_AGREEMENT_CODE_SCHEMA)
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


def validation_ci_create_agreement_code(document):
    return validate_document(document, CI_CREATE_AGREEMENT_CODE_SCHEMA)


def validation_send_agreement(document):
    return validate_document(document, SEND_AGREEMENT_SCHEMA)


def validation_get_packages(document):
    return validate_document(document, GET_PACKAGES_SCHEMA)

def validation_create_agreement_code(document):
    return validate_document(document, CREATE_AGREEMENT_CODE_SCHEMA)
