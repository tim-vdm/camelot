import collections
import operator

from camelot.core.orm import Session
from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from sqlalchemy import orm, sql

from ...bank.report.abstract import AbstractReport
from ..premium import FinancialAccountPremiumScheduleHistory as FAPSH

report_fulfillment_types = [('M', 'Premium', ('depot_movement', )),
                            ('N', 'Redemption', ('capital_redemption_deduction',
                                                 'interest_redemption_deduction',
                                                 'additional_interest_redemption_deduction',
                                                 'redemption')),
                            ('O', 'Financed commissions', ('financed_commissions_deduction', 'financed_commissions_redemption_deduction')),
                            ('P', 'Risk', ('risk_deduction', )),
                            ('Q', 'Interest', ('interest_attribution', 'additional_interest_attribution')),
                            ('R', 'Profit', ('profit_attribution', )),
                            ('S', 'Sundry', ('sundry', )),
                            ('T', 'Quotation', ('security_quotation', )),
                            ('U', 'Financed switch', ('financed_switch', )),
                            ('V', 'Switch out', ('switch_out',)),
                            ('W', 'Switch in', ('switch_attribution', 'switch_deduction')),
                            ('X', 'Attribution cost', ('fund_attribution', )),
                            ]

check_column = 'Y'

class MovementsReport( AbstractReport ):
    
    name = _('Movements')
            
    def fill_sheet( self, sheet, offset, options ):
        from ..visitor.abstract import FinancialBookingAccount
        from ..visitor.security_orders import SecurityOrdersVisitor
        visitor = SecurityOrdersVisitor(valid_at=options.report_date)
        
        from integration.spreadsheet.base import Cell, Add, Sub, Sum, Range
        yield UpdateProgress(text=_('Create movements report'))

        all_fulfillment_types = []

        # Account related Info
        sheet.render( Cell( 'A', offset, 'Account' ) )
        sheet.render( Cell( 'B', offset, 'Master Broker' ) )
        sheet.render( Cell( 'C', offset, 'Broker' ) )
        # Premium schedule related info
        sheet.render( Cell( 'D', offset, 'Premium schedule' ) )
        sheet.render( Cell( 'E', offset, 'Product' ) )
        sheet.render( Cell( 'F', offset, 'Base product' ) )
        sheet.render( Cell( 'G', offset, 'Agreement Code' ) )
        sheet.render( Cell( 'H', offset, 'Account number' ) )
        # Fonds info
        sheet.render( Cell( 'I', offset, 'Fund' ) )
        sheet.render( Cell( 'J', offset, 'Fund name' ) )
        # Waardes
        sheet.render( Cell( 'K', offset, 'Value From' ) )
        sheet.render( Cell( 'L', offset, 'Value Thru' ) )
        # Wijzigingen
        for col_name, title, fulfillment_types in report_fulfillment_types:
            all_fulfillment_types.extend(fulfillment_types)
            sheet.render( Cell( col_name, offset, title ) )
        sheet.render( Cell( check_column, offset, 'Check' ) )
        sheet.render(Cell('Z', offset, 'Account status'))

        session = Session()
        query = session.query(FAPSH).filter(sql.and_(
            FAPSH.from_date <= options.report_date,
            FAPSH.thru_date >= options.report_date,
        ))
        if options.product:
            query = query.filter( FAPSH.product_id==options.product )
        if options.from_account_suffix:
            query = query.filter( FAPSH.account_suffix>=options.from_account_suffix )
        if options.thru_account_suffix:
            query = query.filter( FAPSH.account_suffix<=options.thru_account_suffix )
        number_of_schedules = query.count()
        query = query.order_by(FAPSH.financial_account_id, FAPSH.history_of_id)
        query = query.options(orm.joinedload('financial_account'))
        
        for i, premium_schedule in enumerate(query.yield_per(10)):
            if i % 10 == 0:
                yield UpdateProgress(i, number_of_schedules, text='Schedule {0.product_name} {0.id}'.format(premium_schedule))
            account = premium_schedule.financial_account
            booking_accounts = set()
            for fund_distribution in premium_schedule.fund_distribution:
                booking_accounts.add(FinancialBookingAccount('fund', fund_distribution.fund))
            booking_accounts = list(booking_accounts)
            booking_accounts.sort()
            # uninvested account as last one, since all fund attributions will be compensated on it
            uninvested_fulfillment_values = collections.defaultdict(int)
            for booking_account in booking_accounts + [FinancialBookingAccount('uninvested')]:
                offset += 1
                sheet.render( Cell( 'A', offset, account.id ) )
                sheet.render( Cell( 'B', offset, account.master_broker ) )
                sheet.render( Cell( 'C', offset, account.broker ) )
                sheet.render( Cell( 'D', offset, premium_schedule.history_of_id ) )
                sheet.render( Cell( 'E', offset, premium_schedule.product.name ) )
                sheet.render( Cell( 'F', offset, premium_schedule.product.base_product or '') )
                sheet.render( Cell( 'G', offset, '.'.join(list(premium_schedule.agreement_code)) ) )
                sheet.render( Cell( 'H', offset, premium_schedule.full_account_number ) )

                if booking_account.account_type == 'fund':
                    sheet.render( Cell( 'I', offset, booking_account.fund.full_account_number ) )
                    sheet.render( Cell( 'J', offset, booking_account.fund.name ) )
                    fulfillment_values = collections.defaultdict(int)
                else:
                    fulfillment_values = uninvested_fulfillment_values
                
                #
                # instead of requesting the from value, ask the thru value, and then
                # subtract the delta calculated with the same options as the movements,
                # to make sure the picture is consistent
                #
                
                thru_value = visitor.get_total_amount_until( premium_schedule, 
                                                             thru_document_date = options.thru_document_date,
                                                             thru_book_date=options.thru_book_date,
                                                             account=booking_account)[0]
                
                delta_value = visitor.get_total_amount_until( premium_schedule,
                                                              thru_document_date = options.thru_document_date,
                                                              thru_book_date = options.thru_book_date,
                                                              from_document_date=options.from_document_date,
                                                              from_book_date=options.from_book_date, 
                                                              account=booking_account)[0]
                
                from_value = thru_value - delta_value

                sheet.render( Cell( 'K', offset, from_value*-1 ) )
                sheet.render( Cell( 'L', offset, thru_value*-1 ) )
                
                first_cell, last_cell = None, None
                
                for fulfillment_type in all_fulfillment_types:
                    value = visitor.get_total_amount_until( premium_schedule, 
                                                            thru_document_date = options.thru_document_date,
                                                            thru_book_date = options.thru_book_date,
                                                            from_document_date=options.from_document_date,
                                                            from_book_date=options.from_book_date, 
                                                            account=booking_account,
                                                            fulfillment_type=fulfillment_type )[0]
                    if booking_account.account_type == 'fund':
                        value_with_association = visitor.get_total_amount_until( premium_schedule, 
                                                                                 thru_document_date = options.thru_document_date,
                                                                                 thru_book_date = options.thru_book_date,
                                                                                 from_document_date=options.from_document_date,
                                                                                 from_book_date=options.from_book_date, 
                                                                                 account=booking_account,
                                                                                 fulfillment_type='fund_attribution',
                                                                                 conditions=[('associated_to_fulfillment_type', operator.eq, fulfillment_type)])[0]
                        fulfillment_values['fund_attribution'] -= value_with_association
                        uninvested_fulfillment_values['fund_attribution'] += value_with_association
                        uninvested_fulfillment_values[fulfillment_type] -= value_with_association
                        value += value_with_association
                    fulfillment_values[fulfillment_type] += value

                for j, (col_name, _title, fulfillment_types) in enumerate(report_fulfillment_types):
                    value = sum(fulfillment_values[fulfillment_type] for fulfillment_type in fulfillment_types)
                    cell = Cell( col_name, offset, value*-1 )
                    if j == 0:
                        first_cell = cell
                    else:
                        last_cell = cell
                    sheet.render(cell)

                
                sheet.render( Cell( check_column, offset, Sub(Add(Cell('K',offset), Sum(Range(first_cell, last_cell))), Cell('L', offset)) ))
                sheet.render(Cell('Z', offset, account.current_status))
