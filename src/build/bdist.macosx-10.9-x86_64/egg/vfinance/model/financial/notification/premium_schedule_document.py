# coding=utf-8
import collections
import datetime
import logging
from collections import defaultdict
import traceback

LOGGER = logging.getLogger('vfinance.model.financial.notification')

from integration.tinyerp.convenience import (months_between_dates,
                                             add_months_to_date)

from sqlalchemy import sql

from jinja2.exceptions import UndefinedError

from camelot.admin.action import Action
from camelot.core.exception import UserException
from camelot.core.utils import ugettext_lazy as _
from camelot.view.utils import text_from_richtext

from camelot.view.action_steps import ( ChangeObject, 
                                        WordJinjaTemplate, 
                                        PrintJinjaTemplate,
                                        PrintHtml )

from ...bank.constants import period_types, product_features_description
from vfinance.model.financial.constants import amount_types
from vfinance.model.financial.formulas import get_rate_at, get_amount_at
from vfinance.model.financial.notification import NotificationOptions
from vfinance.model.financial.notification.utils import (subscriber_types,
                                                         broker,
                                                         get_or_undefined_list,
                                                         get_or_undefined_object,
                                                         get_recipient,
                                                         calculate_duration,
                                                         generate_qr_code)
from vfinance.model.financial.constants import ( notification_types,
                                                 notification_type_fulfillment_types,
                                                 rate_types )
from vfinance.model.bank.natuurlijke_persoon import burgerlijke_staten

from environment import TemplateLanguage

premium_data = collections.namedtuple( 'premium_data',
                                       [ 'premium_schedule',
                                         'product_name',
                                         'base_product_name',
                                         'unit_linked',
                                         'profit_shared',
                                         'duration_months',
                                         'payment_duration_months',
                                         'number_of_payments',
                                         'funds',
                                         # movements: what really happened
                                         'movements',
                                         'features',
                                         'rates',
                                         'coverages',
                                         # amounts: what was agreed upon
                                         'amounts',
                                         # additional information
                                         'rank',
                                         # dates
                                         'valid_from_date',
                                         'valid_thru_date',
                                         'payment_thru_date',
                                         'increase_rate',
                                         ] )

premiums_summary = collections.namedtuple('premiums_summary',
                                          ['movements'])

fund_data = collections.namedtuple( 'fund_data',
                                    ['name', 
                                     'risk_type', 
                                     'target_percentage', 
                                     'target_amount' ] )

coverage_data = collections.namedtuple( 'coverage_data',
                                        ['reference_number',
                                         'coverage_limit',
                                         'duration',
                                         'from_date', 
                                         'thru_date', 
                                         'type',
                                         'insured_capitals', 
                                         'loan' ] )

loan_data = collections.namedtuple('loan_data',
                                   ['loan_amount', 
                                    'interest_rate',
                                    'periodic_interest', 
                                    'number_of_months', 
                                    'type_of_payments', 
                                    'payment_interval', 
                                    'repayment_amount',
                                    'number_of_repayments',
                                    'starting_date', 
                                    'credit_institution'])

insured_capital_data = collections.namedtuple( 'insured_capital_data',
                                               ['from_date', 
                                                'insured_capital'] )

