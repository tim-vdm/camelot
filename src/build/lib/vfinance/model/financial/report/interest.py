from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from ...bank.report.abstract import AbstractReport
from ..premium import FinancialAccountPremiumScheduleHistory

class InterestAttributionReport( AbstractReport ):
    
    name = _('Interest Attribution')
            
    def fill_sheet( self, sheet, offset, options ):
        from sqlalchemy import sql, orm
        from integration.spreadsheet.base import Cell

        from vfinance.model.financial.account import FinancialAccount
        from vfinance.model.financial.visitor.interest_attribution import InterestAttributionVisitor
        from vfinance.model.financial.visitor.abstract import FinancialBookingAccount
        
        from vfinance.model.financial.visitor.risk_deduction import RiskDeductionVisitor
        risk_deduction = RiskDeductionVisitor( valid_at=options.report_date )

        interest_attribution = InterestAttributionVisitor( valid_at=options.report_date )
        sheet.render( Cell( 'A', offset, 'Interest Attribution' ) )
        offset += 2
        
        session = FinancialAccount.query.session
        
        sheet.render( Cell( 'A', offset, 'Account' ) )
        sheet.render( Cell( 'B', offset, 'Received premiums up to %s' % options.from_document_date ) )
        sheet.render( Cell( 'C', offset, 'Received premiums up to %s' % options.thru_document_date ) )
        sheet.render( Cell( 'D', offset, 'Interest attributed up to %s' % options.from_document_date ) )
        sheet.render( Cell( 'E', offset, 'Interest attributed up to %s' % options.thru_document_date ) )
        sheet.render( Cell( 'F', offset, 'Interest rate at %s' % options.from_document_date) )
        sheet.render( Cell( 'G', offset, 'Additional Interest rate at %s' % options.from_document_date) )
        sheet.render(Cell('H', offset, 'Account status'))
        offset += 1
        
        FAPSH = orm.aliased( FinancialAccountPremiumScheduleHistory )
        fa   = orm.aliased( FinancialAccount )
        
        query = session.query( FAPSH,
                               fa  ).filter( sql.and_(
                                   FAPSH.financial_account_id == fa.id,
                                   FAPSH.from_date <= options.report_date,
                                   FAPSH.thru_date >= options.report_date,
                               ) )
                
        if options.product:
            query = query.filter( FAPSH.product_id==options.product )
            
        query = query.order_by( fa.id, FAPSH.history_of_id )
                
        for i, (faps, fa) in enumerate( query.yield_per(100) ):
            
            if i%10 == 0:
                yield UpdateProgress( text = faps.full_account_number )
                
            interest_at_from_date = ( risk_deduction.get_total_amount_until(faps, 
                                                                            options.from_document_date, 
                                                                            fulfillment_type = 'interest_attribution', 
                                                                            account = FinancialBookingAccount())[0] + \
                                      risk_deduction.get_total_amount_until(faps, 
                                                                            options.from_document_date, 
                                                                            fulfillment_type = 'additional_interest_attribution', 
                                                                            account = FinancialBookingAccount())[0] ) * -1
            interest_at_thru_date = ( risk_deduction.get_total_amount_until(faps, 
                                                                            options.thru_document_date, 
                                                                            fulfillment_type = 'interest_attribution', 
                                                                            account = FinancialBookingAccount())[0] + \
                                      risk_deduction.get_total_amount_until(faps, 
                                                                            options.thru_document_date, 
                                                                            fulfillment_type = 'additional_interest_attribution', 
                                                                            account = FinancialBookingAccount())[0] ) * -1 
            
            premiums_at_from_date = interest_attribution.get_total_amount_until(faps, 
                                                                                options.from_document_date, 
                                                                                fulfillment_type = 'depot_movement')[0] * -1
            premiums_at_thru_date = interest_attribution.get_total_amount_until(faps, 
                                                                                options.thru_document_date, 
                                                                                fulfillment_type = 'depot_movement')[0] * -1
            
            interest_rate_at_from_date = faps.get_applied_feature_at(options.from_document_date, faps.valid_from_date, faps.premium_amount, 'interest_rate', default=0).value
            additional_interest_rate_at_from_date = faps.get_applied_feature_at(options.from_document_date, faps.valid_from_date, faps.premium_amount, 'additional_interest_rate', default=0).value

            sheet.render( Cell( 'A', offset + i, faps.full_account_number ) )
            sheet.render( Cell( 'B', offset + i, premiums_at_from_date ) )
            sheet.render( Cell( 'C', offset + i, premiums_at_thru_date ) )
            sheet.render( Cell( 'D', offset + i, interest_at_from_date ) )
            sheet.render( Cell( 'E', offset + i, interest_at_thru_date ) )
            sheet.render( Cell( 'F', offset + i, interest_rate_at_from_date ) )
            sheet.render( Cell( 'G', offset + i, additional_interest_rate_at_from_date ) )
            sheet.render(Cell('H', offset + i, fa.current_status))
            
