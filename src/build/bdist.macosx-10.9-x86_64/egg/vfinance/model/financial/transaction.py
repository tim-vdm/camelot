import collections
import datetime
import decimal
from decimal import Decimal as D
import logging
import math
import os

logger = logging.getLogger('vfinance.model.financial.transaction')

import sqlalchemy.types
import camelot.types

from sqlalchemy import sql, orm, schema

from camelot.core.qt import Qt

from camelot.core.orm import ( Entity, OneToMany, ManyToOne,
                               using_options, ColumnProperty )
from camelot.model.authentication import end_of_times
from camelot.admin.action import Action, list_action
from camelot.admin.object_admin import ObjectAdmin
from camelot.view import forms, action_steps
from camelot.view.controls import delegates
from camelot.core.utils import ugettext_lazy as _, ugettext
from camelot.core.exception import UserException
from camelot.model.type_and_status import Status

from ..bank.statusmixin import (BankStatusMixin,
                                StatusDraft,
                                StatusComplete,
                                StatusVerified,
                                StatusIncomplete,
                                StatusCancel,
                                BankStatusAdmin,
                                BankRelatedStatusAdmin,
                                )
from ..bank import validation
from ..bank.admin import CodeValidator
from ..bank.financial_functions import ONE
from vfinance.admin.vfinanceadmin import VfinanceAdmin
from vfinance.model.financial.account import FinancialAccount
from .premium import (FinancialAccountPremiumSchedule,
                      financial_account_premium_schedule_table,
                      FinancialAccountPremiumScheduleHistory)
from .security import FinancialSecurity
from .security_order import FinancialSecurityOrderLine
from vfinance.model.financial.summary.account_summary import FinancialTransactionAccountsSummary
from vfinance.model.financial.summary.transaction_summary import FinancialTransactionSummary
from vfinance.model.financial.summary.transaction_verification import TransactionVerificationForm
from vfinance.model.financial.notification.transaction_document import TransactionDocument
from vfinance.model.financial.notification.account_document import FinancialTransactionAccountDocument
from vfinance.model.bank.direct_debit import AbstractBankAccount, IbanBicMixin

from constants import transaction_statuses, period_types, transaction_types
from constants import transaction_distribution_type_suffix, transaction_distribution_type_enumeration
from constants import transaction_distribution_type_precision

FSOL = FinancialSecurityOrderLine

class BulkTransactionOptions( object ):

    def __init__( self ):
        self.from_fund = None
        self.to_fund = None
        self.units_at = None
        self.amount_per_unit = 0

    class Admin( ObjectAdmin ):
        list_display = ['from_fund', 'to_fund', 'units_at', 'amount_per_unit']
        field_attributes = {
            'from_fund' : {'editable':True,
                           'nullable':False,
                           'target':FinancialSecurity,
                           'delegate':delegates.Many2OneDelegate},
            'to_fund' : {'editable':True,
                         'nullable':False,
                         'target':FinancialSecurity,
                         'delegate':delegates.Many2OneDelegate},
            'units_at' : {'editable':True,
                          'nullable':False,
                          'delegate':delegates.DateDelegate},
            'amount_per_unit' : {'editable':True,
                                 'nullable':False,
                                 'precision':6,
                                 'delegate':delegates.FloatDelegate},
        }


