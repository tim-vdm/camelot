import itertools
import logging
import tempfile
import os
import collections
import datetime

from camelot.view.art import Icon
from camelot.view.action_steps import ( ChangeObject, 
                                        WordJinjaTemplate, 
                                        OpenString, 
                                        PrintHtml,
                                        UpdateProgress, 
                                        OpenFile )
from camelot.core.exception import UserException
from camelot.view.utils import text_from_richtext
from camelot.core.conf import settings
from camelot.core.utils import ugettext_lazy as _
from camelot.model.authentication import end_of_times


from vfinance.admin.translations import Translations
from vfinance.model.financial.notification.utils import (broker,
                                                         get_recipient)
from vfinance.model.financial.summary.utils import get_premium_data
from vfinance.model.financial.constants import notification_types
from vfinance.model.bank.natuurlijke_persoon import burgerlijke_staten
from vfinance.model.bank.constants import fulfillment_types
from vfinance.model.financial.notification import NotificationOptions
from vfinance.model.financial.notification.premium_schedule_document import PremiumScheduleDocument
from vfinance.process import WorkerProcessException, Progress

from environment import TemplateLanguage

from utils import get_or_undefined_list, get_or_undefined_object, generate_qr_code

logger = logging.getLogger('vfinance.model.financial.notification.account_document')

account_notification_types = [(notification_type,notification_type) for (_id,notification_type,related_to,_ft) in notification_types if related_to == 'account']

account_movement_data = collections.namedtuple( 'account_movement_data',
                                                'movement_type, reference, amount' )

security_data = collections.namedtuple( 'security_data',
                                        'name, security, security_quotation, movements, from_value, thru_value, risk_deduction, from_quantity, thru_quantity' )

security_movement_data = collections.namedtuple( 'security_movement_data',
                                                 'doc_date, nav_date, movement_type, reference, amount, quantity, nav, transfer_revenue' )

premium_schedule_movement_data = collections.namedtuple( 'premium_schedule_movement_data',
                                                         'doc_date, movement_type, reference, amount, features' )

premium_schedule_state = collections.namedtuple( 'premium_schedule_state',
                                                 'premium_data, capital, interest, additional_interest, profit_sharing, value, uninvested, invested, thru_value, movements, funds_data' )

fund_data = collections.namedtuple('fund_data',
                                   'name, doc_date, niw, risk_type, quantity, value_overview_date, amount')

non_quotation_fulfillment_types = [ft[1] for ft in fulfillment_types if ft[1] != 'security_quotation']

"""
1.  Storting
2.  Taks
3.  Commissie (% voor de makelaars)
4.  Instapkost mpij (de kost voor de maatschappij, 35 EUR en dergelijke)
5.  Bonusallocatie
6.  Intrest
7.  Aanvullende intrest
8.  Winstdeelname
9.  Risicopremieonttrekking
10. Fondsinstap - uitstapkosten
11. Git-recuperatie
12. Afkoop
13. Afkoopkosten
14. Switch
15. Switchkosten
16. Roerende voorheffing
17. Rendement
"""
revenue_types = [ 'redemption_rate_revenue',
                  'redemption_fee_revenue',
                  'switch_revenue',
                  'taxes',
                  'premium_rate_1_revenue',
                  'premium_fee_1_revenue',
                  'premium_rate_2_revenue',
                  'premium_fee_2_revenue',
                  'premium_rate_3_revenue',
                  'premium_fee_3_revenue',
                  'premium_rate_4_revenue',
                  'premium_fee_4_revenue',
                  'premium_rate_5_revenue',
                  'premium_fee_5_revenue',
                  'entry_fee_revenue',
                  'funded_premium',
                  'market_fluctuation_revenue',
                  'effective_interest_tax',
                  'fictive_interest_tax',
                  ]

