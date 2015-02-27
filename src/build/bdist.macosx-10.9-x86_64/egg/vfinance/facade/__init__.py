from . import (financial_agreement,
               redemption)

__all__ = [
    financial_agreement.__name__,
    redemption.__name__,
]

from vfinance.model.financial.account import FinancialAccount
from sqlalchemy.orm import sessionmaker

from .redemption import RedemptionAction

FinancialAccount.Admin.form_actions.append(RedemptionAction())
FinancialAccount.Admin.list_actions.append(RedemptionAction())

FacadeSession = sessionmaker(autoflush=False,
                             autocommit=True,
                             expire_on_commit=False)
