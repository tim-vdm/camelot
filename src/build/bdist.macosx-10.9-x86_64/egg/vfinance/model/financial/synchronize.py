'''
Created on Jun 1, 2010

@author: tw55413
'''

import calendar
import datetime
import heapq
import logging

logger = logging.getLogger('vfinance.model.financial.synchronize')

from camelot.admin.action import Action
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import Session
from camelot.core.conf import settings
from camelot.view import action_steps
from camelot.admin.object_admin import ObjectAdmin
from camelot.view.controls import delegates

from integration.venice.venice import clear_com_object_cache

from sqlalchemy import orm, sql
from sqlalchemy.exc import OperationalError

from .visitor.joined import JoinedVisitor
from ...process import WorkerProcess, WorkerPool, Progress, WorkerProcessException
from ...retry_generator import retry_generator, retry_function

#
# During nightly sync, the OperationalError : software caused connection abort is
# sometimes thrown, for an explanation, see :
#
# http://technet.microsoft.com/en-us/library/cc976365.aspx
#
# This is believed to be a network glitch
#

# these are the method names of FinancialSynchronizer in the order they
# should be called
ordered_options = [
    'read_account_entries',
    'read_pending_premiums',
    'create_premium_schedules',
    'attribute_pending_premiums',
    'run_forward',
    'create_premium_invoices',
    'create_direct_debit_batches'
]

class SynchronizerOptions(object):

    def __init__(self, options=ordered_options):
        for option in ordered_options:
            if option in options:
                setattr(self, option, True)
            else:
                setattr(self, option, False)

    class Admin(ObjectAdmin):
        form_display = ordered_options
        field_attributes = dict( (o,{'delegate':delegates.BoolDelegate, 'editable':True}) for o in ordered_options)

default_options = SynchronizerOptions()

class ModelContext( object ):
    """Fake model context to run actions"""

    def __init__( self, selection, mode_name ):
        self.mode_name = mode_name
        self.selection = selection
        self.session = Session()

    def get_selection( self ):
        return self.selection

class SynchronizationException(WorkerProcessException):
    """To be yielded when an exception takes place during
    synchronization.  This object stores information of the
    exception for reuse"""

    def __init__( self, message ):
        super(SynchronizationException, self).__init__(message)

    def __unicode__(self):
        return self.message

class VisitPremiumSchedulesProcess(WorkerProcess):
    """A worker that runs the joined visitor on sets of premium schedules
    """

    def __init__(self, from_doc_date, thru_doc_date, book_date, **kwargs):
        super(VisitPremiumSchedulesProcess, self).__init__(**kwargs)
        self.from_doc_date = from_doc_date
        self.thru_doc_date = thru_doc_date
        self.book_date = book_date

    def initialize(self):
        self.visitor = JoinedVisitor()
        self.visit_counter = 0

    @retry_generator(OperationalError)
    def handle_work(self, premium_schedule_ids):
        try:
            # send a progress update to allow the parent process to terminate
            # the work
            #yield Progress(', '.join([unicode(ps_id) for ps_id in premium_schedule_ids]))
            for visit in self.visitor.run_visitors(premium_schedule_ids,
                                                   self.from_doc_date,
                                                   self.thru_doc_date,
                                                   self.book_date):
                if visit is not None:
                    yield visit
            #
            # every 100 schedules, disconnect Venice, to clean up resources
            #
            for _id in premium_schedule_ids:
                self.visit_counter += 1
                if (self.visit_counter % 100) == 0:
                    clear_com_object_cache()
        except Exception:
            yield SynchronizationException(u'Error when visiting premium schedules %s'%(premium_schedule_ids))


