"""
Application Interfaces - Dependency Inversion Principle.
These interfaces define contracts for infrastructure services.
"""

from .repository_interfaces import (
    IDatabaseConnectionRepository,
    ILLMModelRepository,
    IAIDictionaryRepository,
    ISnapshotRepository
)
from .service_interfaces import (
    ILLMService,
    IDatabaseService,
    IEncryptionService
)
from .unit_of_work import IUnitOfWork
from .event_publisher import IEventPublisher

__all__ = [
    # Repository interfaces
    'IDatabaseConnectionRepository',
    'ILLMModelRepository',
    'IAIDictionaryRepository',
    'ISnapshotRepository',

    # Service interfaces
    'ILLMService',
    'IDatabaseService',
    'IEncryptionService',

    # Infrastructure interfaces
    'IUnitOfWork',
    'IEventPublisher'
]









