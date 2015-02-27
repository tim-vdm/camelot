import logging
import datetime

from decimal import Decimal as D

from sqlalchemy import orm, inspect

from camelot.admin.object_admin import ObjectAdmin
from camelot.admin.action import Action
from camelot.view import forms, action_steps
from camelot.view.controls import delegates
from camelot.core.utils import ugettext_lazy as _
from camelot.core.memento import memento_change
from camelot.model.authentication import end_of_times
from camelot.core.orm import Entity

from ..model.financial.transaction import (FinancialTransaction,
                                           FinancialTransactionPremiumSchedule,
                                           FinancialTransactionAdmin,
                                           FinancialTransactionCreditDistribution)
from ..model.financial.transaction_task import FinancialTransactionPremiumScheduleTask
from vfinance.model.financial.summary.account_summary import FinancialAccountSummary
#from vfinance.model.financial.summary.transaction_verification import TransactionVerificationForm
from vfinance.model.financial.notification import NotificationOptions
#from vfinance.model.financial.admin import RunTransactionSimulation
from vfinance.model.financial.account import FinancialAccountItem
from vfinance.model.bank.statusmixin import StatusComplete, StatusIncomplete, set_status

from .constants import checks


logger = logging.getLogger(__name__)


# all attributes preceeded by a certain prefix point to a specific object
# in the transaction object hierarchy
credit_distribution_prefix = 'credit_distribution_'

def create_check_needed(check):
    return lambda obj: getattr(obj, check + '_check_needed')

class IncompleteRedemption(StatusIncomplete):
    verbose_name = _('Incomplete')

    def model_run(self, model_context):
        facade = model_context.get_object()

        facade.change_status('incomplete')

        memento = model_context.admin.get_related_admin(FinancialTransaction).get_memento()
        memento.register_changes([memento_change(model=unicode(FinancialTransaction.__name__),
                                                 primary_key=[facade.id],
                                                 previous_attributes={'completion time':int((datetime.datetime.now() - facade.created_at).seconds),
                                                                      'status': 'incomplete'},
                                                 memento_type='facade creation')])

        accounts = [account for account in facade.accounts]

        facade._facade_session.flush()

        facade = model_context.session.merge(facade)

        for account in accounts:
            model_context.session.expire(account)
            yield action_steps.UpdateObject(account)

        yield action_steps.OpenFormView([facade],
                                        model_context.admin.get_related_admin(FinancialTransaction))
        yield action_steps.gui.CloseView()

    def get_state(self, model_context):
        state = super(IncompleteRedemption, self).get_state(model_context)
        facade = model_context.get_object()
        state.enabled = True
        validator = model_context.admin.get_validator()
        for message in validator.validate_object(facade):
            state.enabled = False
            return state
        for check in facade.checks:
            if getattr(facade, check) is None:
                state.enabled = False
                return state
        return state

class CompleteRedemption(StatusComplete):
    verbose_name = _('Complete')

    def model_run(self, model_context):
        facade = model_context.get_object()

        facade.is_complete()

        accounts = [account for account in facade.accounts]
        created_at = facade.created_at


        set_status(facade._facade_session, facade)
        facade._facade_session.flush()
        facade.change_status('complete')
        facade._facade_session.flush()
        facade = model_context.session.merge(facade)

        memento = model_context.admin.get_related_admin(FinancialTransaction).get_memento()
        memento.register_changes([memento_change(model=unicode(FinancialTransaction.__name__),
                                                 primary_key=[facade.id],
                                                 previous_attributes={'completion time':int((datetime.datetime.now() - created_at).seconds),
                                                                      'status': 'complete'},
                                                 memento_type='facade creation')])

        for account in accounts:
            model_context.session.expire(account)
            yield action_steps.UpdateObject(account)


        #for step in RunTransactionSimulation().simulate_transactions(model_context, [facade], model_context.session):
        #    yield step
        #for step in TransactionVerificationForm().generate_document(model_context, facade):
        #    yield step
        yield action_steps.gui.CloseView()


    def get_state(self, model_context):
        state = super(CompleteRedemption, self).get_state(model_context)
        facade = model_context.get_object()
        state.enabled = True
        validator = model_context.admin.get_related_admin(facade.__class__).get_validator()
        if len(validator.validate_object(facade)) > 0:
            state.enabled = False
            return state
        for check in facade.checks:
            if not getattr(facade, check):
                state.enabled = False

        return state


class CancelRedemptionWizard(Action):
    verbose_name = _('Cancel')

    def model_run(self, model_context):
        facade = model_context.get_object()
        if facade is not None:
            facade_session = inspect(facade).session
            facade_session.expunge(facade)
        yield action_steps.gui.CloseView()

