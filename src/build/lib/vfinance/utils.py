'''
Created on Apr 6, 2010

@author: tw55413
'''

import logging
import datetime
logger = logging.getLogger('vfinance.utils')

_setup_done_ = False

def setup_model( update=True, templates=True ):
    # prevent this method being called multiple times
    # in unit tests
    global _setup_done_
    if _setup_done_:
        return

    from camelot.core.sql import metadata
    from camelot.core.conf import settings
    from camelot.core.memento import memento_types
    
    memento_types.extend( [(1000, 'run forward'),
                           (1001, 'run backward'),
                           (1002, 'force status'),
                           (1003, 'change status'),
                           (1004, 'facade creation')])

    from sqlalchemy import schema
    from camelot.core.orm import setup_all
    from camelot.model.authentication import update_last_login
    from camelot.model import authentication
    from camelot.model import party
    from camelot.model import i18n
    from camelot.model import memento
    from camelot.model import fixture
    from camelot.model import batch_job
    import vfinance.model
    import vfinance.facade
    #
    # some dummy code to prevent unused imports
    #
    logger.debug('loaded %s'%authentication.__name__)
    logger.debug('loaded %s'%party.__name__)
    logger.debug('loaded %s'%i18n.__name__)
    logger.debug('loaded %s'%memento.__name__)
    logger.debug('loaded %s'%fixture.__name__)
    logger.debug('loaded %s'%batch_job.__name__)
    logger.debug('loaded %s'%vfinance.model.__name__)
    logger.debug('loaded %s'%vfinance.facade.__name__)
    setup_all()
    #
    # Create an index for the accounting entries to speed them up
    #
    from vfinance.model.bank.entry import Entry, EntryPresence
    entry_table = Entry.table
    entry_presence_table = EntryPresence.table
    #
    # Prevent duplication of the indexes when the function is called
    # multiple times
    #
    entry_table_indexes = [i.name for i in entry_table.indexes]
    if 'ix_entry_keys' not in entry_table_indexes:
        schema.Index( 'ix_entry_keys', 
                      entry_table.c.book_date, 
                      entry_table.c.venice_doc,
                      entry_table.c.line_number )
        schema.Index( 'ix_entry_order', 
                      entry_table.c.book_date,
                      entry_table.c.venice_book,
                      entry_table.c.venice_doc,
                      entry_table.c.line_number,
                      entry_table.c.id )
        schema.Index( 'ix_hypo_entry_presence_unique_year',
                      entry_presence_table.c.entry_id,
                      entry_presence_table.c.venice_active_year,
                      entry_presence_table.c.venice_id,
                      unique = True )
        schema.UniqueConstraint( entry_table.c.book_date,
                                 entry_table.c.venice_book,
                                 entry_table.c.venice_doc,
                                 entry_table.c.line_number,
                                 name = 'hypo_betaling_hypo_betaling_unique')
    
    #
    # if the settings table does not exist, assume a database update
    # is needed
    #
    bind = metadata.bind
    from vfinance.model.bank.settings import Settings
    if not Settings.__table__.exists(bind):
        update = True
    if update:
        logger.warn('create all tables, this might take a while')
        connection = bind.connect()
        with connection.begin():
            metadata.create_all(connection)
    #
    # load all settings from the database
    #
    settings.load()
    from integration.win32 import setup_gencache
    setup_gencache()
    vf_roles = [ (1000, 'mortgage'),
                 (1001, 'mortgage_base'),
                 (1002, 'mortgage_detail'),
                 (2000, 'life_insurance'),
                 (2001, 'life_insurance_base'),
                 (2002, 'life_insurance_detail'),
                 (3000, 'accounting'),
                 (4000, 'configuration'),
                ]
    authentication.roles.extend( vf_roles )
    update_last_login( initial_group_name = 'Admin',
                       initial_group_roles = [name for _id, name in vf_roles] )
    #
    # add template loaders
    #
    if templates:
        from vfinance.model.financial.notification.environment import setup_templates
        setup_templates()
    _setup_done_ = True
    
    from sqlalchemy import orm, sql
    from vfinance.model.financial.account import FinancialAccount
    from vfinance.model.financial.premium import FinancialAccountPremiumSchedule
    from vfinance.model.financial.transaction import FinancialTransactionPremiumSchedule, FinancialTransaction
    faps_ftps = FinancialAccountPremiumSchedule.__table__.join(FinancialTransactionPremiumSchedule.__table__)
    
    FinancialAccount.transactions = orm.relationship( FinancialTransaction,
                                                      viewonly = True,
                                                      secondary = faps_ftps,
                                                      primaryjoin = FinancialAccount.id==FinancialAccountPremiumSchedule.financial_account_id,
                                                      secondaryjoin = sql.and_( FinancialTransaction.id==FinancialTransactionPremiumSchedule.within_id,
                                                                                FinancialAccountPremiumSchedule.id==FinancialTransactionPremiumSchedule.premium_schedule_id),
                                                      )

def str_to_date(str):
    return datetime.datetime.strptime(str, '%Y-%m-%d').date()
