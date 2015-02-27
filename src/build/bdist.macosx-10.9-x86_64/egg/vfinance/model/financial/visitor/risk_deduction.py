'''
Created on Jan 18, 2011

@author: tw55413
'''

import datetime
import calendar
import logging

LOGGER = logging.getLogger('vfinance.model.financial.visitor.risk_deduction')

from integration.tinyerp.convenience import add_months_to_date

from abstract import FinancialBookingAccount
from provision import ProvisionVisitor, premium_data
from financed_commission import FinancedCommissionVisitor
from security_quotation import SecurityQuotationVisitor
from account_attribution import AccountAttributionVisitor
from ...bank.visitor import ProductBookingAccount

class RiskDeductionVisitor( ProvisionVisitor ):
    """The risk deduction visitor will deduce risk premiums from the
    Customer Account at the first day of the month for the risk that will be covered
    during that month.
    """
    
    dependencies = [ SecurityQuotationVisitor, 
                     FinancedCommissionVisitor, 
                     AccountAttributionVisitor ]
    
    def get_document_dates(self, premium_schedule, from_date, thru_date):
        if len( premium_schedule.applied_coverages ):
            #
            # Always do a first risk deduction at the beginning of the premium schedule
            #
            if premium_schedule.valid_from_date >= from_date and premium_schedule.valid_from_date <= thru_date:
                yield premium_schedule.valid_from_date
            #
            # After this, always at the first day of the month
            #   
            document_date = from_date
            while document_date <= thru_date:
                document_date = datetime.date(document_date.year, document_date.month, 1)
                if document_date >= from_date:
                    yield document_date
                document_date = add_months_to_date(document_date, 1)            
        
    def get_accounts(self, premium_schedule):
        return set([FinancialBookingAccount()] + [FinancialBookingAccount('fund', fund = fund_distribution.fund) for fund_distribution in premium_schedule.fund_distribution])
        
    def _visit_unit_linked_premium_schedule_at(self, premium_schedule, document_date, book_date, _last_visited_document_date):
        """Visit a single unit-linked premium schedule, and apply changes
        when applicable. Don't call directly, used visit_premium_schedule_at instead.
        :return: a text string if something has been done
        """
        if premium_schedule.product.unit_linked == False:
            raise StopIteration()
        
        accounts = self.get_accounts(premium_schedule)
               
        total_provision_before_document_date = sum( self.get_total_amount_until(premium_schedule, 
                                                                                document_date,
                                                                                account = account)[0] for account in accounts ) * -1
                                                                              
        risk_provision_at_document_date = sum( self.get_total_amount_at(premium_schedule, 
                                                                        document_date, 
                                                                        fulfillment_type = 'risk_deduction', 
                                                                        account = account)[0] for account in accounts )
          
        # for UL3 compatibility, we don't take into account security quotations at the document date, this makes
        # sense, since in theory we don't know these yet at that time
        security_quotation_at_document_date = sum( self.get_total_amount_at(premium_schedule, 
                                                                            document_date,
                                                                            fulfillment_type = 'security_quotation', 
                                                                            account = account)[0] for account in accounts ) * -1
          
        thru_date = datetime.date( document_date.year, document_date.month, calendar.monthrange(document_date.year, document_date.month)[1] )
        
        LOGGER.debug('risk deduction at %s'%document_date)
        LOGGER.debug(' total provision before document date : %s'%total_provision_before_document_date)
        LOGGER.debug(' risk provision at document date      : %s'%risk_provision_at_document_date)
        LOGGER.debug(' security quotation at document date  : %s'%security_quotation_at_document_date)
        
        for pvd,details in self.get_provision( premium_schedule,
                                               document_date, 
                                               [thru_date],
                                               old_provisions = [ total_provision_before_document_date - risk_provision_at_document_date - security_quotation_at_document_date ],
                                               premiums = [] ):
            risk = pvd.risk
            LOGGER.debug(' risk provision                      : %s'%risk)
            if abs(risk + risk_provision_at_document_date) >= self.delta:
                for step in self.create_account_movements(premium_schedule, book_date, document_date, (risk + risk_provision_at_document_date) * -1 ):
                    yield step
        
    def _visit_non_unit_linked_premium_schedule_at(self, premium_schedule, document_date, book_date, _last_visited_document_date):
        """Visit a single non-unit linked premium schedule, and apply changes
        when applicable. Don't call directly, used visit_premium_schedule_at instead.
        :return: a text string if something has been done
        """
        from datetime import timedelta
        if premium_schedule.product.unit_linked == True:
            raise StopIteration()

        def last_day_of_month(date):
            from datetime import timedelta
            if date.month == 12:
                return date.replace(day=31)
            return date.replace(month=date.month+1, day=1) - timedelta(days=1)

        # get all entries
        entries =  list( self.get_entries( premium_schedule, 
                                           from_document_date = None, 
                                           thru_document_date = document_date,
                                           from_book_date = None, 
                                           thru_book_date = None,
                                           fulfillment_types = ['depot_movement',
                                                                'profit_attribution'],
                                           account = FinancialBookingAccount() ) )
        if not entries:
            raise StopIteration()

        # generate list of premium payments and already deducted risks 
        premiums = []
        already_deducted_risks = []
        for entry in entries: 
            premiums += [premium_data(date = entry.doc_date, 
                                      amount = entry.amount * (-1),
                                      gross_amount = entry.amount * (-1),  # FOUT!!!!
                                      associated_surrenderings = [] )]
            
            risk_deduction_at_document_date = self.get_total_amount_until( premium_schedule, 
                                                                           document_date, 
                                                                           fulfillment_type = 'risk_deduction', 
                                                                           account = FinancialBookingAccount(),
                                                                           associated_to_id = entry.fulfillment_id,)[0]
            already_deducted_risks += [ risk_deduction_at_document_date ]  # positive number
            
        # dates for which we want results from provision visitor
        dates = [document_date - timedelta(days = 1), last_day_of_month(document_date)]

        # calc risks
        earliest_document_date = min(entries, key = lambda e: e.doc_date).doc_date
        pvresults = list( self.get_provision( premium_schedule,
                                              earliest_document_date, 
                                              dates,
                                              old_provisions = None, # altijd nul, bedrag zit in premiums
                                              premiums = premiums ) )  # risks in results are negative numbers

        # calc total risk accumulated up to that date for all dates in visitor output
        accumulated_risks_per_date = {} 
        accumulated_risks = [0] * len(entries)
        for e in pvresults:
            for i in range(0, len(entries)):
                accumulated_risks[i] += e[1][i].risk
            accumulated_risks_per_date[e[1][i].date] = accumulated_risks

        LOGGER.debug('risk deduction at %s'%document_date)
        LOGGER.debug(' total risk deducted at document date: %s' % (sum(already_deducted_risks)) )
        
        for i in range(0, len(entries)):
            depot_movement = entries[i]
            # Do bookings. All risk bookings are done on the fulfillment related to the first premium.
            # Step 1: check deducted risk at document date, and book correction if necessary
            if dates[0] in accumulated_risks_per_date:
                correction = ( already_deducted_risks[i] +  accumulated_risks_per_date[dates[0]][i] ) * (-1)
                if abs(correction) >= self.delta:
                    LOGGER.debug(' corrective risk deduction: %s' % (correction))
                    for step in self.create_account_movements(premium_schedule, 
                                                              book_date,
                                                              document_date,
                                                              correction,
                                                              depot_movement):
                        yield step
                    already_deducted_risks[i] += correction
    
            # Step 2: book deducted risk till end of month
            if dates[1] in accumulated_risks_per_date:
                amount = ( already_deducted_risks[i] + accumulated_risks_per_date[dates[1]][i] ) * (-1)
                if abs( amount ) >= self.delta:
                    LOGGER.debug(' risk deduction: %s' % (amount) )
                    for step in self.create_account_movements(premium_schedule, 
                                                              book_date, 
                                                              document_date, 
                                                              amount,
                                                              depot_movement):
                        yield step
        premium_schedule.query.session.flush()

    def visit_premium_schedule_at(self, premium_schedule, document_date, book_date, _last_visited_document_date):
        """Visit a single premium schedule, and apply changes
        when applicable
        :return: a text string if something has been done
        """
        if premium_schedule.product.unit_linked == True:
            for step in self._visit_unit_linked_premium_schedule_at(premium_schedule, document_date, book_date, _last_visited_document_date):
                yield step
        else:
            for step in self._visit_non_unit_linked_premium_schedule_at(premium_schedule, document_date, book_date, _last_visited_document_date):
                yield step
        
    def create_account_movements(self,
                                 premium_schedule,
                                 book_date, 
                                 document_date,
                                 total_amount,
                                 depot_movement = None
                                 ):
        """
        :return: a a list of FinancialAccountPremiumFulfillment that were generated
        """
        
        book_date = self.entered_book_date(document_date, book_date)
        product = premium_schedule.product
        agreement = premium_schedule.agreed_schedule.financial_agreement
        associated_fulfillment_id = None
        if depot_movement:
            associated_fulfillment_id = depot_movement.fulfillment_id
        
        if not product.risk_sales_book:
            raise StopIteration()
        
        transaction_20 = [
            self.create_line( ProductBookingAccount( 'risk_revenue' ),
                              total_amount * -1,
                              agreement.code, 
                              'risk_sales',
                              associated_fulfillment_id = associated_fulfillment_id ),
        ]      
        transaction_21 = [
            self.create_line( FinancialBookingAccount(),
                              total_amount,
                              'risk premium %s'%(agreement.code), 
                              'risk_deduction',
                              associated_fulfillment_id = associated_fulfillment_id
                              ),
            self.create_line( ProductBookingAccount( 'risk_deduction_cost' ),
                              total_amount * -1,
                              'risk premium %s'%(agreement.code),
                              'risk_deduction',
                              associated_fulfillment_id = associated_fulfillment_id
                              ),
            self.create_line( ProductBookingAccount( 'risk_deduction_revenue' ),
                              total_amount,
                              'risk premium %s'%(agreement.code),
                              'risk_deduction',
                              associated_fulfillment_id = associated_fulfillment_id
                              ), 
        ]
        

        for sales in self.create_sales( premium_schedule, 
                                        book_date, 
                                        document_date, 
                                        0, 
                                        transaction_20 + transaction_21,
                                        product.risk_sales_book,
                                        'risk_sales' ):
            yield sales

