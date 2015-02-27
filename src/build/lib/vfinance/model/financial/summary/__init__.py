import datetime


from camelot.view.art import Icon
from camelot.admin.action import Action
from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import PrintHtml
from camelot.view.action_steps import ChangeObject
from camelot.core.templates import environment


class Summary( Action ):
          
    icon = Icon( 'tango/16x16/mimetypes/x-office-document.png' )
    verbose_name = _('Summary')
    template_file = ''
    
    def model_run(self, model_context):
        if not self.template_file:
            raise NotImplementedError('Please specify the template_file in your Summary subclass')
        if hasattr(self, 'options') and self.options is None:
            options = None
        else:
            try:
                options = self.Options()
                yield ChangeObject( options )
            except AttributeError:
                options = None
        obj = model_context.get_object()
        yield PrintHtml( self.html(obj) )
        
    def context(self, obj, recipient=None):
        """:return: a dictionary with objects to be used as context when jinja fills up the html"""
        return {}
    
    def html(self, obj):
        # OPTIONAL if VFinanceStrictUndefined should be acivated 
        #          it can be overruled here
        #          (full path to suggest import)
        # environment.undefined = vfinance.model.financial.notification.environment.VFinanceUndefined
        t = environment.get_template(self.template_file)
        # add document title and date
        context = self.context(obj)
        context['title'] = self.verbose_name
        context['date'] = datetime.datetime.now()
        return t.render(**context)
