import collections
import logging
import os
import datetime

from sqlalchemy import sql

from jinja2 import Markup

from camelot.core.utils import ugettext_lazy as _
from camelot.core.exception import UserException
from camelot.view.action_steps import (ChangeObject, 
                                       WordJinjaTemplate, 
                                       OpenFile, 
                                       PrintHtml)

from premium_schedule_document import PremiumScheduleDocument

from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment
from vfinance.model.financial.notification import NotificationOptions
from vfinance.model.financial.constants import notification_types
from vfinance.model.financial.notification.utils import get_recipient, generate_qr_code
from vfinance.model.financial.notification.account_document import FinancialAccountDocument

from environment import TemplateLanguage
from utils import get_or_undefined_object  # , get_or_undefined_list


logger = logging.getLogger('vfinance.model.financial.notification.transaction_document')

security_movement_data = collections.namedtuple( 'security_movement_data',
                                                 'security, amount, quantity, doc_date, book, document, account, nav' )

settlement_data = collections.namedtuple( 'settlement_data',
                                          'settlement_type, amount, origin_doc_date' )

transaction_revenue_data = collections.namedtuple( 'transaction_revenue_data',
                                                   'revenue_type, amount' )

account_state = collections.namedtuple('account_state',
                                       ['account',
                                        'premium_schedule_states',
                                        'securities'])


