#!/usr/bin/env python

#
# Build and test :
#
# python setup.py bdist_cloud test
# cd dist/cloud
# python -m cloudlaunch.main --cld-file=v-finance-web-service-test.cld 8080
# browse to http://127.0.0.1:8080
# log files are written to /tmp/v-finance-web-service
#
# Build and deploy to production (identical for test):
#
# python setup.py bdist_cloud upload_cloud production
# fab -c ../conf/test.conf restart_service
#
# Certificate generating info :
#
# http://www.thegeekstuff.com/2009/07/linux-apache-mod-ssl-generate-key-csr-crt-file/
#
import os
import logging
import datetime
from setuptools import setup, find_packages
import sys

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s %(levelname)-8s %(name)-35s] %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S')
LOGGER = logging.getLogger('v-finance-web-service setup')

cloud_certificate = """eydwdWJsaWNfYWNjZXNzX2tleSc6IHUnQUtJQUk1NFRZNTIzU0ZTUkpKRFEnLCAncHVibG
ljX3NlY3JldF9rZXknOiB1J1RwSWlLa3hJaHIySVBKcE51MGJZeHV3M0tKcWR1RlBYNGFn
b2lsV3onLCAncHJpdmF0ZV9hY2Nlc3Nfa2V5JzogdSdBS0lBSjNNWkpLN0xCUlpMR0g0QS
csICduYW1lJzogJ1YtRmluYW5jZS1XUycsICdhdXRob3InOiAnVm9ydGV4IEZpbmFuY2lh
bHMnLCAnbG9nZ2luZyc6ICdjbG91ZGxhdW5jaC1Wb3J0ZXhfRmluYW5jaWFscy1WLUZpbm
FuY2UtV1MtbG9nZ2luZycsICdidWNrZXQnOiAnY2xvdWRsYXVuY2gnLCAncHJpdmF0ZV9z
ZWNyZXRfa2V5JzogdScrODJoZmdPN2IxYVNVZ21VTE1lRVY4Vjc5bGxFMmtuNC9ZY1psQU
ovJ30="""

from cloudlaunch2.command.bdist_cloud import bdist_cloud
from cloudlaunch2.command.upload_cloud import upload_cloud
from cloudlaunch2.command.monitor_cloud import monitor_cloud

config = sys.argv.pop()

configuration = dict()
for line in open('../conf/{0}.conf'.format(config)).readlines():
    k, v = line.strip('\n').strip('\r').split('=')
    configuration[k.strip()] = v.strip()

# generate recursive data paths for glob, because glob does not support **
data_paths = []
extensions = ['*.doc',
              '*.png',
              '*.gif',
              '*.jpg',
              '*.qm',
              '*.po',
              '*.qss',
              '*.html',
              '*.css',
              '*.csv',
              '*.xml',
              '*.rels',
              '*.bin',
              '.rels',
              '*.dat']
for extension in extensions:
    for i in range(7):
        for submodule in ['art',
                          'templates',
                          'static'
                          'templates_',
                          'static_']:
            path_parts = ['*'] * i + [extension]
            data_paths.append(os.path.join(submodule, *path_parts))
        path_parts = ['*'] * i + [extension]
        data_paths.append(os.path.join(*path_parts))

setup(
    name='v-finance-web-service',
    version='0.1',
    description='V-Finance Web Service',
    author='Vortex Financials',
    author_email='info@vortex-financials.be',
    url='http://www.vortex-financials.be/vfinance.html',
    include_package_data=True,
    zip_safe=False,
    packages=find_packages(),
    # setup_requires=['hgtools'],
    py_modules=['decorator',
                'itsdangerous',
                'six',
                'polib',
                'voluptuous',
                'flask_httpauth'],
    entry_points={'console_scripts': ['server = vfinance_ws.tornado_run:main'],
                  # "egg_info.writers": ["foo_bar.txt = setuptools.command.egg_info:write_arg"]
                  },
    package_data={'camelot': data_paths,
                  'vfinance': data_paths,
                  'vfinance_ws': data_paths,
                  'stdnum': data_paths,
                  'integration.spreadsheet': data_paths,
                  'integration.venice': ['*.inc']},
    cmdclass={
        'bdist_cloud': bdist_cloud,
        'upload_cloud': upload_cloud,
        'monitor_cloud': monitor_cloud,
    },
    options={'egg_info': {'tag_build': '-{}'.format(config)},
             'bdist_cloud': {'certificate': cloud_certificate,
                             'branch': config,
                             'update_before_launch': True,
                             'default_entry_point': ('console_scripts',
                                                     'server'),
                             'changes': [],
                             'timestamp': datetime.datetime.now(),
                             'configuration': configuration},
             'upload_cloud': {'certificate': cloud_certificate},
             'monitor_cloud': {'certificate': cloud_certificate}})
