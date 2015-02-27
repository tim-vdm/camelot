import logging
import datetime
import calendar

LOGGER = logging.getLogger('vfinance.model.financial.visitors.abstract')

begin_of_times = datetime.date(2000,1,1)

from integration.tinyerp.convenience import months_between_dates,  add_months_to_date
from sqlalchemy import sql

from vfinance.model.bank.entry import Entry as E, EntryFulfillmentTables
from vfinance.model.bank.visitor import (VisitorMixin,
                                         ProductBookingAccount,
                                         CustomerBookingAccount,
                                         SupplierBookingAccount)
from vfinance.model.bank.visitor import BookingAccount

from ..premium import FinancialAccountPremiumFulfillment as FAPF
from ..fund import FinancialAccountFundDistribution
    
bindparam = sql.bindparam

class SecurityBookingAccount( BookingAccount ):
    """An account configured on a security on which can be booked"""
    
    def __init__( self, account_type = 'security', security = None ):
        assert account_type in ( 'security', 'transfer_revenue' )
        assert security != None
        self.account_type = account_type
        self.security = security
        
    def booking_account_number( self ):
        if self.account_type == 'security':
            return self.security.full_account_number
        else:
            return self.security.get_account( 'transfer_revenue' )
        
    def booking_account_number_at( self, schedule, book_date ):
        return self.booking_account_number()
        
    def __hash__( self ):
        return hash( self.booking_account_number() )
    
    def __unicode__( self ):
        return self.account_type        
        
class FinancialBookingAccount( BookingAccount ):
    """A financial account on which can be booked"""
    
    def __init__( self, account_type = 'uninvested', fund = None ):
        assert account_type in ( 'financed_commissions', 'uninvested', 'fund' )
        assert fund==None or account_type=='fund'
        self.account_type = account_type
        self.fund = fund
        
    def booking_account_number_at( self, premium_schedule, book_date ):
        if self.account_type == 'uninvested':
            return premium_schedule.full_account_number
        elif self.account_type == 'financed_commissions':
            return premium_schedule.financed_commissions_account_number
        elif self.account_type == 'fund':
            return FinancialAccountFundDistribution.full_account_number_for_fund( premium_schedule, self.fund )
        
    def __hash__( self ):
        if self.fund is None:
            return hash( (self.account_type, None) )
        else:
            return hash( (self.account_type, self.fund.id) )
    
    def __unicode__( self ):
        return self.account_type
    
