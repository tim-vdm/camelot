#
# Start a Tornade HTTP Server
#
import os
import sys
import logging
import logging.handlers

from PyQt4 import QtGui

from camelot.core.templates import environment, loader
from vfinance.admin.jinja2_filters import filters
from vfinance.model.financial.notification.environment import PackageExtensionLoader

LOGGER = logging.getLogger('v-finance-web-service.tornado_run')

format_str = '[%(asctime)s] [%(levelname)-5s] [%(name)-20s] - %(message)s'
logging.basicConfig(level=logging.INFO, format=format_str)

#
# Configure logging in tmp folder, so everything is gone at reboot
#
logging_path = os.environ['LOGHOME']
if not os.path.exists(logging_path):
    os.makedirs(logging_path)

handler = logging.handlers.TimedRotatingFileHandler(
    os.path.join(logging_path, 'logs-server-{0}.txt'.format(os.getpid())),
    when='midnight',
    backupCount=31
)

handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter(format_str))
logging.root.addHandler(handler)

LOGGER.info('starting application server')

qapplications = []

def main():
    try:
        # import pkg_resources
        # import functools
        from tornado.wsgi import WSGIContainer
        from tornado.httpserver import HTTPServer
        from tornado.ioloop import IOLoop

        from ws_server import create_app
        #from ws import utils

        app = create_app()
        #next_agreement_code = utils.get_next_agreement_code()
        LOGGER.info('app created')#, next agreement code will be: {}'.format(next_agreement_code))

        # resource_filename = functools.partial(pkg_resources.resource_filename, 'vfinance_ws')
        # ssl_options = {
        #     'certfile': resource_filename(os.path.join('data', 'patronale_ssl.crt')),
        #     'keyfile': resource_filename(os.path.join('data', 'patronale_ssl.key'))
        # }
        ssl_options = None
        http_server = HTTPServer(WSGIContainer(app), ssl_options=ssl_options)
        http_server.listen(int(sys.argv[1]))
        # http_server.listen(19021)
        loader.loaders.insert(0, PackageExtensionLoader(
            package_name='vfinance', package_path='art/templates'))
        loader.loaders.insert(0, PackageExtensionLoader(
            package_name='vfinance_ws', package_path='art/templates'))
        environment.autoescape = True
        environment.finalize = lambda x: '' if x is None else x
        environment.add_extension('jinja2.ext.i18n')
        environment.add_extension('jinja2.ext.do')
        environment.filters.update(filters)
        qapplications.append(QtGui.QApplication(([a for a in sys.argv[2:] if a])))
        IOLoop.instance().start()
    except Exception, e:
        LOGGER.fatal('Could not run application', exc_info=e)

if __name__ == '__main__':
    main()
