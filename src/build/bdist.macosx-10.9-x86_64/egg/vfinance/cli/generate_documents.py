import logging
import multiprocessing


from camelot.view.action_steps import UpdateProgress

from vfinance.process import WorkerProcess
from vfinance.utils import str_to_date

from vfinance.model.financial.constants import notification_types
from vfinance.model.financial.document_action import  FinancialDocumentWizardAction
from vfinance.model.financial.notification.account_document import DocumentGenerationException, DocumentGenerationWarning

from . import CliTool

LOGGER = logging.getLogger('vfinance.cli.generate_documents')

financial_documents = [notification_type for (id,notification_type,related_to,ft) in notification_types]

class GenerateDocumentsProcess(WorkerProcess):

    def run(self, documents_options=None):
        documents_options.output_type = 4 # Save as files
        self.configure()
        document_generator = FinancialDocumentWizardAction()
        exceptions_raised = 0

        for step in document_generator.generate_documents(documents_options):
            if isinstance(step, UpdateProgress) and step._detail is not None:
                LOGGER.info(step._detail)
            if isinstance(step, DocumentGenerationWarning):
                LOGGER.warning(step.message, extra=step.extra)
            if isinstance(step, DocumentGenerationException):
                LOGGER.error(step.message, extra=step.extra, exc_info=step.exc_info)
                exceptions_raised += 1

        LOGGER.info(u'{0} exceptions raised during document generation'.format(exceptions_raised))
        if exceptions_raised:
            return -1

        return 0


class GenerateDocuments(CliTool):

    def __init__(self):
        super(GenerateDocuments, self).__init__()

        parser = self.argument_parser

        parser.add_argument('--package-id',
                            help='id of the package for which you want to generate documents',
                            dest='package',
                            default=None),
        parser.add_argument('--fund-id',
                            help='id of the fund fow which you want to generate documents',
                            dest='fund',
                            default=None),
        parser.add_argument('--exclude-empty',
                            help='if empty account should not be taken into account, this should be set to False',
                            dest='exclude_empty_accounts',
                            default=True,
                            choices=[True, False]),
        parser.add_argument('--origin',
                            help='the origin of the account',
                            dest='origin',
                            default=None),
        parser.add_argument('-n',
                            '--notification-type',
                            help='the document type you want to generate',
                            dest='notification_type',
                            choices=financial_documents,
                            default='account-state'),
        parser.add_argument('--notification-date',
                            help='the notification date',
                            type=str_to_date,
                            dest='notification_date'),
        parser.add_argument('--filename',
                            help='filename format for the documents, follows the same syntax as the gui',
                            dest='filename',
                            type=unicode,
                            default='{account.account_suffix}_{account_subscriber_1}_{package_name}_{account.broker}_{options.notification_type}_{recipient_role.id}'),

def main():

    try:
        document_generator = GenerateDocuments()

        documents_options = FinancialDocumentWizardAction.Options()

        # Set report options
        document_generator.parse_arguments(namespace=documents_options)

        LOGGER.warn('Generating documents for profile {}'.format(documents_options.profile))

        document_generator.run(GenerateDocumentsProcess, documents_options)

    except Exception, e:
        LOGGER.error('Failure generating documents', exc_info=e)
        raise

if __name__=='__main__':
    multiprocessing.freeze_support()
    main()
