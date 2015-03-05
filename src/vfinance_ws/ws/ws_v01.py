from __future__ import absolute_import

from flask import Blueprint
from flask import jsonify

import camelot.core.exception
import camelot.core.utils

from vfinance_ws.ws.decorators import log_to_file, check_minimal_requirements
from vfinance_ws.ws.utils import is_json_body

from vfinance_ws.api import v01

bp = Blueprint('api_v01', __name__)


@bp.route('/calculate_proposal', methods=['POST'])
@log_to_file
@check_minimal_requirements
def calculate_proposal():
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
    json_document = is_json_body()

    # Check the json

    from .validation_message import validation_calculate_proposal

    proposal, errors = validation_calculate_proposal(json_document)

    if errors:
        return jsonify(errors), 400

    try:
        return jsonify(v01.calculate_proposal(proposal))
    except Exception, ex:
        if isinstance(ex, camelot.core.exception.UserException):
            if isinstance(ex.message, camelot.core.utils.ugettext_lazy):
                return jsonify({'message': ex.message._string_to_translate}), 400
        return jsonify({'message': ex.message}), 400


@bp.route('/create_agreement_code', methods=['POST'])
@log_to_file
@check_minimal_requirements
def create_agreement_code():
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
    json_document = is_json_body()

    # Check the json

    from .validation_message import validation_create_agreement_code

    proposal, errors = validation_create_agreement_code(json_document)

    if errors:
        return jsonify(errors), 400

    try:
        return jsonify(v01.create_agreement_code(proposal))
    except Exception, ex:
        if isinstance(ex, camelot.core.exception.UserException):
            if isinstance(ex.message, camelot.core.utils.ugettext_lazy):
                return jsonify({'message': ex.message._string_to_translate}), 400
        return jsonify({'message': ex.message}), 400


@bp.route('/send_agreement', methods=['POST'])
@check_minimal_requirements
def send_agreement():
    """
    :synopsis: Send an agreement

    **Not Yet Implemented**

    .. literalinclude:: demo/501.http
        :language: http

    :status 501:
    :reqheader Content-Type: :mimetype:`application/json`
    :resheader Content-Type: :mimetype:`application/json`
    """
    json_document = is_json_body()
    from .validation_message import validation_send_agreement

    proposal, errors = validation_send_agreement(json_document)

    if errors:
        return jsonify(errors), 400

    try:
        v01.send_agreement(proposal)
        return jsonify({})
    except Exception, ex:
        if isinstance(ex, camelot.core.exception.UserException):
            if isinstance(ex.message, camelot.core.utils.ugettext_lazy):
                return jsonify({'message': ex.message._string_to_translate}), 400
        return jsonify({'message': ex.message}), 400 


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
