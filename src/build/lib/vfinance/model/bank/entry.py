"""Copy van Venice Entries met betrekking tot
klant rekeningen, met de bedoeling van deze 's nachts te synchroniseren
met Venice, om het querieen te versnellen
"""
import logging
import datetime
from decimal import Decimal as D
import operator

import sqlalchemy.types
from sqlalchemy import sql, orm, schema, create_engine, MetaData, event

from camelot.core.orm import Session, Entity, using_options
from camelot.admin.action import Action, list_filter
from camelot.admin.not_editable_admin import not_editable_admin
from camelot.admin.object_admin import ObjectAdmin
from camelot.admin.entity_admin import EntityAdmin
from camelot.view.controls import delegates
from camelot.view import forms, action_steps
from camelot.core.utils import ugettext_lazy as _
from camelot.core.conf import settings
import camelot.types

from ...sql import year_part
from ..bank.venice import get_dossier_bank

from vfinance.admin.vfinanceadmin import VfinanceAdmin

logger = logging.getLogger('vfinance.model.bank.entry')

class EntryPresence(Entity):
    """Entries komen in venice in meerdere boekjaren voor"""
    using_options( tablename='hypo_entry_presence' )
    entry_id = schema.Column(sqlalchemy.types.Integer(),
                             schema.ForeignKey('hypo_betaling.id'), nullable=False,
                             index=True, )
    venice_active_year = schema.Column(sqlalchemy.types.Unicode(14), nullable=False)
    venice_id = schema.Column(sqlalchemy.types.Integer(), nullable=False)

    def __unicode__(self):
        return unicode(self.entry)

    class Admin(EntityAdmin):
        list_display =  ['venice_active_year', 'venice_id']
        field_attributes = {
                            'entry':{'editable':False, 'name':_('Betaling')},
                            'venice_active_year':{'editable':False, 'name':_('Venice jaar')},
                            'venice_id':{'editable':False, 'name':_('Venice id')},
                           }

class TickSession(Entity):
    """Afpuntingen waarin verrichtingen betrokken zijn"""
    __tablename__ = 'hypo_afpunt_sessie'
    venice_tick_session_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)
    venice_active_year  =  schema.Column(sqlalchemy.types.Unicode(14), nullable=False)
    venice_id  =  schema.Column(sqlalchemy.types.Integer(), nullable=False)

    def __unicode__(self):
        return '{0.venice_active_year} {0.venice_tick_session_id}'.format(self)

    @classmethod
    def get_tick_session_id(cls, presence):
        """:return: a tick session id that can be used to create fake tick
        sessions"""
        new_id = cls.query.session.query( sql.func.max(TickSession.venice_tick_session_id) ).filter(cls.venice_active_year==presence).scalar()
        return new_id or 1
        
    class Admin(EntityAdmin):
        list_display =  ['venice_active_year', 'venice_tick_session_id']
        form_display = list_display + ['part_of']
        field_attributes = {
                            'venice_tick_session_id':{'editable':False, 'name':_('Afpuntsessie')},
                            'venice_active_year':{'editable':False, 'name':_('Venice jaar')},
                            'venice_id':{'editable':False, 'name':_('Venice id')},
                           }

related_tick_session = sql.alias(TickSession.__table__)

class RelatedTickSession(Entity):
    __table__ = related_tick_session

    class Admin(TickSession.Admin):
        form_display = TickSession.Admin.list_display + ['composed_of']



key_components = ['account', 'venice_doc', 'venice_book', 'book_date', 'line_number']
    
