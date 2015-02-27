#! coding: utf-8
import unittest

from camelot.model.party import Person, City, Country
from vfinance.model.bank.notification import get_addressee

class NotificationCase(unittest.TestCase):

    def test_addressee(self):
        country = Country(code=u'BE',
                          name=u'België')
        city = City(code=u'6200',
                    name=u'Châtelet',
                    country=country)
        party = Person(first_name = u'Jean-François',
                       middle_name = u'André',
                       last_name = u'Macramé',
                       personal_title = u'Président',
                       suffix = u'Sr.')
        party.city = city
        party.street1 = u'Rue Effacé 5',
        party.street2 = u'',
        addressee = get_addressee(party)
        self.assertEqual(addressee.persons[0].personal_title, u'Président')
        self.assertEqual(addressee.persons[0].first_name, u'Jean-François')
        self.assertEqual(addressee.persons[0].middle_name, u'André')
        self.assertEqual(addressee.persons[0].last_name, u'Macramé')
        self.assertEqual(addressee.persons[0].suffix, u'Sr.')
        self.assertEqual(addressee.street1, (u'Rue Effacé 5',)) #why is this a tuple?!
        self.assertEqual(addressee.street2, (u'',)) #why is this a tuple?!
        self.assertEqual(addressee.city_code, u'6200')
        self.assertEqual(addressee.city, u'Châtelet')
        self.assertEqual(addressee.country_code, u'BE')
        self.assertEqual(addressee.country, u'België')
