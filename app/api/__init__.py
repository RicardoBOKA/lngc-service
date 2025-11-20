"""Module des endpoints API."""

from app.api.websocket import router as websocket_router
from app.api.rest import router as rest_router

__all__ = ["websocket_router", "rest_router"]

