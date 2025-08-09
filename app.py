"""
Simple app module that imports the WSGI application.
This is for compatibility with Render's default settings.
"""

from pappulse.wsgi import application

# This file exists to help Render find the application
# The actual WSGI application is defined in pappulse/wsgi.py

app = application
