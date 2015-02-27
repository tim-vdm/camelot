import datetime

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import PrintJinjaTemplate

from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.model.financial.notification.transaction_document import TransactionDocument
from vfinance.model.financial.summary import Summary


class FinancialTransactionSummary(Summary, TransactionDocument):

    verbose_name = _('Financial Transaction Summary')

    def context(self, obj):
        return self.get_context(obj, None, None)

    def model_run(self, model_context):
        obj = model_context.get_object()
        context = self.context(obj)
        context['date'] = datetime.datetime.now()
        context['title'] = self.verbose_name
        context['invalidating_text'] = u''
        with TemplateLanguage():
            yield PrintJinjaTemplate('transaction.html',
                                     context=context)
