import os
import functools

from sqlalchemy.engine import create_engine

from camelot.core.conf import settings
from camelot.core.orm import Session
from camelot.core.sql import metadata

from vfinance.model.bank.settings import SettingsProxy
from vfinance.utils import setup_model as setup_vfinance_model
from vfinance.facade.financial_agreement import FinancialAgreementFacade

from flask import request
import werkzeug.exceptions

# DB_FILENAME = '/home/stephane/vfinance_26022015/src/packages.db'
# DB_FILENAME = '/home/www/staging-patronale-life.mgx.io/src-preprod/src/packages.db'
# DB_FILENAME = '/Users/jeroen/Projects/v-finance-web-service/conf/packages.db'
DB_FILENAME = os.environ['DB_PATH']  # :raises: `KeyError` when env var DB_PATH is not set


def with_session(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        settings.append(SettingsProxy(None))

        db_filename = DB_FILENAME

        engine = create_engine('sqlite:///' + db_filename)

        metadata.bind = engine

        setup_vfinance_model(update=False, templates=False)

        session = Session()
        try:
            return function(session, *args, **kwargs)
        finally:
            session.close()

    return wrapper


def is_json_body():
    try:
        return request.get_json()
    except werkzeug.exceptions.BadRequest:
        return None


@with_session
def get_next_agreement_code(session):
    return FinancialAgreementFacade.next_agreement_code(session)
