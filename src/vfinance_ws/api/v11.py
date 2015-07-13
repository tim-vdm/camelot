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
from vfinance.model.bank.varia import Country_
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
import wingdbstub

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
    field_mappings = {'passport_number': 'identiteitskaart_nummer',
                      'marital_status': 'burgerlijke_staat',
                      'marital_status_since': 'burgerlijke_staat_sinds',
                      'marital_contract': 'huwelijkscontract',
                      'passport_expiry_date': 'identiteitskaart_datum',
                      'activity': 'aktiviteit',
                      'activity_since': 'aktiviteit_sinds',
                      'tax_id': 'tax_number',
                      'personal_title': 'titel',
                      'company_name': 'werkgever',
                      'company_since': 'werkgever_sinds',
                      'occupation': 'beroep'}
    agreement = Hypotheek()
    package = session.query(FinancialPackage).get(long(document['package_id']))
    if not package:
        raise Exception('The package with id {} does not exist'.format(document['package_id']))
    else:
        agreement.package = package
    orm.object_session(agreement).flush()

    agreement.origin = document.get('origin')
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

            # Loop the addresses
            addresses = natural_person['addresses']
            for address in addresses:
                address_type = address['described_by']
                if address_type is not None and address_type == 'domicile':
                    person.street = address['street_1']
                    person.postcode = address['zip_code']
                    person.gemeente = address['city']
                    person.country_code = address['country_code']
                elif address_type is not None and address_type == 'correspondence':
                    person.correspondentie_straat = address['street_1']
                    person.correspondentie_postcode = address['zip_code']
                    person.correspondentie_gemeente = address['city']
                    country = session.query(Country_).filter(Country_.code == address['country_code']).first()
                    person.correspondentie_land = country

            # Loop the contactmechanisms
            contact_mechanisms = natural_person['contact_mechanisms']
            for contact_mechanism in contact_mechanisms:
                described_by = contact_mechanism['described_by']
                value = contact_mechanism['contact_mechanism']
                if described_by == 'fax':
                    person.fax = value
                elif described_by == 'mobile':
                    person.gsm = value
                elif described_by == 'email':
                    person.email = value
                elif described_by == 'phone':
                    address_type = contact_mechanism.get('address_type')
                    if address_type is not None and address_type == 'domicile':
                        person.telefoon = value
                    else:
                        person.telefoon_werk = value

            for attr in natural_person.keys():
                value = None
                attrib = attr


                if attr.endswith('date') or attr.endswith('since'):
                    value = get_date_from_json_date(natural_person[attr])
                else:
                    value = natural_person[attr]

                if attr in field_mappings.keys():
                    attrib = field_mappings.get(attr)

                if attr not in ('row_type'):
                    setattr(person, attrib, value)

        elif role['party']['row_type'] == 'organization':
            raise Exception('An organization as party for an AgreementRole has not yet been implemented')
        for feature_name in constants.role_feature_names:
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

