import sqlalchemy.types

import logging
import os

from sqlalchemy import schema, event

from camelot.core.orm import Entity, using_options
from camelot.admin.entity_admin import EntityAdmin
from camelot.core.utils import ugettext_lazy as _

from camelot.core.qt import QtGui

LOGGER = logging.getLogger(__name__)

constants = ['VENICE_FOLDER', 'VENICE_DOSSIER', 'VENICE_INITIALS', 'VENICE_USER', 'VENICE_PASSWORD', 'VENICE_SECURE',
             'VENICE_VERSION', 'TEMPLATES_FOLDER', 'ATTACHMENT_FOLDER', 'CLIENT_TEMPLATES_FOLDER',
             'CLIENT_TEMP_FOLDER',

             'SEPA_DIRECT_DEBIT_IBAN', 'SEPA_DIRECT_DEBIT_BIC', 'SEPA_CREDITOR_IDENTIFIER',
             'SEPA_DIRECT_DEBIT_IBAN_1', 'SEPA_DIRECT_DEBIT_BIC_1', 'SEPA_CREDITOR_IDENTIFIER_1',
             'SEPA_DIRECT_DEBIT_IBAN_2', 'SEPA_DIRECT_DEBIT_BIC_2', 'SEPA_CREDITOR_IDENTIFIER_2',
             'SEPA_DIRECT_DEBIT_IBAN_3', 'SEPA_DIRECT_DEBIT_BIC_3', 'SEPA_CREDITOR_IDENTIFIER_3',
             'SEPA_DIRECT_DEBIT_IBAN_4', 'SEPA_DIRECT_DEBIT_BIC_4', 'SEPA_CREDITOR_IDENTIFIER_4',
             'SEPA_DIRECT_DEBIT_IBAN_5', 'SEPA_DIRECT_DEBIT_BIC_5', 'SEPA_CREDITOR_IDENTIFIER_5',
             'SEPA_DIRECT_DEBIT_IBAN_6', 'SEPA_DIRECT_DEBIT_BIC_6', 'SEPA_CREDITOR_IDENTIFIER_6',
             'SEPA_DIRECT_DEBIT_IBAN_7', 'SEPA_DIRECT_DEBIT_BIC_7', 'SEPA_CREDITOR_IDENTIFIER_7',
             'SEPA_DIRECT_DEBIT_IBAN_8', 'SEPA_DIRECT_DEBIT_BIC_8', 'SEPA_CREDITOR_IDENTIFIER_8',
             'SEPA_DIRECT_DEBIT_IBAN_9', 'SEPA_DIRECT_DEBIT_BIC_9', 'SEPA_CREDITOR_IDENTIFIER_9',
             'SEPA_DIRECT_DEBIT_IBAN_10', 'SEPA_DIRECT_DEBIT_BIC_10', 'SEPA_CREDITOR_IDENTIFIER_10',

             'BANK_ACCOUNT_SUPPLIER',

             'HYPO_DOSSIER_STEP', 'HYPO_ACCOUNT_KLANT',
             'HYPO_MEDEDELING_AFLOSSING', 'HYPO_DAGBOEK_AFLOSSING', 'HYPO_DAGBOEK_AFKOOP',
             'HYPO_RAPPEL_KOST', 'HYPO_COMPANY_ID',
             'HYPO_FROM_SUPPLIER', 'HYPO_THRU_SUPPLIER',

             'BOND_ACCOUNT_BONDS', 'BOND_DAGBOEK_BESTELLING', 'BOND_ACCOUNT_INTREST',
             'BOND_CENTRALISERENDE_INSTELLING', 'BOND_REKENINGNUMMER', 'BOND_NAAM_OPDRACHTGEVER', 'BOND_IDENTIFICATIE_AFGEVER',

             'FINANCIAL_ACCOUNT_PREMIUMS_RECEIVED', 'FINANCIAL_SECURITY_ACCOUNT_PREFIX', 'FINANCIAL_SECURITY_DIGITS',
             'FINANCIAL_SECURITY_LIABILITY_PREFIX',

             'AWS_ACCESS_KEY', 'AWS_SECRET_KEY', 'AWS_QUEUE_IN_NAME',

             'COMPANY_NAME', 'COMPANY_STREET1', 'COMPANY_STREET2', 'COMPANY_CITY_CODE', 'COMPANY_CITY_NAME', 'COMPANY_COUNTRY_CODE',
             'COMPANY_COUNTRY_NAME',

             'GOV_BE_COMPANY_NUMBER',

             'VFINANCE_DOSSIER_NAME', 'VFINANCE_MAX_WORKERS',
             ]