movement_type_order = [
    'sales',
    'taxes',
    'premium_rate_1_revenue',
    'premium_rate_2_revenue',
    'premium_rate_3_revenue',
    'premium_rate_4_revenue',
    'premium_rate_5_revenue',
    'premium_fee_1_revenue',
    'premium_fee_2_revenue',
    'premium_fee_3_revenue',
    'premium_fee_4_revenue',
    'premium_fee_5_revenue',
    'entry_fee_revenue',
    'funded_premium',
    'interest_attribution', 
    'additional_interest_attribution', 
    'profit_sharing_attribution',
    'risk_deduction',
    'transfer_revenue',
    'financed_commissions_deduction', 
    'redemption_attribution',
    'redemption_rate_revenue',
    'redemption_fee_revenue',
    'switch_revenue',         
    'effective_interest_tax',
    'fictive_interest_tax',
    'security_quotation',
    ]

movement_type_order = dict( (mt,i) for i,mt in enumerate( movement_type_order ) )

LOGGER = logging.getLogger('vfinance.model.financial.notification.account_document')
# special logger which will hold the account document context
CONTEXT_LOGGER = LOGGER.getChild('context')

class DocumentGenerationException(WorkerProcessException):
    """To be yielded when an exception takes place during
    document generation.  This object stores information of the
    exception for reuse

    :param extra: a serializable dictionary with additional context that can be
        used for logging.
    """

    def __init__(self, message, extra={}):
        super(DocumentGenerationException, self).__init__(message)
        self.extra = extra

class DocumentGenerationWarning(object):
    """To be yielded when an exception takes place during document
    document generation but the exit code should remain 0.
    This object stores information of the exception for reuse

    :param extra: a serializable dictionary with additional context that can be
        used for logging.

    """

    def __init__(self, message, extra={}):
        self.message = message
        self.extra = extra

