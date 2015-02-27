import datetime
import os
import logging
from StringIO import StringIO

from jinja2.exceptions import UndefinedError

import sqlalchemy.types
from sqlalchemy import sql, orm, schema

from camelot.admin.entity_admin import EntityAdmin
from camelot.admin.action import CallMethod, Action
from camelot.view.action_steps import OpenFile
from camelot.view import action_steps, forms
from camelot.core.orm import ( Entity, OneToMany, 
                               ManyToOne, using_options )
from camelot.model.authentication import end_of_times
from camelot.core.utils import ugettext_lazy as _
from camelot.core.orm import transaction
from camelot.core.templates import environment
from camelot.model.type_and_status import Status, StatusMixin
import camelot.types
from camelot.core.conf import settings
from camelot.core.exception import UserException
from camelot.admin.not_editable_admin import not_editable_admin

from vfinance.model.bank.dual_person import DualPerson
from vfinance.model.financial.package import FinancialNotificationApplicability
from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.admin.vfinanceadmin import VfinanceAdmin
from vfinance.model.bank.statusmixin import BankRelatedStatusAdmin

from constants import work_effort_statuses, notification_acceptance_statuses

from camelot.core.qt import QtGui, QtCore

LOGGER = logging.getLogger('vfinance.model.financial.work_effort')

class PrintDocuments( Action ):

    verbose_name = _('Print')

    def model_run(self, model_context):
        o = model_context.get_object()
        
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
         
        import tempfile
        destination_folder = tempfile.mkdtemp( dir = settings.CLIENT_TEMP_FOLDER )
        for notification in o.generator_of:
            yield
            account = notification.account
            message = notification.message
            if message:
                storage = message.storage
                stream = storage.checkout_stream( message )
                content = stream.read()
                nr = None
                broker = account.get_broker_at(notification.date)
                if broker is not None:
                    nr = broker_number(broker)
                if nr:
                    if not os.path.exists(os.path.join(destination_folder, nr)):
                        os.mkdir(os.path.join(destination_folder, nr))
                    dest = open(os.path.join(destination_folder, nr, message.name), 'w')
                else:
                    dest = open(os.path.join(destination_folder, message.name), 'w')
                dest.write(content)
        QtGui.QDesktopServices.openUrl( QtCore.QUrl.fromLocalFile( destination_folder ) )

class OpenZip( Action ):

    verbose_name = _('Zip')
    
    def model_run(self, model_context):
        import zipfile
        obj = model_context.get_object()
        filename = OpenFile.create_temporary_file( '.zip' )
        zip = zipfile.ZipFile( open(filename, 'wb'), 'w')
        for notification in obj.generator_of:
            message = notification.message
            if message:
                storage = message.storage
                stream = storage.checkout_stream( message )
                content = stream.read()
                zip.writestr(message.name, content )
        zip.close()
        yield OpenFile( filename )
        
class GenerateDocuments( Action ):
    
    verbose_name = _('Regenerate documents')
    
    def model_run( self, model_context ):
        for work_effort in model_context.get_selection():
            if work_effort.current_status == 'complete':
                raise Exception('Documents have been printed already')
            total = len( work_effort.generator_of )
            for i, notification in enumerate( work_effort.generator_of ):
                yield action_steps.UpdateProgress( i, total, unicode( notification ) )
                try:
                    notification.create_message()
                    yield action_steps.FlushSession( model_context.session )
                except UndefinedError as ue:
                    LOGGER.error('could not generate document', exc_info=ue)
                    yield action_steps.MessageBox( 'Could not create notification %s'%unicode( notification ) )
                except Exception, e:
                    LOGGER.error( 'could not generate document', exc_info=e )
                    yield action_steps.MessageBox( 'Could not create notification %s'%unicode( notification ) )
                    
