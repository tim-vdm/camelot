# -*- coding: utf-8 -*-
import hashlib
import json
from decimal import Decimal

from sqlalchemy import orm

from vfinance.connector.aws import AwsQueue
from vfinance.connector.aws import QueueCommand
from vfinance.connector.json_ import ExtendedEncoder

from vfinance.facade.agreement.credit_insurance import CreditInsuranceAgreementFacade

from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon
from vfinance.model.bank import constants
from vfinance.model.financial.agreement import (FinancialAgreementJsonExport,
                                               FinancialAgreementRole,
                                               FinancialAgreementRoleFeature)
from vfinance.model.financial.package import FinancialPackage
from vfinance.model.financial.product import FinancialProduct
from vfinance.model.hypo.hypotheek import Hypotheek
from vfinance.model.insurance.credit_insurance import CalculateCreditInsurance

from vfinance_ws.api.utils import DecimalEncoder
from vfinance_ws.api.utils import to_table_html
from vfinance_ws.ws.utils import with_session
from vfinance_ws.ws.utils import get_date_from_json_date

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
    agreement = create_agreement_from_json(session, document)

    orm.object_session(agreement).flush()
    agreement_dump = FinancialAgreementJsonExport().entity_to_dict(agreement)
    json.dump(agreement_dump, logfile, indent=4, sort_keys=True, cls=ExtendedEncoder)


    values = {'code': agreement.code}
    use_for_signature = {
        'proposal': document,
        'values': values,
    }
    
    dump = json.dumps(use_for_signature, cls=DecimalEncoder)

    signature = hashlib.sha256(dump).hexdigest()

    values['signature'] = signature
    return values

def create_agreement_from_json(session, document):
    agreement = Hypotheek()
    package = session.query(FinancialPackage).get(long(document['package_id']))
    if not package:
        raise Exception('The package with id {} does not exist'.format(document['package_id']))
    else:
        agreement.package = package
    orm.object_session(agreement).flush()

    agreement.agreement_date = get_date_from_json_date(document['agreement_date'])
    agreement.from_date = get_date_from_json_date(document['from_date'])

    for role in document['roles']:
        agreement_role = FinancialAgreementRole()
        agreement_role.described_by = role['described_by']
        agreement_role.rank = role['rank']
        agreement_role.financial_agreement = agreement
        if role['party']['row_type'] == 'person':
            natural_person = role['party']
            person = NatuurlijkePersoon()
            agreement_role.natuurlijke_persoon = person
            for attr in natural_person.keys():
                if attr.endswith('date'):
                    setattr(person, attr, get_date_from_json_date(natural_person[attr]))
                elif attr != 'row_type':
                    setattr(person, attr, natural_person[attr])
        elif role['party']['row_type'] == 'organization':
            raise Exception('An organization as party for an AgreementRole has not yet been implemented')
        for feature_name in ['net_earnings_of_employment', 'smoker']:
            feature_value = role.get(feature_name)
            if feature_value is not None:
                for feature in constants.role_features:
                    choices = feature[5]
                    if feature_name == feature[1] and choices is not None:
                        for choice in choices:
                            if choice[1] == feature_value:
                                feature_value = Decimal(choice[0])
                role_feature = FinancialAgreementRoleFeature()
                role_feature.of = agreement_role
                role_feature.value = feature_value
                role_feature.described_by = feature_name







    agreement.code = CreditInsuranceAgreementFacade.next_agreement_code(session)

    orm.object_session(agreement).flush()

    return agreement

