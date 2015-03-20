import logging
import sys

LOGGER = logging.getLogger('vfinance_ws')

try:
    import cdecimal
    sys.modules["decimal"] = cdecimal
    LOGGER.info('using cdecimal instead of decimal')
except:
    LOGGER.info('using decimal, cdecimal import failed')
