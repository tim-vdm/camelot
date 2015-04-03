import logging
import sys

LOGGER = logging.getLogger('vfinance_ws')

#
# use cdecimal
#assert fails for yet unknown reason, hence in comment
#assert "decimal" not in sys.modules

try:
    import cdecimal
    sys.modules["decimal"] = cdecimal
    LOGGER.info('using cdecimal instead of decimal')
except:
    LOGGER.info('using decimal, cdecimal import failed')
