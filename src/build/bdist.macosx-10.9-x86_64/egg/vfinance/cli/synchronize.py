import datetime
import logging
import multiprocessing
import os
import sys

from camelot.core.qt import QtCore
from camelot.core.profile import ProfileStore

from vfinance.application_admin import FinanceApplicationAdmin
from vfinance.process import WorkerProcess
from vfinance.utils import str_to_date
from vfinance.model.financial.synchronize import SynchronizerOptions
from vfinance import logging_format
from . import CliTool

logging.basicConfig( level=logging.INFO )
LOGGER = logging.getLogger('vfinance.synchronize')

class SynchronizeProcess(WorkerProcess):

    def run(self, date=None, run_forward_only=False, min_schedule=None, max_schedule=None, read_all=False):
        self.configure()
        datestamp = None
        try:
            if date is not None:
                datestamp = datetime.datetime.combine(date, datetime.datetime.min.time())
            else:
                datestamp = datetime.datetime.now()
            timestamp = '%s_%03d' % (datestamp.strftime('%Y_%m_%d_%H_%M_%S'), datestamp.microsecond / 1000)
            log_path = os.path.join(self.profile.media_location,
                                    'synchronize',
                                    '%d' % datestamp.year,
                                    '%02d' % datestamp.month,
                                    '%02d' % datestamp.day)
            LOGGER.info('log path is %s' % log_path)
            if not os.path.exists( log_path ):
                LOGGER.info('path %s does not exist, creating' % log_path)
                os.makedirs( log_path )
            log_file = os.path.join( log_path, 'synchronize_log_%s.txt' % timestamp)
            handler = logging.FileHandler( log_file )
            formatter = logging.Formatter( logging_format )
            handler.setFormatter( formatter )
            handler.setLevel( logging.INFO )
            logging.root.addHandler( handler )
        except Exception, e:
            LOGGER.error('cannot write logs to media location', exc_info=e)

        from vfinance.model.financial.synchronize import FinancialSynchronizer
        s = FinancialSynchronizer(run_date=date, min_schedule=min_schedule, max_schedule=max_schedule, read_all=read_all)
        if run_forward_only:
            list(s.all(options=SynchronizerOptions(['run_forward'])))
        else:
            list(s.all())


class Synchronizer(CliTool):

    def __init__(self):
        super(Synchronizer, self).__init__()

        parser = self.argument_parser

        parser.add_argument('--only-run-forward',
                            help='Only execute the run forward step of the synchronization',
                            dest='only_run_forward',
                            default=False,
                            action='store_true')
        parser.add_argument('-d',
                            '--thru-date',
                            type=str_to_date,
                            help='The date the synchronizer thinks it is run',
                            dest='date')
        parser.add_argument('-m',
                            '--min-schedule',
                            help='Only run forward premium schedules with a id >=',
                            dest='min_schedule'),
        parser.add_argument('-M',
                            '--max-schedule',
                            help='Only run forward premium schedules with a id <=',
                            dest='max_schedule'),
        parser.add_argument('-A',
                            '--read-all-entries',
                            help='Read all entries no matter which day of the week it is',
                            default=False,
                            dest='read_all',
                            action='store_true')


def main():
    try:
        synchronizer = Synchronizer()

        options = SynchronizerOptions()

        # Set synchro options
        synchronizer.parse_arguments(options)

        profile_name = options.profile or options.server_profile
        if not profile_name:
            raise Exception('No profile specified')
        run_forward = options.only_run_forward
        profile_store = options.profile_store
        if options.date:
            date = options.date
        else:
            date = None
        LOGGER.warn( 'Synchronize %s'%profile_name )
        application = QtCore.QCoreApplication( [a for a in sys.argv if a] )
        application_admin = FinanceApplicationAdmin()
        application.setOrganizationName( application_admin.get_organization_name() )
        application.setOrganizationDomain( application_admin.get_organization_domain() )
        application.setApplicationName( application_admin.get_name() )
        store = ProfileStore()
        if profile_store is not None:
            filename = os.path.join(os.getcwd(), profile_store)
            store.read_from_file(filename)
        profile = store.read_profile(profile_name)
        if profile == None:
            raise Exception('%s is an unknown profile'%profile_name)
        synchronize = SynchronizeProcess(profile=profile)
        # use run instead of start because we don't want to create an actual new
        # process
        synchronize.run(date=date, 
                        run_forward_only=run_forward,
                        min_schedule=options.min_schedule,
                        max_schedule=options.max_schedule,
                        read_all=options.read_all)
    except Exception, e:
        LOGGER.error('Failure starting synchronization', exc_info=e)
        raise

if __name__=='__main__':
    multiprocessing.freeze_support()
    main()
