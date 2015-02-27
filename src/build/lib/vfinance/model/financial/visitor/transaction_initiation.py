import logging

from decimal import Decimal as D

from sqlalchemy import orm, sql

from abstract import FinancialBookingAccount
from ...bank.visitor import ProductBookingAccount
from ..transaction import FinancialTransactionPremiumSchedule
from account_attribution import AccountAttributionVisitor
from financed_commission import FinancedCommissionVisitor

LOGGER = logging.getLogger('vfinance.model.financial.visitor.transaction_initiation')

class TransactionInitiationVisitor(FinancedCommissionVisitor):
    """
    First booking of a financial transaction, this initiates the transaction
    and makes sure the financed commissions principal is redeemed.
    
    This visitor will issue :ref:`transaction-24` and :ref:`transaction-25`
    
    If the transaction is a switch, this visitor will create the fund accounts
    needed for the switch
    """
    
    dependencies = [ AccountAttributionVisitor, FinancedCommissionVisitor]
    applicable_transaction_types = ('partial_redemption', 'full_redemption')
    
    def get_transactions(self, premium_schedule):
        """:return: a list of financial transactions"""
        return list(set(transaction_schedule.within for transaction_schedule in premium_schedule.transactions if transaction_schedule.within.current_status=='verified'))
    
    def get_document_dates(self, premium_schedule, from_date, thru_date):
        for transaction in self.get_transactions(premium_schedule):
            if transaction.from_date >= from_date and transaction.from_date <= thru_date:
                yield transaction.from_date

    def _initiate_profit_attribution(self, ftps, document_date, book_date):
        transaction = ftps.within
        premium_schedule = ftps.premium_schedule
        full_account_number = premium_schedule.full_account_number
        attributed_amount = self.get_total_amount_until(premium_schedule, 
                                                        thru_document_date = document_date, 
                                                        fulfillment_type = 'profit_attribution', 
                                                        account = FinancialBookingAccount(),
                                                        within_id = ftps.id)[0]
        amount_to_attribute = ftps.quantity + attributed_amount
        if abs(amount_to_attribute) >= self.delta:
            product = premium_schedule.product
            lines = [
                self.create_line( FinancialBookingAccount(),
                                  -1 * amount_to_attribute,
                                  'profit attribution %s'%(transaction.code),
                                  'profit_attribution',
                                  within_id = ftps.id),
                self.create_line( ProductBookingAccount('profit_attribution_cost'),
                                  amount_to_attribute,
                                  'profit attribution %s %s'%(full_account_number, transaction.code),
                                  'profit_attribution',
                                  within_id = ftps.id),
                self.create_line( ProductBookingAccount('profit_attribution_revenue'),
                                  -1 * amount_to_attribute,
                                  'profit attribution %s %s'%(full_account_number, transaction.code),
                                  'profit_attribution',
                                  within_id = ftps.id),
                self.create_line( ProductBookingAccount('profit_reserve'),
                                  amount_to_attribute,
                                  'profit attribution %s %s'%(full_account_number, transaction.code),
                                  'profit_attribution',
                                  within_id = ftps.id),
            ]
            for sales in self.create_sales( premium_schedule,
                                            book_date,
                                            document_date,
                                            0,
                                            lines,
                                            product.profit_attribution_book,
                                            'profit_attribution',
                                            within_id = ftps.id ):
                yield sales
            
    def _initiate_financed_switch(self, premium_schedule, transaction, document_date, book_date):
        for ftps in transaction.consisting_of:
            self._initiate_switch(ftps)
        
        switch_out = 0
        switch_in = 0
        lines = []
        
        for ftps in transaction.consisting_of:
            if ftps.premium_schedule != premium_schedule:
                continue
            # the various ftps'es can have a different account
            full_account_number = premium_schedule.full_account_number
            agreement = premium_schedule.agreed_schedule.financial_agreement
            product = premium_schedule.product

            switched_amount = self.get_total_amount_until(premium_schedule, 
                                                          thru_document_date = document_date, 
                                                          fulfillment_type = 'financed_switch', 
                                                          account = FinancialBookingAccount(),
                                                          within_id = ftps.id)[0]
            amount_to_switch = (ftps.quantity * -1) - switched_amount
            if abs(amount_to_switch) >= self.delta:
                
                switch_out_cost = 0
                switch_in_cost  = 0

                if ftps.quantity <= 0:
                    switch_out_fee = ftps.get_applied_feature_at(document_date, premium_schedule.valid_from_date, premium_schedule.premium_amount, 'switch_out_fee', default=D(0)).value
                    switch_out_rate = ftps.get_applied_feature_at(document_date, premium_schedule.valid_from_date, premium_schedule.premium_amount, 'switch_out_rate', default=D(0)).value  
                    switch_out_cost = switch_out_fee + (amount_to_switch * switch_out_rate) / D(100)
                    switch_account =  ProductBookingAccount('switch_deduction_revenue')
                    switch_out += (amount_to_switch - switch_out_cost) 
                else: 
                    switch_account = ProductBookingAccount('switch_deduction_cost')
                    switch_in += (amount_to_switch - switch_in_cost)
                    
                switch_cost = switch_out_cost + switch_in_cost
                
                lines.extend( [
                    self.create_line( FinancialBookingAccount(),
                                      amount_to_switch,
                                      'switch %s'%(agreement.code),
                                      'financed_switch',
                                      within_id = ftps.id),
                    self.create_line( ProductBookingAccount( 'switch_revenue' ),
                                      -1 * switch_cost,
                                      'switch %s %s'%(full_account_number, agreement.code),
                                      'financed_switch',
                                      within_id = ftps.id),
                    self.create_line( switch_account,
                                      (amount_to_switch - switch_cost) * -1,
                                      'switch %s %s'%(full_account_number, agreement.code),
                                      'financed_switch',
                                      within_id = ftps.id), ] )
        
        if lines:
            #
            # with financed switches, we need to be cautious to verify if the
            # switched out amount minus costs is equal to the switch in amount
            #
            # if abs( switch_out + switch_in ) >= self.delta:
            #    raise Exception( 'Switch out is %s while switch in is %s'%(switch_out, switch_in) )
            for sales in self.create_sales( premium_schedule,
                                            book_date,
                                            document_date,
                                            0,
                                            lines,
                                            product.switch_book,
                                            'financed_switch',
                                            within_id = ftps.id ):
                yield sales

    def _initiate_switch(self, ftps):
        #
        # no longer create fund distribution accounts here, since they should
        # exist before the visitors start
        #
        return ''
    
    def _initiate_redemption(self, ftps, document_date, book_date):
        
        premium_schedule = ftps.premium_schedule  
        #
        # Each activation of a financed commission will be treated separately,
        # in 2 parts :
        #
        #  * the part of the capital due that is still on the financed 
        #    commissions account
        #
        #  * the part of the captial due that has been transfered to the cash
        #    account but was not yet attribute to a fund
        #
        for activation_entry in self.get_entries( premium_schedule, 
                                                  thru_document_date = document_date,
                                                  fulfillment_type = 'financed_commissions_activation',
                                                  account = FinancialBookingAccount( 'financed_commissions' ) ):        
            transaction = ftps.within
            entry_doc_date = activation_entry.doc_date
            
            if transaction.transaction_type == 'full_redemption':
                redemption_rate = 100
            else:
                min_redemption = ftps.get_applied_feature_at(document_date, entry_doc_date,  premium_schedule.premium_amount, 'financed_commissions_min_redemption_rate', default=0).value
                max_redemption = ftps.get_applied_feature_at(document_date, entry_doc_date,  premium_schedule.premium_amount, 'financed_commissions_max_redemption_rate', default=100).value
                redemption_rate = min( min_redemption, max_redemption )
    
            if not redemption_rate:
                continue
                
            #
            # Part 1 : what is still on the financed commissions account
            #
            financed_amount = D(str(activation_entry.amount))
            LOGGER.debug( 'activation at %s : %s'%( activation_entry.doc_date,
                                                    activation_entry.amount ) )
            
            #
            # not only look at the part of the financed commissions that was
            # redeemed through this ftps, but look at all amounts, because 
            # each activation only needs to be redeemed once
            #
            interest_booked, principal_booked, principal_movements = self.get_total_amounts_at( premium_schedule,
                                                                                                activation_entry,
                                                                                                document_date,
                                                                                                'financed_commissions_redemption' )
        
            LOGGER.debug( ' principal redeemed at %s : %s'%( activation_entry.doc_date, principal_booked ) )
            LOGGER.debug( ' principal deactivated before %s : %s'%( activation_entry.doc_date, principal_movements ) )
            principal_to_book = financed_amount + principal_movements + principal_booked
            LOGGER.debug( ' principal to redeem : %s'%( principal_to_book ) )
            interest_to_book = 0
    
            financed_commissons_to_attribute = []
            #
            # Part 2 : what is not yet attributed to a fund
            #
            for deduction_entry in self.get_entries( premium_schedule, 
                                                     thru_document_date = document_date,
                                                     fulfillment_type = 'financed_commissions_deduction', 
                                                     account = FinancialBookingAccount(),
                                                     associated_to_id = activation_entry.fulfillment_id ):
            
                
                LOGGER.debug( ' deduction at %s : %s'%( deduction_entry.doc_date,
                                                        deduction_entry.amount ) )
            
                amount_attributed_to_funds = self.get_total_amount_until( premium_schedule,
                                                                          fulfillment_type = 'fund_attribution', 
                                                                          account = FinancialBookingAccount(),
                                                                          thru_document_date = document_date,
                                                                          associated_to_id = deduction_entry.fulfillment_id )[0]
    
                #
                # not only look at the part of the financed commissions that was
                # redeemed through this ftps, but look at all amounts, because 
                # entry.amount only needs to be redeemed once
                #
                amount_attributed_to_redemption = self.get_total_amount_until( premium_schedule,
                                                                               fulfillment_type = 'financed_commissions_redemption_deduction', 
                                                                               account = FinancialBookingAccount(),
                                                                               thru_document_date = document_date,
                                                                               associated_to_id = deduction_entry.fulfillment_id )[0]
                
                LOGGER.debug( ' attributed to funds : %s'%( amount_attributed_to_funds ) )
                LOGGER.debug( ' redeemed : %s'%( amount_attributed_to_redemption ) )
                
                not_attributed_amount = deduction_entry.amount + amount_attributed_to_funds + amount_attributed_to_redemption
                
                LOGGER.debug( ' to redeem : %s'%( not_attributed_amount ) )
                
                if abs(not_attributed_amount) >= self.delta:
                    financed_commissons_to_attribute.append(
                        self.create_line( FinancialBookingAccount(),
                                          not_attributed_amount * -1,
                                          'redemption of financed commission of %s'%deduction_entry.doc_date,
                                          'financed_commissions_redemption_deduction',
                                          deduction_entry.fulfillment_id,
                                          within_id = ftps.id )
                    )
                        
            if abs(principal_to_book) >= self.delta or abs(interest_to_book) >= self.delta or len(financed_commissons_to_attribute):
    
                agreement = premium_schedule.agreed_schedule.financial_agreement
                product = premium_schedule.product
                
                total_financed_commissions_to_attribute = sum(fc.amount for fc in financed_commissons_to_attribute)
                
                total_amount = principal_to_book + interest_to_book
                
                transaction_24 = []
                if abs( interest_to_book ) >= self.delta:
                    transaction_24.append( self.create_line( ProductBookingAccount( 'financed_commissions_interest' ), 
                                                             interest_to_book * -1, 
                                                             'interest %s'%agreement.code, 
                                                             'financed_commissions_redemption', 
                                                             activation_entry.fulfillment_id,
                                                             within_id = ftps.id ) )
                if abs( principal_to_book ) >= self.delta:
                    transaction_24.append( self.create_line( FinancialBookingAccount( 'financed_commissions' ), 
                                                             principal_to_book * -1,
                                                             'principal %s'%agreement.code,
                                                             'financed_commissions_redemption', 
                                                             activation_entry.fulfillment_id,
                                                             within_id = ftps.id ) )
                
                transaction_25 = [
                    self.create_line( FinancialBookingAccount(),
                                      total_amount - total_financed_commissions_to_attribute,
                                      'financed commissions %s'%(agreement.code),
                                      'financed_commissions_redemption_deduction', 
                                      activation_entry.fulfillment_id,
                                      within_id = ftps.id ),
                    ] + financed_commissons_to_attribute
                
                if total_amount >= self.delta:
                    transaction_25.extend( [
                        self.create_line( ProductBookingAccount('financed_commissions_deduction_cost'),
                                          total_amount * -1,
                                          'financed commissions %s'%(agreement.code), ),
                        self.create_line( ProductBookingAccount('financed_commissions_deduction_revenue'),
                                          total_amount,
                                          'financed commissions %s'%(agreement.code), ),
                        ] )
                
                for sales in self.create_sales( premium_schedule, 
                                                book_date, 
                                                document_date, 
                                                0, 
                                                transaction_24 + transaction_25,
                                                product.redemption_book,
                                                'financed_commissions_redemption', 
                                                activation_entry.fulfillment_id,
                                                within_id = ftps.id,
                                                ):
                    yield sales

    def visit_premium_schedule_at( self, premium_schedule, document_date, book_date, last_visited_document_date ):
        for transaction in self.get_transactions(premium_schedule):
            
            if transaction.from_date != document_date:
                continue
            
            if transaction.transaction_type in ('financed_switch',):
                for step in self._initiate_financed_switch(premium_schedule, transaction, document_date, book_date):
                    yield step
                continue
            
            session = orm.object_session(premium_schedule)
            for ftps in session.query(FinancialTransactionPremiumSchedule).filter(sql.and_(FinancialTransactionPremiumSchedule.within_id==transaction.id,
                                                                                            FinancialTransactionPremiumSchedule.premium_schedule_id==premium_schedule.id)):

                if transaction.transaction_type in ('partial_redemption', 'full_redemption'):
                    for step in self._initiate_redemption(ftps, document_date, book_date):
                        yield step
                        
                if transaction.transaction_type in ('switch',):
                    for step in self._initiate_switch(ftps):
                        yield step
                    
                if transaction.transaction_type in ('profit_attribution',):
                    for step in self._initiate_profit_attribution(ftps, document_date, book_date):
                        yield step
