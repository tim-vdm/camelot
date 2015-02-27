import datetime
import logging

from jinja2 import Markup

from camelot.admin.action import Action
from camelot.core.utils import ugettext_lazy as _

from vfinance.view.action_steps.print_preview import PrintJinjaTemplateVFinance

LOGGER = logging.getLogger('vfinance.model.hypo.summary.decision_document')

class DecisionDocument( Action ):

    verbose_name = _('Summary')
    template = 'hypo/decision_summary.html'

    def model_run( self, model_context ):
        from vfinance.model.financial.notification.environment import TemplateLanguage
        with TemplateLanguage():
            for beslissing in model_context.get_selection():
                pjt = PrintJinjaTemplateVFinance(self.template, 
                                                 context=self.context(beslissing))
                yield pjt

    def context( self, beslissing ):
        # FIXME circular imports:
        from vfinance.model.financial.notification.utils import get_recipient, generate_qr_code
        context = { 'beslissing' : beslissing }
        nodige_schuldsaldos = [ns for ns in beslissing.nodige_schuldsaldo]
        nodige_schuldsaldos.sort(key=lambda ns:ns.natuurlijke_persoon.name)
        context['now'] = datetime.datetime.now()
        context['nodige_schuldsaldos'] = nodige_schuldsaldos
        context['title'] = _('Hypotheek beslissing')
        context['opmerkingen'] = Markup(beslissing.opmerkingen)
        context['state_guarantee'] = beslissing.hypotheek.get_functional_setting_description_at(beslissing.hypotheek.aanvraagdatum, 'state_guarantee')
        # TODO fill in if simulating or something that invalidates the document
        context['invalidating_text'] = u''
        borrowers = beslissing.hypotheek.get_roles_at(beslissing.hypotheek.aanvraagdatum, 'borrower')
        if len(borrowers) > 0:
            context['recipient'] = get_recipient(borrowers)
        context['qr_base64'] = generate_qr_code()
        return context
