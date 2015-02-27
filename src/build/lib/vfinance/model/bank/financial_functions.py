import decimal
from decimal import Decimal as D
import logging

LOGGER = logging.getLogger('vfinance.model.bank.financial_functions')

ONE_HUNDRED = D(100)
ONE = D(1)
ONE_TENTH =      D('0.01') # Wooha, how wrong can this be
ONE_HUNDREDTH =  D('0.01')
ONE_THOUSANDTH = D('0.001')
ONE_MILLIONTH =  D('0.000001')
ZERO = D(0)

LOGGER = logging.getLogger( 'vfinance.model.financial.formulas' )

def round_up( unrounded ):
    if isinstance( unrounded, int ):
        return unrounded
    return unrounded.quantize(ONE_HUNDREDTH, rounding=decimal.ROUND_HALF_UP)

def round_down( unrounded ):
    if isinstance( unrounded, int ):
        return unrounded
    return unrounded.quantize(ONE_HUNDREDTH, rounding=decimal.ROUND_HALF_DOWN)

def round_floor( unrounded ):
    if isinstance( unrounded, int ):
        return unrounded
    return unrounded.quantize(ONE_HUNDREDTH, rounding=decimal.ROUND_FLOOR)

def pmt( rate, payments, present_value ):
    LOGGER.debug('pmt : %s %s %s'%(rate, payments, present_value))
    if payments == 0:
        return None
    if rate == 0:
        return present_value/payments
    return present_value*D(rate) / (1 - ( (1 + D(rate) )**(-1 * payments) ) )

def value_left( rate, payments, pmt, present_value):
    if rate != 0:
        rate_plus_1 = rate + 1
        return present_value*(rate_plus_1**payments) + pmt * (1-rate_plus_1**payments)/rate
    else:
        return present_value - pmt * payments

def present_value( rate, payments, pmt ):
    return pmt / D(rate) * (1 - ( (1 + D(rate) )**(-1 * payments) ) )
