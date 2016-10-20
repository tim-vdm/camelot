# -*- coding: utf-8 -*-
import hashlib
import json
import re
import os
from decimal import Decimal
import datetime
from stdnum import iban
from flask import send_file
from pkg_resources import resource_stream

from stdnum.exceptions import InvalidChecksum, InvalidFormat

from sqlalchemy import orm, sql
from camelot.core.exception import UserException
from camelot.core.utils import ugettext
from camelot.core.templates import environment

from camelot.model.party import Country, City, Address
from camelot.model.authentication import end_of_times

from vfinance.connector.json_ import ExtendedEncoder, FinancialAgreementJsonExport

from vfinance.data.types import role_feature_types

from vfinance.facade.agreement.credit_insurance import CreditInsuranceAgreementFacade

from vfinance.admin.translations import TemplateLanguage
from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon
from vfinance.model.bank import constants
from vfinance.model.bank.rechtspersoon import Rechtspersoon
from vfinance.model.bank.dual_person import CommercialRelation
from vfinance.model.bank.validation import iban_regexp, bic_regexp
from vfinance.model.financial.agreement import (FinancialAgreement,
                                               FinancialAgreementRole,
                                               FinancialAgreementRoleFeature,
                                               FinancialAgreementFunctionalSettingAgreement,
                                               InsuredLoanAgreement,
                                               FinancialAgreementItem)
from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
from vfinance.model.financial.package import FinancialPackage, FinancialItemClause
from vfinance.model.financial.product import FinancialProduct
from vfinance.model.financial.feature import FinancialAgreementPremiumScheduleFeature
from vfinance.model.financial.constants import exclusiveness_by_functional_setting_group
from vfinance.model.financial.notification.agreement_document import AgreementDocument
from vfinance.facade.agreement.credit_insurance import CalculatePremium
from vfinance.model.bank.product import Product
from vfinance.model.bank.persoon import PersonAddress
from vfinance.model.bank.direct_debit import DirectDebitMandate
from vfinance.model.bank.constants import get_interface_value_from_model_value, get_model_value_from_interface_value
from vfinance.model.hypo.hypotheek import Hypotheek, TeHypothekerenGoed, EigenaarGoed, GoedAanvraag, Bedrag

from vfinance_ws.api.utils import DecimalEncoder
from vfinance_ws.api.utils import to_table_html
from vfinance_ws.ws.utils import with_session
from vfinance_ws.ws.utils import get_date_from_json_date
from vfinance_ws.api.v01 import create_facade_from_create_agreement_schema as create_facade_from_create_agreement_schema_v01


calculate_credit_insurance = CalculatePremium()

@with_session
def ci_create_agreement_code(session, document, logfile):
    facade = create_facade_from_create_agreement_schema_v01(session, document)

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

def make_address(address, session):
    new_address = None
    address_zipcode = address['zip_code']
    address_city_name = address['city']
    address_country = session.query(Country).filter(Country.code == address['country_code']).first()
    if address_zipcode is not None and address_city_name is not None and address_country is not None:
        address_city = session.query(City).filter(sql.and_(City.code == address_zipcode.strip(),
                                                           City.country == address_country,
                                                           City.name == address_city_name.strip())).first()
        if address_city is None:
            address_city = City()
            address_city.country = address_country
            address_city.name = address_city_name
            address_city.code = address_zipcode

        new_address = Address()
        new_address.street1 = address['street_1']
        new_address.city = address_city

    return new_address

