import logging

from camelot.core.utils import ugettext_lazy as _
from camelot.admin.action import Action
from camelot.view import action_steps

from vfinance.facade.financial_agreement import FinancialAgreementFacade
from vfinance.facade import FacadeSession


logger = logging.getLogger(__name__)

class CreditInsuranceProposalAction(Action):

    verbose_name = _('Create Proposal')

    def model_run(self, model_context):
        facade_session = FacadeSession()
        agreement = FinancialAgreementFacade(_session=facade_session)
        yield action_steps.OpenFormView([agreement], model_context.admin.get_related_admin(FinancialAgreementFacade))