class Entry(Entity):
    """Spiegel tabel van alle verichtingen die in Venice gebeurd zijn op een rekening"""
    #
    # Warning : don't change the order by clauses, there is a special index on
    #           this order, otherwise counting the rows in the table becomes
    #           extremely slow
    #
    using_options(tablename='hypo_betaling', order_by=['book_date', 'venice_book', 'venice_doc', 'line_number'])
    line_number  =  schema.Column(sqlalchemy.types.Integer(), nullable=False, index=True)
    open_amount  =  schema.Column(sqlalchemy.types.Numeric(precision=16, scale=2), nullable=False)
    ticked  =  schema.Column(sqlalchemy.types.Boolean(), nullable=False)
    datum  =  schema.Column(sqlalchemy.types.Date(), index=True)
    remark  =  schema.Column(sqlalchemy.types.Unicode(256))
    venice_active_year  =  schema.Column(sqlalchemy.types.Unicode(10))
    venice_doc  =  schema.Column(sqlalchemy.types.Integer(), nullable=False, index=True)
    account  =  schema.Column(sqlalchemy.types.Unicode(14), nullable=False, index=True)
    venice_book_type  =  schema.Column(sqlalchemy.types.Unicode(10))
    amount  =  schema.Column(sqlalchemy.types.Numeric(precision=16, scale=2))
    # state  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=True)
    book_date  =  schema.Column(sqlalchemy.types.Date(), nullable=False, index=True)
    creation_date = schema.Column(sqlalchemy.types.Date(), nullable=False, index=True, default = sql.func.current_date() )
    venice_id  =  schema.Column(sqlalchemy.types.Integer())
    venice_book  =  schema.Column(sqlalchemy.types.Unicode(10), nullable=False, index=True )
    quantity = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=6), nullable=False, default=0)
    value = schema.Column(sqlalchemy.types.Numeric(precision=17, scale=6), index=True)
    text = schema.Column(sqlalchemy.types.Unicode(25))
    #
    # requested = V-Finance wants to create an entry, but it has not yet instructed the accounting package to do so
    # draft = V-Finance has instructed the accounting package to create an entry
    # confirmed = The accounting package has confirmed the creation of an entry
    # frozen = These entries should no longer be synchronized with the accounting
    #          package, this is used when migrating from one accounting package to
    #          another.
    #
    accounting_state = schema.Column(camelot.types.Enumeration([(1, 'requested'),
                                                                (2, 'draft'),
                                                                (3, 'confirmed'),
                                                                (4, 'frozen'),
                                                                ]), nullable=False, default='confirmed', index=True)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer())

    @property
    def total_amount(self):
        return D(str(Entry.query.session.execute( sql.select([sql.func.sum(Entry.amount)]).where( sql.and_(Entry.datum <= self.datum,
                                                                                                           Entry.account == self.account,
                                                                                                           Entry.book_date <= self.book_date ) ) ).first()[0] or 0)).quantize(D('0.01'))
        
    @property
    def total_quantity(self):
        return D(str(Entry.query.session.execute( sql.select([sql.func.sum(Entry.quantity)]).where( sql.and_(Entry.datum <= self.datum,
                                                                                                             Entry.account == self.account,
                                                                                                             Entry.book_date <= self.book_date ) ) ).first()[0] or 0)).quantize(D('0.001'))
        
    @property
    def book(self):
        return self.venice_book
    
    @property
    def document(self):
        return self.venice_doc

    @property
    def last_presence(self):
        sorted_presences = [p.venice_active_year for p in self.presences]
        sorted_presences.sort(key=int)
        return sorted_presences[-1]
    
    @property
    def last_entry_presence(self):
        sorted_presences = [p for p in self.presences]
        sorted_presences.sort(key=lambda p:getattr(p, 'venice_active_year'))
        return sorted_presences[-1]

    @property
    def doc_date(self):
        return self.datum

    @property
    def same_document(self):
        if not self.book_date or not self.venice_book or not self.venice_doc:
            return []
        """a list of entries appearing in the same document"""
        return Entry.query.filter(self.document_condition(Entry.__table__.c,
                                                          self.book_date,
                                                          self.book,
                                                          self.document)).all()

    @classmethod
    def fulfillment_condition(cls, e_columns, fe_columns):
        """
        :return: a SQLA condition for entries that match the fe_columns
        """
        #
        # only check the equality of the year, because of compatibility with older bookings where book_date
        # and document_date are equal
        #
        return cls.entry_condition(e_columns,
                                   book_date=fe_columns.entry_book_date,
                                   book=fe_columns.entry_book,
                                   document_number=fe_columns.entry_document,
                                   line_number=fe_columns.entry_line_number)

    @classmethod
    def document_condition(cls, e_columns, book_date, book, document_number):
        return sql.and_( year_part( sql.func.coalesce(book_date, datetime.date(2400,1,1) ) ) == year_part( e_columns.book_date ),
                         sql.func.lower( book ) == sql.func.lower( e_columns.venice_book ), # Venice is case insensitive
                         document_number == e_columns.venice_doc)

    @classmethod
    def entry_condition(cls, e_columns, book_date, book, document_number, line_number):
        return sql.and_(cls.document_condition(e_columns, book_date, book, document_number),
                        line_number == e_columns.line_number)

    @classmethod
    def fulfillment_query( cls, session, fulfillemnt_class, e_columns, fe_columns):
        query = session.query(fulfillemnt_class)
        query = query.filter( cls.fulfillment_condition(e_columns, fe_columns))
        return query
    
    @property
    def number_of_fulfillments(self):
        from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment
        if self.book_date:
            query = self.fulfillment_query(orm.object_session(self),
                                           FinancialAccountPremiumFulfillment,
                                           self,
                                           FinancialAccountPremiumFulfillment)
            return query.count()
    
    @property
    def fulfillment_of(self):
        """a list of FinancialAccountPremiumFulfillment objects, relating the entry to another object"""
        from vfinance.model.financial.premium import FinancialAccountPremiumFulfillment
        if self.book_date:
            query = self.fulfillment_query(orm.object_session(self),
                                           FinancialAccountPremiumFulfillment,
                                           self,
                                           FinancialAccountPremiumFulfillment)
            return query.all()

    @property
    def loan_fulfillment_of(self):
        """a list of MortgageFulfillment objects, relating the entry to another object"""
        from vfinance.model.hypo.fulfillment import MortgageFulfillment
        if self.book_date:
            query = self.fulfillment_query(orm.object_session(self),
                                           MortgageFulfillment,
                                           self,
                                           MortgageFulfillment)
            return query.all()

    @property
    def last_tick_date(self):
        return self.get_last_tick_date()
                                            
    def get_last_tick_date(self):
        """Zoek voor een vervaldag de afpunt sessies waarin ze betrokken was, en zoek
        dan de laatste betaling in die afpunt sessies.  De datum van die laatste betaling
        wordt als betaaldatum verondersteld.
        
        Dit is enkel correct als betalingen en vervaldagen niet in bulk na verloop van een
        grote periode zijn afgepunt
        """
        if not self.account:
            return None
        return self.tick_date
        
    def __unicode__(self):
        return u'%s %s %s'%(self.venice_active_year, self.venice_book, self.venice_doc)

    @classmethod
    def sync_venice( cls, accounts = None, dossier = None, constants = None, years=None ):
        """Ga na of objecten afgepunt zijn in Venice, indien ja, verzet de state naar ticked
        geef keyword argument 'accounts' mee om de synchronisatie te beperken tot een range
        van accounts
        :param accounts: de te synchroniseren accounts, if None w de klant rekeningen gesynct
        :param dossier: the venice dossier to use, this is used for unit testing with a mock 
            object.
        :param years: the number of years to look back
        """
        logger.debug('start sync venice of betalingen')
        import decimal
        from vfinance.model.bank.venice import get_inspectable_years
        from integration.venice.venice import venice_date
        #
        # Flush before continueing, to make sure there is no pending state
        # in the session.
        #
        session = Session()
        session.flush()

        if dossier == None:
            dossier, constants = get_dossier_bank()
            #if isinstance(dossier, mock_venice_class):
                #return

        account_klant = settings.get('HYPO_ACCOUNT_KLANT', 400000000000)
        if not accounts:
            accounts = str(account_klant.rstrip('0'))
        logger.info('sync accounts %s'%accounts)
        #
        # only synchronize the last years
        #
        inspectable_years = list(get_inspectable_years(dossier, years=years))
        inspectable_years.sort()
        #
        # Delete all currently stored entries related to entries on these
        # accounts before rereading them from Venice
        #
        # First delete the entry presences for the inspectable years
        #engine = metadata.bind
        #engine = cls.query.session.bind.q
        logger.info('number of current entries : %s'%cls.query.filter( cls.account.like('%s%%'%accounts) ).count())
        with session.begin():
            #
            # Delete the draft entries, as they should now be replaced by confirmed entries
            #
            session.execute( sql.text( """delete from hypo_entry_presence where id in
            (
               select hypo_entry_presence.id as id from hypo_entry_presence
               join hypo_betaling on
               (hypo_entry_presence.entry_id=hypo_betaling.id)
               where hypo_betaling.account like '%s%%' and hypo_betaling.accounting_state=2
            )
            """%(accounts) ), mapper=Entry )
            session.execute( sql.text( """delete from hypo_betaling
            where hypo_betaling.account like '%s%%' and 
                  hypo_betaling.accounting_state=2"""%accounts ), mapper=Entry )
            for year in inspectable_years:
                logger.info(' year %s'%year)
                session.execute( sql.text( """delete from hypo_afpunt_sessie where id in
                (
                  select hypo_afpunt_sessie.id as id from hypo_afpunt_sessie 
                  join hypo_entry_presence on
                    (hypo_entry_presence.venice_active_year=hypo_afpunt_sessie.venice_active_year and
                     hypo_entry_presence.venice_id=hypo_afpunt_sessie.venice_id
                    )
                  join hypo_betaling on
                  (hypo_entry_presence.entry_id=hypo_betaling.id) 
                  where hypo_betaling.account like '%s%%' and hypo_entry_presence.venice_active_year='%s' and hypo_betaling.accounting_state != 4
                )
                """%(accounts, year) ), mapper=Entry )
                session.execute( sql.text( """delete from hypo_entry_presence where id in
                (
                   select hypo_entry_presence.id as id from hypo_entry_presence
                   join hypo_betaling on
                   (hypo_entry_presence.entry_id=hypo_betaling.id)
                   where hypo_betaling.account like '%s%%' and hypo_entry_presence.venice_active_year='%s' and hypo_betaling.accounting_state != 4
                )
                """%(accounts,year) ), mapper=Entry )
            #
            # Then delete the entries that have no entry presence any more
            # (split in 2 queries since 1 query is extremely slow)
            #
            logger.info(' delete entries without presence')
            ids_not_to_delete = [row[0] for row in session.execute( sql.text( """select hypo_betaling.id as id from hypo_betaling
            join hypo_entry_presence on
            (hypo_entry_presence.entry_id=hypo_betaling.id)
            where hypo_betaling.account like '%s%%'"""%accounts ), mapper=Entry )]
            logger.info(' %s entries to keep'%len( ids_not_to_delete ) )
            session.execute( cls.table.delete().where( cls.table.c.account.like( '%s%%'%accounts ) ).where( ~cls.table.c.id.in_( ids_not_to_delete ) ) )
            logger.info('previous entries removed')
            #
            # Read all entries from venice and copy them into tiny
            #
            book_types = { constants.btPurch:'A', 
                           constants.btSales:'V', 
                           constants.btFinan:'F', 
                           constants.btSndry:'D' }
            #
            # Keep a key for all created entries in memory, to find out fast if it was
            # allready registered or not
            #
            # This detection of duplicate entries is not waterproof, because different entries in
            # the same year might have the same key, which will result in of the entries not being
            # loaded.  Maybe pEntryNum should be added to the key to ensure this uniqueness, but
            # this should be tested.
            # UPDATE : try to solve this issue with adding line number to the key components,
            #          but we have historic date for which this line number is not present
            #
            keys_previous_years = dict()
            #
            # Keep a key for all updated entries in memory, because we only want to update
            # each entry once, namely with the first data we encounter, which is the last year
            #
            keys_updated = set()
            #
            # Get all the 'unique' keys of the entries allready in the database in memory
            # to ease the synchronization process
            #
            key_columns = [ getattr(cls.table.c, k) for k in key_components ]
            for row in session.execute( sql.select( [cls.table.c.id,
                                                      cls.table.c.accounting_state] + key_columns ).where( cls.table.c.account.like('%s%%'%accounts) ) ):
                keys_previous_years[tuple( row[k] for k in key_components)] = (row['id'], row['accounting_state'])
            logger.info('%s entry keys loaded'%(len(keys_previous_years)))
            logger.debug('start inlezen betalingen')
            # begin with latest year, because we want the latest tick status in
            # the database
            if len( accounts ) == 12:
                filter_expression = '@ENT.Account == "%s"'%(accounts)
            else:
                filter_expression = '@ENT.Account ^^ "%s"'%(accounts)
            logger.info( 'use filter %s'%filter_expression )
            for year in reversed(inspectable_years):
                year_context = dossier.CreateYearContext(year)
                entry = year_context.CreateEntry(False)
                logger.info('start inlezen betalingen boekjaar %s'%year)
                counter = 0
                if entry.SetFilter( filter_expression, True ):
                    while True:
                        if counter%10000 == 0:
                            logger.debug( '%s read'%counter )
                        counter += 1
                        tick_info, tick_session, _tick_sequence, _tick_date, _tick_user, _tick_amount_det, _tick_amount_dos, tick_sys_nums = entry.GetLastTickInfo()
                        if venice_date( entry.pBookDateOrg ) in (None, datetime.datetime(1899, 12, 30)):
                            book_date = venice_date( entry.pBookDate ).date()
                        else:
                            book_date = venice_date( entry.pBookDateOrg ).date()
                        if venice_date( entry.pDocDateOrg ) in (None, datetime.datetime(1899, 12, 30)):
                            doc_date = venice_date( entry.pDocDate ).date()
                        else:
                            doc_date = venice_date( entry.pDocDateOrg ).date() 
                        creation_date = venice_date( entry.pCreDate ).date()
                        d = { 'account':entry.pAccount,
                              'book_date':book_date,
                              'amount': entry.pAmountDosC,
                              'open_amount':entry.pOpenDosC,
                              'creation_date':creation_date,
                              'quantity':decimal.Decimal('%.6f'%(entry.pQuantity or 0.0)),
                              'ticked':(entry.pTickStatus==2),
                              'datum':doc_date,
                              'value':entry.pValue1,
                              'text':entry.pText1,
                              'venice_doc':entry.pDocNum,
                              'venice_book':entry.pBook or '',
                              'venice_book_type':book_types[entry.pBookType],
                              'remark': unicode(entry.pRemark)[:256],
                              'line_number':entry.vLineNum,
                              'accounting_state':'confirmed',
                            }
                        if entry.pDocNumOrg:
                            # het betreft een overdracht
                            # entry.pAccYearOrg was used as a discriminator in
                            # Tiny.  entry.pBookOrg cannot be used, since there
                            # are entries without a book
                            d['venice_doc'] = entry.pDocNumOrg
                            d['venice_book'] = entry.pBookOrg or ''
                            d['venice_book_type'] = book_types[entry.pBookTypeOrg]
                            d['line_number'] = entry.pLineNumOrg
                        key = tuple( d[k] for k in key_components)
                        logger.debug('entry found with key %s'%str(key))
                        #
                        # if betaling entry not yet stored, store it
                        #
                        try:
                            try:
                                entry_id, accounting_state = keys_previous_years[key]
                            except KeyError:
                                #
                                # try alternative keys for entries that have been stored earlier on without
                                # a line number, we'll assume they have been given line number -1
                                #
                                alternative_key = [c for c in key]
                                alternative_key[-1] = -1
                                entry_id, accounting_state = keys_previous_years[tuple(alternative_key)]
                            #
                            # if it is allready stored, but not yet updated, update it
                            #
                            if (key not in keys_updated) and (accounting_state != 'frozen'):
                                #
                                # update all data that is not part of the key
                                #
                                updates = dict( (k,v) for k,v in d.items() if k not in key_components )
                                session.execute( cls.table.update().where( cls.table.c.id == entry_id ).values( updates ) )
                                keys_updated.add(key)
                        except KeyError:
                            logger.debug('entry not found yet, create it')
                            entry_id = session.execute( cls.table.insert().values( d ) ).inserted_primary_key[0]
                            accounting_state = 'confirmed'
                            keys_previous_years[key] = (entry_id, accounting_state)
                            keys_updated.add(key)
                        #
                        # store its presence in this year
                        #            
                        if accounting_state != 'frozen':
                            session.execute( EntryPresence.table.insert().values( entry_id=entry_id, venice_active_year=year, venice_id=entry.pSysNum ) )
                            if tick_info:
                                for venice_id in tick_sys_nums:
                                    session.execute( TickSession.table.insert().values( venice_id = venice_id, 
                                                                                           venice_tick_session_id = tick_session, 
                                                                                           venice_active_year = year ) )
                                #  This entry participated in the tick session as well
                                session.execute( TickSession.table.insert().values( venice_id = entry.pSysNum, 
                                                                                       venice_tick_session_id = tick_session, 
                                                                                       venice_active_year = year ) )
                        if not entry.GetNext():
                            break
            logger.debug('flush')
        return True

