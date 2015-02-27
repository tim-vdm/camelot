# -*- coding: utf-8 -*-
import datetime
import cStringIO
import logging
import os
import zipfile

from jinja2.exceptions import TemplateNotFound

from camelot.admin.action import Action
from camelot.core.utils import ugettext_lazy as _
from camelot.core.conf import settings
from camelot.core.templates import environment
from camelot.view import action_steps

from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.view.action_steps import PrintJinjaTemplateVFinance
from vfinance.model.financial.notification.premium_schedule_document import loan_data
from vfinance.model.financial.notification.utils import generate_qr_code
from integration.tinyerp.convenience import unique

LOGGER = logging.getLogger('vfinance.model.hypo.notification.aanvaardingsbrief')

class Ondertekenaar(object):
    """Helper class voor in aanvaardingsbrieven"""
  
    def __init__(self, full_name, function=u''):
        self.full_name = full_name
        self.function = function
      
    def __cmp__(self, other):
        return cmp(self.__hash__(), other.__hash__())
    
    def __hash__(self):
        return self.__unicode__().__hash__()
    
    def __unicode__(self):
        return (self.full_name + self.function)
    
class AanvaardingsBrief( Action ):

    verbose_name = _('Aanvaardingsbrief')

    def context_from_beslissing( self, beslissing ):
        from vfinance.model.financial.notification.utils import get_recipient

        def ondertekenaars_van_dual_person(dual_person):
            if dual_person.natuurlijke_persoon:
                yield Ondertekenaar(dual_person.natuurlijke_persoon.full_name)
            elif dual_person.rechtspersoon:
                yield Ondertekenaar(dual_person.rechtspersoon.full_name)
            
        hypotheek = beslissing.hypotheek
        hypotheekstellers = []
        ondertekenaars = []
        hypothecaire_inschrijving, hypothecair_mandaat = 0, 0
        aanvragers_natuurlijke_persoon = []
        aanvragers_rechtspersoon = []
        aanvragers = hypotheek.get_roles_at(hypotheek.aanvraagdatum, 'borrower')
        for aanvrager in aanvragers:
          ondertekenaars.extend(list(ondertekenaars_van_dual_person(aanvrager)))
          if aanvrager.natuurlijke_persoon:
            aanvragers_natuurlijke_persoon.append(aanvrager.natuurlijke_persoon.id)
          if aanvrager.rechtspersoon:
            aanvragers_rechtspersoon.append(aanvrager.rechtspersoon.id)
        for goed_aanvraag in hypotheek.gehypothekeerd_goed:
          if goed_aanvraag.hypothecaire_inschrijving:
            hypothecaire_inschrijving += goed_aanvraag.hypothecaire_inschrijving
          if goed_aanvraag.hypothecair_mandaat:
            hypothecair_mandaat += goed_aanvraag.hypothecair_mandaat      
          for eigenaar in goed_aanvraag.te_hypothekeren_goed.eigenaar:
            if ((eigenaar.natuurlijke_persoon and eigenaar.natuurlijke_persoon.id not in aanvragers_natuurlijke_persoon) or  
                (eigenaar.rechtspersoon and eigenaar.rechtspersoon.id not in aanvragers_rechtspersoon)):
              hypotheekstellers.append(eigenaar)
              ondertekenaars.extend(list(ondertekenaars_van_dual_person(eigenaar)))
        for borgsteller in hypotheek.get_roles_at(hypotheek.aanvraagdatum, 'guarantor'):
          if borgsteller.natuurlijke_persoon:
            ondertekenaars.append(Ondertekenaar(borgsteller.natuurlijke_persoon.full_name))
        hypotheekstellers = unique(hypotheekstellers)
        ondertekenaars = unique(ondertekenaars)
        aanvragers_natuurlijke_persoon = unique(aanvragers_natuurlijke_persoon)
        aanvragers_rechtspersoon = unique(aanvragers_rechtspersoon)
        context = locals()
        context['beroepskrediet'] = 'andere' in hypotheek.wettelijk_kader
        context['recipient'] = get_recipient(aanvragers)
        return context
        
    def context_from_aanvaarding( self, aanvaarding ):
        beslissing = aanvaarding.beslissing
        context = locals()
        context.update( self.context_from_beslissing( beslissing ) )
        # add elements for default html template
        # cf. model_run word_template is None
        context['decision_date'] = aanvaarding.beslissing.datum
        context['now'] = datetime.datetime.now()
        context['full_number'] = aanvaarding.full_number
        # TODO fill in if simulating or something that invalidates the document
        context['invalidating_text'] = u''
        # DEPRECATED in favour of recipient>>>
        context['name'] = ', '.join([ondertekenaar.full_name for ondertekenaar in context['ondertekenaars']])
        context['street'] = context['aanvragers'][0].straat
        context['zipcode'] = context['aanvragers'][0].postcode
        context['city'] = context['aanvragers'][0].gemeente
        # <<<

        return context
    
    def model_run( self, model_context ):     
        for i, aanvaarding in enumerate( model_context.get_selection() ):
            yield action_steps.UpdateProgress( i, model_context.selection_count )
            taal = aanvaarding.beslissing.hypotheek.taal
            with TemplateLanguage( taal ):
                context = self.context_from_aanvaarding( aanvaarding )
                #
                # minimize try catch here to prevent artefacts from
                # template.render method
                #
                word_template = None
                try:
                    # 2 for jinja2
                    word_template = environment.get_template( 'hypo/aanvaardingsbrief_2_%s.xml'%taal )
                except TemplateNotFound:
                    pass

                if word_template is not None:
                    document = word_template.render( context )
                    empty_template = os.path.join( settings.CLIENT_TEMPLATES_FOLDER,
                                                   'bank',
                                                   'empty_letter_fr.docx' )
                    output = cStringIO.StringIO()
                    input_zip = zipfile.ZipFile( open(empty_template, 'rb'), 'r', zipfile.ZIP_DEFLATED )
                    output_zip = zipfile.ZipFile( output, 'w' )
                    for path in input_zip.namelist():
                        if path == 'word/document.xml':
                            output_zip.writestr( path, document.encode('utf-8') )
                        else:  
                            output_zip.writestr( path, input_zip.read( path ) )
                    output_zip.close()
                    input_zip.close()
                    yield action_steps.OpenString( output.getvalue(), suffix='.docx' )
                else:
                    loans_data = []
                    for goedgekeurd_bedrag in aanvaarding.beslissing.goedgekeurd_bedrag:
                        loans_data.append(loan_data(loan_amount=goedgekeurd_bedrag.bedrag.bedrag, 
                                                    interest_rate=goedgekeurd_bedrag.goedgekeurde_jaarlijkse_kosten,
                                                    periodic_interest=goedgekeurd_bedrag.goedgekeurde_rente, 
                                                    number_of_months=goedgekeurd_bedrag.goedgekeurde_looptijd, 
                                                    type_of_payments=goedgekeurd_bedrag.goedgekeurd_type_aflossing, 
                                                    payment_interval=goedgekeurd_bedrag.goedgekeurd_terugbetaling_interval, 
                                                    repayment_amount=goedgekeurd_bedrag.goedgekeurde_aflossing,
                                                    number_of_repayments='NOG TE BEREKENEN',
                                                    starting_date=goedgekeurd_bedrag.aanvangsdatum, 
                                                    credit_institution=None))
                    context['loans_data'] = loans_data
                    context['qr_base64'] = generate_qr_code(context['full_number'])
                    # hack, replace/remove when proper locale codes are implemented
                    locale_code = 'nl_BE'
                    if taal == 'fr':
                        locale_code = 'fr_BE'
                    template = environment.get_template('hypo/acceptance_letter_{}.html'.format(locale_code))
                    yield PrintJinjaTemplateVFinance(template,
                                                     context=context,
                                                     environment=environment)
