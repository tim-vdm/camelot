import os
from fabric import api

def run_tests(tests='',with_debugger=None):
    if with_debugger is not None:
        os.environ['DEBUGGER'] = with_debugger
    api.local("python -m nose.core -v -s -x vfinance_ws/{}".format(tests))
