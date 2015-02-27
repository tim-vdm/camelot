import logging
import os

from camelot.admin.action import Action
from camelot.core.conf import settings
from camelot.core.utils import ugettext as _
from camelot.core.exception import UserException
from camelot.core.orm import Session

from camelot.admin.object_admin import ObjectAdmin
from camelot.view.controls import delegates
from camelot.view import action_steps

from vfinance.model.financial.work_effort import FinancialAccountNotification

LOGGER = logging.getLogger( 'vfinance.model.vfinance.connector.export_wizard' )

class ExportOptions( object ):
    
    def __init__( self ):
        self.from_book_date = None
        self.destination = settings.CLIENT_TEMP_FOLDER
        
    class Admin( ObjectAdmin ):
        verbose_name = _('Export Options')
        list_display = ['from_book_date', 'destination']
        field_attributes = { 'from_book_date':{'delegate':delegates.DateDelegate,
                                               'required':True,
                                               'editable':True},
                             'destination':{'delegate':delegates.LocalFileDelegate,
                                            'editable':True} 
                             }

rabo_templates = dict(
    nl = 'polis_%(full_account_number)s_%(rabo_id)s_%(year)i%(month)02d%(day)02d.xml',
    fr = 'police_%(full_account_number)s_%(rabo_id)s_%(year)i%(month)02d%(day)02d.xml',
)

class ExportAction( Action ):
    
    verbose_name = _('Export Wizard')
    
    def model_run( self, model_context ):
        options = ExportOptions()
        session = Session()
        yield action_steps.ChangeObject( options )
        query = session.query( FinancialAccountNotification ).filter( FinancialAccountNotification.entry_book_date >= options.from_book_date )
        total_notifications = query.count()
        for i, notification in enumerate( query.yield_per( 10 ).all() ):
            yield action_steps.UpdateProgress( i, total_notifications )
            premium_fulfillment = notification.get_premium_fulfillment()
            if premium_fulfillment:
                premium_schedule = premium_fulfillment.of
                from_date = premium_schedule.from_date
                account = premium_schedule.financial_account
                agreement = premium_schedule.agreed_schedule.financial_agreement
                origin = agreement.origin
                if origin and origin.startswith('rabobank:'):
                    yield action_steps.UpdateProgress( i, total_notifications, origin )
                    LOGGER.debug( 'export notification for origin %s'%origin )
                    language = account.get_language_at(premium_fulfillment.entry_doc_date, described_by='subscriber')
                    context = dict(
                        rabo_id = origin.split(':')[-1],
                        full_account_number = premium_schedule.full_account_number,
                        year = from_date.year,
                        month = from_date.month,
                        day = from_date.day,
                    )
                    notification.create_message( force = True )
                    message = notification.message
                    input_stream = message.storage.checkout_stream( message )
                    if language not in rabo_templates:
                        raise UserException( 'Unknown language %s'%language )
                    filename = rabo_templates[ language ]%context
                    output_stream = open( os.path.join( options.destination, filename ), 'wb' )
                    output_stream.write( input_stream.read() )
