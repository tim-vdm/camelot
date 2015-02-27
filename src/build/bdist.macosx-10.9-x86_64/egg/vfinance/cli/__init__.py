import argparse
import sys
import os
import logging
import logging.config

from camelot.core.qt import QtCore
from camelot.core.profile import ProfileStore

from ..utils import str_to_date
from vfinance.application_admin import FinanceApplicationAdmin

LOGGER = logging.getLogger('vfinance.cli')

class CliTool(object):

    def __init__(self):
        self.argument_parser = argparse.ArgumentParser()
        self.argument_parser.add_argument('-L',
                                          '--log-config',
                                          help='The configuration file to use for the logging',
                                          dest='logging_conf')
        self.argument_parser.add_argument('-p',
                                          '--profile',
                                          help='The profile with which to generate the documents',
                                          dest='profile')
        self.argument_parser.add_argument('-s',
                                          '--profile-store',
                                          help='the profile store used for generating the documents',
                                          dest='profile_store')
        self.argument_parser.add_argument('--output-dir',
                                          help='the directory in which to dump the documents',
                                          dest='output_dir',
                                          default=None)
        self.argument_parser.add_argument('--from-book-date',
                                          help='from_book_date for the documents',
                                          type=str_to_date,
                                          dest='from_book_date')
        self.argument_parser.add_argument('--thru-book-date',
                                          help='thru_book_date for the documents',
                                          type=str_to_date,
                                          dest='thru_book_date')
        self.argument_parser.add_argument('--from-document-date',
                                          help='from_document_date for the documents',
                                          type=str_to_date,
                                          dest='from_document_date')
        self.argument_parser.add_argument('--thru-document-date',
                                          help='thru_document_date for the documents',
                                          type=str_to_date,
                                          dest='thru_document_date')

    def parse_arguments(self, namespace=None):
        self.argument_parser.parse_args(namespace=namespace)
        if namespace.logging_conf is not None:
            LOGGER.info(u'reconfigure logging with configuration in {0.logging_conf}'.format(namespace))
            logging.config.fileConfig(namespace.logging_conf, disable_existing_loggers=False)
        self.set_profile(namespace)

    def set_profile(self, namespace):
        # set profile
        profile_name = namespace.profile
        if not profile_name:
            raise Exception('No profile specified')
        profile_store = namespace.profile_store
        application = QtCore.QCoreApplication( [a for a in sys.argv if a] )
        application_admin = FinanceApplicationAdmin()
        application.setOrganizationName( application_admin.get_organization_name() )
        application.setOrganizationDomain( application_admin.get_organization_domain() )
        application.setApplicationName( application_admin.get_name() )
        store = ProfileStore()
        if profile_store is not None:
            filename = os.path.join(os.getcwd(), profile_store)
            store.read_from_file(filename)
        self.profile = store.read_profile(profile_name)
        if self.profile == None:
            raise Exception('%s is an unknown profile'%profile_name)

    def run(self, cli_process, options):
        process = cli_process(profile=self.profile)
        sys.exit(process.run(options))




class EmptyFilter(logging.Filter):

    def filter(self, rec):
        if not hasattr(rec, 'account_id'):
            rec.account_id = '---'
        return True
