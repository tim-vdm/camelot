from __future__ import absolute_import

from flask import Blueprint
from flask import abort
from flask import jsonify
from flask import Response

from .decorators import to_json, log_to_file, check_minimal_requirements
from .utils import is_json_body

from api import v01

bp = Blueprint('api_v01', __name__)


@bp.route('/calculate_proposal', methods=['POST'])
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
            "agent_official_number_fsma": "128Char",
            "agreement_date": {
                "month": 2,
                "year": 2015,
                "day": 29
            },
            "duration": 10,
            "from_date": {"month": 2, "year": 2015, "day": 26},
            "insured_party__1__birthdate": {
                "month": 2,
                "year": 2015,
                "day": 26
            },
            "insured_party__1__sex": "M",
            "package_id": 10,
            "premium_schedule__1__premium_fee_1": "2.00",
            "premium_schedule__1__product_id": 67,
            "premium_schedule__2__product_id": null,
            "premium_schedules_coverage_level_type": "fixed_amount",
            "premium_schedules_coverage_limit": "0.05",
            "premium_schedules_payment_duration": 10,
            "premium_schedules_period_type": "single",
            "premium_schedules_premium_rate_1": "0.0005"
        }

    .. sourcecode:: http

        HTTP/1.0 200 OK
        Content-Length: 19
        Content-Type: application/json
        Date: Mon, 23 Feb 2015 06:35:43 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "premium_schedule__1__amount": "1.0",
            "premium_schedule__2__amount": null
        }


    .. sourcecode:: http

        HTTP/1.0 400 BAD REQUEST
        Content-Length: 1057
        Content-Type: application/json
        Date: Thu, 26 Feb 2015 09:40:32 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "agent_official_number_fsma": {
                "message": "Required"
            },
            "agreement_date": {
                "message": "Required"
            },
            "duration": {
                "message": "Required"
            },
            "from_date": {
                "message": "Required"
            },
            "insured_party__1__birthdate": {
                "message": "Required"
            },
            "insured_party__1__sex": {
                "message": "Required"
            },
            "package_id": {
                "message": "Required"
            },
            "premium_schedule__1__premium_fee_1": {
                "message": "Required"
            },
            "premium_schedule__1__product_id": {
                "message": "Required"
            },
            "premium_schedule__2__product_id": {
                "message": "Required"
            },
            "premium_schedules_coverage_level_type": {
                "message": "Required"
            },
            "premium_schedules_coverage_limit": {
                "message": "Required"
            },
            "premium_schedules_payment_duration": {
                "message": "Required"
            },
            "premium_schedules_period_type": {
                "message": "Required"
            },
            "premium_schedules_premium_rate_1": {
                "message": "Required"
            }
        }

    If there is an error in the values of the json document, the server will
    return a message with the path of the variable.

    .. sourcecode:: http

        HTTP/1.0 400 BAD REQUEST
        Content-Length: 98
        Content-Type: application/json
        Date: Thu, 26 Feb 2015 09:40:32 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "agreement_date/day": {
                "message": "day is out of range for month",
                "value": 29
            }
        }

    If there is a extra key in the json document, the server will return this kind of message

    .. sourcecode:: http

        HTTP/1.0 400 BAD REQUEST
        Content-Length: 1057
        Content-Type: application/json
        Date: Thu, 26 Feb 2015 09:40:32 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "name": {
                "message": "extra keys not allowed",
                "value": "value"
            }
        }

    """
    json_document = is_json_body()

    # Check the json

    from .validation_message import validation_calculate_proposal

    proposal, errors = validation_calculate_proposal(json_document)

    if errors:
        return jsonify(errors), 400

    amount = v01.calculate_proposal(proposal)
    return jsonify({
        'premium_schedule__1__amount': amount,
        'premium_schedule__2__amount': None
    })


@bp.route('/create_agreement_code', methods=['POST'])
# @check_minimal_requirements
def create_agreement_code():
    """
    :synopsis: Create an Agreement Code

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
    return jsonify({
        'code': v01.create_agreement_code()
    })


@bp.route('/create_proposal', methods=['POST'])
def create_proposal():
    """
    :synopsis: Create a proposal

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
    return jsonify({
        'message': "Web service not implemented"
    }), 501


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
    return jsonify({
        'message': "Web service not implemented"
    }), 501

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
    return jsonify({
        'message': "Web service not implemented"
    }), 501

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
    return jsonify({
        'message': "Web service not implemented"
    }), 501

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
    return jsonify({
        'message': "Web service not implemented"
    }), 501