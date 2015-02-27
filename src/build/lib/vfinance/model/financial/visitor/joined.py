'''
Joined Visitor

Puts all the other visitors in series
'''

import collections
import itertools
import logging

from sqlalchemy import orm, sql

from camelot.core.exception import UserException

from .account_attribution import AccountAttributionVisitor
from .customer_attribution import CustomerAttributionVisitor
from .fund_attribution import FundAttributionVisitor
from .supplier_attribution import SupplierAttributionVisitor

from abstract import AbstractVisitor
from vfinance.connector.accounting import (AccountingSingleton,
                                           AccountingRequest,
                                           DocumentRequest,
                                           CreateAccountRequest)

from . import available_visitors
from ..premium import (FinancialAccountPremiumSchedule,
                       financial_account_premium_schedule_table)
from ...bank.account import Account

LOGGER = logging.getLogger('vfinance.model.financial.visitor.joined')
#LOGGER.setLevel( logging.DEBUG )

class JoinedVisitor( AbstractVisitor ):
    
    def __init__(self, accounting_connector=None):
        super( JoinedVisitor, self ).__init__()
        #
        # Construct all needed visitors, so they can be reused for
        # multiple premium schedules
        #
        unsorted_visitor_classes = list( available_visitors )
        sorted_visitor_classes = []
        while len( unsorted_visitor_classes ):
            for visitor_class in unsorted_visitor_classes:
                ok = True
                for dependency in visitor_class.dependencies:
                    if dependency not in sorted_visitor_classes:
                        ok = False
                        break
                if ok:
                    sorted_visitor_classes.append( visitor_class )
                    unsorted_visitor_classes.remove( visitor_class )
                    break
        
        self._all_visitors = [visitor_class() for visitor_class in sorted_visitor_classes if visitor_class!=CustomerAttributionVisitor]
        self._customer_attribution_visitor = CustomerAttributionVisitor()
        self._supplier_attribution_visitor = SupplierAttributionVisitor()
        LOGGER.debug( 'using visitors : ' + ', '.join( [ visitor.__class__.__name__ for visitor in self._all_visitors ] ) )
        if accounting_connector is None:
            accounting_connector = AccountingSingleton()
        self.accounting_connector = accounting_connector
        ps_query = self.session.query(FinancialAccountPremiumSchedule)
        ps_query = ps_query.options(orm.joinedload('financial_account'))
        self.premium_schedule_query = ps_query.options(orm.joinedload('product'))
        lock_select = sql.select([financial_account_premium_schedule_table.c.id])
        self.lock_select = lock_select.with_for_update(nowait=True)

    def visit_premium_schedule(self, premium_schedule, book_date):
        """Shortcut to run the visitors upto a specific book date"""
        for step in self.run_visitors([premium_schedule.id],
                                      premium_schedule.valid_from_date,
                                      book_date,
                                      book_date):
            yield step

    def _lock_premium_schedules(self, premium_schedule_ids):
        #
        # initiate the lock through the table itself instead of going
        # to the FinancialAccountPremiumSchedule object, since the latter
        # one will issue a table level lock because of the from/thru dates
        #
        lock_select = self.lock_select
        lock_select = lock_select.where(financial_account_premium_schedule_table.c.id.in_(premium_schedule_ids))
        self.session.execute(lock_select)

    def run_visitors(self, premium_schedule_ids, from_doc_date, thru_doc_date, book_date):
        """
        Loop through all the visitor classes and have them visit the
        premium schedule in the correct order.
        """
        session = self.session
        session.flush()
        session.expire_all()
    
        ps_query = self.premium_schedule_query
        ps_query = ps_query.filter(FinancialAccountPremiumSchedule.id.in_(premium_schedule_ids))
        premium_schedules = list(ps_query.all())

        visitor_dates_per_premium_schedule = dict()
        customer_attribution_dates = []

        #
        # These cases should be handled efficiently :
        #  * a visitor to be called multiple times on the same document date
        #  * a visitor be be called only for a specific premium schedule on a document date
        #
        with self.accounting_connector.begin(session):
            LOGGER.info('prepare visit of premium schedules {}'.format(premium_schedule_ids))
            self._lock_premium_schedules(premium_schedule_ids)
            for premium_schedule in premium_schedules:
                
                if premium_schedule.account_status not in ('draft', 'active'):
                    raise UserException('Account status is %s, not draft or active'%premium_schedule.account_status)
        
                #
                # find out which visitor needs to be called on which date
                #
                premium_schedule_from_doc_date = max(premium_schedule.valid_from_date, from_doc_date)
                for visit_date in self._customer_attribution_visitor.get_document_dates(premium_schedule, premium_schedule_from_doc_date, thru_doc_date):
                    customer_attribution_dates.append(visit_date)
                other_visitors_per_date = collections.defaultdict( list )
                for visitor in self._all_visitors:
                    for document_date in visitor.get_document_dates(premium_schedule, premium_schedule_from_doc_date, thru_doc_date):
                        visitors_at_document_date = other_visitors_per_date[ document_date ]
                        if not len(visitors_at_document_date) or visitors_at_document_date[-1] != visitor:
                            visitors_at_document_date.append( visitor )
        
                other_visitor_dates = list( other_visitors_per_date.keys() )
                other_visitor_dates.sort()
                max_document_date = max(other_visitor_dates + customer_attribution_dates + [premium_schedule_from_doc_date])
                financial_account = premium_schedule.financial_account
                product = premium_schedule.product
                all_visitors = set(itertools.chain.from_iterable(other_visitors_per_date.values()))

                visitor_dates_per_premium_schedule[premium_schedule.id] = other_visitors_per_date

                # create customers for the needed document dates
                subscriber_switch_dates = financial_account.get_role_switch_dates('subscriber')
                for switch_date in subscriber_switch_dates:
                    if switch_date <= max_document_date:
                        roles = financial_account.get_roles_at(switch_date, described_by='subscriber')
                        customer_request = self.create_customer_request(premium_schedule, roles)
                        self.accounting_connector.register_request(customer_request)
    
                # create suppliers for the needed document dates
                supplier_switch_dates = financial_account.get_supplier_switch_dates()
                for switch_date in supplier_switch_dates:
                    if switch_date <= max_document_date:
                        broker_relation = premium_schedule.financial_account.get_broker_at(switch_date)
                        for supplier_type in ['broker', 'master_broker']:
                            supplier_request = self.create_supplier_request(premium_schedule, broker_relation, supplier_type)
                            if supplier_request is not None:
                                self.accounting_connector.register_request(supplier_request)

                # if the account attribution visitor will run, make sure the accounts are
                # there.
                accounts_to_create = dict()
                for visitor in all_visitors:
                    if isinstance(visitor, AccountAttributionVisitor):
                        full_account_number = premium_schedule.full_account_number
                        name = premium_schedule.financial_account.subscriber_1[:250]
                        accounts_to_create[full_account_number] = name
                        if (product.financed_commissions_prefix) and len(''.join((product.financed_commissions_prefix))):
                            financed_commissions_account_number = premium_schedule.financed_commissions_account_number
                            accounts_to_create[financed_commissions_account_number] = name
                    if isinstance(visitor, FundAttributionVisitor):
                        for fund_distribution in premium_schedule.fund_distribution:
                            fund = fund_distribution.fund
                            # a fund might be canceled or temporary in draft
                            if fund.current_status != 'verified':
                                continue
                            # the fund distribution account
                            fund_distribution_account_number = fund_distribution.full_account_number
                            name = ('%s - %s'%(premium_schedule.financial_account.subscriber_1,
                                               fund_distribution.fund.isin))[:250]
                            accounts_to_create[fund_distribution_account_number] = name
                            # the fund account
                            name = fund.name[:250]
                            fund_account_number = fund.full_account_number
                            accounts_to_create[fund_account_number] = name
                for account_number, account_name in accounts_to_create.items():
                    if session.query(Account).filter(Account.number==account_number).count()==0:
                        request = CreateAccountRequest(
                            from_number=int(account_number),
                            thru_number=int(account_number),
                            name = account_name
                        )
                        self.accounting_connector.register_request(request)

        with self.accounting_connector.begin(session):
            for premium_schedule in premium_schedules:
                for visitor_date in customer_attribution_dates:
                    for step in self._customer_attribution_visitor.visit_premium_schedule_at(premium_schedule, visitor_date, book_date, from_doc_date):
                        if isinstance(step, AccountingRequest):
                            self.accounting_connector.register_request(step)

        retry = True
        while retry:
            retry = False
            previous_book_year = None
            with self.accounting_connector.begin(session):
                self._lock_premium_schedules(premium_schedule_ids)
                for premium_schedule in premium_schedules:
                    LOGGER.info(u'visiting premium schedule {0}'.format(unicode(premium_schedule)))
                    visitors_per_date = visitor_dates_per_premium_schedule[premium_schedule.id]
                    visitor_dates = list(visitors_per_date.keys())
                    visitor_dates.sort()
                    for visitor_date in visitor_dates:
                        for visitor in visitors_per_date[visitor_date]:
                            try:
                                LOGGER.debug( 'visit with %s at %s'%(visitor.__class__.__name__, visitor_date) )
                                for step in visitor.visit_premium_schedule_at( premium_schedule, visitor_date, book_date, from_doc_date):
                                    if isinstance(step, DocumentRequest):
                                        book_year = step.book_date.year
                                        if previous_book_year is None:
                                            previous_book_year = book_year
                                        if book_year != previous_book_year:
                                            # break out of the nested loop, and
                                            # re-run the shedules to handle the
                                            # next year
                                            retry = True
                                            LOGGER.warn('retry due to book year switch')
                                            break
                                    if isinstance(step, AccountingRequest):
                                        self.accounting_connector.register_request(step)
                                    yield step
                                else:
                                    continue
                                break
                            except Exception:
                                LOGGER.error(u'unhandled exception while visiting premium schedule %i with visitor %s on %s'%(premium_schedule.id, unicode(visitor), visitor_date))
                                raise
                        else:
                            continue
                        break
                    else:
                        continue
                    break

        retry = True
        while retry:
            retry = False
            previous_book_year = None
            with self.accounting_connector.begin(session):
                for premium_schedule in premium_schedules:
                    supplier_attribution_dates = self._supplier_attribution_visitor.get_document_dates(premium_schedule, from_doc_date, thru_doc_date)
                    for visitor_date in supplier_attribution_dates:
                        for step in self._supplier_attribution_visitor.visit_premium_schedule_at(premium_schedule, visitor_date, book_date, from_doc_date):
                            if isinstance(step, DocumentRequest):
                                book_year = step.book_date.year
                                if previous_book_year is None:
                                    previous_book_year = book_year
                                if book_year != previous_book_year:
                                    # break out of the nested loop, and
                                    # re-run the shedules to handle the
                                    # next year
                                    retry = True
                                    LOGGER.warn('retry due to book year switch')
                                    break
                            if isinstance(step, AccountingRequest):
                                self.accounting_connector.register_request(step)
                            yield step
                        else:
                            continue
                        break
                    else:
                        continue
                    break
