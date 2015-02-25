#!/usr/bin/env python
from __future__ import absolute_import
import sys

sys.path.insert(0, '.')

from flask import Flask
from flask import request
from flask import abort
from flask import jsonify
import pprint


def bad_request(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

def not_implemented(error):
    response = jsonify({'message': 'Web service not implemented'})
    response.status_code = 501
    return response

def create_app():
    app = Flask(__name__)

    from ws import ws_v01
    from ws import ws_test
    app.register_blueprint(ws_test.bp, url_prefix='/api/test')
    app.register_blueprint(ws_v01.bp, url_prefix='/api/v0.1')

    from ws.exceptions import BadContentType
    app.register_error_handler(BadContentType, bad_request)
    app.register_error_handler(501, not_implemented)

    return app

if __name__ == '__main__':
    app = create_app()

    from werkzeug.contrib.fixers import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app)

    app.debug = True
    app.run(port=19021)