def make_person_address(address, session):
    new_addres = None
    address_ = make_address(address, session)
    if address is not None:
        address_type = address['described_by']
        if address_type == 'official':
            address_type = 'domicile'
        new_address = PersonAddress()
        new_address.address = address_
        new_address.described_by = address_type
        new_address.from_date = constants.begin_of_times
        new_address.thru_date = end_of_times()

    return new_address

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
    agreement = None
    agreement_type = document.get('row_type')
    if agreement_type == 'financial_agreement':
        agreement = FinancialAgreement()
    else:
        agreement = Hypotheek()
    package = session.query(FinancialPackage).get(long(document['package_id']))
    agreement.code = agreement.next_agreement_code(package, session)
    if not package:
        raise Exception('The package with id {} does not exist'.format(document['package_id']))
    else:
        agreement.package = package
    #orm.object_session(agreement).flush()

    origin = document.get('origin')
    agreement.origin = origin
    agreement.agreement_date = get_date_from_json_date(document['agreement_date'])
    agreement.from_date = get_date_from_json_date(document['from_date'])

    agreement_assets = document.get('assets')
    goed = None
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
            goed.address = make_address(asset['address'], session)
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
        agreement_role = None
        role_type = role['described_by']

        if role['party']['row_type'] == 'person':
            natural_person = role['party']
            person = NatuurlijkePersoon()
            person.origin = origin

            # Loop the addresses
            addresses = natural_person['addresses']
            for address in addresses:
                new_address = make_person_address(address, session)
                person.addresses.append(new_address)

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
                    
                if attr == 'place_of_birth':
                    place = natural_person[attr]
                    if place is not None:
                        country_code = place.get('country_code')
                        country = session.query(Country).filter(Country.code==country_code).first()
                        zip_code = place.get('zip_code')
                        city = place.get('city')
                        if city is not None and zip_code is not None:
                            birthplace = session.query(City).filter(sql.and_(City.code==zip_code,
                                                                             City.country==country,
                                                                             City.name==city)).first()
                            if birthplace is None:
                                birthplace = City(country=country, code=zip_code, name=city)
                        elif country is not None:
                            birthplace = country
                                
                    value = birthplace
                    


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

                if attr not in ('row_type', 'addresses'):
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
            rechtspersoon.origin = origin
            organization = role['party']
            # Loop the addresses
            addresses = organization.get('addresses')
            if addresses is not None:
                for address in addresses:
                    address_type = address['described_by']
                    if address_type is not None:
                        new_address = make_person_address(address, session)
                        new_address.organization = rechtspersoon
                        #rechtspersoon.addresses.append = new_address
            #representative = organization.get('representative')
            #if representative is not None:
            #    vertegenwoordiger = create_natural_person_from_party(representative)
            #    rechtspersoon.vertegenwoordiger = vertegenwoordiger
            rechtspersoon.name = organization['name']
            rechtspersoon.ondernemingsnummer = organization['tax_id']
            contact_mechanisms = organization.get('contact_mechanisms', [])
            for contact_mechanism in contact_mechanisms:
                described_by = contact_mechanism['described_by']
                value = contact_mechanism['contact_mechanism']
                if described_by == 'fax':
                    rechtspersoon.fax = value
                elif described_by == 'mobile':
                    rechtspersoon.gsm = value
                elif described_by == 'email':
                    rechtspersoon.email = value
                elif described_by == 'phone':
                    rechtspersoon.telefoon = value
            if role_type == 'appraiser' and goed is not None:
                goed.schatter = rechtspersoon
            else:
                agreement_role = FinancialAgreementRole()
                agreement_role.described_by = role_type
                agreement_role.rank = role['rank']
                agreement_role.financial_agreement = agreement
                agreement_role.rechtspersoon = rechtspersoon

        if agreement_role is not None:
            date_previous_disability = role.get('date_previous_disability')
            agreement_role.reference = role.get('reference')
            if date_previous_disability is not None:
                agreement_role.date_previous_disability = datetime.date(**date_previous_disability)
            date_previous_medical_procedure = role.get('date_previous_medical_procedure')
            if date_previous_medical_procedure is not None:
                agreement_role.date_previous_medical_procedure = datetime.date(**date_previous_medical_procedure)
            for feature_name in constants.role_feature_names:
                feature_value = role.get(feature_name)
                feature_reference_value = role.get(feature_name + '_reference')
                # If role is not mapped to a FinancialAgreementRole, no FinancialAgreementRoleFeatures should be created
                #if feature_value is not None:
                if feature_value is not None and role_type not in ('appraiser', 'owner', 'non_usufruct_owner', 'owner_usufruct'):
                    for feature in role_feature_types:
                        choices = feature.values
                        if feature_name == feature.name and choices is not None:
                            for choice in choices:
                                if choice[2] == feature_value:
                                    feature_value = choice[0]
                    role_feature = FinancialAgreementRoleFeature()
                    role_feature.of = agreement_role
                    role_feature.value = Decimal(feature_value)
                    role_feature.reference = feature_reference_value
                    role_feature.described_by = feature_name



    schedules = document.get('schedules')
    aankoopprijs = Decimal(0.0)
    bestek_bouwwerken = Decimal(0.0)
    te_betalen_btw = Decimal(0.0)
    notariskosten_hypotheek = Decimal(0.0)
    notariskosten_aankoopakte = Decimal(0.0)
    ereloon_architect = Decimal(0.0)
    verzekeringskosten = Decimal(0.0)
    eigen_middelen = Decimal(0.0)
    andere_kosten = Decimal(0.0)
    if schedules is not None:
        aflossing_field_mapping = {'fixed_payment': 'vaste_aflossing',
                                   'fixed_capital_payment': 'vast_kapitaal'}
        interval_field_mapping = {'yearly': 12,
                                  'semesterly': 6,
                                  'quarterly': 3,
                                  'monthly': 1}
        hypo_interval_field_mapping = {'monthly': 12,
                                       'quarterly': 4,
                                       'yearly': 1}
        doel_field_mapping = {'purchase_terrain': 'doel_aankoop_terrein',
                              'new_housing': 'doel_nieuwbouw',
                              'renovation': 'doel_renovatie',
                              'refinancing': 'doel_herfinanciering',
                              'centralization': 'doel_centralisatie',
                              'building_purchase': {'vat': 'doel_aankoop_gebouw_btw',
                                                    'registration_fee': 'doel_aankoop_gebouw_registratie'},
                              'bridging_credit': 'doel_overbrugging'}
        aankoop = ['building_purchase', 'purchase_terrain']
        bouwwerken = ['renovation', 'new_housing']
        verzekeringen = ['homeowners_insurance', 'mortgage_insurance', 'life_insurance']
        insured_loans = {}

        for schedule in [sch for sch in schedules if sch.get('row_type') == 'approved_amount']:
            insured_loan = InsuredLoanAgreement()
            insured_loan.loan_amount = schedule.get('amount')
            insured_loan.interest_rate = schedule.get('initial_interest_rate')
            insured_loan.number_of_months = schedule.get('duration')
            insured_loan.type_of_payments = aflossing_field_mapping.get(schedule.get('described_by'))
            insured_loan.payment_interval = interval_field_mapping.get(schedule.get('period_type'))
            insured_loans[schedule.get('id')] = insured_loan


        for schedule in [sch for sch in schedules if sch.get('row_type') != 'approved_amount']:
            insured_loan = None
            product = session.query(Product).get(long(schedule.get('product_id')))
            insured_loan = insured_loans.get(schedule.get('for_id'))
            period_type = schedule.get('period_type')
            duration = schedule.get('duration')
            amount = schedule.get('amount')
            direct_debit = schedule.get('direct_debit')
            schedule_type = schedule.get('row_type')
            payment_duration = schedule.get('payment_duration')
            if schedule_type == 'premium_amount':
                coverage_level_json = schedule.get('coverage_for')
                coverage_level = None
                if coverage_level_json is not None:
                    for cl in product.get_available_coverage_levels_at(agreement.from_date):
                        if cl.type == coverage_level_json:
                            coverage_level = cl
                            break
                    else:
                        raise UserException('Coverage of type {} is not available'.format(coverage_level_json))
                premium_schedule = FinancialAgreementPremiumSchedule()
                premium_schedule.product = product
                premium_schedule.amount = amount
                premium_schedule.duration = duration
                premium_schedule.payment_duration = payment_duration
                premium_schedule.period_type = period_type
                premium_schedule.direct_debit = direct_debit
                premium_schedule.insured_from_date = get_date_from_json_date(schedule.get('insured_from_date'))
                premium_schedule.insured_duration = schedule.get('insured_duration')
                premium_schedule.coverage_for = coverage_level
                premium_schedule.financial_agreement = agreement
                premium_schedule.coverage_amortization = insured_loan
                for feature_name in [insurance_feature[1] for insurance_feature in constants.insurance_features]:
                    feature_value = schedule.get(feature_name)
                    if feature_value is not None:
                        agreed_feature = FinancialAgreementPremiumScheduleFeature()
                        agreed_feature.described_by = feature_name
                        agreed_feature.value = Decimal(feature_value)
                        agreed_feature.agreed_on = premium_schedule
            elif schedule_type == 'applied_amount':
                bedrag = Bedrag()

                # Should be decided by the product or the package?
                type_vervaldag = 'akte'

                bedrag.product = product
                bedrag.type_vervaldag = type_vervaldag
                bedrag.type_aflossing = aflossing_field_mapping.get(schedule.get('described_by'))
                bedrag.terugbetaling_interval = hypo_interval_field_mapping.get(period_type)
                bedrag.looptijd = duration
                bedrag.bedrag = amount
                bedrag.terugbetaling_start = schedule.get('suspension_of_payment', 0)
                for field in doel_field_mapping:
                    if field == 'building_purchase':
                        if schedule.get('vat'):
                            fieldname = doel_field_mapping[field].get('vat')
                        elif schedule.get('registration_fee'):
                            fieldname = doel_field_mapping[field].get('registration_fee')
                    else:
                        fieldname = doel_field_mapping[field]
                    setattr(bedrag, fieldname, bool(Decimal(schedule.get(field, 0.0))))

                for field in aankoop:
                    aankoopprijs += Decimal(schedule.get(field, 0.0))
                for field in bouwwerken:
                    bestek_bouwwerken += Decimal(schedule.get(field, 0.0))
                for field in verzekeringen:
                    verzekeringskosten += Decimal(schedule.get(field, 0.0))

                te_betalen_btw += Decimal(schedule.get('vat', 0.0))
                notariskosten_hypotheek += Decimal(schedule.get('signing_agent_mortgage', 0.0))
                notariskosten_aankoopakte += Decimal(schedule.get('signing_agent_purchase', 0.0))
                notariskosten_aankoopakte += Decimal(schedule.get('registration_fee', 0.0))
                ereloon_architect += Decimal(schedule.get('architect_fee', 0.0))
                eigen_middelen += Decimal(schedule.get('down_payment', 0.0))
                andere_kosten += Decimal(schedule.get('other_costs', 0.0))

                bedrag.financial_agreement = agreement



    agreement.aankoopprijs = aankoopprijs
    agreement.kosten_bouwwerken = bestek_bouwwerken
    agreement.kosten_verzekering = verzekeringskosten
    agreement.kosten_btw = te_betalen_btw
    agreement.notariskosten_hypotheek = notariskosten_hypotheek
    agreement.notariskosten_aankoop = notariskosten_aankoopakte
    agreement.kosten_architect = ereloon_architect
    agreement.eigen_middelen = eigen_middelen
    agreement.kosten_andere = andere_kosten

    for functional_setting_group in [group for group in exclusiveness_by_functional_setting_group if exclusiveness_by_functional_setting_group.get(group) == True]:
        value = document.get(functional_setting_group)
        if value is not None:
            functional_setting = FinancialAgreementFunctionalSettingAgreement()
            functional_setting.described_by = value
            functional_setting.agreed_on = agreement



    bank_accounts = document.get('bank_accounts')
    if bank_accounts is not None:
        for bank_account in [account for account in bank_accounts if account.get('row_type') == 'direct_debit']:
            iban_number = bank_account.get('iban')
            try:
                iban_number = iban.validate(iban_number)
            except (InvalidChecksum, InvalidFormat):
                raise UserException('IBAN \'{}\' is not valid.'.format(iban_number))

            bic = bank_account.get('bic')
            if iban_number is not None:
                if iban_regexp.match(iban_number.replace(' ', '')) is None:
                    raise UserException('IBAN \'{}\' is not valid.'.format(iban_number))
                iban_number = iban.format(iban_number)
                mandate = DirectDebitMandate()
                mandate.agreement = agreement
                mandate.identification = agreement.code
                mandate.date = agreement.agreement_date
                mandate.from_date = agreement.agreement_date
                mandate.iban = iban_number
                if bic is not None:
                    if bic_regexp.match(bic) is None:
                        raise UserException('BIC \'{}\' is not valid'.format(bic))
                    if mandate.bank_identifier_code is not None and mandate.bank_identifier_code != bic:
                        raise UserException('BIC \'{}\' is not valid for iban {}'.format(iban_number, bic))
                    mandate.bank_identifier_code = bic
                agreement.direct_debit_mandates.append(mandate)

    agreed_items = document.get('agreed_items')
    if agreed_items is not None:
        for agreed_item in agreed_items:
            agreement_item = FinancialAgreementItem()
            agreement_item.described_by = agreed_item.get('described_by')
            agreement_item.rank = agreed_item.get('rank')
            agreement_item.associated_clause = orm.object_session(agreement).query(FinancialItemClause).get(agreed_item.get('associated_clause_id'))
            custom_clause = agreed_item.get('custom_clause')
            if custom_clause is not None:
                agreement_item.use_custom_clause = True
                agreement_item.custom_clause = custom_clause

            agreement.agreed_items.append(agreement_item)



    orm.object_session(agreement).flush()

    return agreement

