import unittest

from camelot.core.exception import UserException

from vfinance.admin import jinja2_filters as filters

class TestFilter( unittest.TestCase ):
    
    def test_user_exception(self):
        self.assertRaises(UserException, 
                          filters.user_exception,
                          {'text': 'test', 'detail': 'test exception '})