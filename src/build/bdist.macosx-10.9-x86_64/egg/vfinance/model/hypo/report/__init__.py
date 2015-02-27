from audit import HypoAccountingAuditReport
from fiscal_certificate import FiscalCertificateReport
from overzicht_aanvragen import AanvraagReport
from overzicht_beslissingen import BeslissingReport
from overzicht_dekkingswaarden import CoverageReport
from overzicht_productie import ProductieReport
from cash_flow import CashFlowReport
from overzicht_portefeuille import PortefeuilleReport
from overzicht_prorata import ProrataReport
from overzicht_provisies import ProvisieReport
from overzicht_kortingen import ReductionReport
from overzicht_afkopen import RedemptionReport
from overzicht_dossiers import DossierReport
from evolutie_report import EvolutieReport
from eindvervaldagen import Expired
from properties import PropertiesReport
from roles import DossierRolesReport

available_reports = [ AanvraagReport,
                      HypoAccountingAuditReport,
                      FiscalCertificateReport,
                      BeslissingReport,
                      CoverageReport,
                      DossierReport,
                      DossierRolesReport,
                      PortefeuilleReport,
                      ProductieReport,
                      PropertiesReport,
                      ProrataReport,
                      ProvisieReport,
                      ReductionReport,
                      RedemptionReport,
                      EvolutieReport,
                      Expired,
                      CashFlowReport,
                      ]