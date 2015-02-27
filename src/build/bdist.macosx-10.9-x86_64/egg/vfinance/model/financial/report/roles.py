from sqlalchemy import sql

from camelot.core.utils import ugettext_lazy as _

from ...bank.report.roles import AbstractRolesReport

from ..account import FinancialAccount, FinancialAccountRole
from ..premium import FinancialAccountPremiumSchedule

class AccountRolesReport( AbstractRolesReport ):
    
    name = _('Account Roles')

    roles_class = FinancialAccountRole
    schedule_class = FinancialAccountPremiumSchedule
    dossier_class = FinancialAccount
    role_attributes = ['surmortality']

    def filter(self, roles_class, schedule_class, dossier_class):
        return sql.and_( roles_class.financial_account_id == dossier_class.id,
                         schedule_class.financial_account_id == dossier_class.id )
