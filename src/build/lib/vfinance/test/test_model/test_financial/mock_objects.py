"""
Objects and classes to be used in unit tests, to test parts of
the application.
"""

import datetime

import mock

from vfinance.model.bank.product import ProductMixin
from vfinance.model.financial.agreement import FinancialAgreementAccountMixin
from vfinance.model.financial.premium import FinancialAccountPremiumScheduleMixin
from vfinance.model.financial.security import FinancialSecurityMixin
from vfinance.model.financial.transaction import ( AbstractFinancialTransaction,
                                                   AbstractFinancialTransactionPremiumSchedule,
                                                   AbstractFinancialTransactionCreditDistribution)

class AgreementMock( mock.Mock, FinancialAgreementAccountMixin ):
    pass
    
class EntryMock( mock.Mock ):
    
    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'account', '456' )
        kwargs.setdefault( 'number_of_fulfillments', 0 )
        kwargs.setdefault( 'doc_date', datetime.date( 2010, 1, 1 ) )
        kwargs.setdefault( 'book_date', datetime.date( 2010, 1, 1 ) )
        super( EntryMock, self ).__init__( *args, **kwargs )

class ProductAccountMock( mock.Mock ):
    
    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'from_date', datetime.date( 2000, 1, 1 ) )
        kwargs.setdefault( 'thru_date', datetime.date( 2400, 12, 31 ) )
        super( ProductAccountMock, self ).__init__( *args, **kwargs )
        
class ProductMock( mock.Mock, ProductMixin ):
    
    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'specialization_of', None )
        kwargs.setdefault( 'financed_commissions_prefix', ['22352'] )
        kwargs.setdefault( 'account_number_digits', 6 )
        kwargs.setdefault( 'available_with', [] )
        kwargs.setdefault( 'available_accounts', [ ProductAccountMock( described_by = 'pending_premiums', number = '456'  ),
                                                   ProductAccountMock( described_by = 'premium_rate_1_revenue', number = '720111201', thru_date = datetime.date( 2010,12,31 ) ),
                                                   ProductAccountMock( described_by = 'premium_rate_1_revenue', number = '730111201', from_date = datetime.date( 2011,1,1 ) ),
                                                   ProductAccountMock( described_by = 'financed_commissions_interest', number = '740801', from_date = datetime.date( 2011,1,1 ) ),
                                                   ProductAccountMock( described_by = 'premium_rate_2_revenue', number = '7408', from_date = datetime.date( 2000,1,1 ) ),
                                                   ] )
        super( ProductMock, self ).__init__( *args, **kwargs )

product_1 = ProductMock( id = 1 ) #get_account = mock.Mock( return_value = '456' ),
                       
product_2 = ProductMock( id = 2 ) #get_account = mock.Mock( return_value = '456' ),
                       

class PremiumScheduleMock( mock.Mock, FinancialAccountPremiumScheduleMixin ):
    
    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'product', product_1 )
        kwargs.setdefault( 'version_id', 1 )
        kwargs.setdefault( 'valid_from_date', datetime.date( 2010, 1, 1 ) )
        kwargs.setdefault( 'valid_thru_date', datetime.date( 2100, 1, 1 ) )
        kwargs.setdefault( 'payment_thru_date', datetime.date( 2100, 1, 1 ) )
        kwargs.setdefault( 'period_type', 'single' )
        kwargs.setdefault( 'account_suffix', 1 )
        #kwargs.setdefault( 'get_applied_feature_at', mock.Mock( return_value = mock.Mock( value = 1 ) ) )
        kwargs.setdefault( 'premiums_attributed_to_customer', 0 )
        kwargs.setdefault( 'fund_distribution', [] )
        kwargs.setdefault( 'applied_coverages', [] )
        kwargs.setdefault( 'applied_features', [] )
        kwargs.setdefault( 'invoice_items', [] )
        super( PremiumScheduleMock, self ).__init__( *args, **kwargs )
        
    @property
    def full_account_number( self ):
        return str( 1400000000 + self.id )
        
premium_schedule_1 = PremiumScheduleMock( id = 1 )
premium_schedule_2 = PremiumScheduleMock( id = 2, product = product_2 ) # different product
premium_schedule_3 = PremiumScheduleMock( id = 3 )                      # same product, different account

class FundMock( mock.Mock, FinancialSecurityMixin ):
    
    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'transfer_revenue_account', ['7778'] )
        kwargs.setdefault( 'account_infix', None )
        kwargs.setdefault( 'account_prefix', None )
        kwargs.setdefault( 'account_number', kwargs.get('id', 0) )
        super( FundMock, self ).__init__( *args, **kwargs )
        
fund_1 = FundMock( id = 1 )
fund_2 = FundMock( id = 2, transfer_revenue_account = ['7779'] )
fund_3 = FundMock( id = 3 )        
    
class FundDistributionMock( mock.Mock ):

    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'from_date', datetime.date( 2010, 1, 1 ) )
        kwargs.setdefault( 'thru_date', datetime.date( 2100, 1, 1 ) )
        kwargs.setdefault( 'fund', fund_1 )
        kwargs.setdefault( 'target_percentage', 50 )
        super( FundDistributionMock, self ).__init__( *args, **kwargs ) 

class FinancialTransactionMock( mock.Mock, AbstractFinancialTransaction ):

    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'agreement_date', datetime.date( 2011, 1, 1 ) )
        kwargs.setdefault( 'from_date', datetime.date( 2011, 1, 1 ) )
        kwargs.setdefault( 'transaction_type', 'partial_redemption' )
        kwargs.setdefault( 'code', u'123/4567/89101')
        kwargs.setdefault( 'consisting_of', [] )
        kwargs.setdefault( 'distributed_via', [] )
        super( FinancialTransactionMock, self ).__init__( *args, **kwargs )
        
class FinancialTransactionPremiumScheduleMock( mock.Mock, AbstractFinancialTransactionPremiumSchedule ):
    
    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'described_by', 'amount' )
        kwargs.setdefault( 'quantity', -100 )
        kwargs.setdefault( 'fund_distribution', [] )
        kwargs.setdefault( 'applied_features', [] )
        super( FinancialTransactionPremiumScheduleMock, self ).__init__( *args, **kwargs )
        
class FinancialTransactionFundDistributionMock( mock.Mock ):
    
    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'distribution_of', None )
        kwargs.setdefault( 'fund', fund_1 )
        kwargs.setdefault( 'target_percentage', 100 )
        kwargs.setdefault( 'change_target_percentage', False )
        kwargs.setdefault( 'new_target_percentage', None )
        super( FinancialTransactionFundDistributionMock, self ).__init__( *args, **kwargs )
        
class FinancialTransactionCreditDistributionMock( mock.Mock, AbstractFinancialTransactionCreditDistribution ):
    
    def __init__( self, *args, **kwargs ):
        kwargs.setdefault( 'described_by', 'percentage' )      
        kwargs.setdefault( 'quantity', 100 )
        kwargs.setdefault( 'iban', None )
        super( FinancialTransactionCreditDistributionMock, self ).__init__( *args, **kwargs )

        
