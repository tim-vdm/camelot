import collections

from sqlalchemy import sql
from sqlalchemy.orm import aliased

from camelot.core.utils import ugettext_lazy as _
from camelot.core.conf import settings
from camelot.view.action_steps import UpdateProgress

from ...bank.constants import free_features, commission_receivers
from ...bank.report.abstract import AbstractReport
from ..visitor.abstract import AbstractVisitor
from ..premium import (FinancialAccountPremiumScheduleHistory,
                       FinancialAgreementPremiumSchedule)

class CommissionReport( AbstractReport ):
    
    name = _('Commissions')
            
    def fill_sheet( self, sheet, offset, options ):
        from vfinance.model.bank.entry import Entry
        from vfinance.model.financial.product import FinancialProduct 
        from vfinance.model.financial.account import FinancialAccount, FinancialAccountBroker
        from vfinance.model.financial.agreement import FinancialAgreement
        from vfinance.model.financial.constants import commission_types
        
        from integration.spreadsheet.base import Cell, Range, column_name, column_index, Add

        customer_prefix = unicode(settings.HYPO_ACCOUNT_KLANT).rstrip('0')
        features_to_list = [] + free_features
        visitor = AbstractVisitor( valid_at=options.report_date )
        
        e = aliased( Entry )
        FAPSH = aliased( FinancialAccountPremiumScheduleHistory )
        a = aliased( FinancialAccount )
        p = aliased( FinancialProduct )
        agr_ps = aliased( FinancialAgreementPremiumSchedule )
        agr = aliased( FinancialAgreement )
        session = Entry.query.session
        
        sheet.render( Cell( 'A', offset, 'Agreement Date' ) )
        sheet.render( Cell( 'B', offset, 'Agreement Code' ) )
        sheet.render( Cell( 'C', offset, 'Customer Number' ) )
        sheet.render( Cell( 'D', offset, 'Document Date' ) )
        sheet.render( Cell( 'E', offset, 'Book Date' ) )
        sheet.render( Cell( 'F', offset, 'Creation Date' ) )
        sheet.render( Cell( 'G', offset, 'Account Number' ) )
        sheet.render( Cell( 'H', offset, 'Account Name' ) )
        sheet.render( Cell( 'I', offset, 'Product Name' ) )
        sheet.render( Cell( 'J', offset, 'Valid From Date' ) )
        sheet.render( Cell( 'K', offset, 'Valid Thru Date' ) )
        sheet.render( Cell( 'L', offset, 'Premium amount' ) )
        sheet.render( Cell( 'M', offset, 'Period type' ) )
        sheet.render( Cell( 'N', offset, 'Taxation amount' ) )
        sheet.render( Cell( 'O', offset, 'Premium fee amount' ) )
        sheet.render( Cell( 'P', offset, 'Premium rate amount' ) )
        sheet.render( Cell( 'Q', offset, 'Entry fee amount' ) )
        sheet.render( Cell( 'R', offset, 'Funded premium amount' ) )
        sheet.render( Cell( 'S', offset, 'Net premium' ) )
        sheet.render( Cell( 'T', offset, 'Master broker' ) )
        sheet.render( Cell( 'U', offset, 'Broker' ) )
        sheet.render( Cell( 'V', offset, 'Street' ) )
        sheet.render( Cell( 'W', offset, 'Zipcode' ) )
        sheet.render( Cell( 'X', offset, 'City' ) )
        sheet.render( Cell( 'Y', offset, 'Number' ) )
        sheet.render( Cell( 'Z', offset, 'Supervisory authority Nr' ) )
        sheet.render( Cell( 'AA', offset, 'Agent' ) )
        sheet.render( Cell( 'AB', offset, 'Document' ) )
        sheet.render( Cell( 'AC', offset, 'Book' ) )
        for i, commission_type in enumerate(commission_types):
            first_col = column_index('AD') + i*len(commission_receivers) 
            sheet.render( Cell( column_name(first_col), offset-1, commission_type[1].replace('_', ' ').capitalize() ) )
            for j, commission_receiver in enumerate(commission_receivers):
                sheet.render( Cell( column_name(first_col + j), offset, commission_receiver[1].replace('_', ' ').capitalize() ) )
                
        first_feature_column = first_col + j + 1
        for i, feature_name in enumerate(features_to_list):
            sheet.render( Cell( column_name(first_feature_column + i), offset, feature_name ) )
            
        first_amount_column = first_feature_column + i + 1
        for i in range( 5 ):
            sheet.render( Cell( column_name(first_amount_column + i), offset, 'Premium rate %i amount'%(i+1) ) )

        status_column = first_amount_column + 5
        
        sheet.render(Cell(column_name(status_column), offset, 'Account status'))
        
        offset = offset + 1
        query = session.query( FAPSH, a, p, agr_ps, agr ).filter( sql.and_(
            FAPSH.from_date <= options.report_date,
            FAPSH.thru_date >= options.report_date,
            a.id==FAPSH.financial_account_id,
            p.id==FAPSH.product_id,
            agr_ps.id==FAPSH.agreed_schedule_id,
            agr.id==agr_ps.financial_agreement_id ) ).order_by( FAPSH.valid_from_date, FAPSH.history_of_id )
        if options.product:
            query = query.filter( p.id==options.product )
                
        for i, (premium_schedule, account, product, _agreed_schedule, agreement) in enumerate(query.yield_per(100)):
            
            grouped_entries = collections.defaultdict( dict )
            entries = dict()
            
            key = lambda e:(e.book_date, e.book.upper(), e.document, e.doc_date)
            
            if i%10 == 0:
                yield UpdateProgress( text = premium_schedule.full_account_number )
                
            for e in visitor.get_entries( premium_schedule, 
                                          from_document_date=options.from_document_date, 
                                          thru_document_date=options.thru_document_date,
                                          from_book_date = options.from_book_date,
                                          thru_book_date = options.thru_book_date,
                                          fulfillment_types = ['depot_movement', 'sales']):
                if e.amount != 0:
                    entry_key = key( e )
                    grouped_entries[ entry_key ][e.account] = e.amount
                    entries[ entry_key ] = e
            
            for entry_key, amounts in grouped_entries.items():
                
                entry = entries[ entry_key ]
                (book_date, book, document, doc_date) = entry_key
                
                def get_bookings_on_prefix( prefix ):
                    """Get all amounts on an account with a certain prefix
                    """
                    if prefix:
                        return sum( (value for key, value in amounts.items() if key.startswith( prefix )), 0 )
                    return 0
                    
                broker = FinancialAccountBroker.query.filter( sql.and_( FinancialAccountBroker.financial_account_id==account.id,
                                                                        FinancialAccountBroker.from_date <= doc_date,
                                                                        FinancialAccountBroker.thru_date >= doc_date ) ).first()
            
                sheet.render( Cell( 'A', offset, agreement.agreement_date ) )
                sheet.render( Cell( 'B', offset, agreement.code ) )
                
                customer = account.subscription_customer_at(doc_date)
                
                if customer:
                    customer_account = customer.full_account_number
                    sheet.render( Cell( 'C', offset, customer_account ) )
                else:
                    customer_account = None
                    sheet.render( Cell( 'C', offset, 'No customer' ) )
                    
                premium_amount = get_bookings_on_prefix( customer_prefix )
                
                def amount(described_by):
                    return premium_schedule.get_amount_at( premium_amount,
                                                           premium_schedule.valid_from_date, 
                                                           premium_schedule.valid_from_date, 
                                                           described_by )
                
                sheet.render( Cell( 'D', offset, doc_date ) )
                sheet.render( Cell( 'E', offset, book_date ) )
                sheet.render( Cell( 'F', offset, entry.creation_date ) )
                sheet.render( Cell( 'G', offset, premium_schedule.full_account_number ) )
                sheet.render( Cell( 'H', offset, premium_schedule.get_role_name_at(options.thru_document_date, 'subscriber', 1) ) )
                sheet.render( Cell( 'I', offset, product.name ) )
                sheet.render( Cell( 'J', offset, premium_schedule.valid_from_date ) )
                sheet.render( Cell( 'K', offset, premium_schedule.valid_thru_date ) )
                #
                # Customer might have changed in time between booking and
                # report, therefor look on all customer accounts
                #
                sheet.render( Cell( 'L', offset, get_bookings_on_prefix( customer_prefix ) ) )
                sheet.render( Cell( 'M', offset, premium_schedule.period_type ) )
                sheet.render( Cell( 'N', offset, get_bookings_on_prefix( product.get_account_at( 'taxes', book_date ) ) * -1 ) )
                sheet.render( Cell( 'O', offset, amount( 'premium_fee_1' ) ) )
                
                premium_rate_amount_cells = []
                for i in range( 5 ):
                    premium_rate_amount_cells.append( Cell( column_name(first_amount_column + i), offset, amount( 'premium_rate_%i'%(i+1) ) ) )
                    
                sheet.render( *premium_rate_amount_cells )

                sheet.render( Cell( 'P', offset, Add( *premium_rate_amount_cells ) ) )
                sheet.render( Cell( 'Q', offset, amount( 'entry_fee' ) ) )
                sheet.render( Cell( 'R', offset, get_bookings_on_prefix( product.get_account_at('funded_premium_attribution_cost', book_date ) ) ) )
                sheet.render( Cell( 'S', offset, get_bookings_on_prefix( premium_schedule.full_account_number ) * -1 ) )
                if broker and broker.broker_relation:
                    sheet.render( Cell( 'T', offset, broker.broker_relation.from_rechtspersoon.name ) )
                    sheet.render( Cell( 'U', offset, broker.broker_relation.name ) )
                    sheet.render( Cell( 'V', offset, broker.broker_relation.street ) )
                    sheet.render( Cell( 'W', offset, broker.broker_relation.zipcode ) )
                    sheet.render( Cell( 'X', offset, broker.broker_relation.city ) )
                    sheet.render( Cell( 'Y', offset, broker.broker_relation.number ) )
                    sheet.render( Cell( 'Z', offset, broker.broker_relation.supervisory_authority_number ) )
                    if broker.broker_agent:
                        sheet.render( Cell( 'AA', offset, broker.broker_agent.name ) )
                sheet.render( Cell( 'AB', offset, document ) )
                sheet.render( Cell( 'AC', offset, book ) )
                last_col = column_index('AD')
                for commission_type in commission_types:
                    for j, commission_receiver in enumerate(commission_receivers):
                        sheet.render( Cell( column_name(last_col + j), offset, premium_schedule.get_commission_distribution(commission_type[1], commission_receiver[1]) ) )
                    last_col += len(commission_receivers)
                for j, feature_name in enumerate(features_to_list):
                    value = premium_schedule.get_applied_feature_at(doc_date, doc_date, premium_schedule.premium_amount, feature_name, default=0).value
                    sheet.render( Cell( column_name(first_feature_column + j), offset, value ) )
                sheet.render(Cell(column_name(status_column), offset, account.current_status))
                offset += 1
                
        sheet.set_column_width( Range( Cell('A',1), Cell('Z',1) ), 20 )
