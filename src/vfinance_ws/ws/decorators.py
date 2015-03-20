import datetime
import os
import pprint
import functools

import voluptuous
from decorator import decorator

from flask import current_app
from flask import json
from flask import jsonify
from flask import request

import flask.wrappers

import werkzeug.exceptions

import camelot.core.exception
import camelot.core.utils

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
        logdir = os.path.join(
            current_app.config['PATH_DIR_LOG'],
            'json-requests'
        )

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


def ws_jsonify(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        try:
            result = function(*args, **kwargs)

            if result is None:
                result = {}

            return jsonify(result)
        except voluptuous.MultipleInvalid as ex:
            errors = {}
            for error in ex.errors:
                if isinstance(error, voluptuous.RequiredFieldInvalid):
                    errors[error.path[0].schema] = {
                        u'message': 'Required',
                    }
                else:
                    path_str = '/'.join(error.path)
                    errors[path_str] = {
                        u'message': error.error_message
                    }
            return jsonify(errors), 400
        except BadContentType, ex:
            raise
        except Exception as ex:
            msg = ex.message
            if isinstance(ex, camelot.core.exception.UserException):
                if isinstance(ex.message, camelot.core.utils.ugettext_lazy):
                    msg = ex.message._string_to_translate
            return jsonify({'message': msg}), 400

    return wrapper


def validation_json(validator=None):
    def decorator(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            if not request.content_type:
                raise BadContentType('Content-Type is not setted')

            if 'application/json' not in request.content_type:
                raise BadContentType("Content-Type is not 'application/json'")

            if validator is None:
                return function(*args, **kwargs)
            else:
                try:
                    document = validator(request.get_json())
                    return function(document, *args, **kwargs)
                except werkzeug.exceptions.BadRequest:
                    raise BadContentType('Invalid JSON message')

        return wrapper
    return decorator
