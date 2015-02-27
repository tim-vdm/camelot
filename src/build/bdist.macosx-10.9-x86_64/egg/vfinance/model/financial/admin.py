from copy import deepcopy
import datetime
import logging
import itertools

from camelot.core.qt import QtGui

from sqlalchemy import sql

from camelot.admin.entity_admin import EntityAdmin
from camelot.admin import table
from camelot.view.controls import delegates
from camelot.view import forms, action_steps
from camelot.admin.action import ( CallMethod,
                                   list_filter,
                                   Action,
                                   ApplicationActionModelContext )
from camelot.core.exception import UserException, CancelRequest
from camelot.core.memento import memento_change
from camelot.core.orm import Session
from camelot.core.utils import ugettext, ugettext_lazy as _
from camelot.admin.action import list_action
from camelot.admin.object_admin import ObjectAdmin
from camelot.admin.not_editable_admin import not_editable_admin
from camelot.model.authentication import end_of_times

from .agreement import FinancialAgreement
from .feature import AbstractFeatureApplicability
from .fund import FundDistributionPremiumScheduleAdmin, FinancialAccountFundDistribution
from .notification.premium_schedule_document import PremiumScheduleDocument
from .premium import (FinancialAgreementPremiumSchedule,
                      FinancialAccountPremiumSchedule,
                      FinancialAccountPremiumFulfillment,)
from .feature import FinancialAccountPremiumScheduleFeature
from .package import FinancialBrokerAvailability
from .transaction import (FinancialTransactionAdmin,
                          FinancialTransactionPremiumSchedule,
                          TransactionStatusVerified,
                          FinancialTransaction)
from .summary.premium_summary import FeatureSummary
from .summary.account_summary import (FinancialAccountPremiumScheduleSummary,
                                      FinancialAccountSummary)
from .account import FinancialAccount
from .summary.transaction_summary import FinancialTransactionSummary
from .visitor.abstract import AbstractVisitor
from .visitor.joined import JoinedVisitor
from .visitor.supplier_attribution import distribution_fulfillment_types
from ..bank.accounting import AccountingPeriod
from ..bank.admin import RelatedEntries
from ..bank.constants import commission_receivers
from ..bank.financial_functions import ZERO
from ..bank.statusmixin import BankRelatedStatusAdmin
from ..insurance.account import CoverageOnAccountPremiumScheduleAdmin
from ..financial.security import FinancialSecurityQuotation
from vfinance.model.financial.notification.environment import TemplateLanguage
from ...connector.accounting import (SimulatedAccounting, AccountingSingleton,
                                     UpdateDocumentRequest, LineRequest,
                                     CreateSupplierAccountRequest,
                                     AccountingRequest, DocumentRequest)
# from ..financial.notification.transaction_document import TransactionDocument
from vfinance.supergenerator import supergenerator, _from

possible_durations = [(12, '1 year')] + [(y*12, '%i years'%y) for y in [2, 3, 4, 5, 7, 8, 9, 10]] + [(200*12, 'Forever')]

LOGGER = logging.getLogger( 'vfinance.model.financial.admin' )

class PremiumApplicableFeature(object):
    """A feature applicable to a premium"""

    class Admin(ObjectAdmin):
        list_display = ['described_by', 'value', 'apply_from_date']
        form_display = list_display
        field_attributes = {'value':{'delegate':delegates.FloatDelegate},
                            'apply_from_date':{'delegate':delegates.DateDelegate},}

fees_and_taxes = ['commission_distribution' ]

class CreateSupplier( Action ):

    verbose_name = _('Create Supplier')

    def model_run(self, model_context):
        accounting = AccountingSingleton()
        with accounting.begin(model_context.session):
            for available_broker in model_context.get_selection():
                package = available_broker.available_for
                broker_relation = available_broker.broker_relation
                if (package is None) or (broker_relation is None):
                    continue
                supplier_request = CreateSupplierAccountRequest(
                    from_number = package.from_supplier,
                    thru_number = package.thru_supplier,
                    person_id = broker_relation.natuurlijke_persoon_id,
                    organization_id = broker_relation.rechtspersoon_id,
                    name = broker_relation.name
                )
                accounting.register_request(supplier_request)
                yield action_steps.UpdateObject(available_broker)

FinancialBrokerAvailability.Admin.form_actions.append(CreateSupplier())

class CopyAgreement( Action ):

    verbose_name = _('Copy from')

    def model_run(self, model_context):
        agreement = model_context.get_object()

        class AgreementSearchAdmin(FinancialAgreement.Admin):
            list_actions = []

            def get_query(self):
                query = super(AgreementSearchAdmin, self).get_query()
                query = query.filter(FinancialAgreement.package_id==agreement.package_id)
                query = query.filter(FinancialAgreement.id!=agreement.id)
                return query

        admin = AgreementSearchAdmin(model_context.admin, FinancialAgreement)
        templates = yield action_steps.SelectObjects(admin)
        for template in templates:
            admin.copy(template, agreement)
            yield action_steps.FlushSession(model_context.session)

    def get_state(self, model_context):
        state = super(CopyAgreement, self).get_state(model_context)
        obj = model_context.get_object()
        if obj is not None:
            if (obj.id is not None) and (obj.current_status=='draft'):
                return state
        state.enabled = False
        return state

FinancialAgreement.Admin.form_actions = tuple(itertools.chain(FinancialAgreement.Admin.form_actions, (CopyAgreement(),)))

