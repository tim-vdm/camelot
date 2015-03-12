import datetime
import os
import pprint

from decorator import decorator
from flask import current_app
from flask import json
from flask import jsonify
from flask import request

import flask.wrappers

import werkzeug.exceptions

from vfinance_ws.ws.exceptions import BadContentType


def log_to_file(function):
    def wrapper(function, *args, **kwargs):
        dump = {
            'request': pprint.pformat(request.__dict__),
            'data': request.data,
            'response': None,
            'exception': None
        }

        timestamp = datetime.datetime.now()
        fname = '{}-{}.json'.format(timestamp, function.func_name)
        logdir = os.path.join(current_app.config['PATH_DIR_LOG'], 'json-requests')

        logfile = os.path.join(logdir, fname)

        with open(logfile, 'w') as outfile:
            try:
                result = function(*args, **kwargs)
                if isinstance(result, flask.wrappers.Response):
                    dump['response'] = result.data
                elif isinstance(result, tuple):
                    dump['response'] = result[0].data
                else:
                    dump['response'] = result
                return result
            except werkzeug.exceptions.BadRequest, ex:
                dump['exception'] = ex.message
                raise
            except BadContentType, ex:
                dump['exception'] = ex.to_dict()
                raise
            finally:
                outfile.write(json.dumps(dump))

    return decorator(wrapper, function)


def to_json(function):
    def wrapper(function, *args, **kwargs):
        result = function(*args, **kwargs)
        return jsonify(result)
    return decorator(wrapper, function)


def check_minimal_requirements(function):
    def wrapper(function, *args, **kwargs):
        if not request.content_type:
            raise BadContentType('Content-Type is not setted')

        if 'application/json' not in request.content_type:
            raise BadContentType("Content-Type is not 'application/json'")

        try:
            request.get_json()
        except werkzeug.exceptions.BadRequest:
            raise BadContentType("Invalid JSON message")

        return function(*args, **kwargs)
    return decorator(wrapper, function)