class FinancialSynchronizer(object):

    def __init__(self, run_date=None, min_schedule=None, max_schedule=None, read_all=False):
        """
        :param run_date: the date at which the synchronizer should think it runs,
            if None is given, it will think it runs today.
        """
        logger.info('build Financial Synchronizer with run date %s'%run_date)
        self._settings = settings
        self._run_date = run_date or datetime.date.today()
        self._min_schedule = min_schedule
        self._max_schedule = max_schedule
        self._from_document_date = datetime.date(self._run_date.year-1,1,1)
        self._batch_job = None
        self._read_all = read_all

    @retry_generator(OperationalError)
    def create_premium_schedules(self):
        """Create premium schedules on accounts from unfulfilled invested amounts"""
        from vfinance.model.financial.premium import FinancialAgreementPremiumSchedule
        from vfinance.model.financial.admin import RunAgreementForward
        run_agreement_forward = RunAgreementForward()
        session = Session()
        for invested_amount in FinancialAgreementPremiumSchedule.query.filter(sql.and_(FinancialAgreementPremiumSchedule.current_status_sql=='verified',
                                                                                       FinancialAgreementPremiumSchedule.fulfilled==0)):
            try:
                for step in run_agreement_forward.run_agreement_forward([invested_amount.financial_agreement], session):
                    if isinstance(step, action_steps.UpdateProgress):
                        if step._detail is not None:
                            yield step._detail
            except Exception:
                yield SynchronizationException( 'could not create premium shedule for invested amount %i'%invested_amount.id )

    @retry_generator(OperationalError)
    def create_premium_invoices(self):
        from vfinance.model.financial.premium import FinancialAccountPremiumSchedule
        for premium in FinancialAccountPremiumSchedule.query.filter(FinancialAccountPremiumSchedule.direct_debit==True).all():
            invoicing_period = premium.get_applied_feature_at(self._run_date, premium.valid_from_date, premium.premium_amount, 'invoicing_period', default=0)
            if invoicing_period:
                due_date = self._run_date + datetime.timedelta(days=int(invoicing_period.value)+1)
                if premium.create_invoice_item( due_date ):
                    yield u'created invoice item for premium on account %s'%unicode(premium.financial_account)

    @retry_generator(OperationalError)
    def create_direct_debit_batches(self):
        from vfinance.model.bank.invoice import InvoiceItem
        for invoice_item in InvoiceItem.query.filter(sql.and_(InvoiceItem.premium_schedule_id!=None,
                                                              InvoiceItem.last_direct_debit_batch_id==None)).yield_per(100):
            if not invoice_item.last_direct_debit_batch_id:
                if invoice_item.premium_schedule.direct_debit is True:
                    direct_debit_period = invoice_item.premium_schedule.get_applied_feature_at(self._run_date,
                                                                                               invoice_item.premium_schedule.valid_from_date,
                                                                                               invoice_item.premium_schedule.premium_amount,
                                                                                               'direct_debit_period',
                                                                                               default = 0)
                    try:
                        if invoice_item.voeg_toe_aan_domiciliering( int(direct_debit_period.value) ):
                            orm.object_session(invoice_item).flush()
                            yield 'invoice item %s attached to direct debit batch'%invoice_item.id
                    except Exception:
                        yield SynchronizationException( 'could not attach invoice item %i to direct debit batch'%invoice_item.id )

    @retry_generator(OperationalError)
    def read_account_entries(self):
        from vfinance.model.bank.entry import Entry
        from vfinance.model.financial.product import FinancialProduct
        from vfinance.model.hypo.product import LoanProduct
        prefixes = set()
        session = Session()
        #
        # No sync of the customer accounts, since this is done in Tiny ??
        #
        prefixes.add( self._settings.get('HYPO_ACCOUNT_KLANT').strip('0') )
        for product in session.query( LoanProduct ).all():
            for product_account in product.get_accounts( 'vordering' ):
                prefixes.add( ''.join( product_account.number ).strip('0') )

        #
        # Sync all accounts only on friday
        #
        weekday = calendar.weekday( self._run_date.year,
                                    self._run_date.month,
                                    self._run_date.day )

        if weekday != 4 and not self._read_all:
            yield 'only read customer and mortgage accounts on a weekday'
        else:
            for product in FinancialProduct.query.all():
                for prefix_name in [ 'account_number_prefix',
                                     'financed_commissions_prefix',
                                     ]:
                    if getattr(product, prefix_name):
                        prefix = getattr(product, prefix_name)
                        if isinstance(prefix, int):
                            prefix = str(prefix)
                        if isinstance(prefix, list):
                            prefix = ''.join( prefix )
                        prefixes.add( prefix )
                for account_type in ['provisions',
                                     'provisions_cost',
                                     'taxes',
                                     'entry_fee_revenue',
                                     'premium_fee_1_revenue',
                                     'premium_rate_1_revenue',
                                     'funded_premium_cost',
                                     'funded_premium',
                                     'financed_commissions_revenue'
                                     ]:
                    for product_account in product.get_accounts( account_type ):
                        if product_account.number:
                            prefix = ''.join( product_account.number )
                            if prefix:
                                prefixes.add( prefix )

        for prefix in prefixes:
            try:
                if prefix:
                    yield u'read entries with prefix : %s'%(prefix)
                    Entry.sync_venice(prefix)
            except Exception, e:
                logger.error( 'error when syncing prefix %s'%prefix, exc_info = e )
                yield SynchronizationException( u'Error when syncing prefix %s'%(prefix) )
            #if self._batch_job and self._batch_job.is_canceled():
            #		break

    @retry_generator(OperationalError)
    def read_pending_premiums(self):
        from vfinance.model.bank.entry import Entry
        from vfinance.model.financial.product import FinancialProduct
        prefixes = set()
        for product in FinancialProduct.query.all():
            for product_account in product.get_accounts('pending_premiums'):
                if product_account.number:
                    prefix = ''.join(product_account.number)
                    if prefix:
                        prefixes.add( prefix )

        for prefix in prefixes:
            Entry.sync_venice(prefix)
            yield u'read pending premiums with prefix : %s'%(prefix)

    @retry_generator(OperationalError)
    def attribute_pending_premiums(self):
        from vfinance.model.financial.open_entries import AttributePendingPremiums
        from vfinance.model.financial.premium import FinancialAccountPremiumSchedule
        attribute_action = AttributePendingPremiums()
        session = Session()
        premium_schedules_query = session.query(FinancialAccountPremiumSchedule)
        try:
            for step in attribute_action.attribute_pending_premiums(premium_schedules_query, session):
                if isinstance(step, action_steps.UpdateProgress):
                    yield step._detail
        except Exception, e:
            logger.error( 'error attributing pending premiums', exc_info = e)
            yield SynchronizationException( 'could not attribute pending premiums' )

    def rollback_batch_session(self):
        if self._batch_job:
            batch_session = orm.object_session( self._batch_job )
            batch_session.rollback()

    @retry_function(OperationalError)
    def is_batch_job_canceled(self):
        #self.rollback_batch_session()
        return self._batch_job and self._batch_job.is_canceled()

    @retry_function(OperationalError)
    def add_strings_to_batch_job(self, strings):
        self._batch_job.add_strings_to_message(strings)

    def run_forward(self):
        from vfinance.model.financial.premium import FinancialAccountPremiumSchedule

        min_schedule = self._min_schedule
        max_schedule = self._max_schedule

        session = Session()
        premium_schedule_info_select = sql.select([FinancialAccountPremiumSchedule.id.label('id'),
                                                   FinancialAccountPremiumSchedule.last_transaction.label('last_transaction'),
                                                   FinancialAccountPremiumSchedule.last_quotation.label('last_quotation'),
                                                   FinancialAccountPremiumSchedule.last_premium_attribution.label('last_premium_attribution')])

        premium_schedule_info_select = premium_schedule_info_select.where(FinancialAccountPremiumSchedule.account_status.in_(['draft', 'active']))

        if min_schedule is not None:
            premium_schedule_info_select = premium_schedule_info_select.where(FinancialAccountPremiumSchedule.id >= int(min_schedule))

        if max_schedule is not None:
            premium_schedule_info_select = premium_schedule_info_select.where(FinancialAccountPremiumSchedule.id <= int(max_schedule))

        logger.info('start reading premium schedule dates')
        premium_schedules = []
        for i,premium_schedule_info in enumerate(session.execute(premium_schedule_info_select)):
            last_activity_date = datetime.date(2000,1,1)
            for activity_date in (premium_schedule_info.last_transaction, premium_schedule_info.last_quotation, premium_schedule_info.last_premium_attribution):
                if activity_date is not None:
                    last_activity_date = max(last_activity_date, activity_date)
            heapq.heappush(premium_schedules, ((self._run_date-last_activity_date).days, premium_schedule_info.id))
            if (i % 1000) == 0:
                if self.is_batch_job_canceled():
                    break

        logger.info('found {0} premium schedules'.format(len(premium_schedules)))

        def work_generator():
            previous_days_since_last_activity = None
            while len(premium_schedules):
                premium_schedule_ids = []
                for j in range(10):
                    if len(premium_schedules):
                        days_since_last_activity, premium_schedule_id = heapq.heappop(premium_schedules)
                        premium_schedule_ids.append(premium_schedule_id)
                if days_since_last_activity != previous_days_since_last_activity:
                    logger.info('enter range of {0} days since last activity'.format(days_since_last_activity))
                    previous_days_since_last_activity = days_since_last_activity
                yield premium_schedule_ids
                #
                # every 10 schedules, verify if the batch job should still be running
                #
                if self.is_batch_job_canceled():
                    break

        yield Progress(u'Start run forward of premium schedules')
        with WorkerPool(VisitPremiumSchedulesProcess,
                        from_doc_date = self._from_document_date,
                        thru_doc_date = self._run_date,
                        book_date = self._run_date) as pool:
            logger.info('using {0} workers'.format(len(pool)))
            for result in pool.submit(work_generator()):
                yield result

    def all(self, options=default_options):
        from camelot.model.batch_job import BatchJob, BatchJobType
        from integration.venice.venice import clear_com_object_cache
        session = Session()
        batch_job_type = BatchJobType.get_or_create('Financial Sync')
        with BatchJob.create( batch_job_type ) as batch_job:
            self._batch_job = batch_job
            for option in ordered_options:
                #
                # restore the session in case is was messed up by previous actions
                #
                session.rollback()
                session.expire_all()
                if not getattr( options, option ):
                    continue
                if self.is_batch_job_canceled():
                    self.add_strings_to_batch_job( [ '<font color="orange">Canceled</font>' ] )
                    break
                logger.info( 'begin %s'%option )
                begin = datetime.datetime.now()
                for message in getattr(self, option)():
                    if isinstance( message, SynchronizationException ):
                        logger.error('synchronization exception', exc_info=message.exc_info)
                        self.add_strings_to_batch_job( [ '<font color="orange">' + message.message + '</font>' ] )
                        # we'll assume the previous method call only finishes when
                        # the database connection is up
                        self._batch_job.add_exception_to_message(*message.exc_info)
                        self._batch_job.change_status(u'warnings')
                    elif isinstance( message, basestring):
                        yield action_steps.UpdateProgress( text = message )
                        self.add_strings_to_batch_job( [unicode(message)] )
                logger.info( 'end %s'%option )
                end = datetime.datetime.now()
                total_seconds = (end-begin).total_seconds()
                self.add_strings_to_batch_job( ['finished {0} in {1} seconds'.format(option, total_seconds)] )
                #
                # after each action, clear the Venice connection, to make
                # room for others should it take a long time before the
                # next connection is needed
                #
                clear_com_object_cache()
            finished_at = datetime.datetime.now()
            self.add_strings_to_batch_job( [ '<br>Finished at %s</br>'%( finished_at ) ] )
            logger.info('all finished at %s'%finished_at )

class SynchronizeAction(Action):

    verbose_name = _('Synchronize')

    def model_run(self, model_context, options=SynchronizerOptions()):
        yield action_steps.ChangeObject(options)
        synchronizer = FinancialSynchronizer()
        yield action_steps.UpdateProgress( text = _('Synchronization in progress') )
        for step in synchronizer.all(options):
            yield step