class BulkTransaction( Action ):
    """Wizard to issue a transaction on multiple premium schedules at once"""

    verbose_name = _('Bulk')

    def model_run( self, model_context ):
        from vfinance.model.financial.visitor.abstract import AbstractVisitor
        from vfinance.model.financial.fund import FinancialAccountFundDistribution, FinancialTransactionFundDistribution
        visitor = AbstractVisitor()
        for transaction in model_context.get_selection():
            if not transaction.id:
                raise UserException( 'Please fill in the from date and the code first' )
            options = BulkTransactionOptions()
            options.units_at = transaction.from_date
            yield action_steps.ChangeObject( options )
            query = model_context.session.query( FinancialAccountPremiumSchedule, FinancialAccountFundDistribution )
            query = query.filter( FinancialAccountFundDistribution.fund == options.from_fund )
            query = query.filter( FinancialAccountPremiumSchedule.id == FinancialAccountFundDistribution.distribution_of_id )
            query = query.distinct( FinancialAccountPremiumSchedule.id )
            count = query.count()
            amount_per_unit = D( options.amount_per_unit )
            #
            # Create premium schedules for a financed switch
            #
            for i, (faps, distribution) in enumerate( query.all() ):
                yield action_steps.UpdateProgress( i, count, text = 'Generate switch amounts' )
                fund_account = distribution.full_account_number
                total_amount, total_units, total_distribution = visitor.get_total_amount_until( faps,
                                                                                                thru_document_date = transaction.from_date,
                                                                                                account = fund_account )
                if total_units > 0:
                    switch_amount = ( total_units * amount_per_unit ).quantize( D('.01'), rounding=decimal.ROUND_DOWN )
                    ftps_out = FinancialTransactionPremiumSchedule( within = transaction,
                                                                    premium_schedule = faps,
                                                                    described_by = 'amount',
                                                                    quantity = -1 * switch_amount )
                    ftps_in = FinancialTransactionPremiumSchedule( within = transaction,
                                                                   premium_schedule = faps,
                                                                   described_by = 'amount',
                                                                   quantity = switch_amount )
                    FinancialTransactionFundDistribution( distribution_of = ftps_out,
                                                          fund = options.from_fund,
                                                          target_percentage = 100 )
                    FinancialTransactionFundDistribution( distribution_of = ftps_in,
                                                          fund = options.to_fund,
                                                          target_percentage = 100 )
                    model_context.session.add( ftps_out )
                    model_context.session.add( ftps_in )
            yield action_steps.UpdateProgress( text = 'Save transaction modifications' )
            yield action_steps.FlushSession( model_context.session )

