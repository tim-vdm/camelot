import os

from camelot.admin.action import Action
from camelot.core.utils import ugettext_lazy as _
from camelot.core.conf import settings
from camelot.view.art import Icon

class ViewLogs( Action ):

    verbose_name = _('View logs')
    tooltip = _('Open the directory with log files')
    icon = Icon('tango/32x32/actions/format-justify-fill.png')

    def model_run( self, model_context ):
        from camelot.view import action_steps
        yield action_steps.OpenFile(os.path.join(settings.LOG_FOLDER,
                                                 settings.LOG_FILENAME))