class FinancialAccountDocument( PremiumScheduleDocument ):
   
    verbose_name = _('Account Document')
    icon = Icon( 'tango/16x16/mimetypes/x-office-document.png' ) 
 
    class Options( NotificationOptions ):
        
        def __init__(self):
            NotificationOptions.__init__( self )
            self.notification_type_choices = account_notification_types
            self.notification_type = self.notification_type_choices[0][0]
            
    def _create_document(self, environment, context, template):    
        template = template.replace('\\', '/')
        template = environment.get_template(template)
        document_xml = template.render(context)
        filedescriptor, filepath = tempfile.mkstemp(suffix='.xml')
        docx_file = os.fdopen(filedescriptor, 'w')
        docx_file.write(document_xml.encode('utf-8'))
        docx_file.close()
        logger.info( 'wrote document to %s'%filepath )
        return filepath
        
    def get_context(self, account, recipient, options=None):
        from ..visitor.abstract import (AbstractVisitor,
                                        FinancialBookingAccount,
                                        CustomerBookingAccount,
                                        SecurityBookingAccount)
        from ..visitor.supplier_attribution import distribution_fulfillment_types
        from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment as FAPF
        from vfinance.model.financial.transaction import FinancialTransactionPremiumSchedule as FTPS
        visitor = AbstractVisitor()

        debug = False
        if options==None:
            options = self.Options()
        elif hasattr(options, 'output_type'):
            if options.output_type == 1:
                debug = True
            
        subscriber_lang = account.get_language_at(options.notification_date, described_by='subscriber')
        premiums, premium_schedules, total = get_premium_data(account, options) # NOTE different from get_premium_schedule_data method !
        
        additional_information = [text_from_richtext(item.clause) for item in account.get_items_at(options.thru_document_date, described_by='additional_information')]
        
        value_overview = []
        premium_schedule_states = []
        value_overview_date = options.thru_document_date
        
        from_value = 0
        thru_value = 0
        uninvested = 0
        account_movements = []
        account_coverages_collection = []
        
        def value_and_quantity_at( premium_schedule, booking_accounts, document_date, fulfillment_type = None ):
            total_value, total_quantity = 0, 0
            for booking_account in booking_accounts:
                value, quantity = visitor.get_total_amount_until(premium_schedule, 
                                                                 thru_document_date = document_date,
                                                                 thru_book_date = options.thru_book_date,
                                                                 account = booking_account,
                                                                 fulfillment_type = fulfillment_type,
                                                                )[:2]
                total_value -= value
                total_quantity += quantity
            return total_value, total_quantity
        
        def value_between( premium_schedule, booking_accounts, fulfillment_type, line_number = None ):
            return sum( ( visitor.get_total_amount_until( premium_schedule, 
                                                          from_document_date = options.from_document_date,
                                                          thru_document_date = options.thru_document_date,
                                                          thru_book_date = options.thru_book_date,
                                                          account = booking_account,
                                                          fulfillment_type = fulfillment_type,
                                                          line_number = line_number,
                                                          )[0] * -1 for booking_account in booking_accounts ), 0 )
        
        
        funds = set()
        accounts = []

        for schedule in premium_schedules:

            account_numbers = set([FinancialBookingAccount('uninvested')])
            accounts.append( schedule.premium_schedule.full_account_number )
            fund_account_numbers = set()
            premium_schedule_movements = []

            #
            # premium schedule movements
            #
            for entry in visitor.get_entries( schedule.premium_schedule, 
                                              account = FinancialBookingAccount(),
                                              thru_document_date = options.thru_document_date,
                                              thru_book_date = options.thru_book_date,
                                              fulfillment_types = ['depot_movement', 'profit_attribution'] ):
                features = []
                for feature_description in ['interest_rate', 'additional_interest_rate', 'profit_sharing_rate']:
                    feature = schedule.premium_schedule.get_applied_feature_at( options.thru_document_date, entry.doc_date, -1 * entry.amount, feature_description )
                    if feature != None and feature.value != None:
                        features.append( feature )

                premium_schedule_movements.append( premium_schedule_movement_data( doc_date = entry.doc_date,
                                                                                   movement_type = entry.fulfillment_type,
                                                                                   reference = schedule.premium_schedule.agreement_code,
                                                                                   amount = -1 * entry.amount,
                                                                                   features = features ) )

            #
            # premium state
            #
            value_at_thru_date = lambda fulfillment_type:value_and_quantity_at( schedule.premium_schedule, account_numbers, options.thru_document_date, fulfillment_type)[0]
            capital = value_at_thru_date('depot_movement') + value_at_thru_date('capital_redemption_deduction' ) + value_at_thru_date('risk_deduction')
            interest = value_at_thru_date('interest_attribution' ) + value_at_thru_date('interest_redemption_deduction' )
            additional_interest = value_at_thru_date('additional_interest_attribution' ) + value_at_thru_date('additional_interest_redemption_deduction' )
            profit_sharing = value_at_thru_date('profit_attribution' )

            #
            # premiums coming in
            #
            account_movements.append( account_movement_data( movement_type = 'sales',
                                                             reference = schedule.premium_schedule.agreement_code,
                                                             amount = value_between( schedule.premium_schedule, [CustomerBookingAccount()], 'sales' ) * -1 )
                                      )

            #
            # redemptions going out
            #
            account_movements.append( account_movement_data( movement_type = 'redemption_attribution',
                                                             reference = schedule.premium_schedule.agreement_code,
                                                             amount = value_between( schedule.premium_schedule, [None], 'redemption_attribution', line_number = 1 ) * -1 )
                                      )

            #
            # all kinds of revenue and costs
            #
            all_entries = list( visitor.get_entries( schedule.premium_schedule,
                                                     from_document_date = options.from_document_date,
                                                     thru_document_date = options.thru_document_date,
                                                     thru_book_date = options.thru_book_date ) )
            total_amounts = collections.defaultdict( int )
            for entry in all_entries:
                if entry.fulfillment_type=='security_quotation':
                    continue
                if entry.fulfillment_type in distribution_fulfillment_types:
                    # these would bring the amounts back to 0
                    continue
                booking_account = visitor.get_booking_account(schedule.premium_schedule, entry.account, entry.book_date)
                account_type = booking_account.account_type_before_distribution()
                total_amounts[account_type] = total_amounts[account_type] + entry.amount

            for revenue_type in revenue_types:
                if total_amounts[revenue_type] != 0:
                    account_movements.append( account_movement_data( movement_type = revenue_type,
                                                                     reference = schedule.premium_schedule.agreement_code,
                                                                     amount = total_amounts[revenue_type] )
                                              )

            for fulfillment_type in ['interest_attribution', 
                                     'profit_attribution',
                                     'additional_interest_attribution', 
                                     'financed_commissions_deduction', 
                                     'financed_commissions_redemption_deduction',
                                     'risk_deduction',]:
                account_movements.append( account_movement_data( movement_type = fulfillment_type,
                                                                 reference = schedule.premium_schedule.agreement_code,
                                                                 amount = value_between( schedule.premium_schedule, account_numbers, fulfillment_type ) )
                                          )

            #
            # security quotations and fund revenues
            #
            fund_revenue_account_numbers = set()
            funds_data = []
            for distribution in schedule.fund_distributions:
                fund_account_number = FinancialBookingAccount( 'fund', distribution.fund_distribution.fund )
                account_numbers.add( fund_account_number )
                funds.add( (distribution.fund_distribution.fund, fund_account_number) )
                fund_account_numbers.add( fund_account_number )
                fund_revenue_account_numbers.add( SecurityBookingAccount( 'transfer_revenue', distribution.fund_distribution.fund ) )
                # add a line if there is currently some value, but this does not mean there were entries in
                # the given period
                if distribution.quantity:
                    fund = distribution.fund_distribution.fund
                    risk_assessment = fund.get_risk_assessment_at(options.thru_document_date)
                    if risk_assessment:
                        risk_type = risk_assessment.risk_type
                    else:
                        risk_type = 'Unknown'
                    if distribution.entries:
                        doc_date = distribution.entries[-1].doc_date
                    else:
                        doc_date = options.from_document_date
                    funds_data.append(fund_data(name=fund.name, 
                                                doc_date=doc_date,
                                                niw=distribution.amount/distribution.quantity,
                                                risk_type=risk_type,
                                                quantity=distribution.quantity,
                                                value_overview_date=value_overview_date,
                                                amount=distribution.amount))
            funds_data.sort(key=lambda fd:fd.name)

            account_movements.append( account_movement_data( movement_type = 'transfer_revenue',
                                                             reference = schedule.premium_schedule.agreement_code,
                                                             amount = -1 * value_between( schedule.premium_schedule, fund_revenue_account_numbers, fulfillment_type = None ) )
                                      )

            account_movements.append( account_movement_data( movement_type = 'security_quotation',
                                                             reference = schedule.premium_schedule.agreement_code,
                                                             amount = value_between( schedule.premium_schedule, fund_account_numbers, 'security_quotation' ) )
                                      )

            premium_schedule_thru_value = value_and_quantity_at( schedule.premium_schedule, account_numbers, options.thru_document_date )[0]
            from_value += value_and_quantity_at( schedule.premium_schedule, account_numbers, options.from_document_date - datetime.timedelta(days=1) )[0]
            thru_value += premium_schedule_thru_value
            premium_schedule_uninvested_thru_value = value_and_quantity_at( schedule.premium_schedule, [FinancialBookingAccount()], options.thru_document_date )[0]
            uninvested += premium_schedule_uninvested_thru_value
            account_coverages_collection.append(schedule.premium_schedule.applied_coverages)

            doc_date = options.thru_document_date
            ps_data = self.get_premium_schedule_data(schedule.premium_schedule,
                                                     doc_date)
            if premium_schedule_thru_value != 0 or sum(v.amount!=0 for _k, v in ps_data.movements.iteritems()):
                premium_schedule_states.append( premium_schedule_state( premium_data = ps_data,
                                                                        capital = capital,
                                                                        interest = interest,
                                                                        additional_interest = additional_interest,
                                                                        profit_sharing = profit_sharing,
                                                                        value = premium_schedule_thru_value,
                                                                        uninvested = premium_schedule_uninvested_thru_value,
                                                                        invested = premium_schedule_thru_value - premium_schedule_uninvested_thru_value,
                                                                        thru_value = premium_schedule_thru_value,
                                                                        movements = premium_schedule_movements,
                                                                        funds_data=funds_data ) )

        # sort premiums schedule states according to rank
        premium_schedule_states.sort(key=lambda pss:pss.premium_data.rank)
            
        securities = []
        for fund, fund_account_number in funds:
            movements = []
            risk_deduction = 0
            
            security_quotation = sum( value_between( ps, [fund_account_number], 'security_quotation' ) for ps in account.premium_schedules )

            for premium_schedule in account.premium_schedules:
                if not premium_schedule.product.unit_linked:
                    continue
                for entry in visitor.get_entries( premium_schedule, 
                                                  account = fund_account_number,
                                                  from_document_date = options.from_document_date,
                                                  thru_document_date = options.thru_document_date,
                                                  thru_book_date = options.thru_book_date,
                                                  fulfillment_types = non_quotation_fulfillment_types ):
                    transfer_revenue = 0 #@todo: query transfer revenue for each transaction if needed
                    if entry.associated_to_id:
                        associated_to = FAPF.get( entry.associated_to_id )
                        if not associated_to:
                            raise Exception( 'No assciated fulfillment found with id %s'%entry.associated_to_id )
                        movement_type = associated_to.fulfillment_type
                        doc_date = associated_to.entry_doc_date
                        if doc_date == None:
                            raise UserException( 'Missing document in accounting system',
                                                 resolution = '''Run the audit report to get more details, '''
                                                              '''and restore the booking in the accounting system''',
                                                 detail = '''Missing document : %s %s %s\n'''
                                                          '''Referring document : %s %s %s'''%( associated_to.entry_book_date,
                                                                                                associated_to.entry_book,
                                                                                                associated_to.entry_document,
                                                                                                entry.book_date,
                                                                                                entry.book,
                                                                                                entry.document ) )
                    elif entry.within_id:
                        movement_type = entry.fulfillment_type
                        ftps = FTPS.get( entry.within_id )
                        if ftps == None:
                            raise Exception( 'No financial transaction with id %s found'%entry.within_id )
                        doc_date = ftps.from_date_sql
                    else:
                        movement_type = entry.fulfillment_type
                        doc_date = entry.doc_date
                        
                    if movement_type != 'risk_deduction':
                        nav = ((entry.amount/entry.quantity) * -1) * 1000
                        movement = security_movement_data( doc_date = doc_date,
                                                           nav_date = entry.doc_date,
                                                           movement_type = movement_type, 
                                                           reference = u'', 
                                                           amount = -1 * entry.amount, 
                                                           quantity = entry.quantity/1000,
                                                           nav = nav,
                                                           transfer_revenue = transfer_revenue )
                        movements.append( movement )
                    else:
                        risk_deduction -= entry.amount
                
            keyfunc = lambda m:(m.doc_date, m.nav_date, m.movement_type, m.reference)
            movements.sort( key = keyfunc )
            grouped_movements = []
            for key, group in itertools.groupby( movements, keyfunc ):
                doc_date, nav_date, movement_type, reference = key
                group = list( group )
                amount = sum( m.amount for m in group)
                quantity = sum( m.quantity for m in group)
                nav = 0
                if quantity:
                    nav = 1000 * (amount/quantity)
                grouped_movements.append( security_movement_data( doc_date = doc_date,
                                                                  nav_date = nav_date,
                                                                  movement_type = movement_type, 
                                                                  reference = reference, 
                                                                  amount = amount, 
                                                                  quantity = quantity,
                                                                  nav = nav,
                                                                  transfer_revenue = sum( m.amount for m in group), ) )

            
            total_security_from_value, total_security_thru_value, total_security_from_quantity, total_security_thru_quantity = 0, 0, 0, 0
            for ps in account.premium_schedules:
                security_from_value, security_from_quantity = value_and_quantity_at( ps, [fund_account_number], options.from_document_date - datetime.timedelta(days=1) )
                security_thru_value, security_thru_quantity = value_and_quantity_at( ps, [fund_account_number], options.thru_document_date )
                total_security_from_value += security_from_value
                total_security_thru_value += security_thru_value
                total_security_from_quantity += security_from_quantity
                total_security_thru_quantity += security_thru_quantity
                
            securities.append( security_data( name = fund.name,
                                              security = fund,
                                              security_quotation = security_quotation,
                                              risk_deduction = risk_deduction,
                                              movements = movements,
                                              from_value = total_security_from_value,
                                              thru_value = total_security_thru_value,
                                              from_quantity = total_security_from_quantity,
                                              thru_quantity = total_security_thru_quantity,
                                              )
                               )


        #
        # Group and sort the account movements
        #
        grouped_account_movements = []
        groups = list( set( m.movement_type for m in account_movements ) )
        keyfunc = lambda mt:movement_type_order.get( mt, len( grouped_account_movements ) )
        groups.sort( key = keyfunc )   
        for movement_type in groups:
            amount = sum( m.amount for m in account_movements if m.movement_type == movement_type )
            grouped_account_movements.append( account_movement_data( movement_type = movement_type,
                                                                     reference = '',
                                                                     amount = amount ) )
        #
        # Sort the security data
        #
        keyfunc = lambda sd:sd.security.name
        securities.sort(key=keyfunc)
        #
        # Group and sort the value overview
        #
        grouped_value_overview = []
        keyfunc = lambda vo:(vo['fund'], vo['doc_date'], vo['value_overview_date'])
        groups = list( set( keyfunc(vo) for vo in value_overview ) )
        for key in groups:
            grouped_vo = dict( quantity = 0, amount = 0 )
            for vo in value_overview:
                if keyfunc( vo ) == key:
                    grouped_vo['quantity'] += vo['quantity']
                    grouped_vo['amount'] += vo['amount']
                    grouped_vo['fund'] = vo['fund']
                    grouped_vo['doc_date'] = vo['doc_date']
                    grouped_vo['value_overview_date'] = vo['value_overview_date']
                    grouped_vo['niw'] = vo['niw']
            grouped_value_overview.append( grouped_vo )
        grouped_value_overview.sort(key=keyfunc)
                    
        civil_states = {}
        for b in burgerlijke_staten:
            civil_states[b[0]]=b[1]
        _broker, _broker_registration = broker(account, options.notification_date)
        #
        # Sort the list of the cash accounts
        #
        accounts.sort()
        
        exit_condition = account.get_functional_setting_description_at(options.thru_document_date, 'exit_condition')

        return {
            'debug' : debug,
            'end_of_times' : end_of_times,
            # TODO 
            #   - is this always a DualPerson? if so:
            #   - get this data from namedtuple, which gets the data from dual_person.mail_street etc...
            'today' : datetime.date.today(),
            'now' : datetime.datetime.now(),
            'recipient' : recipient,
            'options': options,
            'accounts':accounts,
            'account': account,
            'package': account.package,
            'package_name': account.package.name,
            'account_id': account.id,
            'full_account_number': ([ps.full_account_number for ps in account.premium_schedules]+[''])[0],
            'language': subscriber_lang,
            'subscribers': get_or_undefined_list(account.get_roles_at(options.notification_date, described_by='subscriber')),
            'burgerlijke_staten': civil_states,
            'broker': get_or_undefined_object(_broker), 
            'broker_registration': _broker_registration,
            'additional_information': additional_information,
            # 'premium_schedules' : get_or_undefined_list(premium_schedules),
            # 'value_overview' : grouped_value_overview,
            'value_overview_date': value_overview_date,
            # 'value_overview_total': sum([row['amount'] for row in value_overview]),
            'from_value' : from_value,
            'thru_value' : thru_value,
            # 'uninvested' : uninvested,
            'premium_schedule_states' : premium_schedule_states,
            'account_movements' : grouped_account_movements,
            'securities' : securities,
            'account_coverages_collection' : account_coverages_collection, 
            'exit_at_first_deceased' : exit_condition=='exit_at_first_decease',
            'exit_at_last_deceased' : exit_condition=='exit_at_last_decease',
            'insured_parties': account.get_roles_at(options.thru_document_date, described_by='insured_party'),
            # TODO fill in if simulating or something that invalidates the document
            'invalidating_text': u'',
            'qr_base64': generate_qr_code()
        }

    def model_run(self, model_context):
        options = self.Options()
        yield ChangeObject( options )
        for step in self.generate_documents( model_context, options ):
            yield step
        
    def generate_documents( self, model_context, options ):
        from camelot.core.templates import environment
        destination_folder = None
        now = datetime.datetime.now()
        products_without_notification = set()
        doc =  None
        # need at least 1 step to fool the supergenerator
        yield UpdateProgress( text = 'Generate documents' )
        exception = False
        for i, account in enumerate( model_context.get_selection() ):
            yield UpdateProgress( i, model_context.selection_count, text = unicode( account ) )
            try:
                notification_found = False
                for notification in account.package.applicable_notifications:
                    language = account.get_language_at(options.notification_date, described_by='subscriber')
                    if notification.notification_type == options.notification_type and (notification.language == language or not notification.language):
                        notification_found = True
                        for recipient_role, _broker in account.get_notification_recipients(options.notification_date):
                            recipient = get_recipient([recipient_role])
                            context = self.get_context(account, recipient, options)
                            template = notification.template.replace('\\', '/')
                            with TemplateLanguage( language ):
                                if options.output_type == 2:
                                    html = '<html><head><title>Document Debug Context</title></head><body><h1>Context</h1><table border=1>'
                                    for context_element in context:
                                        html += '<tr><td>{0}</td><td>{1}</td></tr>'.format(context_element, context[context_element])
                                    html += '</table></body></html>'
                                    yield PrintHtml( html )
                                elif options.output_type == 5:
                                    translations_object = Translations(language)
                                    html = '<html><head><title>Document Debug Translations</title></head><body><h1>Context</h1><table border=1>'
                                    for entry in translations_object.po:
                                        html += '<tr><td>{0}</td><td>{1}</td></tr>'.format(entry.msgid, entry.msgstr.encode('ascii', 'xmlcharrefreplace'))
                                    html += '</table></body></html>'
                                    yield OpenString(html, suffix='.html')
                                elif options.output_type in (4, 1):
                                    if destination_folder == None:
                                        if options.output_dir is not None:
                                            destination_folder = options.output_dir
                                        else:
                                            destination_folder = tempfile.mkdtemp( dir = settings.CLIENT_TEMP_FOLDER )
                                    if not os.path.exists(destination_folder):
                                        os.mkdir(destination_folder)
                                    subfolder= options.get_document_folder( account )
                                    folder = os.path.join( destination_folder, subfolder or '' )
                                    if not os.path.exists(folder):
                                        os.mkdir(folder)
                                    doc = os.path.join( folder, options.filename.format( account = account,
                                                                                         recipient_role = recipient_role,
                                                                                         options = options,
                                                                                         package = account.package,
                                                                                         now = now ) + '.xml' )
                                    t = environment.get_template( template )
                                    template_stream = t.stream( context )
                                    template_stream.dump( open( doc, 'wb' ), encoding='utf-8' )
                                    CONTEXT_LOGGER.info(doc, extra=context)
                                    yield UpdateProgress( i, model_context.selection_count, unicode( account ) )
                                elif options.output_type == 0:
                                    yield WordJinjaTemplate(template, 
                                                            context=context)
                if not notification_found:
                    msg = u'No document could be created for account {0.id} {0.subscriber_1} (notification not defined)'.format(account)
                    msg2 = u'No notification of type {0} defined for package {1.name} on {2} (lang={3})'.format(options.notification_type,
                                                                                                                account.package,
                                                                                                                options.notification_date,
                                                                                                                account.get_language_at(options.notification_date, described_by='subscriber'))
                    yield DocumentGenerationWarning(msg)
                    yield DocumentGenerationWarning(msg2)
                    yield UpdateProgress(detail=msg)
                    yield UpdateProgress(detail=msg2)

            except Exception as exception:
                exc_msg = unicode(exception)
                yield DocumentGenerationException(exc_msg, {'account_id': account.id})
                yield Progress(exc_msg)
                yield UpdateProgress(detail=u'No document could be created for account {0.id} {0.subscriber_1}'.format(account))
                yield UpdateProgress(detail=exc_msg)
        if exception is not False:
            yield UpdateProgress(1, 1, blocking=True)
        if destination_folder != None:
            yield OpenFile(destination_folder)
        if products_without_notification:
            raise UserException( 'No documents of type %s were generated for %s'%( options.notification_type, ', '.join( list( products_without_notification ) ) ), 
                                 title='No documents generated', 
                                 resolution='Check if the product has an appropriate notification defined')

class FinancialTransactionAccountDocument(FinancialAccountDocument):
    
    def model_run( self, model_context ):
        accounts = set()
        for transaction in model_context.get_selection():
            for ftps in transaction.consisting_of:
                accounts.add( ftps.premium_schedule.financial_account )   
                
        class AccountModelContext( object ):
            
            selection_count = len(accounts)
            
            def get_selection( self ):
                for account in accounts:
                    yield account
                
        for step in super(FinancialTransactionAccountDocument, self).model_run(AccountModelContext()):
            yield step

        
