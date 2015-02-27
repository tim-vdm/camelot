import copy
import datetime
import logging
import tempfile
import os

from camelot.admin.action import Action
from camelot.core.conf import settings
from camelot.core.utils import ugettext_lazy as _
from camelot.view.art import Icon
from camelot.view import action_steps
from camelot.view.controls import delegates

from .constants import wettelijke_kaders
from .dossier import Dossier
from ..financial.notification import NotificationOptions
from notification.fiscal_certificate import FiscalCertificate
from notification.mortgage_table import MortgageTable

LOGGER = logging.getLogger('vfinance.model.hypo.document_action')

hypo_notifications = [FiscalCertificate(),
                      MortgageTable()]

class HypoNotificationOptions( NotificationOptions ):
    
    def __init__( self ):
        super( HypoNotificationOptions, self ).__init__()
        self.notification_type_choices = [(n, n.verbose_name) for n in hypo_notifications]
        self.from_document_date = datetime.date( self.notification_date.year - 1, 1, 1 )
        self.thru_document_date = datetime.date( self.notification_date.year - 1,12,31 )
        self.wettelijk_kader = None
        self.output_dir = None
        
    class Admin( NotificationOptions.Admin ):
        form_display = NotificationOptions.Admin.form_display + ['wettelijk_kader']
        field_attributes = copy.copy( NotificationOptions.Admin.field_attributes )
        field_attributes['wettelijk_kader'] = {'choices':[(None, _('All'))] + wettelijke_kaders,
                                               'editable':True,
                                               'delegate':delegates.ComboBoxDelegate}
        
class HypoDocumentWizardAction(Action):
    
    verbose_name = _('Mortgage documents')
    icon = Icon( 'tango/22x22/actions/document-print.png' )
    
    def model_run( self, model_context ):
        options = HypoNotificationOptions()
        yield action_steps.ChangeObject(options)
        if options.output_type != 0:
            if options.output_dir is None:
                options.output_dir = tempfile.mkdtemp(dir=settings.CLIENT_TEMP_FOLDER)
            if not os.path.exists(options.output_dir):
                os.mkdir(options.output_dir)
        for step in options.notification_type.generate_documents(model_context, options):
            yield step

Dossier.Admin.list_actions.append(HypoDocumentWizardAction())
Dossier.Admin.form_actions.append(HypoDocumentWizardAction())
