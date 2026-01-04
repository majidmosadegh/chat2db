"""
Dependency Injection Container
Centralized service management and dependency injection.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

# Import services only when needed to avoid circular imports
from services.ai_dictionary_service import ai_dictionary_service
from services.db_connector import DirectDatabaseConnector
from db.connector import DatabaseConnector


class Container:
    """
    Centralized dependency injection container.
    Manages all application services and their lifecycles.
    """

    def __init__(self):
        self._db_session: Optional[AsyncSession] = None

    def get_llm_service(self):
        """Get LLM service instance"""
        from services.llm_service import LLMService
        return LLMService()

    @property
    def ai_dictionary_service(self):
        """Get AI dictionary service"""
        return ai_dictionary_service

    def get_database_connector(self, db_type: str, host: str, port: int,
                             username: str, password: str, database: str) -> DirectDatabaseConnector:
        """Create external database connector"""
        return DirectDatabaseConnector(db_type, host, port, username, password, database)

    def get_metadata_connector(self, snapshot, db_conn) -> DatabaseConnector:
        """Create metadata database connector"""
        return DatabaseConnector(snapshot, db_conn)

    async def initialize_services(self, session: AsyncSession):
        """Initialize all services that need database access"""
        self._db_session = session
        # Services are initialized on-demand to avoid circular imports

    async def shutdown(self):
        """Shutdown all services"""
        # Services handle their own cleanup
        pass


# Global container instance
container = Container()