class TransactionDocument(PremiumScheduleDocument):
    
    verbose_name = _('Transaction Document')
    
    class Options(NotificationOptions):
        
        def __init__(self):
            NotificationOptions.__init__( self )
            self.notification_type_choices = [(notification_type,notification_type) for (_id,notification_type,related_to,_nt) in notification_types if related_to == 'transaction']
            self.notification_type = self.notification_type_choices[0][0]
                
    def get_context(self, transaction, recipient, options=None):
        from vfinance.model.financial.visitor.abstract import ( AbstractVisitor,
                                                                ProductBookingAccount,
                                                                FinancialBookingAccount,
                                                                SecurityBookingAccount )
        visitor = AbstractVisitor()
        
        #
        # These are the data structures that will be created
        #
        
        # the securities that have been bought
        security_in_entries = set()
        # the securities that have been sold
        security_out_entries = set()
        # the various kind of revenues for the company made in the transaction
        transaction_revenues = []
        # settlements that had to be made due to the transaction
        settlements = []
        # payments that were made to the client 
        payments = []
        # the money that was taken from/transfered to the customer
        customer_attribution = 0
        # list of the concerning account states
        account_states = []

        revenue_account_types = [ 'redemption_rate_revenue', 
                                  'redemption_fee_revenue', 
                                  'switch_revenue',
                                  'effective_interest_tax',
                                  'fictive_interest_tax',
                                  'market_fluctuation_revenue',
                                  ]
        
        product = None
        financial_account = None
        
        for ftps in transaction.consisting_of:
            
            premium_schedule = ftps.premium_schedule
            
            if financial_account and financial_account is not premium_schedule.financial_account:
                raise UserException('Multiple accounts per transaction not supported', 
                                    title='Possible unexpected results', 
                                    resolution='This transaction is linked to more than one account, please note that this document does not support this.' )

            financial_account = premium_schedule.financial_account
            product = premium_schedule.product
            
            #
            # Revenues
            #
            # different revenues might have the same account, so only get one of them
            #
            # @todo : different revenue accounts might overlap in time, so the line below is not correct, as we only look at the definition of the
            #         accounts at the from date of the transaction
            #
            revenue_accounts = dict( (product.get_account_at( account_type, transaction.from_date ), account_type) for account_type in revenue_account_types )
            for revenue_account, account_type in revenue_accounts.items():
                if revenue_account:
                    revenue = visitor.get_total_amount_until( premium_schedule, 
                                                              account = ProductBookingAccount( account_type ),
                                                              within_id = ftps.id)[0]
                    if abs(revenue) > 0:
                        transaction_revenues.append( transaction_revenue_data( revenue_type = account_type,
                                                                               amount = revenue ) )
            transfer_revenue_accounts = set( SecurityBookingAccount( 'transfer_revenue', security = fund_distribution.fund ) for fund_distribution in ftps.get_fund_distribution() )
            for account in transfer_revenue_accounts:
                revenue = visitor.get_total_amount_until( premium_schedule, 
                                                          account = account,
                                                          within_id = ftps.id )[0]
                if abs(revenue) > 0:
                    transaction_revenues.append( transaction_revenue_data( revenue_type = 'transfer_revenue',
                                                                           amount = revenue ) )
                for premium_fulfillment in FinancialAccountPremiumFulfillment.query.filter( sql.and_( FinancialAccountPremiumFulfillment.of == premium_schedule, 
                                                                                                      FinancialAccountPremiumFulfillment.within == ftps, 
                                                                                                      FinancialAccountPremiumFulfillment.fulfillment_type.in_(['switch_attribution', 'financed_switch']) ) ).all():
                    revenue = visitor.get_total_amount_until( premium_schedule, 
                                                              account = account,
                                                              associated_to_id = premium_fulfillment.id )[0]
                    if abs(revenue) > 0:
                        transaction_revenues.append( transaction_revenue_data( revenue_type = 'transfer_revenue',
                                                                               amount = revenue ) )
            #
            # Settlements
            #
            for premium_fulfillment in FinancialAccountPremiumFulfillment.query.filter( sql.and_( FinancialAccountPremiumFulfillment.of == premium_schedule, 
                                                                                                  FinancialAccountPremiumFulfillment.fulfillment_type == 'financed_commissions_activation' ) ).all():
                redeemed_financed_commissions_amount = visitor.get_total_amount_until( premium_schedule, 
                                                                                       fulfillment_type = 'financed_commissions_redemption_deduction', 
                                                                                       account = FinancialBookingAccount(),
                                                                                       associated_to_id = premium_fulfillment.id,
                                                                                       within_id = ftps.id)[0] * -1
                if abs(redeemed_financed_commissions_amount) > 0:
                    settlements.append( settlement_data( settlement_type='financed_commissions',
                                                         amount = redeemed_financed_commissions_amount,
                                                         origin_doc_date = premium_fulfillment.entry_doc_date ) )
                    
            for settlement_type in ['profit_attribution',]:
                settled_amount = visitor.get_total_amount_until( premium_schedule, 
                                                                 fulfillment_type = settlement_type, 
                                                                 account = FinancialBookingAccount(),
                                                                 within_id = ftps.id)[0] * -1
                if abs(settled_amount) > 0:
                    settlements.append( settlement_data( settlement_type = settlement_type,
                                                         amount = settled_amount,
                                                         origin_doc_date = transaction.from_date ) )                        
                    
            for premium_fulfillment in visitor.get_entries( premium_schedule,
                                                            fulfillment_types = ['depot_movement', 'profit_attribution'] ):

                for settlement_type in ['capital', 'interest', 'additional_interest',]:
                    settled_amount = visitor.get_total_amount_until( premium_schedule, 
                                                                     fulfillment_type = '%s_redemption_deduction'%settlement_type, 
                                                                     account = FinancialBookingAccount(),
                                                                     associated_to_id = premium_fulfillment.fulfillment_id,
                                                                     within_id = ftps.id)[0]
                    if abs(settled_amount) > 0:
                        payments.append( settlement_data( settlement_type = settlement_type,
                                                          amount = settled_amount,
                                                          origin_doc_date = premium_fulfillment.doc_date ) )                    
             
            #
            # Traded securities
            #
            
            def add_entry( entry ):
                security_movement = security_movement_data( security = fund_distribution.fund.name,
                                                            amount = entry.amount * -1,
                                                            quantity = entry.quantity / 1000,
                                                            doc_date = entry.doc_date,
                                                            book = entry.book,
                                                            document = entry.document,
                                                            account = fund_distribution.full_account_number,
                                                            nav = (1000 * (entry.amount/entry.quantity)) * -1 )
                if security_movement.amount >= 0:
                    security_in_entries.add( security_movement )
                else:
                    security_out_entries.add( security_movement )
                        
            for fund_distribution in ftps.get_fund_distribution():
                fund_account = FinancialBookingAccount( 'fund', fund = fund_distribution.fund )
                for entry in visitor.get_entries( premium_schedule,
                                                  account = fund_account,
                                                  within_id = ftps.id ):
                    add_entry( entry )

                for premium_fulfillment in FinancialAccountPremiumFulfillment.query.filter( sql.and_( FinancialAccountPremiumFulfillment.of == premium_schedule, 
                                                                                                      FinancialAccountPremiumFulfillment.within == ftps, 
                                                                                                      FinancialAccountPremiumFulfillment.fulfillment_type.in_(['switch_attribution', 'financed_switch']) ) ).all():
                    for entry in visitor.get_entries( premium_schedule,
                                                      account = fund_account,
                                                      associated_to_id = premium_fulfillment.id, ):
                        add_entry( entry )

            #
            # The net result transfered to the customer
            #
            customer_attribution += visitor.get_total_amount_until( premium_schedule = premium_schedule,
                                                                    fulfillment_type = 'redemption_attribution', 
                                                                    within_id = ftps.id,
                                                                    line_number = 1 )[0] * -1

        for account in transaction.get_financial_accounts():
            financial_account_document = FinancialAccountDocument()
            opts = financial_account_document.Options()
            opts.thru_document_date = transaction.from_date - datetime.timedelta(days=1)
            opts.from_document_date = transaction.from_date - datetime.timedelta(days=1)
            account_context = financial_account_document.get_context(account, None, opts)
            account_states.append(account_state(account=account,
                                                premium_schedule_states=account_context['premium_schedule_states'],
                                                securities=account_context['securities'],))

        account_items = []
        for ftps in transaction.consisting_of:
            for item in ftps.premium_schedule.financial_account.get_items_at(transaction.agreement_date):
                desc = item.described_by.replace('_', ' ')
                if item.use_custom_clause:
                    clause = Markup(item.custom_clause)
                else:
                    if item.associated_clause is None:
                        raise UserException('Item clause has no associated clause and does not use a custom clause')
                    clause = Markup(item.associated_clause.clause)
                account_items.append((desc, clause))

        transaction_total = sum(sum((entry.amount for entry in entries),0) for entries in (security_in_entries, security_out_entries))
        transaction_total -= sum(sum((entry.amount for entry in entries),0) for entries in (transaction_revenues, settlements, payments))

        context = {'title': self.verbose_name,
                   'account_items': account_items,
                   'insured_parties': transaction.get_roles_at(transaction.from_date, 'insured_party'),
                   'subscribers': transaction.get_roles_at(transaction.from_date, 'subscriber'),
                   'transaction_text': Markup(transaction.text),
                   'account_states': account_states,
                   'transaction': get_or_undefined_object(transaction),
                   'recipient': get_or_undefined_object(recipient), 
                   'account': get_or_undefined_object(financial_account),
                   'product': get_or_undefined_object(premium_schedule.product),
                   'package_name': financial_account.package.name,
                   'full_account_number': premium_schedule.full_account_number,
                   'today': datetime.date.today(),
                   'now': datetime.datetime.now(),
                   'security_in_entries': security_in_entries,
                   'security_in_entries_total_amount': sum(entry.amount for entry in security_in_entries),
                   'security_out_entries': security_out_entries,
                   'security_out_entries_total_amount': sum(entry.amount for entry in security_out_entries),
                   'transaction_revenues': transaction_revenues,
                   'settlements': settlements,
                   'payments': payments,
                   'payments_total_amount': sum(entry.amount for entry in payments),
                   'customer_attribution': customer_attribution,
                   'transaction_total': transaction_total,
                   # TODO fill in if simulating or something that invalidates the document
                   'invalidating_text': u'',
                   'qr_base64': generate_qr_code()
                   }
                        
        # print context
        if options and hasattr(options, 'output_type'):
            context['debug'] = options.output_type
        
        # isolate id and agreement code to make it easier to test these
        if transaction:
          if hasattr(transaction, 'id'):
            context['transaction_id'] = transaction.id
          if hasattr(transaction, 'agreement_code'):
            context['transaction_agreement_code'] = transaction.agreement_code

        return context
        
    def model_run(self, model_context):
        options = self.Options()
        printed = False
        yield ChangeObject( options )
        documents = []
        for transaction in model_context.get_selection():
            premium_schedule = transaction.get_first_premium_schedule()
            language = premium_schedule.financial_account.get_language_at(transaction.from_date, described_by='subscriber')
            for notification in premium_schedule.get_applied_notifications_at(premium_schedule.valid_from_date,
                                                                              options.notification_type):
                for recipient_role, _broker in premium_schedule.financial_account.get_notification_recipients(options.notification_date):
                    context = self.get_context(transaction, get_recipient([recipient_role]), options)
                    if options.output_type == 2:
                        html = '<html><head><title>Document Debug Context</title></head><body><h1>Context</h1><table border=1>'
                        for context_element in context:
                            html += '<tr><td>{0}</td><td>{1}</td></tr>'.format(context_element, context[context_element])
                        html += '</table></body></html>'
                        yield PrintHtml(html)
                    with TemplateLanguage( language ):
                        word_step = WordJinjaTemplate( notification.template.replace('\\', '/'), 
                                                       context=context )
                        if options.output_type in (0, 1):
                            yield word_step
                        elif options.output_type == 4:
                            subfolder= options.get_document_folder( premium_schedule.financial_account )
                            documents.append( ( os.path.join( subfolder, '%s-%s-%s.xml'%( transaction.code.replace('/', '-'),
                                                                                          transaction.id,
                                                                                          language ) ),
                                                word_step.file_name ) )
                        printed = True

        if documents:
            import zipfile
            filename = OpenFile.create_temporary_file( '.zip' )
            zip = zipfile.ZipFile( open(filename, 'wb'), 'w')
            for name, document in documents:
                content = open(document, 'rb').read()
                zip.writestr( name, content )
            zip.close()
            yield OpenFile( filename )
        if not printed:
            raise UserException( 'No documents of type %s were printed' % options.notification_type, 
                                 title='No documents generated', 
                                 resolution='Check if the package has an appropriate notification defined' )