def after_entry_create(target, connection, **kw):
    if connection.dialect.name == 'postgresql':
        connection.execute("""
        CREATE INDEX ix_entry_book_year
        ON hypo_betaling
        USING btree
        (date_part('year', hypo_betaling.book_date));
        """)

event.listen(Entry.__table__, "after_create", after_entry_create)

class SyncEntriesOptions( object ):
    
    def __init__( self ):
        self.accounts = ''
        self.years = 2
        # dossier, for unit test purposes
        self.dossier = None
        self.constants = None
        
    class Admin( ObjectAdmin ):
        list_display = ['accounts', 'years']
        field_attributes = {'accounts':{'editable':True,
                                        'delegate':delegates.PlainTextDelegate },
                            'years':{'editable':True,
                                     'delegate':delegates.IntegerDelegate}
                            }
        
class SyncEntries( Action ):

    verbose_name = _('Sync Entries')

    def model_run( self, model_context ):
        options = SyncEntriesOptions()
        yield action_steps.ChangeObject( options )
        if options.accounts:
            Entry.sync_venice( options.accounts, 
                               dossier = options.dossier,
                               constants = options.constants,
                               years = options.years )
        
class EditableEntryAdmin(VfinanceAdmin):
    verbose_name_plural = _('Entries')
    list_display =  ['account', 'doc_date', 'book_date', 'venice_book', 'venice_doc', 'line_number', 'amount', 'quantity', 'ticked', 'remark']
    list_filter = [list_filter.EditorFilter('book_date',
                                            default_operator = operator.gt,
                                            default_value_1 = datetime.date.today() - datetime.timedelta( days = 62 ) )]
    
    # no filters here, to keep the list relatively fast to open
    form_display =  forms.TabForm( [ ( _('Accounting'), forms.Form(['book_date', 'venice_book_type', 'venice_book','venice_doc', 'datum', 
                                                                    'ticked', 'amount','open_amount','remark', 'account', 
                                                                    'accounting_state', 'presences'], columns=2)),
                                     ( _('Related to'), forms.Form(['fulfillment_of', 'loan_fulfillment_of']) ),
                                     ( _('Complete document'), forms.Form(['same_document'])),
                                     ( _('Ticks'), forms.Form(['ticked_within', 'tick_date']))
                                     ])

    field_attributes = {
                        'line_number':{'editable':False, 'name':_('Line')},
                        'open_amount':{'editable':False, 'name':_('Openstaand bedrag')},
                        'ticked':{'editable':False, 'name':_('Afgepunt')},
                        'datum':{'editable':False, 'name':_('Document date')},
                        'remark':{'editable':False, 'name':_('Remark'), 'minimal_column_width':50},
                        'venice_active_year':{'editable':False, 'name':_('Actief jaar')},
                        'venice_doc':{'editable':False, 'name':_('Document')},
                        'account':{'editable':False, 'name':_('Rekening')},
                        'venice_book_type':{'editable':False, 'name':_('Dagboek Type')},
                        'amount':{'editable':False, 'name':_('Bedrag')},
                        'state':{'editable':False, 'name':_('Status')},
                        'book_date':{'editable':False, 'name':_('Book date')},
                        'doc_date':{'editable':False, 'delegate':delegates.DateDelegate},
                        'document':{'editable':False, 'delegate':delegates.FloatDelegate, 'name':_('Document')},
                        'venice_id':{'editable':False, 'name':_('Systeem Nummer Venice')},
                        'venice_book':{'editable':False, 'name':_('Dagboek')},
                        'quantity':{'editable':False},
                        'tick_date':{'editable':False},
                        'fulfillment_of':{'editable':False, 'target':'FinancialAccountPremiumFulfillment', 'delegate':delegates.One2ManyDelegate, 'name':_('Related premium schedules')},
                        'loan_fulfillment_of':{'editable':False, 'target':'FinancialAccountPremiumFulfillment', 'delegate':delegates.One2ManyDelegate, 'name':_('Related loan schedules')},
                        'same_document':{'editable':False, 'target':Entry, 'delegate':delegates.One2ManyDelegate},
                        'number_of_fulfillments':{'name':_('Attributed')},
                       }

