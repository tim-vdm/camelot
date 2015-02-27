import collections
import logging

LOGGER = logging.getLogger('vfinance.model.bank.report.audit')

from camelot.core.utils import ugettext_lazy as _
from camelot.view.action_steps import UpdateProgress

from sqlalchemy import sql

from .abstract import AbstractReport

class AccountingAuditReport( AbstractReport ):

    name = _('Accounting Audit')

    product_class = None
    fulfillment_class = None
    
    def fill_sheet( self, sheet, offset, options ):

        from integration.spreadsheet.base import Cell
        from vfinance.model.bank.entry import Entry

        yield UpdateProgress( text = _('Loading accounting entries in memory') )

        entry_condition = sql.and_(
            Entry.book_date >= options.from_book_date,
            Entry.book_date <= options.thru_book_date
        )
        fulfillment_condition = sql.and_(
            self.fulfillment_class.entry_book_date >= options.from_book_date,
            self.fulfillment_class.entry_book_date <= options.thru_book_date,
        )
        entry_keys = dict()
        entry_query = sql.select( [ Entry.book_date, 
                                    Entry.venice_doc,
                                    Entry.venice_book,
                                    Entry.line_number,
                                    Entry.account] ).where(entry_condition)

        total_entries = Entry.query.session.execute( sql.select( [sql.func.count( Entry.id )] ).where(entry_condition) ).first()[0]

        for i, entry_data in enumerate(Entry.query.session.execute( entry_query )):
            entry_key = (entry_data.book_date,
                         entry_data.venice_doc,
                         entry_data.venice_book.lower(),
                         entry_data.line_number)
            entry_keys[entry_key] = entry_data.account
            if i%1000 == 0:
                yield UpdateProgress( i, total_entries )

        yield UpdateProgress( text = _('Loading premium schedule entries in memory') )

        fapf_keys = dict()
        fapf_query = sql.select( [ self.fulfillment_class.entry_book_date, 
                                   self.fulfillment_class.entry_document,
                                   self.fulfillment_class.entry_book,
                                   self.fulfillment_class.entry_line_number,
                                   self.fulfillment_class.account_suffix.label('account_suffix'),
                                   self.fulfillment_class.account_number_prefix.label('account_prefix'),
                                   self.fulfillment_class.id] ).where(fulfillment_condition)


        total_fapf_keys = Entry.query.session.execute( sql.select( [sql.func.count( self.fulfillment_class.id )] ).where(fulfillment_condition) ).first()[0]

        for i, fapf_data in enumerate(self.fulfillment_class.query.session.execute( fapf_query )):
            fapf_keys[ ( fapf_data.entry_book_date, 
                         fapf_data.entry_document, 
                         fapf_data.entry_book.lower(), 
                         fapf_data.entry_line_number ) ] = (fapf_data.id, fapf_data.account_suffix, fapf_data.account_prefix)
            if i%1000 == 0:
                yield UpdateProgress( i, total_fapf_keys )

        sheet.render( Cell( 'A', offset, 'Missing Accounting Documents' ) )
        offset += 2
        sheet.render( Cell( 'A', offset, 'Book' ) )
        sheet.render( Cell( 'B', offset, 'Book date' ) )
        sheet.render( Cell( 'C', offset, 'Document' ) )
        sheet.render( Cell( 'D', offset, 'Line' ) )
        offset += 2
        found = 0


        found = 0

        yield UpdateProgress( text = _('Look for missing accounting documents') )

        for i, (fapf_key, (fapf_id, fapf_account_suffix, fapf_account_prefix)) in enumerate( fapf_keys.items() ):

            if i%1000 == 0:
                yield UpdateProgress( i, total_fapf_keys, text = unicode(fapf_key[0]) )

            if fapf_key not in entry_keys:
                fulfillment = self.fulfillment_class.get( fapf_id )
                sheet.render( Cell( 'A', offset, fulfillment.entry_book ) )
                sheet.render( Cell( 'B', offset, fulfillment.entry_book_date ) )
                sheet.render( Cell( 'C', offset, fulfillment.entry_document ) )
                sheet.render( Cell( 'D', offset, fulfillment.entry_line_number ) )
                try:
                    sheet.render( Cell( 'E', offset, fulfillment.product_name ) )
                    sheet.render( Cell( 'F', offset, fulfillment.of.full_number ) )
                    sheet.render( Cell( 'G', offset, fulfillment.fulfillment_type ) )
                except Exception, e:
                    sheet.render( Cell( 'I', offset, unicode(e) ) )
                offset += 1
                found += 1
            if i%1000 == 0:
                LOGGER.debug( 'audited %s entries, %s found'%(i, found) )

        yield UpdateProgress( text = _('Look for unknown accounting documents') )

        offset += 2
        sheet.render( Cell( 'A', offset, 'Unknown Accounting Documents' ) )
        offset += 2
        found = 0

        # store for each prefix the allowed product id
        prefixes = collections.defaultdict(list)
        excluded_books = set()

        for product in self.product_class.query.all():
            if product.account_number_prefix:
                prefixes[str(product.account_number_prefix)].append(product.id)
            if product.accounting_year_transfer_book:
                excluded_books.add( product.accounting_year_transfer_book )
            if product.external_application_book:
                excluded_books.add( product.external_application_book )

        entry_query = sql.select( [ Entry.book_date, 
                                    Entry.venice_doc,
                                    Entry.venice_book,
                                    Entry.line_number,
                                    Entry.account,
                                    Entry.amount ] )
        entry_query = entry_query.where(entry_condition)
        entry_query = entry_query.where( Entry.amount != 0 )
        # the product definitions might have an empty book in the list of excluded books
        entry_query = entry_query.where( sql.or_( sql.not_( Entry.venice_book.in_( list(excluded_books) ) ),
                                                  Entry.venice_book == '' ))

        for prefix in prefixes:

            yield UpdateProgress( text = _('Look on accounts with prefix %s'%prefix) )

            total_entries = Entry.query.session.execute( sql.select( [sql.func.count( Entry.id )] ).where(entry_condition).where( Entry.amount != 0 ).where( Entry.account.like('%s%%'%prefix) ) ).first()[0]
            prefix_entry_query = entry_query.where( Entry.account.like('%s%%'%prefix) )
            for i, entry_data in enumerate(Entry.query.session.execute( prefix_entry_query )):
                entry_key = ( ( entry_data.book_date, 
                                entry_data.venice_doc, 
                                entry_data.venice_book.lower(), 
                                entry_data.line_number ) )
                fapf_id, fapf_account_suffix, fapf_account_prefix = fapf_keys.get(entry_key, (None, None, None))
                # we combine 2 searches here, those for entries that have no
                # fulfillment or those entries that have a fulfillment with
                # a different account suffix or prefix than the account of the entry
                # itself
                if (None in (fapf_id, fapf_account_suffix, fapf_account_prefix)) or (not entry_data.account.endswith(str(int(fapf_account_suffix)))) or (not entry_data.account.startswith(str(int(fapf_account_prefix)))):
                    sheet.render( Cell( 'A', offset, entry_data.book_date, ) )
                    sheet.render( Cell( 'B', offset, entry_data.venice_doc ) )
                    sheet.render( Cell( 'C', offset, entry_data.venice_book ) )
                    sheet.render( Cell( 'D', offset, entry_data.line_number ) )
                    sheet.render( Cell( 'E', offset, entry_data.account ) )
                    sheet.render( Cell( 'F', offset, entry_data.amount ) )
                    sheet.render( Cell( 'G', offset, fapf_account_suffix ) )
                    sheet.render( Cell( 'H', offset, fapf_account_prefix ) )
                    offset += 1
                    found += 1
                if i%1000 == 0:
                    yield UpdateProgress( i, total_entries )
                    LOGGER.debug( 'audited %s entries, %s found'%(i, found) )
