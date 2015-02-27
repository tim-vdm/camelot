import collections
import datetime

from camelot.admin.action import Action, list_filter
from camelot.core.utils import ugettext_lazy as _
from camelot.core.exception import UserException, CancelRequest
from camelot.admin.object_admin import ObjectAdmin
from camelot.view.controls import delegates
from camelot.view import action_steps

from vfinance.model.bank.entry import Entry, EditableEntryAdmin, SyncEntries
from vfinance.model.bank.constants import fulfillment_types
from vfinance.model.bank.direct_debit import DirectDebitMandate
from vfinance.model.financial.premium import (FinancialAccountPremiumSchedule,
                                              FinancialAccountPremiumFulfillment)
from .admin import FinancialAccountPremiumScheduleAdmin, RunForward
from match import get_code, match_premiums_and_entries

from camelot.core.qt import QtGui

from sqlalchemy import orm, sql

class OpenEntriesOptions(object):
    
    def __init__( self, entry ):
        self.entry = entry
        self.entry_remark = entry.remark
        self.entry_open_amount = entry.open_amount
        self.premium_schedule = None
        self.run_forward = False
        self.fulfillment_type = 'premium_attribution'
        self.associated_to = None
        self.within = None
        self.amount_distribution = 0
        self.active = True
        
    @property
    def agreement_code( self ):
        if self.premium_schedule:
            return self.premium_schedule.agreement_code
        
    def get_transaction_choices( self ):
        choices = [(None, '')]
        if self.premium_schedule != None:
            for transaction in self.premium_schedule.transactions:
                choices.append( ( transaction, unicode( transaction ) ) )
        return choices
    
    class Admin(ObjectAdmin):
        form_display = [ 'entry_remark', 'entry_open_amount', 'premium_schedule',
                         'agreement_code',
                         'run_forward', 'fulfillment_type', 'associated_to', 
                         'within', 'amount_distribution', 'active' ]
        field_attributes = {'premium_schedule':{'editable':True,
                                                'nullable':False,
                                                'delegate':delegates.Many2OneDelegate,
                                                'target':FinancialAccountPremiumSchedule,
                                                'admin':FinancialAccountPremiumScheduleAdmin},
                            'associated_to':{'editable':True,
                                             'name':_('Associated to entry'),
                                             'nullable':True,
                                             'delegate':delegates.Many2OneDelegate,
                                             'target':Entry,},
                            'entry_open_amount':{'delegate':delegates.FloatDelegate},
                            'amount_distribution':{'editable':True,
                                                   'name':_('Amount distribution'),
                                                   'required':True,
                                                   'delegate':delegates.FloatDelegate,},
                            'within':{'editable':True,
                                      'name':_('Within transaction'),
                                      'nullable':True,
                                      'choices':lambda o:o.get_transaction_choices(),
                                      'delegate':delegates.ComboBoxDelegate},
                            'fulfillment_type':{'editable':True,
                                                'nullable':False,
                                                'delegate':delegates.ComboBoxDelegate,
                                                'choices':[(ft,ft.capitalize()) for _i,ft in fulfillment_types],},
                            'run_forward':{'editable':True,
                                           'delegate':delegates.BoolDelegate,
                                           'tooltip':_('Run forward after attributing the entry to the schedule')},
                            'active':{'editable':True,
                                      'delegate':delegates.BoolDelegate,
                                      'tooltip':_('Keep the entry active within the premium schedule')},
                            }
            