Entry.Admin = not_editable_admin( EditableEntryAdmin )

tick_session_related_tick_session_condition = sql.and_(TickSession.venice_tick_session_id==orm.foreign(RelatedTickSession.__table__.c.venice_tick_session_id),
                                                       TickSession.venice_active_year==orm.foreign(RelatedTickSession.__table__.c.venice_active_year))

TickSession.part_of = orm.relationship(RelatedTickSession,
                                       foreign_keys = [TickSession.__table__.c.id],
                                       primaryjoin=tick_session_related_tick_session_condition)

entry_presence = EntryPresence.__table__
tick_session = TickSession.__table__

EntryPresence.entry = orm.relationship(Entry, backref='presences')

entry_presence_tick_session_condition = sql.and_(tick_session.c.venice_active_year==entry_presence.c.venice_active_year,
                                        tick_session.c.venice_id==entry_presence.c.venice_id)

Entry.ticked_within = orm.relationship(
    TickSession,
    secondary=entry_presence,
    primaryjoin=Entry.id==entry_presence.c.entry_id,
    secondaryjoin=entry_presence_tick_session_condition,
    viewonly=True,
    lazy='dynamic')

class RelatedEntry(Entity):
    __table__ = sql.alias(Entry.__table__)

    @property
    def doc_date(self):
        return self.datum

    class Admin(Entry.Admin):
        list_display = Entry.Admin.list_display
        form_display = list_display

