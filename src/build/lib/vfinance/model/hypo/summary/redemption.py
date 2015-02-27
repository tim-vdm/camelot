import datetime

from camelot.core.utils import ugettext_lazy as _
from camelot.core.templates import environment
from camelot.admin.action import Action

from vfinance.view.action_steps.print_preview import PrintJinjaTemplateVFinance
from vfinance.admin.jinja2_filters import filters
from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.model.hypo.notification.dossier_notification import DossierNotification


class RedemptionAction(Action, DossierNotification):

    verbose_name = _('Redemption document')
    template = 'hypo/redemption.html'

    def model_run( self, model_context ):
        # FIXME circular imports:
        from vfinance.model.financial.notification.utils import get_recipient, generate_qr_code
        redemption = model_context.get_object()
        environment.filters.update(filters)
        with TemplateLanguage(redemption.dossier.taal):
            context = self.get_context(redemption.dossier, redemption.datum)
            context['redemption'] = redemption
            context['now'] = datetime.datetime.now()
            context['title'] = _('Terugbetaling')
            context['full_number'] = redemption.full_number
            context['qr_base64'] = generate_qr_code(redemption.full_number)
            # TODO fill in if simulating or something that invalidates the document
            context['invalidating_text'] = u''
            aanvragers = redemption.dossier.get_roles_at(redemption.datum, 'borrower')
            if len(aanvragers) > 0:
                context['recipient'] = get_recipient(aanvragers)

            pjt = PrintJinjaTemplateVFinance(self.template, 
                                             context = context,
                                             environment = environment)
            # margins are set by PrintJinjaTemplateVFinance now
            # pjt.margin_left = 10
            # pjt.margin_top = 10
            # pjt.margin_right = 10
            # pjt.margin_bottom = 10
            yield pjt