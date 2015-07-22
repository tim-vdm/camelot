# -*- coding: utf-8 -*-
import hashlib
import json
from decimal import Decimal

from sqlalchemy import orm

from vfinance.connector.aws import AwsQueue
from vfinance.connector.aws import QueueCommand
from vfinance.connector.json_ import ExtendedEncoder

from vfinance.facade.agreement.credit_insurance import CreditInsuranceAgreementFacade

from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon, burgerlijke_staten
from vfinance.model.bank import constants
from vfinance.model.bank.varia import Country_
from vfinance.model.bank.rechtspersoon import Rechtspersoon
from vfinance.model.financial.agreement import (FinancialAgreementJsonExport,
                                               FinancialAgreementRole,
                                               FinancialAgreementRoleFeature)
from vfinance.model.financial.package import FinancialPackage
from vfinance.model.financial.product import FinancialProduct
from vfinance.model.hypo.hypotheek import Hypotheek, TeHypothekerenGoed, EigenaarGoed, GoedAanvraag
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
    assets = []
    agreement = Hypotheek()
    package = session.query(FinancialPackage).get(long(document['package_id']))
    if not package:
        raise Exception('The package with id {} does not exist'.format(document['package_id']))
    else:
        agreement.package = package
    #orm.object_session(agreement).flush()

    agreement.origin = document.get('origin')
    agreement.agreement_date = get_date_from_json_date(document['agreement_date'])
    agreement.from_date = get_date_from_json_date(document['from_date'])

    agreement_assets = document.get('assets')
    if agreement_assets is not None:
        for agreement_asset in agreement_assets:
            goed = TeHypothekerenGoed()
            goed_aanvraag = GoedAanvraag()
            goed_aanvraag.te_hypothekeren_goed = goed
            goed_aanvraag.financial_agreement = agreement
            goed_aanvraag.hypothecaire_inschrijving = agreement_asset.get('lien_amount')
            goed_aanvraag.hypothecair_mandaat = agreement_asset.get('conditional_lien_amount')
            goed_aanvraag.prijs_grond = agreement_asset.get('building_lot_price')
            goed_aanvraag.waarde_voor_werken = agreement_asset.get('initial_value')
            goed_aanvraag.waarde_verhoging = agreement_asset.get('added_value')

            goed.kadaster = agreement_asset.get('building_log_number')
            goed.venale_verkoopwaarde = agreement_asset.get('appraised_value')
            goed.vrijwillige_verkoop = agreement_asset.get('selling_value')
            goed.gedwongen_verkoop = agreement_asset.get('forced_selling_value')
            goed.bewoonbare_oppervlakte = agreement_asset.get('habitable_area')
            goed.straat_breedte_gevel = agreement_asset.get('housefront_width')
            goed.straat_breedte_grond = agreement_asset.get('building_lot_width')
            goed.huurwaarde = agreement_asset.get('rental_revenues')

            asset = agreement_asset['asset']
            id = asset['id']
            address = asset['address']
            goed.straat = address['street_1']
            goed.postcode = address['zip_code']
            goed.gemeente = address['city']
            mapping = {'building_lot': 'bouwgrond',
                       'condominium': 'appartement',
                       'attached': 'rijwoning',
                       'semi_detached': 'half_open',
                       'detached': 'villa',
                       'bungalow': 'bungalow',
                       'commercial_building': 'handelspand',
                       'castle': 'kasteel'}
            goed.type = mapping.get(asset['described_by'])
            assets.append({'id': id,
                           'asset': goed})


    for role in document['roles']:
        role_type = role['described_by']

        if role['party']['row_type'] == 'person':
            natural_person = role['party']
            person = NatuurlijkePersoon()

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


                if attr == 'marital_status':
                    val = natural_person[attr]
                    mapping = {'single': 'o',
                               'cohabited': 's',
                               'legally_cohabited': 'ows',
                               'married': 'h',
                               'divorced': 'g',
                               'widowed': 'w',
                               'legally_separated': 'f'}
                    value = mapping.get(val)

                if attr == 'marital_contract':
                    val = natural_person[attr]
                    mapping = {'none': 'geen',
                               'community_of_goods': 'gemeenschap',
                               'separation_of_goods': 'scheiding',
                               'separation_of_goods_community_of_acquisitions': 'scheiding_aanwinsten'}
                    value = mapping.get(val)

                if attr == 'occupation':
                    val = natural_person[attr]
                    mapping = {'labourer': 'arbeider',
                               'clerk': 'bediende',
                               'self_employed': 'zelfstandige',
                               'retiree': 'gepensioneerde',
                               'job-seeker': 'werkzoekende',
                               'housewife': 'huisvrouw',
                               'disabled': 'arbeidsonbekwaam',
                               'manager': 'bedrijfsleider'}
                    value = mapping.get(val)

                if attr == 'language':
                    value = natural_person[attr][:2]

                if attr in field_mappings.keys():
                    attrib = field_mappings.get(attr)

                if attr not in ('row_type'):
                    setattr(person, attrib, value)

            if role_type in ('owner', 'non_usufruct_owner', 'owner_usufruct'):
                eigenaar = EigenaarGoed()
                for asset in assets:
                    if asset['id'] == role['asset_id']:
                        owned_asset = asset['asset']
                        eigenaar.percentage = Decimal(role['asset_ownership_percentage'])
                        eigenaar.te_hypothekeren_goed_id = owned_asset
                        eigenaar.natuurlijke_persoon = person
                        if role_type == 'owner':
                            eigenaar.type = 'volle_eigendom'
                        elif role_type == 'non_usufruct_owner':
                            eigenaar.type = 'naakte_eigendom'
                        else:
                            eigenaar.type = 'vruchtgebruik'

            else:
                agreement_role = FinancialAgreementRole()
                agreement_role.described_by = role_type
                agreement_role.rank = role['rank']
                agreement_role.financial_agreement = agreement
                agreement_role.natuurlijke_persoon = person

        elif role['party']['row_type'] == 'organization':
            rechtspersoon = Rechtspersoon()
            organization = role['party']
            #representative = organization.get('representative')
            #if representative is not None:
            #    vertegenwoordiger = create_natural_person_from_party(representative)
            #    rechtspersoon.vertegenwoordiger = vertegenwoordiger
            rechtspersoon.name = organization['name']
            rechtspersoon.ondernemingsnummer = organization['tax_id']
            if role_type == 'appraiser':
                goed.schatter = rechtspersoon
            else:
                agreement_role = FinancialAgreementRole()
                agreement_role.described_by = role_type
                agreement_role.rank = role['rank']
                agreement_role.financial_agreement = agreement
                agreement_role.rechtspersoon = rechtspersoon

        for feature_name in constants.role_feature_names:
            feature_value = role.get(feature_name)
            if feature_value is not None:
                for feature in constants.role_features:
                    choices = feature[5]
                    if feature_name == feature[1] and choices is not None:
                        for choice in choices:
                            if choice[1] == feature_value:
                                feature_value = choice[0]
                role_feature = FinancialAgreementRoleFeature()
                role_feature.of = agreement_role
                role_feature.value = Decimal(feature_value)
                role_feature.described_by = feature_name








    agreement.code = CreditInsuranceAgreementFacade.next_agreement_code(session)

    orm.object_session(agreement).flush()

    return agreement

