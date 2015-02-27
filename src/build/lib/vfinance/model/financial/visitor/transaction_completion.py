import logging
import datetime
from decimal import Decimal as D
from collections import namedtuple

from sqlalchemy import orm, sql

from camelot.core.exception import UserException

from abstract import FinancialBookingAccount
from ...bank.visitor import ProductBookingAccount
from ..transaction import FinancialTransactionPremiumSchedule
from fund_attribution import FundAttributionVisitor
from transaction_initiation import TransactionInitiationVisitor
from interest_attribution import InterestAttributionVisitor
from vfinance.model.financial.formulas import get_amount_at
from vfinance.model.bank.financial_functions import round_down
from vfinance.model.financial.interest import single_period_future_value
from vfinance.model.financial.work_effort import FinancialWorkEffort, FinancialAccountNotification

LOGGER = logging.getLogger('vfinance.model.financial.visitor.transaction_completion')
#LOGGER.setLevel( logging.DEBUG )

depot_movement_summary = namedtuple( 'depot_movement_summary',
                                     ( 'depot_movement', 'intrest_amount', 'additional_intrest_amount', 
                                       'all_amounts', 'redeemed_amount' ) )

class TransactionCompletionVisitor(TransactionInitiationVisitor):
    """
    Last booking of a financial transaction, this completes the transaction
    and puts the redeemed amount on the account of the customer.
    
    This visitor will issue :ref:`transaction-8` and :ref:`transaction-10`
    """
    
    dependencies = [ TransactionInitiationVisitor, FundAttributionVisitor, InterestAttributionVisitor ]

    def __init__(self, *args, **kwargs):
        super(TransactionCompletionVisitor, self).__init__(*args, **kwargs)
        self._transaction_completion_date_cache = {}

    def get_transaction_completion_date(self, transaction):
        """
        the transaction completion date can be very expensive to compute, when
        there are multiple premium schedules involved in the same transaction
        """
        try:
            completion_date = self._transaction_completion_date_cache[transaction.id]
        except KeyError:
            completion_date = transaction.completion_date
            self._transaction_completion_date_cache[transaction.id] = completion_date
        return completion_date

    def get_document_dates(self, premium_schedule, from_date, thru_date):
        LOGGER.debug('look for transactions')
        for transaction in self.get_transactions(premium_schedule):
            LOGGER.debug('determine completion date for transaction {0.id}'.format(transaction))
            #
            # 
            #
            completion_date = self.get_transaction_completion_date(transaction)
            LOGGER.debug('completion date of transaction {0.id} : {1}'.format(transaction, completion_date))
            if completion_date and (completion_date >= from_date) and (completion_date <= thru_date):
                yield completion_date
        
    def visit_premium_schedule_at(self, premium_schedule, document_date, book_date, last_visited_document_date):
        LOGGER.debug('visit %s with document date %s and book date %s'%(premium_schedule.full_account_number,
                                                                         document_date,
                                                                         book_date))
        for transaction in self.get_transactions(premium_schedule):
            completion_date = self.get_transaction_completion_date(transaction)
            if completion_date != document_date:
                continue
            
            account = premium_schedule.financial_account
            package = account.package
            full_account_number = premium_schedule.full_account_number
            agreement = premium_schedule.agreed_schedule.financial_agreement
            product = premium_schedule.product
            related_sales = []

            session = orm.object_session(premium_schedule)
            for ftps in session.query(FinancialTransactionPremiumSchedule).filter(sql.and_(FinancialTransactionPremiumSchedule.within_id==transaction.id,
                                                                                            FinancialTransactionPremiumSchedule.premium_schedule_id==premium_schedule.id)):

                redeemed_amount = self.get_total_amount_until(premium_schedule, 
                                                              thru_document_date = document_date, 
                                                              thru_book_date = book_date, 
                                                              fulfillment_type = 'redemption', 
                                                              account = FinancialBookingAccount(),
                                                              within_id = ftps.id)[0]
                
                deduced_amount_from_premium = 0
                effective_interest_tax = 0
                fictive_interest_tax = 0
                transaction_8 = []
                redemption_rate_amount = 0
                market_fluctuation = 0
                lines = []
                
                #
                # Summarize the depot movements to calculate the total amount
                # to deduce.
                #
                depot_movements = []
                profit_attributions = []
                if transaction.transaction_type == 'full_redemption':
                    depot_movement_thru_document_date = None
                else:
                    depot_movement_thru_document_date = transaction.from_date
                
                for depot_movement in self.get_entries( premium_schedule,
                                                        thru_document_date=depot_movement_thru_document_date,
                                                        account = FinancialBookingAccount(),
                                                        fulfillment_types = ['depot_movement', 'profit_attribution'] ):
                    
                    def associated_amount( fulfillment_type, within_id = None ):
                        return self.get_total_amount_until( premium_schedule, 
                                                            thru_document_date = document_date, 
                                                            thru_book_date = book_date, 
                                                            fulfillment_type = fulfillment_type, 
                                                            account = FinancialBookingAccount(),
                                                            associated_to_id = depot_movement.fulfillment_id,
                                                            within_id = within_id )[0]
                    
                    intrest_redemtion_amount_within_transaction = associated_amount( 'interest_redemption_deduction', ftps.id )
                    additional_interest_redemption_amount_within_transaction = associated_amount( 'additional_interest_redemption_deduction', ftps.id )
                    intrest_amount = associated_amount( 'interest_attribution' ) + associated_amount( 'interest_redemption_deduction' )
                    additional_intrest_amount = associated_amount( 'additional_interest_attribution' ) + associated_amount( 'additional_interest_redemption_deduction' )
                    capital_redemption_amount_within_transaction = associated_amount( 'capital_redemption_deduction', ftps.id )
                    deduced_amount_from_premium += capital_redemption_amount_within_transaction
                    all_amounts = associated_amount( None ) + depot_movement.amount - associated_amount( None, ftps.id )
                    
                    summary = depot_movement_summary( depot_movement = depot_movement,
                                                      intrest_amount = intrest_amount - intrest_redemtion_amount_within_transaction,
                                                      additional_intrest_amount = additional_intrest_amount - additional_interest_redemption_amount_within_transaction,
                                                      all_amounts = all_amounts,
                                                      redeemed_amount = ( intrest_redemtion_amount_within_transaction + \
                                                                          additional_interest_redemption_amount_within_transaction + \
                                                                          capital_redemption_amount_within_transaction ) )
                    if depot_movement.fulfillment_type == 'depot_movement':
                        depot_movements.append( summary )
                    elif depot_movement.fulfillment_type == 'profit_attribution':
                        profit_attributions.append( summary )
                    else:
                        raise Exception('Unhandled fulfillment type')
                #
                # Calculate total amount to deduce
                #
                max_amount_to_deduce_from_premiums =  -1 * sum( s.all_amounts for s in depot_movements + profit_attributions )
                amount_to_deduce_from_premiums = 0
                if transaction.transaction_type == 'full_redemption':
                    amount_to_deduce_from_premiums = max_amount_to_deduce_from_premiums
                elif transaction.transaction_type == 'partial_redemption':
                    if ftps.described_by == 'amount':
                        amount_to_deduce_from_premiums = min( max_amount_to_deduce_from_premiums, ftps.quantity * -1 )
                    elif ftps.described_by == 'percentage':
                        amount_to_deduce_from_premiums = max_amount_to_deduce_from_premiums * min( ftps.quantity * -1, 100 ) / 100
                    else:
                        raise Exception( 'unknown financial transaction premium schedule type %s'%ftps.described_by )
                LOGGER.debug( 'total amount to deduce : %s'%amount_to_deduce_from_premiums )
                #
                # Deduce the uninvested premiums and their intrest
                #
                for summary in depot_movements + profit_attributions:
                    #
                    # determine the amount to deduce
                    #
                    amount_to_deduce_from_premium = 0
                    max_amount_to_deduce_from_premium =  -1 * ( summary.all_amounts )
                    amount_to_deduce_from_premium = min( max_amount_to_deduce_from_premium, amount_to_deduce_from_premiums )
                    amount_to_deduce_from_premiums -= amount_to_deduce_from_premium
                    #
                    # subtract the amount that has been deduced for this transaction
                    #
                    amount_to_deduce_from_premium -= summary.redeemed_amount
                    #
                    # split this amount in capital and interest, to calculate taxes
                    #
                    if max_amount_to_deduce_from_premium != 0:
                        deduction_rate = amount_to_deduce_from_premium / max_amount_to_deduce_from_premium
                        interest_amount_to_deduce = round_down( -1 * summary.intrest_amount * deduction_rate )
                        additional_interest_amount_to_deduce = round_down( -1 * summary.additional_intrest_amount * deduction_rate )
                        capital_to_deduce = amount_to_deduce_from_premium - interest_amount_to_deduce - additional_interest_amount_to_deduce
                    else:
                        interest_amount_to_deduce = 0
                        additional_interest_amount_to_deduce = 0
                        capital_to_deduce = 0
                        
                    depot_movement = summary.depot_movement
                    
                    effective_interest_tax += get_amount_at( ftps, 
                                                             (interest_amount_to_deduce + additional_interest_amount_to_deduce), 
                                                             document_date, 
                                                             depot_movement.doc_date, 
                                                             'effective_interest_tax' )
                    
                    market_fluctuation += get_amount_at( ftps,
                                                         depot_movement.amount * -1,
                                                         document_date,
                                                         depot_movement.doc_date,
                                                         'market_fluctuation',
                                                         applied_amount = amount_to_deduce_from_premium )
                    
                    fictive_interest_rate = ftps.get_applied_feature_at( document_date, 
                                                                         depot_movement.doc_date, 
                                                                         premium_schedule.premium_amount,
                                                                         'fictive_interest_rate', 
                                                                         default=D(0) ).value
                    
                    interest_before_attribution_days = ftps.get_applied_feature_at( document_date, 
                                                                                    depot_movement.doc_date, 
                                                                                    premium_schedule.premium_amount,
                                                                                    'interest_before_attribution', 
                                                                                    default=D(0) ).value                    
                    
                    fictive_interest = max( 0, single_period_future_value( capital_to_deduce, 
                                                                           depot_movement.doc_date - datetime.timedelta( days = int(interest_before_attribution_days) ),
                                                                           document_date, 
                                                                           fictive_interest_rate, 
                                                                           product.days_a_year ) - capital_to_deduce )
                    
                    fictive_interest_tax += get_amount_at( ftps, 
                                                           fictive_interest, 
                                                           document_date, 
                                                           depot_movement.doc_date, 
                                                           'fictive_interest_tax' )
                    
                    if abs( amount_to_deduce_from_premium ) >= self.delta:
                        LOGGER.debug( 'deduce %s from depot movement %s'%( amount_to_deduce_from_premium, depot_movement.doc_date ) )
                        LOGGER.debug( unicode( summary ) )
                        premium_redemption_rate_amount = get_amount_at( ftps, 
                                                                        -1 * summary.depot_movement.amount, 
                                                                        document_date, 
                                                                        summary.depot_movement.doc_date, 
                                                                        'redemption_rate',
                                                                        applied_amount = amount_to_deduce_from_premium )
                        if abs( premium_redemption_rate_amount ) >= self.delta:
                            redemption_rate_amount += premium_redemption_rate_amount
                            transaction_8 += [
                                self.create_line( ProductBookingAccount( 'redemption_rate_revenue' ),
                                                  premium_redemption_rate_amount * -1,
                                                  'redemption %s %s'%(full_account_number, agreement.code),
                                                  'redemption_attribution',
                                                  associated_fulfillment_id = summary.depot_movement.fulfillment_id,
                                                  within_id = ftps.id)
                                ]
                        transaction_10 = [
                            self.create_line( FinancialBookingAccount(),
                                              capital_to_deduce,
                                              'redemption %s'%(agreement.code),
                                              'capital_redemption_deduction',
                                              associated_fulfillment_id = depot_movement.fulfillment_id,
                                              within_id = ftps.id),
                            self.create_line( ProductBookingAccount( 'redemption_cost' ),
                                              capital_to_deduce * -1,
                                              'capital redemption %s %s'%(full_account_number, agreement.code), 
                                              'capital_redemption_deduction',
                                              associated_fulfillment_id = depot_movement.fulfillment_id,
                                              within_id = ftps.id ),
                        ]
                        lines.extend( transaction_10 )
                        if abs( interest_amount_to_deduce ) >= self.delta: 
                            transaction_33 = [
                                self.create_line( FinancialBookingAccount(),
                                                  interest_amount_to_deduce,
                                                  'redemption interest %s'%(agreement.code),
                                                  'interest_redemption_deduction',
                                                  associated_fulfillment_id = depot_movement.fulfillment_id,
                                                  within_id = ftps.id),
                                self.create_line( ProductBookingAccount( 'redemption_cost' ),
                                                  interest_amount_to_deduce * -1,
                                                  'redemption interest %s %s'%(full_account_number, agreement.code), 
                                                  'interest_redemption_deduction',
                                                  associated_fulfillment_id = depot_movement.fulfillment_id,
                                                  within_id = ftps.id ),
                            ]
                            lines.extend( transaction_33 )
                        if abs( additional_interest_amount_to_deduce ) >= self.delta: 
                            transaction_34 = [
                                self.create_line( FinancialBookingAccount(),
                                                  additional_interest_amount_to_deduce,
                                                  'redemption additional interest %s'%(agreement.code),
                                                  'additional_interest_redemption_deduction',
                                                  associated_fulfillment_id = depot_movement.fulfillment_id,
                                                  within_id = ftps.id),
                                self.create_line( ProductBookingAccount( 'redemption_cost' ),
                                                  additional_interest_amount_to_deduce * -1,
                                                  'redemption additional interest %s %s'%(full_account_number, agreement.code), 
                                                  'additional_interest_redemption_deduction',
                                                  associated_fulfillment_id = depot_movement.fulfillment_id,
                                                  within_id = ftps.id ),
                            ]
                            lines.extend( transaction_34 )
                  
                #
                # Deduce the redeemed financed commissions
                #
                redeemed_financed_commissions_amount = 0
                for financed_commissions_activation in self.get_entries( premium_schedule, 
                                                                         fulfillment_type='financed_commissions_activation' ):
                    LOGGER.debug( ' look for redeemed financed commissions for activation %s : %s %s'%( financed_commissions_activation.fulfillment_id,
                                                                                                        financed_commissions_activation.book,
                                                                                                        financed_commissions_activation.document ) )
                    redeemed_financed_commissions_amount += self.get_total_amount_until(premium_schedule, 
                                                                                        thru_document_date = document_date, 
                                                                                        thru_book_date = book_date, 
                                                                                        fulfillment_type = 'financed_commissions_redemption_deduction', 
                                                                                        account = FinancialBookingAccount(),
                                                                                        associated_to_id = financed_commissions_activation.fulfillment_id,
                                                                                        within_id = ftps.id)[0]
                    LOGGER.debug( '   upto %s found'%redeemed_financed_commissions_amount )
                #
                # Deduce the redeemed funds
                #                    
                deduced_amount_from_funds = self.get_total_amount_until( premium_schedule, 
                                                                         thru_document_date = document_date, 
                                                                         thru_book_date = book_date, 
                                                                         fulfillment_type = 'capital_redemption_deduction', 
                                                                         account = FinancialBookingAccount(),
                                                                         within_id = ftps.id)[0] - deduced_amount_from_premium
                
                amount_to_deduce_from_funds = -1 * (deduced_amount_from_funds + redeemed_amount + redeemed_financed_commissions_amount)
                
                if abs(amount_to_deduce_from_funds) >= self.delta:
                    transaction_10 = [
                        self.create_line( FinancialBookingAccount(),
                                          amount_to_deduce_from_funds,
                                          'redemption %s'%(agreement.code),
                                          'capital_redemption_deduction',
                                          within_id = ftps.id),
                        self.create_line( ProductBookingAccount( 'redemption_cost' ),
                                          amount_to_deduce_from_funds * -1,
                                          'redemption %s %s'%(full_account_number, agreement.code), 
                                          'capital_redemption_deduction',
                                          within_id = ftps.id ),
                    ]
                    lines.extend( transaction_10 )
                #
                # if there is something to deduce, calculate fees etc, and go ahead
                #
                if len( lines ):                    
                    effective_interest_tax_to_apply = effective_interest_tax
                    fictive_interest_tax_to_apply = fictive_interest_tax
                    amount_to_deduce = sum( (line.amount for line in lines if line.account==FinancialBookingAccount()), 0 )
                    
                    transaction_8 += [
                        self.create_line( ProductBookingAccount( 'redemption_revenue'),
                                          amount_to_deduce,
                                          'redemption %s %s'%(full_account_number, agreement.code),
                                          'redemption_attribution',
                                          within_id = ftps.id),                        
                        ]
                    
                    #
                    # redemption rate has been added before per redeemed premium,
                    # add it here for the fund redemption.
                    #
                    if abs(amount_to_deduce_from_funds) >= self.delta:
                        fund_redemption_rate_amount = get_amount_at( ftps, 
                                                                        0, 
                                                                        document_date, 
                                                                        premium_schedule.valid_from_date, 
                                                                        'redemption_rate',
                                                                        applied_amount = amount_to_deduce_from_funds )
                        redemption_rate_amount += fund_redemption_rate_amount
                        transaction_8 += [
                            self.create_line( ProductBookingAccount( 'redemption_rate_revenue'),
                                              fund_redemption_rate_amount * -1,
                                              'redemption %s %s'%(full_account_number, agreement.code),
                                              'redemption_attribution',
                                              within_id = ftps.id)
                            ]    
                    #
                    # redemption fee is calculated per premium schedule
                    #
                    redemption_fee = ftps.get_applied_feature_at( document_date, 
                                                                  premium_schedule.valid_from_date, 
                                                                  premium_schedule.premium_amount,
                                                                  'redemption_fee', 
                                                                  default=D(0)).value 
                    
                    #begin redemption_fee
                    redemption_fee_amount = max( 0, min( amount_to_deduce - redemption_rate_amount, redemption_fee ) )
                    #end redemption_fee
                    
                    transaction_8 += [
                        self.create_line( ProductBookingAccount( 'redemption_fee_revenue'),
                                          redemption_fee_amount * -1,
                                          'redemption %s %s'%(full_account_number, agreement.code),
                                          'redemption_attribution',
                                          within_id = ftps.id), 
                        self.create_line( ProductBookingAccount( 'effective_interest_tax'),
                                          effective_interest_tax_to_apply * -1,
                                          'redemption %s %s'%(full_account_number, agreement.code),
                                          'redemption_attribution',
                                          within_id = ftps.id),
                        self.create_line( ProductBookingAccount( 'fictive_interest_tax'),
                                          fictive_interest_tax_to_apply * -1,
                                          'redemption %s %s'%(full_account_number, agreement.code),
                                          'redemption_attribution',
                                          within_id = ftps.id), 
                    ]
                    
                    LOGGER.debug( 'market fluctuation : %s'%market_fluctuation )
                    if market_fluctuation != 0:
                        transaction_8 += [                    
                            self.create_line( ProductBookingAccount( 'market_fluctuation_revenue'),
                                              market_fluctuation * -1,
                                              'market fluctuation %s %s'%(full_account_number, agreement.code),
                                              'redemption_attribution',
                                              within_id = ftps.id),
                        ]

                    if abs(amount_to_deduce) >= self.delta:
                        for sales in self.create_sales(premium_schedule,
                                                       book_date,
                                                       document_date,
                                                       (amount_to_deduce - redemption_rate_amount - redemption_fee_amount - effective_interest_tax_to_apply - fictive_interest_tax_to_apply - market_fluctuation)* -1,
                                                       lines + transaction_8,
                                                       product.redemption_book,
                                                       'redemption_attribution',
                                                       within_id = ftps.id):
                            related_sales.append(sales)
                            yield sales

                switch_out_amount = self.get_total_amount_until(premium_schedule, 
                                                                thru_document_date = document_date, 
                                                                thru_book_date = book_date, 
                                                                fulfillment_type = 'switch_out', 
                                                                account = FinancialBookingAccount(),
                                                                within_id = ftps.id)[0]
                    
                switch_deduction_amount = self.get_total_amount_until(premium_schedule, 
                                                                      thru_document_date = document_date, 
                                                                      thru_book_date = book_date, 
                                                                      fulfillment_type = 'switch_deduction', 
                                                                      account = FinancialBookingAccount(),
                                                                      within_id = ftps.id)[0]
                
                amount_to_switch = (switch_out_amount + switch_deduction_amount) * -1
                if abs(amount_to_switch) >= self.delta:

                    switch_out_fee = ftps.get_applied_feature_at( document_date, premium_schedule.valid_from_date, premium_schedule.premium_amount, 'switch_out_fee', default=D(0)).value
                    switch_out_rate = ftps.get_applied_feature_at( document_date, premium_schedule.valid_from_date, premium_schedule.premium_amount, 'switch_out_rate', default=D(0)).value                    
                    switch_out_cost = switch_out_fee + (-1 * switch_out_amount * switch_out_rate) / D(100)
                    
                    transaction_27 = [
                        self.create_line( FinancialBookingAccount(),
                                          amount_to_switch,
                                          'switch %s'%(agreement.code),
                                          'switch_deduction',
                                          within_id = ftps.id),
                        self.create_line( ProductBookingAccount( 'switch_revenue' ),
                                          -1 * switch_out_cost,
                                          'switch %s %s'%(full_account_number, agreement.code),
                                          'switch_deduction',
                                          within_id = ftps.id),
                        self.create_line( ProductBookingAccount( 'switch_deduction_revenue' ),
                                          (amount_to_switch - switch_out_cost) * -1,
                                          'switch %s %s'%(full_account_number, agreement.code),
                                          'switch_deduction',
                                          within_id = ftps.id), ]
                    
                    transaction_28 = []
                    for switch_in_ftps in transaction.consisting_of:
                        if switch_in_ftps.premium_schedule!=premium_schedule:
                            continue
                        if switch_in_ftps.quantity > 0:
                            
                            amount_to_switch_in = amount_to_switch - switch_out_cost
                            #switch_in_fee = switch_in_ftps.get_applied_feature_at(document_date, premium_schedule.valid_from_date, 'switch_in_fee', default=D(0)).value
                            #switch_in_rate = switch_in_ftps.get_applied_feature_at(document_date, premium_schedule.valid_from_date, 'switch_in_rate', default=D(0)).value
                    
                            if transaction_28:
                                raise UserException('Transaction %s has more than one switch out'%(transaction.id))
                            
                            transaction_28 = [
                                self.create_line( ProductBookingAccount( 'switch_deduction_cost'),
                                                  amount_to_switch_in,
                                                  'switch %s'%(agreement.code),
                                                  'switch_attribution',
                                                  within_id = switch_in_ftps.id),
                                self.create_line( FinancialBookingAccount(),
                                                  amount_to_switch_in * -1,
                                                  'switch %s %s'%(full_account_number, agreement.code), 
                                                  'switch_attribution',
                                                  within_id = switch_in_ftps.id ),
                            ]
                    if not transaction_28:
                        raise UserException('Transaction %s has no switch out defined'%(transaction.id))

                    for sales in self.create_sales( premium_schedule,
                                                    book_date,
                                                    document_date,
                                                    0,
                                                    transaction_27 + transaction_28,
                                                    product.switch_book,
                                                    'switch_deduction',
                                                    within_id = ftps.id ):
                        related_sales.append(sales)
                        yield sales
            if len( related_sales ):
                sales = related_sales[0]
                for applied_notification in package.get_applied_notifications_at(
                    document_date,
                    'transaction-completion',
                    premium_period_type = premium_schedule.period_type, 
                    subscriber_language = premium_schedule.get_document_language_at( document_date ),
                ):
                    work_effort = FinancialWorkEffort.get_open_work_effort(u'notification')
                    for recipient, _broker in account.get_notification_recipients(document_date):
                        FinancialAccountNotification( generated_by = work_effort,
                                                      date = document_date,
                                                      balance = 0,
                                                      application_of = applied_notification,
                                                      account = premium_schedule.financial_account,
                                                      entry_book_date = sales.book_date,
                                                      entry_document = sales.document_number,
                                                      entry_book = sales.book,
                                                      entry_line_number = sales.first_line_number,
                                                      natuurlijke_persoon = recipient.natuurlijke_persoon,
                                                      rechtspersoon = recipient.rechtspersoon,
                                                      )
                orm.object_session( premium_schedule ).flush()
