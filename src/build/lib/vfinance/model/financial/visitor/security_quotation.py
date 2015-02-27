# -*- coding: utf-8 -*-
"""
Created on Thu Dec 30 23:23:56 2010

@author: tw55413
"""

import logging
import decimal
from decimal import Decimal as D
import collections

from sqlalchemy import sql
from security_orders import SecurityOrdersVisitor

from vfinance.model.financial.visitor.abstract import ( FinancialBookingAccount, 
                                                        SecurityBookingAccount )
from ...bank.visitor import ProductBookingAccount
from vfinance.model.financial.security import FinancialSecurityQuotation

LOGGER = logging.getLogger('vfinance.model.financial.visitor.security_quotation')
#LOGGER.setLevel( logging.DEBUG )

quotation_attributes =  [ 'purchase_date',
                          'sales_date',
                          'from_datetime',
                          'value',
                          'current_status',
                          'from_date'] 

quotation = collections.namedtuple( 'quotation',
                                    quotation_attributes )

class SecurityQuotationVisitor(SecurityOrdersVisitor):
    """
    Each time the quotation of a security changes, the value of an account
    changes.
    
    this value is reflected by booking a value change on the security account
    without booking aditional units.
    """

    def get_funds(self, premium_schedule):
        return set(fund_distribution.fund for fund_distribution in premium_schedule.fund_distribution)
    
    def get_quotation_value_at_date( self, fund, document_date ):
        key = (fund.id, document_date.year, document_date.month, document_date.day)
        try:
            quotation_value = self._quotation_values_at_dates_cache[ key ]
        except KeyError:
            quotation_value = fund.value_at( document_date )
            self._quotation_values_at_dates_cache[ key ] = quotation_value
        return quotation_value
            
    def get_document_date_quotations( self, fund_id ):
        try:
            quotations = self._document_dates_cache[ fund_id ]
        except KeyError:
            quotations = []
            for q in FinancialSecurityQuotation.query.filter( sql.and_(FinancialSecurityQuotation.current_status == 'verified',
                                                                       FinancialSecurityQuotation.financial_security_id == fund_id ) ).order_by(FinancialSecurityQuotation.from_datetime).all():
                quotation_data = dict( (k,getattr(q,k)) for k in quotation_attributes )
                quotations.append( quotation(**quotation_data ) )
            self._document_dates_cache[ fund_id ] = quotations
        return quotations
                                       
    def get_document_dates(self, premium_schedule, from_date, thru_date):
        fund_ids = [fund.id for fund in self.get_funds(premium_schedule)]
        quotation_dates = set()
        for fund_id in fund_ids:
            for quotation in self.get_document_date_quotations( fund_id ):
                if quotation.from_date >= from_date and quotation.from_date <= thru_date:
                    quotation_dates.add( quotation.from_date )
        return sorted( quotation_dates )
            
    def visit_premium_schedule_at(self, premium_schedule, document_date, book_date, _last_visited_document_date):
        for fund_distribution in premium_schedule.fund_distribution:
            # @todo: only call this func if this fund has a quotation at this doc date
            for step in self.attribute_security_quotation(premium_schedule, document_date, book_date, fund_distribution):
                yield step

    def attribute_security_quotation(self, premium_schedule, document_date, book_date, fund_distribution):
        """Adapt the value of an account to the value of the units at the document date.
        This is :ref:`transaction-7`
        :return: a list of FinancialAccountPremiumFulfillments that were generated
        """
        quotation_value = self.get_quotation_value_at_date( fund_distribution.fund, document_date )
        #
        # It might be that this fund has no quotation at the document date
        # (the document date might come from another distribution)
        #
        if quotation_value == None:
            return
        
        full_account_number = fund_distribution.full_account_number
        old_value, quantity, _distribution = self.get_total_amount_until( premium_schedule, 
                                                                          document_date, 
                                                                          book_date, 
                                                                          fulfillment_type = None, 
                                                                          account = FinancialBookingAccount( 'fund', fund_distribution.fund ) )

        book_date = self.entered_book_date(document_date, book_date)
        new_value = quantity * quotation_value
        
        LOGGER.debug( 'quotation of %s with nav %s units %s at : %s'%( quantity, quotation_value, fund_distribution.fund.name, document_date ) )
        LOGGER.debug( 'old value : %s'%old_value )
        LOGGER.debug( 'new value : %s'%new_value )
        
        value_difference = (new_value + D(str(old_value))).quantize(D('.01'), rounding=decimal.ROUND_DOWN )
        
        if abs(value_difference) < self.delta:
            return
        
        product = premium_schedule.product
        book = product.quotation_book
        
        lines = []
        lines.append( self.create_line( FinancialBookingAccount( 'fund', fund_distribution.fund ), 
                                        value_difference * -1, 
                                        'NAV {0}'.format( quotation_value ), 
                                        fulfillment_type = 'security_quotation' ) )
        lines.append( self.create_line( ProductBookingAccount('quotation_cost'), 
                                        value_difference, 
                                        full_account_number, 
                                        fulfillment_type = 'security_quotation' ) )
        lines.append( self.create_line( SecurityBookingAccount( security = fund_distribution.fund ), 
                                        value_difference, 
                                        full_account_number, 
                                        fulfillment_type = 'security_quotation' ) )
        lines.append( self.create_line( ProductBookingAccount('quotation_revenue', suffix=fund_distribution.fund.account_suffix), 
                                        value_difference * -1, 
                                        full_account_number, 
                                        fulfillment_type = 'security_quotation' ) )
        
        for sales in self.create_sales( premium_schedule, book_date, document_date, 0, lines, book, 'security_quotation' ):
            yield sales
