import datetime
from decimal import Decimal as D

from camelot.core.orm import Session
from camelot.test.action import MockModelContext

from ... import test_case, app_admin
from ..test_bank import test_rechtspersoon
from . import test_product
from . import test_waarborg

hypotheek_data = {'aanvraagdatum': datetime.date(2007, 4, 1),
                  'aktedatum': datetime.date(2007, 4, 1),
                  'company_id': 123,
                  'rank': 1
                  }
bedrag_data_1 = { 'bedrag' : D(100000),
                  'looptijd' : 120,
                  'terugbetaling_interval' : 12,
                  'terugbetaling_start' : 0,
                  'opname_periode' : 0,
                  'type_aflossing' : 'vaste_aflossing',
                  'type_vervaldag' : 'akte',
                  'doel_aankoop_gebouw_registratie': True,
                }
bedrag_data_2 = { 'bedrag' : D(50000),
                  'looptijd' : 60,
                  'terugbetaling_interval' : 12,
                  'terugbetaling_start' : 0,
                  'opname_periode' : 12,
                  'type_aflossing' : 'vaste_aflossing',
                  'type_vervaldag' : 'akte',
                  'doel_renovatie' : True,
                }

from vfinance.model.hypo import hypotheek
from vfinance.model.bank import direct_debit, validation