class Heal( Action ):

    verbose_name = _('Unattribute Entries')

    def unattribute_fulfillement( self, model_context, fulfillment ):
        from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment as FAPF
        yield action_steps.UpdateProgress( text = ugettext('Unattribute {fapf.entry_book_date} {fapf.entry_book} {fapf.entry_document}').format( fapf = fulfillment ) )
        for assoc_fapf in model_context.session.query( FAPF ).filter( sql.and_( FAPF.of == fulfillment.of,
                                                                                FAPF.associated_to == fulfillment ) ).all():
            if assoc_fapf.entry_doc_date != None:
                # There is no good solution for this case.  This means
                # accounting entries are missing but their related entries
                # still exist, and it might no longer be possible to remove
                # those.
                raise UserException( 'Could not continue because of related entries' )
            for step in self.unattribute_fulfillement( model_context, assoc_fapf ):
                yield step
        model_context.session.delete( fulfillment )
        yield action_steps.FlushSession( model_context.session )

    def model_run( self, model_context ):
        from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment as FAPF
        for premium_schedule in model_context.get_selection():
            response = yield action_steps.MessageBox( text = ugettext("""This will permanently remove entries from V-Finance """
                                                                      """for which no Accounting entry has been found. Only proceed """
                                                                      """if you know what you are doing."""),
                                                      title = ugettext('Continue ?'),
                                                      standard_buttons = QtGui.QMessageBox.Yes | QtGui.QMessageBox.No )
            if response == QtGui.QMessageBox.Yes:
                LOGGER.warn( 'heal premium schedule %s'%premium_schedule.id )
                with Session().begin():
                    orphan_fulfillment_query = model_context.session.query( FAPF )
                    orphan_fulfillment_query = orphan_fulfillment_query.filter( sql.and_( FAPF.of == premium_schedule,
                                                                                          FAPF.entry_doc_date == None ) )
                    for fulfillment in orphan_fulfillment_query.all():
                        for step in self.unattribute_fulfillement( model_context, fulfillment ):
                            yield step

class RunBackward(Action):

    verbose_name = _('Run Backward')

    class Options( object ):

        def __init__( self ):
            accounting_period = AccountingPeriod.get_accounting_period_at()
            self.from_document_date = None
            self.thru_document_date = None
            self.from_book_date = accounting_period.from_book_date
            self.thru_book_date = None
            self.reason = None
            self.revert = False

        class Admin( ObjectAdmin ):
            list_display = ['reason', 'from_document_date', 'from_book_date', 'revert']
            field_attributes = {'from_document_date':{'delegate':delegates.DateDelegate,
                                                      'nullable':False,
                                                      'editable':True},
                                'thru_document_date':{'delegate':delegates.DateDelegate,
                                                      'nullable':True,
                                                      'editable':True},
                                'from_book_date':{'delegate':delegates.DateDelegate,
                                                  'nullable':False,
                                                  'editable':True},
                                'thru_book_date':{'delegate':delegates.DateDelegate,
                                                  'nullable':False,
                                                  'editable':True},
                                'reason':{'delegate':delegates.PlainTextDelegate,
                                          'nullable':False,
                                          'length':100,
                                          'editable':True},
                                'revert':{'delegate':delegates.BoolDelegate,
                                          'editable':True}}

    def handle_entries(self, premium_schedule, entries, entry_handler, session, verbose_handler_name):

        accounting_connector = AccountingSingleton()

        purchase_entries = [e for e in entries if e.fulfillment_type in distribution_fulfillment_types]
        sales_entries = [e for e in entries if e.fulfillment_type not in distribution_fulfillment_types+['premium_attribution']]

        for description, entries_to_remove in [
            ('purchase', purchase_entries),
            ('sales', sales_entries)]:
            yield action_steps.UpdateProgress(detail='Handle {0} {1} lines {2}'.format(len(entries_to_remove), description, verbose_handler_name))
            with accounting_connector.begin(session):
                yield action_steps.UpdateProgress(text='Look for associated documents')
                for step in entry_handler(premium_schedule, entries_to_remove):
                    if isinstance(step, AccountingRequest):
                        yield accounting_connector.register_request(step)
                        yield action_steps.UpdateProgress(detail=unicode(step))

    @supergenerator
    def run_premium_schedule_backward( self, premium_schedule, options ):
        """Undo all transactions until the doc date
        """

        session = Session()
        session.expire_all()

        visitor = AbstractVisitor(session=session)
        accounting_period = AccountingPeriod.get_accounting_period_at()

        yield action_steps.UpdateProgress(text = 'Process documents in accounting period')
        entries_in_accounting_period = list(visitor.get_entries(
            premium_schedule,
            from_book_date = max(options.from_book_date, accounting_period.from_book_date),
            thru_book_date = options.thru_book_date,
            from_document_date = max(options.from_document_date, accounting_period.from_doc_date),
            thru_document_date = options.thru_document_date))
        for step in self.handle_entries(premium_schedule,
                                        entries_in_accounting_period,
                                        visitor.create_remove_request,
                                        session,
                                        u'to remove'):
            yield step
        yield action_steps.UpdateProgress(text = 'Process documents outside accounting period')
        entries_out_accounting_period = list(itertools.ifilter(
            lambda entry: entry.fulfillment_type != 'premium_attribution',
            visitor.get_entries(
            premium_schedule,
            from_book_date = options.from_book_date,
            thru_book_date = options.thru_book_date,
            from_document_date = options.from_document_date,
            thru_document_date = options.thru_document_date)))
        if len(entries_out_accounting_period) and (options.revert == False):
            raise UserException('Cannot continue removing bookings before the accounting period')
        for step in self.handle_entries(premium_schedule,
                                        entries_out_accounting_period,
                                        visitor.create_revert_request,
                                        session,
                                        'to revert'):
            yield step

    @supergenerator
    def model_run( self, model_context ):
        from .premium import FinancialAccountPremiumSchedule
        options = self.Options()
        yield action_steps.ChangeObject( options )
        admin = model_context.admin
        memento = admin.get_memento()
        for i, obj in enumerate( model_context.get_selection() ):
            if isinstance(obj, FinancialAccountPremiumSchedule):
                premium_schedule = obj
            elif isinstance(obj, FinancialAccountFundDistribution):
                premium_schedule = obj.distribution_of
            memento.register_changes( [memento_change( model = unicode( admin.entity.__name__ ),
                                                       primary_key = admin.primary_key( premium_schedule ),
                                                       previous_attributes = {'reason':options.reason,
                                                                              'thru_document_date':options.thru_document_date},
                                                       memento_type = 'run backward' )] )
            yield action_steps.UpdateProgress( i, model_context.selection_count, text = unicode( premium_schedule ) )
            yield _from( self.run_premium_schedule_backward( premium_schedule, options) )
        yield action_steps.UpdateProgress(detail=u'Finished', blocking=True)

