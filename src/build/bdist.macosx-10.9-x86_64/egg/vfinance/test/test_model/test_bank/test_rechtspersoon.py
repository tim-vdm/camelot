# coding=UTF-8
import copy
import logging

from camelot.model.fixture import Fixture

from vfinance.model.bank.rechtspersoon import Rechtspersoon
from vfinance.model.bank.dual_person import CommercialRelation, BankAccount
from vfinance.model.bank.official_number import OfficialNumber

from ...test_case import SessionCase
from . import test_natuurlijke_persoon

logger = logging.getLogger('vfinance.test.test_bank.test_rechtspersoon')


class MixinRechtspersoonCase(test_natuurlijke_persoon.MixinNatuurlijkePersoonCase):

    rechtspersoon_data_1 = dict(
        name = 'Evest Belgium NV',
        tax_number = '00123456789',
        ondernemingsnummer = '00123456789',
        straat = 'Am Hock 2',
        postcode = '9991',
        gemeente = 'Weiswampach',
        taal = 'nl',
        land = (u'BE', u'Belgium'),
    )
    rechtspersoon_data_1_official_number = dict(type='cbfa',number='9191')

    rechtspersoon_data_2 = dict(
        name = 'Willemot NV',
        tax_number = '00987654321',
        ondernemingsnummer = '00987654321',
        straat = 'Coupure 228',
        correspondentie_straat = 'Coupure-correspondentie 228',
        postcode = '9000',
        correspondentie_postcode = '2000',
        gemeente = 'Gent',
        correspondentie_gemeente = 'Antwerpen',
        taal = 'nl',
        land = (u'BE', u'Belgium'),
        correspondentie_land = (u'BE', u'Belgium'),
    )
    rechtspersoon_data_2_official_number = dict(type='cbfa',number='8181')

    rechtspersoon_data_3 = dict(
        name = u'Notaris Héndrik MUYSHONDT',
        tax_number = 'BE 0454.159.938',
        ondernemingsnummer = 'BE 0454.159.938',
        straat = u'Dekènstraat 20',
        postcode = '1500',
        gemeente = u'Hàlle',
        taal = 'nl',
        land = (u'BE', u'Belgium'),
    )

    rechtspersoon_data_4 = dict(
        name = 'Notaris Ilse DE BRAUWERE',
        tax_number = 'BE 0434.306.810',
        ondernemingsnummer = 'BE 0434.306.810',
        straat = u'Chàrles de Kerçhovelaan 14',
        postcode = '9000',
        gemeente = u'Gènt',
        taal = 'nl',
        land = (u'BE', u'Belgium'),
    )

    rechtspersoon_data_5 = dict(
        name = u'Drâkkar Import',
        tax_number = 'BE 0882.680.105',
        ondernemingsnummer = 'BE 0882.680.105',
        straat = u'Kùlvestraat 9/11',
        postcode = '8000 ',
        gemeente = u'Brùgge',
        taal = 'nl',
        land = (u'BE', u'Belgium'),
    )

    @classmethod
    def get_or_create_rechtspersoon(cls, persoon_data={}):
        """Helper function to create a unique natuurlijke persoon"""
        if not persoon_data:
            persoon_data = cls.rechtspersoon_data_1
        
        # copy, because we will replace the countries
        persoon_data = copy.copy( persoon_data )
        
        for country_key in ['land', 'correspondentie_land']:
            """replace country entries with real objects"""
            if country_key in persoon_data:
                country_code = persoon_data[country_key]
                if country_code is None:
                    continue
                country = cls.get_or_create_country(country_code[0])
                assert country is not None
                persoon_data[country_key] = country
                    
        person = Fixture.insert_or_update_fixture(Rechtspersoon,
                                                  persoon_data['name'],
                                                  persoon_data,
                                                  'unittests' )
        return person

class RechtspersoonCase(SessionCase, MixinRechtspersoonCase):

    def setUpClass(cls):
        SessionCase.setUpClass()
        cls.natuurlijke_persoon_case = test_natuurlijke_persoon.NatuurlijkePersoonCase('setUp')
        cls.natuurlijke_persoon_case.setUpClass()

    def setUp(self):
        self.natuurlijke_persoon_case.setUp()
        self.rechtspersoon_1 = self.get_or_create_rechtspersoon(self.rechtspersoon_data_1)
        self.rechtspersoon_data_1_official_number['rechtspersoon'] = self.rechtspersoon_1
        Fixture.insert_or_update_fixture(BankAccount, 'rechtspersoon_1', {'iban': u'BE94001618621014', 'rechtspersoon': self.rechtspersoon_1})
        Fixture.insert_or_update_fixture(OfficialNumber, 'rechtspersoon_1', self.rechtspersoon_data_1_official_number)
        self.rechtspersoon_2 = self.get_or_create_rechtspersoon(self.rechtspersoon_data_2)
        self.rechtspersoon_data_2_official_number['rechtspersoon'] = self.rechtspersoon_2
        Fixture.insert_or_update_fixture(OfficialNumber, 'rechtspersoon_2', self.rechtspersoon_data_2_official_number)
        self.rechtspersoon_3 = self.get_or_create_rechtspersoon(self.rechtspersoon_data_3)
        self.rechtspersoon_4 = self.get_or_create_rechtspersoon(self.rechtspersoon_data_4)
        self.rechtspersoon_5 = self.get_or_create_rechtspersoon(self.rechtspersoon_data_5)
        self.broker_relation =  Fixture.insert_or_update_fixture(CommercialRelation,
                                                              '2_broker_for_1',
                                                              {'from_rechtspersoon':self.rechtspersoon_1,
                                                               'rechtspersoon':self.rechtspersoon_2,
                                                               'type':'broker'} )
