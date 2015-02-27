import StringIO

from camelot.core.files.storage import Storage

from vfinance.connector.aws import AwsQueue, QueueCommand
from vfinance.connector.import_wizard import ImportAction, QueueImportFormat
from vfinance.model.financial import agreement as financial_agreement
from vfinance.test.test_financial import AbstractFinancialCase
from vfinance.test import test_credit_insurance

class AwsConnectorCase( AbstractFinancialCase ):

    @classmethod
    def setUpClass(cls):
        AbstractFinancialCase.setUpClass()
        cls.credit_insurance_case = test_credit_insurance.CreditInsuranceCase('setUp')
        cls.credit_insurance_case.setUpClass()

    def setUp( self ):
        super( AwsConnectorCase, self ).setUp()
        self.credit_insurance_case.setUp()
        self.queue = AwsQueue( mock = True )
        self.queue.clear()
        self.storage = Storage()
        
    def test_write_count_read( self ):
        count = self.queue.count_messages()
        self.queue.write_message( QueueCommand( 'test', [1] ) )
        self.queue.write_message( QueueCommand( 'test', [2] ) )
        self.queue.write_message( QueueCommand( 'test', [3] ) )
        self.assertEqual( self.queue.count_messages(), count + 3 )
        with self.queue.read_message():
            pass
        self.assertEqual( self.queue.count_messages(), count + 2 )
        
    def test_read_with_exception( self ):
        #
        # when an exception occurs during the processing of the
        # message read, the message should stay in the queue
        #
        self.queue.write_message( QueueCommand( 'test', [1] ) )
        count = self.queue.count_messages()
        with self.assertRaises( Exception ):
            with self.queue.read_message():
                raise Exception()
        self.assertEqual( self.queue.count_messages(), count )
        
    def test_write_read_agreement( self ):
        #
        # Create a financial agreement
        #
        export_action = financial_agreement.FinancialAgreementJsonExport()
        self.credit_insurance_case.create_product_definition( 'Queue', 0 )
        self.credit_insurance_case.create_person()
        agreement = self.credit_insurance_case.create_agreement()
        stream = StringIO.StringIO()
        stream.write( 'Agreement Document' )
        stream.seek( 0 )        
        agreement_document = self.storage.checkin_stream( 'agreement', '.txt', stream )        
        agreement.document = agreement_document
        #
        # Write the agreement to the queue
        #
        json = export_action.entity_to_dict( agreement )
        self.queue.write_message( QueueCommand( 'import_agreement', json ) )
        #
        # Read the agreement from the queue
        #
        import_action = ImportAction()
        count = financial_agreement.FinancialAgreement.query.count()
        for i, step in enumerate( import_action.model_run( None ) ):
            if i == 0:
                options = step.get_object()
                options.format = QueueImportFormat()
                options.mock = self.queue.mock
        self.assertEqual( financial_agreement.FinancialAgreement.query.count(), count + 1 )