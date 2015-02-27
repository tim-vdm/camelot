import datetime

import os
import unittest

from camelot.test.action import MockModelContext
from camelot.view import action_steps

from vfinance.connector.gov_be import ExportPremiumTaxation, taxation_detail

from .. import app_admin
from ..test_financial import test_data_folder

xsd_location = os.path.join( os.path.dirname(__file__),
                             '..', '..', 'connector', 'gov_be' )

class GovBeCase(unittest.TestCase):
    
    def validate_xml( self, xml_filename, xsd_filename ):
        from lxml import etree
        schema_tree = etree.parse(open(os.path.join(xsd_location, 
                                                    xsd_filename)))
        schema = etree.XMLSchema(schema_tree)
        document = etree.parse(xml_filename)
        schema.assertValid(document)
        
    def test_long_term_savings(self):
        #
        # validate the example xml
        #
        self.validate_xml( os.path.join( xsd_location, 'voorbeeldpremietaks.xml' ),
                           'DeclarationLongTermSavings-1.6.xsd' )
        #
        # validate the generated xml
        #
        D=float
        detail = taxation_detail(full_account_number='123', 
                                 from_date=datetime.date.today(), 
                                 premium_amount=D('400.00'), 
                                 taxation_amount=D('4.40'), 
                                 payment_date=datetime.date.today(),
                                 taxation_percentage='1.1')
        ExportPremiumTaxation.create_long_term_savings_declarartion('lts.xml', 2012, [detail])
        self.validate_xml('lts.xml', 'DeclarationLongTermSavings-1.6.xsd' )
    
    def test_xslx_import(self):
        export_wizard = ExportPremiumTaxation()
        model_context = MockModelContext()
        model_context.admin = app_admin
        model_run_iterator = export_wizard.model_run(model_context)
        for step in model_run_iterator:
            if isinstance(step, action_steps.SelectFile):
                model_run_iterator.send([os.path.join(test_data_folder,
                                                      'long_term_savings.xlsx')])
            if isinstance(step, action_steps.SaveFile):
                model_run_iterator.send('long_term_savings.xml')
