import contextlib
import datetime
import decimal
import os

from camelot.core.exception import UserException
from camelot.view import action_steps

from vfinance.model.bank.direct_debit import direct_debit_detail
from vfinance.connector.sepa.direct_debit_initiation import DirectDebitInitiation
from vfinance.connector.sepa.bank_to_customer_statement import BankToCustomerStatementImport

from ..test_case import SessionCase, test_data_folder

xsd_location = os.path.join( os.path.dirname(__file__),
                             '..', '..', 'connector', 'sepa' )

class KbcSettings(object):
    SEPA_DIRECT_DEBIT_BIC = 'KREDBEBB'
    SEPA_DIRECT_DEBIT_IBAN = 'BE05733017202675'
    SEPA_CREDITOR_IDENTIFIER = 'BE10ZZZ0403288089'

class MultipleBankSettings(object):
    SEPA_DIRECT_DEBIT_BIC_1 = 'KEYTBEBB'
    SEPA_DIRECT_DEBIT_IBAN_1 = 'BE94001618621014'
    SEPA_CREDITOR_IDENTIFIER_1 = 'BE10ZZZ0403288090'

class BelfiusSettings(object):
    VFINANCE_DOSSIER_NAME = 'Eigen Huis'

@contextlib.contextmanager
def temp_settings(s):
    from camelot.core.conf import settings
    settings.insert(0, s)
    yield
    settings.remove(s)

details = [direct_debit_detail(end_to_end_id=5,
                               amount = decimal.Decimal('1022.84'),
                               bic='KREDBEBB',
                               iban='NL91ABNA0417164300',
                               remark_1='Your mortgage',
                               remark_2='This months repayment',
                               mandate_id='27',
                               mandate_signature_date=datetime.date.today()-datetime.timedelta(days=10),
                               mandate_sequence_type='FRST',
                               debtor_name='Debtor 1',
                               collection_date=datetime.date.today()+datetime.timedelta(days=7),
                               original_mandate_id=None,
                               ),
           direct_debit_detail(end_to_end_id=6,
                               amount = decimal.Decimal('300.62'),
                               bic='KREDBEBB',
                               iban='NL91ABNA0417164300',
                               remark_1='Your mortgage',
                               remark_2='This months repayment',
                               mandate_id='27',
                               mandate_signature_date=datetime.date.today()-datetime.timedelta(days=10),
                               mandate_sequence_type='FRST',
                               debtor_name='Debtor 1',
                               collection_date=datetime.date.today()+datetime.timedelta(days=7),
                               original_mandate_id='123456789012',
                               ),
           direct_debit_detail(end_to_end_id=7,
                               amount = decimal.Decimal('365.25'),
                               bic='KREDBEBB',
                               iban='NL91ABNA0417164300',
                               remark_1='Your mortgage',
                               remark_2='This months repayment',
                               mandate_id='28',
                               mandate_signature_date=datetime.date.today()-datetime.timedelta(days=10),
                               mandate_sequence_type='RCUR',
                               debtor_name='Debtor 1',
                               collection_date=datetime.date.today()+datetime.timedelta(days=5),
                               original_mandate_id=None,
                               ),
           ]

invalid_details = [
    direct_debit_detail(end_to_end_id=8,
                        amount = decimal.Decimal('365.25'),
                        bic='KREDBEBB',
                        iban='NL91 ABNA0417164300',
                        remark_1='Your mortgage',
                        remark_2='This months repayment',
                        mandate_id='28',
                        mandate_signature_date=datetime.date.today()-datetime.timedelta(days=10),
                        mandate_sequence_type='RCUR',
                        debtor_name='Debtor 1',
                        collection_date=datetime.date.today()+datetime.timedelta(days=5),
                        original_mandate_id=None,
                        ),
    ]

class DirectDebitCase(SessionCase):

    def validate_xml( self, xml_filename, xsd_filename ):
        from lxml import etree
        schema_tree = etree.parse(open(os.path.join(xsd_location,
                                                    xsd_filename)))
        schema = etree.XMLSchema(schema_tree)
        document = etree.parse(xml_filename)
        schema.assertValid(document)
        
    def string_present(self, xml_filename, string):
        string_present = False
        with open(xml_filename, 'r') as stream:
            for line in stream:
                if string in line:
                    string_present = True
            self.assertTrue(string_present)
        

    def test_create_direct_debit_initiation(self):
        #
        # validate the example xml
        #
        self.validate_xml( os.path.join( xsd_location, 'pain.008.001.02.xml' ),
                           'pain.008.001.02.xsd' )
        ##
        ## validate the generated xml
        ##
        with temp_settings(KbcSettings()):
            with open('ddi-kbc.xml', 'w+') as stream:
                list(DirectDebitInitiation.create_direct_debit_initiation(stream,
                                                                          'direct_debit_batch_1',
                                                                          75,
                                                                          datetime.date.today(),
                                                                          datetime.date.today()+datetime.timedelta(days=7),
                                                                          details))
            self.validate_xml('ddi-kbc.xml', 'pain.008.001.02.xsd')
            self.string_present('ddi-kbc.xml', 'BE05733017202675')
            self.string_present('ddi-kbc.xml', 'KREDBEBB')
            self.string_present('ddi-kbc.xml', 'BE10ZZZ0403288089')


        with temp_settings(MultipleBankSettings()):
            with open('ddi-other.xml', 'w+') as stream:
                list(DirectDebitInitiation.create_direct_debit_initiation(stream,
                                                                          'direct_debit_batch_1',
                                                                          75,
                                                                          datetime.date.today(),
                                                                          datetime.date.today()+datetime.timedelta(days=7),
                                                                          details))
            self.validate_xml('ddi-other.xml', 'pain.008.001.02.xsd')
            self.string_present('ddi-other.xml', 'BE94001618621014')
            self.string_present('ddi-other.xml', 'KEYTBEBB')
            self.string_present('ddi-other.xml', 'BE10ZZZ0403288090')

    def test_user_exception_on_invalid_data(self):
        with temp_settings(KbcSettings()):
            with open('ddi-kbc-invalid.xml', 'w+') as stream:
                with self.assertRaises(UserException):
                    list(DirectDebitInitiation.create_direct_debit_initiation(stream,
                                                                              'direct_debit_batch_1',
                                                                              75,
                                                                              datetime.date.today(),
                                                                              datetime.date.today()+datetime.timedelta(days=7),
                                                                              details+invalid_details))

class BankToCustomerStatementCase(SessionCase):

    def import_xml(self, xml_filenames):
        action = BankToCustomerStatementImport()
        step_iterator = action.model_run(self.app_model_context)
        steps = []
        for step in step_iterator:
            if isinstance(step, action_steps.SelectFile):
                step_iterator.send(xml_filenames)
            steps.append(step)
        return steps

    def test_belfius(self):
    
        belfius_files = [os.path.join(test_data_folder, u'belfius-20140806.xml'),
                         os.path.join(test_data_folder, u'belfius-20140807.xml')]

        steps = self.import_xml(belfius_files)
        self.assertTrue(len(steps) < 5)

        # direct debit results should only be generated if the dossier name matches
        with temp_settings(BelfiusSettings()):
            steps = self.import_xml(belfius_files)
            self.assertTrue(len(steps) > 10)
