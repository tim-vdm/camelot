# Module for switching between decimals and floats for use as real numbers.

from decimal import Decimal, ROUND_FLOOR
from math import floor as float_floor
from functools import wraps

DECIMAL = True
FLOAT   = False

_use_decimals = False

def set_real_mode(mode):
    """
    Sets the real-number mode. Mode can be DECIMAL or FLOAT. 
    """
    global _use_decimals
    _use_decimals = mode
    
def get_real_mode():
    """
    Returns DECIMAL (true) when in decimal mode, FLOAT (false) when in float mode.
    """
    return _use_decimals
    
def real(number = 0, *args):
    """
    Returns a real number. According to the mode set using set_real_mode, this function returns either a decimal or a float.
    
    :param number: input to be converted to either float or decimal. Can be a string, float or decimal.
    """
    global _use_decimals
    if _use_decimals:
        return Decimal(str(number), *args)
    else:
        return float(number)

def floor(real_number):
    """
    Returns floor function (round down to nearest integer) of a real number.
    """
    global _use_decimals
    if _use_decimals:
        return real_number.to_integral_value(rounding=ROUND_FLOOR)
    else:
        return float_floor(real_number)  

def quantize(real_number, quantization_string, *args, **kwargs):
    """
    Rounds a real number. Same as decimal.quantize, but valid for both floats and decimals.
    quantization_string is a string representing a decimal that indicates the required quantization.
    """
    global _use_decimals
    if _use_decimals:
        return real_number.quantize( Decimal(quantization_string), *args, **kwargs )
    else:
        d = Decimal(str(real_number))
        return float ( d.quantize( Decimal(quantization_string), *args, **kwargs ) )

def to_decimal(real_number, *args, **kwargs):
    """
    Converts number to decimal, whether it is a float or not.
    """
    return Decimal(str(real_number), *args, **kwargs)

def reset_to_decimal_mode(method):
    """
    Decorator used to reset to decimal mode after the function ends,
    both in case of normal return and in case of exception.
    """
    @wraps(method)  # to preserve names in stacktraces etc.
    def new_method(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        finally:
            set_real_mode(DECIMAL)
    return new_method

def reset_to_previous_real_mode(method):
    """
    Decorator used to reset the decimal mode that was active before the function call,
    in case of normal return and in case of exception.
    """
    @wraps(method)  # to preserve names in stacktraces etc.
    def new_method(*args, **kwargs):
        prev_mode = get_real_mode()
        try:
            return method(*args, **kwargs)
        finally:
            set_real_mode(prev_mode)
    return new_method
