import logging

from vfinance.model.financial.visitor.abstract import AbstractVisitor

from sqlalchemy import orm

from ...bank.constants import commission_receivers
from ...bank.entry import Entry
from ...bank.visitor import ProductBookingAccount
from .account_attribution import distributed_revenue_types

LOGGER = logging.getLogger('vfinance.model.financial.visitor.supplier_attribution')

# dont change the order of the supplier attributions or of the distributed revenue
# types
supplier_attributions = [
    ('sales',                           'sales_distribution',                [(revenue_type+'_revenue', revenue_type+'_cost') for revenue_type in distributed_revenue_types]),
    ('financed_commissions_activation', 'financed_commissions_distribution', [('financed_commissions_revenue', 'financed_commissions_cost')]),
    ('funded_premium_activation',       'funded_premium_distribution',       [('funded_premium', 'funded_premium')]),
    ]

supplier_attribution_fulfillment_types = [supplier_attribution[0] for supplier_attribution in supplier_attributions]
distribution_fulfillment_types = [supplier_attribution[1] for supplier_attribution in supplier_attributions]

class SupplierAttributionVisitor(AbstractVisitor):
    """Attribute revenues/costs that have been booked on behalf of the broker,
    master-broker or agent to their supplier account.
    """

    def get_document_dates(self, premium_schedule, from_date, thru_date):
        LOGGER.debug('get_document_dates')
        document_dates = set()
        for supplier_attribution_entry in self.get_entries(premium_schedule,
                                                           from_document_date = from_date,
                                                           thru_document_date = thru_date,
                                                           fulfillment_types = supplier_attribution_fulfillment_types):
            document_date = supplier_attribution_entry.doc_date
            if document_date not in document_dates:
                yield document_date
                document_dates.add(document_date)

    def visit_premium_schedule_at(self, premium_schedule, document_date, book_date, last_visited_document_date):
        product = premium_schedule.product
        LOGGER.debug('visit {0.id} at {1}'.format(premium_schedule, document_date))
        for _receiver_id, receiver in commission_receivers:
            for origin_fulfillment, destination_fulfillment, revenue_types in supplier_attributions:
                transaction = [] # this will be transaction 31 or 16
                entries = list(self.get_entries(premium_schedule, 
                                                from_document_date = document_date,
                                                thru_document_date = document_date,
                                                fulfillment_type = origin_fulfillment))
                # each entry should only be transferred once to the supplier
                for entry in entries:
                    for revenue_account, cost_account in revenue_types:
                        distributed_revenue_account = ProductBookingAccount('{revenue_account}_{receiver}'.format(revenue_account=revenue_account, receiver=receiver))
                        if entry.account == distributed_revenue_account.booking_account_number_at(premium_schedule, entry.book_date):
                            distributed_cost_account = ProductBookingAccount('{cost_account}_{receiver}'.format(cost_account=cost_account, receiver=receiver))
                            attributed_to_supplier = self.get_total_amount_until(premium_schedule,
                                                                                 associated_to_id=entry.fulfillment_id,
                                                                                 account=distributed_cost_account)[0]
                            commission_amount = entry.amount + attributed_to_supplier
                            if commission_amount != 0:
                                session = orm.object_session(premium_schedule)
                                entry_object = session.query(Entry).get(entry.id)
                                transaction.append(
                                    self.create_line(distributed_cost_account,
                                                     commission_amount * -1,
                                                     entry_object.remark,
                                                     destination_fulfillment,
                                                     associated_fulfillment_id=entry.fulfillment_id)
                                )
                            break
                if len(transaction):
                    LOGGER.debug('book transaction {0}'.format(destination_fulfillment))
                    for step in self.create_purchase(premium_schedule,
                                                     book_date,
                                                     document_date,
                                                     transaction,
                                                     product.supplier_distribution_book,
                                                     destination_fulfillment,
                                                     receiver,
                                                     remark=transaction[0].remark):
                        yield step


