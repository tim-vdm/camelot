'''
Created on July 5, 2011

'''

import logging
import copy

from camelot.admin.action import Action
from camelot.core.utils import ugettext_lazy as _
from camelot.view.controls import delegates
from camelot.view.art import Icon
from camelot.view import action_steps

from sqlalchemy import sql

from vfinance.model.financial.agreement import FinancialAgreement
from vfinance.model.financial.fund import FinancialAccountFundDistribution
from vfinance.model.financial.notification import NotificationOptions
from vfinance.model.financial.notification.account_document import FinancialAccountDocument
from vfinance.model.financial.package import FinancialPackage
from vfinance.model.financial.premium import FinancialAccountPremiumSchedule, FinancialAgreementPremiumSchedule
from vfinance.model.financial.security import FinancialSecurity
from vfinance.model.financial.constants import notification_types
from vfinance.model.financial.account import FinancialAccount
from vfinance.model.financial.visitor.abstract import AbstractVisitor, FinancialBookingAccount

LOGGER = logging.getLogger('vfinance.model.financial.documents')

def get_package_choices(obj):
    return [(None,u'All')] + [(p.id, p.name) for p in FinancialPackage.query.all()]

def get_fund_choices(obj):
    return [(None,u'All')] + [(p.id, p.name) for p in FinancialSecurity.query.all()]

class FinancialDocumentWizardAction(Action):
    
    verbose_name = _('Financial documents')
    icon = Icon( 'tango/22x22/actions/document-print.png' )
    
    class Options( NotificationOptions ):

        def __init__(self):
            NotificationOptions.__init__( self )
            self.notification_type_choices = [(notification_type,notification_type.replace('-',' ').capitalize()) for (id,notification_type,related_to,ft) in notification_types]
            self.package = None
            self.fund = None
            self.notification_type = 'account-state'
            self.exclude_empty_accounts = True
            self.origin = None


        class Admin(NotificationOptions.Admin):
            form_display = ['package', 'fund', 'exclude_empty_accounts', 'origin'] + NotificationOptions.Admin.form_display

            field_attributes = copy.copy(NotificationOptions.Admin.field_attributes)
            field_attributes['package'] = {'choices':get_package_choices,
                                           'delegate':delegates.ComboBoxDelegate,
                                           'editable':True}
            field_attributes['fund'] = {'choices':get_fund_choices,
                                        'delegate':delegates.ComboBoxDelegate,
                                        'editable':True}
            field_attributes['exclude_empty_accounts'] = {'tooltip':'Exclude accounts with no value at the document thru date',
                                                          'delegate':delegates.BoolDelegate,
                                                          'editable':True}
            field_attributes['origin'] = {'editable':True}

    class Context( object ):

        def __init__(self, query, options, visitor):
            self.query = query
            self.options = options
            self.visitor = visitor
            self.selection_count = query.count()

        def get_selection(self):
            for account in self.query.yield_per(100).all():
                if self.options.exclude_empty_accounts:
                    value = 0
                    for premium_schedule in account.premium_schedules:
                        booking_accounts = set( [FinancialBookingAccount('uninvested')] )
                        for fund_distribution in premium_schedule.fund_distribution:
                            booking_accounts.add( FinancialBookingAccount( 'fund', fund_distribution.fund ) )
                        for booking_account in booking_accounts:
                            value += self.visitor.get_total_amount_until( premium_schedule,
                                                                          thru_document_date = self.options.thru_document_date,
                                                                          account = booking_account
                                                                        )[0]
                    if value == 0:
                        continue
                yield account


    def model_run( self, model_context ):

        options = self.Options()
        yield action_steps.ChangeObject(options)

        for step in self.generate_documents(options):
            yield step

    def generate_documents(self, options):

        query = FinancialAccount.query.filter( FinancialAccount.current_status != 'closed' )
        query = query.join( FinancialAccountPremiumSchedule )
        if options.package:
            query = query.filter( FinancialAccount.package == FinancialPackage.get(options.package))
        if options.fund:
            query = query.join( FinancialAccountFundDistribution ).filter( FinancialAccountFundDistribution.fund_id == options.fund )
            query = query.join( FinancialAccountFundDistribution ).filter( FinancialAccountFundDistribution.fund_id == options.fund )
            query = query.filter( sql.and_( FinancialAccountFundDistribution.from_date <= options.thru_document_date,
                                            FinancialAccountFundDistribution.thru_date >= options.from_document_date ) )
        if options.origin:
            query = query.join( FinancialAgreementPremiumSchedule )
            query = query.join( FinancialAgreement )
            query = query.filter( FinancialAgreement.origin.like( '%s%%'%options.origin ) )

        visitor = AbstractVisitor()

        account_document_action = FinancialAccountDocument()
        for step in account_document_action.generate_documents(self.Context(query, options, visitor), options):
            yield step

        #yield _from(account_document_action.generate_documents(self.Context(query, options, visitor), options))

