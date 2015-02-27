import datetime
import os

import sqlalchemy.types
from sqlalchemy import schema

from camelot.core.orm import Entity, using_options, ManyToOne
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
import camelot.types
from camelot.core.utils import ugettext_lazy as _

class FinancialDocumentType( Entity ):
    using_options(tablename='financial_document_type', order_by=['description'])
    description = schema.Column( sqlalchemy.types.Unicode(48), nullable=False, index=True )
    
    def __unicode__(self):
        return self.description or ''
    
    class Admin( EntityAdmin ):
        verbose_name = _('Document Type')
        list_display = ['description']
  
class FinancialDocument( Entity ):
    using_options(tablename='financial_document')
    document_date = schema.Column( sqlalchemy.types.Date(), default = datetime.date.today, nullable=False, index = True )
    type = ManyToOne('FinancialDocumentType', required = True, ondelete = 'restrict', onupdate = 'cascade')
    financial_agreement = ManyToOne('FinancialAgreement', required = False, ondelete = 'set null', onupdate = 'cascade')
    financial_account = ManyToOne('FinancialAccount', required = False, ondelete = 'set null', onupdate = 'cascade')
    financial_transaction = ManyToOne('FinancialTransaction', required = False, ondelete = 'set null', onupdate = 'cascade')
    document = schema.Column( camelot.types.File(upload_to=os.path.join('financial_document', 'document') ) )
    description = schema.Column( sqlalchemy.types.Unicode(200) )
    summary = schema.Column( camelot.types.RichText() )
        
    class Admin(EntityAdmin):
        verbose_name = _('Document')
        list_display = ['document_date', 'type', 'document', 'description']
        form_display = list_display + ['summary']
        field_attributes = {'type':{'delegate':delegates.ManyToOneChoicesDelegate}}
