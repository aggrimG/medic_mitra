import sys
import os
import urllib.parse

# Add parent directory to sys.path so app and its modules can be resolved
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class VercelWSGIMiddleware:
    """
    WSGI middleware to resolve Vercel serverless routing.
    When Vercel rewrites incoming requests, this middleware
    extracts the target route from '__vercel_route' or headers
    and sets PATH_INFO so Flask routes match accurately.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = environ.get('QUERY_STRING', '')
        if '__vercel_route=' in qs:
            params = urllib.parse.parse_qs(qs, keep_blank_values=True)
            routes = params.pop('__vercel_route', None)
            if routes and routes[0]:
                route = routes[0]
                if not route.startswith('/'):
                    route = '/' + route
                environ['PATH_INFO'] = route
            environ['QUERY_STRING'] = urllib.parse.urlencode(params, doseq=True)
        else:
            path = environ.get('PATH_INFO', '')
            if path in ('/api/index', '/api/index/', '/api', '/api/'):
                environ['PATH_INFO'] = '/'
            elif path.startswith('/api/index/'):
                environ['PATH_INFO'] = path[len('/api/index'):]

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelWSGIMiddleware(app.wsgi_app)

# Expose WSGI app for Vercel Serverless Function
application = app