@with_session
def calculate_proposal(session, document):
    facade = create_facade_from_calculate_proposal_schema(session, document)


    amount1 = str(facade.premium_schedule__1__amount)
    amount2 = str(facade.premium_schedule__2__amount) \
        if facade.premium_schedule__2__amount else None
    payment_thru_date1 = {"year": facade.premium_schedule__1__payment_thru_date.year,
                          "month": facade.premium_schedule__1__payment_thru_date.month,
                          "day": facade.premium_schedule__1__payment_thru_date.day}
    payment_thru_date2 = {"year": facade.premium_schedule__2__payment_thru_date.year,
                          "month": facade.premium_schedule__2__payment_thru_date.month,
                          "day": facade.premium_schedule__2__payment_thru_date.day} \
        if facade.premium_schedule__2__payment_thru_date else None
    premium_period_type1 = facade.premium_schedule__1__period_type
    premium_period_type2 = facade.premium_schedule__2__period_type \
        if facade.premium_schedule__2__period_type else None

    session.expunge(facade)

    for message in facade.get_messages(proposal_mode=True):
        raise UserException(message)


    return {
        'premium_schedule__1__amount': amount1,
        'premium_schedule__2__amount': amount2,
        'premium_schedule__1__payment_thru_date': payment_thru_date1,
        'premium_schedule__2__payment_thru_date': payment_thru_date2,
        'premium_schedule__1__period_type': premium_period_type1,
        'premium_schedule__2__period_type': premium_period_type2
    }

