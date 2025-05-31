"""
WSGI config for Render deployment.
This module imports the WSGI application from the Django project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pappulse.settings')

application = get_wsgi_application()
app = application  # Add this alias for Render 