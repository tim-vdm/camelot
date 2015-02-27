from werkzeug.contrib.fixers import ProxyFix

from ws_server import create_app


app = create_app()
app.wsgi_app = ProxyFix(app.wsgi_app)
app.debug = True
app.run(port=19021)