class AbstractFinancialTransaction( object ):

    @property
    def note(self):
        if not self.from_date:
            return _('Specify the transaction date')
        after_transaction = self.from_date + datetime.timedelta(days=1)
        if not len(self.consisting_of):
            return _('Select the premium schedules on which to apply the transaction')
        if self.transaction_type not in ['profit_attribution']:
            ftps_per_ps = collections.defaultdict(list)
            #
            # Check the version of the premium schedule
            #
            for ftps in self.consisting_of:
                ftps_per_ps[ ftps.premium_schedule ].append( ftps )
                if self.current_status != 'verified':
                    if ftps.previous_version_id != ftps.get_premium_schedule_version_id():
                        return _('Premium schedule has been modified after transaction creation')
                else:
                    if ftps.next_version_id != ftps.get_premium_schedule_version_id():
                        return _('Premium schedule has been modified after transaction verification')
            #
            # Check the distribution
            #
            if self.transaction_type in ['partial_redemption', 'full_redemption']:
                if len(self.distributed_via):
                    percentage_distributions = (cd.quantity for cd in self.distributed_via if cd.described_by=='percentage')
                    sum_percentage = sum(percentage_distributions, 0)
                    if sum_percentage != 100:
                        return _('Redeemed amount should be distributed for 100%')
            for credit_distribution in self.distributed_via:
                if not credit_distribution.is_valid():
                    return _('Invalid credit distribution')
            #
            # Check the transaction premium schedules
            #
            if self.transaction_type == 'partial_redemption':
                for ftps in self.consisting_of:
                    if ftps.quantity >= 0:
                        return _('Only negative quantities can be redeemed')
            if self.transaction_type == 'full_redemption':
                for ftps in self.consisting_of:
                    if (ftps.quantity != -100) or (ftps.described_by != 'percentage'):
                        return _('Only complete premium schedules can be redeemed')
                    if ftps.get_payments_planned():
                        return _('Payments are planned after redemption')
                    if ftps.premium_schedule is not None:
                        for invoice_item in ftps.premium_schedule.invoice_items:
                            if invoice_item.last_direct_debit_status in (None, 'draft', 'incomplete'):
                                return _('Invoices are planned after redemption')
            elif self.transaction_type in ['switch', 'financed_switch']:
                if len( ftps_per_ps ) > 1:
                    return _('Switch between multiple premium schedules is not allowed')
                negative = len([ftps for ftps in self.consisting_of if ftps.quantity <= 0])
                positive = len([ftps for ftps in self.consisting_of if ftps.quantity >= 0])
                if negative==0 or positive==0:
                    return _('A switch needs a positive and a negative schedule')
                if positive>1:
                    return _('A switch can have only one positive schedule')
            #
            # Check the coverages
            #
            for ps, ftpses in ftps_per_ps.items():
                if ps is None:
                    continue
                for applied_coverage in ps.get_coverages_at( after_transaction ):
                    if self.transaction_type == 'full_redemption':
                        return _('Cannot redeem a premium schedule with an active coverage')
                    for ftps in ftpses:
                        if ftps.described_by == 'percentage' and ftps.quantity <= -100:
                            return _('Cannot redeem a premium schedule with an active coverage')
            #
            # Check the fund distribution after the transaction
            #
            if self.transaction_type != 'full_redemption':
                for ps, ftpses in ftps_per_ps.items():
                    if ps is None:
                        continue
                    total_target_percentage = 0
                    full_redeemed_funds = set()
                    fund_distribution_after_transaction = set(ps.get_funds_at(after_transaction))
                    funds_after_transaction = set(fd.fund for fd in fund_distribution_after_transaction)
                    for ftps in ftpses:
                        for fd in ftps.get_fund_distribution():
                            if ((ftps.quantity <= -100) and (ftps.described_by == 'percentage')):
                                if fd.fund in funds_after_transaction:
                                    return _('Full redeemed fund still in fund distribution after transaction')
                            elif ftps.quantity > 0:
                                if fd.fund not in funds_after_transaction:
                                    return _('Fund involved in transaction not in fund distribution after transaction')
                    if len(full_redeemed_funds) == len(set(ps.get_funds_at(self.from_date))) and len(full_redeemed_funds) > 0:
                        if self.transaction_type not in  ('switch', 'financed_switch'):
                            return _('Cannot redeem all funds if the transaction is not a full redemption')
                    for fund_distribution in fund_distribution_after_transaction:
                        total_target_percentage += fund_distribution.target_percentage
                    if total_target_percentage not in (0, 100):
                        return _('Incorrect fund distribution after transaction')


    @property
    def completion_date(self):
        """The date at which all units that should have been sold are sold, None
        if this date is not yet known, this is T26"""
        from vfinance.model.financial.security import FinancialSecurityQuotation
        completion_date = None
        funds_involved = set()
        for ftps in self.consisting_of:
            #
            # there might be hundreds of ftps in one transaction, so this loop might
            # be very expensive
            #
            if ftps.quantity >= 0:
                continue
            #
            # In non unit linked premium schedules are in the transaction,
            # the from_date is the the completion date of the transaction
            #
            if ftps.premium_schedule is not None:
                if ftps.premium_schedule.product.unit_linked == False:
                    if completion_date:
                        completion_date = max( completion_date, self.from_date )
                    else:
                        completion_date = self.from_date
            #
            # If there are unit linked premium schedules, the completion date
            # is the last quotation date of the units involved, multiple fund
            # distributions might point to the same fund, so gather the funds
            # first
            #
            for fd in ftps.get_fund_distribution():
                # only the sign of the distribution is relevant to get the purchase
                # or sales quotation
                funds_involved.add((fd.fund, math.copysign(ONE, ftps.quantity)))
        for fund, quantity in funds_involved:
            quotation = FinancialSecurityQuotation.valid_quotation(fund, self.from_date, quantity)
            if quotation:
                if completion_date:
                    completion_date = max( completion_date, quotation.from_datetime.date() )
                else:
                    completion_date = quotation.from_datetime.date()
        return completion_date

    def get_financial_accounts(self):
        """The financial accounts on which this transaction acts"""
        return set( ftps.premium_schedule.financial_account for ftps in self.consisting_of )

    def get_premium_schedules(self):
        """The premium schedules on which this transaction acts"""
        return set( ftps.premium_schedule for ftps in self.consisting_of )