FinancialAccountFundDistribution.Admin.list_actions.append(RunBackward())

class RunForward( RunBackward ):

    verbose_name = _('Run Forward')

    class Options(RunBackward.Options):

        def __init__(self):
            RunBackward.Options.__init__(self)
            self.from_document_date = datetime.date(2000, 1, 1)
            self.thru_document_date = datetime.date.today()

        class Admin(RunBackward.Options.Admin):
            list_display = ['from_document_date', 'thru_document_date']
            field_attributes = RunBackward.Options.Admin.field_attributes.copy()
            field_attributes['thru_document_date']['nullable'] = False

    def model_run( self, model_context ):
        for step in self.run_forward(model_context.get_selection(),
                                     model_context.selection_count,
                                     model_context):
            yield step

    def run_forward(self, premium_schedule_iterator, premium_schedule_count, model_context=None, options=None):
        """
        :param model_context: the model context of the action that triggered the run of this method.  if there
            is no model context, no user action log will be created
        """
        from .premium import FinancialAccountPremiumSchedule
        options = self.Options()
        yield action_steps.ChangeObject( options )
        if options.thru_document_date >= ( datetime.date.today() + datetime.timedelta( days = 7 ) ):
            raise UserException( _('Unable to run forward that far in the future') )
        visitor = JoinedVisitor()
        memento = None
        if model_context is not None:
            premium_schedule_admin = model_context.admin.get_related_admin(FinancialAccountPremiumSchedule)
            memento = premium_schedule_admin.get_memento()
        last_visit = None
        for i, premium_schedule in enumerate( premium_schedule_iterator ):
            if memento is not None:
                memento.register_changes( [memento_change( model = unicode( premium_schedule_admin.entity.__name__ ),
                                                           primary_key = premium_schedule_admin.primary_key( premium_schedule ),
                                                           previous_attributes = {'reason':options.reason,
                                                                                  'from_document_date':options.from_document_date,
                                                                                  'thru_document_date':options.thru_document_date},
                                                           memento_type = 'run forward' )] )
            yield action_steps.UpdateProgress( i, premium_schedule_count, text = unicode( premium_schedule ) )
            for visit in visitor.run_visitors([premium_schedule.id],
                                              options.from_document_date,
                                              options.thru_document_date,
                                              datetime.date.today()):
                if visit is not None:
                    last_visit = visit
                    yield action_steps.UpdateProgress(detail=unicode(visit))
        if last_visit is not None:
            yield action_steps.UpdateProgress(blocking=True)

