# معماری Clean Architecture (Domain-Driven Design)

## نمای کلی (Overview)

پلتفرم SQL PT از معماری **Clean Architecture** پیروی می‌کند که توسط Robert C. Martin ارائه شده و با اصول **Domain-Driven Design (DDD)** ترکیب شده است. این معماری لایه‌های مجزا با مسئولیت‌های مشخص ایجاد کرده و وابستگی‌ها را از لایه‌های داخلی به خارجی هدایت می‌کند.

## معماری کلی (Architecture Overview)

```
┌─────────────────────────────────────────────────────────────┐
│                    Clean Architecture                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Presentation Layer                     │    │
│  │  ┌─────────────────────────────────────────────────┐ │    │
│  │  │               API Controllers                    │ │    │
│  │  │  (REST API, DTOs, Request/Response Models)      │ │    │
│  │  └─────────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Application Layer                     │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │  Use Cases  │Commands &   │ Application     │    │    │
│  │  │             │Queries      │ Services        │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 Domain Layer                        │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │  Entities   │Value Objects│ Domain Services │    │    │
│  │  │             │             │                 │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Infrastructure Layer                   │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │Repositories │External     │ Configuration   │    │    │
│  │  │             │Services     │                 │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────┘
                      │
           ┌──────────┴──────────┐
           │   External Systems  │
           │   (Database, APIs,  │
           │    File System)     │
           └─────────────────────┘
```

## اصول معماری (Architecture Principles)

### 1. **Dependency Inversion Principle**
- لایه‌های داخلی به abstractionها وابسته هستند، نه پیاده‌سازی‌های concrete
- Dependency injection برای تزریق وابستگی‌ها
- Interface segregation در تعریف قراردادها

### 2. **Single Responsibility Principle**
- هر کلاس یک مسئولیت واحد دارد
- لایه‌ها مرزهای واضح مسئولیت دارند
- Separation of concerns در همه سطوح

### 3. **Domain-Driven Design**
- تمرکز بر business domain
- Ubiquitous language در کد
- Bounded contexts برای مرزهای domain

## لایه‌ها و مسئولیت‌ها (Layers & Responsibilities)

### 1. Domain Layer (لایه دامنه)

لایه مرکزی که قوانین کسب‌وکار و منطق domain را پیاده‌سازی می‌کند:

#### Entities (موجودیت‌ها):
```python
# src/domain/entities/base_entity.py
from abc import ABC
from typing import Any, Dict
from pydantic import BaseModel

class BaseEntity(BaseModel, ABC):
    """Base class for all domain entities"""

    id: Any

    def to_dict(self) -> Dict[str, Any]:
        return self.dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)
```

```python
# src/domain/entities/database_connection.py
from .base_entity import BaseEntity
from typing import Optional

class DatabaseConnection(BaseEntity):
    """Domain entity for database connections"""

    db_type: str
    host: str
    port: int
    username: str
    encrypted_password: str
    database_name: str
    is_active: bool = True

    def get_connection_string(self) -> str:
        """Business logic for connection string generation"""
        if self.db_type.lower() == "postgresql":
            return f"postgresql://{self.username}:{self._decrypt_password()}@{self.host}:{self.port}/{self.database_name}"
        # ... other database types

    def _decrypt_password(self) -> str:
        """Domain logic for password handling"""
        # Implementation details hidden from other layers
        pass

    def validate_connection(self) -> bool:
        """Business rules for connection validation"""
        return (
            bool(self.host and self.host.strip()) and
            1 <= self.port <= 65535 and
            bool(self.database_name and self.database_name.strip())
        )
```

