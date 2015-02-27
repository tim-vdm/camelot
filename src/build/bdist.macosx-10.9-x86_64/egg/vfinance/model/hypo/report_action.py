'''
Created on Sep 4, 2010

@author: tw55413
'''

import copy
import logging

LOGGER = logging.getLogger('vfinance.model.hypo.report_action')

from camelot.view import forms

from vfinance.model.financial.report_action import FinancialReportAction #, get_product_choices
from camelot.view.controls import delegates

def get_report_choices():
    from vfinance.model.hypo.report import available_reports
    sorted_reports = [(report, unicode(report.name)) for report in available_reports]
    sorted_reports.sort(key=lambda rep:rep[1])
    return sorted_reports

class HypoReportAction( FinancialReportAction ):
    
    verbose_name = 'Mortgage Reports' 
    
    class Options(FinancialReportAction.Options):

        def __init__(self):
            super(HypoReportAction.Options, self).__init__()
            self.choices = get_report_choices()
            for r, report_name in self.choices:
                self.__setattr__(r.__name__, None)

        class Admin( FinancialReportAction.Options.Admin ):
            form_display = forms.Form([], columns=2)
            field_attributes = copy.deepcopy(FinancialReportAction.Options.Admin.field_attributes)

            for r, report_name in get_report_choices():
                form_display.append(r.__name__)
                field_attributes[r.__name__] = {'name':report_name,
                                                'delegate':delegates.BoolDelegate,
                                                'editable':True}

            form_display.extend(['output_dir',
                                 'from_document_date',
                                 'thru_document_date',
                                 'from_book_date',
                                 'thru_book_date',
                                 ])
