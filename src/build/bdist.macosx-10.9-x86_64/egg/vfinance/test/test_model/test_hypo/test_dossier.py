# coding=utf-8
import datetime
from decimal import Decimal as D

import test_akte

from camelot.test.action import MockModelContext

from vfinance.model.bank.invoice import InvoiceItem
from vfinance.model.hypo.dossier import (DossierFunctionalSettingApplication,
                                         Korting, SyncVenice)
from vfinance.model.hypo.notification.dossier_notification import DossierNotification

from ... import test_case

class DossierCase(test_case.SessionCase):

    @classmethod
    def setUpClass(cls):
        test_case.SessionCase.setUpClass()
        cls.akte_case = test_akte.AkteCase('setUp')
        cls.akte_case.setUpClass()

    def setUp(self):
        super(DossierCase, self).setUp()
        self.akte_case.setUp()
        self.akte_case.akte.datum_verlijden = test_akte.akte_data_datum_verlijden
        self.akte_case.test_voer_door()
        for i,goedgekeurd_bedrag in enumerate( self.akte_case.akte.beslissing.goedgekeurd_bedrag ):
            setattr(self, 'goedgekeurd_bedrag_%i'%(i+1), goedgekeurd_bedrag)
            setattr(self, 'dossier_%i'%(i+1), goedgekeurd_bedrag.dossier)
            DossierFunctionalSettingApplication(applied_on = goedgekeurd_bedrag.dossier,
                                                described_by = 'direct_debit_batch_4',
                                                from_date = goedgekeurd_bedrag.dossier.originele_startdatum )
        self.dossier = self.dossier_1
        self.model_context = MockModelContext()
        self.model_context.obj = self.dossier
        DossierFunctionalSettingApplication.query.session.flush()

    def test_sync(self):
        sync = SyncVenice()
        list(sync.model_run(self.model_context))

    def test_notification_context(self):
        # TODO test with multiple subscribers, ranking
        dossier_notification = DossierNotification()
        context = dossier_notification.get_context(self.dossier, datetime.date(2007, 6, 1))
        self.assertEqual(context['now'].year, datetime.datetime.now().year)
        self.assertTrue('Ms. Celie Dehaen' in [addressee.full_name for addressee in context['recipient'].addressees])
        self.assertEqual(context['recipient'].street1, 'Correspondentielaan 33')
        self.assertEqual(context['recipient'].city_code, '3333')
        self.assertEqual(context['recipient'].city, u'Correspondentegem')
        self.assertEqual(context['recipient'].country, u'Belgium')

    def test_dossier_running( self ):
        self.assertEqual( self.dossier_1.state, 'running')
        bijkomende_waarborg = self.akte_case.aanvaarding_case.beslissing_case.request_case.guarantee_case.bijkomende_waarborg
        self.assertEqual( self.dossier_1.startdatum, test_akte.akte_data_datum_verlijden)
        self.assertEqual( self.dossier_1.get_functional_setting_description_at(self.dossier_1.startdatum, 'state_guarantee'), 'walloon_region_guarantee' )
        self.assertEqual( self.dossier_2.get_functional_setting_description_at(self.dossier_2.startdatum, 'state_guarantee'), 'walloon_region_guarantee' )
        self.assertEqual( self.dossier_1.get_applied_feature_value_at(self.dossier_1.startdatum, 'state_guarantee', 0), 300 )
        self.assertEqual( self.dossier_2.get_applied_feature_value_at(self.dossier_2.startdatum, 'state_guarantee', 0), 0 )
        self.assertEqual( self.dossier_1.bijkomende_waarborgen[0].bijkomende_waarborg_id, bijkomende_waarborg.id )
        self.assertEqual( self.dossier_2.bijkomende_waarborgen[0].bijkomende_waarborg_id, bijkomende_waarborg.id )
        self.assertTrue( len( self.dossier.direct_debit_mandates ) )

    def test_dossier_summary( self ):
        from vfinance.model.hypo.summary import DossierSummary
        dossier_summary = DossierSummary()
        list( dossier_summary.model_run( self.model_context ) )

    def test_dossier_sheet( self ):
        from vfinance.model.hypo.notification.rappel_sheet import DossierSheet
        dossier_sheet = DossierSheet()
        list( dossier_sheet.model_run( self.model_context ) )

    def test_dossier_kost( self ):
        dossier_kost = InvoiceItem(dossier = self.dossier,
                                   doc_date = datetime.date(2007,9,11),
                                   item_description = 'verzekering',
                                   amount=250)
        self.assertFalse(dossier_kost.laatste_domiciliering)
        dossier_kost.button_voeg_toe_aan_domiciliering()
        # verifieer of dossier kost in domicil zit
        self.assertTrue(dossier_kost.laatste_domiciliering)
    
    def test_reduction(self):
        Korting(dossier=self.dossier,
                valid_date_start=datetime.date(2007,1,1),
                valid_date_end=datetime.date(2400,12,31),
                datum=datetime.date.today(),
                rente=D('0.05001'),
                type='per_aflossing')
        self.session.flush()
        reductions = self.dossier.get_reductions_at(datetime.date(2008,1,1),
                                                    D(100000))
        reduction = sum((amount for _type, amount in reductions), D(0))
        self.assertEqual(reduction, D('50.01'))

    def tearDown(self):
        for melding in self.dossier_1.melding_nbb:
          melding.state = 'deletable'
          melding.delete()
        for melding in self.dossier_2.melding_nbb:
          melding.state = 'deletable'
          melding.delete()
        self.akte_case.tearDown()
