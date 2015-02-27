from decimal import Decimal as D
import logging

from camelot.core.exception import UserException

from vfinance.model.financial.visitor.abstract import ( AbstractVisitor, 
                                                        #begin_of_times,
                                                        FinancialBookingAccount)

from ...bank.constants import commission_receivers
from ...bank.visitor import ProductBookingAccount
from vfinance.model.financial import constants
from vfinance.model.financial.formulas import all_amounts
from vfinance.model.financial.work_effort import (FinancialWorkEffort,
                                                  FinancialAccountNotification)

from integration.tinyerp.convenience import add_months_to_date, months_between_dates

LOGGER = logging.getLogger('vfinance.model.financial.visitor.account_attribution')

# dont change the order of the distributed revenue types
distributed_revenue_types = ['premium_rate_1', 'premium_fee_1',
                             'premium_rate_2', 'premium_fee_2',
                             'premium_rate_3', 'premium_fee_3',
                             'premium_rate_4', 'premium_fee_4',
                             'premium_rate_5',
                             'entry_fee',]
    
class AccountAttributionVisitor(AbstractVisitor):
    """Attribute premiums to the financial account, either those that are 
    pending on the customer account, or according to the requested schedule.

    Once a premium is transferred an account, the account is activated.
    """

    dependencies = []

    def get_payment_dates( self, premium_schedule, from_date, thru_date ):
        """
        Generates successive dates (between from_date and thru_date) when payments from premium_schedule are supposed to be made.
        Starting date of the premium_schedule is taken to be the from_date of the corresponding agreement.
        """
        start_date = premium_schedule.valid_from_date
        interval = constants.period_types_by_granularity[premium_schedule.period_type]
        if interval == 0:
            if start_date >= from_date and start_date <= thru_date:
                yield start_date
            return
        duration = months_between_dates( premium_schedule.valid_from_date, premium_schedule.payment_thru_date )
        for i in range(0, duration):
            if i % interval == 0:
                d = add_months_to_date(start_date, i)
                if d >= from_date and d <= thru_date:
                    yield d

    def get_attribute_condition( self, premium_schedule ):
        attribute_settings = premium_schedule.financial_account.get_applied_functional_settings_at( premium_schedule.valid_from_date, 
                                                                                                    'attribute_condition' )
        if 'attribute_on_schedule' in [s.described_by for s in attribute_settings]:
            return 'attribute_on_schedule'
        else:
            return 'attribute_on_payment'

    def get_document_dates( self, premium_schedule, from_date, thru_date ):
        if self.get_attribute_condition( premium_schedule ) == 'attribute_on_schedule':
            for d in self.get_payment_dates( premium_schedule, premium_schedule.valid_from_date, thru_date ):
                yield d
        else:
            agreement = premium_schedule.agreed_schedule.financial_agreement
            min_doc_date = max(self.get_agreement_fulfillment_date(agreement), self.get_premium_schedule_end_of_cooling_off(premium_schedule))
            #
            # There might have been entries attributed to the customer before the
            # from date of the premium schedule, those should be taken care of
            # at the min doc date, look 30 days back
            #
            if premium_schedule.valid_from_date >= from_date:
                from_date = None
            for customer_attribution_entry in self.get_entries( premium_schedule,
                                                                from_document_date = from_date, 
                                                                thru_document_date = thru_date,
                                                                fulfillment_type='premium_attribution' ):
                yield max(min_doc_date, customer_attribution_entry.doc_date)

    def visit_premium_schedule_at(self, premium_schedule, document_date, book_date, last_visited_document_date=None):
        LOGGER.debug('visit %s at %s'%(premium_schedule, document_date))
        #
        # Use until, because the new document date might be later then the document
        # date of the premium attribution
        #
        if self.get_attribute_condition( premium_schedule ) == 'attribute_on_schedule':
            attributed_to_customer = premium_schedule.get_premiums_invoicing_due_amount_at( document_date )
        else:
            #
            # Verify if the time is right to attribute the premium to the account
            #
            if book_date < self.get_premium_schedule_end_of_cooling_off(premium_schedule):
                return
            attributed_to_customer = self.get_total_amount_until( premium_schedule, 
                                                                  thru_document_date = document_date,
                                                                  fulfillment_type = 'premium_attribution')[2] * -1

        attributed_to_account = self.get_total_amount_until(premium_schedule,
                                                            thru_document_date = document_date,
                                                            fulfillment_type = 'sales',
                                                            line_number = 1)[0]

        LOGGER.debug('attributed to customer : %s'%attributed_to_customer )
        LOGGER.debug('attributed to account : %s'%attributed_to_account )

        premium_amount = attributed_to_customer - attributed_to_account

        #
        # This action is not reversible, so if premium amount < 0, nothing can
        # be done
        #
        # This can happen if amounts have been attributed manual to the account
        # schedule, without being attributed to the customer
        #
        if premium_amount >= D('0.01'):
            for step in self.attribute_premium_to_account( premium_schedule,
                                                           attributed_to_customer - attributed_to_account,
                                                           document_date,
                                                           book_date ):
                yield step

    def distribute_feature_amount(self, premium_schedule, document_date, feature_description, account, premium_amount, amount, fulfillment_type, message):
        """
        Split an amount in different booking lines according to the configured commission distribution
        
        :return: a generator of booking lines
        """
        # todo : filter commission distribution of 0 out of the commission distribution to prevent remainders being booked on it
        #        reuse the security orders distribution to prevent having this mechanism twice
        if amount != 0:
            commission_distribution = [(receiver[1], premium_schedule.get_commission_distribution(feature_description, receiver[1])) for receiver in commission_receivers]
            total_distribution = sum(distribution[1] for distribution in commission_distribution)
            if total_distribution == 0:
                # no distribution at the schedule level, use the distribution at
                # the product level
                feature = premium_schedule.get_applied_feature_at(document_date,
                                                                  document_date,
                                                                  premium_amount,
                                                                  feature_description)
                commission_distribution = [(feature_distribution.recipient, feature_distribution.distribution) for feature_distribution in feature.distributed_via]
                total_distribution = sum(distribution[1] for distribution in commission_distribution)
            if total_distribution == 0:
                raise UserException('{0} is not distributed'.format(feature_description))
            for receiver, commission_amount, percentage in self.distribute_amount(amount, commission_distribution, total_distribution):
                remark = u'{0.full_account_number} {1:>13,.2f} {2:>5,.2f} {3}'.format(premium_schedule, premium_amount, percentage, message[:18])
                if receiver == 'company':
                    revenue_account = ProductBookingAccount(account)
                else:
                    revenue_account = ProductBookingAccount('{account}_{receiver}'.format(account=account, receiver=receiver), alternative_account_type=account)
                yield self.create_line(revenue_account, 
                                       commission_amount,
                                       remark,
                                       fulfillment_type)

    def attribute_premium_to_account(self, premium_schedule, premium_amount, document_date, book_date):
        """
        :return: a a list of FinancialAccountPremiumFulfillment that were generated
        """
        LOGGER.debug( 'attribute %s to account on %s'%( premium_amount, document_date ) )
        #
        # security check for amount
        #
        if premium_amount < D('0.01'):
            return

        book_date = self.entered_book_date(document_date, book_date)
        product = premium_schedule.product
        account = premium_schedule.financial_account
        agreement = premium_schedule.agreed_schedule.financial_agreement
        subscribers = [role for role in premium_schedule.financial_account.roles if role.described_by=='subscriber']
        if len(subscribers):
            subscriber_language = subscribers[0].language
            subscriber_string = u', '.join([r.name for r in subscribers])
        else:
            subscriber_language = None
            subscriber_string = u''

        amounts = all_amounts( premium_schedule, premium_amount, document_date, document_date )

        #
        # Taxes
        # the premium amount is the amount that will be payed by the customer, this includes 1.1% taxes on
        # the premium amount minus taxes :
        #
        transaction_2 = [
            self.create_line( ProductBookingAccount('taxes'), 
                              amounts['taxation'] * -1, 
                              'taxes %s'%agreement.code,
                              'sales',  ),]
        #
        # Revenues that are split between company / master broker / broker / agent
        #
        for revenue_type in distributed_revenue_types:
            revenue_amount = amounts[revenue_type]
            transaction_2.extend(self.distribute_feature_amount(
                premium_schedule,
                document_date,
                revenue_type,
                revenue_type+'_revenue',
                premium_amount,
                revenue_amount * -1,
                'sales',
                subscriber_string,
            ))
        #
        # Other revenues
        #
        for revenue_type in ['distributed_medical_fee']:
            amount = amounts[revenue_type]
            if amount != 0:
                transaction_2.append(
                    self.create_line(ProductBookingAccount('%s_revenue'%revenue_type),
                                     amount * -1,
                                     '%s %s'%(revenue_type, agreement.code),
                                     'sales')
                )

        transaction_2.append(
            self.create_line(  ProductBookingAccount('capital_revenue'),
                               (amounts['net_premium'] - amounts['funded_premium']) * -1,
                               'attributed premiums %s'%agreement.code,
                               'sales', ),
        )

        transaction_6 = [
            self.create_line( FinancialBookingAccount(),
                              amounts['net_premium'] * -1,
                              agreement.code,
                              'depot_movement',  ),
            self.create_line( ProductBookingAccount( 'capital_cost' ),
                              amounts['net_premium'] - amounts['funded_premium'],
                              agreement.code,
                              'depot_movement', ),
            self.create_line( ProductBookingAccount( 'funded_premium_attribution_cost' ),
                              amounts['funded_premium'],
                              'funded premium %s'%agreement.code,
                              'depot_movement', ),
        ]

        transaction_15 = []
        if amounts['financed_commissions']:
            transaction_15 = [
                self.create_line( FinancialBookingAccount( 'financed_commissions' ),
                                  amounts['financed_commissions'],
                                  agreement.code,
                                  'financed_commissions_activation',  ),
            ]
            transaction_15.extend(self.distribute_feature_amount(
                premium_schedule,
                document_date,
                'financed_commissions_rate',
                'financed_commissions_revenue',
                premium_amount,
                amounts['financed_commissions'] * -1,
                'financed_commissions_activation',
                subscriber_string,
                ))

        transaction_30 = []
        if amounts['funded_premium']:
            transaction_30 = list(
                self.distribute_feature_amount(
                    premium_schedule,
                    document_date,
                    'funded_premium_rate_1',
                    'funded_premium',
                    premium_amount,
                    amounts['funded_premium'],
                    'funded_premium_activation',
                    subscriber_string,
                    ))
            transaction_30.append(
                self.create_line( ProductBookingAccount( 'funded_premium_attribution_revenue'),
                                  amounts['funded_premium'] * -1,
                                  agreement.code,
                                  'funded_premium_activation', )
                )

        for sales in self.create_sales( premium_schedule,
                                        book_date, 
                                        document_date, 
                                        premium_amount, 
                                        transaction_2 + transaction_6 + transaction_15 + transaction_30,
                                        product.premium_sales_book,
                                        'sales',
                                        ):
            yield sales
            #
            # activate the account
            #
            if account.current_status == 'draft':
                account.change_status('active')
            #
            # Get a work effort to attach notifications to
            #
            generated = False
            for applied_notification in account.package.get_applied_notifications_at(
                self.get_agreement_fulfillment_date(agreement),
                'certificate',
                premium_period_type = premium_schedule.period_type, 
                subscriber_language = subscriber_language 
                ):
                work_effort = FinancialWorkEffort.get_open_work_effort(u'notification')
                for recipient, _broker in account.get_notification_recipients(document_date):
                    notification = FinancialAccountNotification(generated_by = work_effort,
                                                                date = document_date,
                                                                balance = 0,
                                                                application_of = applied_notification,
                                                                account = premium_schedule.financial_account,
                                                                entry_book_date = sales.book_date,
                                                                entry_document = sales.document_number,
                                                                entry_book = sales.book,
                                                                entry_line_number = 1,
                                                                natuurlijke_persoon = recipient.natuurlijke_persoon,
                                                                rechtspersoon = recipient.rechtspersoon,
                                                                )
                    notification.flush()
                generated = True
            if not generated:
                LOGGER.debug('No notifications created')
