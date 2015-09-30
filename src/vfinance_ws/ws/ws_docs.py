import os
from flask import Blueprint
from flask import send_file
from pkg_resources import resource_stream

bp = Blueprint('api_docs', __name__)

@bp.route('/', defaults={'filename': 'index.html'})
@bp.route('/<path:filename>')
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
    # path = os.path.join('docs', 'v1.1', filename)
    path = os.path.join('docs', filename)
    return send_file(resource_stream(__name__, path), mimetype=mimetype)

