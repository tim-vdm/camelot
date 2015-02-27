import datetime

from camelot.core.utils import ugettext_lazy as _
from camelot.admin.object_admin import ObjectAdmin
from camelot.view.controls import delegates
from camelot.view import forms

from vfinance.model.financial.constants import document_output_types
        
class NotificationOptions(object):
    
    def __init__(self):
        self.notification_type = None
        self.notification_date = datetime.date.today()
        self.from_document_date = datetime.date( 2000, 1, 1 )
        self.thru_document_date = datetime.date.today()
        self.from_book_date = datetime.date(2000,1,1)
        self.thru_book_date = datetime.date.today()
        self.notification_type_choices = []
        self.output_type = 0
        self.output_dir = None
        self.filename = u'{account.account_suffix}_{account.subscriber_1}_{package.name}_{account.broker}_{options.notification_type}_{recipient_role.id}'
        
    def get_document_folder( self, financial_account ):
        
        def broker_number(broker):
            nr = None
            if broker.broker_agent:
                nr = broker.broker_agent.name
                if not nr:
                    for commercial_relation in broker.broker_agent.commercial_relations_from:
                        if commercial_relation.type=='distributor':
                            nr = commercial_relation.name
            elif broker.broker_relation:
                 nr = broker.broker_relation.name
            return nr
        
        brokername = 'default'
        for b in financial_account.brokers:
            if b.thru_date >= datetime.date.today() and b.from_date <= datetime.date.today():
                brokername = broker_number(b)
                break
            
        return brokername
                    
    class Admin(ObjectAdmin):
        verbose_name = _('Notification Options')
        form_display = forms.Form(['notification_type',
                                   'notification_date',
                                   'from_document_date',
                                   'thru_document_date',
                                   'from_book_date',
                                   'thru_book_date',
                                   'output_type',
                                   'output_dir',
                                   'filename'])
        
        field_attributes = {'notification_type':{'choices':lambda obj:obj.notification_type_choices,
                                                 'editable':True,
                                                 'nullable':False,
                                                 'delegate':delegates.ComboBoxDelegate},
                            'notification_date':{'delegate':delegates.DateDelegate, 
                                                 'nullable':False,
                                                 'editable':True},                            
                            'from_document_date':{'delegate':delegates.DateDelegate, 
                                                  'nullable':False,
                                                  'editable':True},
                            'thru_document_date':{'delegate':delegates.DateDelegate, 
                                                  'nullable':False,
                                                  'editable':True},
                            'from_book_date':{'delegate':delegates.DateDelegate, 
                                              'nullable':False,
                                              'editable':True},
                            'thru_book_date':{'delegate':delegates.DateDelegate, 
                                              'nullable':False,
                                              'editable':True},
                            'output_type':{'choices':document_output_types,
                                           'delegate':delegates.ComboBoxDelegate,
                                           'editable':True},
                            'output_dir':{'delegate':delegates.LocalFileDelegate,
                                         'directory':True,
                                         'editable':True},
                            'filename':{'editable':True},
                            }
