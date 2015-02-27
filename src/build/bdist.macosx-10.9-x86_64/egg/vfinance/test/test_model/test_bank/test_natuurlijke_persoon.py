# coding=UTF-8

import copy
import datetime
from decimal import Decimal as D
import logging

from camelot.model.fixture import Fixture
from camelot.core.qt import QtGui, QtCore

from sqlalchemy.sql.expression import and_

from vfinance.model.bank.varia import Country_
from vfinance.model.bank.natuurlijke_persoon import NatuurlijkePersoon, Title
from vfinance.model.bank.direct_debit import AbstractBankAccount

from ...test_case import SessionCase

logger = logging.getLogger('vfinance.test.test_bank.test_natuurlijke_persoon')


class MixinNatuurlijkePersoonCase(object):

    natuurlijke_personen_data = [{'voornaam': u'Celie',
                                  'naam': u'Dehaen',
                                  'titel': u'Ms.',
                                  'taal':u'nl',
                                  'gender': u'v',
                                  'nationaal_nummer': '67062938894',
                                  'nationaliteit': (u'BE', u'Belgium'),
                                  'huwelijkscontract': None,
                                  'alimentatie_lasten': None,
                                  'identiteitskaart_datum': None,
                                  'straat': u'Teststraat 12b',
                                  'postcode': u'2222',
                                  'gemeente': u'Testergem Cité',
                                  'land': (u'BE', u'Belgium'),
                                  'telefoon': '02/222.22.22',
                                  'email': u'celie@example.com',
                                  'gsm': None,
                                  'correspondentie_straat':u'Correspondentielaan 33',
                                  'correspondentie_postcode': u'3333',
                                  'correspondentie_gemeente':u'Correspondentegem',
                                  'correspondentie_land': (u'BE', u'Belgium'),
                                  'functie': None,
                                  'burgerlijke_staat': u'ows',
                                  'burgerlijke_staat_sinds': datetime.date(2003, 8, 24),
                                  'aktiviteit_sinds': None,
                                  'kinderbijslag': None,
                                  'identiteitskaart_nummer': None,
                                  'werkgever': None,
                                  'werkgever_sinds': None,
                                  'beroeps_inkomsten': None,
                                  'aktiviteit': None,
                                  'geboorteplaats': u'Maternitéville',
                                  'vervangings_inkomsten': None,
                                  'geboortedatum': datetime.date(1967, 6, 29),
                                  'btw_nummer': None,
                                  'huur_inkomsten': None,
                                  'andere_inkomsten': None,
                                  'andere_lasten': None,
                                  'huur_lasten': None,
                                  'educational_level': u'primary',},
                                 {'burgerlijke_staat': u'w', # [('o','ongehuwd'),('s','ongehuwd samenwonend'),('ows', 'ongehuwd wettelijk samenwonend'),('h','gehuwd'),('g','gescheiden'),('w','weduwe(naar)'),('f','feitelijk gescheiden')]
                                  'aktiviteit_sinds': datetime.date(1973, 12, 31),
                                  'titel': u'Signor',
                                  'naam': u'Gioventù',
                                  'huwelijkscontract': 'gemeenschap', # of 'geen'
                                  # 'postcode': '2143',
                                  'alimentatie_lasten': None,
                                  'identiteitskaart_datum': datetime.date(1953, 1, 1),
                                  'straat': u'Kœstraße',
                                  'kinderbijslag': None,
                                  'identiteitskaart_nummer': None,
                                  'nationaliteit': (u'IT', u'Italy'),
                                  'werkgever_sinds': None,
                                  'beroeps_inkomsten': None,
                                  'email': u'giüséppe@gioventù.it',
                                  'werkgever': None,
                                  'aktiviteit': None,
                                  'geboorteplaats': None,
                                  'vervangings_inkomsten': None,
                                  'voornaam': u'Giüséppe',
                                  'gemeente': None,
                                  'burgerlijke_staat_sinds': datetime.date(1996, 2, 29),
                                  'nationaal_nummer': '51040836608',
                                  'gender': u'm',
                                  'functie': None,
                                  'geboortedatum': datetime.date(1944, 4, 7),
                                  'btw_nummer': None,
                                  'huur_inkomsten': None,
                                  'andere_inkomsten': None,
                                  'andere_lasten': None,
                                  'gsm': None,
                                  'huur_lasten': None,
                                  'telefoon': None,
                                  # 'correspondentie_straat' : u'Ôúwÿg 23',
                                  # 'correspondentie_gemeente' : u'Mävvøstádt',
                                  # 'correspondentie_postcode' : '9487279848',
                                  'rookgedrag' : True,
                                  'taal':u'it',
                                  'educational_level': u'primary',},
                                 {'burgerlijke_staat': u'h', # [('o','ongehuwd'),('s','ongehuwd samenwonend'),('ows', 'ongehuwd wettelijk samenwonend'),('h','gehuwd'),('g','gescheiden'),('w','weduwe(naar)'),('f','feitelijk gescheiden')]
                                  'aktiviteit_sinds': datetime.date(2000, 1, 1),
                                  'titel': u'Signora',
                                  'naam': u'Mîdélìhnå',
                                  'huwelijkscontract': 'geen', # of 'geen'
                                  # 'postcode': '93842',
                                  'alimentatie_lasten': None,
                                  'identiteitskaart_datum': datetime.date(2008, 4, 20),
                                  'straat': u'Ô∂owëg',
                                  'kinderbijslag': 399.99,
                                  'identiteitskaart_nummer': u'1234åßƒs54',
                                  'nationaliteit': None,
                                  'werkgever_sinds': None,
                                  'beroeps_inkomsten': None,
                                  'email': u'åndréà@mîdélìhnå.it',
                                  'werkgever': None,
                                  'aktiviteit': None,
                                  'geboorteplaats': None,
                                  'vervangings_inkomsten': None,
                                  'voornaam': u'Åndréà',
                                  'gemeente': None,
                                  'burgerlijke_staat_sinds': datetime.date(2004, 2, 29),
                                  'nationaal_nummer': '51040836608',
                                  'gender': u'f',
                                  'functie': None,
                                  'geboortedatum': datetime.date(1985, 4, 30),
                                  'btw_nummer': u'012345åüî901234',
                                  'huur_inkomsten': 620.54,
                                  'andere_inkomsten': None,
                                  'andere_lasten': 222.22,
                                  'gsm': u'+32444/23.23.23',
                                  'huur_lasten': None,
                                  'telefoon': None,
                                  'taal':u'it',
                                  'educational_level': u'primary',},
                                 {'burgerlijke_staat': 'ows', # [('o','ongehuwd'),('s','ongehuwd samenwonend'),('ows', 'ongehuwd wettelijk samenwonend'),('h','gehuwd'),('g','gescheiden'),('w','weduwe(naar)'),('f','feitelijk gescheiden')]
                                  'aktiviteit_sinds': datetime.date(1973, 12, 31),
                                  'titel': u'Signor',
                                  'naam': u'Márcø',
                                  # 'postcode': '436783',
                                  'alimentatie_lasten': D('210.01'),
                                  'identiteitskaart_datum': datetime.date(1976, 12, 24),
                                  'straat': u'Løwwéeg',
                                  'kinderbijslag': None,
                                  'identiteitskaart_nummer': None,
                                  'nationaliteit': None,
                                  'werkgever_sinds': None,
                                  'beroeps_inkomsten': None,
                                  'email': u'cårlø@márcø.it',
                                  'werkgever': None,
                                  'aktiviteit': None,
                                  'geboorteplaats': None,
                                  'vervangings_inkomsten': None,
                                  'voornaam': u'Cårlø',
                                  'gemeente': None,
                                  'nationaal_nummer': '51040836608',
                                  'gender': u'm',
                                  'functie': None,
                                  'geboortedatum': datetime.date(1967, 8, 17),
                                  'btw_nummer': None,
                                  'huur_inkomsten': None,
                                  'andere_inkomsten': None,
                                  'andere_lasten': None,
                                  'gsm': None,
                                  'huur_lasten': None,
                                  'telefoon': u'+32/11.23.45',
                                  'taal':u'it',
                                  'educational_level': u'primary',},
                                 {'burgerlijke_staat': 'o', # [('o','ongehuwd'),('s','ongehuwd samenwonend'),('ows', 'ongehuwd wettelijk samenwonend'),('h','gehuwd'),('g','gescheiden'),('w','weduwe(naar)'),('f','feitelijk gescheiden')]
                                  'aktiviteit_sinds': datetime.date(1973, 12, 31),
                                  'titel': u'M.',
                                  'naam': u'Vanhove',
                                  # 'postcode': '436783',
                                  'alimentatie_lasten': 210.01,
                                  'identiteitskaart_datum': datetime.date(1976, 12, 24),
                                  'straat': u'Bruggestraat 73',
                                  'kinderbijslag': None,
                                  'identiteitskaart_nummer': None,
                                  'nationaliteit': (u'BE', u'Belgium'),
                                  'werkgever_sinds': None,
                                  'beroeps_inkomsten': None,
                                  'email': u'',
                                  'werkgever': None,
                                  'aktiviteit': None,
                                  'geboorteplaats': u'Maternitéstad',
                                  'vervangings_inkomsten': None,
                                  'voornaam': u'Giovanni',
                                  'gemeente': u'Torhout',
                                  'postcode': u'8820',
                                  'land': (u'BE', u'Belgium'),
                                  'nationaal_nummer': '51040836608',
                                  'gender': u'm',
                                  'functie': None,
                                  'geboortedatum': datetime.date(1974, 1, 13),
                                  'btw_nummer': None,
                                  'huur_inkomsten': None,
                                  'andere_inkomsten': None,
                                  'andere_lasten': None,
                                  'gsm': None,
                                  'huur_lasten': None,
                                  'telefoon': u'+32/11.23.45',
                                  'taal':u'nl',
                                  'educational_level': u'primary',},
                                 {'burgerlijke_staat': 'o', # [('o','ongehuwd'),('s','ongehuwd samenwonend'),('ows', 'ongehuwd wettelijk samenwonend'),('h','gehuwd'),('g','gescheiden'),('w','weduwe(naar)'),('f','feitelijk gescheiden')]
                                  'aktiviteit_sinds': datetime.date(1973, 12, 31),
                                  'titel': u'M.',
                                  'naam': u'Verhoeyen',
                                  # 'postcode': '436783',
                                  'alimentatie_lasten': 210.01,
                                  'identiteitskaart_datum': datetime.date(1976, 12, 24),
                                  'straat': u'Bruggestraat 73',
                                  'kinderbijslag': None,
                                  'identiteitskaart_nummer': None,
                                  'nationaliteit': None,
                                  'werkgever_sinds': None,
                                  'beroeps_inkomsten': None,
                                  'email': u'',
                                  'werkgever': None,
                                  'aktiviteit': None,
                                  'geboorteplaats': None,
                                  'vervangings_inkomsten': None,
                                  'voornaam': u'Alain',
                                  'postcode': u'8820',
                                  'gemeente': u'Torhout',
                                  'nationaal_nummer': '51040836608',
                                  'gender': u'm',
                                  'functie': None,
                                  'geboortedatum': datetime.date(1964, 12, 10),
                                  'btw_nummer': None,
                                  'huur_inkomsten': None,
                                  'andere_inkomsten': None,
                                  'andere_lasten': None,
                                  'gsm': None,
                                  'huur_lasten': None,
                                  'telefoon': u'+32/11-452.345',
                                  'taal':u'nl',
                                  'educational_level': u'primary',},
                                 {'burgerlijke_staat': 'g', # [('o','ongehuwd'),('s','ongehuwd samenwonend'),('ows', 'ongehuwd wettelijk samenwonend'),('h','gehuwd'),('g','gescheiden'),('w','weduwe(naar)'),('f','feitelijk gescheiden')]
                                  'aktiviteit_sinds': datetime.date(1980, 12, 31),
                                  'titel': u'M.',
                                  'naam': u'François',
                                  # 'postcode': '436783',
                                  'alimentatie_lasten': D('210.01'),
                                  'identiteitskaart_datum': datetime.date(1994, 12, 24),
                                  'straat': u'Rue Sénèque 109B',
                                  'land': (u'FR', u'France'),
                                  'postcode':u'4444',
                                  'kinderbijslag': None,
                                  'identiteitskaart_nummer': None,
                                  'nationaliteit': (u'FR', u'France'),
                                  'werkgever_sinds': None,
                                  'beroeps_inkomsten': None,
                                  'email': u'',
                                  'werkgever': None,
                                  'aktiviteit': None,
                                  'geboorteplaats': None,
                                  'vervangings_inkomsten': None,
                                  'voornaam': u'Alain',
                                  'gemeente': u'Mulhouse',
                                  'nationaal_nummer': '51040836608',
                                  'gender': u'm',
                                  'functie': None,
                                  'geboortedatum': datetime.date(1964, 12, 10),
                                  'btw_nummer': None,
                                  'huur_inkomsten': None,
                                  'andere_inkomsten': None,
                                  'andere_lasten': None,
                                  'gsm': None,
                                  'huur_lasten': None,
                                  'telefoon': u'+32/12-345.678',
                                  'taal':u'fr',
                                  'educational_level': u'primary',},
                                  {'voornaam': u'Jan-Peter',
                                  'naam': u'Terpstra',
                                  'titel': u'M.',
                                  'taal':u'nl',
                                  'gender': u'm',
                                  'nationaal_nummer': '6123.45.671',
                                  'nationaliteit': (u'NL', u'The Netherlands'),
                                  'huwelijkscontract': None,
                                  'alimentatie_lasten': None,
                                  'identiteitskaart_datum': None,
                                  'straat': u'Oranjesingel 77',
                                  'postcode': u'5623 LH',
                                  'gemeente': u'Eindhoven',
                                  'land': (u'NL', u'The Netherlands'),
                                  'telefoon': '0543-536385',
                                  'email': u'janpeter@example.com',
                                  'gsm': None,
                                  'functie': None,
                                  'burgerlijke_staat': None,
                                  'burgerlijke_staat_sinds': None,
                                  'aktiviteit_sinds': None,
                                  'kinderbijslag': None,
                                  'identiteitskaart_nummer': None,
                                  'werkgever': None,
                                  'werkgever_sinds': None,
                                  'beroeps_inkomsten': None,
                                  'aktiviteit': None,
                                  'geboorteplaats': None,
                                  'vervangings_inkomsten': None,
                                  'geboortedatum': datetime.date(1970, 2, 2),
                                  'btw_nummer': None,
                                  'huur_inkomsten': None,
                                  'andere_inkomsten': None,
                                  'andere_lasten': None,
                                  'huur_lasten': None,
                                  'educational_level': u'primary',},]
    titles_data = [(u'M.', u'M.', u'contact'),(u'Ms.', u'Ms.', u'contact')]
    countries_data = {u'BE': u'Belgium',
                      u'NL': u'The Netherlands',
                      u'LU': u'Luxemburg',
                      u'IT': u'Italy',
                      u'FR': u'France'
                      }

    # 
    # get and create helper methods
    #
    @classmethod
    def get_or_create_natuurlijke_persoon(cls, persoon_data={}):
        """Helper function to create a unique natuurlijke persoon"""
        if not persoon_data:
            persoon_data = cls.natuurlijke_personen_data[0]
        
        # copy, because we will replace the countries
        persoon_data = copy.copy( persoon_data )
        
        for country_key in ['land', 'nationaliteit', 'correspondentie_land']:
            """replace country entries with real objects"""
            if country_key in persoon_data:
                country_code = persoon_data[country_key]
                if country_code is None:
                    continue
                country = cls.get_or_create_country(country_code[0])
                assert country is not None
                persoon_data[country_key] = country
                
        person = Fixture.insert_or_update_fixture( NatuurlijkePersoon,
                                                   persoon_data['naam'] + '_' + persoon_data['voornaam'],
                                                   persoon_data,
                                                   'unittests' )
        return person

    def create_natuurlijke_persoon( self, persoon_data={} ):
        """Legacy function"""
        return self.get_or_create_natuurlijke_persoon(persoon_data)

    def get_natuurlijke_personen(self, personen_data=[]):
        if not personen_data:
            personen_data = self.natuurlijke_personen_data
        personen = []
        for persoon_data in personen_data:
            p = self.get_or_create_natuurlijke_persoon(persoon_data)
            personen.append(p)
        return personen

    def create_natuurlijke_personen(self, natuurlijke_personen_data=[]):
        """Helper function to create a list of people"""
        if not natuurlijke_personen_data:
            natuurlijke_personen_data = self.natuurlijke_personen_data
        for persoon_data in self.natuurlijke_personen_data:
            self.get_or_create_natuurlijke_persoon(persoon_data)

    @classmethod
    def create_titles(cls, titles_data=[]):
        if not titles_data:
            titles_data = cls.titles_data
        for title_data in titles_data:
            cls.get_or_create_title(title_data)

    @classmethod
    def get_or_create_title(cls, title_data=()):
        if not title_data:
            title_data = cls.titles_data[0]
        name, shortcut, domain = title_data
        title = Fixture.insert_or_update_fixture( Title,
                                                  name,
                                                  {'shortcut':shortcut, 'name':name, 'domain':domain},
                                                  'unittests' )
        return title

    @classmethod
    def create_countries(cls):
        """Create countries in the database to be used for Addresses"""
        for code in cls.countries_data.keys():
            cls.get_or_create_country(code)

    @classmethod
    def get_or_create_country(cls, code):
        name = cls.countries_data[code]
        country = Fixture.insert_or_update_fixture( Country_,
                                                    code,
                                                    {'code':code, 'name':name},
                                                    'unittests' )
        return country