class FinancialTransaction(Entity, BankStatusMixin, AbstractFinancialTransaction ):
    """Maintains the transaction activity as the customer uses his financial
    accounts.  The transaction may be monetary in nature, such as deposit or
    withdrawal, or it may be non-monetary, such as inquiry

    documented on page 284 of the DMRB
    """
    using_options(tablename='financial_transaction', order_by=['id'])
    agreement_date = schema.Column( sqlalchemy.types.Date(), nullable=False, index = True )
    from_date = schema.Column( sqlalchemy.types.Date(), nullable=False, index = True )
    thru_date = schema.Column( sqlalchemy.types.Date(), default = end_of_times, nullable=False, index = True )
    code = schema.Column(sqlalchemy.types.Unicode(15), nullable=False, index=True)
    text = schema.Column( camelot.types.RichText )
    status = Status( enumeration=transaction_statuses )
    transaction_type = schema.Column( camelot.types.Enumeration( transaction_types ), nullable=False, index=True, default='partial_redemption')
    period_type = schema.Column( camelot.types.Enumeration( period_types ), nullable=False, index=True, default='single')
    document = schema.Column(camelot.types.File(upload_to=os.path.join('product.financial_agreements', 'document')))
    documents = OneToMany('vfinance.model.financial.document.FinancialDocument')
    distributed_via = OneToMany('vfinance.model.financial.transaction.FinancialTransactionCreditDistribution', cascade='all, delete, delete-orphan')
    #tasks = ManyToMany( 'Task',
    #                    tablename='financial_transaction_task',
    #                    remote_colname='task_id',
    #                    local_colname='financial_transaction_id',
    #                    backref='financial_transactions' )

    @classmethod
    def security_order_lines_condition(cls, transaction_columns, order_lines_columns):

        FTPS = FinancialTransactionPremiumSchedule.table.alias().columns

        return sql.and_( order_lines_columns.document_date == transaction_columns.from_date,
                         order_lines_columns.premium_schedule_id == FTPS.premium_schedule_id,
                         FTPS.within_id == transaction_columns.id,
                         order_lines_columns.fulfillment_type.in_( [ 'switch_out',
                                                                     'switch_attribution',
                                                                     'financed_switch',
                                                                     'redemption' ] ) )
    @classmethod
    def subscriber_query(cls, transaction_columns, rank=1):

        FA = FinancialAccount.table.alias().columns
        FAPS = FinancialAccountPremiumSchedule.table.alias().columns
        FTPS = FinancialTransactionPremiumSchedule.table.alias().columns

        return FinancialAccount.subscriber_query( FA, rank=rank ).where( sql.and_( FA.id == FAPS.financial_account_id,
                                                                                   FAPS.id == FTPS.premium_schedule_id,
                                                                                   FTPS.within_id == transaction_columns.id ) )

    subscriber_1 = ColumnProperty( lambda self:FinancialTransaction.subscriber_query( self, 1 ),
                                   deferred = True,
                                   group = 'subscriber' )

    subscriber_2 = ColumnProperty( lambda self:FinancialTransaction.subscriber_query( self, 2 ),
                                   deferred = True,
                                   group = 'subscriber' )

    @staticmethod
    def premium_sum_query(columns):
        ftps = orm.aliased( FinancialTransactionPremiumSchedule )
        return sql.select( [sql.func.coalesce( sql.func.sum(ftps.quantity), 0 )],
                           columns.id == ftps.within_id )

    def total_quantity(self):
        return FinancialTransaction.premium_sum_query( self )#.where(FinancialAgreementPremiumSchedule.direct_debit==False)

    total_quantity = ColumnProperty( total_quantity, deferred = True )

    @property
    def security_order_lines( self ):
        fsol_query = orm.object_session(self).query(FSOL)
        fsol_query = fsol_query.filter(self.security_order_lines_condition(self, FSOL))
        return fsol_query.all()

    def is_verifiable(self):
        """
        This method will be called by the default verify action.  The exception is
        raised to prevent default action to be used by accident to verify the
        transaction.
        """
        raise Exception('Transaction is only verfiable through specialized action')

    def __unicode__(self):
        return u'%s : '%(self.from_date or '') + u' - '.join([s for s in [self.subscriber_1, self.subscriber_2] if s])

    def is_complete(self):
        note = self.note
        if note:
            raise UserException( note )
        self.future_order_lines()
        self.future_transactions()
        return True

    def future_order_lines(self):
        """Verify if there are no security order lines after this date"""
        for ftps in self.consisting_of:
            session = orm.object_session(self)
            query = session.query(FinancialSecurityOrderLine)
            query = query.filter(sql.and_(FinancialSecurityOrderLine.premium_schedule == ftps.premium_schedule,
                                  FinancialSecurityOrderLine.document_date >= self.from_date))
            count = query.count()
            if count > 0:
                raise UserException('There are order lines past the from date, please remove those or change the from date', title = 'Invalid transaction')

    def future_transactions(self):
        """Verify if there are no transactions afther this date"""
        from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment
        for ftps in self.consisting_of:
            session = orm.object_session(self)
            query = session.query(FinancialAccountPremiumFulfillment).filter(sql.and_(FinancialAccountPremiumFulfillment.of == ftps.premium_schedule,
                                                                             FinancialAccountPremiumFulfillment.entry_doc_date >= self.from_date,
                                                                             FinancialAccountPremiumFulfillment.fulfillment_type != 'premium_attribution',))
            count = query.count()
            if count > 0:
                detail = ''
                for fapf in query.all():
                    detail = unicode( fapf )
                    break;
                premium_schedule = ftps.premium_schedule
                raise UserException( 'There are bookings past the from date on %s, please run backward or change the from date'%unicode( premium_schedule ),
                                     detail = detail,
                                     title = 'Invalid transaction' )

    def get_first_premium_schedule(self):
        for ftps in self.consisting_of:
            return ftps.premium_schedule

    def get_roles_at( self, application_date, role_type = None ):
        """
        :param application_date: date at which to know the roles
        :param role_type: None if all roles should be returned, a specific role
        type, if only those should be returned.
        :return: a list of *unique* roles
        """
        roles = []
        for tps in self.consisting_of:
            roles += tps.premium_schedule.get_roles_at(application_date, role_type)
        # unique values
        seen = set()
        seen_add = seen.add
        return [ x for x in roles if x not in seen and not seen_add(x)]

