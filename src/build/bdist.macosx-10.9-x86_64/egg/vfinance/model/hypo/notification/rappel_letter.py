# -*- coding: utf-8 -*-
import datetime

import collections
from decimal import Decimal as D
import itertools
import logging

from camelot.core.utils import ugettext_lazy as _
from camelot.admin.action import Action
from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.model.financial.notification.utils import generate_qr_code
from vfinance.view.action_steps.print_preview import PrintJinjaTemplateVFinance

LOGGER = logging.getLogger('vfinance.model.hypo.notification.rappel_letter')


class RappelLetter( Action ):

    verbose_name = _('Rappel Brief')

    def model_run( self, model_context ):
        from vfinance.model.financial.notification.utils import get_recipient
        for brief in model_context.get_selection():
            dossier = brief.dossier
            datum = brief.doc_date
            context = dict( intrest_b = '%.2f'%D(dossier.goedgekeurd_bedrag_nieuw.goedgekeurde_intrest_b),
                            intrest_a = '%.4f'%D(dossier.goedgekeurd_bedrag_nieuw.goedgekeurde_intrest_a),
                            id = '%s / %s'%(dossier.nummer,brief.id), 
                            nummer_dossier = dossier.nummer, 
                            aantal_dagen = 14, 
                            aantal_dagen_wanbetaling = 14, 
                            datum = '%s/%s/%s'%(datum.day, datum.month, datum.year) )
            # print letters in rank order
            letters = collections.OrderedDict()
            for recipient in itertools.chain(dossier.get_roles_at(datum, 'borrower'),
                                             dossier.get_roles_at(datum, 'guarantor')):
                address_key = ( recipient.straat or '', recipient.postcode or '', recipient.gemeente or '', recipient.taal or '' )
                letters.setdefault( address_key, []).append( recipient )
            for i, ( ( straat, postcode, gemeente, taal ), recipients ) in enumerate( letters.items() ):
                if taal not in ['nl', 'fr']:
                    # we only have nl and fr templates anyway ...
                    taal = 'nl'
                with TemplateLanguage(taal):
                    context['now'] = datetime.datetime.now()
                    context['title'] = _('Rappel brief')
                    context['full_number'] = dossier.full_number
                    context['qr_base64'] = generate_qr_code()
                    # TODO fill in if simulating or something that invalidates the document
                    context['invalidating_text'] = u''
                    # 
                    # FIXME
                    # additional context elements
                    # 
                    context['date_last_reminder'] = ''
                    context['total_amount'] = ''
                    context['recipient'] = get_recipient(recipients)
                    yield PrintJinjaTemplateVFinance('hypo/reminder_level_{0}_{1}_BE.html'.format(brief.rappel_level, taal), 
                                                     context=context)
