# -*- coding: utf-8 -*-
import datetime
import decimal
import hashlib
import json

from sqlalchemy import orm

from vfinance.facade.financial_agreement import FinancialAgreementFacade
from vfinance.model.financial.agreement import FinancialAgreementJsonExport
from vfinance.model.financial.package import FinancialPackage
from vfinance.model.financial.product import FinancialProduct
from vfinance.model.insurance.credit_insurance import CalculateCreditInsurance
from vfinance_ws.ws.utils import with_session

import vfinance.connector.json_

calculate_credit_insurance = CalculateCreditInsurance()

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return str(o)
        return super(DecimalEncoder, self).default(o)


def fill_financial_agreement_facade(session, document):
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

    facade.code = "000"

    return facade


@with_session
def calculate_proposal(session, document):
    facade = fill_financial_agreement_facade(session, document)

    for premium_schedule in facade.invested_amounts:
        for coverage in premium_schedule.agreed_coverages:
            premium_schedule.amount = calculate_credit_insurance.calculate_premium(premium_schedule, coverage)

    orm.object_session(facade).flush()

    amount1 = str(facade.premium_schedule__1__amount)
    amount2 = str(facade.premium_schedule__2__amount) \
        if facade.premium_schedule__2__amount else None

    return {
        'premium_schedule__1__amount': amount1,
        'premium_schedule__2__amount': amount2,
    }


def to_table_html(document):
    TD_TEMPLATE = u"<td>{0}</td>"
    TR_TEMPLATE = u"<tr>{0}</tr>"
    TABLE_TEMPLATE = u"<table>{0}</table>"

    lines = []
    for k, v in document.iteritems():
        lines.append(
            TR_TEMPLATE.format(u''.join([TD_TEMPLATE.format(k),
                                         TD_TEMPLATE.format(unicode(v))]))
        )
    return TABLE_TEMPLATE.format(u''.join(lines))


@with_session
def create_agreement_code(session, document, logfile):
    facade = fill_financial_agreement_facade(session, document)

    facade.code = next_code = FinancialAgreementFacade.next_agreement_code(session)

    for premium_schedule in facade.invested_amounts:
        for coverage in premium_schedule.agreed_coverages:
            premium_schedule.amount = calculate_credit_insurance.calculate_premium(premium_schedule, coverage)

    facade.text = to_table_html(document)

    orm.object_session(facade).flush()

    dump = FinancialAgreementJsonExport().entity_to_dict(facade)
    json.dump(dump, logfile, cls=vfinance.connector.json_.ExtendedEncoder)

    amount1 = str(facade.premium_schedule__1__amount)
    amount2 = str(facade.premium_schedule__2__amount) \
        if facade.premium_schedule__2__amount else None

    values = {
        'premium_schedule__1__amount': amount1,
        'premium_schedule__2__amount': amount2,
        'code': next_code,
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
def send_agreement(session, document):

    return None