class RunTransactionSimulation(FinancialTransactionSummary):

    verbose_name = _('Simulation')

    def get_anticipated_quotations(self, transaction, funds, min_date, session):
        anticipated_quotations = {}
        new_quotations = []
        for fund in funds:
            quotation = fund.fund.get_quotation_at(transaction.from_date)
            from_date = min_date \
                + datetime.timedelta(days=max((fund.fund.sales_delay, fund.fund.purchase_delay))) \
                + datetime.timedelta(days=1)
            from_datetime = datetime.datetime.combine(from_date,
                                                        datetime.time(0, 0))
            if quotation is None:
                quotation = FinancialSecurityQuotation()
                quotation.from_datetime = from_datetime
                quotation.purchase_date = from_date - datetime.timedelta(days=fund.fund.purchase_delay)
                quotation.sales_date = from_date - datetime.timedelta(days=fund.fund.sales_delay)
                quotation.value = fund.fund.last_quotation_value
                quotation.financial_security = fund.fund
                quotation.financial_security_id = fund.fund.id
                new_quotations.append(quotation)

            session.expunge(quotation)

            if (fund.fund.id, quotation.from_date) not in anticipated_quotations:
                anticipated_quotations[(fund.fund.id, quotation.from_date)] = quotation
        return anticipated_quotations

    def model_run(self,
                  model_context):

        selected_transactions = []

        for i, transaction in enumerate(model_context.get_selection()):
            selected_transactions.append(transaction)
            yield action_steps.UpdateProgress(i, model_context.selection_count)

        for step in self.simulate_transactions(model_context, selected_transactions, model_context.session):
            yield step

    def simulate_transactions(self, model_context, selected_transactions, session):
        transaction_quotations = {}
        transaction_status_verified = TransactionStatusVerified()

        if (len(selected_transactions) > 0):
            for i, transaction in enumerate(selected_transactions):
                if not isinstance(transaction, FinancialTransaction):
                    transaction = transaction._transaction
                anticipated_quotations = {}
                for schedule in transaction.consisting_of:
                    out_funds = []
                    in_funds = []
                    if schedule.quantity >= 0:
                        in_funds = schedule.get_fund_distribution()
                    else:
                        out_funds = schedule.get_fund_distribution()

                    anticipated_quotations.update(self.get_anticipated_quotations(transaction, out_funds, min_date=transaction.from_date, session=session))
                    last_quot_out_from_date = max([q.from_datetime.date() for q in anticipated_quotations.values()] + [transaction.from_date])
                    anticipated_quotations.update(self.get_anticipated_quotations(transaction, in_funds, min_date=last_quot_out_from_date, session=session))
                    transaction_quotations[transaction.id] = anticipated_quotations

                yield action_steps.UpdateProgress(i, len(selected_transactions))

            # get quotations out of session
            all_anticipated_quotations = {}
            for tr in transaction_quotations.values():
                all_anticipated_quotations.update(tr.items())

            if len(all_anticipated_quotations) > 0:
                change_objects = action_steps.ChangeObjects(sorted(all_anticipated_quotations.values(),
                                                            key=lambda quot: quot.financial_security.name),
                                                            model_context.admin.get_related_admin(FinancialSecurityQuotation),
                                                            )
                change_objects.window_title=_('Anticipated Quotations')
                change_objects.title=_('Anticipated quotations for the simulated transaction')
                change_objects.subtitle=_('Please check the anticipated quotations for the simulated transaction and correct where necessary')
                yield change_objects

            try:
                # only begin db transaction here
                session.begin()

                merged_quotations = []
                for quotation in all_anticipated_quotations.values():
                    # merging the quotation will fire set_status event, and set the
                    # status to draft
                    merged_quotations.append(session.merge(quotation))

                # flush the session to make sure the draft status has an id, smaller
                # then the verified status
                session.flush()
                for merged_quotation in merged_quotations:
                    if merged_quotation.current_status != 'verified':
                        merged_quotation.change_status('verified')

                # set transaction to verified if this is not the case
                for transaction in selected_transactions:
                    if transaction.current_status != 'verified':
                        transaction_status_verified.before_status_change(model_context, transaction)
                        transaction.change_status('verified')
                        transaction_status_verified.after_status_change(model_context, transaction)

                session.flush()
                visitor = JoinedVisitor(accounting_connector=SimulatedAccounting())
                last_visit = None

                for i, transaction in enumerate(selected_transactions):
                    quotation_dates = [q.from_datetime.date() for q in transaction_quotations[transaction.id].values()]
                    end_date = max(quotation_dates + [transaction.from_date])
                    premium_schedules = set(ftps.premium_schedule for ftps in transaction.consisting_of)
                    for ps in premium_schedules:
                        for visit in visitor.run_visitors([ps.id],
                                                          ps.valid_from_date,
                                                          end_date,
                                                          end_date):
                            if visit is not None:
                                last_visit = visit
                                yield action_steps.UpdateProgress(i, len(selected_transactions), detail=unicode(visit))
                                if isinstance(visit, DocumentRequest):
                                    for line in visit.lines:
                                        # __unicode__ is not used due to slots
                                        yield action_steps.UpdateProgress(i, len(selected_transactions), detail=LineRequest.__unicode__(line))

                # gather context of document
                contexts = []
                for transaction in selected_transactions:
                    contexts.append(self.get_context(transaction, None, None))

                # rollback transaction here
                yield action_steps.UpdateProgress(text='Remove simulation data')
                session.rollback()

                if last_visit is not None:
                    yield action_steps.UpdateProgress(blocking=True)

                # generate document for each transaction
                self.invalidating_text = u'Simulation'
                for context in contexts:
                    context['invalidating_text'] = u'Simulation'
                    context['date'] = datetime.datetime.now()
                    context['title'] = super(RunTransactionSimulation, self).verbose_name
                    with TemplateLanguage():
                        yield action_steps.PrintJinjaTemplate('transaction.html',
                                                              context=context)

            finally:
                session.rollback()

