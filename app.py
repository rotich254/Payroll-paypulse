"""
Simple app module that imports the WSGI application.
This is for compatibility with Render's default settings.
"""

from wsgi import application, app

# This file exists to help Render find the application
# The actual WSGI application is defined in wsgi.py 