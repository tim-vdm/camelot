#
# Fabric file for deploying and updating the webservices server(s)
#
# Use the appropriate (test or production) configuration when
# using this script.  To get an overview of all commands, run :
#
# fab --config=../conf/test.conf -l
#

# IMPORTANT >>>>>>
# To win time, initial deployment is on Tornado, and Tornado only.
# Eventually a move to nginx+appserver (gunicorn?) is needed to handle
# multiple requests.
# <<<<<< IMPORTANT

import os
import logging

from fabric.state import env
from fabric import (context_managers,
                    api,
                    contrib)

from cloudlaunch2.record import CloudRecord

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger('v-finance-web-service.fabric')
sdk_path = '/opt/python-sdk/11-11'
install_path = os.path.join('/', 'var', 'v-finance-web-service')


def _get_instance_context():
    return context_managers.settings(host_string=env.HOST_NAME,
                                     user=env.HOST_USER,
                                     key_filename='../conf/{0}.pem'.format(env.CONFIGURATION))


def _get_sdk_context():
    return context_managers.settings(_get_instance_context(),
                                     context_managers.path(os.path.join(sdk_path, 'bin'), behavior='prepend'),
                                     context_managers.prefix('export DISPLAY=localhost:99.0 && export LD_LIBRARY_PATH={0}/lib && export PYTHONHOME={0}'.format(sdk_path)), )


def build_test():
    api.local('python setup.py bdist_cloud test')


def run_test():
    with context_managers.lcd('dist/cloud'):
        api.local('python -m cloudlaunch.main --cld-file=v-finance-web-service-test.cld 8080')


def build_production_upload():
    run_tests()
    api.local('python setup.py bdist_cloud upload_cloud production')
    print 'NOTE ========================================================'
    print 'Don\'t forget: fab -c ../conf/production.conf restart_service'
    print '============================================================='


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
        #
        # nginx (initially, only Tornado is used to server requests.
        #        SSL certs are inside egg for Tornado)
        #
        # api.sudo('yum install nginx')
        # # set init script
        # api.sudo('chmod +x /etc/init.d/nginx')
        # api.sudo('chkconfig --add nginx')
        # api.sudo('chkconfig nginx on')
        # # copy conf file
        # api.put('../conf/nginx.conf', '/etc/nginx/nginx.conf', use_sudo=True)
        # copy cert and key
        # api.sudo('mkdir -p /opt/ssl')
        # api.sudo('chmod a+rwx /opt/ssl')
        # try:
        #     api.put('../conf/patronale_ssl.crt', '/opt/ssl/patronale_ssl.crt', use_sudo=True)
        #     api.put('../conf/patronale_ssl.key', '/opt/ssl/patronale_ssl.key', use_sudo=True)
        # except ValueError as ve:
        #     print('*** You must generate the key and crt files. Please see ../conf/README. ***')
        #     raise ve
        # api.sudo('service nginx start')
        # api.sudo('service nginx reload')


def install_v_finance_web_service():
    build_dir = os.path.join('dist', 'cloud')
    cloudfile = 'v-finance-web-service-{0.IMAGE_KEY}.cld'.format(env)
    with context_managers.settings(host_string=env.HOST_NAME,
                                   user=env.HOST_USER,
                                   key_filename='../conf/{0}.pem'.format(env.CONFIGURATION)):
        api.sudo('mkdir -p {0}'.format(install_path))
        api.sudo('chmod a+rwx {0}'.format(install_path))
        # upload database
        api.put('../conf/packages.db', install_path, use_sudo=True)
        # upload init conf
        contrib.files.upload_template('xvfb.conf',
                                      os.path.join('/', 'etc', 'init'),
                                      use_jinja=True,
                                      template_dir=os.path.join('..', 'conf'),
                                      use_sudo=True)
        try:
            api.sudo('stop xvfb')
        except:
            pass
        api.sudo('start xvfb')
        api.put(os.path.join(build_dir, cloudfile), install_path)
        cloud_records = CloudRecord.read_records_from_file(os.path.join(build_dir, cloudfile))
        for cloud_record in cloud_records:
            for filename, checksum in cloud_record.eggs:
                api.put(os.path.join(build_dir, filename), install_path)
        contrib.files.upload_template('v-finance-web-service.conf',
                                      os.path.join('/', 'etc', 'init'),
                                      use_jinja=True,
                                      template_dir=os.path.join('..', 'conf'),
                                      use_sudo=True,
                                      context=dict(cloudfile=cloudfile,
                                                   sdk_path=sdk_path,
                                                   install_path=install_path))
        try:
            api.sudo('stop v-finance-web-service')
        except:
            pass
        api.sudo('start v-finance-web-service')


def restart_service():
    with _get_sdk_context():
        api.sudo('restart v-finance-web-service')


def start_service():
    with _get_sdk_context():
        api.sudo('start v-finance-web-service')


def stop_service():
    with _get_sdk_context():
        api.sudo('stop v-finance-web-service')


def get_log_file(filename=''):
    with _get_sdk_context():
        api.get(os.path.join('/tmp', filename), 'logs')


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
