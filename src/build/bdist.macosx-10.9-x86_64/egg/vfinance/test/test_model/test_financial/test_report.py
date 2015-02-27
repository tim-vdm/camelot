import datetime
import logging
import string

from camelot.core.conf import settings
from camelot.model.party import end_of_times

from integration.spreadsheet.base import Expression
from integration.spreadsheet.xlsx import XlsxSpreadsheet

from vfinance.model.financial.report_action import FinancialReportAction
from vfinance.model.financial import report as reports
from vfinance.model.financial.premium import (
    FinancialAccountPremiumScheduleHistory as FAPSH,
    FinancialAccountPremiumSchedule as FAPS,
)

from ... import test_branch_21, test_financial

LOGGER = logging.getLogger(__package__)


class FinancialReportCase(test_financial.AbstractFinancialCase):

    # a single premium schedule is created during the setup of the class,
    # so the premium schedule should not be modified during the individual
    # unit tests

    @classmethod
    def setUpClass(cls):
        test_financial.AbstractFinancialCase.setUpClass()
        cls.branch_21_case = test_branch_21.Branch21Case('setUp')
        cls.branch_21_case.setUpClass()
        cls.branch_21_case.setUp()
        cls.premium_schedule = cls.branch_21_case.test_create_entries_for_single_premium()

    def setUp(self):
        super(FinancialReportCase, self).setUp()
        self.options = FinancialReportAction.Options()
        self.options.report_date = datetime.date.today()
        self.options.output_dir = settings.TEST_FOLDER
    
    def test_report_generation(self):
        report_action = FinancialReportAction()
        LOGGER.info('store reports in {0.output_dir}'.format(self.options))
        for report_class, report_name in self.options.choices:
            setattr(self.options, report_class.__name__, True)

        for step in report_action.write_files(self.options):
            pass

    def create_sheet(self, report):
        sheet = XlsxSpreadsheet()
        list(report.fill_sheet(sheet, 1, self.options))
        return sheet

    def lookup_row(self, sheet, column, value):
        """
        lookup a specific row in a sheet, return None if the value was not found
        in the column
        """
        row = 1
        while True:
            try:
                sheet_value = sheet.get_value(column, row)
            except:
                break
            if value == sheet_value:
                return row
            row += 1

    def test_report_versions(self):
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)
        #
        # modify a new premium schedule tomorrow
        #
        premium_schedule = self.branch_21_case.test_create_entries_for_single_premium()
        with self.session.begin():
            previous_version = FAPSH.store_version(premium_schedule,
                                                   at=tomorrow)
            # manually change the history, since it's not possible
            # to modify a premium schedule in the future
            previous_version.version_id = 0
        #
        # a report of today and tomorrow should be identical except for the
        # version number
        #
        history_size = self.session.query(FAPSH).count()
        for report_class, report_name in self.options.choices:
            LOGGER.info(u'test report {0}'.format(report_name))
            report = report_class()
            self.options.report_date = today
            today_sheet = self.create_sheet(report)
            self.options.report_date = tomorrow
            tomorrow_sheet = self.create_sheet(report)
            skip_column = None
            for column in string.ascii_uppercase:
                # use offset 0 to be able to check the column
                # headers to decide which columns to skip
                for row in range(0, history_size+1):
                    today_value, tomorrow_value = None, None
                    try:
                        today_value = today_sheet.get_value(column, row)
                    except:
                        pass
                    try:
                        tomorrow_value = tomorrow_sheet.get_value(column, row)
                    except:
                        pass
                    # dont check formulas and references
                    if isinstance(today_value, Expression):
                        continue
                    if today_value in ('Schedule From Date', 'Schedule Version'):
                        skip_column = column
                    if column != skip_column:
                        self.assertEqual(today_value, tomorrow_value)
            
    def test_detailed_valuation(self):
        self.options.product = self.premium_schedule.product_id
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        #
        # use next_week to avoid interference with test_report_versions, which
        # runs tomorrow
        #
        next_week = today + datetime.timedelta(days=7)
        premium_schedule = self.session.query(FAPS).get(self.premium_schedule.id)
        sheet = self.create_sheet(reports.DetailedValuationReport())
        row = self.lookup_row(sheet, 'AC', self.premium_schedule.id)
        self.assertEqual(sheet.get_value('F', row), self.branch_21_case.t4)
        self.assertEqual(sheet.get_value('AI', row), today)
        self.assertEqual(sheet.get_value('AJ', row), 1)
        self.assertEqual(sheet.get_value( 'V', row), 2500)
        booked_value = sheet.get_value('E', row)
        self.assertNotEqual(booked_value, 0)
        #
        # the premium schedule was not there yesterday
        #
        self.options.report_date = yesterday
        sheet = self.create_sheet(reports.DetailedValuationReport())
        row = self.lookup_row(sheet, 'AC', self.premium_schedule.history_of_id)
        self.assertEqual(row, None)
        #
        # modify the premium schedule next_week, the report should be
        # updated
        #
        with self.session.begin():
            previous_version = FAPSH.store_version(premium_schedule,
                                                   at=next_week)
            # manually change the history, since it's not possible
            # to modify a premium schedule in the future
            previous_version.version_id = 0
            previous_version.premium_amount = 2000
           
        self.options.report_date = next_week
        sheet = self.create_sheet(reports.DetailedValuationReport())
        row = self.lookup_row(sheet, 'AC', self.premium_schedule.history_of_id)
        self.assertTrue(row)
        self.assertEqual(sheet.get_value('AJ', row), 1)
        self.assertEqual(sheet.get_value( 'V', row), 2500)
        self.assertEqual(sheet.get_value('E', row), booked_value)
        #
        # the report of today should show the history
        #
        self.options.report_date = today
        sheet = self.create_sheet(reports.DetailedValuationReport())
        row = self.lookup_row(sheet, 'AC', self.premium_schedule.history_of_id)
        self.assertTrue(row)
        self.assertEqual(sheet.get_value('F', row), self.branch_21_case.t4)
        self.assertEqual(sheet.get_value('AI', row), today)
        self.assertEqual(sheet.get_value('AJ', row), 0)
        self.assertEqual(sheet.get_value( 'V', row), 2000)
        self.assertEqual(sheet.get_value('E', row), booked_value)
        #
        # it will be there till the end of times
        #
        self.options.report_date = end_of_times()
        sheet = self.create_sheet(reports.DetailedValuationReport())
        row = self.lookup_row(sheet, 'AC', self.premium_schedule.history_of_id)
        self.assertTrue(row)
        self.assertEqual(sheet.get_value('AJ', row), 1)
        self.assertEqual(sheet.get_value( 'V', row), 2500)
        self.assertEqual(sheet.get_value('E', row), booked_value)
        #
        # but it won't be there after the end of times
        #
        self.options.report_date = end_of_times() + datetime.timedelta(days=1)
        sheet = self.create_sheet(reports.DetailedValuationReport())
        row = self.lookup_row(sheet, 'AC', self.premium_schedule.history_of_id)
        self.assertEqual(row, None)