class RedemptionFacade(FinancialTransaction):
    """Provides a flat proxy towards a Redemption, to make it easy to
    build simplified UI elements around a redemption.

    :param transaction: the `FinancialTransaction` for which a proxy is provided
    """

    def __init__(self, **kwargs):
        """

        """
        #
        # All fields in this object should have a prefix that describes
        # to which object they relate
        #

        # @todo: RedemptionFacade should be able to process transactions with multiple accounts. Currently this isn't possible.
        # @todo: warn and display other incomplete or unverified transactions involving the same premium schedules
        # @todo: unit test should not modify the transaction, but should go through the facade
        super(RedemptionFacade, self).__init__(**kwargs)
        self._facade_session = orm.object_session(self)
        self.transaction_type = 'full_redemption'
        self.thru_date = end_of_times()
        self.period_type = 'single'
        credit_distribution = self._create_object(FinancialTransactionCreditDistribution)
        credit_distribution.bank_identifier_code = None
        credit_distribution._iban = None
        credit_distribution.described_by = 'percentage'
        credit_distribution.quantity = 100.0
        self.distributed_via.append(credit_distribution)
        self.reconstruct()

    @orm.reconstructor
    def reconstruct(self):
        """
        set al non-orm attributes
        """
        self.created_at = datetime.datetime.now()
        self.clauses_check_needed = False
        self.compliance_check_needed = False
        self.terminate_premium_payments_check_needed = True
        self.clauses_checked = None
        self.compliance_checked = None
        self.accounts = []
        self.value = D(0.0)
        self._clauses = []
        self.messages = []

    def __setattr__(self, name, value):
        if isinstance(value, Entity):
            session = inspect(value).session
            if session != self._facade_session:
                value = self._facade_session.merge(value)
        return super(RedemptionFacade, self).__setattr__(name, value)

    def __unicode__(self):
        return '|'.join(unicode(account) for account in self.accounts)

    def set_account_states(self, account_states):
        self.account_states = account_states
        for account_state  in account_states:
            self.accounts.append(account_state.get('account'))
            if account_state.get('total'):
                self.value += account_state.get('total')
            for clause in account_state.get('clauses'):
                self._clauses.append(clause)
                if clause.use_custom_clause == True:
                    self.clauses_check_needed = True

        # @todo: remove magic number, must become a feature on premium_schedule (bank.constants.insurance_features)
        if self.value > 100000:
            self.compliance_check_needed = True

        self.checks = set([check[0] + '_checked' for check in checks if getattr(self, check[0] + '_check_needed')])

    def set_premium_schedule_quantities(self):
        for schedule in self.consisting_of:
            schedule.described_by = 'percentage'
            schedule.quantity = -100.0

    @property
    def credit_distribution_bank_identifier_code(self):
        if len(self.distributed_via):
            return self.distributed_via[0].bank_identifier_code

    @credit_distribution_bank_identifier_code.setter
    def credit_distribution_bank_identifier_code(self, value):
        self.distributed_via[0].bank_identifier_code = value

    @property
    def credit_distribution_iban(self):
        if len(self.distributed_via):
            return self.distributed_via[0]._iban

    @credit_distribution_iban.setter
    def credit_distribution_iban(self, value):
        session = inspect(self.distributed_via[0]).session
        if session != self._facade_session:
            self.distributed_via[0] = self._facade_session.merge(self.distributed_via[0])
        self.distributed_via[0]._iban = value

    @property
    def clauses(self):
        return self._clauses

    @property
    def terminate_premium_payments_checked(self):
        for ftps in self.consisting_of:
            payments_planned = ftps.get_payments_planned()
            if payments_planned == True:
                return False
            elif payments_planned is None:
                return None
        return True

    @terminate_premium_payments_checked.setter
    def terminate_premium_payments_checked(self, value):
        for ftps in self.consisting_of:
            if value == True:
                if ftps.get_payments_planned() == True:
                    task = self._create_object(FinancialTransactionPremiumScheduleTask)
                    session = inspect(task).session
                    if session != self._facade_session:
                        task = self._facade_session.merge(task)
                    task.described_by = 'terminate_payment_thru_date'
                    ftps.created_via.append(task)
            else:
                for task in ftps.created_via:
                    if task.described_by == 'terminate_payment_thru_date':
                        ftps.created_via.remove(task)


    def _create_object(self, cls):
        """Create an object of type `cls` to its constructor.
        The created object will live in the same session as the proxied agreement.

        No attributes are passes as kwargs in the constructor as those would risk
        to modify the session of the agreement or the passed argument.
        """
        obj = cls()
        obj_session = orm.object_session(obj)
        if self._facade_session != obj_session:
            if obj_session is not None:
                obj_session.expunge(obj)
            if self._facade_session is not None:
                self._facade_session.add(obj)
        return obj


    class Admin(FinancialTransactionAdmin):

        verbose_name = 'Full Redemption'

        checklist = [check + '_checked' for check, _choices, _message in checks]

        form_display = forms.Form([
            forms.WidgetOnlyForm('note'),
            forms.TabForm([(_('Redemption'),
                            forms.HBoxForm([
                                forms.VBoxForm([
                                    forms.GroupBoxForm(
                                        _('Account'),
                                        ['code',
                                         'value'],
                                    ),
                                    forms.GroupBoxForm(
                                        _('Dates'),
                                        ['agreement_date',
                                         'from_date',]
                                    ),
                                    forms.GroupBoxForm(
                                        _('Bank'),
                                        ['credit_distribution_iban',
                                         'credit_distribution_bank_identifier_code',]
                                    ),
                                    forms.GroupBoxForm(
                                        _('Checks'),
                                        checklist
                                    ),
                                    forms.GroupBoxForm(
                                        _('Remarks'),
                                        ['text',]
                                    ),
                                    forms.Stretch(),
                                    ],),
                                ],),),
                            (_('Clauses'),
                             forms.HBoxForm([
                                 forms.GroupBoxForm(
                                     _('Clauses'),
                                     ['clauses',]
                                 ),
                                 forms.Stretch(),
                             ],),)
                           ]),
            ], scrollbars=True)

        field_attributes =  {check + '_checked': {'choices': choice,
                                                          'delegate': delegates.ComboBoxDelegate,
                                                          'name': text,
                                                          'editable': create_check_needed(check)
                                                          }
                                     for check, choice, text in checks}

        field_attributes['clauses'] = {'target': FinancialAccountItem,
                                      'delegate': delegates.One2ManyDelegate,
                                      'editable': False}
        field_attributes['value'] = {'delegate': delegates.FloatDelegate}

        field_attributes.update(FinancialTransactionAdmin.field_attributes)





        form_actions = [IncompleteRedemption(),
                        CompleteRedemption(),
                        CancelRedemptionWizard()]

        form_state = 'maximized'

        def flush(self, obj):
            pass

        def get_related_admin_and_object_for_field(self, related_field_name, obj=None):
            """Find out the correct admin, object and field_name for determining the field attributes
            :param related_field_name: The field name passed to get_dynamic_field_attributes
            :param obj: The object passed to get_dynamic_field_attributes
            :return: (admin, object, field_name)
            """

            related_admin = None
            related_obj = obj
            field_name = related_field_name

            if related_field_name.startswith(credit_distribution_prefix):
                related_admin = self.get_related_admin(FinancialTransactionCreditDistribution)
                if obj is not None:
                    related_obj = obj.distributed_via[0]
                field_name = related_field_name[len(credit_distribution_prefix):]
            return related_admin, related_obj, field_name


        def get_field_attributes(self, field_name):
            related_admin, ni, related_field_name = self.get_related_admin_and_object_for_field(field_name)
            if related_admin is not None:
                field_attributes = related_admin.get_field_attributes(related_field_name)
            else:
                field_attributes = ObjectAdmin.get_field_attributes(self, field_name)
            return field_attributes

        def get_dynamic_field_attributes(self, obj, field_names):
            for field_name in field_names:
                related_admin, related_obj, related_field_name = self.get_related_admin_and_object_for_field(field_name, obj)

                if related_admin is not None:
                    dynamic_field_attributes = related_admin.get_dynamic_field_attributes(related_obj, [related_field_name])
                else:
                    dynamic_field_attributes = ObjectAdmin.get_dynamic_field_attributes(self, related_obj, [related_field_name])

                for attributes in dynamic_field_attributes:
                    yield attributes


class RedemptionAction(Action):

    verbose_name = _('Full Redemption')

    def model_run(self, model_context):
        from . import FacadeSession
        account_states = []

        facade_session = FacadeSession()

        options = NotificationOptions()
        options.from_document_date = datetime.datetime.today()

        facade = RedemptionFacade(_session=facade_session)

        for account in model_context.get_selection():
            for schedule in account.premium_schedules:
                session = orm.object_session(schedule)
                if session != facade_session:
                    schedule = facade_session.merge(schedule)
                if facade.code is None:
                    facade.code = schedule.agreed_schedule.financial_agreement.code

                facade.consisting_of.append(FinancialTransactionPremiumSchedule(within=facade,
                                                                                premium_schedule=schedule))
            account_states.append(FinancialAccountSummary().context(account, options))

        facade.set_premium_schedule_quantities()
        facade.set_account_states(account_states)

        yield action_steps.OpenFormView([facade], model_context.admin.get_related_admin(RedemptionFacade))

