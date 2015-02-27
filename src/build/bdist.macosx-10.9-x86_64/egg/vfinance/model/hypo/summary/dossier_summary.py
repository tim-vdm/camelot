import datetime

from camelot.core.utils import ugettext_lazy as _

from vfinance.model.bank.summary.customer_summary import CustomerSummary
from ..visitor.abstract import AbstractHypoVisitor
from vfinance.view.action_steps.print_preview import PrintJinjaTemplateVFinance


class DossierSummary( CustomerSummary ):

    verbose_name = _('Dossier Summary')
    template = 'dossier_summary.html'

    def model_run( self, model_context ):
        # FIXME circular imports:
        from vfinance.model.financial.notification.utils import get_recipient, generate_qr_code
        from vfinance.model.financial.notification.environment import TemplateLanguage
        visitor = AbstractHypoVisitor()
        today = datetime.date.today()
        with TemplateLanguage():
            for dossier in model_context.get_selection():
                customer = visitor.get_customer_at( dossier.goedgekeurd_bedrag, today )
                context = self.context( customer )
                context['now'] = datetime.datetime.now()
                context['startdate'] = dossier.startdatum
                context['full_number'] = dossier.full_number
                borrowers = dossier.get_roles_at(datetime.date.today(), 'borrower')
                if len(borrowers) > 0:
                    context['recipient'] = get_recipient(borrowers)
                context['name'] = dossier.name
                # TODO fill in if simulating or something that invalidates the document
                context['invalidating_text'] = u''
                context['qr_base64'] = generate_qr_code(dossier.full_number)

                yield PrintJinjaTemplateVFinance(self.template,
                                                 context=context)
