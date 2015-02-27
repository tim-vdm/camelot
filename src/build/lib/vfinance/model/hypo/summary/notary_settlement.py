#! coding: utf-8

import datetime
import itertools
import logging

from camelot.admin.action import Action
from camelot.core.templates import environment
from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps.update_progress import UpdateProgress
from camelot.core.exception import UserException

LOGGER = logging.getLogger('vfinance.model.hypo.notification.notary_settlement')

from vfinance.view.action_steps.print_preview import PrintJinjaTemplateVFinance
from vfinance.admin.jinja2_filters import filters
from vfinance.admin.translations import Translations
from vfinance.model.financial.notification.utils import generate_qr_code, get_recipient


class NotarySettlement(Action):

    verbose_name = _('Afrekening Notaris')
    template = 'hypo/notary_settlement.html'

    def model_run(self, model_context):
        environment.filters.update(filters)
        for akte in model_context.get_selection():
            hypotheek = akte.beslissing.hypotheek
            signing_agent_found = False
            for signing_agent in itertools.chain(hypotheek.get_roles_at(hypotheek.aanvraagdatum,
                                                                        'borrower_signing_agent'),
                                                 hypotheek.get_roles_at(hypotheek.aanvraagdatum,
                                                                        'lender_signing_agent')):
                signing_agent_found = True
                language = akte.beslissing.hypotheek.taal
                environment.install_gettext_translations(Translations(language))
                yield PrintJinjaTemplateVFinance(self.template,
                                                 context=self.context(akte, signing_agent),
                                                 environment=environment)
            if not signing_agent_found:
                msg = u'No signing agent found for deed {} ({})'
                yield UpdateProgress(detail=msg.format(akte.full_number,
                                                       akte),
                                     blocking=True)

    def context(self, akte, signing_agent):
        hypotheek = akte.beslissing.hypotheek
        if len(signing_agent.bank_accounts) > 0:
            notary_bank_account = unicode(signing_agent.bank_accounts[0])
        else:
            text = u'Notary does not have a bank account'
            raise UserException(text=text,
                                title=u'Missing notary bank account',
                                resolution=u'Please add a bank account number for notary {}'.format(signing_agent))
        return {'now': datetime.datetime.now(),
                'today': datetime.date.today(),
                'title': 'Afrekening Notaris',
                'deed': akte,
                'borrowers': list(hypotheek.get_roles_at(hypotheek.aanvraagdatum, 'borrower')),
                'decision': akte.beslissing,
                'language': akte.beslissing.hypotheek.taal,
                'recipient': get_recipient([signing_agent]),
                'notary_bank_account': notary_bank_account,
                # TODO fill in if simulating or something that invalidates the document
                'invalidating_text': u'',
                'qr_base64': generate_qr_code(akte.full_number)}
