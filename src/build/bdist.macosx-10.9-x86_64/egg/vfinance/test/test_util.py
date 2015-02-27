import unittest

from sqlalchemy.exc import OperationalError

from vfinance.retry_generator import retry_generator, retry_function

class DecoratorCase(unittest.TestCase):
    
    def setUp(self):
        self.retry_counter = 0

    @retry_generator(OperationalError, delay=0.1)
    def always_failing_generator(self):
        for i in range(10):
            yield i
        self.raise_operational_error()

    @retry_generator(OperationalError, delay=0.1)
    def fail_first_time_generator(self):
        self.retry_counter += 1
        if self.retry_counter==1:
            self.raise_operational_error()
        for i in range(10):
            yield i

    @retry_function(OperationalError, delay=0.1)
    def always_failing_method(self):
        self.raise_operational_error()

    @retry_function(OperationalError, delay=0.1)
    def fail_first_time_method(self):
        self.retry_counter += 1
        if self.retry_counter==1:
            self.raise_operational_error()

    def raise_operational_error(self):
        raise OperationalError('Wooha', {}, None, None)
    
    def test_retry_generator(self):
        with self.assertRaises(OperationalError):
            list(self.always_failing_generator())
        list(self.fail_first_time_generator())

    def test_retry_function(self):
        with self.assertRaises(OperationalError):
            self.always_failing_method()
        self.fail_first_time_method()