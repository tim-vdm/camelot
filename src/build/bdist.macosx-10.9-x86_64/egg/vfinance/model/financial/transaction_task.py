"""
Account Transaction Tasks (as described in DMRBII p. 288)

Functions that are executed in an automated fashion when a transaction
is verified.

"""

import datetime

from camelot.core.orm import Entity, ManyToOne
from camelot.core.utils import ugettext_lazy as _
import camelot.types

from sqlalchemy import schema

from .constants import transaction_task_type_enumeration
from .transaction import FinancialTransactionPremiumSchedule
from ..bank.statusmixin import BankRelatedStatusAdmin

class FinancialTransactionPremiumScheduleTask(Entity):

    __tablename__ = 'financial_transaction_premium_schedule_task'

    creating = ManyToOne(FinancialTransactionPremiumSchedule,
                         nullable=False, ondelete='cascade', onupdate='cascade',
                         backref='created_via')
    described_by = schema.Column(camelot.types.Enumeration(transaction_task_type_enumeration),
                                 nullable=False,
                                 index=True,
                                 default='terminate_payment_thru_date')

    def get_payment_termination_date(self):
        if self.creating is not None:
            if self.creating.within is not None:
                if self.creating.premium_schedule is not None:
                    payment_thru_date = self.creating.premium_schedule.payment_thru_date
                    return min(payment_thru_date, self.creating.within.from_date - datetime.timedelta(days=1))

    def get_description(self):
        payment_termination_date = self.get_payment_termination_date()
        if payment_termination_date is not None:
            premium_schedule = self.creating.premium_schedule
            return u'Terminate payments of {1.full_account_number} rank {1.rank} at {0.year}-{0.month}-{0.day}'.format(payment_termination_date, premium_schedule)

    def execute(self):
        payment_termination_date = self.get_payment_termination_date()
        if payment_termination_date is not None:
            self.creating.premium_schedule.payment_thru_date = payment_termination_date

    def __unicode__(self):
        return u'Terminate payments'

    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Transaction task')
        list_display = ['described_by']
        field_attributes = {'described_by' : {'name':_('Type')},
                            }

        def get_depending_objects(self, obj):
            if obj.creating is not None:
                yield obj.creating
                if obj.creating.within is not None:
                    yield obj.creating.within

        def get_related_status_object(self, obj):
            if obj.creating is not None:
                if obj.creating.within is not None:
                    return obj.creating.within
