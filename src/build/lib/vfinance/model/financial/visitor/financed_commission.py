import datetime
import decimal
import logging
from decimal import Decimal as D

from abstract import ( AbstractVisitor,
                       FinancialBookingAccount )
from ...bank.visitor import ProductBookingAccount
from account_attribution import AccountAttributionVisitor
#from transaction_initiation import TransactionInitiationVisitor

LOGGER = logging.getLogger('vfinance.model.financial.visitor.financed_commission')
#LOGGER.setLevel( logging.DEBUG )

ONE_DAY = datetime.timedelta(days=1)

class FinancedCommissionVisitor(AbstractVisitor):
       
    dependencies = [AccountAttributionVisitor, ]
            
    def get_document_dates(self, premium_schedule, from_date, thru_date):
        #
        # if there is no financed commission deduction feature, and there are
        # no financed commission activations, skip this visitor
        #
        number_of_activations = len( list( self.get_entries( premium_schedule, 
                                                             fulfillment_type = 'financed_commissions_activation' ) ) )
        has_deduction_rate = premium_schedule.has_feature_between( from_date, thru_date, 'financed_commissions_deduction_rate' )
        
        if number_of_activations != 0 or has_deduction_rate:
            for document_date in super( FinancedCommissionVisitor, self ).get_document_dates( premium_schedule, from_date, thru_date):
                yield document_date
            
    def get_amount_to_deduce_at(self, premium_schedule, document_date, attribution_date, financed_amount, previously_remaining_capital):
        """
        Given a premium schedule, get the theoretical amount to deduce at a
        document date, assuming the document_date is the last date of a month
        for a principal amount attributed at attribution date
        :return (total_amount, interest, capital, remaining_capital):
        """
        periodicity = premium_schedule.get_applied_feature_at(document_date, attribution_date, premium_schedule.premium_amount, 'financed_commissions_periodicity', default=1)
        if document_date.month%periodicity.value != 0:
            return 0, 0, 0, previously_remaining_capital
        
        deduction_rate = premium_schedule.get_applied_feature_at(document_date, attribution_date, premium_schedule.premium_amount, 'financed_commissions_deduction_rate', default=0).value
        if not deduction_rate:
            return 0, 0, 0, previously_remaining_capital
        
        interest_rate = premium_schedule.get_applied_feature_at(document_date, attribution_date, premium_schedule.premium_amount, 'financed_commissions_interest_rate', default=0).value            
        deduced_interest = premium_schedule.get_applied_feature_at(document_date, attribution_date, premium_schedule.premium_amount, 'financed_commissions_deduced_interest', default=0).value
        
        interest = (previously_remaining_capital * interest_rate / 100)
        max_total_amount = (deduction_rate * financed_amount / 100).quantize(D('.01'), rounding=decimal.ROUND_HALF_UP)
        max_capital = (max_total_amount * (1 - deduced_interest / 100 )).quantize(D('.01'), rounding=decimal.ROUND_HALF_DOWN) - interest
        
        capital = min( previously_remaining_capital, max_capital )
        interest = interest + ( capital * deduced_interest / (100 * ( 1 - deduced_interest / 100 ) ) ).quantize(D('.01'), rounding=decimal.ROUND_HALF_UP)
        
        return capital + interest, interest, capital, previously_remaining_capital-capital
            
    def get_total_amounts_at(self, premium_schedule, activation_entry, document_date, fulfillment_type, within_id=None):
        """
        Get the total amount of booked entries of a certain fulfillment type on
        a document date.
        
        total_principal_movements is until the date before the document date
        
        return: (total_interest, total_principal, total_principal_movements)
        """
        
        total_interest = self.get_total_amount_at(premium_schedule, 
                                                  document_date, 
                                                  fulfillment_type = fulfillment_type, 
                                                  account = ProductBookingAccount('financed_commissions_interest'),
                                                  associated_to_id = activation_entry.fulfillment_id,
                                                  within_id = within_id)[0]
        
        total_principal = self.get_total_amount_at(premium_schedule, 
                                                   document_date,
                                                   fulfillment_type = fulfillment_type, 
                                                   account=FinancialBookingAccount('financed_commissions'),
                                                   associated_to_id = activation_entry.fulfillment_id,
                                                   within_id = within_id)[0]
        
        total_principal_movements = self.get_total_amount_until(premium_schedule,
                                                                thru_document_date = document_date - datetime.timedelta(days=1),
                                                                account=FinancialBookingAccount('financed_commissions'),
                                                                associated_to_id = activation_entry.fulfillment_id)[0]
                
        return (total_interest, total_principal, total_principal_movements)
        
    def get_total_amounts_at_end_of_months(self, premium_schedule, activation_entry, from_date, thru_date, fulfillment_type, within_id = None):
        """
        Get the total amount of booked entries of a certain fulfillment type for each last day
        of the month starting from the premium_schedule from date to the thru date.
        
        If the premium schedule from date is the last day of the month, it will not be included.
        
        :param premium_schedule: a FinancialAccountPremiumSchedule
        :param thru_date: date until which to get the total amounts
        :param fulfillment_type: the type of fulfillment for which to get the total
        :return: a generator yielding (date, total_interest, total_principal, total_principal_movements)
        """
        for document_date in self.get_document_dates( premium_schedule, 
                                                      max(from_date, premium_schedule.valid_from_date + datetime.timedelta(days=1)), 
                                                      thru_date ):
            total_interest, total_principal, total_principal_movements = self.get_total_amounts_at( premium_schedule, 
                                                                                                    activation_entry,
                                                                                                    document_date, 
                                                                                                    fulfillment_type,
                                                                                                    within_id = within_id)
            yield (document_date,  total_interest, total_principal, total_principal_movements)
        
    def visit_activation_at(self, premium_schedule, activation_entry, document_date, book_date, _last_visited_document_date):
        entry_doc_date = activation_entry.doc_date
        if entry_doc_date:
            financed_amount = D(str(activation_entry.amount))
            remaining_capital = financed_amount
            LOGGER.debug( 'visit premium fulfillment of %s at %s'%(financed_amount, document_date) )
            for date, booked_interest, booked_principal, total_principal_movements in self.get_total_amounts_at_end_of_months( premium_schedule,  
                                                                                                                               activation_entry,
                                                                                                                               max(entry_doc_date + ONE_DAY, document_date), 
                                                                                                                               document_date, 
                                                                                                                               'financed_commissions_write_off'):
                LOGGER.debug( 'totals at %s : %s booked principal'%(date, booked_principal) ) 
                if date==document_date:
                    remaining_capital = financed_amount + total_principal_movements
                    (_total_amount, interest, principal, _new_remaining_capital) = self.get_amount_to_deduce_at( premium_schedule, 
                                                                                                                 date,
                                                                                                                 entry_doc_date, 
                                                                                                                 financed_amount, 
                                                                                                                 remaining_capital)
                    
                    if (abs(booked_interest + interest) >= D('0.01')) or (abs(booked_principal+principal) >= D('0.01')):
                        for step in self.create_account_movements( premium_schedule, activation_entry.fulfillment_id, book_date, date, interest + booked_interest, principal + booked_principal):
                            yield step

    def visit_premium_schedule_at( self, premium_schedule, document_date, book_date, last_visited_document_date ):
        for activation_entry in self.get_entries( premium_schedule, 
                                                  thru_document_date = document_date,
                                                  fulfillment_type = 'financed_commissions_activation',
                                                  account = FinancialBookingAccount('financed_commissions') ):
            for step in self.visit_activation_at( premium_schedule, activation_entry, document_date, book_date, last_visited_document_date ):
                yield step
    
    def create_account_movements(self, 
                                 premium_schedule, 
                                 associated_fulfillment_id, 
                                 book_date, 
                                 document_date,
                                 interest,
                                 capital
                                 ):
        """
        :return: a a list of FinancialAccountPremiumFulfillment that were generated
        """ 
        product = premium_schedule.product
        agreement = premium_schedule.agreed_schedule.financial_agreement
        
        book_date = self.entered_book_date(document_date, book_date)
        total_amount = interest + capital
        
        transaction_17 = [
            self.create_line( ProductBookingAccount( 'financed_commissions_interest' ), 
                              interest * -1, 
                              'interest %s'%agreement.code, 
                              'financed_commissions_write_off', 
                              associated_fulfillment_id ),
            self.create_line( FinancialBookingAccount( 'financed_commissions' ), 
                              capital * -1,
                              'principal %s'%agreement.code,
                              'financed_commissions_write_off', 
                              associated_fulfillment_id )
            ]
        
        transaction_18 = [
            self.create_line( FinancialBookingAccount(),
                              total_amount,
                              'financed commissions %s'%(agreement.code),
                              'financed_commissions_deduction', 
                              associated_fulfillment_id ),
            self.create_line( ProductBookingAccount('financed_commissions_deduction_cost'),
                              total_amount * -1,
                              'financed commissions %s'%(agreement.code), ),
            self.create_line( ProductBookingAccount('financed_commissions_deduction_revenue'),
                              total_amount,
                              'financed commissions %s'%(agreement.code), ),
            ]

        for sales in self.create_sales( premium_schedule,
                                        book_date, 
                                        document_date, 
                                        0, 
                                        transaction_17 + transaction_18,
                                        product.financed_commissions_sales_book,
                                        'financed_commissions_write_off', 
                                        associated_fulfillment_id
                                        ):
            yield sales