class RemoveFutureOrderLines(Action):

    verbose_name = _('Remove Order Lines')

    def model_run(self, model_context):
        with model_context.session.begin():
            for transaction in model_context.get_selection():
                for premium_schedule in transaction.get_premium_schedules():
                    query = model_context.session.query(FinancialSecurityOrderLine)
                    query = query.filter(sql.and_(FinancialSecurityOrderLine.premium_schedule == premium_schedule,
                                          FinancialSecurityOrderLine.document_date >= transaction.from_date,
                                          FinancialSecurityOrderLine.part_of != None))
                    count = query.count()
                    if count > 0:
                        raise UserException('There are order lines that are part of an order, those cannot be removed')
                    
                    del_query = model_context.session.query(FinancialSecurityOrderLine)
                    del_query = del_query.filter(sql.and_(FinancialSecurityOrderLine.premium_schedule == premium_schedule,
                                              FinancialSecurityOrderLine.document_date >= transaction.from_date,
                                              FinancialSecurityOrderLine.part_of == None))
                    del_count = del_query.count()
                    yield action_steps.UpdateProgress(text=ugettext('Remove {0} order lines').format(del_count))
                    del_query.delete(synchronize_session='fetch')
                model_context.session.expire(transaction)
                yield action_steps.UpdateObject(transaction)

class TransactionStatusVerified(StatusVerified):

    def before_status_change(self, model_context, obj):
        note = obj.note
        if note:
            raise UserException(note)
        obj.future_order_lines()
        obj.future_transactions()
        for j, ftps in enumerate(obj.consisting_of):
            current_version_id = ftps.get_premium_schedule_version_id()
            if ftps.previous_version_id != current_version_id:
                raise UserException(_('Premium schedule has been modified'),
                                    resolution=_(u'Cancel this transaction and create a new transaction'),
                                    detail=u'The current version of premium schedule {0.premium_schedule_id} is {0.previous_version_id} while the one at completion time was {1}'.format(ftps, current_version_id))
            for i, task in enumerate(ftps.created_via):
                if i==0:
                    FinancialAccountPremiumScheduleHistory.store_version(ftps.premium_schedule)
                yield action_steps.UpdateProgress(detail=task.get_description())
                task.execute()
            yield action_steps.FlushSession(model_context.session)
            ftps.next_version_id = ftps.get_premium_schedule_version_id()
        yield action_steps.FlushSession(model_context.session)

    def model_run(self, model_context):
        for step in super(TransactionStatusVerified, self).model_run(model_context):
            yield step
        yield action_steps.UpdateProgress(blocking=True)

class TransactionStatusUndoVerified(StatusDraft):

    new_status = 'draft'
    verbose_name =  _('Undo verification')
    allowed_statuses = ['verified']

    def before_status_change(self, model_context, obj):
        for step in super(TransactionStatusUndoVerified, self).before_status_change(model_context, obj):
            yield step
        obj.future_order_lines()
        obj.future_transactions()
        for ftps in obj.consisting_of:
            if ftps.next_version_id != ftps.get_premium_schedule_version_id():
                raise UserException(_('Premium schedule has been modified'))
            if ftps.previous_version_id != ftps.next_version_id:
                FinancialAccountPremiumScheduleHistory.restore_version(ftps.premium_schedule)

