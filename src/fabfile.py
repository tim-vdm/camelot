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
# Although Tornado might do the trick https://github.com/tornadoweb/tornado/wiki/Threading-and-concurrency
# <<<<<< IMPORTANT

import os
import logging
import urllib2
import json
import datetime
import dateutil.relativedelta
from base64 import b64encode


import requests

from fabric.state import env
from fabric import (context_managers,
                    api,
                    contrib)

from cloudlaunch2.record import CloudRecord

API_VERSION = '1.1'

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


def build():
    api.local('python setup.py bdist_cloud {0.CONFIGURATION}'.format(env))


def build_upload():
    run_tests()
    api.local('python setup.py bdist_cloud upload_cloud {0.CONFIGURATION}'.format(env))
    print 'NOTE ========================================================'
    print 'Don\'t forget: fab -c ../conf/{0.CONFIGURATION}.conf restart_service'.format(env)
    print '============================================================='


def run_local():
    with context_managers.lcd('dist/cloud'), context_managers.shell_env(LOGHOME='/tmp/log-vfws.txt'), context_managers.shell_env(DB_PATH='/tmp/test.db'):
        api.local('python -m cloudlaunch.main'
                  ' --cld-file=v-finance-web-service-{0.CONFIGURATION}.cld'
                  ' --cld-name=V-Finance-WS'
                  ' --cld-branch={0.CONFIGURATION}'
                  ' 8080'.format(env))


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


def install_v_finance_web_service():
    build_dir = os.path.join('dist', 'cloud')
    cloudfile = 'v-finance-web-service-{0.IMAGE_KEY}.cld'.format(env)
    with _get_sdk_context():
        api.sudo('mkdir -p {0}'.format(install_path))
        api.sudo('chmod a+rwx {0}'.format(install_path))
        if not contrib.files.exists(os.path.join(install_path, 'packages_{0.CONFIGURATION}.db'.format(env)), use_sudo=True):
            # upload database !!! ONLY IF NOT PRESENT YET
            # be careful, because contract numbers are written back to this file
            api.put('../conf/packages_{0.CONFIGURATION}.db'.format(env), install_path, use_sudo=True)
        # upload nginx conf
        api.put('../conf/nginx_{0.CONFIGURATION}.conf'.format(env), '/etc/nginx/conf.d/', use_sudo=True)
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
        contrib.files.upload_template('v-finance-web-service-{0.IMAGE_KEY}.conf'.format(env),
                                      os.path.join('/', 'etc', 'init'),
                                      use_jinja=True,
                                      template_dir=os.path.join('..', 'conf'),
                                      use_sudo=True,
                                      context=dict(cloudfile=cloudfile,
                                                   sdk_path=sdk_path,
                                                   install_path=install_path))
        # TODO run as user, not root
        # api.sudo('chmod +x /etc/init/v-finance-web-service-{0.IMAGE_KEY}.conf'.format(env))
        # api.sudo('chown ec2-user:ec2-user /etc/init/v-finance-web-service-{0.IMAGE_KEY}.conf'.format(env))
        # stop/start
        try:
            api.sudo('stop v-finance-web-service-{0.CONFIGURATION}'.format(env))
        except:
            pass
        api.sudo('start v-finance-web-service-{0.CONFIGURATION}'.format(env))
        api.sudo('service nginx reload')


def restart_service():
    with _get_sdk_context():
        api.sudo('restart v-finance-web-service-{0.CONFIGURATION}'.format(env))


def start_service():
    with _get_sdk_context():
        api.sudo('start v-finance-web-service-{0.CONFIGURATION}'.format(env))


def stop_service():
    with _get_sdk_context():
        api.sudo('stop v-finance-web-service-{0.CONFIGURATION}'.format(env))


def get_log_file(filename=''):
    with _get_sdk_context():
        api.get(os.path.join('/tmp', 'log', env.CONFIGURATION, filename), 'logs')


