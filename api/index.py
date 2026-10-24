import sys
import os

# Add parent directory to sys.path so app and its modules can be resolved
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class VercelWSGIMiddleware:
    """
    WSGI middleware to resolve Vercel serverless path translation.
    When Vercel rewrites incoming traffic (/(.*)) to /api/index,
    this middleware extracts the actual requested route from Vercel's
    HTTP headers or normalizes PATH_INFO so Flask routes match correctly.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        matched = environ.get('HTTP_X_MATCHED_PATH') or environ.get('HTTP_X_FORWARDED_URI')
        if matched and matched not in ('/api/index', '/api/index/'):
            environ['PATH_INFO'] = matched.split('?')[0]
        else:
            path = environ.get('PATH_INFO', '')
            if path in ('/api/index', '/api/index/', '/api', '/api/'):
                environ['PATH_INFO'] = '/'
            elif path.startswith('/api/index/'):
                environ['PATH_INFO'] = path[len('/api/index'):]
            elif path.startswith('/api/'):
                environ['PATH_INFO'] = path[len('/api'):]

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelWSGIMiddleware(app.wsgi_app)

# Expose WSGI app for Vercel Serverless Function
application = app
