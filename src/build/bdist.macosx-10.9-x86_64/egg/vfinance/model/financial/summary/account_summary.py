'''
Created on Jan 7, 2011

@author: tw55413
'''
import datetime
import copy

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import PrintJinjaTemplate, ChangeObject
from camelot.view.controls import delegates

from vfinance.model.financial.notification.account_document import FinancialAccountDocument
from vfinance.model.financial.summary import Summary
from vfinance.model.bank.summary import CustomerSummary
from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.model.financial.notification import NotificationOptions


def notification_type_choices_tuple(*args):
    return [(action, action.name) for action in args]

class FinancialAccountSummary(CustomerSummary):

    verbose_name = _('Account Summary')
    name = _('Summary')
    options = None

    def context(self, account, options, recipient=None):
        from utils import get_premium_data
        thru_book_date = None
        if options:
            from_document_date = options.from_document_date
            thru_book_date = options.thru_book_date
        premiums, premium_schedules, total = get_premium_data(account, options)
        context = {
            'now': datetime.datetime.now(),
            'title': unicode(self.verbose_name),
            'account': account,
            'premiums': premiums,
            'premium_schedules': premium_schedules,
            'thru_book_date': thru_book_date,
            'from_document_date': from_document_date,
            'total': total,
            'clauses':account.get_items_at(options.notification_date),
            # TODO fill in if simulating or something that invalidates the document
            'invalidating_text': u''
        }
        customer = account.subscription_customer_at(datetime.date.today())
        context.update(super(FinancialAccountSummary, self).context(customer, options=options))
        return context


    def model_run(self, model_context, options, account=None):
        financial_account = account or model_context.get_object()
        context = self.context(financial_account, options=options)
        with TemplateLanguage():
            yield PrintJinjaTemplate('financial_account.html',
                                     context=context)


class FinancialAccountPremiumScheduleSummary(Summary):

    verbose_name = _('Premium Schedule Summary')
    name = _('Summary')

    class Options(NotificationOptions):

        def __init__(self):
            NotificationOptions.__init__(self)
            self.notification_type_choices = notification_type_choices_tuple(FinancialAccountPremiumScheduleSummary())
            self.notification_type = self.notification_type_choices[0][0]

        class Admin(NotificationOptions.Admin):
            field_attributes = copy.copy(NotificationOptions.Admin.field_attributes)
            field_attributes['notification_types'] = {'editable':False}


    def context(self, premium_schedule, options, recipient=None):
        from utils import get_premium_schedule_data

        context = get_premium_schedule_data(premium_schedule, options)._asdict()
        context['account'] = premium_schedule.financial_account
        context['now'] = datetime.datetime.now()
        context['title'] = unicode(self.verbose_name)
        context['from_document_date'] = options.from_document_date
        # TODO fill in if simulating or something that invalidates the document
        context['invalidating_text'] = u''
        return context

    def model_run(self, model_context, options=None):
        options = self.Options()
        options.from_document_date = datetime.date(datetime.date.today().year-1, 1, 1)
        yield ChangeObject(options)
        premium_schedule = model_context.get_object()
        context = self.context(premium_schedule, options)
        with TemplateLanguage():
            yield PrintJinjaTemplate('financial_account_premium_schedule.html',
                                     context=context)


class FinancialTransactionAccountsSummary(FinancialAccountSummary):

    verbose_name = _('Transaction Accounts Summary')

    class Options(NotificationOptions):

        def __init__(self):
            NotificationOptions.__init__(self)
            self.notification_type_choices = notification_type_choices_tuple(FinancialAccountSummary())
            self.notification_type = self.notification_type_choices[0][0]

        class Admin(NotificationOptions.Admin):
            field_attributes = copy.copy(NotificationOptions.Admin.field_attributes)
            field_attributes['notification_type'] = {'choices':lambda obj:obj.notification_type_choices,
                                                     'editable':False,
                                                     'nullable':False,
                                                     'delegate':delegates.ComboBoxDelegate}

    def model_run(self, model_context, options=None):
        options = self.Options()
        options.from_document_date = datetime.date(datetime.date.today().year-1, 1, 1)
        yield ChangeObject(options)
        transaction = model_context.get_object()
        aggregated_context = {
            'now': datetime.datetime.now(),
            'title': unicode(self.verbose_name),
            'financial_accounts': [],
            'from_document_date': options.from_document_date,
            # TODO fill in if simulating or something that invalidates the document
            'invalidating_text': u''
        }
        for financial_account in transaction.get_financial_accounts():
            aggregated_context['financial_accounts'].append(self.context(financial_account, options))
        with TemplateLanguage():
            yield PrintJinjaTemplate('financial_transaction_accounts.html',
                                     context=aggregated_context)


class FinancialAccountEvolution(Summary, FinancialAccountDocument):

    verbose_name = _('Account Evolution')
    name = _('Evolution')

    def context(self, account, recipient=None, options=None):
        context = self.get_context(account, recipient=recipient, options=options)
        context['date'] = datetime.datetime.now()
        context['title'] = unicode(self.verbose_name)
        # TODO fill in if simulating or something that invalidates the document
        context['invalidating_text'] = u''
        return context

    def model_run(self, model_context, account=None, options=None):
        financial_account = account or model_context.get_object()
        context = self.context(financial_account, options=options)
        context['now'] = datetime.datetime.now()
        context['title'] = unicode(self.verbose_name)
        with TemplateLanguage():
            yield PrintJinjaTemplate('evolution.html',
                                     context=context)


class FinancialAccountOverview(Summary):

    verbose_name = _('Account Overview')
    options = None

    class Options(NotificationOptions):

        def __init__(self):
            NotificationOptions.__init__(self)
            # self.notification_type_choices = [(action, action.name) for action in [FinancialAccountSummary(), FinancialAccountEvolution()]]
            self.notification_type_choices = notification_type_choices_tuple(FinancialAccountSummary(), FinancialAccountEvolution())
            self.notification_type = self.notification_type_choices[0][0]

    def model_run(self, model_context, options=None, account=None):
        options = self.Options()
        options.from_document_date = datetime.date(datetime.date.today().year-1, 1, 1)
        yield ChangeObject(options)
        for step in options.notification_type.model_run(model_context, account=account, options=options):
            yield step

