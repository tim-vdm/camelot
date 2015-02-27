from camelot.admin.action import Action
from camelot.core.utils import ugettext_lazy as _
from camelot.view import art, action_steps

class DisconnectVenice( Action ):
    
    verbose_name = _('Venice Disconnect')
    icon = art.Icon('tango/22x22/status/network-offline.png')
    
    def model_run( self, model_context ):
        yield action_steps.UpdateProgress( text = _('Closing Venice connections') )
        from integration.venice.venice import clear_com_object_cache
        clear_com_object_cache()
