import os
from fabric import api

def run_tests(tests='',with_debugger=None):
    if with_debugger is not None:
        os.environ['DEBUGGER'] = with_debugger
    api.local("python -m nose.core -v -s -x vfinance_ws/{}".format(tests))

def run_tests_with_coverage(tests=''):
    api.local("rm -rf cover")
    api.local("export MALLOC_CHECK_=0 && python -m nose.core --ignore-files=.*.pyc --with-coverage --cover-html --cover-html-dir=cover --cover-package=vfinance_ws -v -s --with-xunit vfinance_ws/{}".format(tests))
