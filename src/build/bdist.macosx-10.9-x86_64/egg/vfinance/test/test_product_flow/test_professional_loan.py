import datetime
from decimal import Decimal as D

from camelot.core.exception import UserException
from camelot.test.action import MockModelContext

from vfinance.model.hypo import hypotheek, product, akte, terugbetaling, dossier

from .. import test_case

from ..test_model.test_bank import test_rechtspersoon
from ..test_model.test_hypo import test_product, test_waarborg

principal = D(100000)
duration = 60

schedule_data_1 = {'bedrag' : principal,
                   'looptijd' : duration,
                   'terugbetaling_interval' : 12,
                   'terugbetaling_start' : 0,
                   'opname_periode' : 12,
                   'type_aflossing' : 'cummulatief',
                   'type_vervaldag' : 'akte',
                   'doel_aankoop_gebouw_registratie': True,}

product_data = {'name': 'Pro Credit',
                'comment': 'Professionele kredieten',
                'book_from_date':datetime.date(1980,1,1),
                'account_number_prefix': 292
               }

interest_rate = D('0.4') # monthly rate
euribor_rate = D('2.5') # yearly rate

class ProfessionalLoanCase(test_case.SessionCase):

    t0 = datetime.date(2014, 4, 1)    # ondertekening aanvraag
    t1 = datetime.date(2014, 6, 2)    # vermoedelijke aktedatum op moment aanvr
    t2 = datetime.date(2014, 4, 4)    # opmaak beslissingsdocument
    t3 = datetime.date(2014, 4, 3)    # voorwaarden beslissingsdocument
    t4 = datetime.date(2014, 4, 5)    # beslissing door kredietcomite
    t5 = datetime.date(2014, 4, 6)    # opmaak aanbod voor klant
    t6 = datetime.date(2014, 4, 7)    # versturen aanbod naar klant
    t7 = datetime.date(2014, 4, 10)   # ondertekenen aanbod door klant
    t8 = datetime.date(2014, 4, 13)   # aanbod ondertekend ontvangen
    t9 = datetime.date(2014, 5, 3)    # akte goedgekeurd door notarissen
    t10 = datetime.date(2014, 5, 30)  # betaling naar notaris
    t11 = datetime.date(2014, 6, 1)   # geplande aktedatum door notaris
    t12 = datetime.date(2014, 6, 4)   # verlijden akte
    t13 = datetime.date(2014, 7, 1)   # ontvangst grossen

    t60 = datetime.date(2016, 1, 5)   # ontvangst aanvraag afkoop
    t62 = datetime.date(2016, 2, 7)   # gewenste datum van terugbetaling


    @classmethod
    def setUpClass(cls):
        test_case.SessionCase.setUpClass()
        cls.organization_case = test_rechtspersoon.RechtspersoonCase('setUp')
        cls.organization_case.setUpClass()
        cls.person_case = cls.organization_case.natuurlijke_persoon_case

    def setUp(self):
        super(ProfessionalLoanCase, self).setUp()
        self.product_case = test_product.ProductCase('setUp')
        self.guarantee_case = test_waarborg.WaarborgCase('setUp')
        self.organization_case.setUp()
        self.product_case.setUp()
        self.product_case.set_default_configuration(self.product_case.base_product)
        self.product = product.LoanProduct(specialization_of=self.product_case.base_product, **product_data)
        self.guarantee_case.setUp()
        self.guarantor = self.person_case.get_or_create_natuurlijke_persoon(self.person_case.natuurlijke_personen_data[2])
        #
        # Define the loan application
        #
        self.agreement = hypotheek.Hypotheek(aanvraagdatum=self.t0,
                                             aktedatum=self.t1,
                                             wettelijk_kader='andere')
        self.agreement.aanvraagnummer = hypotheek.nieuw_aanvraagnummer(self.agreement)
        hypotheek.HypoApplicationRole(rechtspersoon = self.organization_case.rechtspersoon_3, 
                                      application = self.agreement,
                                      described_by = 'borrower_signing_agent',
                                      rank = 1 )
        hypotheek.HypoApplicationRole(rechtspersoon = self.organization_case.rechtspersoon_4, 
                                      application = self.agreement,
                                      described_by = 'lender_signing_agent',
                                      rank = 1 )
        hypotheek.HypoApplicationRole(rechtspersoon = self.organization_case.rechtspersoon_5, 
                                      application = self.agreement,
                                      described_by = 'borrower',
                                      rank = 1 )
        hypotheek.HypoApplicationRole(natuurlijke_persoon = self.guarantor, 
                                      application = self.agreement,
                                      described_by = 'guarantor',
                                      rank = 1 )
        self.agreement.broker_relation = self.organization_case.broker_relation
        self.agreement.broker_agent = self.organization_case.rechtspersoon_1
        self.goed_aanvraag = hypotheek.GoedAanvraag(hypotheek=self.agreement,
                                                    te_hypothekeren_goed=self.guarantee_case.goed,
                                                    hypothecaire_inschrijving=80000,
                                                    hypothecair_mandaat=10000 )
        self.bedrag_1 = hypotheek.Bedrag(hypotheek_id=self.agreement,
                                         product=self.product, 
                                         **schedule_data_1)

        self.session.flush()
        self.model_context = MockModelContext()
        self.model_context.obj = self.agreement
    
    def test_argeement_states(self):
        self.button(self.agreement, hypotheek.request_complete_action)
        return self.agreement.beslissingen[-1]

    def test_account_creation(self):
        beslissing = self.test_argeement_states()
        beslissing.button_maak_voorstel()
        agreed_premium_schedule = beslissing.goedgekeurd_bedrag[-1]
        agreed_premium_schedule.commerciele_wijziging = '%.2f'%interest_rate
        beslissing.button_approved()
        self.assertEqual(agreed_premium_schedule.goedgekeurde_rente, '%.2f'%interest_rate)
        aanvaarding = beslissing.aanvaarding[-1]
        aanvaarding.button_send()
        aanvaarding.button_received()
        self.button(beslissing.akte[-1], akte.Valid())
        self.button(beslissing.akte[-1], akte.Payed())
        #self.button(beslissing.akte[-1], akte.Pending())
        with self.assertRaises(UserException):
            self.button(beslissing.akte[-1], akte.CreateDossiers())
        beslissing.akte[-1].datum_verlijden = self.t12
        self.button(beslissing.akte[-1], akte.CreateDossiers())
        self.button(beslissing.akte[-1], akte.CreateMortgage())
        loan_account = agreed_premium_schedule.dossier
        return loan_account

    def test_complete_repayment(self):
        loan_account = self.test_account_creation()
        complete_repayment = terugbetaling.Terugbetaling(
            datum=self.t60,
            datum_terugbetaling=self.t62)
        complete_repayment.dossier = loan_account
        complete_repayment.button_maak_voorstel()
        # Deze nieuwe regeling is slechts van toepassing op kredietovereenkomsten die afgesloten werden vanaf 10 januari 2014.
        # M.a.w. de vervroegde terugbetalingen van kredieten afgesloten voor 10 januari 2014 blijven nog steeds onder de vroegere regeling inzake wederbeleggingsvergoeding vallen
        # samen met nieuwe kredieten van 1 miljoen euro of meer.
        self.assertEqual(complete_repayment.wederbeleggingsvergoeding,
                         principal * interest_rate * 6 / 100)
        dossier.DossierFunctionalSettingApplication(applied_on=loan_account,
                                                    described_by='discounted_repayment',
                                                    from_date=self.t60)
        self.session.flush()
        with self.assertRaises(UserException):
            complete_repayment.button_maak_voorstel()
        complete_repayment.euribor = euribor_rate
        complete_repayment.button_maak_voorstel()
        last_repayment = principal * (1+interest_rate/100)**D(duration)
        discounted_repayment = last_repayment / (1+euribor_rate/(12*100))**D(duration-1)
        self.assertAlmostEqual(complete_repayment.wederbeleggingsvergoeding,
                               discounted_repayment.quantize(D('0.01')) - principal,
                               1)
        #
        # A new repayment should not be allowed as long as the previous repayment
        # is dangling
        #
        second_complete_repayment = terugbetaling.Terugbetaling(
            datum=self.t60,
            datum_terugbetaling=self.t62,
            euribor=euribor_rate)
        second_complete_repayment.dossier = loan_account
        with self.assertRaises(UserException):
            second_complete_repayment.button_maak_voorstel()
        complete_repayment.button_canceled()
        second_complete_repayment.button_maak_voorstel()
        second_complete_repayment.button_process()
        #
        # A new repayment on a repayed loan is not possible
        #
        third_complete_repayment = terugbetaling.Terugbetaling(
            datum=self.t60,
            datum_terugbetaling=self.t62,
            euribor=euribor_rate)
        third_complete_repayment.dossier = loan_account
        with self.assertRaises(UserException):
            third_complete_repayment.button_maak_voorstel()
        with self.assertRaises(UserException):
            third_complete_repayment.button_process()