class FinancialTransactionAdmin(BankStatusAdmin, VfinanceAdmin):
    verbose_name = _('Financial Transaction')
    list_display = ['id', 'agreement_date', 'transaction_type', 'from_date', 'period_type',
                    'subscriber_1', 'subscriber_2', 'current_status', 'code', 'agreement_code',
                    'security_order_lines_count']
    list_filter = BankStatusAdmin.list_filter + ['transaction_type']
    list_search = ['subscriber_1', 'subscriber_2']
    list_actions = (StatusComplete(),
                    TransactionStatusVerified(),
                    TransactionStatusUndoVerified(),
                    RemoveFutureOrderLines(),
                    TransactionDocument(),
                    FinancialTransactionAccountDocument(),
                    )
    form_state = 'maximized'
    form_display = forms.Form([forms.WidgetOnlyForm('note'), forms.TabForm( [(_('Transaction'), forms.Form(['agreement_date', 'from_date',
                                                                                                            'thru_date', 'code',
                                                                                                            'transaction_type', 'period_type',
                                                                                                            'subscriber_1', 'subscriber_2',
                                                                                                            'document', 'current_status', 'completion_date',
                                                                                                            'consisting_of', 'distributed_via'], columns=2) ),
                                                                              (_('Extra'), ['text', 'documents']),
                                                                              (_('Orders'), ['security_order_lines']),
                                                                              (_('Status history'), ['status',]) ])])
    form_actions = (StatusDraft(),
                    StatusComplete(),
                    TransactionStatusVerified(),
                    StatusIncomplete(),
                    StatusCancel(),
                    TransactionStatusUndoVerified(),
                    BulkTransaction(),
                    RemoveFutureOrderLines(),
                    FinancialTransactionSummary(),
                    FinancialTransactionAccountsSummary( ),
                    TransactionDocument(),
                    FinancialTransactionAccountDocument(),
                    TransactionVerificationForm(),)

    field_attributes = {'current_status':{'name':_('current status'), 'editable':False},
                        'id':{'editable':False},
                        'code':{'validator':CodeValidator(), 'tooltip':u'bvb. \'789/5345/88943\''},
                        'security_order_lines_count':{'name':_('Orders')},
                        'security_order_lines':{'name':_('Order lines'),
                                                'python_type':list,
                                                'delegate':delegates.One2ManyDelegate,
                                                'target':FinancialSecurityOrderLine},
                        'note':{'delegate':delegates.NoteDelegate},
                        'completion_date':{'delegate':delegates.DateDelegate}}

FinancialTransaction.Admin = FinancialTransactionAdmin

class FinancialTransactionOnAccountAdmin(FinancialTransactionAdmin):
    list_display = ['id', 'agreement_date', 'transaction_type', 'from_date', 'period_type', 'current_status', 'code',]

FinancialAccount.Admin.field_attributes['transactions'] = {'admin':FinancialTransactionOnAccountAdmin}

quantity_field_attributes = {
    'suffix' : lambda o:transaction_distribution_type_suffix.get(o.described_by, 'Euro'),
    'precision' : lambda o:transaction_distribution_type_precision.get(o.described_by, 2),
}