@with_session
def get_proposal(session, document):
    facade = create_facade_from_calculate_proposal_schema(session, document)
    facade.insured_party__1__first_name = document.get('insured_party__1__first_name')
    facade.insured_party__1__last_name = document.get('insured_party__1__last_name')
    facade.insured_party__1__language = document.get('insured_party__1__language')
    facade.agreed_functional_settings.append(FinancialAgreementFunctionalSettingAgreement(described_by='exit_at_first_decease'))
    broker = CommercialRelation()
    broker.from_rechtspersoon = Rechtspersoon()
    broker.from_rechtspersoon.name = document.get('broker__name')
    broker.from_rechtspersoon.email = document.get('broker__email')
    address = make_person_address({'zip_code':document.get('broker__zip_code',''),
                                   'city':document.get('broker__city',''),
                                   'country_code':'BE',
                                   'street_1':document.get('broker__street',),
                                   'described_by':'domicile'}, session)
    broker.from_rechtspersoon.addresses.append(address)
    broker.from_rechtspersoon.telefoon = document.get('broker__telephone')
    facade.broker_relation = broker
    options = None
    language = document.get('insured_party__1__language')
    package = facade.package

    html = None

    with TemplateLanguage(language=language):
        facade_context = AgreementDocument().context(facade, None, options)
        template = environment.get_template('notifications/Select_Plus/agreement-proposal_{}.html'.format(language))
        html = template.render(facade_context)

    return html

