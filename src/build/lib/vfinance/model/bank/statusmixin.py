import datetime
import logging

from sqlalchemy import orm, event

from camelot.core.exception import UserException
from camelot.core.orm import transaction
from camelot.core.memento import memento_change
from camelot.core.utils import ugettext_lazy as _
from camelot.admin.entity_admin import EntityAdmin
from camelot.model.authentication import end_of_times
from camelot.model.type_and_status import (StatusMixin, StatusFilter, ChangeStatus)
from camelot.view import action_steps

from vfinance.admin.vfinanceadmin import VfinanceAdmin

logger = logging.getLogger('vfinance.model.financial.statusmixin')

def send_mail(mail):
    yield action_steps.MessageBox(str(mail))


class ForceStatus(ChangeStatus):

    def __init__(self):
        super(ForceStatus, self).__init__(new_status=None,
                                          verbose_name = _('Force status'))

    def before_status_change(self, model_context, obj):
        yield action_steps.UpdateProgress(text='Register force status')
        admin = model_context.admin
        cls = admin.entity
        cls_name = unicode(cls.__name__)
        memento = admin.get_memento()
        memento.register_changes([memento_change( model = cls_name,
                                                  primary_key = admin.primary_key( obj ),
                                                  previous_attributes = {'current_status': obj.current_status},
                                                  memento_type = 'force status' )])

    def model_run(self, model_context):
        admin = model_context.admin
        status_items = [(v, v) for _k, v in admin.entity._status_enumeration]
        select_status = action_steps.SelectItem(status_items)
        select_status.autoaccept = False
        new_status = yield select_status
        if new_status is not None:
            for step in super(ForceStatus, self).model_run(model_context,
                                                           new_status):
                yield step


class StatusDraft(ChangeStatus):
    
    new_status = 'draft'
    verbose_name = _('Draft')
    allowed_statuses = ['complete']
    
    def __init__(self):
        super(StatusDraft, self).__init__(self.new_status, self.verbose_name)

    def before_status_change(self, model_context, obj):
        if obj.current_status not in self.allowed_statuses:
            raise UserException('Status not ' + ' or '.join(self.allowed_statuses) + ' but %s.'%(obj.current_status))
        yield action_steps.UpdateProgress(text='Register status change')
        admin = model_context.admin
        cls = admin.entity
        cls_name = unicode(cls.__name__)
        memento = admin.get_memento()
        memento.register_changes([memento_change( model = cls_name,
                                                  primary_key = admin.primary_key( obj ),
                                                  previous_attributes = {'current_status': obj.current_status},
                                                  memento_type = 'change status' )],)
                                 #session=model_context.session)

    def get_state(self, model_context):
        state = super(StatusDraft, self).get_state(model_context)
        obj = model_context.get_object()
        if (obj is None) or (obj.current_status not in self.allowed_statuses):
            state.enabled = False
        return state


class StatusComplete(StatusDraft):
    
    new_status = 'complete'
    verbose_name =  _('Complete')
    allowed_statuses = ['draft', 'incomplete']
    
    def before_status_change(self, model_context, obj):
        if not obj.is_complete():
            raise UserException(u'Not complete : %s'%obj.note)
        for step in super(StatusComplete, self).before_status_change(model_context, obj):
            yield step


class StatusVerified(StatusComplete):
    
    new_status = 'verified'
    verbose_name =  _('Verified')
    allowed_statuses = ['complete']

    def before_status_change(self, model_context, obj):
        if not obj.is_verifiable():
            raise UserException(u'Not verifiable : %s'%obj.note)
        for step in super(StatusComplete, self).before_status_change(model_context, obj):
            yield step


class StatusIncomplete(StatusDraft):
    
    new_status = 'incomplete'
    verbose_name =  _('Incomplete')
    allowed_statuses = ['draft', 'complete', 'canceled']


class StatusCancel(StatusDraft):
    
    new_status = 'canceled'
    verbose_name =  _('Cancel')
    allowed_statuses = ['draft', 'complete', 'incomplete']


