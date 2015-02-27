import datetime
import logging
import collections
from decimal import Decimal as D

from sqlalchemy import sql, orm

from camelot.core.exception import UserException

from ..security_order import FinancialSecurityOrderLine
from security_orders import SecurityOrdersVisitor, security_order
from financed_commission import FinancedCommissionVisitor
from account_attribution import AccountAttributionVisitor
from risk_deduction import RiskDeductionVisitor
from transaction_initiation import TransactionInitiationVisitor

LOGGER = logging.getLogger('vfinance.model.financial.visitor.security_order_lines')

class SecurityOrderLinesVisitor(SecurityOrdersVisitor):
 
    dependencies = [FinancedCommissionVisitor,
                    AccountAttributionVisitor,
                    RiskDeductionVisitor,
                    TransactionInitiationVisitor,]
    
    def get_document_dates(self, _premium_schedule, from_date, thru_date):
        # @todo : when the premium schedule is not unit linked there should be
        # no visit
        document_date = min( datetime.date.today(), thru_date )
        yield document_date
        
    def visit_premium_schedule_at(self, premium_schedule, document_date, book_date, _last_visited_document_date):
        # @todo : use the actual last visited document date
        #         the issue here is that current logic does not take into account
        #         the uninvested amount before the last visited document date.
        #         as such, faulty orders might be created in cases such as :
        #         - a full redemption before the last visited document date which 
        #           has not yet been executed due to no quotation -> there is an
        #           uninvested order line
        #         - a second full redemption after the last visited document date
        #           -> this one will generate a second order line for the same
        #           quantity
        #         - as a result, the ordered amount will be twice the available
        #           amount.
        #         premium schedule 2816, suffix 2777 is an example of such behavior
        last_visited_document_date = datetime.date(2000, 1, 1)
        #
        # All amounts on a specific date need to be grouped, because only
        # grouped ordered and to order amounts can be compared
        #
        grouped_amounts = collections.defaultdict( D )
        funds_by_id = dict( (distribution.fund_id, distribution.fund) for distribution in premium_schedule.fund_distribution )
        funds_distribution_by_id = dict( (distribution.fund_id, distribution) for distribution in premium_schedule.fund_distribution )
        
        #
        # Add all existing order lines to the list, to make sure counter lines
        # are made if necessary
        #
        for security_order_line in FinancialSecurityOrderLine.query.filter( sql.and_( FinancialSecurityOrderLine.premium_schedule == premium_schedule,
                                                                                      FinancialSecurityOrderLine.document_date  <= document_date,
                                                                                      FinancialSecurityOrderLine.document_date >= last_visited_document_date ) ).all():
            
            key = (security_order_line.document_date, security_order_line.fulfillment_type, security_order_line.financial_security_id, security_order_line.described_by)
            grouped_amounts[key] += 0 
        
        for security_orders in self.get_premium_security_orders( premium_schedule, document_date, last_visited_document_date):
            key = (security_orders.doc_date, security_orders.fulfillment_type, security_orders.fund_distribution.fund_id, security_orders.order_type)
            grouped_amounts[key] += security_orders.quantity
                    
        keys = list( grouped_amounts.keys() )
        keys.sort( key = lambda x:x[0] )
        for key in keys:
            order_line_document_date, fulfillment_type, fund_id, order_type = key
            amount_to_invest = grouped_amounts[ key ]
            try:
                financial_security = funds_by_id[ fund_id ]
                fund_distribution = funds_distribution_by_id[ fund_id ]
            except KeyError:
                raise UserException( 'Premium schedule has no fund distribution defined for fund %s'%fund_id )
            
            uninvested_orders = 0
            for univested_key in keys:
                if univested_key == key:
                    continue
                uninvested_order_line_document_date, uninvested_fulfillment_type, uninvested_fund_id, uninvested_order_type = univested_key
                if uninvested_fund_id != fund_id:
                    continue
                if uninvested_order_type != order_type:
                    continue
                if uninvested_order_line_document_date > order_line_document_date:
                    continue
                uninvested_amount = grouped_amounts[ univested_key ]
                quotation = self.get_valid_quotation_at_date( financial_security, 
                                                              uninvested_order_line_document_date, 
                                                              uninvested_amount )
                if quotation == None or quotation.from_datetime.date() >= order_line_document_date:
                    uninvested_orders += uninvested_amount
            
            amount_to_invest = self.get_limited_quantity( premium_schedule, 
                                                          fund_distribution, 
                                                          order_line_document_date, 
                                                          order_type, 
                                                          amount_to_invest, 
                                                          uninvested_orders = uninvested_orders )
            
            ordered_amount = self.get_ordered_amount( premium_schedule, order_line_document_date, fulfillment_type, fund_id, order_type)
            amount_to_order = amount_to_invest - ordered_amount
            
            if fulfillment_type == 'amount':
                order_treshold = D('0.01')
            else:
                order_treshold = D('0.00001')
                
            if abs(amount_to_order) > order_treshold:
                if financial_security.order_lines_from <= order_line_document_date and financial_security.order_lines_thru >= order_line_document_date:
                    order_line = FinancialSecurityOrderLine(document_date = order_line_document_date,
                                                            fulfillment_type = fulfillment_type,
                                                            financial_security = financial_security,
                                                            described_by = order_type,
                                                            quantity = amount_to_order,
                                                            premium_schedule = premium_schedule)
                    # make sure we yield a pickable object, that can be used in the
                    # progress indicator and be sent over the wire
                    yield security_order(doc_date=order_line_document_date,
                                         fulfillment_type=fulfillment_type,
                                         fund_distribution=fund_distribution.fund.name,
                                         order_type=order_type,
                                         quantity=amount_to_order,
                                         attribution_rate_quantity=None,
                                         associated_to=None,
                                         within_id=None)
                    # flush immediately, to make the next get_limited_quantity work
                    orm.object_session(order_line).flush()
                    LOGGER.info('Create order line {0.id} on {0.document_date}'.format(order_line))