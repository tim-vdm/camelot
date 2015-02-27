"""
Helper classes to store and retrieve historical versions of entities.
"""

from camelot.core.exception import UserException
from camelot.core.utils import ugettext

from sqlalchemy import sql, orm, schema

from ...sql import date_sub

class HistoryMixin(object):

    @classmethod
    def store_version(cls, entity, at=sql.func.current_date()):
        """
        Store a the current version of the record.  This method should be
        called within a transaction.

        :param entity: the entity of which a version should be stored
        :param at: the from_date of the stored version, this should only
          be used for unit testing
        :return: the object representing the stored history
        """
        session = cls._validate_active(entity)
        history = cls.get_current_version(entity)
        stored_history = cls(_session=session)
        mapper = orm.class_mapper(cls)
        primary_key = list(mapper.primary_key)
        for key, col in mapper.columns.items():
            if col not in primary_key:
                value = getattr(history, key)
                setattr(stored_history, key, value)
        stored_history.thru_date = date_sub(at, 1)
        history.from_date = at
        return stored_history

    @classmethod
    def restore_version(cls, entity):
        """
        Restore the previous version of the record.  This method should be
        called within a transaction.
        """
        cls._validate_active(entity)
        history = cls.get_previous_version(entity)
        cls.store_version(entity)
        mapper = orm.class_mapper(type(entity))
        primary_key = list(mapper.primary_key)
        for key, col in mapper.columns.items():
            if isinstance(col, schema.Column):
                if col.key == 'version_id':
                    continue
                if col not in primary_key:
                    value = getattr(history, key)
                    setattr(entity, key, value)

    @classmethod
    def _validate_active(cls, entity):
        session = orm.object_session(entity)
        if session is None:
            raise Exception('Current object not in a session')
        if session.is_active != True:
            raise Exception('Current session not in an active transaction')
        return session

    @classmethod
    def get_current_version(cls, entity):
        """
        :return: a history object representing the current entity state
        """
        session = orm.object_session(entity)
        version_id = entity.version_id
        current_version_query = session.query(cls).populate_existing()
        current_version_query = current_version_query.filter(
            sql.and_(cls.from_date <= sql.func.current_date(),
                     cls.thru_date >= sql.func.current_date(),
                     cls.history_of_id == entity.history_of_id)
        )
        current_versions = current_version_query.all()
        if len(current_versions) != 1:
            raise Exception('More than 1 current version')
        current_version = current_versions[0]
        if current_version.version_id != version_id:
            raise UserException(ugettext('Concurrent change by another user'),
                                resolution=ugettext('Use refresh to validate the changes'),
                                detail='Concurrent change created version {0}, the expected version was {1}'.format(current_version.version_id, version_id)
                                )
        return current_version

    @classmethod
    def get_previous_version(cls, entity):
        """
        :return: a history object representing the previous entity state, raises
            an exception when there is no history object, or the history object
            doesn't represent the previous state.
        """
        session = orm.object_session(entity)
        current_version = cls.get_current_version(entity)
        previous_version_id = current_version.version_id - 1
        previous_version_query = session.query(cls).populate_existing()
        previous_version_query = previous_version_query.filter(
            sql.and_(cls.thru_date < sql.func.current_date(),
                     cls.from_date <= sql.func.current_date(),
                     cls.history_of_id == entity.history_of_id,
                     )
        )
        previous_version_query = previous_version_query.order_by(cls.version_id.desc())
        previous_version = previous_version_query.first()
        if (previous_version is None) or (previous_version.version_id != previous_version_id):
            raise UserException(ugettext('History unavailable'),
                                resolution=ugettext('Unable to restore the previous state'),
                                detail='Required version is {0}'.format(previous_version_id))
        return previous_version
