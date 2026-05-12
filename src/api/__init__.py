"""rest-api-template — production FastAPI scaffold.

Exports the application factory + a few thin re-exports so consumers can do
``from api import create_app, settings``.
"""

from api.app import create_app
from api.config import Settings, get_settings

__all__ = ["Settings", "create_app", "get_settings"]