class RunAgreementForward( RunForward ):

    @supergenerator
    def model_run(self, model_context):
        from .open_entries import AttributePendingPremiums
        attribute_pending_premiums = AttributePendingPremiums()
        #
        # first try to transition the agreed schedule to an account schedule
        #
        premium_schedule_ids = set()
        for i, agreement in enumerate(model_context.get_selection()):
            yield action_steps.UpdateProgress(i, model_context.selection_count, text='Run agreements forward')
            yield _from(self.run_agreement_forward([agreement], model_context.session))
            for agreed_schedule in agreement.invested_amounts:
                for premium_schedule in agreed_schedule.fulfilled_by:
                    premium_schedule_ids.add(premium_schedule.id)
        #
        # next, attribute pending premiums to the agreements
        #
        premium_schedule_query = model_context.session.query(FinancialAccountPremiumSchedule)
        premium_schedule_query = premium_schedule_query.filter(FinancialAccountPremiumSchedule.id.in_(list(premium_schedule_ids)))
        yield _from(attribute_pending_premiums.attribute_pending_premiums(premium_schedule_query, model_context.session, model_context))
        yield action_steps.UpdateProgress(detail='Finished', blocking=True)

    def run_agreement_forward(self, agreement_iterator, session):
        """
        Try to transition the agreed schedule to an account schedule
        """
        for agreement in agreement_iterator:
            yield action_steps.UpdateProgress(detail=u'{0.code} : evaluate agreement {0.id}'.format(agreement))
            with session.begin():
                if agreement.current_status != 'verified':
                    yield action_steps.UpdateProgress(detail='{0.code} - not yet verified, current status is {0.current_status}'.format(agreement))
                    continue
                if not agreement.is_fulfilled():
                    if not agreement.amount_on_hold:
                        yield action_steps.UpdateProgress(detail='{0.code} - no pending entries'.format(agreement))
                    else:
                        yield action_steps.UpdateProgress(detail='{0.code} - agreed amounts not yet fulfilled'.format(agreement))
                    continue
                agreement_query = session.query(FinancialAgreement)
                agreement_query = agreement_query.filter(FinancialAgreement.id==agreement.id)
                agreement_query = agreement_query.filter(FinancialAgreement.account_id==None)
                agreement_query = agreement_query.with_lockmode('update')
                for agreement in agreement_query.all():
                    account = FinancialAccount.create_account_from_agreement(agreement)
                    yield action_steps.FlushSession(session)
                    yield action_steps.UpdateProgress(detail='{0.code} - account {1.id} created'.format(agreement, account))
                agreed_schedule_query = session.query(FinancialAgreementPremiumSchedule)
                # make the order of construction of premium schedules deterministic
                agreed_schedule_query = agreed_schedule_query.order_by(FinancialAgreementPremiumSchedule.id)
                agreed_schedule_query = agreed_schedule_query.filter(FinancialAgreementPremiumSchedule.financial_agreement==agreement)
                agreed_schedule_query = agreed_schedule_query.filter(FinancialAgreementPremiumSchedule.fulfilled==0)
                agreed_schedule_query = agreed_schedule_query.with_lockmode('update')
                for agreed_schedule in agreed_schedule_query.all():
                    premium_schedule = agreed_schedule.create_premium()
                    yield action_steps.UpdateProgress(detail='{0.code} - premium schedule {1.valid_from_date} {1.premium_amount} {1.account_number} created'.format(agreement, premium_schedule))
                yield action_steps.FlushSession(session)

    def get_state(self, model_context):
        state = Action.get_state(self, model_context)
        for obj in model_context.get_selection():
            if obj is None:
                state.enabled = False
                break
            if obj.current_status != 'verified':
                state.enabled = False
                break
        return state

FinancialAgreement.Admin.list_actions = tuple(itertools.chain(FinancialAgreement.Admin.list_actions, (RunAgreementForward(),)))
FinancialAgreement.Admin.form_actions = tuple(itertools.chain(FinancialAgreement.Admin.form_actions, (RunAgreementForward(),)))

class CloseAccount( Action ):

    verbose_name = _('Close Accounts')

    def model_run( self, model_context ):
        from ..bank.entry import Entry
        from .account import FinancialAccount
        from .premium import FinancialAccountPremiumSchedule
        from .transaction import ( FinancialTransactionPremiumSchedule,
                                   FinancialTransaction )
        from .visitor.abstract import ( AbstractVisitor,
                                        FinancialBookingAccount )

        class CloseException( Exception ):
            pass

        today = datetime.date.today()
        visitor = AbstractVisitor()
        entry_total = sql.select( [ sql.func.sum( Entry.amount ),
                                    sql.func.sum( Entry.quantity ), ] )

        accounts_to_close = set()

        if isinstance( model_context, ApplicationActionModelContext ):
            offset = datetime.date.today() - datetime.timedelta( days = 140 )
            query = model_context.session.query( FinancialAccount )
            query = query.join( FinancialAccountPremiumSchedule,
                                FinancialTransactionPremiumSchedule,
                                FinancialTransaction
                                )
            query = query.filter( FinancialTransaction.transaction_type == 'full_redemption' )
            query = query.filter( FinancialTransaction.current_status == 'verified' )
            query = query.filter( FinancialAccount.current_status == 'active' )
            query = query.filter( FinancialTransaction.from_date <= offset )
            selection_count = query.count()
            selection = query.yield_per(10)
        else:
            selection_count = model_context.selection_count
            selection = model_context.get_selection()
        for i, account in enumerate( selection ):
            yield action_steps.UpdateProgress( i,
                                               selection_count,
                                               'Evaluate account {0.id}'.format( account ) )
            with model_context.session.begin():
                try :
                    for ps in account.premium_schedules:
                        product = ps.product
                        excluded_books = [ product.external_application_book,
                                           product.accounting_year_transfer_book ]

                        booking_accounts = [ FinancialBookingAccount('uninvested'),
                                             FinancialBookingAccount('financed_commissions') ]
                        for fund_distribution in ps.fund_distribution:
                            booking_accounts.append( FinancialBookingAccount('fund', fund = fund_distribution.fund) )
                        for booking_account in booking_accounts:
                            booking_account_number = booking_account.booking_account_number_at( ps, today )
                            vf_totals = list( visitor.get_total_amount_until( ps, account = booking_account ) )
                            ps_entry_total = entry_total.where( Entry.account == booking_account_number )
                            for excluded_book in excluded_books:
                                if excluded_book != None:
                                    ps_entry_total = ps_entry_total.where( Entry.venice_book != excluded_book )
                            accounting_totals = list( model_context.session.execute( ps_entry_total ).first().values() )
                            for total in vf_totals:
                                if total not in  (ZERO, None):
                                    raise CloseException('Account {} has non zero value in V-Finance {}'.format( booking_account_number, total ) )
                            for total in accounting_totals:
                                if total not in  (ZERO, None):
                                    raise CloseException('Account {} has non zero value in accounting {}'.format( booking_account_number, total ) )
                    accounts_to_close.add( account )
                    yield action_steps.UpdateProgress( i, selection_count )
                except CloseException as e:
                    yield action_steps.UpdateProgress( i, selection_count, detail = unicode( e ) )

        # wait for user to review the details
        yield action_steps.UpdateProgress( 99, 100, text=_('Press OK to continue'), blocking=True )

        accounts_to_close = list( accounts_to_close )

        class CloseAccountAdmin( ObjectAdmin ):
            list_display = ['id', 'package_name', 'account_suffix', 'subscriber_1', 'subscriber_2']

            def get_related_toolbar_actions( self, toolbar_area, direction ):
                return [list_action.RemoveSelection()]

        close_account_admin = CloseAccountAdmin( model_context.admin, FinancialAccount )

        yield action_steps.ChangeObjects( accounts_to_close, close_account_admin )
        yield action_steps.UpdateProgress( clear_details=True )
        for i, account in enumerate( accounts_to_close ):
            with model_context.session.begin():
                yield action_steps.UpdateProgress( i,
                                                   len( accounts_to_close ),
                                                   'close account {0.id}'.format( account ) )
                account.change_status('closed')
                yield action_steps.UpdateObject(account)

