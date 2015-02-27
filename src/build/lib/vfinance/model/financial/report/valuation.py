from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from ...bank.report.abstract import AbstractReport
from ..premium import FinancialAccountPremiumScheduleHistory

import logging

LOGGER = logging.getLogger('vfinance.model.financial.report.valuation')

class ValuationReport( AbstractReport ):
    
    name = _('Valuation')
            
    def fill_sheet( self, sheet, offset, options ):
       
        from sqlalchemy import sql
        from sqlalchemy.orm import aliased
        
        from vfinance.model.bank.entry import Entry
        from vfinance.model.financial.product import FinancialProduct 
        from vfinance.model.financial.account import FinancialAccount, FinancialAccountBroker
        from vfinance.model.financial.visitor.abstract import FinancialBookingAccount
        
        from integration.spreadsheet.base import Cell, Range
        
        FAPSH = aliased( FinancialAccountPremiumScheduleHistory )
        a = aliased( FinancialAccount )
        p = aliased( FinancialProduct )
        session = Entry.query.session
        
        from vfinance.model.financial.visitor.provision import ProvisionVisitor
        provision = ProvisionVisitor( valid_at=options.report_date )
        
        sheet.render( Cell( 'A', offset, 'Account Number' ) )
        sheet.render( Cell( 'B', offset, 'Subscriber' ) )
        sheet.render( Cell( 'C', offset, 'Product' ) )
        sheet.render( Cell( 'D', offset, 'Period Type' ) )
        sheet.render( Cell( 'E', offset, 'Booked Value' ) )
        sheet.render( Cell( 'F', offset, 'Valid From Date' ) )
        sheet.render( Cell( 'G', offset, 'Thru Interest Rate' ) )
        sheet.render( Cell( 'H', offset, 'Premiums' ) )
        sheet.render( Cell( 'I', offset, 'Earned Interest' ) )
        sheet.render( Cell( 'J', offset, 'Deducted Risk' ) )
        sheet.render( Cell( 'K', offset, 'Master broker' ) )
        sheet.render( Cell( 'L', offset, 'Broker' ) )
        sheet.render( Cell( 'M', offset, 'Supervisory authority Nr' ) )
        sheet.render( Cell( 'N', offset, 'Attributed Profit' ) )
        sheet.render( Cell( 'O', offset, 'Account status'))
        sheet.render( Cell( 'P', offset, 'Schedule From Date' ) )
        sheet.render( Cell( 'Q', offset, 'Schedule Version' ) )
        
        offset += 1
        
        query = session.query( FAPSH, a, p ).filter( sql.and_(
            FAPSH.from_date <= options.report_date,
            FAPSH.thru_date >= options.report_date,
            FAPSH.product_id == p.id,
            a.id==FAPSH.financial_account_id,
            )).order_by( FAPSH.product_id, FAPSH.history_of_id )

        if options.product:
            query = query.filter( p.id==options.product )
        
        i = 0
        count = query.count()
        for i, (ps, account, product) in enumerate( query.yield_per(100) ):
            
            full_account_number = ps.full_account_number
            
            if i%20 == 0:
                yield UpdateProgress( i, count, text = full_account_number)
                
            broker = FinancialAccountBroker.query.filter( sql.and_( FinancialAccountBroker.financial_account_id==account.id,
                                                                    FinancialAccountBroker.from_date <= options.thru_document_date,
                                                                    FinancialAccountBroker.thru_date >= options.thru_document_date ) ).first()
                
            sheet.render( Cell( 'A', offset + i, full_account_number ) )
            sheet.render( Cell( 'B', offset + i, ps.get_role_name_at(options.thru_document_date, 'subscriber', 1) ) )
            sheet.render( Cell( 'C', offset + i, product.name ) )
            sheet.render( Cell( 'D', offset + i, ps.period_type ) )
            accounts = set([FinancialBookingAccount()])
            for fund_distribution in ps.fund_distribution:
                accounts.add( FinancialBookingAccount( 'fund', fund_distribution.fund ) )
            total = sum( ( provision.get_total_amount_until( ps, 
                                                             thru_document_date = options.thru_document_date,
                                                             thru_book_date = options.thru_book_date,
                                                             account = account )[0] for account in accounts), 0 )
            sheet.render( Cell( 'E', offset + i, total * -1 ) )
            sheet.render( Cell( 'F', offset + i, ps.valid_from_date ) )
            thru_interest_rate = ps.get_applied_feature_at(options.thru_document_date, ps.valid_from_date, ps.premium_amount, 'interest_rate', default=0).value
            thru_additional_interest_rate = ps.get_applied_feature_at(options.thru_document_date, ps.valid_from_date, ps.premium_amount, 'additional_interest_rate', default=0).value
            sheet.render( Cell( 'G', offset + i, thru_interest_rate + thru_additional_interest_rate ) )
            total_premiums = provision.get_total_amount_until( ps, 
                                                               options.thru_document_date, 
                                                               options.thru_book_date, 
                                                               'depot_movement',
                                                               account = FinancialBookingAccount() )[0] * -1
            total_profit = provision.get_total_amount_until( ps, 
                                                             options.thru_document_date, 
                                                             options.thru_book_date, 
                                                             'profit_attribution',
                                                             account = FinancialBookingAccount())[0] * -1
            interest = provision.get_total_amount_until( ps, 
                                                         options.thru_document_date, 
                                                         options.thru_book_date, 
                                                         'interest_attribution',
                                                         account = FinancialBookingAccount())[0] * -1
            additional_interest = provision.get_total_amount_until( ps, 
                                                                    options.thru_document_date, 
                                                                    options.thru_book_date, 
                                                                    'additional_interest_attribution',
                                                                    account = FinancialBookingAccount())[0] * -1
            total_risk = provision.get_total_amount_until( ps, 
                                                           options.thru_document_date, 
                                                           options.thru_book_date, 
                                                           'risk_deduction',
                                                           account = FinancialBookingAccount())[0] * -1
            sheet.render( Cell( 'H', offset + i, total_premiums ) )
            sheet.render( Cell( 'I', offset + i, interest + additional_interest ) )
            sheet.render( Cell( 'J', offset + i, total_risk ) )
            if broker and broker.broker_relation:
                sheet.render( Cell( 'K', offset + i, broker.broker_relation.from_rechtspersoon.name ) )
                sheet.render( Cell( 'L', offset + i, broker.broker_relation.name ) )
                sheet.render( Cell( 'M', offset + i, broker.broker_relation.supervisory_authority_number ) )
            sheet.render( Cell( 'N', offset + i, total_profit ) )
            sheet.render(Cell('O', offset + i, account.current_status))
            sheet.render(Cell('P', offset + i, ps.from_date))
            sheet.render(Cell('Q', offset + i, ps.version_id))
            
        sheet.set_column_width( Range( Cell('A',1), Cell('G',offset + i)), 20 )
