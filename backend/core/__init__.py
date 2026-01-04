"""
Core module for centralized application architecture.
Provides unified access to all major services and components.
"""

from .app import create_application
from .container import container

__all__ = ['create_application', 'container']
