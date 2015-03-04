from __future__ import absolute_import
import datetime

from flask import Blueprint
from flask import request
from flask import jsonify

import werkzeug.exceptions

from . import decorators
from .utils import is_json_body

bp = Blueprint('api_test', __name__)


@bp.route('/request', methods=['GET', 'POST', 'PUT', 'PATCH', 'HEAD'])
@decorators.to_json
@decorators.log_to_file
def debug_request():
    """
    :synopsis: Show the content of your HTTP request

    **Example request**

    .. sourcecode:: http

        POST /api/test/request HTTP/1.1
        Accept: application/json
        Accept-Encoding: gzip, deflate
        Connection: keep-alive
        Content-Length: 0
        Content-Type:  application/json
        Host: localhost:5000
        User-Agent: HTTPie/0.9.1

    **The response from the server**

    .. sourcecode:: http

        HTTP/1.0 200 OK
        Content-Length: 440
        Content-Type: application/json
        Date: Mon, 23 Feb 2015 10:04:39 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "content_type": "application/json",
            "data": "",
            "headers": {
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Content-Length": "0",
                "Content-Type": "application/json",
                "Host": "localhost:5000",
                "User-Agent": "HTTPie/0.9.1"
            },
            "is_json": false,
            "method": "POST",
            "remote_addr": "127.0.0.1",
            "timestamp": "Mon, 23 Feb 2015 11:04:39 GMT"
        }
    """

    json = is_json_body()

    return {
        'remote_addr': request.remote_addr,
        'timestamp': datetime.datetime.now(),
        'method': request.method,
        'data': request.data,
        'content_type': request.content_type,
        'headers': dict(request.headers.items()),
        'is_json': json is not None,
        'json': json
    }


@bp.route('/is_compliant', methods=['POST'])
def is_compliant():
    """
    :synopsis: Inform if you respect the minimal requirements
               for the web services.

    .. sourcecode:: http

        POST /api/test/is_compliant HTTP/1.1
        Accept: application/json
        Accept-Encoding: gzip, deflate
        Connection: keep-alive
        Content-Length: 0
        Content-Type: application/json; charset=utf-8
        Host: localhost:5000
        User-Agent: HTTPie/0.9.1

    .. sourcecode:: http

        HTTP/1.0 200 OK
        Content-Length: 103
        Content-Type: application/json
        Date: Mon, 23 Feb 2015 10:21:27 GMT
        Server: Werkzeug/0.10.1 Python/2.7.8+

        {
            "compliant": false,
            "message": "Content-Type is not 'application/json'",
            "status_code": 400
        }

    :json> boolean compliant: Inform if the request is compliant
    :json> string message: Error for the compliancy
    :json> integer status_code: HTTP Code

    :status 405: Method not allowed
    """

    response = {
        'status_code': 400,
        'compliant': False
    }

    if not request.content_type:
        response['message'] = 'Content-Type is not setted'
    elif request.content_type != 'application/json':
        response['message'] = "Content-Type is not 'application/json'"
    else:
        try:
            request.get_json()  # NOQA
            response.update({
                'compliant': True,
                'status_code': 200,
            })
        except werkzeug.exceptions.BadRequest:
            response['message'] = "Invalid JSON message"

    return jsonify(response)
