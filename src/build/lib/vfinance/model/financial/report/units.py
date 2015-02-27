from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from ...bank.report.abstract import AbstractReport
from ..premium import FinancialAccountPremiumScheduleHistory

import logging

LOGGER = logging.getLogger('vfinance.model.financial.report.units')

class UnitReport( AbstractReport ):
    
    name = _('Units')
            
    def fill_sheet( self, sheet, offset, options ):

        from sqlalchemy import sql
        from sqlalchemy.orm import aliased

        from integration.spreadsheet.base import Cell
        from vfinance.model.financial.account import FinancialAccount, FinancialAccountBroker
        from vfinance.model.financial.visitor.abstract import AbstractVisitor, FinancialBookingAccount
        from vfinance.model.financial.product import FinancialProduct
        from vfinance.model.financial.security import FinancialFund
        from vfinance.model.financial.fund import FinancialAccountFundDistribution

        sheet.render( Cell( 'A', offset, 'Units' ) )
        offset += 2
    
        visitor = AbstractVisitor( valid_at=options.report_date )
        session = FinancialFund.query.session

        sheet.render( Cell( 'A', offset, 'Fund' ) )
        sheet.render( Cell( 'B', offset, 'Fund Account Number' ) )
        sheet.render( Cell( 'C', offset, 'Account'  ) )
        sheet.render( Cell( 'D', offset, 'Product'  ) )
        sheet.render( Cell( 'E', offset, 'Suffix'  ) )
        sheet.render( Cell( 'F', offset, 'Subscriber 1'  ) )
        sheet.render( Cell( 'G', offset, 'Subscriber 2'  ) )
        sheet.render( Cell( 'H', offset, 'Agreement'  ) )
        sheet.render( Cell( 'I', offset, 'Units'  ) )
        sheet.render( Cell( 'J', offset, 'Value'  ) )
        sheet.render( Cell( 'K', offset, 'Master broker' ) )
        sheet.render( Cell( 'L', offset, 'Broker' ) )
        sheet.render(Cell('M', offset, 'Account status'))
        offset += 2

        ff = aliased( FinancialFund )
        fd = aliased( FinancialAccountFundDistribution )
        FAPSH = aliased( FinancialAccountPremiumScheduleHistory )
        fa = aliased( FinancialAccount )
        fp = aliased( FinancialProduct )

        query = session.query( ff,
                               fd,
                               FAPSH,
                               fp,
                               fa,
                               ).filter( sql.and_(
                                   FAPSH.from_date <= options.report_date,
                                   FAPSH.thru_date >= options.report_date,
                                   fd.distribution_of_id == FAPSH.id,
                                   fd.fund_id == ff.id,
                                   FAPSH.financial_account_id == fa.id,
                                   FAPSH.product_id == fp.id
                               ) )
        
        if options.product:
            query = query.filter( fp.id==options.product )
            
        query = query.order_by( fa.id, FAPSH.history_of_id, fd.id )
        
        number_of_lines = query.count()
        yield UpdateProgress( 0, number_of_lines)

        # lines without a valid time interval can still contain units, and multiple lines
        # can span the same time interval, so we need to filter on fund account number instead
        # of valid time
        fund_keys = set()
        for i, (fund, distribution, premium_schedule, product, account) in enumerate(query.yield_per(100)):
            fund_account_number = distribution.full_account_number
            fund_key = (premium_schedule.id, fund_account_number)
            if fund_key in fund_keys:
                continue
            fund_keys.add( fund_key )
            if i%20 == 0:
                yield UpdateProgress( i, number_of_lines, text = fund_account_number)
                
            broker = FinancialAccountBroker.query.filter( sql.and_( FinancialAccountBroker.financial_account_id==premium_schedule.financial_account_id,
                                                                    FinancialAccountBroker.from_date <= options.thru_document_date,
                                                                    FinancialAccountBroker.thru_date >= options.thru_document_date ) ).first()
            
            sheet.render( Cell( 'A', offset, fund.name ) )
            sheet.render( Cell( 'B', offset, fund_account_number ) )
            sheet.render( Cell( 'C', offset, premium_schedule.full_account_number ) )
            sheet.render( Cell( 'D', offset, product.name ) )
            sheet.render( Cell( 'E', offset, premium_schedule.account_suffix ) )
            sheet.render( Cell( 'F', offset, premium_schedule.get_role_name_at(options.thru_document_date, 'subscriber', 1) ) )
            sheet.render( Cell( 'G', offset, premium_schedule.get_role_name_at(options.thru_document_date, 'subscriber', 2) ) )
            sheet.render(Cell('H', offset, premium_schedule.agreement_code))

            amount, units, _distribution = visitor.get_total_amount_until( premium_schedule, 
                                                                           options.thru_document_date, 
                                                                           options.thru_book_date, 
                                                                           account = FinancialBookingAccount('fund', fund = fund ) )
            sheet.render( Cell( 'I', offset, units ) )
            sheet.render( Cell( 'J', offset, amount * -1) )
            if broker and broker.broker_relation:
                sheet.render( Cell( 'K', offset, broker.broker_relation.from_rechtspersoon.name ) )
                sheet.render( Cell( 'L', offset, broker.broker_relation.name ) )
            sheet.render(Cell('M', offset, account.current_status))
            
            offset += 1