class PremiumScheduleDocument( Action ):

    verbose_name = _('Document')

    class Options(NotificationOptions):

        def __init__(self):
            NotificationOptions.__init__( self )
            self.notification_type_choices = [(notification_type,notification_type) for (_id,notification_type,related_to,_nt) in notification_types if related_to == 'premium_schedule']
            self.notification_type = self.notification_type_choices[0][0]

    def model_run( self, model_context ):
        premium_schedule = model_context.get_object()
        account = premium_schedule.financial_account
        options = self.Options()
        yield ChangeObject( options )
        language = account.get_language_at(options.notification_date)

        printed = False

        for notification in premium_schedule.get_applied_notifications_at(premium_schedule.valid_from_date,
                                                                          options.notification_type,
                                                                          language):
            if notification.notification_type == options.notification_type:
                for recipient_role, _broker in account.get_notification_recipients(options.notification_date):
                    context = self.get_context(premium_schedule, get_recipient([recipient_role]), options)
                    if options.output_type == 1:
                        html = '<html><head><title>Document Debug Context</title></head><body><h1>Context</h1><table border=1>'
                        for context_element in context:
                            html += '<tr><td>{0}</td><td>{1}</td></tr>'.format(context_element, context[context_element])
                        html += '</table></body></html>'
                        yield PrintHtml(html)
                    with TemplateLanguage(language):
                        if '.' in notification.template and notification.template.split(".")[-1] == 'html':
                            print_jinja_template = PrintJinjaTemplate( notification.template.replace('\\', '/'),
                                                                       context = context )
                            # set margins conform to model.finacnial.work_effort.py:FinancialAccountNotification.create_message
                            print_jinja_template.margin_left = 20.0
                            print_jinja_template.margin_top = 5.0
                            print_jinja_template.margin_right = 20.0 
                            print_jinja_template.margin_bottom = 10.0
                            yield print_jinja_template
                        else:
                            try:
                                yield WordJinjaTemplate(notification.template.replace('\\', '/'),
                                                        context=context)
                            except UndefinedError:
                                raise UserException('Document could not be created',
                                                    resolution='Please check the product definition',
                                                    detail=unicode(traceback.format_exc(), 'utf-8'))
                    printed = True
        if not printed:
            raise UserException( 'No documents of type %s were printed' % options.notification_type,
                                 title='No documents generated',
                                 resolution='Check if the package has an appropriate notification defined')

    def get_context( self, premium_schedule, recipient, options, premium_fulfillment = None ):
        from ..premium import FinancialAccountPremiumFulfillment as FAPS
        from .account_document import account_movement_data
        amount_summary = defaultdict(int)
        quantity_summary = defaultdict(int)
        date_summary = defaultdict(str)
        #
        # If the premium fulfillment is associated to a parent fulfillment,
        # query all the childs of the parent fulfillment
        #
        # This is to gather investment information from multiple funds in case
        # of an investment confirmation.
        #
        notification_type, premium_fulfillment = self._notification_type_premium_fulfillment(premium_schedule, options, premium_fulfillment)
        premium_fulfillments = set( [premium_fulfillment] )
        if premium_fulfillment.associated_to:
            parent_fulfillment = premium_fulfillment.associated_to
            premium_fulfillments.add( parent_fulfillment )
            for child_premium_fulfillment in FAPS.query.filter( FAPS.associated_to == parent_fulfillment ):
                premium_fulfillments.add( child_premium_fulfillment )

        entries = set()

        for gathered_premium_fulfillment in premium_fulfillments:
            for entry in gathered_premium_fulfillment.entry.same_document:
                entries.add( entry )

        for entry in entries:
            amount_summary[entry.account] += entry.amount
            quantity_summary[entry.account] += entry.quantity
            date_summary[entry.account] = entry.doc_date

        # from vfinance.model.financial.constants import period_types_by_granularity
        account = premium_schedule.financial_account
        invested_amount = premium_schedule.agreed_schedule
        agreement = invested_amount.financial_agreement

        premiums_data = []
        total_movements = collections.defaultdict(self._no_movement )
        for ps in premium_schedule.financial_account.premium_schedules:
            doc_date = premium_fulfillment.entry_doc_date
            notification_fulfillment_types = notification_type_fulfillment_types.get( notification_type, [] )
            ps_data = self.get_premium_schedule_data(ps, doc_date, notification_fulfillment_types)
            if sum(v.amount!=0 for _k, v in ps_data.movements.iteritems()):
                premiums_data.append( ps_data )
                for movement_type, movement in ps_data.movements.iteritems():
                  total_movement = total_movements[movement_type]
                  total_movements[movement_type] = account_movement_data(movement_type=movement_type,
                                                                         reference=movement.reference,
                                                                         amount=total_movement.amount + movement.amount )
        
        # sort premiums schedule states according to rank
        premiums_data.sort(key=lambda pd:pd.rank)

        pss_summary = premiums_summary(movements=total_movements)

        all_items = account.get_items_at(premium_fulfillment.entry_doc_date)
        beneficiary_items = account.get_items_at(premium_fulfillment.entry_doc_date, described_by='beneficiary')
        conventional_return_items = account.get_items_at(premium_fulfillment.entry_doc_date, described_by='conventional_return')
        # text_from_richtext returns a list! so this is a list of lists
        account_items = [text_from_richtext(item._get_shown_clause()) for item in beneficiary_items + conventional_return_items]
        special_agreed_items = [text_from_richtext(item._get_shown_clause()) for item in all_items if item not in beneficiary_items + conventional_return_items] 
        roles = account.get_roles_at(premium_fulfillment.entry_doc_date)
        _broker, _broker_registration = broker(account, premium_fulfillment.entry_doc_date)
        civil_states = {}
        for b in burgerlijke_staten:
            civil_states[b[0]]=b[1]
        _subscribers = account.get_roles_at(premium_fulfillment.entry_doc_date, described_by='subscriber')
        _subscriber_types = subscriber_types(_subscribers)
        subscriber_lang = account.get_language_at(premium_fulfillment.entry_doc_date, described_by='subscriber')
        exit_condition = account.get_functional_setting_description_at(premium_fulfillment.entry_doc_date, 'exit_condition')

        # NOTE get_roles_at from DossierMixin (model.bank.dossier.py)
        context = {
            'premiums_data': premiums_data,
            'premiums_summary': pss_summary,
            'account_text' : text_from_richtext(account.text),
            'roles' : roles,
            'burgerlijke_staten': civil_states,
            'subscribers' : get_or_undefined_list(_subscribers),
            'subscriber_types' : _subscriber_types,
            'language': subscriber_lang,
            # TODO 
            #   - get this data from namedtuple, which gets the data from dual_person.mail_street
            #   - find solution for broker_relation case
            #   - try to remove util function
            'broker': get_or_undefined_object(_broker),
            'broker_registration': get_or_undefined_object(_broker_registration),
            'renters' : get_or_undefined_list(account.get_roles_at(premium_fulfillment.entry_doc_date, described_by='renter')),
            'insured_parties' : get_or_undefined_list(account.get_roles_at(premium_fulfillment.entry_doc_date, described_by='insured_party')),
            'payers': get_or_undefined_list(account.get_roles_at(premium_fulfillment.entry_doc_date, described_by='payer')),
            'assets' : [asset_usage.asset_usage for asset_usage in account.assets],
            'today' : datetime.date.today(),
            'now' : datetime.datetime.now(),
            'account' : get_or_undefined_object(account),
            'recipient' : get_or_undefined_object(recipient),
            'agreement' : get_or_undefined_object(agreement),
            'full_account_number': premium_schedule.full_account_number,
            'exit_at_first_deceased' : exit_condition=='exit_at_first_decease',
            'exit_at_last_deceased' : exit_condition=='exit_at_last_decease',
            'account_items' : account_items,
            'special_agreed_items':special_agreed_items,
            'package_name': premium_schedule.financial_account.package.name,
            'amount_summary': amount_summary,
            'quantity_summary': quantity_summary,
            'date_summary': date_summary,
            'pledged': False,  # verpanding
            # TODO fill in if simulating or something that invalidates the document
            'invalidating_text': u'',
            'qr_base64': generate_qr_code()
        }
        context['debug'] = False
        if options and hasattr(options, 'output_type') and options.output_type == 1:
            context['debug'] = True
        return context

    def get_coverages_data(self, premium_schedule, doc_date):
        from vfinance.model.financial.visitor.provision import ProvisionVisitor
        provision_visitor = ProvisionVisitor()
        coverages_data = []
        for idx, coverage in enumerate(premium_schedule.get_coverages_at(doc_date)):
            insured_party_data = premium_schedule.get_insured_party_data( doc_date )
            amortization = insured_party_data.amortization
            insured_capitals_data = []
            for month in range(0, months_between_dates(coverage.from_date, coverage.thru_date)+1):
                coverage_date = add_months_to_date(coverage.from_date, month)
                insured_capital = provision_visitor.insured_capital_at( coverage_date,
                                                                        coverage,
                                                                        amortization = amortization )
                insured_capitals_data.append( insured_capital_data( from_date = coverage_date,
                                                                    insured_capital = insured_capital ) )
                
            if coverage.coverage_amortization:
                _loan_data = loan_data(loan_amount = coverage.coverage_amortization.loan_amount,
                                       interest_rate = coverage.coverage_amortization.interest_rate,
                                       periodic_interest = coverage.coverage_amortization.periodic_interest,
                                       number_of_months = coverage.coverage_amortization.number_of_months,
                                       type_of_payments = coverage.coverage_amortization.type_of_payments,
                                       payment_interval = dict(period_types)[coverage.coverage_amortization.payment_interval],
                                       repayment_amount=None,
                                       number_of_repayments=None,
                                       starting_date = coverage.coverage_amortization.starting_date,
                                       credit_institution = coverage.coverage_amortization.credit_institution)
            else:
                _loan_data = None

            coverages_data.append( coverage_data(reference_number=idx,
                                                 coverage_limit=coverage.coverage_limit,
                                                 duration=calculate_duration(coverage.from_date, coverage.thru_date),
                                                 from_date=coverage.from_date,
                                                 thru_date=coverage.thru_date,
                                                 type=coverage.coverage_for.type,
                                                 insured_capitals=insured_capitals_data,
                                                 loan=_loan_data))
        return coverages_data

    def get_premium_schedule_data(self,
                                  premium_schedule,
                                  doc_date,
                                  notification_fulfillment_types=None,
                                  tables = None):
        from vfinance.model.financial.visitor.security_orders import SecurityOrdersVisitor
        from account_document import account_movement_data
        visitor = SecurityOrdersVisitor(tables=tables)
        #
        # get all documents of the same fulfillment type at the same date
        #
        document_entries = list( visitor.get_entries(premium_schedule,
                                                     from_document_date=doc_date,
                                                     thru_document_date=doc_date,
                                                     fulfillment_types=notification_fulfillment_types))

        product = premium_schedule.product

        total_account_amounts = collections.defaultdict( int )
        for entry in document_entries:
            booking_account = visitor.get_booking_account(premium_schedule, entry.account, entry.book_date)
            account_type = booking_account.account_type_before_distribution()
            total_account_amounts[account_type] = total_account_amounts[account_type] - entry.amount
            
        movements = collections.defaultdict(self._no_movement )
        for account_type, total_amount in total_account_amounts.items():
            if account_type == 'customer':
                movement_type = 'sales'
            elif account_type == 'uninvested':
                movement_type = 'depot_movement'
            else:
                movement_type = account_type
            movements[ movement_type ] = account_movement_data( movement_type = movement_type,
                                                                reference = '',
                                                                amount = total_amount )


        sales_amount = movements['sales'].amount * -1
        depot_movement_amount = movements['depot_movement'].amount * -1

        features = dict()
        for feature_type, _description in product_features_description.items():
            feature = premium_schedule.get_applied_feature_at(doc_date,
                                                              doc_date,
                                                              sales_amount,
                                                              feature_type,
                                                              default=0)
            features[ feature_type ] = feature.value

        rates = dict()
        for rate_type in rate_types:
            rates[rate_type] = get_rate_at(premium_schedule,
                                           sales_amount,
                                           doc_date,
                                           doc_date,
                                           rate_type )

        amounts = {}
        for amount_type in amount_types:
            amounts[amount_type] = get_amount_at(premium_schedule,
                                                 premium_schedule.premium_amount,
                                                 premium_schedule.fulfillment_date,
                                                 premium_schedule.fulfillment_date,
                                                 amount_type)

        funds_data = []
        for fund_distribution, target_amount in visitor.get_amounts_to_invest( premium_schedule, depot_movement_amount, doc_date ):
            fund = fund_distribution.fund
            risk_assessment = fund.get_risk_assessment_at( doc_date )
            if risk_assessment:
                risk_type = risk_assessment.risk_type
            else:
                risk_type = 'Unknown'
            funds_data.append( fund_data( name = fund.name,
                                          risk_type = risk_type,
                                          target_percentage = fund_distribution.target_percentage,
                                          target_amount = target_amount ) )

        coverages_data = self.get_coverages_data(premium_schedule, doc_date)

        ps_data = premium_data( premium_schedule = premium_schedule,
                                product_name = product.name,
                                base_product_name = product.base_product or '',
                                unit_linked = product.unit_linked,
                                profit_shared = product.profit_shared,
                                duration_months = months_between_dates(premium_schedule.valid_from_date,
                                                                       premium_schedule.valid_thru_date),
                                payment_duration_months = months_between_dates(premium_schedule.valid_from_date,
                                                                               premium_schedule.payment_thru_date),
                                number_of_payments = premium_schedule.planned_premiums,
                                movements = movements,
                                features = features,
                                amounts = amounts,
                                rates = rates,
                                funds = funds_data,
                                coverages = coverages_data,
                                rank = premium_schedule.rank,
                                valid_from_date = premium_schedule.valid_from_date,
                                valid_thru_date = premium_schedule.valid_thru_date,
                                payment_thru_date = premium_schedule.payment_thru_date,
                                increase_rate = premium_schedule.increase_rate,
                                )

        return ps_data

    def _no_movement(self):
        from account_document import account_movement_data
        return account_movement_data(movement_type = None,
                                     reference = '',
                                     amount = 0)

    def _create_documents(self, environment, context, template):
        import tempfile
        import os
        template = environment.get_template(template.replace('\\', '/'))
        document_xml = template.render(context)
        filedescriptor, filepath = tempfile.mkstemp(suffix='.xml')
        docx_file = os.fdopen(filedescriptor, 'w')
        docx_file.write(document_xml.encode('utf-8'))
        docx_file.close()
        self._template = template
        LOGGER.info( 'wrote certificate to %s'%filepath )
        return filepath
    
    def _notification_type_premium_fulfillment(self, premium_schedule, options, premium_fulfillment=None):
        from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment as FAPS
        #
        # because we don't know exactly which entry to make this document for,
        # take the last one
        #
        if premium_fulfillment is None:
            notification_type = options.notification_type
            fulfillment_type = notification_type_fulfillment_types[ options.notification_type ][0]
            premium_fulfillment = FAPS.query.filter( sql.and_( FAPS.of == premium_schedule,
                                                               FAPS.entry_doc_date >= options.from_document_date,
                                                               FAPS.entry_doc_date <= options.thru_document_date,
                                                               FAPS.entry_book_date >= options.from_book_date,
                                                               FAPS.entry_book_date <= options.thru_book_date,
                                                               FAPS.fulfillment_type == fulfillment_type ) ).order_by( FAPS.entry_doc_date.desc() ).first()
            if not premium_fulfillment:
                raise UserException( 'No documents of type {0} were printed'.format(options.notification_type),
                                     title = 'No documents generated',
                                     resolution = 'There was no accounting entry found that relates to this type of document',
                                     detail = 'Expected document type was {0}'.format(fulfillment_type) )
        else:
            fulfillment_type = premium_fulfillment.fulfillment_type
            for nt, ft in notification_type_fulfillment_types.items():
                if fulfillment_type in ft:
                    notification_type = nt
                    break
        return notification_type, premium_fulfillment
