import itertools

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from sqlalchemy import sql

from ...bank.report.abstract import AbstractReport

class PendingAgreementsReport( AbstractReport ):
    
    name = _('Pending Agreements')
            
    def fill_sheet( self, sheet, offset, options ):

        from integration.spreadsheet.base import Cell
        from vfinance.model.financial.agreement import FinancialAgreement
        from vfinance.model.financial.product import FinancialProduct
        from vfinance.model.financial.premium import FinancialAccountPremiumSchedule, FinancialAgreementPremiumSchedule
        from vfinance.model.bank.entry import Entry
        
        sheet.render( Cell( 'A', offset, 'Unverified Agreements' ) )
        offset += 2
        
        yield UpdateProgress( text = 'Unverified agreements' )
        
        for pending_state in ['draft', 
                               'complete', 
                               'incomplete',]:
            
            for agreement in FinancialAgreement.query.filter( FinancialAgreement.current_status == pending_state ):
                for premium_schedule in agreement.invested_amounts:
                    sheet.render( Cell( 'A', offset, pending_state ) )
                    sheet.render( Cell( 'B', offset, agreement.agreement_date ) )
                    sheet.render( Cell( 'C', offset, agreement.code))
                    sheet.render( Cell( 'D', offset, agreement.subscriber_1 or '') )
                    sheet.render( Cell( 'E', offset, agreement.subscriber_2 or '') )
                    sheet.render( Cell( 'F', offset, premium_schedule.period_type ) )
                    sheet.render( Cell( 'G', offset, premium_schedule.amount ) )
                    sheet.render( Cell( 'H', offset, premium_schedule.direct_debit ) )
                    offset += 1
                    
        offset += 2
        sheet.render( Cell( 'A', offset, 'Unmatched Payments' ) )
        offset += 2
            
        yield UpdateProgress( text = 'Unmatched Payments' )
    
        products = FinancialProduct.query.all()
        pending_premium_accounts = list( set( itertools.chain.from_iterable( (''.join(a.number) for a in product.get_accounts( 'pending_premiums' ) if a.number)
                                                                             for product in products ) ) )
        
        for entry in Entry.query.filter( sql.and_( Entry.account.in_( pending_premium_accounts ),
                                                   Entry.open_amount != 0) ):
                sheet.render( Cell( 'A', offset, entry.account ) )
                sheet.render( Cell( 'B', offset, entry.book ) )
                sheet.render( Cell( 'C', offset, entry.document ) )
                sheet.render( Cell( 'D', offset, entry.line_number ) )
                sheet.render( Cell( 'E', offset, entry.open_amount ) )
                sheet.render( Cell( 'F', offset, entry.remark ) )
                offset += 1

        offset += 2
        
        yield UpdateProgress( text = 'Unmatched Premium Schedules'  )
        
        sheet.render( Cell( 'A', offset, 'Unmatched Premium Schedules' ) )
        offset += 2
        
        for premium_schedule in FinancialAccountPremiumSchedule.query.filter( FinancialAccountPremiumSchedule.premiums_attributed_to_customer < 1 ):
            account = premium_schedule.financial_account
            agreement = premium_schedule.agreed_schedule.financial_agreement
            sheet.render( Cell( 'A', offset, premium_schedule.full_account_number ) )
            sheet.render( Cell( 'B', offset, agreement.agreement_date ) )
            sheet.render(Cell('C', offset, agreement.code))
            sheet.render( Cell( 'D', offset, account.subscriber_1 or '') )
            sheet.render( Cell( 'E', offset, account.subscriber_2 or '') )
            sheet.render( Cell( 'F', offset, premium_schedule.period_type ) )
            sheet.render( Cell( 'G', offset, premium_schedule.premium_amount ) )
            sheet.render( Cell( 'H', offset, premium_schedule.direct_debit ) )
            offset += 1
            
        yield UpdateProgress( text = 'Unmatched Agreements'  )
        
        offset += 2
        sheet.render( Cell( 'A', offset, 'Unmatched Agreements' ) )
        offset += 2
        
        for agreed_schedule in FinancialAgreementPremiumSchedule.query.filter( sql.and_( FinancialAgreementPremiumSchedule.fulfilled < 1,
                                                                                         FinancialAgreementPremiumSchedule.current_status_sql == 'verified' ) ):
            agreement = agreed_schedule.financial_agreement
            sheet.render( Cell( 'A', offset, '' ) )
            sheet.render( Cell( 'B', offset, agreement.agreement_date ) )
            sheet.render(Cell('C', offset, agreement.code))
            sheet.render( Cell( 'D', offset, agreement.subscriber_1 or '') )
            sheet.render( Cell( 'E', offset, agreement.subscriber_2 or '') )
            sheet.render( Cell( 'F', offset, agreed_schedule.period_type ) )
            sheet.render( Cell( 'G', offset, agreed_schedule.amount ) )
            sheet.render( Cell( 'H', offset, agreed_schedule.direct_debit ) )
            offset += 1