class AttributeOpenEntriesAction( RunForward ):
            
    verbose_name = _('Manual Attribution')
    
    def attribute_entry( self, model_context, pending_entry, options ):
        if options.premium_schedule:
            today = datetime.date.today()
            if not pending_entry.number_of_fulfillments:
                associated_fulfillment = None
                if options.associated_to:
                    associated_fulfillments = options.associated_to.fulfillment_of
                    if len( associated_fulfillments ) != 1:
                        raise UserException( _('Unable to associate the entries') )
                    associated_fulfillment = associated_fulfillments[0]
                fapf = FinancialAccountPremiumFulfillment( of = options.premium_schedule,
                                                           entry_book_date = pending_entry.book_date,
                                                           entry_document = pending_entry.document,
                                                           entry_book = pending_entry.book,
                                                           entry_line_number = pending_entry.line_number,
                                                           fulfillment_type = options.fulfillment_type,
                                                           associated_to = associated_fulfillment,
                                                           within = options.within,
                                                           amount_distribution = options.amount_distribution,
                                                           )
                if not options.active:
                    fapf.from_date = today
                    fapf.thru_date = today - datetime.timedelta( days = 1 )
                yield action_steps.FlushSession( model_context.session )
            else:
                raise UserException( _('This entry has been attributed before') )
            if options.run_forward:
                for step in self.run_forward([options.premium_schedule], 1, model_context):
                    yield step
                yield action_steps.FlushSession( model_context.session )
                    
    def model_run( self, model_context ):
        for pending_entry in model_context.get_selection():
            options = OpenEntriesOptions( pending_entry )
            options.amount_distribution = pending_entry.open_amount
            yield action_steps.ChangeObject( options )
            for step in self.attribute_entry( model_context,
                                              pending_entry,
                                              options ):
                yield step

