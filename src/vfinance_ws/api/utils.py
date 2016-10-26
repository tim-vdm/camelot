import decimal
import json

from sqlalchemy import  sql

from camelot.model.party import Country, City, Address
from camelot.model.authentication import end_of_times

from vfinance.model.bank.persoon import PersonAddress
from vfinance.model.bank import constants

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


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return str(o)
        return super(DecimalEncoder, self).default(o)
    
    
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