class PremiumToPending( Action ):
    """
    Remove a FinancialAccountPremiumFulfillment for a premium that was pending
    """

    verbose_name = _('To pending')

    def model_run( self, model_context ):
        yield action_steps.FlushSession( model_context.session )
        model_context.session.expire_all()

        accounting = AccountingSingleton()
    
        for fulfillment in list( model_context.get_selection() ):
            if fulfillment.fulfillment_type != 'premium_attribution':
                raise UserException( 'Only premium attribution entries can be moved to the pending premiums account' )

            premium_schedule = fulfillment.of
            product = premium_schedule.product
            pending_premiums_account = product.get_account_at( 'pending_premiums',
                                                               fulfillment.entry_book_date )

            with accounting.begin(model_context.session):
                request = UpdateDocumentRequest(
                    book_date = fulfillment.entry_book_date,
                    book = fulfillment.entry_book,
                    document_number = fulfillment.entry_document,
                    lines = [LineRequest(
                        line_number = fulfillment.entry_line_number,
                        amount = fulfillment.amount,
                        quantity = fulfillment.quantity,
                        account = pending_premiums_account
                    )]
                    )
                accounting.register_request(request)
                model_context.session.delete(fulfillment)
            
            yield action_steps.UpdateObject(fulfillment)

FinancialAccountPremiumFulfillment.Admin.list_actions = [PremiumToPending()]


class FinancialAccountPremiumScheduleFeatureOnAccountAdmin(
                FinancialAccountPremiumScheduleFeature.Admin):
    list_display = AbstractFeatureApplicability.Admin.list_display

class FinancialAccountPremiumScheduleAdmin(BankRelatedStatusAdmin):
    verbose_name = _('Premium Schedule')
    verbose_name_plural = _('Premium Schedules')
    list_display = [ 'id', 'full_account_number', 'financial_account_id', 'product_name', 'account_suffix', 'rank', 'premium_amount', 'period_type',
                     table.ColumnGroup( _('Subscribers'), ['subscriber_1', 'subscriber_2', 'agreement_code'] ),
                     table.ColumnGroup( _('Dates'), ['valid_from_date', 'valid_thru_date', 'payment_thru_date',] ) ]
    list_search = ['account_suffix', 'subscriber_1', 'agreement_code']
    list_filter = [list_filter.ComboBoxFilter('product_name'),
                   list_filter.EditorFilter('account_suffix'),
                   list_filter.ComboBoxFilter('account_status'),
                   list_filter.EditorFilter('agreement_code'),
                   'unit_linked',
                   list_filter.ComboBoxFilter('period_type'),
                   ]
    form_display = forms.TabForm( [(_('Premium'), forms.Form(['product', 'premium_amount', 'full_account_number', 'period_type', 'increase_rate', 'direct_debit', 'valid_from_date', 'valid_thru_date',
                                                              'payment_thru_date',
                                                              'acceptance_post_date', 'end_of_cooling_off'], columns=2)),
                                   (_('Insurance'), ['applied_coverages']),
                                   (_('Fees and taxes'), ['commission_distribution'] ),
                                   #(_('Entries'), ['fulfilled_by']),
                                   (_('Features'), ['applied_features', 'applicable_features']),
                                   (_('Funds'), ['unit_linked', 'fund_distribution', 'earliest_investment_date',]),
                                   (_('Invoices'), ['invoice_items', 'premiums_invoicing_due_amount', 'premiums_invoiced_amount']),
                                   (_('Transactions'), ['transactions']),
                                   ] )

    field_attributes = {'fulfilled_by':{'name':_('Entries')},
                        'rank':{'editable':False},
                        'applied_features':{'admin':FinancialAccountPremiumScheduleFeatureOnAccountAdmin},
                        'premium_amount':{'delegate':delegates.CurrencyDelegate},
                        'premiums_attributed_to_customer':{'delegate':delegates.IntegerDelegate, 'editable':False, 'name':_('Premiums to customer')},
                        'premiums_attributed_to_account':{'delegate':delegates.IntegerDelegate, 'editable':False, 'name':_('Premiums to account')},
                        'premiums_invoiced_amount':{'editable':False,},
                        'premiums_invoicing_due_amount':{'delegate':delegates.IntegerDelegate, 'editable':False,},
                        'acceptance':{'editable':False},
                        'transactions':{'editable':False},
                        'agreement_code':{'editable':False},
                        'applicable_features':{'editable':False, 'delegate':delegates.One2ManyDelegate, 'python_type':list, 'target':PremiumApplicableFeature},
                        # these fields should be editable to allow importing premium
                        # schedules
                        'product_id': {'editable':True},
                        'agreed_schedule_id': {'editable':True},
                        'financial_account_id': {'editable':True},
                        'applied_coverages': {'admin': CoverageOnAccountPremiumScheduleAdmin},
                        'fund_distribution': {'admin': FundDistributionPremiumScheduleAdmin},
                        }
    form_actions = [
        FinancialAccountPremiumScheduleSummary( ),
        PremiumScheduleDocument( ),
        FeatureSummary( ),
        CallMethod(_('Fund Accounts'), lambda obj:obj.button_create_fund_accounts(), ),
        RunForward(),
        RunBackward(),
        CallMethod(_('Create Invoice'), lambda obj:obj.button_create_invoice_item(),),
        Heal(),
        RelatedEntries(FinancialAccountPremiumFulfillment),
    ]
    list_actions = [
        RunForward(),
        RunBackward(),
        Heal(),
    ]
    form_size = (1100, 700)
    #disallow_delete = True

    def get_related_status_object(self, obj):
        return obj.financial_account