#### Value Objects (اشیاء ارزش):
```python
# src/domain/value_objects/sql_query.py
from pydantic import BaseModel, validator
from typing import List, Optional

class SQLQuery(BaseModel):
    """Value object representing a SQL query"""

    query_text: str
    parameters: Optional[Dict[str, Any]] = None
    execution_timeout: int = 30

    @validator('query_text')
    def validate_query_text(cls, v):
        if not v or not v.strip():
            raise ValueError('Query text cannot be empty')
        return v.strip()

    def is_read_only(self) -> bool:
        """Business rule: Check if query is read-only"""
        query_upper = self.query_text.upper().strip()
        dangerous_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER']
        return not any(keyword in query_upper for keyword in dangerous_keywords)

    def get_query_hash(self) -> str:
        """Generate hash for query identification"""
        import hashlib
        content = f"{self.query_text}{self.parameters or {}}"
        return hashlib.md5(content.encode()).hexdigest()
```

```python
# src/domain/value_objects/llm_prompt.py
class LLMPrompt(BaseModel):
    """Value object for LLM prompts"""

    template: str
    variables: Dict[str, Any]
    language: str = "english"
    version: str = "1.0.0"

    def render(self) -> str:
        """Render prompt with variables"""
        try:
            return self.template.format(**self.variables)
        except KeyError as e:
            raise ValueError(f"Missing required variable: {e}")

    def validate_variables(self) -> bool:
        """Validate that all required variables are provided"""
        import re
        placeholders = re.findall(r'\{(\w+)\}', self.template)
        return all(var in self.variables for var in placeholders)
```

### 2. Application Layer (لایه اپلیکیشن)

لایه orchestrator که use cases را پیاده‌سازی می‌کند:

#### Commands & Queries (CQRS Pattern):
```python
# src/application/commands/generate_ai_dictionary_command.py
from pydantic import BaseModel
from typing import Optional

class GenerateAIDictionaryCommand(BaseModel):
    """Command for AI dictionary generation"""

    snapshot_id: int
    business_domain: str
    database_description: str
    target_user: str
    language: Optional[str] = "persian"
    additional_notes: Optional[str] = None

    def validate(self) -> None:
        """Business validation for command"""
        if not self.business_domain or not self.business_domain.strip():
            raise ValueError("Business domain is required")

        if not self.target_user or not self.target_user.strip():
            raise ValueError("Target user is required")
```

```python
# src/application/queries/execute_sql_query.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ExecuteSQLQuery(BaseModel):
    """Query for SQL execution"""

    sql_query: str
    snapshot_id: int
    parameters: Optional[Dict[str, Any]] = None
    row_limit: int = 1000

    def validate_query(self) -> None:
        """Application-level query validation"""
        if not self.sql_query or not self.sql_query.strip():
            raise ValueError("SQL query cannot be empty")

        # Additional business rules
        if len(self.sql_query) > 10000:
            raise ValueError("Query too long")

        if self.row_limit > 50000:
            raise ValueError("Row limit too high")
```

#### Command Handlers:
```python
# src/application/handlers/generate_ai_dictionary_handler.py
from ..commands.generate_ai_dictionary_command import GenerateAIDictionaryCommand
from ..interfaces.service_interfaces import IAIDictionaryService
from typing import Protocol

class GenerateAIDictionaryHandler:
    """Handler for AI dictionary generation command"""

    def __init__(self, ai_dictionary_service: IAIDictionaryService):
        self._ai_dictionary_service = ai_dictionary_service

    async def handle(self, command: GenerateAIDictionaryCommand) -> str:
        """
        Handle the generate AI dictionary command.

        Args:
            command: The command to handle

        Returns:
            Job ID for tracking the generation process
        """
        # Validate command
        command.validate()

        # Delegate to service
        job_id = await self._ai_dictionary_service.start_generation_job(
            snapshot_id=command.snapshot_id,
            business_domain=command.business_domain,
            database_description=command.database_description,
            target_user=command.target_user,
            language=command.language,
            additional_notes=command.additional_notes
        )

        return job_id
```

