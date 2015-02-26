# -*- coding: utf-8 -*-
import datetime
import hashlib

from sqlalchemy.engine import create_engine
from camelot.core.conf import settings
from camelot.core.orm import Session
from camelot.core.sql import metadata

from vfinance.model.bank.settings import SettingsProxy
from vfinance.utils import setup_model as setup_vfinance_model
from vfinance.model.financial.package import FinancialPackage
from vfinance.facade.financial_agreement import FinancialAgreementFacade


def calculate_proposal(proposal):

    settings.append(SettingsProxy(None))

    db_filename = '/home/stephane/vfinance_26022015/src/packages.db'

    engine = create_engine('sqlite:///'+db_filename)

    metadata.bind = engine

    setup_vfinance_model(update=False, templates=False)

    session = Session()

    package = session.query(FinancialPackage).get(long(proposal['package_id']))
    if not package:
        raise Exception("This package does not exist")

    facade = FinancialAgreementFacade()

    # facade.agreement_date = datetime.date(2015, 3, 2)
    facade.agreement_date = datetime.date(**proposal['agreement_date'])
    # facade.from_date = datetime.date(2015, 3, 1)
    facade.from_date = datetime.date(**proposal['from_date'])

    facade.package = package

    facade.insured_party__1__birthdate = datetime.date(
        **proposal['insured_party__1__birthdate']
    )
    # facade.insured_party__1__birthdate = datetime.date(1980, 1, 1)
    facade.insured_party__1__sex = proposal['insured_party__1__sex']
    # facade.insured_party__1__sex = 'M'

    facade.premium_schedule__1__product = package.available_products[0].product
    # facade.premium_schedule__1__premium_fee_1 = D(100)
    facade.premium_schedule__1__premium_fee_1 = \
        proposal['premium_schedule__1__premium_fee_1']

    # facade.duration = 5*12
    facade.duration = proposal['duration']

    # facade.premium_schedules_coverage_limit = D('150000')
    facade.premium_schedules_coverage_limit = \
        proposal['premium_schedules_coverage_limit']
    # facade.premium_schedules_payment_duration = 5*12
    facade.premium_schedules_payment_duration = \
        proposal['premium_schedules_payment_duration']
    # facade.premium_schedules_coverage_level_type = 'fixed_amount'
    facade.premium_schedules_coverage_level_type = \
        proposal['premium_schedules_coverage_level_type']
    # facade.premium_schedules_premium_rate_1 = D(20)
    facade.premium_schedules_premium_rate_1 = \
        proposal['premium_schedules_premium_rate_1']
    # facade.premium_schedules_period_type = 'single'
    facade.premium_schedules_period_type = \
        proposal['premium_schedules_period_type']

    facade.update_premium()

    amount1 = str(facade.premium_schedule__1__amount)
    amount2 = str(facade.premium_schedule__2__amount) \
        if facade.premium_schedule__2__amount else None

    return {
        'premium_schedule__1__amount': amount1,
        'premium_schedule__2__amount': amount2,
    }


def create_agreement_code(proposal):
    amounts = calculate_proposal(proposal)
    signature = hashlib.sha256(str(datetime.datetime.now())).hexdigest()[32:]
    values = {
        'code': "000/0000/00000",
        'signature': signature,
    }

    values.update(amounts)

    return values
