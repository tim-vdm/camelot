import unittest

from vfinance.model.bank.validation import (validate_bic,
                                            iban as validate_iban,
                                            tax_id)

from vfinance.model.bank.admin import NumericValidator

class BicCase(unittest.TestCase):
    
    def test_validate_bic( self ):
        self.assertTrue(validate_bic('RABONL2U'))
        self.assertTrue(validate_bic('UNCRIT2B912'))
        self.assertTrue(validate_bic('KREDBEBB'))
        self.assertTrue(validate_bic('BBRUBEBB'))
        self.assertFalse(validate_bic('qwyetrweruiyourtpuoirpouyiweotieroyweotuyqeoyuiqet'))
        self.assertFalse(validate_bic(''))

class IbanCase(unittest.TestCase):
    
    def test_valid_nl( self ):
        (valid, bic, message) = validate_iban( 'NL91ABNA0417164300' )
        self.assertTrue( valid )
        #ABNANL2A  
        
    def test_valid_nl_lowercase( self ):
        (valid, bic, message) = validate_iban( 'nl91abna0417164300' )
        self.assertTrue( valid )
        
    def test_valid_nl_groups( self ):
        (valid, bic, message) = validate_iban( 'NL91 ABNA 0417 1643 00' )
        self.assertTrue( valid )
        
    def test_invalid_nl( self ):
        (valid, bic, message) = validate_iban( 'NL91ABNA0417174300' )
        self.assertFalse( valid )
        
    def test_unknown_country( self ):
        (valid, bic, message) = validate_iban( 'IQ91ABNA0417164300' )
        self.assertFalse( valid )
        
    def test_fr(self):
        (valid, bic, message) = validate_iban( 'FR76 1831 5100 0008 0039 7429 536' )
        self.assertTrue( valid )

class TaxIdCase(unittest.TestCase):

    def test_empty(self):
        self.assertTrue(tax_id(None))
        self.assertFalse(tax_id(''))
        self.assertFalse(tax_id('0'))

    def test_belgium(self):
        self.assertTrue(tax_id('BE0878169209'))
        self.assertTrue(tax_id('BE 0878.169.209'))
        self.assertFalse(tax_id('BE 0878.169.20'))
        self.assertFalse(tax_id('0878169209'))

    def test_unknown_country(self):
        self.assertTrue(tax_id('SY0878169209'))


class NumberValidatorCase(unittest.TestCase):

    def test_emtpy(self):
        from camelot.core.qt import QtGui
        validator = NumericValidator()
        self.assertEqual(validator.validate(None, 0), (QtGui.QValidator.Intermediate, 0))
        self.assertEqual(validator.validate('', 0), (QtGui.QValidator.Intermediate, 0))

    def test_valid(self):
        from camelot.core.qt import QtGui
        validator = NumericValidator()
        self.assertEqual(validator.validate('234', 3), (QtGui.QValidator.Acceptable, 3))
        self.assertEqual(validator.validate('2342342342', 10), (QtGui.QValidator.Acceptable, 10))

    def test_invalid(self):
        from camelot.core.qt import QtGui
        validator = NumericValidator()
        self.assertEqual(validator.validate('123a', 4), (QtGui.QValidator.Intermediate, 4))
        self.assertEqual(validator.validate('123-3', 6), (QtGui.QValidator.Intermediate, 6))

