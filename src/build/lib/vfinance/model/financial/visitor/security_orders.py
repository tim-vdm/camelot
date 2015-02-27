# -*- coding: utf-8 -*-
"""
Created on Mon Dec 20 16:32:06 2010

@author: tw55413
"""

import collections
import decimal
import logging
from decimal import Decimal as D

from camelot.core.exception import UserException
from camelot.model.authentication import end_of_times
from sqlalchemy import sql

from ..constants import precision
from ..security import FinancialSecurityQuotation
from ..security_order import FinancialSecurityOrderLine
from ..transaction import (FinancialTransactionPremiumSchedule,
                           FinancialTransaction)
from .abstract import AbstractVisitor, FinancialBookingAccount


LOGGER = logging.getLogger('vfinance.model.financial.visitor.security_orders')
#LOGGER.setLevel( logging.DEBUG )

max_target_percentage_delta = D('0.000001')
total_target_percentage = D(100)

security_order = collections.namedtuple('security_order',
                                        ['doc_date', 'fulfillment_type', 
                                         'fund_distribution', 'order_type', 
                                         'quantity', 'attribution_rate_quantity', 
                                         'associated_to', 'within_id'] )

attributed_to_redemption_fulfillment_types = {
    'financed_commissions_deduction': 'financed_commissions_redemption_deduction',
    'depot_movement': 'capital_redemption_deduction',
    }