def create_facade_from_calculate_proposal_schema(session, document):
    package = session.query(FinancialPackage).get(long(document['package_id']))

    if not package:
        raise Exception("This package does not exist")

    facade = CreditInsuranceAgreementFacade()

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

    product_2_id = document.get('premium_schedule__2__product_id')
    if isinstance(product_2_id, (int, long)):
        product = session.query(FinancialProduct).get(product_2_id)
        if not product:
            raise Exception("The premium_schedule__2__product_id does not exist")

        facade.premium_schedule__2__product = product

    # facade.duration = 5*12
    facade.duration = document.get('duration')

    # facade.premium_schedules_coverage_limit = D('150000')
    facade.premium_schedules_coverage_limit = \
        document.get('premium_schedules_coverage_limit')
    # facade.premium_schedules_payment_duration = 5*12
    facade.premium_schedules_payment_duration = \
        document.get('premium_schedules_payment_duration', None)
    # facade.premium_schedules_coverage_level_type = 'fixed_amount'
    facade.premium_schedule__1__coverage_level_type = \
        document.get('premium_schedule__1__coverage_level_type')
    facade.premium_schedule__2__coverage_level_type = \
        document.get('premium_schedule__2__coverage_level_type')
    # facade.premium_schedules_premium_rate_1 = D(20)
    facade.premium_schedules_premium_rate_1 = \
        document.get('premium_schedules_premium_rate_1')
    # facade.premium_schedules_period_type = 'single'
    facade.premium_schedules_period_type = \
        document.get('premium_schedules_period_type')

    # New fields for select+
    facade.insured_party__1__educational_level = \
        get_model_value_from_interface_value('educational_level', document.get('insured_party__1__educational_level'))
    facade.insured_party__1__net_earnings_of_employment = \
        document.get('insured_party__1__net_earnings_of_employment')
    facade.insured_party__1__fitness_level = \
        get_model_value_from_interface_value('fitness_level', document.get('insured_party__1__fitness_level'))
    facade.insured_party__1__smoking_habit = \
        get_model_value_from_interface_value('smoking_habit', document.get('insured_party__1__smoking_habit'))
    facade.premium_schedule__1__premium_taxation_physical_person = \
        document.get('premium_schedule__1__premium_taxation_physical_person')
    facade.loan_type_of_payments = \
        document.get('loan_type_of_payments')
    facade.loan_interest_rate = \
        document.get('loan_interest_rate')
    facade.loan_loan_amount = \
        document.get('loan_loan_amount')

    calculate_fictitious_extra_age(facade)

    calculate_credit_insurance.calculate(facade)

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
    facade.pledgee__1__rechtspersoon = Rechtspersoon()
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

    facade.code = CreditInsuranceAgreementFacade.next_agreement_code(facade.package, session)

    facade.text = to_table_html(document)

    return facade

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
    #agreement_dict = FinancialAgreementJsonExport().entity_to_dict(facade)
    FinancialAgreementJsonExport().entity_to_dict(facade)

    # queue = AwsQueue()
    # command = QueueCommand('import_agreement', agreement_dict)
    # queue.write_message(command)

    return None

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

