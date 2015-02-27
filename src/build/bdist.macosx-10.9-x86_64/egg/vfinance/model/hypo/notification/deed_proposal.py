# -*- coding: utf-8 -*-

import logging
import os

from camelot.core.conf import settings
from camelot.core.templates import environment
from camelot.core.utils import ugettext_lazy as _
from camelot.view import action_steps

LOGGER = logging.getLogger('vfinance.model.hypo.notification.mortgage_table')

from .aanvaardingsbrief import AanvaardingsBrief
from vfinance.model.financial.notification.environment import TemplateLanguage

class DeedProposal( AanvaardingsBrief ):
  
    verbose_name = _('Akte Voorstel')

    def model_run( self, model_context ):
        import cStringIO
        import zipfile
        for akte in model_context.get_selection():
            taal = akte.beslissing.hypotheek.taal
            beslissing = akte.beslissing
            voorschotten = []
            for gb in beslissing.goedgekeurd_bedrag:
                voorschot = {'goedgekeurd_bedrag':gb}
                voorschotten.append(voorschot)
                  
            context = { 'taal':taal,
                        'akte':akte,
                        'beslissing':beslissing,
                        'voorschotten':voorschotten,
                        # TODO fill in if simulating or something that invalidates the document
                        'invalidating_text': u''}
            context.update( self.context_from_beslissing( beslissing ) )
            with TemplateLanguage( taal ):
                template = environment.get_template( 'hypo/akte_2_%s.xml'%taal )
                document = template.render( context )
                empty_template = os.path.join( settings.CLIENT_TEMPLATES_FOLDER,
                                               'hypo',
                                               'empty_akte.docx' )
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
