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

@with_session
def ci_create_agreement_code(session, document, logfile):
    facade = create_facade_from_create_agreement_schema(session, document)

    orm.object_session(facade).flush()

    dump = FinancialAgreementJsonExport().entity_to_dict(facade)
    json.dump(dump, logfile, indent=4, sort_keys=True, cls=ExtendedEncoder)

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
def create_agreement_code(session, document, logfile):
    values = {'code': '000/0000/00000'}
    use_for_signature = {
        'proposal': document,
        'values': values,
    }
    json.dump(document, logfile, indent=4, sort_keys=True, cls=ExtendedEncoder)

    dump = json.dumps(use_for_signature, cls=DecimalEncoder)

    signature = hashlib.sha256(dump).hexdigest()

    values['signature'] = signature
    return values

