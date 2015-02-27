import datetime

from ..test_bank import test_index
from ... import test_case

from_date = datetime.date(1980,1,1)
product_data = {'name': 'sociaal 3-6-9 +2 -1',
                'comment': 'sociale kredieten met variabele rentevoet',
                'book_from_date': from_date,
                'rank_number_digits': 1
               }

variabiliteit_historiek_data = {'minimale_afwijking': '0.2',
                                'maximale_stijging':'2',
                                'maximale_daling':'1',
                                'maximale_spaar_ristorno':'0',
                                'maximale_product_ristorno':'0',
                                'maximale_conjunctuur_ristorno':'0',
                                }

from camelot.core.orm import Session
from camelot.test.action import MockModelContext

from vfinance.model.bank.product import (ProductFeatureApplicability,
                                         ProductIndexApplicability)
from vfinance.model.hypo.product import (LoanProduct, 
                                         DefaultProductConfiguration,
                                         loan_account_types)

class ProductCase(test_case.SessionCase):
    
    def setUp(self):
        super(ProductCase, self).setUp()
        self.session = Session()
        self.index_case = test_index.IndexCase('setUp')
        self.index_case.setUp()
        self.base_product = LoanProduct(name = 'Basis Hypotheek', company_code='0CHB', account_number_prefix=292)
        self.product = LoanProduct(specialization_of = self.base_product,
                                    account_number_prefix=292, **product_data )
        ProductIndexApplicability(available_for=self.product,
                                  index_type=self.index_case.index_type,
                                  described_by='interest_revision',
                                  apply_from_date=from_date)
        ProductFeatureApplicability(described_by='eerste_herziening',
                                    value=3*12,
                                    premium_from_date=from_date,
                                    apply_from_date=from_date,
                                    available_for=self.product,
                                    )
        ProductFeatureApplicability(described_by='volgende_herzieningen',
                                    value=3*12,
                                    premium_from_date=from_date,
                                    apply_from_date=from_date,
                                    available_for=self.product,
                                    )
        self.session.flush()
              
    def set_default_configuration( self, product ):
        model_context = MockModelContext()
        model_context.obj = product
        default_configuration = DefaultProductConfiguration(loan_account_types)
        list( default_configuration.model_run( model_context ) )
        
    def test_default_product(self):
        product = self.product
        self.set_default_configuration( product )
        self.assertEqual( 'Hypot',
                          product.get_book_at( 'repayment', datetime.date(2007,2,1) ) )

    def test_product_code(self):
        product = self.product
        base_product = self.base_product
        self.assertEqual(product.get_company_code(), '0CHB')
        product.company_code = '0CEI'
        self.assertEqual(product.get_company_code(), '0CEI')
        product.company_code = None
        base_product.company_code = None
        self.assertIsNone(product.get_company_code())
