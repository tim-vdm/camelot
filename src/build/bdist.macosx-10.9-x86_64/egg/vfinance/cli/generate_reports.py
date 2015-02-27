import logging
import multiprocessing


from camelot.view.action_steps import UpdateProgress

from vfinance.process import WorkerProcess
from vfinance.model.hypo.report_action import FinancialReportAction
from vfinance.model.financial.report import available_reports as available_reports_financial
from vfinance.model.hypo.report import available_reports as available_reports_hypo
from vfinance.utils import str_to_date

from . import CliTool

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger('vfinance.generatereports')

available_reports = available_reports_financial + available_reports_hypo

class GenerateReportsProcess(WorkerProcess):

    def run(self, report_options=None):
        self.configure()
        report = ''
        percentage = 0
        last_percentage = 1
        for step in FinancialReportAction().write_files(report_options):
            if isinstance(step, UpdateProgress) and step._detail is not None and step._detail != report:
                report = step._detail
            if isinstance(step, UpdateProgress) and step._maximum is not None:
                percentage = int(step._value * 100.0 / step._maximum)
                if percentage % 5 == 0 and last_percentage != percentage:
                    last_percentage = percentage
                    LOGGER.info('{}: {}%'.format(report, percentage))


class GenerateReports(CliTool):

    def __init__(self):
        super(GenerateReports, self).__init__()

        parser = self.argument_parser

        parser.add_argument('--report-date',
                            help='report_date for the reports',
                            type=str_to_date,
                            dest='report_date')
        parser.add_argument('--product',
                            help='product-parameter for the reports',
                            dest='product'),
        parser.add_argument('--from-account-suffix',
                            help='from_account_suffix-parameter for the reports',
                            dest='from_account_suffix')
        parser.add_argument('--thru-account-suffix',
                            help='thru_account_suffix-parameter for the reports',
                            dest='thru_account_suffix')
        parser.add_argument('-r',
                            '--reports',
                            help='reports to generate',
                            dest='reports'),


def main():

    try:
        report_generator = GenerateReports()

        report_options = FinancialReportAction.Options()

        # Set report options
        report_generator.parse_arguments(report_options)

        if report_options.reports is not None:
            for report in report_options.reports.split(', '):
                report_options.__setattr__(report, True)
        else:
            for report in available_reports_financial + available_reports_hypo:
                report_options.__setattr__(report.__name__, True)
            report_options.choices = [(report, str(report.name)) for report in available_reports]

        LOGGER.warn('Generating reports for profile {}'.format(report_options.profile))

        report_generator.run(GenerateReportsProcess, report_options)

    except Exception, e:
        LOGGER.error('Failure generating reports', exc_info=e)
        raise

if __name__=='__main__':
    multiprocessing.freeze_support()
    main()
