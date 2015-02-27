"""
The visitor module contains visitor classes, that visit all
the premium schedules and apply the necessary changes to them,
like applying costs
"""

from account_attribution import AccountAttributionVisitor
from customer_attribution import CustomerAttributionVisitor
from financed_commission import FinancedCommissionVisitor
from fund_attribution import FundAttributionVisitor
from transaction_completion import TransactionCompletionVisitor
from transaction_initiation import TransactionInitiationVisitor
from risk_deduction import RiskDeductionVisitor
from security_quotation import SecurityQuotationVisitor
from security_order_lines import SecurityOrderLinesVisitor
from interest_attribution import InterestAttributionVisitor

available_visitors = [AccountAttributionVisitor,
                      CustomerAttributionVisitor,
                      FinancedCommissionVisitor,
                      FundAttributionVisitor,
                      InterestAttributionVisitor,
                      RiskDeductionVisitor,
                      SecurityQuotationVisitor,
                      SecurityOrderLinesVisitor,
                      TransactionCompletionVisitor,
                      TransactionInitiationVisitor]

__all__ = [v.__name__ for v in available_visitors]
