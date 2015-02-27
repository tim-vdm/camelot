from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from ...bank.report.abstract import AbstractReport

import logging
import operator

from sqlalchemy import orm
from sqlalchemy.sql import operators

LOGGER = logging.getLogger('vfinance.model.financial.report.valuation')

def distinct_from( a, b ):
    """Operator that checks if a and b are different or one of them is null 
    
    see : http://www.postgresql.org/docs/8.2/static/functions-comparison.html    
    """
    return operators.op( a, 'is distinct from', b )

class DetailedValuationReport( AbstractReport ):
    
    name = _('Premium Valuation')
            
    def fill_sheet( self, sheet, offset, options ):
       
        from sqlalchemy import sql
        from sqlalchemy.orm import aliased
        
        from vfinance.model.bank.entry import Entry
        from vfinance.model.financial.premium import FinancialAccountPremiumScheduleHistory
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
        
        sheet.render( Cell( 'A',  offset, 'Full Account Number' ) )
        sheet.render( Cell( 'B',  offset, 'Subscriber' ) )
        sheet.render( Cell( 'C',  offset, 'Product' ) )
        sheet.render( Cell( 'D',  offset, 'Period Type' ) )
        sheet.render( Cell( 'E',  offset, 'Booked Value' ) )
        sheet.render( Cell( 'F',  offset, 'Schedule Valid From Date' ) )
        sheet.render( Cell( 'G',  offset, 'Thru Total Interest Rate' ) )
        sheet.render( Cell( 'H',  offset, 'Premiums' ) )
        sheet.render( Cell( 'I',  offset, 'Total Earned Interest' ) )
        sheet.render( Cell( 'J',  offset, 'Deducted Risk' ) )
        sheet.render( Cell( 'K',  offset, 'Master broker' ) )
        sheet.render( Cell( 'L',  offset, 'Broker' ) )
        sheet.render( Cell( 'M',  offset, 'Supervisory authority Nr' ) )
        sheet.render( Cell( 'N',  offset, 'Document date' ) )
        sheet.render( Cell( 'O',  offset, 'Book date' ) )
        sheet.render( Cell( 'P',  offset, 'Book' ) )
        sheet.render( Cell( 'Q',  offset, 'Document' ) )
        sheet.render( Cell( 'R',  offset, 'Creation date' ) )
        sheet.render( Cell( 'S',  offset, 'From Total Interest Rate' ) )
        sheet.render( Cell( 'T',  offset, 'Schedule Valid Thru date' ) )
        sheet.render( Cell( 'U',  offset, 'Payment thru date' ) )
        sheet.render( Cell( 'V',  offset, 'Schedule amount' ) )
        sheet.render( Cell( 'W',  offset, 'Increase rate' ) )
        sheet.render( Cell( 'X',  offset, 'Direct debit' ) )
        sheet.render( Cell( 'Y',  offset, 'Product id' ) )
        sheet.render( Cell( 'Z',  offset, 'Agreed schedule id' ) )
        sheet.render( Cell( 'AA', offset, 'Financial Account id' ) )
        sheet.render( Cell( 'AB', offset, 'Account Number' ) )
        sheet.render( Cell( 'AC', offset, 'Schedule id' ) )
        sheet.render( Cell( 'AD', offset, 'Origin' ) )
        sheet.render( Cell( 'AE', offset, 'Account status' ) )
        sheet.render( Cell( 'AF', offset, 'From Interest Rate' ) )
        sheet.render( Cell( 'AG', offset, 'Thru Interest Rate' ) )
        sheet.render( Cell( 'AH', offset, 'Earned Interest' ) )
        sheet.render( Cell( 'AI', offset, 'Schedule From Date' ) )
        sheet.render( Cell( 'AJ', offset, 'Schedule Version' ) )
        
        offset += 1
        
        query = session.query(FAPSH, a, p).filter(sql.and_(FAPSH.product_id == p.id,
                                                          FAPSH.from_date <= options.report_date,
                                                          FAPSH.thru_date >= options.report_date,
                                                          a.id==FAPSH.financial_account_id)).order_by(FAPSH.product_id, FAPSH.history_of_id)
        
        query = query.options( orm.undefer(FAPSH.origin) )

        if options.product:
            query = query.filter( p.id==options.product )
        
        i = 0
        count = query.count()
        for i, (ps, account, product) in enumerate( query.yield_per(100) ):
            
            full_account_number = ps.full_account_number
            accounts = set([FinancialBookingAccount()])
            for fund_distribution in ps.fund_distribution:
                accounts.add( FinancialBookingAccount('fund', fund_distribution.fund) )
            
            if i%20 == 0:
                yield UpdateProgress( i, count, text = full_account_number)
                
            broker = FinancialAccountBroker.query.filter( sql.and_( FinancialAccountBroker.financial_account_id==account.id,
                                                                    FinancialAccountBroker.from_date <= options.thru_document_date,
                                                                    FinancialAccountBroker.thru_date >= options.thru_document_date ) ).first()
        
            depot_movment_entries = list( provision.get_entries( ps, 
                                                                 thru_document_date = options.thru_document_date,
                                                                 thru_book_date = options.thru_book_date,
                                                                 fulfillment_types = ['depot_movement',
                                                                                      'profit_attribution'],
                                                                 account = FinancialBookingAccount() ) )
            
            # per depot movement, the depot movement and its associated entries
            # are summed, so for the remaining line, we should exclude both of
            # them
            not_associated_conditions = sum( ( [ ('associated_to_id', distinct_from, entry.fulfillment_id),
                                                 ('id', operator.ne, entry.id), ]
                                               for entry in depot_movment_entries ), [] )
            
            # summarize one line per depot movement, and one line with all
            # the remaining entries
            for depot_movement_entry in depot_movment_entries + [None]:
                document_date = ps.valid_from_date
                entry_amount = 0
                conditions = not_associated_conditions
                if depot_movement_entry != None:
                    document_date = depot_movement_entry.doc_date
                    entry_amount = depot_movement_entry.amount
                    conditions = [('associated_to_id', operator.eq, depot_movement_entry.fulfillment_id )]
                                        
                from_interest_rate = ps.get_applied_feature_at(document_date, document_date, entry_amount, 'interest_rate', default=0).value
                from_additional_interest_rate = ps.get_applied_feature_at(document_date, document_date, entry_amount, 'additional_interest_rate', default=0).value
                thru_interest_rate = ps.get_applied_feature_at(options.thru_document_date, document_date, entry_amount, 'interest_rate', default=0).value
                thru_additional_interest_rate = ps.get_applied_feature_at(options.thru_document_date, document_date, entry_amount, 'additional_interest_rate', default=0).value
                
                interest = provision.get_total_amount_until( ps, 
                                                             options.thru_document_date, 
                                                             options.thru_book_date, 
                                                             'interest_attribution',
                                                             conditions = conditions,
                                                             account = FinancialBookingAccount(),)[0] * -1
                
                additional_interest = provision.get_total_amount_until( ps, 
                                                                        options.thru_document_date, 
                                                                        options.thru_book_date, 
                                                                        'additional_interest_attribution',
                                                                        conditions = conditions,
                                                                        account = FinancialBookingAccount(),)[0] * -1
                
                total_risk = provision.get_total_amount_until( ps, 
                                                               options.thru_document_date, 
                                                               options.thru_book_date, 
                                                               'risk_deduction',
                                                               conditions = conditions,
                                                               account = FinancialBookingAccount(),)[0] * -1
                
                total_associated = sum( provision.get_total_amount_until( ps, 
                                                                          options.thru_document_date, 
                                                                          options.thru_book_date, 
                                                                          conditions = conditions,
                                                                          account = account )[0] for account in accounts ) * -1
                
                # avoid lines with only zeros in the report
                if not (entry_amount or interest or additional_interest or total_risk or total_associated):
                    continue
                
                sheet.render( Cell( 'A', offset, full_account_number ) )
                sheet.render( Cell( 'B', offset, ps.get_role_name_at(options.thru_document_date, 'subscriber', 1) ) )
                sheet.render( Cell( 'C', offset, product.name ) )
                sheet.render( Cell( 'D', offset, ps.period_type ) )
                sheet.render( Cell( 'E', offset, total_associated - entry_amount ) )
                sheet.render( Cell( 'F', offset, ps.valid_from_date ) )
                sheet.render( Cell( 'G', offset, thru_interest_rate + thru_additional_interest_rate ) )
                sheet.render( Cell( 'H', offset, - entry_amount ) )
                sheet.render( Cell( 'I', offset, interest + additional_interest ) )
                sheet.render( Cell( 'J', offset, total_risk ) )
                if broker and broker.broker_relation:
                    sheet.render( Cell( 'K', offset, broker.broker_relation.from_rechtspersoon.name ) )
                    sheet.render( Cell( 'L', offset, broker.broker_relation.name ) )
                    sheet.render( Cell( 'M', offset, broker.broker_relation.supervisory_authority_number ) )
                if depot_movement_entry != None:
                    sheet.render( Cell( 'N', offset, depot_movement_entry.doc_date ) )
                    sheet.render( Cell( 'O', offset, depot_movement_entry.book_date ) )
                    sheet.render( Cell( 'P', offset, depot_movement_entry.book ) )
                    sheet.render( Cell( 'Q', offset, depot_movement_entry.document ) )
                    sheet.render( Cell( 'R', offset, depot_movement_entry.creation_date ) )
                sheet.render( Cell( 'S', offset, from_interest_rate + from_additional_interest_rate ) )  
                sheet.render( Cell( 'T',  offset, ps.valid_thru_date ) )
                sheet.render( Cell( 'U',  offset, ps.payment_thru_date ) )
                sheet.render( Cell( 'V',  offset, ps.premium_amount ) )
                sheet.render( Cell( 'W',  offset, ps.increase_rate ) )
                sheet.render( Cell( 'X',  offset, ps.direct_debit ) )
                sheet.render( Cell( 'Y',  offset, ps.product_id ) )
                sheet.render( Cell( 'Z',  offset, ps.agreed_schedule_id ) )
                sheet.render( Cell( 'AA', offset, ps.financial_account_id ) )
                sheet.render( Cell( 'AB', offset, ps.account_number ) )
                sheet.render( Cell( 'AC', offset, ps.history_of_id ) )
                sheet.render( Cell( 'AD', offset, ps.origin ) )
                sheet.render( Cell( 'AE', offset, account.current_status))
                sheet.render( Cell( 'AF', offset, from_interest_rate) )
                sheet.render( Cell( 'AG', offset, thru_interest_rate) )
                sheet.render( Cell( 'AH', offset, interest) )
                sheet.render( Cell( 'AI', offset, ps.from_date ) )
                sheet.render( Cell( 'AJ', offset, ps.version_id ) )

                offset += 1

        sheet.set_column_width( Range( Cell('A',1), Cell('S',offset)), 20 )
