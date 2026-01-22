"""WSGI entry point for production servers."""

from .app import create_app

# Expose the WSGI application callable named "app" for servers like gunicorn
app = create_app()