class Complete( GenerateDocuments ):
    
    verbose_name = _('Complete')
    
    def model_run( self, model_context ):
        for work_effort in model_context.get_selection():
            if work_effort.current_status != 'closed':
                raise Exception( 'Task should be closed before it can be completed' )
            for step in super( Complete, self ).model_run( model_context ):
                yield step
            work_effort.change_status( 'completed' )
            yield action_steps.FlushSession( model_context.session )

class FinancialWorkEffort( Entity, StatusMixin ):
    using_options(tablename='financial_work_effort')
    status = Status( enumeration=work_effort_statuses )
    type = schema.Column(camelot.types.Enumeration([(1, 'notification')]), nullable=False, index=True, default='notification')
    generator_of = OneToMany('FinancialAccountNotification')
 
    def __unicode__( self ):
        return self.type
            
    @classmethod
    def get_open_work_effort(cls, type):
        """Get or create an open work effort of a certain type"""
        work_effort = cls.query.filter( sql.and_( cls.current_status==u'open',
                                                  cls.type==type ) ).first()
        if not work_effort:
            work_effort = cls(type=type)
            work_effort.change_status(u'open')
            work_effort.flush()
        return work_effort
        
    def close(self):
        if self.current_status != 'open':
            raise Exception('This task is not open and cannot be closed')
        self.change_status( 'closed' )
        
    @transaction
    def button_close(self):
        return self.close()
    
    class Admin(EntityAdmin):
        verbose_name = _('Printing job')
        verbose_name_plural = _('Printing jobs')
        list_display = ['id', 'type', 'current_status']
        form_display = forms.TabForm( [ ( _('Jobs'), list_display + ['generator_of'] ),
                                        ( _('Status'), ['status'] ) ] )
        list_filter = ['type', 'current_status']
        field_attributes = {'id':{'editable':False}, 
                            'type':{'editable':False},}
        form_actions = [CallMethod( _('Close'),
                                    lambda obj:obj.button_close(),
                                    enabled = lambda obj:obj.current_status in ['open']),
                        Complete(),
                        GenerateDocuments(),
                        PrintDocuments(),
                        OpenZip() ]                                                                                                                                                                                         

class FinancialNotificationApplicabilityWorkEffortAdmin(FinancialNotificationApplicability.Admin):
    list_display = ['available_for', 'notification_type', 'premium_period_type', 'template', 'language','from_date', 'thru_date']
        
