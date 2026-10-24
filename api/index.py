import sys
import os
import urllib.parse

# Add parent directory to sys.path so app and its modules can be resolved
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

def resolve_route(environ):
    """
    Deterministically extracts the client-requested route path across all
    possible Vercel execution contexts.
    """
    # 1. Query parameter passed via Vercel rewrite (__vercel_route)
    qs = environ.get('QUERY_STRING', '')
    if '__vercel_route=' in qs:
        params = urllib.parse.parse_qs(qs, keep_blank_values=True)
        routes = params.pop('__vercel_route', None)
        environ['QUERY_STRING'] = urllib.parse.urlencode(params, doseq=True)
        if routes and routes[0]:
            candidate = routes[0].strip()
            if not candidate.startswith('/'):
                candidate = '/' + candidate
            # Guard against un-substituted wildcard literals ($1, :path, etc.)
            if candidate and not any(token in candidate for token in ('$1', ':path', ':path*')):
                return candidate

    # 2. Vercel edge / proxy forwarding headers
    for header in ('HTTP_X_FORWARDED_URI', 'HTTP_X_ORIGINAL_URL', 'HTTP_X_INVOKE_PATH', 'HTTP_X_MATCHED_PATH'):
        val = environ.get(header)
        if val:
            path_only = val.split('?')[0].strip()
            if path_only and path_only not in ('/api/index', '/api/index/', '/api', '/api/'):
                if not any(token in path_only for token in ('$1', ':path', ':path*')):
                    return path_only

    # 3. Direct PATH_INFO from WSGI gateway
    path = environ.get('PATH_INFO', '')
    if path and path not in ('/api/index', '/api/index/', '/api', '/api/'):
        if path.startswith('/api/index/'):
            return path[len('/api/index'):]
        elif path.startswith('/api/'):
            return path[len('/api'):]
        return path

    return '/'

class VercelWSGIMiddleware:
    """
    WSGI middleware to resolve Vercel serverless routing.
    Normalizes PATH_INFO so Flask internal router matches
    endpoints accurately without 404 or redirect loops.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        environ['PATH_INFO'] = resolve_route(environ)
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelWSGIMiddleware(app.wsgi_app)

# Expose WSGI app for Vercel Serverless Function
application = app
