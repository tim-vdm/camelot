import sqlalchemy.types
from sqlalchemy import schema

from camelot.core.orm import Entity, using_options, ManyToOne
from camelot.admin.entity_admin import EntityAdmin
from camelot.core.utils import ugettext_lazy as _
import camelot.types

class OfficialNumber(Entity):
    using_options(tablename='bank_official_number')
    type = schema.Column(camelot.types.Enumeration([(2,'cbfa'), (3,'mez'), (4,'biv')]), index=True, nullable=False)
    number = schema.Column(sqlalchemy.types.Unicode(128), index=True, nullable=False)
    issue_date = schema.Column(sqlalchemy.types.Date)
    note = schema.Column(camelot.types.RichText)
    rechtspersoon = ManyToOne('vfinance.model.bank.rechtspersoon.Rechtspersoon')
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)
    
    class Admin(EntityAdmin):
        verbose_name = _('Erkenningsnummers')
        list_display = ['type', 'number', 'issue_date']
        form_display = ['type', 'number', 'issue_date', 'note']
