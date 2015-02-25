#
# Fabric file for deploying and updating the webservices server(s)
#
# Use the appropriate (test or production) configuration when
# using this script.  To get an overview of all commands, run :
#
# fab --config=../conf/test.conf -l
#
import logging

from fabric.state import env
from fabric import context_managers, api

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger('v-finance-web-service.fabric')


def connect():
    """SSH to the instance"""
    with context_managers.settings(host_string=env.HOST_NAME,
                                   user=env.HOST_USER,
                                   key_filename='../conf/{0}.pem'.format(env.CONFIGURATION)):
        api.open_shell()