class FinancialAccountNotification( DualPerson ):
    """A notification is a dual person to which the document should be sent"""
    using_options(tablename='financial_account_notification')
    __table_args__ = ( schema.CheckConstraint('natuurlijke_persoon is not null or rechtspersoon is not null', name='financial_account_notification_persoon_fk'), )
    generated_by = ManyToOne('FinancialWorkEffort', required=True)
    date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True, default=datetime.date.today)
    balance = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=2), nullable=False, default=0)
    application_of = ManyToOne('vfinance.model.financial.package.FinancialNotificationApplicability', required=True, ondelete='restrict', onupdate='cascade')
    message = schema.Column(camelot.types.File(upload_to=os.path.join('financial.work_effort.financial_account_notification', 'message')))
    account = ManyToOne('vfinance.model.financial.account.FinancialAccount', required=True, ondelete='restrict', onupdate='cascade')
    entry_book_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True)
    entry_document = schema.Column(sqlalchemy.types.Integer(), nullable=False, index=True)
    entry_book = schema.Column(sqlalchemy.types.Unicode(25), nullable=False, index=True)
    entry_line_number = schema.Column(sqlalchemy.types.Integer(), nullable=False, index=True)
    # dual person fields
    natuurlijke_persoon_id = schema.Column(sqlalchemy.types.Integer(), name='natuurlijke_persoon')
    natuurlijke_persoon  =  ManyToOne( 'vfinance.model.bank.natuurlijke_persoon.NatuurlijkePersoon', field=natuurlijke_persoon_id,
                                       ondelete = 'restrict', onupdate = 'cascade',
                                       backref = orm.backref('notifications_sent', passive_deletes = True ) )
    rechtspersoon_id = schema.Column(sqlalchemy.types.Integer(), name='rechtspersoon')
    rechtspersoon  =  ManyToOne( 'vfinance.model.bank.rechtspersoon.Rechtspersoon', field=rechtspersoon_id,
                                 ondelete = 'restrict', onupdate = 'cascade',
                                 backref = orm.backref('notifications_sent', passive_deletes = True ) )
    
    @property
    def type(self):
        if self.application_of:
            return self.application_of.notification_type
    
    @property
    def template(self):
        if self.application_of:
            return self.application_of.template
    
    def get_premium_fulfillment( self ):
        """:return: the FinancialAccountPremiumFulfillment that triggered
        the generation of this notification"""
        from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment
        return FinancialAccountPremiumFulfillment.query.filter_by( entry_book_date=self.entry_book_date,
                                                                   entry_document=self.entry_document,
                                                                   entry_book=self.entry_book,
                                                                   entry_line_number=self.entry_line_number).first()
    
    def get_context( self ):
        from vfinance.model.financial.notification.transaction_document import TransactionDocument
        from vfinance.model.financial.notification.premium_schedule_document import PremiumScheduleDocument
        from vfinance.model.financial.notification.utils import get_recipient

        transaction_document = TransactionDocument()
        premium_schedule_document = PremiumScheduleDocument()
        
        context = {}
        premium_fulfillment = self.get_premium_fulfillment()
        if premium_fulfillment:
            if premium_fulfillment.within:
                context.update( transaction_document.get_context(premium_fulfillment.within.within, 
                                                                 recipient=get_recipient([self]), 
                                                                 options=None))
            else:
                context.update( premium_schedule_document.get_context( premium_fulfillment.of, 
                                                                       get_recipient([self]),
                                                                       options = None,
                                                                       premium_fulfillment = premium_fulfillment ) )
        return context
        
    def create_message(self, force = False):
        """
        :param force: if True, then do not reuse the exisiting message if available
        """
        from sqlalchemy import orm
        mapper = orm.class_mapper(self.__class__)
        property = mapper.get_property(
                    'message',
                )
        type = property.columns[0].type
        storage = type.storage

        if force or (not self.message):
            # find out for which premium the notification should be created            
            premium_fulfillment = self.get_premium_fulfillment()
            # now create the cerfificate
            if premium_fulfillment:
                context = self.get_context()
                language = premium_fulfillment.of.financial_account.get_language_at(self.date, described_by='subscriber')
                with TemplateLanguage( language ):
                    if self.application_of.language and language != self.application_of.language:
                        raise UserException( text = u'Language of template ({0}) and language of receiver ({1}) do not match.'.format(self.application_of.language, language),
                                             detail = u'',
                                             resolution = u'Please contact vendor' )
                    else:
                        template_name = self.application_of.template.replace('\\', '/')
                    LOGGER.debug( 'use template "%s"'%(template_name) )
                    template = environment.get_template( template_name )
                    document = template.render(context)
                    filename_prefix = '%s-%s-%s-%s'%( premium_fulfillment.of.account_number, 
                                                      self.entry_book_date.year, 
                                                      self.entry_book, 
                                                      self.entry_document )
                    if template_name.endswith( '.html' ):
                        text_document = QtGui.QTextDocument()
                        text_document.setHtml( document )
                        printer = QtGui.QPrinter()
                        printer.setPageSize( QtGui.QPrinter.A4 )
                        printer.setOutputFormat( QtGui.QPrinter.PdfFormat )
                        printer.setPageMargins( 20.0, 5.0, 20.0, 10.0, QtGui.QPrinter.Millimeter )
                        temp_file = action_steps.OpenFile.create_temporary_file('.pdf')
                        printer.setOutputFileName( temp_file )
                        text_document.print_( printer )
                        stored_file = storage.checkin( temp_file, filename = filename_prefix + '.pdf' )
                    else:
                        message = StringIO( document.encode('utf-8') )
                        stored_file = storage.checkin_stream( filename_prefix, '.xml', message )
                    self.message = stored_file
            else:
                LOGGER.warn('no premium fulfillment found for notification %s'%self.id)
        else:
            LOGGER.debug('document already generated, doing nothing')
            
    def __unicode__(self):
        return '%s %s %s'%( self.entry_book_date, self.entry_book, self.entry_document )
    
    class Admin(BankRelatedStatusAdmin):
        verbose_name = _('Account Notification')
        list_display = ['id', 'account', 'date', 'type', 'balance', 'name', 'message', 'generated_by']
        form_display = forms.Form( list_display + [ 'application_of', 'template', 'entry_book_date', 'entry_book', 
                                                    'entry_document', 'natuurlijke_persoon', 'rechtspersoon' ], columns = 2 )
        field_attributes = {'id':{'editable':False},
                            'name':{'name':_('Recipient')},
                            'generated_by':{'name':_('Job')},
                            'application_of':{'admin':not_editable_admin(FinancialNotificationApplicabilityWorkEffortAdmin)}}
        form_actions = [ CallMethod( _('Generate document'),
                                     lambda obj:obj.create_message(),),]

        def get_related_status_object(self, obj):
            return obj.account