class AbstractVisitor( VisitorMixin ):
            
    def __init__( self,
                  tables = None,
                  valid_at = sql.func.current_date(),
                  session = None ):
        if tables is None:
            tables = EntryFulfillmentTables(E.__table__, FAPF.__table__)
        super( AbstractVisitor, self ).__init__( entry_table = tables.entry_table,
                                                 fapf_table = tables.fulfillment_table,
                                                 valid_at = valid_at,
                                                 session = session )
        self._agreement_fulfillment_date_cache = dict()
        self._premium_schedule_end_of_cooling_off_cache = dict()

    def get_agreement_fulfillment_date(self, agreement):
        key = agreement.id
        try:
            fulfillment_date = self._agreement_fulfillment_date_cache[key]
        except KeyError:
            fulfillment_date = agreement.fulfillment_date
            self._agreement_fulfillment_date_cache[key] = fulfillment_date
        return fulfillment_date

    def get_premium_schedule_end_of_cooling_off(self, premium_schedule):
        key = premium_schedule.id
        try:
            end_of_cooling_off = self._premium_schedule_end_of_cooling_off_cache[key]
        except KeyError:
            end_of_cooling_off = premium_schedule.end_of_cooling_off
            self._premium_schedule_end_of_cooling_off_cache[key] = end_of_cooling_off
        return end_of_cooling_off

    def visit_premium_schedule(self, premium_schedule,  book_date):
        """Visit a single premium schedule, and apply changes
        when applicable.  This method is to be used only for testing purposes,
        as it will let a single visitor do its work, without involving other
        visitors.  Using this method will therefor create an inconsistent
        account.
        
        :return: an iterator over the executed steps
        """
        from_doc_date = self.accounting_period.from_doc_date
        last_visited_document_date = from_doc_date
        for document_date in self.get_document_dates( premium_schedule, from_doc_date, book_date):
            for step in self.visit_premium_schedule_at(premium_schedule, document_date, book_date, last_visited_document_date ):
                yield step
            last_visited_document_date = document_date

    def get_customer_at(self, premium_schedule, doc_date):
        return premium_schedule.financial_account.subscription_customer_at(doc_date)

    def create_supplier_request(self, premium_schedule, broker_relation, supplier_type):
        package = premium_schedule.financial_account.package
        from_number, thru_number = package.from_supplier, package.thru_supplier
        return self._get_supplier_from_broker(broker_relation, supplier_type, from_number, thru_number)

    def get_document_dates(self, _premium_schedule, from_date, thru_date):
        """by default, return all the last days of the months between from_date and thru_date,
        including from_date and thru_date, should those be the last day of the month""" 
        for i in range(months_between_dates(from_date,
                                             thru_date) + 1):
            document_date = add_months_to_date( from_date, i)
            document_date = datetime.date(year = document_date.year, 
                                          month = document_date.month, 
                                          day = calendar.monthrange(document_date.year, 
                                                                    document_date.month)[1])
            if document_date <= thru_date:
               yield document_date
       
    def _apply_condition( self, schedule, query, condition, condition_number ):
        (field_name, field_operator, value) = condition
        if (field_name == 'account') and isinstance( value, FinancialBookingAccount ):
            rhs = bindparam( str(condition_number) )
            query = query.where( field_operator( self.entry_table.c.account, rhs ) )
        elif (field_name == 'account') and isinstance( value, SecurityBookingAccount ):
            query = query.where( field_operator( self.entry_table.c.account, value.booking_account_number() ) )
        else:
            query = super( AbstractVisitor, self )._apply_condition( schedule, query, condition, condition_number ) 
        return query
    
    def _param_value( self, schedule, condition ):
        if isinstance( condition[2], FinancialBookingAccount ):
            yield condition[2].booking_account_number_at( schedule, None )
        else:
            for value in super( AbstractVisitor, self )._param_value( schedule, condition ):
                yield value
                
    def get_booking_account(self, premium_schedule, account_number, book_date):
        booking_account = super(AbstractVisitor, self).get_booking_account(premium_schedule, account_number, book_date)
        if booking_account is None:

            premium_schedule_fund_accounts = dict( (fd.full_account_number,fd.fund) for fd in premium_schedule.fund_distribution )
            security_fund_accounts = dict( (''.join(fd.fund.full_account_number),fd.fund) for fd in premium_schedule.fund_distribution if fd.fund.full_account_number)
            transfer_revenue_fund_accounts = dict( (''.join(fd.fund.transfer_revenue_account),fd.fund) for fd in premium_schedule.fund_distribution if fd.fund.transfer_revenue_account)
            quotation_revenue_accounts = dict()
            for product_account in premium_schedule.product.get_accounts( 'quotation_revenue' ):
                for fd in premium_schedule.fund_distribution:
                    quotation_revenue_accounts[''.join(product_account.number) + fd.fund.account_suffix] = fd.fund

            if account_number.startswith(self._settings.get('HYPO_ACCOUNT_KLANT')[:-9]):
                booking_account = CustomerBookingAccount()
            elif account_number.startswith(self._settings.get('BANK_ACCOUNT_SUPPLIER')[:-9]):
                booking_account = SupplierBookingAccount(None)
            elif account_number == premium_schedule.full_account_number:
                booking_account = FinancialBookingAccount('uninvested')
            elif account_number == premium_schedule.financed_commissions_account_number:
                booking_account = FinancialBookingAccount('financed_commissions')
            elif account_number in premium_schedule_fund_accounts:
                booking_account = FinancialBookingAccount('fund', fund = premium_schedule_fund_accounts[account_number])
            elif account_number in security_fund_accounts:
                booking_account = SecurityBookingAccount('security', security = security_fund_accounts[account_number] )
            elif account_number in transfer_revenue_fund_accounts:
                booking_account = SecurityBookingAccount('transfer_revenue', transfer_revenue_fund_accounts[account_number] )  
            elif account_number in quotation_revenue_accounts:
                booking_account = ProductBookingAccount( 'quotation_revenue', suffix = quotation_revenue_accounts[account_number].account_suffix )
            else:
                account_type = premium_schedule.product.get_account_type_at(account_number,
                                                                             book_date)
                booking_account = ProductBookingAccount( account_type )
        return booking_account