class StatusClose(StatusDraft):

    new_status = 'closed'
    verbose_name = _('Close')
    allowed_statuses = ['active', 'delayed']


class StatusDelay(StatusDraft):

    new_status = 'delayed'
    verbose_name = _('Delay')
    allowed_statuses = ['active']


class StatusActivate(StatusDraft):

    new_status = 'active'
    verbose_name = _('Activate')
    allowed_statuses = ['delayed']

status_form_actions = (
    StatusDraft(),
    StatusComplete(),
    StatusVerified(),
    StatusIncomplete(),
    StatusCancel(),
    ForceStatus(),
)


class BankStatusMixin( StatusMixin ):
    """Shared functionality between a Financial classes and Statuses"""

    def is_complete(self):
        return not self.note

    def is_verifiable(self):
        return not self.note

    #
    # transitions for financial accounts
    #
    @transaction
    def button_closed(self):
        self.expire()
        if not self.current_status in ['active', 'delayed']:
            raise UserException('Status is not active or delayed')
        self.change_status('closed')

    @transaction
    def button_delayed(self):
        self.expire()
        if not self.current_status in ['active',]:
            raise UserException('Status is not active')
        self.change_status('delayed')

    @transaction
    def button_active(self):
        self.expire()
        if not self.current_status in ['delayed',]:
            raise UserException('Status is not delayed')
        self.change_status('active')

class BankRelatedStatusAdmin(VfinanceAdmin):

    def get_status(self, obj):
        if self.get_related_status_object(obj) is not None:
            return self.get_related_status_object(obj).current_status
        return None

    def get_related_status_object(self, obj):
        raise NotImplemented

    def delete(self, obj):
        status = self.get_status(obj)
        if status not in (None, 'draft'):
            raise UserException('Cannot delete while in status {0}'.format(status))
        super(BankRelatedStatusAdmin, self).delete(obj)

    def get_dynamic_field_attributes(self, obj, field_names):
        """Make sure all field are only editable in draft status or for new agreements"""
        field_names = list(field_names)
        dynamic_field_attributes = list(EntityAdmin.get_dynamic_field_attributes(self, obj, field_names))
        static_field_attributes = list(EntityAdmin.get_static_field_attributes(self, field_names))
        if self.get_status(obj) in (None, 'draft', 'incomplete', 'delayed'):
            editable = True
        else:
            editable = False
        for static_attributes, dynamic_attributes, field_name in zip(static_field_attributes, dynamic_field_attributes, field_names):
            if static_attributes.get('editable', True)==False:
                dynamic_attributes['editable'] = False
            elif dynamic_attributes.get('editable', True)==False:
                dynamic_attributes['editable'] = False
            elif field_name != 'document' or obj.document != None:
                dynamic_attributes['editable'] = editable
            if field_name in self.always_editable_fields:
                dynamic_attributes['editable'] = True

        return dynamic_field_attributes

class BankStatusAdmin(BankRelatedStatusAdmin):
    """Shared functionallity for the admin classes that have a financial status
    This Admin will render the fields not editable when they are not in the draft
    or incomplete status.  It will also provide the default draft status.
    """

    list_filter = [StatusFilter('status')]

    def get_query(self, *args, **kwargs):
        query = super(BankStatusAdmin, self).get_query(*args, **kwargs)
        query = query.options(orm.subqueryload('status'))
        return query
    
    def get_status(self, obj):
        return obj.current_status

    def get_mail(self, obj, previous_state, new_state):
        return None

@event.listens_for(orm.Session, 'after_attach')
def set_status(session, instance, status=None):
    """Set the status of a new contract to draft"""
    if isinstance(instance, BankStatusMixin):
        if instance.current_status is None or status is not None:
            today = datetime.date.today()
            instance._status_history(status_for=instance,
                                     classified_by=status or 'draft',
                                     status_from_date=today,
                                     status_thru_date=end_of_times(),
                                     from_date=today,
                                     thru_date=end_of_times())