class SecurityOrdersVisitor( AbstractVisitor ):
    #
    # These are the types of fulfillments for which securities will be ordered
    #
    fulfillment_types = ['depot_movement', 
                         'financed_commissions_deduction', 
                         'risk_deduction', 
                         'switch_attribution',
                         'financed_switch',
                         ]

    #
    # These are the types of transactions for which securities will be ordered
    #
    transaction_types = {'partial_redemption':'redemption',
                         'full_redemption':'redemption',
                         'switch':'switch_out'}
    
    def __init__( self, *args, **kwargs ):
        super( SecurityOrdersVisitor, self ).__init__(*args, **kwargs)
        self._earliest_investment_date_cache = dict()
        #
        # dictionary with as key the id of the security and as value a list
        # of security quotation tuples
        #
        self._document_dates_cache = dict()
        self._quotation_values_at_dates_cache = dict()
        self._quotation_at_date_cache = dict()
        
    def get_valid_quotation_at_date( self, fund, document_date, quantity_to_invest ):
        key = (fund.id, document_date, quantity_to_invest > 0)
        try:
            quotation = self._quotation_at_date_cache[key]
        except KeyError:
            quotation = FinancialSecurityQuotation.valid_quotation( fund, document_date, quantity_to_invest )
            self._quotation_at_date_cache[key] = quotation
        return quotation
    
    def get_earliest_investment_date( self, premium_schedule ):
        try:
            earliest_investment_date = self._earliest_investment_date_cache[ premium_schedule.id ]
        except KeyError:
            earliest_investment_date = premium_schedule.earliest_investment_date
            self._earliest_investment_date_cache[ premium_schedule.id ] = earliest_investment_date
        return earliest_investment_date
        
    def get_limited_quantity( self, premium_schedule, fund_distribution, thru_document_date, quantity_type, quantity, uninvested_orders=0 ):
        """Limit the quantity to order with regard to the available quantity"""
        #print 'LIMIT QUANTITY', thru_document_date, quantity_type, quantity, uninvested_orders
        if quantity < 0:         
            total_available_quantity = self.get_total_amount_until( premium_schedule, 
                                                                    thru_document_date = thru_document_date, 
                                                                    thru_book_date = self._end_of_times, 
                                                                    account = FinancialBookingAccount( 'fund', fund_distribution.fund ) )
            
            #print total_available_quantity, uninvested_orders
            if quantity_type == 'amount':
                available_quantity = total_available_quantity[0] - uninvested_orders
                quantity = max( quantity, available_quantity ) # max, because both pending and available are negative
            else:
                available_quantity = total_available_quantity[1] + uninvested_orders
                quantity = max( quantity, -1 * available_quantity )
            #print '==>', quantity
            
        return quantity
    
    def get_attribution_rate_quantity( self, 
                                       fund, 
                                       distribution_date, 
                                       quantity_to_invest, 
                                       quantity_type,
                                       reverse = False ):
        """
        From the quantity to invest, determine the exit or entry fee
        
        :param fund: the FinancialSecurity in which will be invested
        :param distribution_date: the date at which the tariff will be applied
        :param quantity_to_invest: the amount or number of units that will be invested, a positive number
            means a purchase of units
        :param quantity_type: either 'amount' or 'units'
        :param reverse: if reverse is True, calculate the attribution rate starting
            from the amount that allready includes the attribution rate
        
        :return: the attribution rate, of the same quantity type as the quantity to invest, and is always
        negative, indicating it needs to be subtracted from the quantity to invest.
        """
        
        if quantity_to_invest < 0:
            attribution_rate = fund.get_feature_value_at( distribution_date, 'exit_rate' )
        else:
            attribution_rate = fund.get_feature_value_at( distribution_date, 'entry_rate' )
            
        if reverse:
            divide_by = 101
        else:
            divide_by = 100
            
        return ( abs( quantity_to_invest ) * -1 * attribution_rate / divide_by ).quantize(precision[quantity_type], rounding=decimal.ROUND_HALF_UP)

    def get_amounts_to_invest(self, premium_schedule, attributed_amount, distribution_date, fund_distributions=[]):
        """Split an amount over a set of fund distributions
        
        :param fund_distributions: list with elements of type FundDistribution, if not given or empty, the list of the
        premium schedule at the distribution date will be taken.
        :param attributed_amount: the amount that needs to be invested in the funds, a positive amount is an
        investment, a negative amount a desinvestment.
        
        :return: a generator of tuples (premium_distribution, amount_to_invest, attribution_rate_amount)
        
        The sum of the amounts to invest can be less than the attributed amount because of
        the attribution rate amount.
        """
        if not fund_distributions:
            fund_distributions = premium_schedule.get_funds_at( distribution_date )
        if fund_distributions:
            total_percentage = sum(fund_distribution.target_percentage for fund_distribution in fund_distributions)
            if total_percentage not in [0, 100]:
                raise UserException( 'Total fund fund distribution is %s%% on %s, different from 100'%( total_percentage, distribution_date ) )
            distribution = list((fd.fund_id, fd.target_percentage) for fd in fund_distributions)
            for fund_id, amount_to_invest, _percentage in self.distribute_amount(
                attributed_amount,
                distribution,
                100):
                for fund_distribution in fund_distributions:
                    if fund_distribution.fund_id == fund_id:
                        yield (fund_distribution, amount_to_invest)
                        break
                else:
                    raise Exception('Fund has no distribution')
    
    def get_ordered_amount(self, premium_schedule, document_date, fulfillment_type, fund_id, order_type):
        
        FSOL = FinancialSecurityOrderLine
        
        query =  sql.select([sql.func.coalesce(sql.func.sum(FSOL.quantity), 0)],
                             whereclause = sql.and_(FSOL.premium_schedule==premium_schedule,
                                                    FSOL.described_by == order_type,
                                                    FSOL.document_date == document_date,
                                                    FSOL.fulfillment_type == fulfillment_type,
                                                    FSOL.financial_security_id == fund_id))
                             
        return FinancialSecurityOrderLine.query.session.execute( query ).first()[0] or 0
                           
    def get_premium_security_orders(self, premium_schedule, order_date, from_document_date):
        """
        :param order_date: the earliest date on which the securities can be ordered
        :param from_document_date: only documents after this date will be considered
            for the generation of premium security orders
        
        :return : a generator that yields tuples of the `security_orders` type for
            the securities that have to be ordered or sold.
        """ 
        LOGGER.debug( 'get premium security orders for order date %s from document date %s'%( order_date, from_document_date ) )
        
        earliest_investment_date = self.get_earliest_investment_date( premium_schedule )
        
        if earliest_investment_date <= order_date and premium_schedule.unit_linked==True:
            #
            # Collect the orders generated by other entries (financed commissions)
            #
            uninvested_account = FinancialBookingAccount( 'uninvested' )
            
            for entry in self.get_entries( premium_schedule, 
                                           max( premium_schedule.valid_from_date, from_document_date ),
                                           order_date,
                                           from_book_date = None, 
                                           thru_book_date = end_of_times(),
                                           fulfillment_types = self.fulfillment_types,
                                           account = uninvested_account ):
                    
                    attributed_amount = entry.amount
                    fund_distributions = None
                    if entry.within_id:
                        ftps = FinancialTransactionPremiumSchedule.get( entry.within_id )
                        fund_distributions = ftps.get_fund_distribution()
                        
                    LOGGER.debug( 'distribute %s at %s : %s'%( entry.fulfillment_type,
                                                               entry.doc_date,
                                                               entry.amount ) )
                    #
                    # Part of this amount might have been involved in a redemption, and as such is no
                    # longer due.  This amount cannot be deduced from the total amount that needs to
                    # be distributed to the funds, but should only be applied to the units that have
                    # not yet been sold
                    #
                    attributed_to_redemption_fulfillment_type = attributed_to_redemption_fulfillment_types.get(entry.fulfillment_type)
                    if attributed_to_redemption_fulfillment_type is not None:
                        amount_attributed_to_redemption = self.get_total_amount_until( premium_schedule,
                                                                                       fulfillment_type = attributed_to_redemption_fulfillment_type, 
                                                                                       account = uninvested_account,
                                                                                       associated_to_id = entry.fulfillment_id )[0] * -1
                    else:
                        amount_attributed_to_redemption = 0

                    for fund_distribution, amount_to_invest in self.get_amounts_to_invest( premium_schedule, 
                                                                                           attributed_amount * -1, 
                                                                                           entry.doc_date,
                                                                                           fund_distributions = fund_distributions):
                        LOGGER.debug( ' %s : %s'%( fund_distribution.fund.name, amount_to_invest ) )
                        
                        if amount_attributed_to_redemption != 0:
                            
                            # this amount includes the attribution rate amount
                            invested_amount = self.get_total_amount_until( premium_schedule, 
                                                                           fulfillment_type = 'fund_attribution', 
                                                                           account = FinancialBookingAccount( 'fund', fund_distribution.fund ),
                                                                           associated_to_id = entry.fulfillment_id )[0] * -1
                            
                            invested_attribution_rate_amount = self.get_attribution_rate_quantity( fund_distribution.fund, 
                                                                                                   entry.doc_date, 
                                                                                                   invested_amount, 
                                                                                                   'amount',
                                                                                                   reverse = True )
                                                  
                            LOGGER.debug( '  invested amount : %s'%invested_amount )
                            LOGGER.debug( '  invested attribution rate : %s'%invested_attribution_rate_amount )
                            LOGGER.debug( '  amount attributed to redemption : %s'%amount_attributed_to_redemption)
                            net_invested_amount = invested_amount - invested_attribution_rate_amount # amount that went to/from the cash account with regard to this
                                                                                                     # this fund and this entry, so for this amount the units have
                                                                                                     # been sold/bought
                            uninvested_amount = amount_to_invest - net_invested_amount               # this part can be compensated with the redeemed amount
                            if amount_to_invest < 0:
                                redeemed_amount = min( uninvested_amount * -1, amount_attributed_to_redemption ) # verified against account 2904 of Patronale
                            else:
                                redeemed_amount = max( uninvested_amount * -1, amount_attributed_to_redemption )
                                
                            amount_to_invest = amount_to_invest + redeemed_amount
                            LOGGER.debug( '  redeemed amount : %s'%redeemed_amount )
                            #print '---> redeemed amount', redeemed_amount, '-->', amount_to_invest
                            amount_attributed_to_redemption -= redeemed_amount
                        else:
                            redeemed_amount = 0

                        attribution_rate_amount = self.get_attribution_rate_quantity( fund_distribution.fund, 
                                                                                      entry.doc_date, 
                                                                                      amount_to_invest, 
                                                                                      'amount' )
                        LOGGER.debug( '  without redemption : %s + %s'%( amount_to_invest, attribution_rate_amount ) )
                
                        amount_to_order = amount_to_invest + attribution_rate_amount
                        LOGGER.debug( 'security order for %s %s %s %s for %s'%( entry.fulfillment_type,
                                                                                entry.book,
                                                                                entry.document,
                                                                                entry.book_date,
                                                                                amount_to_order ) )
                        
                        yield security_order( doc_date = entry.doc_date, 
                                               fulfillment_type = entry.fulfillment_type, 
                                               fund_distribution = fund_distribution, 
                                               order_type = 'amount', 
                                               quantity = amount_to_order, 
                                               attribution_rate_quantity = attribution_rate_amount, 
                                               associated_to = entry, 
                                               within_id = None )

            #
            # @todo : investigate performance implications of this query
            # @todo : exclude transactions before the from_document_date
            #
            transaction_schedule_query = FinancialTransactionPremiumSchedule.query.session.query( FinancialTransactionPremiumSchedule,
                                                                                                  FinancialTransaction )
            transaction_schedule_query = transaction_schedule_query.filter( sql.and_( FinancialTransactionPremiumSchedule.premium_schedule == premium_schedule,
                                                                                       FinancialTransactionPremiumSchedule.within_id == FinancialTransaction.id,
                                                                                       FinancialTransactionPremiumSchedule.quantity < 0,
                                                                                       FinancialTransaction.current_status == 'verified',
                                                                                       FinancialTransaction.thru_date >= order_date,
                                                                                       FinancialTransaction.from_date <= order_date,
                                                                                       FinancialTransaction.from_date >= from_document_date,
                                                                                       FinancialTransaction.agreement_date <= order_date,
                                                                                       FinancialTransaction.transaction_type != 'financed_switch',
                                                                                       ) )
            transaction_schedule_query = transaction_schedule_query.order_by( FinancialTransaction.id, FinancialTransactionPremiumSchedule.id )
            #
            # Collect the orders generated by financial transactions (redemptions, ...)
            #
            for transaction_schedule, transaction in transaction_schedule_query.all():
                document_date = transaction.from_date
                fund_distributions = transaction_schedule.get_fund_distribution()
                
                fulfillment_type = self.transaction_types[transaction.transaction_type]
                
                LOGGER.debug( 'collect orders for transaction %s : %s'%(transaction.id, transaction.transaction_type))
                
                if transaction_schedule.described_by == 'amount':
                    for fund_distribution, amount_to_invest in self.get_amounts_to_invest( premium_schedule,
                                                                                           transaction_schedule.quantity,
                                                                                           document_date,
                                                                                           fund_distributions=fund_distributions):
                        
                        attribution_rate_amount = self.get_attribution_rate_quantity( fund_distribution.fund, 
                                                                                      document_date, 
                                                                                      amount_to_invest, 
                                                                                      'amount' )
                        
                        yield security_order( doc_date=document_date, 
                                               fulfillment_type=fulfillment_type, 
                                               fund_distribution=fund_distribution, 
                                               order_type='amount', 
                                               quantity=amount_to_invest + attribution_rate_amount, 
                                               attribution_rate_quantity=attribution_rate_amount, 
                                               associated_to=None, 
                                               within_id=transaction_schedule.id)

                else:
                    for fund_distribution in fund_distributions:
                        _total_amount, total_quantity = self.get_total_amount_until( premium_schedule,
                                                                                     thru_document_date = document_date, 
                                                                                     account=FinancialBookingAccount( 'fund', fund_distribution.fund ) )[:2]
                        
                        quantity = (transaction_schedule.quantity / 100) * total_quantity
                        quantity = quantity.quantize(D('.000001'), rounding=decimal.ROUND_DOWN)
                        
                        LOGGER.debug( 'quantity to order : %s'%quantity )
                        
                        attribution_rate_quantity = self.get_attribution_rate_quantity( fund_distribution.fund, 
                                                                                        document_date, 
                                                                                        quantity, 
                                                                                        'units' )
                                        
                        yield security_order( doc_date=document_date, 
                                               fulfillment_type=fulfillment_type, 
                                               fund_distribution=fund_distribution, 
                                               order_type='units', 
                                               quantity=quantity, 
                                               attribution_rate_quantity=attribution_rate_quantity, 
                                               associated_to=None, 
                                               within_id=transaction_schedule.id)