#### Application Services:
```python
# src/application/interfaces/service_interfaces.py
from abc import ABC, abstractmethod
from typing import Protocol, Optional, Dict, Any, List

class IAIDictionaryService(Protocol):
    """Interface for AI Dictionary service"""

    async def start_generation_job(
        self,
        snapshot_id: int,
        business_domain: str,
        database_description: str,
        target_user: str,
        language: str = "persian",
        additional_notes: Optional[str] = None
    ) -> str:
        """Start AI dictionary generation job"""
        ...

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status and progress"""
        ...

class IDatabaseService(Protocol):
    """Interface for database operations"""

    async def execute_query(
        self,
        snapshot_id: int,
        sql_query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute SQL query against snapshot"""
        ...

class ILLMService(Protocol):
    """Interface for LLM operations"""

    async def generate_text(
        self,
        model_id: int,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text using specified LLM"""
        ...
```

### 3. Infrastructure Layer (لایه زیرساخت)

لایه پیاده‌سازی external concerns:

#### Repository Implementations:
```python
# Infrastructure layer - Repository implementations
class DatabaseConnectionRepository:
    """Concrete repository implementation"""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def get_by_id(self, connection_id: int) -> Optional[DatabaseConnection]:
        async with self.session_factory() as session:
            # Implementation using SQLAlchemy
            result = await session.execute(
                select(DatabaseConnectionORM).where(
                    DatabaseConnectionORM.id == connection_id
                )
            )
            orm_obj = result.scalar_one_or_none()
            return orm_obj.to_domain() if orm_obj else None

    async def create(self, connection: DatabaseConnection) -> DatabaseConnection:
        async with self.session_factory() as session:
            orm_obj = DatabaseConnectionORM.from_domain(connection)
            session.add(orm_obj)
            await session.commit()
            await session.refresh(orm_obj)
            return orm_obj.to_domain()
```

#### External Service Implementations:
```python
# src/infrastructure/external/llm_service_impl.py
from ...application.interfaces.service_interfaces import ILLMService
from ...domain.value_objects.llm_prompt import LLMPrompt

class LLMServiceImpl(ILLMService):
    """Concrete implementation of LLM service using infrastructure"""

    def __init__(self, llm_connector):
        self.llm_connector = llm_connector

    async def generate_text(
        self,
        model_id: int,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text using LLM infrastructure"""
        try:
            request = LLMRequest(
                model_id=str(model_id),
                messages=[Message(role=MessageRole.USER, content=prompt)],
                temperature=temperature,
                max_tokens=max_tokens
            )

            response = await self.llm_connector.generate(request)
            return response.text

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise LLMServiceError(f"Failed to generate text: {e}")
```

#### Configuration & Dependency Injection:
```python
# src/infrastructure/config/dependencies.py
from dependency_injector import containers, providers
from ..external.llm_service_impl import LLMServiceImpl
from ..repositories.database_connection_repository import DatabaseConnectionRepository

class Container(containers.DeclarativeContainer):
    """Dependency injection container"""

    # Infrastructure providers
    session_factory = providers.Singleton(get_session_factory)

    # Repository providers
    database_connection_repository = providers.Factory(
        DatabaseConnectionRepository,
        session_factory=session_factory
    )

    # Service providers
    llm_service = providers.Factory(
        LLMServiceImpl,
        llm_connector=get_llm_connector()
    )

    # Application layer wiring
    generate_ai_dictionary_handler = providers.Factory(
        GenerateAIDictionaryHandler,
        ai_dictionary_service=llm_service
    )
```

### 4. Presentation Layer (لایه ارائه)

لایه رابط کاربری و API endpoints:

#### API Controllers:
```python
# src/presentation/api/v1/api.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ...application.commands.generate_ai_dictionary_command import GenerateAIDictionaryCommand
from ...application.handlers.generate_ai_dictionary_handler import GenerateAIDictionaryHandler
from ...infrastructure.config.dependencies import Container

router = APIRouter()
container = Container()

class GenerateAIDictionaryRequest(BaseModel):
    snapshot_id: int
    business_domain: str
    database_description: str
    target_user: str
    language: Optional[str] = "persian"
    additional_notes: Optional[str] = None

@router.post("/ai-dictionary/generate")
async def generate_ai_dictionary(
    request: GenerateAIDictionaryRequest,
    handler: GenerateAIDictionaryHandler = Depends(container.generate_ai_dictionary_handler)
):
    """Generate AI dictionary for database schema"""
    try:
        command = GenerateAIDictionaryCommand(**request.dict())
        job_id = await handler.handle(command)

        return {
            "success": True,
            "message": "AI dictionary generation started",
            "job_id": job_id
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
```