class FinancialAccountPremiumScheduleOnAccountAdmin(FinancialAccountPremiumScheduleAdmin):
    list_display = ['rank', 'full_account_number', 'premium_amount', 'period_type', 'direct_debit', 'valid_from_date', 'valid_thru_date', 'payment_thru_date', 'agreement_code']

FinancialAccountPremiumSchedule.Admin = FinancialAccountPremiumScheduleOnAccountAdmin

def available_products( premium_schedule ):
    products = [(None, '')]
    agreement = premium_schedule.financial_agreement
    if agreement and agreement.package and agreement.agreement_date:
        for product in agreement.package.get_available_products_at( agreement.agreement_date ):
            products.append( ( product, product.name ) )
    return products

class FinancialAgreementPremiumScheduleAdmin(BankRelatedStatusAdmin):
    verbose_name = _('Invested Amount')
    list_display = [ 'financial_agreement', 'product', 'duration', 'payment_duration',
                     'amount', 'increase_rate', 'direct_debit', 'current_status_sql', 'fulfilled',]
    form_display = forms.TabForm( [(_('Premium'), [ 'financial_agreement', 'product', 'duration', 'payment_duration',
                                                    'amount', 'increase_rate', 'period_type', 'direct_debit', 'fulfilled']),
                                   (_('Insurance'), ['agreed_coverages']),
                                   (_('Fees, Taxes and Commissions'), fees_and_taxes),
                                   (_('Features'), ['agreed_features']),
                                   # (_('Funds'), ['fund_distribution', 'funds_target_percentage_total',]),
                                   (_('Funds'), ['fund_distribution']),
                                   (_('Account'), ['fulfilled_by']),
                                   ])
    field_attributes = {'duration':{'delegate':delegates.MonthsDelegate,},
                        'payment_duration':{'delegate':delegates.MonthsDelegate,},
                        'product':{'choices':available_products},
                        'increase_rate':{'suffix':'% per period'},
                        'current_status':{'name':_('Current status'), 'editable':False},
                        'fulfilled':{'delegate':delegates.BoolDelegate, 'editable':False},
                        'amount':{'minimum':0, 'delegate':delegates.CurrencyDelegate},
                        'applicable_features':{'editable':False, 'delegate':delegates.One2ManyDelegate, 'python_type':list, 'target':PremiumApplicableFeature},}
    list_filter = ['current_status_sql',]
    form_actions = [
        CallMethod( _('Default Features'),
                    lambda obj:obj.button_default_features(),
                    enabled = lambda obj:obj.financial_agreement and obj.financial_agreement.current_status in ['draft', 'incomplete'] and obj.product!=None),
        CallMethod(
            _('Calc Payment Duration'),
            lambda obj:obj.button_calc_optimal_payment_duration(),
            enabled = lambda obj:obj.financial_agreement and obj.financial_agreement.current_status in ['draft', 'incomplete'] and obj.duration \
                                 and obj.product!=None
        ),
        CallMethod(
            _('Calc Credit Insurance'),
            lambda obj:obj.button_calc_credit_insurance_premium(),
            enabled = lambda obj:obj.financial_agreement and obj.financial_agreement.current_status in ['draft', 'incomplete'] \
                                 and obj.product!=None and obj.has_fully_specified_credit_insurance() \
                                 and obj.financial_agreement.has_insured_party()
        ),
        FeatureSummary(),
    ]
    form_size = (1100, 700)
    #disallow_delete = True

    def flush(self, premium_schedule):
        from commission import FinancialAgreementCommissionDistribution
        from constants import commission_types
        if not len(premium_schedule.commission_distribution):
            for type in commission_types:
                for recipient in commission_receivers:
                    premium_schedule.commission_distribution.append( FinancialAgreementCommissionDistribution(described_by=type[1], distribution=0, recipient=recipient[1]) )
        EntityAdmin.flush( self, premium_schedule )

    def get_related_status_object(self, obj):
        return obj.financial_agreement

