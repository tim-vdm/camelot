'''
Created on Sep 4, 2010

@author: tw55413
'''

import datetime
import logging
import os

from camelot.admin.action import Action
from camelot.admin.object_admin import ObjectAdmin
from camelot.view.art import Icon
from camelot.view import forms
from camelot.view.action_steps import ChangeObject, OpenString, UpdateProgress
from camelot.view.controls import delegates

LOGGER = logging.getLogger('vfinance.model.financial.report')

def get_product_choices(obj):
    from vfinance.model.financial.product import FinancialProduct
    return [(None,u'All')] + [(p.id, p.name) for p in FinancialProduct.query.all()]
        
def get_report_choices():
    from vfinance.model.financial.report import available_reports
    sorted_reports =  [(report, unicode(report.name)) for report in available_reports]
    sorted_reports.sort(key=lambda rep:rep[1])
    return sorted_reports

class FinancialReportAction( Action ):
     
    verbose_name = 'Financial Reports'
    icon = Icon('tango/16x16/mimetypes/x-office-spreadsheet.png')
    offset = 8
        
    class Options(object):
        
        def __init__(self):
            self.from_document_date = datetime.date(2000,1,1)
            self.thru_document_date = datetime.date.today()
            self.from_book_date = datetime.date(2000,1,1)
            self.thru_book_date = datetime.date.today()
            self.report_date = datetime.date.today()
            self.product = None
            self.products = None
            self.from_account_suffix = None
            self.thru_account_suffix = None
            self.output_dir = None
            self.choices = get_report_choices()
            for r, report_name in self.choices:
                self.__setattr__(r.__name__, None)

        class Admin(ObjectAdmin):
            form_display = forms.Form([], columns=2)
            field_attributes = {}

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
                                 'report_date',
                                 'product',
                                 'from_account_suffix',
                                 'thru_account_suffix',
                                 ])

            field_attributes.update({'output_dir':{'delegate':delegates.LocalFileDelegate,
                                                   'directory':True,
                                                   'editable':True},
                                     'from_document_date':{'delegate':delegates.DateDelegate, 
                                                           'nullable':False,
                                                           'editable':True},
                                     'thru_document_date':{'delegate':delegates.DateDelegate, 
                                                           'nullable':False,
                                                           'editable':True},
                                     'from_book_date':{'delegate':delegates.DateDelegate, 
                                                       'nullable':False,
                                                       'editable':True},
                                     'thru_book_date':{'delegate':delegates.DateDelegate, 
                                                       'nullable':False,
                                                       'editable':True},
                                     'report_date':{'delegate':delegates.DateDelegate, 
                                                    'nullable':False,
                                                    'editable':True},
                                     'product':{'choices':get_product_choices,
                                                'delegate':delegates.ComboBoxDelegate,
                                                'editable':True},
                                     'from_account_suffix':{'nullable':True,
                                                            'delegate':delegates.IntegerDelegate,
                                                            'editable':True},
                                     'thru_account_suffix':{'nullable':True,
                                                            'delegate':delegates.IntegerDelegate,
                                                            'editable':True},
                                     })

        
    def model_run( self, model_context ):
        options = self.Options()
        yield ChangeObject(options)
        for step in self.write_files( options ):
            yield step

    def write_files(self, options):
        from integration.spreadsheet.xlsx import XlsxSpreadsheet
        from integration.spreadsheet.base import Cell
        from vfinance.model.bank.entry import Entry

        for report_class, report_name in options.choices:
            if options.__getattribute__(report_class.__name__) == True:
                yield UpdateProgress(detail='Generating {}'.format(report_name))
                # use xlsx, because some reports contain formula
                sheet = XlsxSpreadsheet()
                options.report = report_class
                report = report_class()

                #
                # make sure we have no obsolete data in our report
                #
                Entry.query.session.expire_all()

                #
                # Headers
                #
                sheet.render( Cell( 'A', 1, 'Reporting date' ) )
                sheet.render( Cell( 'A', 2, 'Document date' ) )
                sheet.render( Cell( 'B', 2, 'From' ) )
                sheet.render( Cell( 'B', 3, 'Thru' ) )
                sheet.render( Cell( 'A', 4, 'Book date' ) )
                sheet.render( Cell( 'B', 4, 'From' ) )
                sheet.render( Cell( 'B', 5, 'Thru' ) )
                sheet.render( Cell( 'E', 2, 'Report date' ) )      
                sheet.render( Cell( 'E', 1, unicode( options.report.name ) ) )
                sheet.render( Cell( 'C', 1, datetime.date.today() ) )
                sheet.render( Cell( 'C', 2, options.from_document_date ) )
                sheet.render( Cell( 'C', 3, options.thru_document_date ) )
                sheet.render( Cell( 'C', 4, options.from_book_date ) )
                sheet.render( Cell( 'C', 5, options.thru_book_date ) )
                sheet.render( Cell( 'F', 2, options.report_date ) )

                for step in report.fill_sheet( sheet, self.offset, options ):
                    yield step

                content = sheet.generate_xlsx()

                if options.output_dir is not None:
                    with open(os.path.join(options.output_dir, report.__class__.__name__ + '.xlsx'), 'wb') as f:
                        f.write(content)
                        f.close()
                else:
                    yield OpenString(content, '.xlsx')
