from commission import CommissionReport
from detailed_valuation import DetailedValuationReport
from movements import MovementsReport
from valuation import ValuationReport
from pending import PendingAgreementsReport
from audit import FinancialAccountingAuditReport
from units import UnitReport
from roles import AccountRolesReport
from coverages import InsuredCoveragesReport
from interest import InterestAttributionReport
from orderlines import OrderlinesReport

available_reports = [FinancialAccountingAuditReport,
                     AccountRolesReport,
                     CommissionReport,
                     DetailedValuationReport,
                     InsuredCoveragesReport,
                     MovementsReport,
                     PendingAgreementsReport,
                     UnitReport,
                     ValuationReport,
                     InterestAttributionReport,
                     OrderlinesReport,
                     ]
