from vfinance.model.financial.report_action import FinancialReportAction

class ReportGenerator(object):

    def __init__(self, options):
        self.options = options

    def run(self):
        FinancialReportAction().write_file(self.options, '~/tmp/test.xlsx')