class AbstractFinancialTransactionPremiumSchedule( object ):

    @property
    def transaction_from_date(self):
        if self.within:
            return self.within.from_date

    @property
    def agreement_code(self):
        if self.premium_schedule:
            return self.premium_schedule.agreement_code

    def get_applied_feature_at(self, application_date, attribution_date, amount, feature_description, default=None):
        """
        :param application_date: the date at which the features will be used, eg to book a premium
        :param attribution_date: the date at which the principal was attributed to the account
        :param feature_description: the name of the feature
        :param default: what will be returned in case no feature is found (distinction between None and 0)
        :return: the applicable feature, or None in no such feature applicable
        """
        applied_feature = None
        for feature in self.applied_features:
            if feature.described_by == feature_description and feature.apply_from_date <= application_date and feature.apply_thru_date >= application_date:
                applied_feature = feature
        if applied_feature:
            return applied_feature
        return self.premium_schedule.get_applied_feature_at(application_date, attribution_date, amount, feature_description, default)

    def get_fund_distribution(self):
        """A list of fund distributions, either the one specified within this transaction.
        or the default distribution of the premium schedule
        Always ordered by the id the fund distribution. not on the id of the fund
        since the same fund might appear multiple times within a different
        distribution
        """
        if len(self.fund_distribution):
            fund_distributions = [fd for fd in self.fund_distribution]
            fund_distributions.sort(key = lambda x:x.id)
        elif self.premium_schedule is not None:
            fund_distributions = self.premium_schedule.get_funds_at(self.within.from_date)
        else:
            fund_distributions = []
        return fund_distributions

    # don't add properties here which are shortcuts to the premium schedule
    # or the transaction, since this might result in ambiguous code

    def get_product(self):
        if self.premium_schedule is not None:
            return self.premium_schedule.product

    def get_premium_schedule_version_id(self):
        if self.premium_schedule is not None:
            return self.premium_schedule.version_id

    def get_payments_planned(self):
        """
        :return: True if there are payments planned after the transaction from date,
                 False if there are no payments planned, None if there is no premium
                 schedule specified yet
        """
        if (self.premium_schedule is not None) and (self.within is not None):
            ps = self.premium_schedule
            if self.within.from_date is None:
                return None
            if (ps.payment_thru_date >= self.within.from_date):
                for task in self.created_via:
                    if task.described_by == 'terminate_payment_thru_date':
                        return False
                return True
            return False

class FinancialTransactionPremiumSchedule(Entity, AbstractFinancialTransactionPremiumSchedule):

    __tablename__ ='financial_transaction_premium_schedule'

    within_id = schema.Column(sqlalchemy.types.Integer(),
                              schema.ForeignKey(FinancialTransaction.__table__.c.id,
                              ondelete='cascade',
                              onupdate='cascade'),
                              nullable=False)
    within = orm.relationship(FinancialTransaction,
                              backref=orm.backref('consisting_of', cascade='all, delete, delete-orphan'),
                              enable_typechecks=False)

    premium_schedule_id = schema.Column(sqlalchemy.types.Integer(),
                                        schema.ForeignKey(financial_account_premium_schedule_table.c.id,
                                                          ondelete='restrict',
                                                          onupdate='cascade'),
                                        nullable=False)
    premium_schedule = orm.relationship(
        FinancialAccountPremiumSchedule,
        backref = orm.backref('transactions'),
    )
    previous_version_id = schema.Column(sqlalchemy.types.Integer(), nullable=False)
    next_version_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    described_by = schema.Column( camelot.types.Enumeration( transaction_distribution_type_enumeration ), nullable=False, index=True, default='amount')
    quantity = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False, default=0)
    fund_distribution = OneToMany('vfinance.model.financial.fund.FinancialTransactionFundDistribution', cascade='all, delete, delete-orphan', order_by=['id'])
    applied_features = OneToMany('vfinance.model.financial.feature.FinancialTransactionPremiumScheduleFeature', cascade='all, delete, delete-orphan')

    def __init__(self, *args, **kwargs):
        """Uses the current version_id of the premium schedule passed as a
        constructor argument as previous_version_id
        """
        faps = kwargs.get('premium_schedule', None)
        if faps is not None:
            kwargs['previous_version_id'] = faps.version_id
        Entity.__init__(self, *args, **kwargs)

    def __unicode__( self ):
        if self.within:
            return u'%s %s %s'%( unicode( self.within ), self.quantity or 0, transaction_distribution_type_suffix.get(self.described_by, 'Euro') )

    def current_status_sql( self ):
        return FinancialTransaction.current_status_query( FinancialTransaction._status_history,
                                                          FinancialTransaction ).where( FinancialTransaction.id == self.within_id )

    current_status_sql = ColumnProperty( current_status_sql, deferred=True )

    def from_date_sql( self ):
        return sql.select( [FinancialTransaction.from_date] ).where( FinancialTransaction.id == self.within_id ).limit(1)

    from_date_sql = ColumnProperty( from_date_sql, deferred=True )

    def thru_date_sql( self ):
        return sql.select( [FinancialTransaction.thru_date] ).where( FinancialTransaction.id == self.within_id ).limit(1)

    thru_date_sql = ColumnProperty( thru_date_sql, deferred=True )

FinancialTransaction.security_order_lines_count = orm.column_property(
    sql.select( [sql.func.count(FSOL.id.distinct())] ).where(FinancialTransaction.security_order_lines_condition(FinancialTransaction, FSOL)),
    deferred=True,
)