#### DTOs (Data Transfer Objects):
```python
# src/presentation/api/v1/models.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class DatabaseConnectionDTO(BaseModel):
    """Data Transfer Object for API responses"""

    id: int
    db_type: str
    host: str
    port: int
    username: str
    database_name: str
    is_active: bool

    @classmethod
    def from_domain(cls, domain_obj: DatabaseConnection) -> 'DatabaseConnectionDTO':
        """Convert domain object to DTO"""
        return cls(
            id=domain_obj.id,
            db_type=domain_obj.db_type,
            host=domain_obj.host,
            port=domain_obj.port,
            username=domain_obj.username,
            database_name=domain_obj.database_name,
            is_active=domain_obj.is_active
        )

class APIResponse(BaseModel):
    """Standard API response format"""

    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
```

## جریان کنترل (Control Flow)

### درخواست از Presentation به Domain:

```
1. HTTP Request → Presentation Layer (API Controller)
   ↓
2. Request Validation & DTO Conversion
   ↓
3. Create Command/Query Object
   ↓
4. Inject Handler/Service from DI Container
   ↓
5. Application Layer (Handler/Service)
   ├─ Business Validation
   ├─ Domain Logic Execution
   └─ Coordinate with Domain Entities
   ↓
6. Infrastructure Layer (Repository/Service Implementation)
   ├─ Database Operations
   ├─ External API Calls
   └─ File System Operations
   ↓
7. Return Result through Layers
   ├─ Domain Objects → DTOs
   ├─ Error Handling
   └─ Response Formatting
   ↓
8. HTTP Response
```

### مثال کامل:
```python
# 1. API Endpoint (Presentation)
@router.post("/database/connections")
async def create_connection(request: CreateConnectionRequest):
    command = CreateDatabaseConnectionCommand(**request.dict())
    handler = container.create_connection_handler()
    connection_id = await handler.handle(command)
    return {"connection_id": connection_id}

# 2. Command Handler (Application)
class CreateDatabaseConnectionHandler:
    def __init__(self, repository: IDatabaseConnectionRepository):
        self.repository = repository

    async def handle(self, command: CreateDatabaseConnectionCommand) -> int:
        # Validate business rules
        connection = DatabaseConnection(**command.dict())
        connection.validate()

        # Persist using repository
        return await self.repository.create(connection)

# 3. Repository (Infrastructure)
class DatabaseConnectionRepository(IDatabaseConnectionRepository):
    async def create(self, connection: DatabaseConnection) -> int:
        # Convert to ORM and persist
        orm_obj = DatabaseConnectionORM.from_domain(connection)
        session.add(orm_obj)
        await session.commit()
        return orm_obj.id
```

## مزایای معماری (Architecture Benefits)

### 1. **Testability**
- هر لایه به طور مستقل قابل تست است
- Mocking ساده با dependency injection
- Unit tests برای business logic

### 2. **Maintainability**
- تغییرات در infrastructure بر domain تأثیر نمی‌گذارد
- Clear separation of concerns
- Easy to understand and modify

### 3. **Flexibility**
- امکان تغییر frameworkها (FastAPI → Django)
- Database migration بدون تغییر business logic
- External service replacement

### 4. **Scalability**
- Horizontal scaling در لایه‌های مختلف
- Microservices-ready architecture
- Clear boundaries برای team organization

## Dependency Injection & IoC

### Container Configuration:
```python
class Container(containers.DeclarativeContainer):
    """IoC Container for dependency management"""

    # Data layer
    session_factory = providers.Singleton(get_database_session)

    # Repository layer
    user_repository = providers.Factory(
        UserRepository,
        session_factory=session_factory
    )

    # Domain services
    user_service = providers.Factory(
        UserService,
        user_repository=user_repository
    )

    # Application services
    create_user_handler = providers.Factory(
        CreateUserHandler,
        user_service=user_service
    )

    # Presentation adapters
    user_controller = providers.Factory(
        UserController,
        create_user_handler=create_user_handler
    )
```