related_entry_presence = sql.alias(entry_presence)

related_tick_session_related_entry_presence_condition = sql.and_(related_tick_session.c.venice_active_year==related_entry_presence.c.venice_active_year,
                                                                 related_tick_session.c.venice_id==related_entry_presence.c.venice_id)

RelatedTickSession.composed_of = orm.relationship(
    RelatedEntry,
    secondary=related_entry_presence,
    primaryjoin=related_tick_session_related_entry_presence_condition,
    secondaryjoin=RelatedEntry.id==related_entry_presence.c.entry_id,
    viewonly=True,
    lazy='dynamic'
    )

# 
# using joins as secondary arguments is only supported as SQLA 0.9.2,
# try this again when SQLA is upgraded
#
#TickSession.composed_of = orm.relationship(
    #RelatedEntry,
    #secondary=related_entry_presence,
    #primaryjoin=sql.and_(related_tick_session_related_entry_presence_condition,
                         #tick_session_related_tick_session_condition),
    #secondaryjoin=orm.foreign(RelatedEntry.id)==related_entry_presence.c.entry_id,
    #viewonly=True,
    #lazy='dynamic'
    #)

entry_tick_date_condition = sql.and_(Entry.id==entry_presence.c.entry_id,
                                     RelatedEntry.id==related_entry_presence.c.entry_id,
                                     entry_presence_tick_session_condition,
                                     tick_session_related_tick_session_condition,
                                     related_tick_session_related_entry_presence_condition,
                                     Entry.id!=RelatedEntry.id,
                                     Entry.account==RelatedEntry.account,
                                     Entry.amount * RelatedEntry.amount < 0,
                                     )