class AttributePendingPremiums( AttributeOpenEntriesAction ):
    """
    This action is meant to attribute the open entries without any manual
    intervention.
    """
    
    def attribute_pending_premiums(self, premium_schedule_query, session, model_context=None):
        """Look on the pending premium accounts, and try to match premiums
        with premium_schedules.  When a premium matches, run attribute it and
        run the account schedule forward.
        
        :param premium_schedule_query: a query object that can be used to determine
            on which premiums schedules the pending premium can be attributed.

        :param session: the session to be used

        :param model_context: the model_context in which the action is run.  If this
            is None, it is assumed that no action is run
        """
        run_forward = None
        yield action_steps.UpdateProgress(detail='read open entries')
        open_entries_query = OpenEntriesAdmin.get_open_entries_query(session)
        open_entries_query = open_entries_query.filter(Entry.open_amount < 0)
        open_entries_with_code = collections.defaultdict(list)
        for entry in open_entries_query.yield_per(100):
            code_type, code = get_code(entry)
            if code_type is not None:
                open_entries_with_code[(code_type, code)].append(entry)
        yield action_steps.UpdateProgress(detail='match premium schedules with open entries')
        # make sure the attribution is deterministic
        premium_schedule_query = premium_schedule_query.order_by(FinancialAccountPremiumSchedule.id)
        for ((code_type, code), entries) in open_entries_with_code.items():
            session = orm.object_session(entries[0])
            entries.sort(key=lambda e:e.doc_date)
            premium_schedules = []
            if code_type == 'agreement':
                premium_schedules.extend(premium_schedule_query.filter(FinancialAccountPremiumSchedule.agreement_code==code).all())
            elif code_type == 'mandate':
                for mandate in session.query(DirectDebitMandate).filter(DirectDebitMandate.identification==code):
                    if mandate.financial_account is not None:
                        premium_schedules.extend(mandate.financial_account.premium_schedules)
            document_dates = set()
            for match in match_premiums_and_entries(entries, premium_schedules):
                document_dates.add(match.entry.doc_date)
                FinancialAccountPremiumFulfillment(of = match.premium,
                                                   entry_book_date = match.entry.book_date,
                                                   entry_document = match.entry.document,
                                                   entry_book = match.entry.book,
                                                   entry_line_number = match.entry.line_number,
                                                   fulfillment_type = 'premium_attribution',
                                                   amount_distribution = -1 * match.amount )
                yield action_steps.UpdateProgress(detail=u'{1.agreement_code} : attribute {2:.2f} of {0.book_date} {0.book} {0.document} to premium schedule {1.id}'.format(match.entry, match.premium, match.amount))

            if len(premium_schedules):
                if len(document_dates):
                    # in case there was a match, run the associated schedules forward, to
                    # make sure certifcates are generated.
                    session.flush()
                    for premium_schedule in premium_schedules:
                        session.expire(premium_schedule)
                    if run_forward is None:
                        run_forward = yield action_steps.MessageBox(u'Run associated premium schedule forward ?',
                                                                    title='Pending premium attributed',
                                                                    standard_buttons=QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
                    if run_forward == QtGui.QMessageBox.Yes:
                        options = self.Options()
                        options.thru_document_date = max(document_dates)
                        options.reason = 'run agreement forward'
                        yield action_steps.UpdateProgress(detail=u'{0} : run associated premium schedules forward thru {1}'.format(code, options.thru_document_date))
                        for step in self.run_forward(premium_schedules, len(premium_schedules), model_context):
                            if step.blocking == False:
                                yield step
                else:
                    # generate some feedback for the user in case no match was made,
                    # silently ignoring partial matches of codes
                    yield action_steps.UpdateProgress(detail=u'{0} no match found between {1} and entries'.format(code, code_type))
                    entry_total = 0
                    premium_schedule_total = 0
                    for entry in entries:
                        entry_total += entry.open_amount
                        yield action_steps.UpdateProgress(detail=u'{0} entry {1.book_date} {1.book} {1.document} {1.open_amount:.2f}'.format(code, entry))
                    for premium_schedule in premium_schedules:
                        premium_schedule_total += premium_schedule.premium_amount
                        yield action_steps.UpdateProgress(detail=u'{0.agreement_code} premium schedule {0.id} {0.premium_amount} {0.period_type}'.format(premium_schedule))
                    yield action_steps.UpdateProgress(detail=u'{0} entry total : {1:.2f} vs premium schedule total {2:.2f}'.format(code, entry_total * -1, premium_schedule_total))


class AttributionWizard( AttributeOpenEntriesAction ):
    
    verbose_name = _('Attribution Wizard')
    
    def model_run( self, model_context ):
        session = model_context.session
        for i, pending_entry in enumerate( model_context.get_selection() ):
            yield action_steps.UpdateProgress( i, model_context.selection_count, 
                                               pending_entry.remark )
            _code_type, code = get_code( pending_entry )
            if code and (not pending_entry.number_of_fulfillments):
                premium_schedules = list( session.query( FinancialAccountPremiumSchedule ).filter( FinancialAccountPremiumSchedule.agreement_code == code ).all() )
                if len( premium_schedules ) == 1:
                    options = OpenEntriesOptions( pending_entry )
                    options.premium_schedule = premium_schedules[0]
                    options.amount_distribution = pending_entry.open_amount
                    try:
                        yield action_steps.ChangeObject( options )
                    except CancelRequest:
                        continue
                    for step in self.attribute_entry( model_context, pending_entry, options ):
                        yield step
            
class UnAttributeOpenEntriesAction( Action ):
            
    verbose_name = _('Unattribute')
    
    def model_run( self, model_context ):
        from camelot.view.action_steps import FlushSession, MessageBox
        for entry in model_context.get_selection():
            if entry.number_of_fulfillments:
                yield MessageBox( _('Are you sure you want to continue\nThis action cannot be undone and can cause data loss') )
                for fulfillment in entry.fulfillment_of:
                    model_context.session.delete( fulfillment )
                yield FlushSession( model_context.session )
    
class OpenEntriesAdmin( EditableEntryAdmin ):
    
    verbose_name = _('Open entry')
    verbose_name_plural = _('Open entries')
    list_display =  ['book_date', 'datum', 'venice_book', 'venice_doc', 'open_amount', 'remark', 'number_of_fulfillments']
    list_actions = [AttributionWizard(), AttributeOpenEntriesAction()]
    list_filter = EditableEntryAdmin.list_filter + [list_filter.EditorFilter('datum')]

    @classmethod
    def get_open_entries_query(cls, session):
        from vfinance.model.bank.product import ProductAccount
        query = session.query(Entry)

        accounts = set()
        account_query = query.session.query(ProductAccount)
        account_query = account_query.filter(ProductAccount.described_by=='pending_premiums')
        for account in account_query.all():
            accounts.add( ''.join(account.number) )

        query = query.order_by(Entry.datum.desc())
        return query.filter(sql.and_(Entry.account.in_(list(accounts)),
                                     Entry.open_amount != 0
                                     ) )

    def get_query(self, *args, **kwargs):
        query = super(OpenEntriesAdmin, self).get_query(*args, **kwargs)
        return self.get_open_entries_query(query.session)



# @todo : move some of this to bank or do something, because this is a dirty injection
Entry.Admin = EditableEntryAdmin
Entry.Admin.list_actions = [AttributeOpenEntriesAction(), UnAttributeOpenEntriesAction(), SyncEntries()]
Entry.Admin.form_actions = [AttributeOpenEntriesAction(), UnAttributeOpenEntriesAction()]