extra_age_table = {'educational_level':
                        {'no_schooling': 3,
                         'incomplete_primary': 3,
                         'primary': 3,
                         'lower_secondary': 2,
                         'upper_secondary': 1,
                         'post_secondary': 1,
                         'first_stage_tertiary': -1,
                         'second_stage_tertiary': -1,
                         },
                   'fitness_level':
                        {'extremely_inactive': 0,
                         'sedentary': 0,
                         'moderately_active': -1,
                         'vigorously_active': -1,
                         'extremely_active': -1},
                   'smoking_habit':
                         {'never': 0,
                          'regular': 5},
                   }

def calculate_fictitious_extra_age(agreement):
    if agreement.package is not None:
        if agreement.package.id == 65:
            years = []
            for key in extra_age_table.keys():
                value = get_interface_value_from_model_value(key, getattr(agreement, 'insured_party__1__{}'.format(key)))
                years.append(extra_age_table[key].get(value, 0))
            earnings = agreement.insured_party__1__net_earnings_of_employment
            if earnings <= 500:
                years.append(3)
            elif earnings <= 1200:
                years.append(2)
            elif earnings <= 1700:
                years.append(1)
            else:
                years.append(0)
            agreement.premium_schedule__1__insurance_fictitious_extra_age = \
                sum(years) * 365

