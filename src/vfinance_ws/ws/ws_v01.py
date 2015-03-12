import functools
import datetime
import os

import werkzeug.exceptions

from flask import Blueprint
from flask import jsonify
from flask import request
from flask import current_app

import camelot.core.exception
import camelot.core.utils

import voluptuous

from vfinance_ws.ws.decorators import log_to_file

from vfinance_ws.ws.validation_message import (
    validation_calculate_proposal,
    validation_create_agreement_code,
    validation_send_agreement,
)
from vfinance_ws.ws.exceptions import BadContentType

from vfinance_ws.api import v01

bp = Blueprint('api_v01', __name__)

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
                except werkzeug.exceptions.BadRequest, ex:
                    raise BadContentType('Invalid JSON message')

        return wrapper
    return decorator


@bp.route('/calculate_proposal', methods=['POST'])
@ws_jsonify
@log_to_file
@validation_json(validation_calculate_proposal)
def calculate_proposal(document):
    """
    :synopsis: Calculate the amount of a proposal
    :reqheader Content-Type: :mimetype:`application/json`
    :resheader Content-Type: :mimetype:`application/json`

    :status 200:
    :status 400:
    :status 501:

    .. literalinclude:: demo/post_calculate_proposal.http
        :language: http

    .. literalinclude:: demo/calculate_proposal.json
        :language: json

    .. literalinclude:: demo/200.http
        :language: http

    .. literalinclude:: demo/calculate_proposal_response.json
        :language: json

    .. literalinclude:: demo/400.http
        :language: http

    .. literalinclude:: demo/bad_request_required.json
        :language: json

    If there is an error in the values of the json document, the server will
    return a message with the path of the variable.

    .. literalinclude:: demo/400.http
        :language: http

    .. literalinclude:: demo/bad_request_error.json
        :language: json

    If there is a extra key in the json document, the server will return
    this kind of message.

    .. literalinclude:: demo/400.http
        :language: http

    .. literalinclude:: demo/bad_request_extra.json
        :language: json

    """
    identifier = document['agent_official_number_fsma']
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = '%s-%s.json' % (identifier, timestamp,)
    fname = os.path.join(current_app.config['PATH_DIR_LOG'], 'calculate_proposal', fname)

    with open(fname, 'w') as outfile:
        result = v01.calculate_proposal(document, logfile=outfile)

    return result


@bp.route('/create_agreement_code', methods=['POST'])
@ws_jsonify
@log_to_file
@validation_json(validation_create_agreement_code)
def create_agreement_code(document):
    """
    :synopsis: Create an Agreement Code

    .. literalinclude:: demo/post_create_agreement_code.http
        :language: http

    .. literalinclude:: demo/create_agreement_code.json
        :language: json

    .. literalinclude:: demo/200.http
        :language: http

    .. literalinclude:: demo/create_agreement_code_response.json
        :language: json


    :status 200:
    :status 400:
    :reqheader Content-Type: Must be `application/json`
    :resheader Cotnent-Type: :mimetype:`application/json`

    """
    identifier = document['agent_official_number_fsma']
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = '%s-%s.json' % (identifier, timestamp,)
    fname = os.path.join(current_app.config['PATH_DIR_LOG'], 'create_agreement_code', fname)

    with open(fname, 'w') as outfile:
        result = v01.create_agreement_code(document, logfile=outfile)

    return result

@bp.route('/send_agreement', methods=['POST'])
@ws_jsonify
@log_to_file
@validation_json(validation_send_agreement)
def send_agreement(document):
    """
    :synopsis: Send an agreement

    **Not Yet Implemented**

    .. literalinclude:: demo/501.http
        :language: http

    :status 501:
    :reqheader Content-Type: :mimetype:`application/json`
    :resheader Content-Type: :mimetype:`application/json`
    """
    return v01.send_agreement(document)


@bp.route('/get_proposal_pdf', methods=['POST'])
def get_proposal_pdf():
    """
    :synopsis: Get a PDF version of a Proposal

    **Not Yet Implemented**

    .. literalinclude:: demo/501.http
        :language: http
    """
    return jsonify({
        'message': "Web service not implemented"
    }), 501