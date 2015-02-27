import collections
import datetime

from camelot.core.utils import ugettext_lazy as _
from camelot.admin.action import Action
from camelot.view.action_steps import PrintJinjaTemplate

from sqlalchemy import sql

from ..entry import Entry

customer_data = collections.namedtuple( 'customer_data',
                                        ['name', 'full_account_number', 'customer', 'last_entries',] )

class CustomerSummary( Action ):

    verbose_name = _('Customer Summary')

    def context(self, customer, delta=62, options=None):
        """:param delta: days to look back when displaying recent entries"""
        context = dict()
        now = datetime.datetime.now()
        cutoff_date = None
        if options is not None:
            cutoff_date = options.from_document_date
        else:
            cutoff_date = now.date() - datetime.timedelta(days=delta)
        if customer != None:
            last_entries = list(Entry.query.filter(sql.and_(Entry.account == customer.full_account_number,
                                                            Entry.amount != 0,
                                                            Entry.datum >= cutoff_date)))
            context['customer'] = customer_data( name = customer.name,
                                                 full_account_number = customer.full_account_number,
                                                 last_entries = last_entries,
                                                 customer = customer )
        else:
            context['customer'] = customer_data( name = 'None',
                                                 full_account_number = '',
                                                 last_entries = [],
                                                 customer = None )
        context['now'] = now
        context['title'] = self.verbose_name
        # TODO fill in if simulating or something that invalidates the document
        context['invalidating_text'] = ''
        return context

    def model_run( self, model_context ):
        from vfinance.model.financial.notification.environment import TemplateLanguage
        with TemplateLanguage():
            for customer in model_context.get_selection():
                context = self.context( customer )
                yield PrintJinjaTemplate( 'customer_summary.html', context = context )
