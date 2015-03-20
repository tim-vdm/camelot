# -*- coding: utf-8 -*-
import datetime
import hashlib
import json

from sqlalchemy import orm

from vfinance.connector.aws import AwsQueue
from vfinance.connector.aws import QueueCommand
from vfinance.connector.json_ import ExtendedEncoder

from vfinance.facade.financial_agreement import FinancialAgreementFacade

from vfinance.model.financial.agreement import FinancialAgreementJsonExport
from vfinance.model.financial.package import FinancialPackage
from vfinance.model.financial.product import FinancialProduct
from vfinance.model.insurance.credit_insurance import CalculateCreditInsurance

from vfinance_ws.api.utils import DecimalEncoder
from vfinance_ws.api.utils import to_table_html
from vfinance_ws.ws.utils import with_session


calculate_credit_insurance = CalculateCreditInsurance()


@with_session
def calculate_proposal(session, document):
    facade = create_facade_from_calculate_proposal_schema(session, document)

    orm.object_session(facade).flush()

    amount1 = str(facade.premium_schedule__1__amount)
    amount2 = str(facade.premium_schedule__2__amount) \
        if facade.premium_schedule__2__amount else None

    return {
        'premium_schedule__1__amount': amount1,
        'premium_schedule__2__amount': amount2,
    }


@with_session
def create_agreement_code(session, document, logfile):
    facade = create_facade_from_create_agreement_schema(session, document)

    orm.object_session(facade).flush()

    dump = FinancialAgreementJsonExport().entity_to_dict(facade)
    json.dump(dump, logfile, cls=ExtendedEncoder)

    amount1 = str(facade.premium_schedule__1__amount)
    amount2 = str(facade.premium_schedule__2__amount) \
        if facade.premium_schedule__2__amount else None

    values = {
        'premium_schedule__1__amount': amount1,
        'premium_schedule__2__amount': amount2,
        'code': facade.code,
    }

    use_for_signature = {
        'proposal': document,
        'values': values,
    }

    dump = json.dumps(
        use_for_signature,
        cls=DecimalEncoder
    )

    signature = hashlib.sha256(dump).hexdigest()

    values['signature'] = signature
    return values


@with_session
def get_packages(session, document):
    packages = []

    for package in session.query(FinancialPackage).all():
        products = []
        for product in package.available_products:
            products.append({
                'id': product.product.id,
                'name': product.product.name,
            })

        packages.append({
            'id': package.id,
            'name': package.name,
            'available_products': products
        })

    return packages


@with_session
def send_agreement(session, document):
    facade = create_facade_from_send_agreement_schema(session, document)
    agreement_dict = FinancialAgreementJsonExport().entity_to_dict(facade)

    # queue = AwsQueue()
    # command = QueueCommand('import_agreement', agreement_dict)
    # queue.write_message(command)

    return None


def create_facade_from_calculate_proposal_schema(session, document):
    package = session.query(FinancialPackage).get(long(document['package_id']))

    if not package:
        raise Exception("This package does not exist")

    facade = FinancialAgreementFacade()

    # facade.agreement_date = datetime.date(2015, 3, 2)
    facade.agreement_date = datetime.date(**document['agreement_date'])
    # facade.from_date = datetime.date(2015, 3, 1)
    facade.from_date = datetime.date(**document['from_date'])

    facade.package = package

    facade.insured_party__1__birthdate = datetime.date(
        **document['insured_party__1__birthdate']
    )
    # facade.insured_party__1__birthdate = datetime.date(1980, 1, 1)
    facade.insured_party__1__sex = document['insured_party__1__sex']
    # facade.insured_party__1__sex = 'M'

    facade.premium_schedule__1__product = package.available_products[0].product

    # facade.premium_schedule__1__premium_fee_1 = D(100)
    facade.premium_schedule__1__premium_fee_1 = \
        document['premium_schedule__1__premium_fee_1']

    product_2_id = document['premium_schedule__2__product_id']
    if isinstance(product_2_id, (int, long)):
        product = session.query(FinancialProduct).get(product_2_id)
        if not product:
            raise Exception("The premium_schedule__2__product_id does not exist")

        facade.premium_schedule__2__product = product

    # facade.duration = 5*12
    facade.duration = document['duration']

    # facade.premium_schedules_coverage_limit = D('150000')
    facade.premium_schedules_coverage_limit = \
        document['premium_schedules_coverage_limit']
    # facade.premium_schedules_payment_duration = 5*12
    facade.premium_schedules_payment_duration = \
        document['premium_schedules_payment_duration']
    # facade.premium_schedules_coverage_level_type = 'fixed_amount'
    facade.premium_schedule__1__coverage_level_type = \
        document['premium_schedule__1__coverage_level_type']
    facade.premium_schedule__2__coverage_level_type = \
        document['premium_schedule__2__coverage_level_type']
    # facade.premium_schedules_premium_rate_1 = D(20)
    facade.premium_schedules_premium_rate_1 = \
        document['premium_schedules_premium_rate_1']
    # facade.premium_schedules_period_type = 'single'
    facade.premium_schedules_period_type = \
        document['premium_schedules_period_type']

    for premium_schedule in facade.invested_amounts:
        for coverage in premium_schedule.agreed_coverages:
            premium_schedule.amount = calculate_credit_insurance.calculate_premium(premium_schedule, coverage)

    facade.code = "000"

    return facade


def create_facade_from_create_agreement_schema(session, document):
    facade = create_facade_from_calculate_proposal_schema(session, document)

    FIELDS = [
        'origin',
        'pledgee_name',
        'pledgee_tax_id',
        'pledgee_reference'
    ]
    for field in FIELDS:
        setattr(facade, field, document[field])

    FIELDS = [
        'last_name', 'first_name', 'language', 'nationality_code',
        'social_security_number', 'passport_number', 'dangerous_hobby',
        'dangerous_profession', 'street_1', 'city_code', 'city_name',
        'country_code'
    ]
    for field in FIELDS:
        key = 'insured_party__1__{}'.format(field)
        setattr(facade, key, document.get(key, None))

    facade.code = FinancialAgreementFacade.next_agreement_code(session)

    facade.text = to_table_html(document)

    return facade


def create_facade_from_send_agreement_schema(session, document):
    facade = create_facade_from_create_agreement_schema(session, document)
    FIELDS = [
        'signature',
        'premium_schedule__1__amount',
        'premium_schedule__2__amount',
        'code',
    ]
    for field in FIELDS:
        setattr(facade, field, document[field])
    return facade
