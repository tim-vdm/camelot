import os
import uuid
import json
import datetime
from cStringIO import StringIO
from pkg_resources import resource_stream, resource_listdir

from flask import Blueprint
from flask import current_app
from flask import jsonify
from flask import send_file

from vfinance_ws.ws.decorators import log_to_file, ws_jsonify, validation_json

from vfinance_ws.ws.validation_message import (
    validation_calculate_proposal,
    validation_ci_create_agreement_code,
    validation_send_agreement,
    validation_get_packages,
    validation_create_agreement_code
)

from vfinance_ws.api import v01
from vfinance_ws.api import v11
from flask_httpauth import HTTPBasicAuth

bp = Blueprint('api_v11', __name__)

auth = HTTPBasicAuth()
@auth.verify_password
def verify_token(username, password):
    with resource_stream(__name__, os.path.join('..', 'data', 'tokens.json')) as infile:
        tokens = json.load(infile)
    return username in tokens

@bp.route('/credit_insurance/calculate_proposal', methods=['POST'])
@auth.login_required
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

    ..versionchanged:: 1.1
        Prefix the /calculate_proposal WS with /credit_insurance


    """
    return v01.calculate_proposal(document)


@bp.route('/credit_insurance/create_agreement_code', methods=['POST'])
@auth.login_required
@ws_jsonify
@log_to_file
@validation_json(validation_ci_create_agreement_code)
def ci_create_agreement_code(document):
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
    :resheader Content-Type: :mimetype:`application/json`

    ..versionchanged:: 1.1
        Prefix the /create_agreement_code WS with /credit_insurance

    """
    # from nose.tools import set_trace
    # set_trace()
    try:
        sIO = StringIO()

        result = v11.ci_create_agreement_code(document, logfile=sIO)

        values = {
            'fsma': document['agent_official_number_fsma'],
            'code': result['code'].replace('/', '_'),
            'ident': uuid.uuid4().hex,
        }
        fname = '{code}-{fsma}-{ident}.json'.format(**values)

        fname = os.path.join(current_app.config['PATH_DIR_LOG'],
                             'create_agreement_code',
                             fname)

        with open(fname, 'w') as outfile:
            sIO.seek(0)
            outfile.write(sIO.getvalue())

        return result
    finally:
        sIO.close()


@bp.route('/credit_insurance/send_agreement', methods=['POST'])
@auth.login_required
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

    ..versionchanged:: 1.1
        Prefix the /send_agreement WS with /credit_insurance

    """
    return v01.send_agreement(document)


@bp.route('/credit_insurance/get_proposal_pdf', methods=['POST'])
@auth.login_required
def get_proposal_pdf():
    """
    :synopsis: Get a PDF version of a Proposal

    **Not Yet Implemented**

    .. literalinclude:: demo/501.http
        :language: http

    ..versionchanged:: 1.1
        Prefix the /get_proposal_pdf WS with /credit_insurance

    """
    return jsonify({
        'message': "Web service not implemented"
    }), 501


@bp.route('/credit_insurance/get_packages', methods=['POST'])
@auth.login_required
@ws_jsonify
@validation_json(validation_get_packages)
def get_packages(document):
    """
    :synopsis: Get a list of the available packages for the customer
    .. literalinclude:: demo/post_get_packages.http
        :language: http

    .. literalinclude:: demo/get_packages.json
        :language: json

    .. literalinclude:: demo/200.http
        :language: http

    .. literalinclude:: demo/get_packages_response.json
        :language: json

    :status 200:
    :status 400:
    :reqheader Content-Type: Must be `application/json`
    :resheader Content-Type: :mimetype:`application/json`

    ..versionchanged:: 1.1
        Prefix the /get_package WS with /credit_insurance
    """
    return {'packages': v01.get_packages(document)}


@bp.route('/docs/', defaults={'filename': 'index.html'})
@bp.route('/docs/<path:filename>')
def docs(filename):
    mimetypes = {
        ".css": "text/css",
        ".html": "text/html",
        ".js": "application/javascript",
        ".png": "image/png",
        ".gif": "image/gif"
    }
    ext = os.path.splitext(filename)[1]
    mimetype = mimetypes.get(ext, "text/html")
    path = os.path.join('docs', 'v0.1', filename)
    return send_file(resource_stream(__name__, path), mimetype=mimetype)

@bp.route('/create_agreement_code', methods=['POST'])
@ws_jsonify
@validation_json(validation_create_agreement_code)
def create_agreement_code(document):
    try:
        sIO = StringIO()

        result = v11.create_agreement_code(document, logfile=sIO)

        values = {
            'fsma': document['agent_official_number_fsma'],
            'code': result['code'].replace('/', '_'),
            'ident': uuid.uuid4().hex,
        }
        fname = '{code}.json'.format(**values)

        today = datetime.date.today()
        day = '{0:02}'.format(today.day)
        month = '{0:02}'.format(today.month)
        year = '{}'.format(today.year)

        full_dir = os.path.join(current_app.config['PATH_DIR_LOG'],
                                'v11',
                                'create_agreement_code',
                                year,
                                month,
                                day)

        if not os.path.exists(full_dir):
            os.makedirs(full_dir)
        fname = os.path.join(full_dir,
                             fname)


        with open(fname, 'w') as outfile:
            sIO.seek(0)
            outfile.write(sIO.getvalue())

        return result
    finally:
        sIO.close()
