"""
Presentation API Layer - REST API endpoints.
Clean API endpoints that delegate to application handlers.
"""

from .v1.api import router as v1_router

__all__ = ['v1_router']









