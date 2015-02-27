"""Copy van Venice Accounts  met de bedoeling van deze 's nachts te synchroniseren
met Venice, om het querieen te versnellen
"""

import logging

import sqlalchemy.types
from sqlalchemy import schema

from camelot.core.orm import Entity, using_options
from camelot.core.utils import ugettext_lazy as _
import camelot.types

from .statusmixin import StatusClose, StatusDelay, StatusActivate, ForceStatus
from vfinance.admin.vfinanceadmin import VfinanceAdmin

logger = logging.getLogger('vfinance.model.bank.account')


class Account(Entity):
    """Spiegel tabel van alle accounts in Venice"""
    using_options(tablename='bank_account', order_by=['number'])
    number  =  schema.Column(sqlalchemy.types.Unicode(14), nullable=False)
    description =  schema.Column(sqlalchemy.types.Unicode(250), nullable=False)
    accounting_state = schema.Column(camelot.types.Enumeration([(1, 'requested'), (2, 'draft'), (3, 'confirmed'),]), nullable=False, default='confirmed', index=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    class Admin(VfinanceAdmin):
        verbose_name = _('Account')
        list_display = ['number', 'description']

status_form_actions = (
    StatusClose(),
    StatusDelay(),
    StatusActivate(),
    ForceStatus(),
)
