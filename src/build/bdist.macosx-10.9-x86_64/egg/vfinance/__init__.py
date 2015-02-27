"""Some boilerplate code for an empty project

This project is copied by the camelot-admin tool
when starting a new project
"""

#
# remove certain packages from the path, to make sure they are
# taken from the project egg instead of from the python distro
#
import sys
packages_to_remove = ['SQLAlchemy', 'sqlalchemy', 'camelot', 'Camelot']

entries_to_remove = []
for entry in sys.path:
    for to_remove in packages_to_remove:
        if to_remove in entry:
            entries_to_remove.append( entry )
            
for entry in entries_to_remove:
    sys.path.remove( entry )
    
import logging
logging_format = '[%(asctime)s]  [%(process)5d] [%(levelname)-5s] [%(name)-35s] - %(message)s'
logging.basicConfig(level=logging.INFO, format=logging_format)
LOGGER = logging.getLogger( 'vfinance' )

try:
    import cdecimal
    sys.modules["decimal"] = cdecimal
    LOGGER.info('using cdecimal instead of decimal')
except:
    LOGGER.info('using decimal, cdecimal import failed')
    
from camelot.core.conf import settings
from vfinance.model.bank.settings import VFinanceSettings
settings.append(VFinanceSettings())
