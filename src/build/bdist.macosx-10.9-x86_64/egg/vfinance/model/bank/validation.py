"""
Visual iban, is the iban number as seen/used by the end user or customer
Electronic iban, is the iban number used in electronic communication
"""

import string
import re

iban_regexp = re.compile('[A-Z]{2,2}[0-9]{2,2}[a-zA-Z0-9]{1,30}')
bic_regexp = re.compile('[A-Z]{6,6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3,3}){0,1}')
tax_id_regexp = re.compile('[A-Z]{2,2}[0-9]{7,12}')
country_tax_id_regexp = {'BE': re.compile('BE[0-9]{10,10}'),
                         }

def tax_id(tax_id):
    """Validate a Tax ID
    http://ec.europa.eu/taxation_customs/vies/faq.html#item_16
    
    :return: `True` or `False`
    """
    if tax_id is None:
        return True
    tax_id = electronic_iban(tax_id)
    if tax_id_regexp.match(tax_id) is None:
        return False
    regexp = country_tax_id_regexp.get(tax_id[0:2], None)
    if regexp is not None:
        if regexp.match(tax_id) is None:
            return False
    return True

def electronic_iban(iban):
    """
    Convert a visual iban number to an electronic iban number
    """
    # convert to uppercase
    uppercase_iban = ''
    for i, c in enumerate( iban ):
        if c in string.ascii_lowercase:
            uppercase_iban = uppercase_iban + string.ascii_uppercase[string.ascii_lowercase.index(c)]
        elif c in string.ascii_uppercase:
            uppercase_iban = uppercase_iban + c
        elif c in string.digits:
            uppercase_iban = uppercase_iban + c
    return uppercase_iban

def iban(iban):
    """Validate iban bank accounts.
    http://en.wikipedia.org/wiki/International_Bank_Account_Number
    
    :return: (valid, bic, message)
    """
    if len(iban) <= 4:
        return (False, '', 'Too short')
    uppercase_iban = electronic_iban(iban)
    if iban_regexp.match(uppercase_iban) is None:
        return (False, '', 'Invalid sequence')
    rearranged_iban = uppercase_iban[4:] + uppercase_iban[:4]
    converted_iban = ''
    for c in rearranged_iban:
        if c in string.ascii_uppercase:
            c = str( string.ascii_uppercase.index(c) + 10 )
        converted_iban = converted_iban + c
    remainder = int( converted_iban ) % 97
    if remainder != 1:
        return (False, '', 'Invalid checksum')
    return (True, '', '')

def checksum(number):
    remainder = number%97
    if remainder != 0:
        return remainder
    else:
        return 97

def split_ogm( ogm ):
    """
    split an ogm in it's integer base and a checksum

    :return: (base, check) both as integers, return None if the ogm could
             not be split
    """
    if ogm is None:
        return None, None
    code = ''.join( [ c for c in ''.join( ogm ) if c in string.digits] )
    if len(code) > 2:
        base = int(code[:-2].lstrip('0') or '0')
        check = int(code[-2:].lstrip('0') or '0')
        return base, check
    return None, None

def ogm( ogm ):
    """Validate an OGM
    
    :return: `True` or `False`
    """
    base, check = split_ogm(ogm)
    if base is not None:
        if (base%97 == check and check != 97) or (base%97 == 0 and check == 97):
            return True
    return False

def validate_bic( bic ):
    if bic_regexp.match(bic) is not None:
        return True
    return False
