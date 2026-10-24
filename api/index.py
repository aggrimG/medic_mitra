import sys
import os

# Add parent directory to sys.path so app and its modules can be resolved
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Expose WSGI app for Vercel Serverless Function
application = app
