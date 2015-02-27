from camelot.core.utils import ugettext_lazy as _

from vfinance.model.financial.notification.transaction_document import TransactionDocument
from vfinance.model.financial.notification.utils import get_recipient
from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.view.action_steps.print_preview import PrintJinjaTemplateVFinance

default_features = ['entry_fee',
                    'premium_taxation_physical_person',
                    'premium_taxation_legal_person',
                    'premium_fee_1',
                    'premium_rate_1']
template = 'financial/transaction_verification_form.html'


class TransactionVerificationForm(TransactionDocument):

    verbose_name = _('Transaction verification form')

    def model_run(self, model_context):
        for step in self.generate_document(model_context):
            yield step

    def generate_document(self, model_context, transaction=None):
        with TemplateLanguage():
            transaction = transaction or model_context.get_object()
            premium_schedule = transaction.get_first_premium_schedule()
            for recipient_role, _broker in premium_schedule.financial_account.get_notification_recipients(transaction.from_date):
                recipient = get_recipient([recipient_role])
                pjt = PrintJinjaTemplateVFinance(template,
                                                 context=self.get_context(transaction,
                                                                          recipient))
                yield pjt
