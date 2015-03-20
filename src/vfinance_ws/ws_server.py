#!/usr/bin/env python
import os
from flask import Flask
from flask import jsonify
from werkzeug.contrib.fixers import ProxyFix


def bad_request(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


def not_implemented(error):
    response = jsonify({'message': 'Web service not implemented'})
    response.status_code = 501
    return response


def create_path_dir_log(*args, **kwargs):
    """
    Create the directory for the logs
    """

    from flask import current_app
    path_dir_log = current_app.config['PATH_DIR_LOG']

    directories = [
        (path_dir_log,),
        (path_dir_log, 'json-requests'),
        (path_dir_log, 'calculate_proposal'),
        (path_dir_log, 'create_agreement_code'),
    ]

    current_app.logger.info(
        "Creating the path directory for log: %s",
        path_dir_log
    )

    for directory in directories:
        directory = os.path.join(*directory)
        if not os.path.exists(directory):
            os.makedirs(directory)


def create_app():
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = True

    # FIXME: Use the tempdir module
    path = os.path.join('/', 'tmp', 'vfinance_ws')
    app.config['PATH_DIR_LOG'] = os.environ.get('LOGHOME', path)

    app.before_first_request(create_path_dir_log)

    from vfinance_ws.ws import ws_v01
    from vfinance_ws.ws import ws_test
    app.register_blueprint(ws_test.bp, url_prefix='/api/test')
    app.register_blueprint(ws_v01.bp, url_prefix='/api/v0.1')

    from vfinance_ws.ws.exceptions import BadContentType
    app.register_error_handler(BadContentType, bad_request)
    app.register_error_handler(501, not_implemented)

    return app


if __name__ == '__main__':
    app = create_app()

    app.wsgi_app = ProxyFix(app.wsgi_app)

    app.debug = True
    app.run(port=19021)
