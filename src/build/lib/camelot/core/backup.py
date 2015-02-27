#  ============================================================================
#
#  Copyright (C) 2007-2013 Conceptive Engineering bvba. All rights reserved.
#  www.conceptive.be / info@conceptive.be
#
#  This file is part of the Camelot Library.
#
#  This file may be used under the terms of the GNU General Public
#  License version 2.0 as published by the Free Software Foundation
#  and appearing in the file license.txt included in the packaging of
#  this file.  Please review this information to ensure GNU
#  General Public Licensing requirements will be met.
#
#  If you are unsure which license is appropriate for your use, please
#  visit www.python-camelot.com or contact info@conceptive.be
#
#  This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
#  WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#
#  For use of this library in commercial applications, please contact
#  info@conceptive.be
#
#  ============================================================================
import logging

import six
from sqlalchemy import types, sql

from .qt import QtGui

from camelot.core.utils import ugettext as _
from camelot.core.sql import metadata as default_metadata

logger = logging.getLogger('camelot.core.backup')

class BackupMechanism(object):
    """Create a backup of the current database to an sqlite database stored in 
    a file.
    
    The backupmechanism always considers the schema of the backed up database
    as the master, and never that of the backup.  This means that when a backup
    is made, the backup file is first removed, and then filled with the tables
    from the the database to backup.  When a restore is done, the schema of the
    database is not touched, but the tables are emptied and the data from the
    backup is copied into the existing schema.
    """
    
    def __init__(self, filename, storage=None, metadata=None):
        """Backup and restore to a file using it as an sqlite database.
        :param filename: the name of the file in which to store the backup, this
        can be either a local file or the name of a file in the storage.
        :param storage: a storage in which to store the file, if None is given,
        it is assumed that the file should be stored or retrieved from the local
        filesystem.
        :param metadata: the metadata of the database to be backed up or restored,
            this defaults to the `metadata` object of :module:`camelot.core.sql`.
            This metadata object should not contain any dialect specific constructs.
        """
        self.filename = six.text_type(filename)
        self.storage = storage
        self.metadata = metadata or default_metadata

    @classmethod
    def get_filename_prefix(cls):
        """
        :return: a string with the prefix for the default name of the backup file
        
        By default this method returns 'backup', overwrite this method to
        return a custom string, like the name of the company or such.
        
        This method will be called inside the model thread.
        """
        return u'backup'
    
    @classmethod
    def get_default_storage(cls):
        """
        :return: a camelot.core.files.storage.Storage object
        
        Returns the storage to be used to store default backups.
        
        By default, this will return a Storage that puts the backup files
        in the DataLocation as specified by the QDesktopServices
        """
        apps_folder = six.text_type(QtGui.QDesktopServices.storageLocation(QtGui.QDesktopServices.DataLocation))
        
        from camelot.core.files.storage import Storage
        return Storage(upload_to='backups', root=apps_folder)
        
    def backup_table_filter(self, from_table):
        """
        Method used to filter which tables should be backed up, overwrite this method
        for taking into account specific schema issues.
        
        :from_table: the table that is considered for backup
        :return: True when the table should be backed up
        """
        return True
    
    def restore_table_filter(self, from_table):
        """
        Method used to filter which tables should be restored, overwrite this method
        for taking into account specific schema issues.  restore_table_filter is different
        from backup_table_filter, since we might want to store data in the backup that 
        should not be restored, like schema version information.
        
        :from_table: the table that is considered for backup
        :return: True when the table should be restored
        """
        return True
    
    def prepare_schema_for_restore(self, from_connection, to_connection):
        """This method will be called before the actual restore starts.  It allows bringing
        the schema at the same revision as the backed up data.
        """
        pass

    def update_schema_after_restore(self, from_connection, to_connection):
        """This method will be called after the restore has been done.  It allows bringing
        the schema at the revision the application expects.
        """
        pass

    def backup(self, from_engine):
        """Generator function that yields tuples :
        (numer_of_steps_completed, total_number_of_steps, description_of_current_step)
        while performing a backup.
        
        :param from_engine: a :class:`sqlalchemy.engine.Engine` object that
            provides a connection to the database to be backed up.
        """
        import os
        import tempfile
        import shutil
        from sqlalchemy import create_engine
        from sqlalchemy import MetaData
        from sqlalchemy.pool import NullPool
        
        yield (0, 0, _('Analyzing database structure'))
        from_meta_data = self.metadata

        yield (0, 0, _('Preparing backup file'))
        #
        # We'll first store the backup in a temporary file, since
        # the selected file might be on a server or in a storage
        #
        file_descriptor, temp_file_name = tempfile.mkstemp(suffix='.db')
        os.close(file_descriptor)
        logger.info("preparing backup to '%s'"%temp_file_name)
        if os.path.exists(self.filename):
            os.remove(self.filename)
        to_engine = create_engine( u'sqlite:///%s'%temp_file_name, poolclass=NullPool)
        to_connection = to_engine.connect()
        to_meta_data = MetaData()
        #
        # Only copy tables, to prevent issues with indices and constraints
        #
        from_and_to_tables = []
        for from_table in from_meta_data.sorted_tables:
            if self.backup_table_filter(from_table):
                to_table = from_table.tometadata(to_meta_data)
                to_table.constraints = set()
                to_table.primary_key = []
                to_table.foreign_keys = set()
                from_and_to_tables.append((from_table, to_table))
        to_meta_data.create_all(to_connection)

        number_of_tables = len(from_and_to_tables)
        with from_engine.begin() as from_connection:
            for i,(from_table, to_table) in enumerate(from_and_to_tables):
                yield (i, number_of_tables + 1, _('Copy data of table %s')%from_table.name)
                self.copy_table_data(from_table, to_table,
                                     from_connection, to_connection)
        yield (number_of_tables, number_of_tables + 1, _('Store backup at requested location') )
        to_connection.close()
        to_engine.dispose()
        if not self.storage:
            logger.info(u'move backup file to its final location')
            shutil.move(temp_file_name, self.filename)
        else:
            logger.info(u'check backfup file in to storage with name %s'%self.filename)
            self.storage.checkin( temp_file_name, self.filename )
            os.remove( temp_file_name )
        yield (number_of_tables + 1, number_of_tables + 1, _('Backup completed'))
    
    def restore(self, to_engine):
        """Generator function that yields tuples :
        (numer_of_steps_completed, total_number_of_steps, description_of_current_step)
        while performing a restore.

        :param to_engine: a :class:`sqlalchemy.engine.Engine` object that
            provides a connection to the database to be backed up.
        """
        #
        # The restored database may contain different AuthenticationMechanisms
        #
        from camelot.model.authentication import clear_current_authentication
        clear_current_authentication()
        #
        # Proceed with the restore
        #
        import os
        from camelot.core.files.storage import StoredFile
        from sqlalchemy import create_engine
        from sqlalchemy import MetaData
        from sqlalchemy.pool import NullPool

        yield (0, 0, _('Open backup file'))
        if self.storage:
            if not self.storage.exists(self.filename):
                raise Exception('Backup file does not exist')
            stored_file = StoredFile(self.storage, self.filename)
            filename = self.storage.checkout( stored_file )
        else:
            if not os.path.exists(self.filename):
                raise Exception('Backup file does not exist')
            filename = self.filename
        from_engine = create_engine('sqlite:///%s'%filename, poolclass=NullPool )
        from_connection = from_engine.connect()

        yield (0, 0, _('Analyzing database structure'))
        from_meta_data = MetaData()
        to_meta_data = self.metadata
        to_tables = to_meta_data.sorted_tables
        for to_table in to_tables:
            if self.restore_table_filter(to_table):
                to_table.tometadata(from_meta_data)

        with to_engine.begin() as to_connection:
            yield (0, 0, _('Prepare database for restore'))
            self.prepare_schema_for_restore(from_connection, to_connection)
    
            yield (0, 0, _('Analyzing database structure'))
            number_of_tables = len(to_tables)
            steps = number_of_tables * 2 + 2
            
            for i,to_table in enumerate(reversed(to_tables)):
                yield (i, steps, _('Delete data from table %s')%to_table.name)
                self.delete_table_data(to_table, to_connection)
    
            for i,to_table in enumerate(to_tables):
                if to_table.name in from_meta_data.tables:
                    yield (number_of_tables+i, steps, _('Copy data from table %s')%to_table.name)
                    self.copy_table_data(from_meta_data.tables[to_table.name], to_table,
                                         from_connection, to_connection)
                    
            yield (number_of_tables * 2 + 1, steps, _('Update schema after restore'))
            self.update_schema_after_restore(from_connection, to_connection)
        from_connection.close()
        from_engine.dispose()
        
        yield (1, 1, _('Restore completed'))

    def delete_table_data(self, to_table, to_connection):
        """This method might be subclassed to turn off/on foreign key checks"""
        to_connection.execute(to_table.delete())

    def copy_table_data(self, from_table, to_table, from_connection, to_connection):
        query = sql.select([from_table])
        to_dialect = to_connection.engine.url.get_dialect().name
        table_data = [row for row in from_connection.execute(query).fetchall()]
        if len(table_data):
            to_connection.execute(to_table.insert(), table_data)
            if to_dialect == 'postgresql':
                for column in to_table.columns:
                    if isinstance(column.type, types.Integer) and column.autoincrement==True and column.primary_key==True:
                        column_name = column.name
                        table_name = to_table.name
                        seq_name = table_name + "_" + column_name + "_seq"
                        to_connection.execute("select setval('%s', max(%s)) from %s" % (seq_name, column_name, table_name))

