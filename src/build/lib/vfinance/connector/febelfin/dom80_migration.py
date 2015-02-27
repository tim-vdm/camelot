"""
Wizard to migrate DOM80 direct debit mandates to SEPA
"""

import datetime

from camelot.admin.action import Action
from camelot.admin.object_admin import ObjectAdmin
from camelot.admin.validator.object_validator import ObjectValidator
from camelot.view.art import ColorScheme
from camelot.core.exception import UserException
from camelot.core.utils import ugettext_lazy as _
from camelot.view import action_steps
from camelot.view.controls import delegates
from camelot.view.import_utils import (XlsReader, ColumnMapping, 
                                       ColumnMappingAdmin)

from sqlalchemy import sql

from ...model.bank.validation import iban, ogm, validate_bic
from ...model.bank.direct_debit import DirectDebitMandate, BankIdentifierCode
from ...application_admin import FinanceApplicationAdmin

class MandateMigrationValidator(ObjectValidator):
    
    def validate_object(self, obj):
        for value in (obj.bic, obj.iban, obj.local):
            if not value:
                return ['Incomplete']
        if not validate_bic(obj.bic):
            return ['Invalid BIC']
        if not iban(obj.iban)[0]:
            return ['Invalid IBAN']
        if not ogm(obj.local):
            return ['Invalid local mandate']
        return []

class MandateMigration(object):
    
    def __init__(self):
        self.iban = None
        self.bic = None
        self.local = None
        self.color = None
    
    class Admin(ObjectAdmin):
        list_display = ['local', 'iban', 'bic']
        field_attributes = {'local': {'background_color': lambda o:o.color},
                            'iban': {'background_color': lambda o:o.color},
                            'bic': {'background_color': lambda o:o.color},
                            }
        validator = MandateMigrationValidator

class Options(object):
    
    def __init__(self):
        self.migration_date = datetime.date.today()
    
    class Admin(ObjectAdmin):
        list_display = ['migration_date']
        field_attributes = {'migration_date': {'editable': True,
                                               'name': 'Use new mandate as of',
                                               'delegate': delegates.DateDelegate}}

class SepaMigration(Action):
    
    verbose_name = _('Migrate Direct Debit Mandates')
    tooltip = _('Migrate local mandates to SEPA')
    
    def model_run(self, model_context):
        step = action_steps.SelectFile()
        step.caption = _('Select migration spreadsheet')
        filenames = yield step
        mandate_migrations = []
        mandate_migration_admin = model_context.admin.get_related_admin(MandateMigration)
        validator = MandateMigrationValidator(mandate_migration_admin)
        for filename in filenames:
            yield action_steps.UpdateProgress(text='Reading spreadsheet')
            items = list(XlsReader(filename))
            if not len(items):
                raise UserException('Empty file')
            mappings = [ColumnMapping(i, items) for i in range(len(items[0]))]
            mapping_admin = ColumnMappingAdmin(mandate_migration_admin,
                                               field_choices=[('local', 'Local Mandate reference'),
                                                              ('iban',  'IBAN'),
                                                              ('bic',   'BIC'),
                                                              ])
            yield action_steps.ChangeObjects(mappings, mapping_admin)
            for item in items:
                mandate_migration = MandateMigration()
                for mapping in mappings:
                    if mapping.field is not None:
                        setattr(mandate_migration, 
                                mapping.field,
                                item[mapping.column])
                if len(validator.validate_object(mandate_migration)):
                    mandate_migration.color = ColorScheme.pink_1
                mandate_migrations.append(mandate_migration)
        yield action_steps.ChangeObjects(mandate_migrations,
                                         mandate_migration_admin)
        options = Options()
        yield action_steps.ChangeObject(options)
        session = model_context.session
        with session.begin():
            yield action_steps.UpdateProgress(text='load existing mandates')
            existing_mandates = session.query(DirectDebitMandate).filter(sql.and_(DirectDebitMandate.from_date<=options.migration_date,
                                                                                  DirectDebitMandate.thru_date>=options.migration_date)).all()
            for i, mandate_migration in enumerate(mandate_migrations):
                yield action_steps.UpdateProgress(i, 
                                                  len(mandate_migrations),
                                                  text=u'evaluate {0.local}'.format(mandate_migration)
                                                  )
                if not mandate_migration.local:
                    continue
                found = False
                for existing_mandate in existing_mandates:
                    existing_mandate_id = existing_mandate.get_identification()
                    if not existing_mandate_id:
                        continue
                    if existing_mandate_id == mandate_migration.local.replace('-','').replace('/','').strip():
                        bic = session.query(BankIdentifierCode).filter(BankIdentifierCode.code==mandate_migration.bic).first()
                        if not bic:
                            bic = BankIdentifierCode(code=mandate_migration.bic,
                                                     name=mandate_migration.bic,
                                                     country=u'BE')
                            yield action_steps.UpdateProgress(detail=u'create new bic {0.bic}'.format(mandate_migration))
                        mandate = DirectDebitMandate(from_date=options.migration_date,
                                                     identification=existing_mandate.identification,
                                                     financial_agreement_id=existing_mandate.financial_agreement_id,
                                                     financial_account_id=existing_mandate.financial_account_id,
                                                     hypotheek_id=existing_mandate.hypotheek_id,
                                                     bank_identifier_code=bic,
                                                     iban=mandate_migration.iban,
                                                     date=options.migration_date,
                                                     modification_of_id=existing_mandate.id)
                        for dossier in existing_mandate.dossiers:
                            dossier.direct_debit_mandates.append(mandate)
                        existing_mandate.thru_date = options.migration_date - datetime.timedelta(days=1)
                        yield action_steps.FlushSession(model_context.session)
                        found = True
                        yield action_steps.UpdateProgress(detail=u'{0.local} : mandate {1.id} migrated to {0.iban}'.format(mandate_migration,
                                                                                                                           existing_mandate))
                if found is False:
                    yield action_steps.UpdateProgress(detail=u'{0.local} : no existing mandate found '.format(mandate_migration))
        yield action_steps.Refresh()
        yield action_steps.UpdateProgress(text='Finished', blocking=True)

FinanceApplicationAdmin.configuration_actions.append(SepaMigration())
