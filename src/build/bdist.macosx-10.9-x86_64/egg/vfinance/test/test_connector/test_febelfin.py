import os

from camelot.test.action import MockModelContext

from vfinance.connector.febelfin.dom80_migration import SepaMigration

from ..test_case import SessionCase
from ..test_financial import test_data_folder
from .. import app_admin

class FebelfinCase(SessionCase):
    
    def test_sepa_migration(self):
        migration_action = SepaMigration()
        model_context = MockModelContext(session=self.session)
        model_context.admin = app_admin
        generator = migration_action.model_run(model_context)
        for i, step in enumerate(generator):
            if i==0:
                generator.send([os.path.join(test_data_folder, 'dom80migration.xls')])