class FinancialAccountNotificationAcceptance( Entity, StatusMixin ):
    using_options(tablename='financial_account_notification_acceptance')
    acceptance_of = ManyToOne('FinancialAccountNotification', required=True, ondelete='restrict', onupdate='cascade')
    document = schema.Column(camelot.types.File(upload_to=os.path.join('financial.work_effort.financial_account_notification_acceptance', 'document')))
    reception_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True, default=datetime.date.today)
    post_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True)
    status = Status( enumeration=notification_acceptance_statuses )
           
    def accept(self):
        if self.current_status!='draft':
            raise Exception('Notification can only be accepted in draft status')
        self.change_status('accepted')
        
    def decline(self):
        if self.current_status!='draft':
            raise Exception('Notification can only be declined in draft status')
        self.change_status('declined')
        
    @transaction
    def button_accept(self):
        return self.accept()
    
    @transaction
    def button_decline(self):
        return self.decline()
    
    class Admin(VfinanceAdmin):
        
        def flush(self, obj):
            """Set the status of the acceptance to draft if it has no status yet"""
            if not len(obj.status):
                obj.status.append(self.get_field_attributes('status')['target'](status_from_date=datetime.date.today(),
                                                                                status_thru_date=end_of_times(),
                                                                                classified_by='draft'))
            EntityAdmin.flush(self, obj)
            
        def get_dynamic_field_attributes(self, obj, field_names):
            """Make sure all field are only editable in draft status"""
            field_names = list(field_names)
            dynamic_field_attributes = list(super(EntityAdmin, self).get_dynamic_field_attributes(obj, field_names))
            static_field_attributes = list(super(EntityAdmin, self).get_static_field_attributes(field_names))
            if obj.current_status in (None, 'draft',):
                editable = True
            else:
                editable = False
            for static_attributes, dynamic_attributes in zip(static_field_attributes, dynamic_field_attributes):
                if static_attributes.get('editable', True)==False:
                    dynamic_attributes['editable'] = False
                else:
                    dynamic_attributes['editable'] = editable
            return dynamic_field_attributes
            
        verbose_name = _('Acceptance')
        list_display = ['acceptance_of', 'reception_date', 'post_date', 'current_status']
        form_display = forms.Form( list_display + ['document'], columns = 1 )
        field_attributes = {'current_status':{'editable':True}}
        form_actions = [ CallMethod( _('Accept'),
                                     lambda obj:obj.button_accept(),
                                     enabled = lambda obj:obj.current_status in ['draft']),
                         CallMethod( _('Decline'),
                                     lambda obj:obj.button_decline(),
                                     enabled = lambda obj:obj.current_status in ['draft']),]