coda_settings = ['CENTRALISERENDE_INSTELLING',
                 'IDENTIFICATIE_AFGEVER',
                 'IDENTIFICATIE_SCHULDEISER',
                 'REKENINGNUMMER',
                 'NAAM_SCHULDEISER', ]

constants.extend(['CODA_%s' % setting for setting in coda_settings])

for i in range(5):
    constants.extend(['CODA_%i_%s' % (i, setting) for setting in coda_settings])

constants.sort()


class Settings(Entity):
    """Global bank settings, like location of the venice data"""
    using_options(tablename='bank_settings', order_by=['id'])
    value = schema.Column(sqlalchemy.types.Unicode(250), nullable=False)
    key = schema.Column(sqlalchemy.types.Unicode(250), nullable=False)
    # fields for tinyerp compatibility
    perm_id = schema.Column(sqlalchemy.types.Integer(), nullable=True)

    class Admin(EntityAdmin):
        verbose_name_plural = _('Settings')
        list_display = ['key', 'value']
        field_attributes = {'value': {'editable': True,
                                      'name': _('Value'),
                                      'minimal_column_width': 30},
                            'key': {'editable': True,
                                    'name': _('Key'),
                                    'choices': lambda o: [(c, c) for c in constants],
                                    'minimal_column_width': max(len(c) for c in constants)}}


class VFinanceSettings(object):
    """class to be used in combination with :class:`camelot.core.conf.settings`
    to attach the non database V-Finance settings to Camelot.
    """

    CAMELOT_DBPROFILES_CIPHER = 'rent'
    REPOSITORY = 'repository'
    VENICE_DISCONNECT_WIZ_ID = 1

class SettingsProxy(object):
    """class to be used in combination with :class:`camelot.core.conf.settings`
    to attach the database V-Finance settings to Camelot.
    """

    def __init__(self, profile):
        self._engine = None
        self.profile = profile

    def CAMELOT_MEDIA_ROOT(self, *args, **kwargs):
        return self.profile.media_location

    @property
    def LOG_FOLDER(self):
        data_location = QtGui.QDesktopServices.storageLocation(QtGui.QDesktopServices.DataLocation)
        log_folder = os.path.join(unicode(data_location), 'V-Finance', 'logs')
        if not os.path.exists(log_folder):
            try:
                os.makedirs(log_folder)
            except Exception, e:
                LOGGER.error('could not create local log folder', exc_info=e)
                return None
        return log_folder

    @property
    def LOG_FILENAME(self):
        return u'application-logs.txt'

    def ENGINE(self, **kwargs):
        if self._engine is None:
            kwargs.setdefault('pool_recycle', 3600)
            self._engine = self.profile.create_engine(**kwargs)
            if self._engine.dialect.name == 'postgresql':

                @event.listens_for(self._engine.pool, 'connect')
                def receive_connect(dbapi_connection, connection_record):
                    "setup dbabi specific connection defaults"
                    LOGGER.debug('set lock timeout for database connection')
                    cursor = dbapi_connection.cursor()
                    # lock timeout only support as of pg 9.3 or so
                    #cursor.execute('set lock_timeout to 1000;')
                    cursor.close()

        return self._engine

    def setup_model(self):
        from vfinance.utils import setup_model
        setup_model(False)

    def load(self):
        #
        # set default settings here
        #
        for s in Settings.query.all():
            setattr(self, s.key, s.value)