tick_date_query = sql.select([sql.func.max(RelatedEntry.datum)],
                             whereclause=entry_tick_date_condition,
                   )

Entry.tick_date = orm.column_property(
    tick_date_query,
    deferred=True,
)

class EntryFulfillmentTables(object):
    """
    Helper object to group an entry table and a fulfillment
    table
    """
    
    def __init__(self, entry_table, fulfillment_table):
        self.entry_table = entry_table
        self.fulfillment_table = fulfillment_table

class InMemoryEntryFulfillmentTables(EntryFulfillmentTables):
    """
    In memory fulfillment tables, either for speed, or for
    separation
    """
    
    def __init__(self, entry_table, fulfillment_table):
        # create an in memory engine for speedy operations
        self.memory_engine = create_engine( 'sqlite://' )
        self.metadata = MetaData()
        self.metadata.bind = self.memory_engine
        entry_table_columns = []
        for col in entry_table.columns:
            entry_table_columns.append(schema.Column(col.name, col.type, primary_key=col.primary_key))
        self.entry_table = schema.Table( 'entry', 
                                         self.metadata, 
                                         *entry_table_columns )
        fapf_table_columns = []
        for col in fulfillment_table.columns:
            fapf_table_columns.append( schema.Column(col.name, col.type, primary_key=col.primary_key) )
        self.fulfillment_table = schema.Table( 'fapf', 
                                               self.metadata, 
                                               *fapf_table_columns )
        self.metadata.create_all()
