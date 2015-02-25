#
# Fabric file for deploying and updating the webservices server(s)
#
# Use the appropriate (test or production) configuration when
# using this script.  To get an overview of all commands, run :
#
# fab --config=../conf/test.conf -l
#
import os
import logging

from fabric.state import env
from fabric import context_managers, api

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger('v-finance-web-service.fabric')


def install_dependencies():
    raise NotImplementedError()


def install_v_finance_web_service():
    raise NotImplementedError()


def restart_service():
    raise NotImplementedError()


def start_service():
    raise NotImplementedError()


def stop_service():
    raise NotImplementedError()


def get_log_file(filename=''):
    raise NotImplementedError()


def run_tests(tests='', with_debugger=None):
    if with_debugger is not None:
        os.environ['DEBUGGER'] = with_debugger
    api.local("python -m nose.core -v -s -x vfinance_ws/{}".format(tests))


def run_tests_with_coverage(tests=''):
    api.local("rm -rf cover")
    api.local("export MALLOC_CHECK_=0 && python -m nose.core --ignore-files=.*.pyc --with-coverage --cover-html --cover-html-dir=cover --cover-package=vfinance_ws -v -s --with-xunit vfinance_ws/{}".format(tests))


def connect():
    """SSH to the instance"""
    with context_managers.settings(host_string=env.HOST_NAME,
                                   user=env.HOST_USER,
                                   key_filename='../conf/{0}.pem'.format(env.CONFIGURATION)):
        api.open_shell()
