"""
Dependency Injection Configuration.
Provides factory functions for injecting dependencies.
"""

from ...application.handlers.generate_ai_dictionary_handler import GenerateAIDictionaryHandler
from ...application.handlers.execute_sql_handler import ExecuteSQLHandler
from ...domain.services.ai_dictionary_service import AIDictionaryService
from ...infrastructure.external.llm_service_impl import LLMServiceImpl
from ...infrastructure.database.repositories import AIDictionaryRepositoryImpl
from ...infrastructure.database.unit_of_work import UnitOfWorkImpl


# Service instances (singletons)
_llm_service = LLMServiceImpl()
_ai_service = AIDictionaryService()
_unit_of_work = UnitOfWorkImpl()
_ai_repository = AIDictionaryRepositoryImpl()

# Handler instances
_ai_handler = GenerateAIDictionaryHandler(
    ai_service=_ai_service,
    llm_service=_llm_service,
    repository=_ai_repository,
    unit_of_work=_unit_of_work
)

_sql_handler = ExecuteSQLHandler(
    database_service=None,  # TODO: Implement database service
    unit_of_work=_unit_of_work
)


def get_ai_handler() -> GenerateAIDictionaryHandler:
    """Get AI dictionary handler instance."""
    return _ai_handler


def get_sql_handler() -> ExecuteSQLHandler:
    """Get SQL execution handler instance."""
    return _sql_handler









