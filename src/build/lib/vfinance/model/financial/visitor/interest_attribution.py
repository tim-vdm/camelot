'''
Created on Jan 18, 2011

@author: tw55413
'''

import logging
import datetime

from sqlalchemy import sql

from vfinance.model.financial.transaction import FinancialTransactionPremiumSchedule

LOGGER = logging.getLogger('vfinance.model.financial.visitor.interest_attribution')

from abstract import FinancialBookingAccount
from ...bank.visitor import ProductBookingAccount
from provision import ProvisionVisitor, premium_data

class InterestAttributionVisitor( ProvisionVisitor ):
    """The interest attribution visitor will add interest earned during the past month to the
    Customer Account at the last day of the month.
    """
        
    def get_document_dates(self, premium_schedule, from_date, thru_date):
        if not premium_schedule.unit_linked:
            for document_date in super(InterestAttributionVisitor, self).get_document_dates(premium_schedule, from_date, min(thru_date, premium_schedule.valid_thru_date)):
                yield document_date
            if thru_date > premium_schedule.valid_thru_date:
                yield premium_schedule.valid_thru_date
            for ftps in FinancialTransactionPremiumSchedule.query.filter( sql.and_( FinancialTransactionPremiumSchedule.premium_schedule_id == premium_schedule.id,
                                                                                    FinancialTransactionPremiumSchedule.current_status_sql == 'verified',
                                                                                    FinancialTransactionPremiumSchedule.from_date_sql <= thru_date, 
                                                                                    FinancialTransactionPremiumSchedule.thru_date_sql >= from_date )
                                                                          ):
                yield min( premium_schedule.valid_thru_date, ftps.transaction_from_date )
    
    def visit_premium_schedule_at(self, 
                                  premium_schedule, 
                                  document_date, 
                                  book_date, 
                                  _last_visited_document_date):
        """Visit a single premium schedule, and apply changes
        when applicable
        :return: a text string if something has been done
        """
        LOGGER.debug( 'visit at %s'%( document_date ) )

        document_date = min( document_date, premium_schedule.valid_thru_date - datetime.timedelta(days=1) )
        
        # get all entries
        entries = list( self.get_entries( premium_schedule, 
                                          from_document_date = None, 
                                          thru_document_date = document_date,
                                          from_book_date = None, 
                                          thru_book_date = None,
                                          fulfillment_types = ['depot_movement',
                                                               'profit_attribution',
                                                               ], 
                                          account = FinancialBookingAccount('uninvested') ) )
        if not entries:
            return

        # generate list of premium payments and already attributed interests 
        premiums = []
        already_attributed_interests = []
        already_attributed_additional_interests = []
        for entry in entries:
            associated_surrenderings = []
            # @todo : investigate performance implications of this step
            for surrender_entry in self.get_entries( premium_schedule,
                                                     thru_document_date = document_date,
                                                     fulfillment_types = ['capital_redemption_deduction', 
                                                                          'interest_redemption_deduction', 
                                                                          'additional_interest_redemption_deduction'],
                                                     account = FinancialBookingAccount('uninvested'),
                                                     associated_to_id = entry.fulfillment_id ):
                associated_surrenderings.append( surrender_entry )
            
            
            interest_attribution_at_document_date = self.get_total_amount_until( premium_schedule, 
                                                                                 document_date, 
                                                                                 fulfillment_type = 'interest_attribution', 
                                                                                 account = FinancialBookingAccount('uninvested'),
                                                                                 associated_to_id = entry.fulfillment_id,)[0]
    
            additional_interest_attribution_at_document_date = self.get_total_amount_until( premium_schedule, 
                                                                                            document_date, 
                                                                                            fulfillment_type = 'additional_interest_attribution', 
                                                                                            account = FinancialBookingAccount('uninvested'),
                                                                                            associated_to_id = entry.fulfillment_id)[0]

            already_attributed_interests            += [ interest_attribution_at_document_date ]
            already_attributed_additional_interests += [ additional_interest_attribution_at_document_date ]
            
            premiums += [premium_data(date = entry.doc_date, 
                                      amount = entry.amount * (-1),
                                      gross_amount = entry.amount * (-1),  # FOUT!!!!
                                      associated_surrenderings = associated_surrenderings)]

        # calc interests
        earliest_document_date = min(entries, key = lambda e: e.doc_date).doc_date
        pvresult = list( self.get_provision( premium_schedule,
                                             earliest_document_date, 
                                             [document_date],
                                             old_provisions = None, # altijd nul, bedrag zit in premiums
                                             premiums = premiums ) )[0]
                
        # do interest bookings for all entries
        for i, entry in enumerate(entries):
    
            LOGGER.debug('interest attribution at %s'%document_date)
            LOGGER.debug(' interest attribution at document date           : %s' % (already_attributed_interests[i]) )
            LOGGER.debug(' additional interest attribution at document date: %s' % (already_attributed_additional_interests[i]) )

            interest = pvresult[1][i].interest
            additional_interest = pvresult[1][i].additional_interest
    
            LOGGER.debug(' interest attribution                            : %s' % (interest))
            LOGGER.debug(' additional interest attribution                 : %s' % (additional_interest))

            if abs(interest + already_attributed_interests[i]) >= self.delta or \
               abs(additional_interest + already_attributed_additional_interests[i]) >= self.delta:
                for step in self.create_account_movements( premium_schedule, 
                                                           book_date, 
                                                           document_date, 
                                                           interest + already_attributed_interests[i], 
                                                           additional_interest + already_attributed_additional_interests[i],
                                                           entry ):
                    yield step

    def create_account_movements(self,
                                 premium_schedule,
                                 book_date,
                                 document_date,
                                 interest_amount,
                                 additional_interest_amount,
                                 entry
                                 ):
        """
        Transaction 32 and transaction 22
        """
        book_date = self.entered_book_date(document_date, book_date)
        
        product = premium_schedule.product
        
        if not product.interest_book:
            return
        
        agreement = premium_schedule.agreed_schedule.financial_agreement
        
        if abs( interest_amount ) >= self.delta:
            transaction_22 = [
                self.create_line( ProductBookingAccount( 'interest_cost' ),
                                  interest_amount,
                                  agreement.code, 
                                  'interest_attribution',
                                  associated_fulfillment_id = entry.fulfillment_id),
                self.create_line( FinancialBookingAccount(),
                                  interest_amount * -1,
                                  agreement.code, 
                                  'interest_attribution',
                                  associated_fulfillment_id = entry.fulfillment_id),
            ] 
        else:
            transaction_22 = []
        
        if abs( additional_interest_amount ) >= self.delta:
            transaction_32 = [
                self.create_line( ProductBookingAccount( 'additional_interest_cost' ),
                                  additional_interest_amount,
                                  agreement.code, 
                                  'additional_interest_attribution',
                                  associated_fulfillment_id = entry.fulfillment_id),
                self.create_line( FinancialBookingAccount(),
                                  additional_interest_amount * -1,
                                  agreement.code, 
                                  'additional_interest_attribution',
                                  associated_fulfillment_id = entry.fulfillment_id),
            ] 
        else:
            transaction_32 = []

        for sales in self.create_sales( premium_schedule, 
                                        book_date, 
                                        document_date, 
                                        0, 
                                        transaction_22 + transaction_32,
                                        product.interest_book,
                                        'interest_attribution' ):
            yield sales