## Validation & Error Handling

### Domain Validation:
```python
class DatabaseConnection(BaseEntity):
    # ... fields ...

    def validate(self) -> None:
        """Domain validation rules"""
        if not self.host or not self.host.strip():
            raise DomainValidationError("Host is required")

        if not (1 <= self.port <= 65535):
            raise DomainValidationError("Port must be between 1 and 65535")

        # Business rules
        if self.db_type not in ["postgresql", "mysql", "sqlserver"]:
            raise DomainValidationError("Unsupported database type")
```

### Application Error Handling:
```python
class ApplicationError(Exception):
    """Base class for application errors"""
    pass

class ValidationError(ApplicationError):
    """Validation failed"""
    pass

class NotFoundError(ApplicationError):
    """Resource not found"""
    pass
```

## Migration Strategy

### از Traditional Architecture به Clean Architecture:

1. **شناسایی Domain Entities**
   - استخراج business objects
   - تعریف value objects
   - تعیین domain services

2. **ایجاد Application Layer**
   - تعریف use cases
   - ایجاد command/query objects
   - پیاده‌سازی handlers

3. **انتزاع Infrastructure**
   - تعریف repository interfaces
   - ایجاد service abstractions
   - پیاده‌سازی dependency injection

4. **توسعه Presentation Layer**
   - ایجاد API controllers
   - تعریف DTOs
   - تنظیم routing

## Testing Strategy

### Unit Tests:
```python
def test_database_connection_validation():
    """Test domain validation"""
    connection = DatabaseConnection(
        db_type="invalid",
        host="",
        port=99999,
        # ...
    )

    with pytest.raises(DomainValidationError):
        connection.validate()
```

### Integration Tests:
```python
async def test_create_connection_integration():
    """Test full flow integration"""
    # Arrange
    command = CreateDatabaseConnectionCommand(...)

    # Act
    handler = CreateDatabaseConnectionHandler(repository)
    connection_id = await handler.handle(command)

    # Assert
    connection = await repository.get_by_id(connection_id)
    assert connection.db_type == command.db_type
```

### End-to-End Tests:
```python
def test_create_connection_api(client):
    """Test API endpoint"""
    response = client.post("/api/connections", json={...})
    assert response.status_code == 201
    assert "connection_id" in response.json()
```

## چالش‌ها و بهترین روش‌ها (Challenges & Best Practices)

### چالش‌ها:
1. **Learning Curve**: پیچیدگی درک معماری
2. **Over-engineering**: اضافه کردن abstraction غیرضروری
3. **Performance Overhead**: لایه‌های اضافی
4. **Testing Complexity**: تست وابستگی‌های پیچیده

### بهترین روش‌ها:
1. **Start Small**: از domain entities شروع کنید
2. **YAGNI Principle**: فقط abstractionهای لازم را اضافه کنید
3. **TDD Approach**: تست‌ها را قبل از implementation بنویسید
4. **Refactoring**: تدریجی مهاجرت به معماری clean

## نتیجه‌گیری (Conclusion)

معماری Clean Architecture با DDD یک foundation قوی برای توسعه نرم‌افزار enterprise فراهم می‌کند که:

- **قابل نگهداری**: تغییرات ایزوله و predictable
- **قابل تست**: هر component به طور مستقل testable
- **قابل توسعه**: افزودن features جدید ساده
- **Technology Agnostic**: مستقل از technology stack

این معماری تضمین می‌کند که business logic در مرکز توجه قرار دارد و تغییرات technology بر core business تأثیر نمی‌گذارد.

---

**پیاده‌سازی Clean Architecture در SQL PT یک رویکرد strategic برای اطمینان از کیفیت کد، قابلیت نگهداری و scalability سیستم است.**