FTPS = FinancialTransactionPremiumSchedule.__table__.alias().columns
FAPS = FinancialAccountPremiumSchedule.__table__.alias().columns

FinancialTransaction.agreement_code = orm.column_property(
    FinancialAccountPremiumSchedule.agreement_code_query( FAPS ).where( sql.and_( FAPS.id == FTPS.premium_schedule_id,
                                                                                  FTPS.within_id == FinancialTransaction.id ) ).limit(1),
    deferred=True,
)


class FinancialTransactionPremiumScheduleAdmin(BankRelatedStatusAdmin):
    verbose_name = _('Premium Schedule Transaction')
    list_display = ['transaction_from_date', 'premium_schedule', 'described_by', 'quantity', 'agreement_code']
    form_display = list_display + ['fund_distribution', 'applied_features', 'created_via']
    field_attributes = {'described_by' : {'name':_('Type')},
                        'agreement_code' : {'validator':CodeValidator(), 'tooltip':u'bvb. \'789/5345/88943\''},
                        'quantity':quantity_field_attributes,
                        'status_parent':'within',
                        'created_via': {'name': _('Tasks'), 'create_inline': True},
                        'previous_version_id': {
                            'default': FinancialTransactionPremiumSchedule.get_premium_schedule_version_id,
                            }
                        }

    def get_depending_objects(self, obj):
        if obj.within:
            if self.is_persistent(obj.within):
                obj.within.expire(['agreement_code',])
            yield obj.within

    def get_related_status_object(self, o):
        return o.within

    def get_related_toolbar_actions( self, toolbar_area, direction ):
        actions = BankRelatedStatusAdmin.get_related_toolbar_actions( self, toolbar_area, direction )
        if toolbar_area == Qt.RightToolBarArea and direction == 'onetomany':
            actions.append( list_action.ImportFromFile() )
        return actions

FinancialTransactionPremiumSchedule.Admin = FinancialTransactionPremiumScheduleAdmin

class AbstractFinancialTransactionCreditDistribution(object):

    def __unicode__(self):
        return self.iban or '...'

    def is_valid( self ):
        if self.iban == None:
            return False
        return validation.iban(self.iban)[0] or validation.ogm(self.iban)

class FinancialTransactionCreditDistribution( Entity, AbstractFinancialTransactionCreditDistribution, IbanBicMixin):
    """A SEPA style mandate to credit a customer account
    """
    using_options(tablename='financial_transaction_credit_distribution')
    financial_transaction = ManyToOne('vfinance.model.financial.transaction.FinancialTransaction', onupdate='cascade', ondelete='cascade', enable_typechecks=False)
    document = schema.Column( camelot.types.File( upload_to=os.path.join('financial', 'transaction_debit_account', 'document') ), nullable=True )
    bank_identifier_code = ManyToOne('BankIdentifierCode', required=False, onupdate='cascade', ondelete='restrict' )
    iban = schema.Column( sqlalchemy.types.Unicode(4+30), nullable=False )
    described_by = schema.Column( camelot.types.Enumeration( transaction_distribution_type_enumeration ), nullable=False, index=True, default='percentage')
    quantity = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False, default=100)

    class Admin( BankRelatedStatusAdmin ):
        verbose_name = _('Credit Account')
        list_display = ['bank_identifier_code', 'iban', 'described_by', 'quantity']
        form_display = list_display + ['document']
        field_attributes = {'quantity':quantity_field_attributes,
                            'iban':{'tooltip':'example : NL91ABNA0417164300', 'validator':AbstractBankAccount.Admin.BankingNumberValidator()},
                            'described_by' : {'name':_('Type')},}

        def get_related_status_object(self, obj):
            return obj.financial_transaction

        def get_depending_objects(self, obj):
            if obj.financial_transaction:
                yield obj.financial_transaction

FinancialAccountPremiumSchedule.last_transaction = ColumnProperty(lambda ps:
    sql.select([sql.func.max(FinancialTransaction.from_date)],
               from_obj = FinancialTransaction.__table__.join(FinancialTransactionPremiumSchedule.__table__),
               whereclause = sql.and_(FinancialTransaction.current_status=='verified',
                                      FinancialTransaction.from_date <= sql.func.current_date(),
                                      FinancialTransaction.id==FinancialTransactionPremiumSchedule.within_id,
                                      FinancialTransactionPremiumSchedule.premium_schedule_id==ps.id),
               ),
    deferred=True
    )