class AanvraagformulierCase(test_case.SessionCase):

    @classmethod
    def setUpClass(cls):
        cls.organization_case = test_rechtspersoon.RechtspersoonCase('setUp')
        cls.organization_case.setUpClass()
        cls.person_case = cls.organization_case.natuurlijke_persoon_case
        
    def setUp(self):
        super(AanvraagformulierCase, self).setUp()
        self.organization_case.setUp()
        self.variability_case = test_product.ProductCase('setUp')
        self.guarantee_case = test_waarborg.WaarborgCase('setUp')
        self.variability_case.setUp()
        self.variability_case.set_default_configuration( self.variability_case.base_product )
        self.guarantee_case.setUp()
        self.person_case.setUp()
        self.organization_case.setUp()
        self.test_person_1 = self.person_case.create_natuurlijke_persoon()
        self.test_person_2 = self.person_case.create_natuurlijke_persoon( self.person_case.natuurlijke_personen_data[6] )
        self.test_person_3 = self.person_case.create_natuurlijke_persoon( self.person_case.natuurlijke_personen_data[3] )
        self.hypotheek = hypotheek.Hypotheek(**hypotheek_data)
        self.hypotheek.aanvraagnummer = hypotheek.nieuw_aanvraagnummer(self.hypotheek)
        hypotheek.HypoApplicationRole(rechtspersoon = self.organization_case.rechtspersoon_1, 
                                      application = self.hypotheek,
                                      described_by = 'borrower_signing_agent',
                                      rank = 1 )
        self.hypotheek.broker_relation = self.organization_case.broker_relation
        self.hypotheek.broker_agent = self.organization_case.rechtspersoon_1
        self.goed_aanvraag = hypotheek.GoedAanvraag(hypotheek=self.hypotheek,
                                                    te_hypothekeren_goed=self.guarantee_case.goed,
                                                    hypothecaire_inschrijving=50000,
                                                    hypothecair_mandaat=50000 )
        self.bijkomende_waarborg_hypotheek = hypotheek.BijkomendeWaarborgHypotheek( hypotheek=self.hypotheek,
                                                                                    bijkomende_waarborg=self.guarantee_case.bijkomende_waarborg)
        self.bedrag_1 = hypotheek.Bedrag(hypotheek_id=self.hypotheek,
                                         product=self.variability_case.product, 
                                         **bedrag_data_1)
        self.bedrag_2 = hypotheek.Bedrag(hypotheek_id=self.hypotheek,
                                         product=self.variability_case.product, 
                                         **bedrag_data_2)
        self.hypotheeknemer = None
        self.session = Session()
        self.session.flush()
        self.admin = app_admin.get_related_admin(hypotheek.Hypotheek)
        self.model_context = MockModelContext()
        self.model_context.obj = self.hypotheek
        self.model_context.admin = self.admin
    
    def test_full_number(self):
        application = hypotheek.Hypotheek(company_id=234, aanvraagnummer=4887, rank=0)
        self.assertEqual(application.full_number, '234-00-04887-70')

    def test_totals(self):
        self.assertEqual(self.hypotheek.gedwongen_verkoop, 100000)
        self.assertEqual(self.hypotheek.vrijwillige_verkoop, 150000)
        goeden = self.hypotheek.gehypothekeerd_goed
        self.assertEqual( len(goeden), 1 )
        for goed in goeden:
            bestaande_inschrijvingen = goed.te_hypothekeren_goed.waarborgen
            self.assertEqual( len(bestaande_inschrijvingen), 1 )
        self.assertEqual(self.hypotheek.bestaande_inschrijvingen, 80000)
        self.assertEqual(self.hypotheek.saldo_bestaande_inschrijvingen, 60000)
        self.assertEqual(self.hypotheek.waarborgen_venale_verkoop, 130000 - 1.2 * 80000.0)
        self.assertEqual(self.hypotheek.hypothecaire_waarborgen, 100000 - 1.2 * 80000.0)
        self.assertEqual(self.hypotheek.handelsdoeleinden, True)
        gevraagde_bedragen = self.hypotheek.gevraagd_bedrag
        self.assertEqual(len(gevraagde_bedragen), 2)
        self.assertEqual(self.hypotheek.totaal_gevraagd_bedrag, bedrag_data_1['bedrag'] + bedrag_data_2['bedrag'])
    
    def test_complete(self):
        # check of bedrag data ingevuld is
        self.assertEqual(self.bedrag_1.type_vervaldag, 'akte')
        # add a direct debit mandate
        self.mandate = direct_debit.DirectDebitMandate( hypotheek = self.hypotheek,
                                                        described_by = 'local',
                                                        iban = '038-1571569-50',
                                                        from_date = self.hypotheek.aanvraagdatum,
                                                        date = self.hypotheek.aanvraagdatum )
        self.mandate.identification = self.mandate.get_default_identification()
        self.assertTrue( validation.ogm(self.mandate.identification) )
        self.session.flush()
        # without an hypotheeknemer, an exception should be raised
        with self.assertRaises( Exception ):
            list( hypotheek.request_complete_action.model_run( self.model_context ) )
        list( hypotheek.request_incomplete_action.model_run( self.model_context ) )
        self.assertEqual(self.hypotheek.state, 'incomplete' )
        # now add an hypotheeknemer
        role_1 = hypotheek.HypoApplicationRole(natuurlijke_persoon=self.test_person_2,
                                               application=self.hypotheek,
                                               described_by='borrower',
                                               rank=2)
        self.session.flush()
        role_2 = hypotheek.HypoApplicationRole(natuurlijke_persoon=self.test_person_1,
                                               application=self.hypotheek,
                                               described_by='borrower',
                                               rank=1)
        role_2.company_coverage_limit = 50
        role_2.person_coverage_limit = 20
        self.session.flush()
        role_3 = hypotheek.HypoApplicationRole(natuurlijke_persoon=self.test_person_3,
                                               application=self.hypotheek,
                                               described_by='borrower',
                                               rank=3)
        self.session.flush()
        self.assertEqual(self.hypotheek.borrower_1_name, self.test_person_1.name)
        self.assertEqual(self.hypotheek.borrower_2_name, self.test_person_2.name)
        role_1.rank = 2
        role_2.rank = 1
        role_3.rank = 3
        self.assertEqual(self.hypotheek.borrower_1_name, self.test_person_1.name)
        self.assertEqual(self.hypotheek.borrower_2_name, self.test_person_2.name)
        self.session.flush()
        self.assertEqual(role_2.company_coverage_limit, 50)
        role_1.rank = 2
        role_2.rank = 1
        role_3.rank = 3
        self.session.flush()
        # set, unset and reset gewestwaarborg to test the functional settings
        # code
        self.assertEqual(self.hypotheek.agreed_functional_setting_state_guarantee, None)
        self.hypotheek.agreed_functional_setting_state_guarantee = 'flemish_region_guarantee'
        state_guarantee = self.hypotheek.get_functional_setting_description_at(self.hypotheek.aanvraagdatum, 'state_guarantee')
        self.assertEqual(state_guarantee, 'flemish_region_guarantee')
        self.assertEqual(self.hypotheek.agreed_functional_setting_state_guarantee, 'flemish_region_guarantee')
        self.hypotheek.agreed_functional_setting_state_guarantee = None
        self.assertEqual(self.hypotheek.agreed_functional_setting_state_guarantee, None)
        self.hypotheek.agreed_functional_setting_state_guarantee = 'walloon_region_guarantee'
        self.assertEqual(self.hypotheek.agreed_functional_setting_state_guarantee, 'walloon_region_guarantee')
        # test the field attributes
        state_guarantee_fa = self.admin.get_field_attributes('agreed_functional_setting_state_guarantee')
        self.assertEqual(state_guarantee_fa['editable'](self.hypotheek), True)
        self.assertEqual(len(state_guarantee_fa['choices']), 3)
        # set the state guarantee feature
        self.bedrag_1.state_guarantee = 300
        self.session.flush()
        # make sure the feature is stored in the related table
        self.assertEqual(self.bedrag_1.agreed_features_by_description['state_guarantee'].value, 300)
        # and retry to put it in complete state
        list( hypotheek.request_complete_action.model_run( self.model_context ) )
        self.assertEqual(self.hypotheek.state, 'complete' )
        beslissing = list(self.hypotheek.beslissingen)[-1]
        self.assertEqual( beslissing.datum_voorwaarde, 
                          hypotheek_data['aanvraagdatum'] )
        return beslissing

    #def test_get_query(self):
        #import wingdbstub
        #from sqlalchemy import event, create_engine
        #from sqlalchemy.engine import Engine
        #from camelot.view.proxy.queryproxy import QueryTableProxy

        #def my_on_select(conn, clauseelement, multiparams, params):
            #if clauseelement.is_selectable:
                #print(clauseelement)                
                #where_clause = clauseelement._whereclause
                #if where_clause is not None and '.id' in where_clause:
                    #self.fail("Select query fetches by id: '{0}'".format(where_clause))

        #event.listen(Engine, 'before_execute', my_on_select)

        #adm = app_admin.get_related_admin(hypotheek.Hypotheek)
        #proxy = QueryTableProxy(adm)
        #proxy.set_value(adm.get_query())
        #proxy._get_collection_range(0, 10)

        #event.remove(Engine, 'before_execute', my_on_select)        