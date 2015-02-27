import datetime
import logging

from camelot.admin.action import Action
from camelot.core.utils import ugettext_lazy as _
from camelot.core.templates import environment

from vfinance.admin.jinja2_filters import filters
from vfinance.admin.translations import Translations
from vfinance.view.action_steps.print_preview import PrintJinjaTemplateVFinance

LOGGER = logging.getLogger('vfinance.model.hypo.summary.decision_document')


class CreditApplicationVerification( Action ):

    verbose_name = _('Application verification')
    template = 'hypo/credit_application_verification_{0}_BE.html'

    def model_run( self, model_context ):
        environment.filters.update(filters)
        mortgage = model_context.get_object()
        language = mortgage.taal
        environment.install_gettext_translations(Translations(language))
        pjt = PrintJinjaTemplateVFinance(self.template.format(language), 
                                         context=self.context(mortgage),
                                         environment=environment)
        # margins are set by PrintJinjaTemplateVFinance now
        # pjt.margin_left = 10
        # pjt.margin_top = 10
        # pjt.margin_right = 10
        # pjt.margin_bottom = 10
        yield pjt

    def context( self, mortgage ):
        # FIXME circular imports:
        from vfinance.model.financial.notification.utils import get_recipient, generate_qr_code
        context = { 'mortgage' : mortgage }
        context['now'] = datetime.datetime.now()
        context['title'] = _('Hypotheek aanvraag')
        borrowers = mortgage.get_roles_at(mortgage.aanvraagdatum, 'borrower')
        if len(borrowers) > 0:
            context['recipient'] = get_recipient(borrowers)
        # TODO fill in if simulating or something that invalidates the document
        context['invalidating_text'] = u''
        context['qr_base64'] = generate_qr_code(mortgage.full_number)
        return context


class TestDoc(Action):

    verbose_name = _('Test')
    template = 'hypo/test.html'

    def model_run( self, model_context ):
        pjt = PrintJinjaTemplateVFinance(self.template,
                                         context = {'now': datetime.datetime.now()})
        # margins are set by PrintJinjaTemplateVFinance now
        # pjt.margin_left = 10
        # pjt.margin_top = 10
        # pjt.margin_right = 10
        # pjt.margin_bottom = 10
        yield pjt