def tail_nginx_log():
    with context_managers.settings(host_string=env.HOST_NAME,
                                   user=env.HOST_USER,
                                   key_filename='../conf/{0}.pem'.format(env.CONFIGURATION)):
        api.sudo('tail -f -n200 /var/log/nginx/error_{0}.log'.format(env.CONFIGURATION))


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

def get_all_jsons():
    with context_managers.settings(host_string=env.HOST_NAME,
                                   user=env.HOST_USER,
                                   key_filename='../conf/{0}.pem'.format(env.CONFIGURATION)):
        for f in api.run('ls {}'.format(os.path.join('/tmp', 'log', env.CONFIGURATION, 'create_agreement_code'))).split():
            api.get(os.path.join('/tmp', 'log', env.CONFIGURATION, 'create_agreement_code', f), '/tmp/generated_jsons/%(path)s')

def get_db_files():
    with context_managers.settings(host_string=env.HOST_NAME,
                                   user=env.HOST_USER,
                                   key_filename='../conf/{0}.pem'.format(env.CONFIGURATION)):
        for f in api.run('ls {}'.format(os.path.join('/var', 'v-finance-web-service'))).split():
            if f.endswith('db'):
                api.get(os.path.join('/var', 'v-finance-web-service', f), '/tmp/ws_db/%(path)s')

def put_db_file(filename):
    with context_managers.settings(host_string=env.HOST_NAME,
                                   user=env.HOST_USER,
                                   key_filename='../conf/{0}.pem'.format(env.CONFIGURATION)):
        print('copying {} to {}'.format(filename, os.path.join('/var', 'v-finance-web-service', 'packages_{}.db'.format(env.CONFIGURATION))))
        api.put(local_path=filename, remote_path=os.path.join('/var', 'v-finance-web-service', 'packages_{}.db'.format(env.CONFIGURATION)))

def generate_hash():
    api.local("hg identify -q | tr '+' ' ' > vfinance_ws/hash")

def check_hash():
    h = api.local("hg identify -q | tr '+' ' '", capture=True).strip()
    with context_managers.settings(host_string=env.HOST_NAME,
                                   user=env.HOST_USER,
                                   key_filename='../conf/{0}.pem'.format(env.CONFIGURATION)):
        scheme = 'http' if env.CONFIGURATION == 'local' else 'https'
        h2 = urllib2.urlopen("{}://{}/api/v{}/hash".format(scheme, env.HOST_NAME, API_VERSION)).read().strip()

        print "Local Hash: %r\nRemote Hash: %r\nEqual: %s" % (h, h2, h == h2)

def check_amount_proposal():
    scheme = 'http' if env.CONFIGURATION == 'local' else 'https'
    port = ':8080' if env.CONFIGURATION == 'local' else ''
    ws_url = "%s://%s%s/api/v%s/credit_insurance/calculate_proposal" % (scheme, env.HOST_NAME, port, API_VERSION)

    fpath = os.path.join(os.path.dirname(__file__), 'vfinance_ws', 'demo', 'calculate_proposal.json')

    with open(fpath) as fp:
        agreement = json.load(fp)

    def convert_datetime_to_date(dt):
        return dict(
            year=dt.year,
            month=dt.month,
            day=dt.day
        )

    today = datetime.date.today()

    date = convert_datetime_to_date(today)

    agreement['agreement_date'] = date

    birthdate = today + dateutil.relativedelta.relativedelta(years=-20)

    agreement['insured_party__1__birthdate'] = convert_datetime_to_date(birthdate)

    agreement['from_date'] = date

    headers = {
        'content-type': 'application/json',
        'authorization': 'Basic ' + b64encode("{0}:{1}".format("04f3debc-85b4-4fb3-9de1-88642557764b", "secret"))
    }

    response = requests.post(ws_url, headers=headers, data=json.dumps(agreement), verify=False)

    fpath = os.path.join(os.path.dirname(__file__), 'vfinance_ws', 'demo', 'calculate_proposal_response.json')

    with open(fpath) as fp:
        values = json.load(fp)

    r = response.json()

    print "Local Hash: %r\nRemote Hash: %r\nEqual: %s" % (r, values, r == values)