class NatuurlijkePersoonCase(SessionCase, MixinNatuurlijkePersoonCase):

    @classmethod
    def setUpClass(cls):
        SessionCase.setUpClass()
        cls.create_countries()
        cls.create_titles()

    def setUp(self):
        # persons might be changed during tests
        self.create_natuurlijke_personen()
    
    def test_natuurlijke_persoon( self ):
        # test our Celie
        persoon = NatuurlijkePersoon.query.filter(and_(NatuurlijkePersoon.naam==u'Dehaen', NatuurlijkePersoon.voornaam==u'Celie')).first()
        # print persoon.__dict__
        self.assertEqual( persoon.voornaam, u'Celie' )
        self.assertEqual( persoon.naam, u'Dehaen' )
        self.assertEqual( persoon.straat, u'Teststraat 12b' )
        self.assertEqual( persoon.postcode, u'2222' )
        self.assertEqual( persoon.gemeente, u'Testergem Cité' )
        self.assertEqual( persoon.land.code, u'BE' )
        self.assertEqual( persoon.land.name, u'Belgium' )

    def test_burger_service_nummer( self ):
        #
        # Nationaal Nummer voor Nederland
        #
        from vfinance.model.bank.natuurlijke_persoon import analyze_nationaal_nummer
        nederlander = self.get_or_create_natuurlijke_persoon(self.natuurlijke_personen_data[7])
        self.assertEqual( nederlander.voornaam, u'Jan-Peter' )
        self.assertEqual( nederlander.naam, u'Terpstra' )
        nederlander.nationaal_nummer = '6123.45.672'
        self.assertFalse( analyze_nationaal_nummer( nederlander )[0] )
        nederlander.nationaal_nummer = '6123.45.671'
        self.assertTrue( analyze_nationaal_nummer( nederlander )[0] )


    def test_validate_national_number(self):
        persoon = NatuurlijkePersoon.query.filter(and_(NatuurlijkePersoon.naam==u'Dehaen', NatuurlijkePersoon.voornaam==u'Celie')).first()
        persoon_nl = NatuurlijkePersoon.query.filter(and_(NatuurlijkePersoon.naam==u'Terpstra', NatuurlijkePersoon.voornaam==u'Jan-Peter')).first()
        validator = NatuurlijkePersoon.Admin.NationalNumberValidator(persoon.land)
        validator_nl = NatuurlijkePersoon.Admin.NationalNumberValidator(persoon_nl.land)
        national_number = QtCore.QString('8107033950')
        burger_service_number = QtCore.QString('612345672')
        self.assertEqual(validator.validate(national_number, 10), (QtGui.QValidator.Intermediate, 10))
        national_number.append('3')
        self.assertEqual(validator.validate(national_number, 11), (QtGui.QValidator.Intermediate, 11))
        national_number.replace(10, 1, '4')
        self.assertEqual(validator.validate(national_number, 11), (QtGui.QValidator.Acceptable, 15))
        self.assertEqual(national_number, '81.07.03-395.04')
        self.assertEqual(validator.validate(national_number, 15), (QtGui.QValidator.Acceptable, 15))
        # voor nederlandse burgerservicenummers
        self.assertEqual(validator_nl.validate(burger_service_number, 9), (QtGui.QValidator.Intermediate, 9))
        burger_service_number.replace(8, 1, '1')
        self.assertEqual(validator_nl.validate(burger_service_number, 9), (QtGui.QValidator.Acceptable, 11))
        self.assertEqual(burger_service_number, '6123.45.671')


    def test_validate_vat_number(self):
        validator = NatuurlijkePersoon.Admin.VATNumberValidator()
        VAT_number_wrong = QtCore.QString('0878169208')
        VAT_number_correct = QtCore.QString('0878169209')

        # Test of correcte nummers aanvaard worden en foutieve geweigerd
        self.assertEqual(validator.validate(VAT_number_wrong, 10), (QtGui.QValidator.Intermediate, 13))
        self.assertEqual(validator.validate(VAT_number_correct, 10), (QtGui.QValidator.Acceptable, 16))

        # Test of de opmaak correct verloopt
        self.assertEqual(VAT_number_correct, QtCore.QString('BE 0878.169.209'))

    def test_validate_id_card_number(self):
        persoon = NatuurlijkePersoon.query.filter(and_(NatuurlijkePersoon.naam==u'Dehaen', NatuurlijkePersoon.voornaam==u'Celie')).first()
        persoon_nl = NatuurlijkePersoon.query.filter(and_(NatuurlijkePersoon.naam==u'Terpstra', NatuurlijkePersoon.voornaam==u'Jan-Peter')).first()
        validator = NatuurlijkePersoon.Admin.IDCardNumberValidator(persoon.land)
        validator_nl = NatuurlijkePersoon.Admin.IDCardNumberValidator(persoon_nl.land)
        card_number = QtCore.QString('5918442723')
        card_number_nl = QtCore.QString('Iw058Fb74')

        # Testen of de correcte nummbers worden aanvaard en foutieve geweigerd
        self.assertEqual(validator.validate(card_number, 10), (QtGui.QValidator.Intermediate, 10))
        card_number.append('42')
        self.assertEqual(validator.validate(card_number, 12), (QtGui.QValidator.Acceptable, 14))
        self.assertEqual(validator_nl.validate(card_number_nl, 9), (QtGui.QValidator.Acceptable, 9))

        # Testen of de formattering correct verloopt
        self.assertEqual(card_number, QtCore.QString('591-8442723-42'))
        self.assertEqual(card_number_nl, QtCore.QString('IW058FB74'))


    def test_validate_tel_numbers(self):
        validator = NatuurlijkePersoon.Admin.TelephoneNumberValidator()
        tel_nr = QtCore.QString('03.288.02.03')
        gsm_nr = QtCore.QString('0485 93 84 31')
        tel_nr_nl = QtCore.QString('+3120-3114411')

        # Testen of de correcte nummers worden geaccepteerd en foutieve geweigerd
        self.assertEqual(validator.validate(QtCore.QString('03288020'), 9), (QtGui.QValidator.Intermediate, 8))
        self.assertEqual(validator.validate(QtCore.QString('03288'), 5), (QtGui.QValidator.Intermediate, 5))
        self.assertEqual(validator.validate(tel_nr, 12), (QtGui.QValidator.Acceptable, 15))
        self.assertEqual(validator.validate(gsm_nr, 13), (QtGui.QValidator.Acceptable, 16))
        self.assertEqual(validator.validate(tel_nr_nl, 15), (QtGui.QValidator.Acceptable, 15))

        # Testen of formattering correct verloopt
        self.assertEqual(tel_nr, QtCore.QString('+32 3 288 02 03'))
        self.assertEqual(gsm_nr, QtCore.QString('+32 485 93 84 31'))
        self.assertEqual(tel_nr_nl, QtCore.QString('+31 20 311 4411'))


    def test_validate_banking_account_number(self):
        validator = AbstractBankAccount.Admin.BankingNumberValidator()
        reknr1 = QtCore.QString('BE 94.0016.1862.1015')
        reknr2 = QtCore.QString('be56c6511-5262-8088')
        reknr3 = QtCore.QString('nL20iNgB/0655/7885/30')

        # Testen of de correcte nummers worden geaccepteerd en foutieve geweigerd
        self.assertEqual(validator.validate(reknr1, 3), (QtGui.QValidator.Intermediate, 3))
        self.assertEqual(validator.validate(reknr2, 18), (QtGui.QValidator.Intermediate, 18))
        reknr1.replace(19, 1, '4')
        reknr2.replace(4, 1, ' ')
        self.assertEqual(validator.validate(reknr1, 19), (QtGui.QValidator.Acceptable, 19))
        self.assertEqual(validator.validate(reknr2, 18), (QtGui.QValidator.Acceptable, 19))
        self.assertEqual(validator.validate(reknr3, 20), (QtGui.QValidator.Acceptable, 22))

        # Testen of formattering correct verloopt
        self.assertEqual(reknr1, QtCore.QString('BE94 0016 1862 1014'))
        self.assertEqual(reknr2, QtCore.QString('BE56 6511 5262 8088'))
        self.assertEqual(reknr3, QtCore.QString('NL20 INGB 0655 7885 30'))

    def test_validate_email(self):
        self.assertTrue(True)




