import datetime
import unittest
import dateutil

from vfinance.model.financial.notification import utils


class NotificationCase(unittest.TestCase):

    def test_calculate_duration(self):
        d1 = datetime.date(1900, 4, 10)
        d2 = datetime.date(1900, 7, 10)
        calculated_duration = utils.calculate_duration(d1, d2)
        self.assertEqual(calculated_duration, 3)
        self.assertEqual(d1 + dateutil.relativedelta.relativedelta(months=+3), d2)

        d1 = datetime.date(2014, 3, 31)
        d2 = datetime.date(2014, 4, 30)
        calculated_duration = utils.calculate_duration(d1, d2)
        self.assertEqual(calculated_duration, 0)
        self.assertEqual(d1 + dateutil.relativedelta.relativedelta(months=+1), d2)

        d1 = datetime.date(2014, 2, 28)
        d2 = datetime.date(2014, 4, 30)
        calculated_duration = utils.calculate_duration(d1, d2)
        self.assertEqual(calculated_duration, 2)
        self.assertEqual(d1 + dateutil.relativedelta.relativedelta(months=+2),
                         datetime.date(2014, 4, 28))