FinancialAgreementPremiumSchedule.Admin = FinancialAgreementPremiumScheduleAdmin

class FinancialAgreementPremiumScheduleOnAgreementAdmin(FinancialAgreementPremiumScheduleAdmin):
    list_display = ['product', 'duration', 'amount', 'period_type', 'direct_debit', 'fulfilled']
    form_display = deepcopy( FinancialAgreementPremiumScheduleAdmin.form_display )
    form_display.remove_field( 'financial_agreement' )

    def get_depending_objects(self, obj):
        if obj.financial_agreement:
            yield obj.financial_agreement

FinancialAgreementPremiumScheduleAdmin = not_editable_admin(FinancialAgreementPremiumScheduleAdmin)
FinancialAgreement.Admin.field_attributes['invested_amounts']['admin'] = FinancialAgreementPremiumScheduleOnAgreementAdmin

class InitiateTransaction(FinancialAccountSummary):
    """
    Create a new financial transaction with some guidance
    """

    verbose_name = _('New Transaction')
    icon = None

    def model_run( self, model_context ):
        from .transaction import ( FinancialTransaction,
                                   FinancialTransactionAdmin,
                                   FinancialTransactionPremiumSchedule,
                                   FinancialTransactionCreditDistribution )

        options = FinancialAccountPremiumScheduleSummary.Options()

        for account in model_context.get_selection():

            for step in super( InitiateTransaction, self ).model_run( model_context, options, account = account ):
                yield step

            class InitialTransactionAdmin( FinancialTransactionAdmin ):
                form_display = [ 'agreement_date', 'from_date',
                                 'code', 'transaction_type']
                form_actions = []
                form_state = None

            initial_transaction_admin = InitialTransactionAdmin( model_context.admin,
                                                                 FinancialTransaction )

            class InitialDistributionAdmin( FinancialTransactionCreditDistribution.Admin ):
                form_display = [ 'bank_identifier_code', 'iban']

            initial_distribution_admin = InitialDistributionAdmin( model_context.admin,
                                                                   FinancialTransactionCreditDistribution )

            transaction = FinancialTransaction( transaction_type = 'full_redemption' )
            transaction.period_type = 'single'
            transaction.thru_date = end_of_times()
            for premium_schedule in account.premium_schedules:
                transaction.code = premium_schedule.agreed_schedule.financial_agreement.code
                break

            try:
                yield action_steps.ChangeObject( transaction, initial_transaction_admin )
                if transaction.transaction_type in ('full_redemption', 'partial_redemption'):
                    distribution = FinancialTransactionCreditDistribution( financial_transaction = transaction,
                                                                           described_by = 'percentage',
                                                                           quantity = 100 )
                    yield action_steps.ChangeObject( distribution, initial_distribution_admin )
                if transaction.transaction_type == 'full_redemption':
                    for premium_schedule in account.premium_schedules:
                        FinancialTransactionPremiumSchedule( within = transaction,
                                                             premium_schedule = premium_schedule,
                                                             described_by = 'percentage',
                                                             quantity = -100 )
                yield action_steps.FlushSession( model_context.session )
                if transaction.note == None and transaction.transaction_type == 'full_redemption':
                    response = yield action_steps.MessageBox( text = ugettext("""All conditions to complete this transaction are met. """
                                                                              """Complete it now ?"""),
                                                              title = ugettext('Complete'),
                                                              standard_buttons = QtGui.QMessageBox.Yes | QtGui.QMessageBox.No )
                    if response == QtGui.QMessageBox.Yes:
                        transaction.change_status( 'complete' )

                        raise StopIteration
                yield action_steps.OpenFormView( [transaction], model_context.admin.get_related_admin( FinancialTransaction ) )
            except CancelRequest:
                model_context.session.expunge( transaction )

class RunBackTransaction( RunBackward ):
    """Run all premium schedules related to a transaction back"""

    tooltip = _('Run backward till from date')

    @supergenerator
    def model_run( self, model_context ):
        for transaction in model_context.get_selection():
            options = self.Options()
            options.from_document_date = transaction.from_date
            for ftps in transaction.consisting_of:
                yield _from(self.run_premium_schedule_backward(ftps.premium_schedule,
                                                               options))


class RunForwardTransaction( RunForward ):

    def model_run(self, model_context):
        for step in self.run_forward((ftps.premium_schedule for transaction in model_context.get_selection() for ftps in transaction.consisting_of),
                                     model_context.selection_count,
                                     model_context):
            yield step

FinancialTransactionAdmin.list_actions = tuple(itertools.chain(
    FinancialTransactionAdmin.list_actions, [
    RunTransactionSimulation(),
    RunBackTransaction(),
    RunForwardTransaction(),
    ]))

FinancialTransactionAdmin.form_actions = tuple(itertools.chain(
    FinancialTransactionAdmin.form_actions, [
    RunTransactionSimulation(),
    RunBackTransaction(),
    RunForwardTransaction(),
    ]))

FinancialTransactionPremiumSchedule.Admin.field_attributes.update({
    'premium_schedule':{'admin':FinancialAccountPremiumScheduleAdmin}
    })
