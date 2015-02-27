import datetime

from ... import test_case
from . import test_product

from vfinance.model.hypo.dossier import AbstractDossier
from vfinance.model.hypo.visitor import AbstractHypoVisitor

import mock

class RoleMock(mock.Mock):
    
    def __init__(self, **kwargs):
        kwargs.setdefault('from_date', datetime.date(2000,1,1))
        kwargs.setdefault('thru_date', datetime.date(2400,12,31))
        kwargs.setdefault('rank', 1)
        kwargs.setdefault('described_by', 'borrower')
        super(RoleMock, self).__init__(**kwargs)
        
class DossierMock(mock.Mock, AbstractDossier):
    
    def __init__(self, **kwargs):
        kwargs.setdefault('company_id', 234)
        kwargs.setdefault('nummer', 4887)
        kwargs.setdefault('rank', 1)
        kwargs.setdefault('startdatum', datetime.date(2006,1,1))
        kwargs.setdefault('roles', [])
        super(DossierMock, self).__init__(**kwargs)

class Schedule(mock.Mock):

    def __init__(self, **kwargs):
        kwargs.setdefault('dossier', DossierMock())
        super(Schedule, self).__init__(**kwargs)
        self.dossier.goedgekeurd_bedrag = self
        
class AbstractVisitorCase(test_case.SessionCase):

    def setUp(self):
        super(AbstractVisitorCase, self).setUp()
        self.product_case = test_product.ProductCase('setUp')
        self.product_case.setUp()
        self.product_case.set_default_configuration(self.product_case.product)
        self.visitor = AbstractHypoVisitor()
    
    def test_create_customer_request(self):
        schedule = Schedule(product=self.product_case.product)
        customer_request = self.visitor.create_customer_request(schedule, schedule.dossier.roles)
        self.assertEqual(customer_request.from_number, int('23404887'))
        self.assertEqual(customer_request.thru_number, int('23404887'))
    
    def test_get_full_account_number(self):
        schedule = Schedule(product=self.product_case.product)
        full_account_number = self.visitor.get_full_account_number_at(schedule,
                                                                      schedule.dossier.startdatum)
        self.assertEqual(full_account_number, '292234048871')
