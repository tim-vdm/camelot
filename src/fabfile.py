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
from fabric import (context_managers,
                    api,
                    contrib)

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger('v-finance-web-service.fabric')
sdk_path = '/opt/python-sdk/11-11'


def install_dependencies():
    with context_managers.settings(host_string=env.HOST_NAME,
                                   user=env.HOST_USER,
                                   key_filename='../conf/{0}.pem'.format(env.CONFIGURATION)):
        api.sudo('yum -y update')
        api.sudo('mkdir -p /opt/python-sdk')
        api.sudo('chmod a+rwx /opt/python-sdk')
        api.sudo('yum -y install xorg-x11-xauth xorg-x11-server-utils xclock xorg-x11-server-Xvfb libXext liberation*')
        if not contrib.files.exists('python-sdk-linux2-2012-9-14-11-11.zip'):
            api.sudo('wget http://cloudlaunch.s3.amazonaws.com/cloudlaunch/images/python-sdk-linux2-2012-9-14-11-11.zip')
        if not contrib.files.exists(sdk_path):
            api.sudo('unzip python-sdk-linux2-2012-9-14-11-11.zip -d {sdk_path}'.format(sdk_path=sdk_path))
        api.sudo('yum install nginx')
        # set init script
        api.sudo('chmod +x /etc/init.d/nginx')
        api.sudo('chkconfig --add nginx')
        api.sudo('chkconfig nginx on')
        # copy conf file
        api.put('../conf/nginx.conf', '/etc/nginx/nginx.conf', use_sudo=True)
        # copy cert and key
        api.sudo('mkdir -p /opt/ssl')
        api.sudo('chmod a+rwx /opt/ssl')
        try:
            api.put('../conf/patronale_ssl.crt', '/opt/ssl/patronale_ssl.crt', use_sudo=True)
            api.put('../conf/patronale_ssl.key', '/opt/ssl/patronale_ssl.key', use_sudo=True)
        except ValueError as ve:
            print('*** You must generate the key and crt files. Please see ../conf/README. ***')
            raise ve
        api.sudo('service nginx start')
        api.sudo('service nginx reload')
        # TODO
        #   - application server (gunicorn)


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


def tail_nginx_log():
    with context_managers.settings(host_string=env.HOST_NAME,
                                   user=env.HOST_USER,
                                   key_filename='../conf/{0}.pem'.format(env.CONFIGURATION)):
        api.sudo('tail -f -n200 /var/log/nginx/error.log')


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
