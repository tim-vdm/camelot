from ...bank.report.audit import AccountingAuditReport

from ..premium import FinancialAccountPremiumFulfillment as FAPF
from ..product import FinancialProduct

class FinancialAccountingAuditReport(AccountingAuditReport):
    
    product_class = FinancialProduct
    fulfillment_class = FAPF
