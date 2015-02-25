from flask import request
import werkzeug.exceptions


def is_json_body():
    try:
        return request.get_json()
    except werkzeug.exceptions.BadRequest:
        return None
