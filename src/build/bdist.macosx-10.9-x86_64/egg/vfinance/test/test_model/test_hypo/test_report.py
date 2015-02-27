import datetime

import test_beslissing
import test_period

from sqlalchemy.orm import object_session

from camelot.view.action_steps import OpenFile

from vfinance.model.financial.notification import NotificationOptions

from ... import test_case


class NotificationCase(test_case.SessionCase):

    @classmethod
    def setUpClass(cls):
        test_case.SessionCase.setUpClass()
        cls.period_case = test_period.PeriodiekeVerichtingCase('setUp')
        cls.period_case.setUpClass()

    def setUp(self):
        super(NotificationCase, self).setUp()
        self.period_case.setUp()
        self.dossier_case = self.period_case.dossier_case

    def test_fiscaal_attest(self):
        from vfinance.model.hypo.dossier import DossierFeatureApplication
        from vfinance.model.hypo.notification.fiscal_certificate import FiscalCertificate
        # make sure a repayment has been payed
        period = self.period_case.periode
        self.period_case.test_tick_date()
        initial_amount = 314000
        gewestwaarborg = 300
        DossierFeatureApplication(applied_on=self.dossier_case.dossier,
                                  from_date=datetime.date(2000, 1, 1),
                                  described_by='initial_approved_amount',
                                  value=initial_amount)
        DossierFeatureApplication(applied_on=self.dossier_case.dossier,
                                  from_date=datetime.date(2000, 1, 1),
                                  described_by='duration_before_start_date',
                                  value=1)
        object_session(self.dossier_case.dossier).flush()
        object_session(self.dossier_case.dossier).expire_all()
        fiscaal_attest = FiscalCertificate()
        options = NotificationOptions()
        year = period.startdatum.year
        total_repayment = 0
        for repayment in self.dossier_case.dossier.repayments:
            if period.einddatum >= repayment.doc_date >= period.startdatum:
                total_repayment += repayment.kapitaal
        self.assertNotEqual(total_repayment, 0)
        options.from_document_date = datetime.date(year, 1, 1)
        options.thru_document_date = datetime.date(year, 12, 31)
        context = fiscaal_attest.get_context(self.dossier_case.dossier, options)
        self.assertEqual(context['origineel_bedrag'], initial_amount - gewestwaarborg)
        self.assertEqual(context['aktedatum'], datetime.date(2007, 5, 1))
        self.assertEqual(context['betaald_kapitaal'], total_repayment)
        self.assertEqual(context['openstaand_kapitaal'], self.dossier_case.dossier.get_theoretisch_openstaand_kapitaal_at(options.thru_document_date) - gewestwaarborg)
        for step in fiscaal_attest.model_run(self.dossier_case.model_context):
            if isinstance(step, OpenFile):
                with open(step.get_path(), 'r') as f:
                    # test ranking in borrowers roles
                    # first is Celie (Correspondentegem)
                    # second is Alain Francois
                    # added is Marco Carlo
                    self.assertTrue('Correspondentegem' in f)


class ReportCase(test_case.SessionCase):

    def setUp(self):
        super(ReportCase, self).setUp()
        self.beslissing_case = test_beslissing.BeslissingCase('setUp')
        self.beslissing_case.setUp()
    
    def run_report( self, report ):
        from integration.spreadsheet.xls import XlsSpreadsheet
        from vfinance.model.hypo.report_action import FinancialReportAction
        
        options = FinancialReportAction.Options()
        options.from_document_date = datetime.date(2007,1,1)
        options.thru_document_date = datetime.date(2007,12,31)
        options.type = 'obligatie'
        
        sheet = XlsSpreadsheet()
        
        list( report.fill_sheet( sheet, 5, options ) )
        
        sheet.generate_xls( 'test_' + unicode(report.name).replace(' ','_').lower() + '.xls' )
    
    def test_accounting_audit(self):
        from vfinance.model.hypo.report.audit import HypoAccountingAuditReport
        self.run_report( HypoAccountingAuditReport() )
        
    def test_overzicht_aanvragen(self):
        from vfinance.model.hypo.report.overzicht_aanvragen import AanvraagReport
        self.run_report( AanvraagReport() )
        
    def test_overzicht_beslissingen(self):
        from vfinance.model.hypo.report.overzicht_beslissingen import BeslissingReport
        self.run_report( BeslissingReport() )
        
    def test_overzicht_dekkingswaarden(self):
        from vfinance.model.hypo.report.overzicht_dekkingswaarden import CoverageReport
        self.run_report( CoverageReport() )

    def test_overzicht_afkopen(self):
        from vfinance.model.hypo.report.overzicht_afkopen import RedemptionReport
        self.run_report( RedemptionReport() )
        
    def test_overzicht_prorata(self):
        from vfinance.model.hypo.report.overzicht_prorata import ProrataReport
        self.run_report( ProrataReport() )
 
    def test_overzicht_kortingen(self):
        from vfinance.model.hypo.report.overzicht_kortingen import ReductionReport
        self.run_report( ReductionReport() )
        
    def test_overzicht_dossiers(self):
        from vfinance.model.hypo.report.overzicht_dossiers import DossierReport
        self.run_report( DossierReport() )
        
    def test_evolutie(self):
        from vfinance.model.hypo.report.evolutie_report import EvolutieReport
        self.run_report( EvolutieReport() )
        
    def test_einvervaldagen(self):
        from vfinance.model.hypo.report.eindvervaldagen import Expired
        self.run_report( Expired() )       
        
    def test_overzicht_productie(self):
        from vfinance.model.hypo.report.overzicht_productie import ProductieReport
        self.run_report( ProductieReport() )   
        
    def test_overzicht_portefeuille(self):
        from vfinance.model.hypo.report.overzicht_portefeuille import PortefeuilleReport
        self.run_report( PortefeuilleReport() )
        
    def test_overzicht_provisies(self):
        from vfinance.model.hypo.report.overzicht_provisies import ProvisieReport
        self.run_report( ProvisieReport() )
        
    def test_cashflow(self):
        from vfinance.model.hypo.report.cash_flow import CashFlowReport
        self.run_report( CashFlowReport() )        
