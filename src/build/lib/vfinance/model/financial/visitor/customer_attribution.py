import logging

from vfinance.model.financial.visitor.abstract import AbstractVisitor

from ..work_effort import FinancialWorkEffort, FinancialAccountNotification
from ...bank.visitor import ProductBookingAccount
from ....connector.accounting import UpdateDocumentRequest, LineRequest

LOGGER = logging.getLogger('vfinance.model.financial.visitor.customer_attribution')

class CustomerAttributionVisitor(AbstractVisitor):
    """Attribute entries on the pending premiums account that have been connected
    to a premium schedule.
    
    This is done by manipulating the entry and changing its account number to
    the account number of the customer.
    """
            
    def get_document_dates(self, premium_schedule, from_date, thru_date):
        LOGGER.debug( 'get_document_dates' )
        if len( list( premium_schedule.product.get_accounts( 'pending_premiums' ) ) ):
            if premium_schedule.valid_from_date >= from_date:
                from_date = None
            for customer_attribution_entry in self.get_entries( premium_schedule, 
                                                                from_document_date = from_date, 
                                                                thru_document_date = thru_date,
                                                                fulfillment_type='premium_attribution',
                                                                account = ProductBookingAccount( 'pending_premiums' ) ):
                yield customer_attribution_entry.doc_date
            
    def visit_premium_schedule_at(self, premium_schedule, document_date, book_date, last_visited_document_date):
        account = premium_schedule.financial_account
        agreement = premium_schedule.agreed_schedule.financial_agreement
        fulfillment_date = self.get_agreement_fulfillment_date(agreement)
        customer = self.get_customer_at( premium_schedule, max(fulfillment_date, document_date))
        
        LOGGER.debug('visit %s at %s'%(premium_schedule, document_date))
        subscriber_language = [(role.natuurlijke_persoon  or role.rechtspersoon) for role in account.roles if role.described_by=='subscriber'][0].taal
        
        for pending_entry in self.get_entries( premium_schedule, 
                                               from_document_date = document_date, 
                                               thru_document_date = document_date,
                                               fulfillment_type = 'premium_attribution',
                                               account = ProductBookingAccount( 'pending_premiums' ) ):
            
            LOGGER.debug('got entry on line %s'%pending_entry.line_number)
            #
            # The entry might be ticked, so there is no need to transfer its
            # account number.  This might happen in case the entry was transferred
            # from a previous year
            #
            if pending_entry.open_amount == 0:
                continue
            
            yield UpdateDocumentRequest(
                book_date = pending_entry.book_date,
                book = pending_entry.book,
                document_number = pending_entry.document,
                lines = [LineRequest(
                    line_number = pending_entry.line_number,
                    amount = pending_entry.amount,
                    quantity = pending_entry.quantity,
                    account = customer.full_account_number
                )]
                )
            #
            # Create pre-certificate notifications
            #
            for applied_notification in account.package.get_applied_notifications_at(
                self.get_agreement_fulfillment_date(agreement), 
                'pre-certificate', 
                premium_schedule.period_type,
                subscriber_language
            ):
                work_effort = FinancialWorkEffort.get_open_work_effort(u'notification')
                for recipient, _broker in account.get_notification_recipients(pending_entry.doc_date):
                    FinancialAccountNotification(generated_by = work_effort,
                                                 date = pending_entry.doc_date,
                                                 balance = 0,
                                                 application_of = applied_notification,
                                                 account = account,
                                                 entry_book_date = pending_entry.book_date,
                                                 entry_document = pending_entry.document,
                                                 entry_book = pending_entry.book,
                                                 entry_line_number = pending_entry.line_number,
                                                 natuurlijke_persoon = recipient.natuurlijke_persoon,
                                                 rechtspersoon = recipient.rechtspersoon,)


