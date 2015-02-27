from collections import namedtuple

AdresseeOrganization = namedtuple('AddresseeOrganization', ['name'])
AddresseePerson = namedtuple('AddresseeName', ['first_name',
                                               'middle_name',
                                               'last_name',
                                               'personal_title',
                                               'suffix'])
Addressee = namedtuple('Addressee', ['organization',
                                     'persons',
                                     'street1', 
                                     'street2', 
                                     'city_code',
                                     'city',
                                     'country_code',
                                     'country'])

def get_addressee(party):
    """
    This is a function to unittest the namedtuples
    Please note that the origin of an Addressee might
    not be a Party, so it can contain Organization *and* PersonS, 
    and not necessarily just *one* Organization *or* Person as 
    described below
    """
    organization = None
    persons = []
    street1 = u''
    street2 = u''
    zipcode = u''
    city = u''
    country_code = u''
    country = u''

    if party:
        if party.row_type == u'person':
            person = AddresseePerson(first_name = party.first_name, 
                                     middle_name = party.middle_name,
                                     last_name = party.last_name,
                                     personal_title = party.personal_title,
                                     suffix = party.suffix)
            persons = [person]
        else:
            organization = AdresseeOrganization(name = party.name)
        street1 = party.street1
        street2 = party.street2
        if party.city:
            zipcode = party.city.code
            city = party.city.name
            if party.city.country:
                country_code = party.city.country.code
                country = party.city.country.name
    addressee = Addressee(persons = persons,
                          organization = organization,
                          street1 = street1,
                          street2 = street2,
                          city_code = zipcode,
                          city = city,
                          country_code = country_code,
                          country = country,)
    return addressee
