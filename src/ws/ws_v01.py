from __future__ import absolute_import

from flask import Blueprint
from flask import abort

bp = Blueprint('api_prototype', __name__)

from .decorators import to_json, log_to_file, check_minimal_requirements
from .utils import is_json_body

from api import v01


@bp.route('/calculate_proposal', methods=['POST'])
@to_json
@log_to_file
@check_minimal_requirements
def calculate_proposal():
    """
    :synopsis: Calculate the amount of a proposal
    :reqheader Content-Type: application/json

    :status 200: OK
    :status 400: Bad Request
    :status 501: Not implemented

    .. sourcecode:: http

        POST /api/v0.1/calculate_proposal HTTP/1.1
        Accept: application/json
        Accept-Encoding: gzip, deflate
        Connection: keep-alive
        Content-Length: 20
        Content-Type:  application/json
        Host: localhost:5000
        User-Agent: HTTPie/0.9.1

        {
        }

    .. sourcecode:: http

        HTTP/1.0 200 OK
        Content-Length: 19
        Content-Type: application/json
        Date: Mon, 23 Feb 2015 06:35:43 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "amount": "1.0"
        }

    """
    message = is_json_body()
    # Check the json

    amount = v01.calculate_proposal(message)
    return {'amount': amount}


@bp.route('/create_agreement_code', methods=['POST'])
@to_json
@log_to_file
def create_agreement_code():
    """
    :synopsis: Create an Agreement Code

    .. sourcecode:: bash

        > http --verbose -j POST "http://staging-patronale-life.mgx.io/api/v0.1/create_agreement_code" "Content-Type: application/json"

    **Not Yet Implemented**

    .. sourcecode:: http

        POST /api/v0.1/create_agreement_code HTTP/1.1
        Accept: application/json
        Accept-Encoding: gzip, deflate
        Connection: keep-alive
        Content-Length: 0
        Content-Type:  application/json
        Host: localhost:19021
        User-Agent: HTTPie/0.9.1

    .. sourcecode:: http

        HTTP/1.0 200 OK
        Content-Length: 36
        Content-Type: application/json
        Date: Mon, 23 Feb 2015 15:26:04 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "code": "000/0000/00000"
        }

    :status 200: OK
    :reqheader Content-Type: Must be `application/json`

    """

    return {
        'code': v01.create_agreement_code()
    }


@bp.route('/create_proposal', methods=['POST'])
def create_proposal():
    """
    :synopsis: Create a proposal

    .. sourcecode:: bash

        > http --verbose -j POST "http://staging-patronale-life.mgx.io/api/v0.1/create_proposal" "Content-Type: application/json"

    **Not Yet Implemented**

    .. sourcecode:: http

        HTTP/1.0 501 NOT IMPLEMENTED
        Content-Length: 46
        Content-Type: application/json
        Date: Mon, 23 Feb 2015 06:44:54 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "message": "Web service not implemented"
        }

    :status 501: Not implemented
    :reqheader Content-Type: Must be :mimetype:`application/json`

    """
    abort(501)


@bp.route('/modify_proposal', methods=['POST'])
def modify_proposal():
    """
    :synopsis: Modify a proposal

    **Not Yet Implemented**

    .. sourcecode:: http

        HTTP/1.0 501 NOT IMPLEMENTED
        Content-Length: 46
        Content-Type: application/json
        Date: Mon, 23 Feb 2015 06:44:54 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "message": "Web service not implemented"
        }
    """
    abort(501)


@bp.route('/cancel_proposal', methods=['POST'])
def cancel_proposal():
    """
    :synopsis: Cancel a Proposal

    **Not Yet Implemented**

    .. sourcecode:: http

        HTTP/1.0 501 NOT IMPLEMENTED
        Content-Length: 46
        Content-Type: application/json
        Date: Mon, 23 Feb 2015 06:44:54 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "message": "Web service not implemented"
        }
    """
    abort(501)


@bp.route('/proposal_to_managed', methods=['POST'])
def proposal_to_managed():
    """
    :synopsis: Proposal to managed

    **Not Yet Implemented**

    .. sourcecode:: http

        HTTP/1.0 501 NOT IMPLEMENTED
        Content-Length: 46
        Content-Type: application/json
        Date: Mon, 23 Feb 2015 06:44:54 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "message": "Web service not implemented"
        }
    """
    abort(501)


@bp.route('/get_proposal_pdf', methods=['POST'])
def get_proposal_pdf():
    """
    :synopsis: Get a PDF version of a Proposal

    **Not Yet Implemented**

    .. sourcecode:: http

        HTTP/1.0 501 NOT IMPLEMENTED
        Content-Length: 46
        Content-Type: application/json
        Date: Mon, 23 Feb 2015 06:44:54 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "message": "Web service not implemented"
        }
    """
    abort(501)
