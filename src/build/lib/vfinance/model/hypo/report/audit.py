from ...bank.report.audit import AccountingAuditReport

from ..fulfillment import MortgageFulfillment
from ..product import LoanProduct

class HypoAccountingAuditReport(AccountingAuditReport):
    
    product_class = LoanProduct
    fulfillment_class = MortgageFulfillment