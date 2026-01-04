# SQL PT Project Architecture Rules

**Last Updated**: 2024
**Purpose**: Stabilize backend architecture, prevent structural entropy, eliminate duplication, ensure SQL Server compatibility, and maintain modular design.

---

## 🎯 Core Principles

1. **Backend-First Priority**: Backend stability, database access, query accuracy, queue system, and WebSocket infrastructure take absolute priority.
2. **No Runtime Behavior Changes**: Refactoring must preserve existing functionality.
3. **Prevent Structural Entropy**: No file sprawl, duplicated abstractions, broken imports, or inconsistent naming.
4. **Eliminate Repetition**: New features must extend existing modules, never duplicate them.
5. **SQL Server Compatibility**: All SQL logic must remain SQL Server compatible.
6. **Valid JSON Responses**: LLM responses must always be valid JSON to avoid parsing crashes.
7. **Unified Prompt Building**: All prompt building must go through `backend/chat/engine/prompt_engine.py` to prevent duplication.
8. **Sample Data from Dictionary**: Always use 3-5 unique sampled rows already stored in data dictionary. Do NOT sample again.
9. **src/ Directory**: `src/` is a clean orchestration layer only. It defines use case flows and contracts but must call `backend/` modules for execution.

---

## 📁 Project Structure

### Directory Organization

```
backend/
├── api/              # FastAPI routers (endpoints only, no business logic)
├── services/         # Business logic services (queue workers, generators)
├── db/               # Database connectors and models
├── llm/              # LLM connectors and providers
├── core/             # Core utilities, prompts, app factory
├── chat/             # Chat engine and SQL pipeline
├── config/           # Configuration and logging
└── scripts/          # Maintenance and migration scripts
```

### Module Placement Rules

| Component Type | Location | Example |
|----------------|----------|---------|
| API Endpoints | `backend/api/` | `ai_dictionary.py`, `use_case_job_router.py` |
| Business Logic | `backend/services/` | `ai_dictionary_generator.py`, `use_case_generator.py` |
| Database Access | `backend/db/` | `connector.py`, `models.py` |
| LLM Access | `backend/llm/` | `connector.py`, `providers/` |
| Core Utilities | `backend/core/` | `db_utils.py`, `prompts/` |
| Chat Logic | `backend/chat/` | `engine/`, `router.py` |

---

## 🎨 Unified Prompt Building

### Mandatory: Use `PromptEngine` for All Prompts

**Location**: `backend/chat/engine/prompt_engine.py`

**Class**: `PromptEngine`

**Unified Methods**:
- `build_use_case_generation_prompt()` - For use case generation
- `build_relationship_suggestion_prompt()` - For relationship suggestions
- `build_sql_generation_prompt_with_sample_data()` - For SQL generation with sample data

**Usage Pattern**:
```python
from chat.engine.prompt_engine import PromptEngine

prompt_engine = PromptEngine()

# For use case generation
prompt = prompt_engine.build_use_case_generation_prompt(
    request, minified_schema, data_dictionary, relationships,
    sample_data, language, database_type, table_row_counts
)

# For relationship suggestions
prompt = prompt_engine.build_relationship_suggestion_prompt(
    schema_data, data_dict, tables_with_samples,
    intermediary_tables, business_context
)

# For SQL generation (with sample data from dictionary)
prompt = prompt_engine.build_sql_generation_prompt_with_sample_data(
    context, question, intent, tables_info, language, query_plan
)
```

**Rules**:
- ✅ **ALWAYS** use `PromptEngine` methods for prompt building
- ✅ Sample data must come from dictionary `example_values` (3-5 rows)
- ✅ Do NOT sample again - use existing dictionary data
- ✅ All prompts must respect SQL Server dialect if detected
- ❌ **NEVER** create new prompt building functions outside `PromptEngine`
- ❌ **NEVER** duplicate prompt building logic
- ❌ **NEVER** sample data again if dictionary already has it

**Sample Data Rules**:
- Use `example_values` from `DataDictionary` model
- Extract 3-5 unique rows from dictionary
- Do NOT call `DatabaseConnector.sample_rows()` if dictionary has data
- Format sample data as JSON in prompts

---

## 🔌 Database Connector Usage

### Mandatory: Use `DatabaseConnector`

**Location**: `backend/db/connector.py`

**Class**: `DatabaseConnector`

**Usage Pattern**:
```python
from db.connector import DatabaseConnector
from db.models import Snapshot, DatabaseConnection

# Create connector
connector = DatabaseConnector(snapshot, db_conn)
await connector.connect()

# Execute queries
results = await connector.execute_readonly(sql, limit=1000)

# Always disconnect
await connector.disconnect()
```

**Rules**:
- ✅ **ALWAYS** use `DatabaseConnector` for all database operations
- ✅ Use `execute_readonly()` for all queries (enforces security validation)
- ✅ Always call `disconnect()` when done
- ❌ **NEVER** create new database connector classes
- ❌ **NEVER** use direct SQLAlchemy sessions outside `DatabaseConnector`
- ❌ **NEVER** bypass security validation

**Helper Function**:
```python
from services.db_connector_utils import create_db_connector_for_snapshot
connector = await create_db_connector_for_snapshot(session, snapshot_id)
```

---

## 🤖 LLM Connector Usage

### Mandatory: Use `ModelConnector`

**Location**: `backend/llm/connector.py`

**Class**: `ModelConnector`

**Usage Pattern**:
```python
from llm import ModelConnector, LLMRequest, Message, MessageRole

# Initialize connector
connector = ModelConnector()
await connector.initialize()

# Generate response
request = LLMRequest(
    model_id="gpt-4",
    messages=[Message(role=MessageRole.USER, content="Hello!")]
)
response = await connector.generate(request)
```

**Rules**:
- ✅ **ALWAYS** use `ModelConnector` for all LLM operations
- ✅ Initialize connector before first use
- ✅ Use `LLMRequest` and `LLMResponse` schemas
- ❌ **NEVER** create direct provider instances
- ❌ **NEVER** bypass the connector layer
- ❌ **NEVER** hardcode API endpoints or keys

**Service Layer**:
For services, use `LLMService` wrapper:
```python
from services.llm_service import LLMService
llm_service = LLMService()
response = await llm_service.generate(...)
```

---

## 📊 SQL Generation Standards

### SQL Server Compatibility (MANDATORY)

All SQL queries must be **SQL Server compatible**. Default to SQL Server syntax unless explicitly targeting another database.

#### Critical Rules:

1. **TOP vs LIMIT**:
   - ✅ Use `TOP N` for SQL Server
   - ❌ Never use `LIMIT` for SQL Server
   - ✅ Use `LIMIT` only for PostgreSQL/MySQL

2. **Unicode Strings**:
   - ✅ **ALWAYS** use `N'...'` prefix for non-ASCII strings (Persian, Arabic, etc.)
   - ✅ Use `N'...'` when in doubt (works for both ASCII and Unicode)
   - ❌ Never use plain `'...'` for non-ASCII text

3. **Date Column Handling**:
   - ✅ **CHECK SAMPLE DATA FIRST** to determine if date column is STRING or DATE type
   - ✅ For STRING date columns: Use `LIKE N'YYYY%'` or `SUBSTRING()` instead of `YEAR()`, `MONTH()`, `DAY()`
   - ✅ For DATE type columns: Use `YEAR()`, `MONTH()`, `DAY()`, `DATEPART()`
   - ❌ Never use date functions (`YEAR`, `MONTH`, `DAY`, `DATEPART`, `DATEADD`, `DATEDIFF`) on string columns
   - ❌ Never use `CAST`/`CONVERT` on string dates unless format is guaranteed

4. **Identifier Quoting**:
   - ✅ Use square brackets `[TableName]`, `[ColumnName]` when needed
   - ✅ Use brackets for reserved words or special characters

5. **SQL Server Functions**:
   - ✅ Use: `ISNULL()`, `COALESCE()`, `CAST()`, `CONVERT()`, `GETDATE()`, `DATEADD()`, `DATEDIFF()`
   - ✅ Use: `LEN()`, `SUBSTRING()`, `CHARINDEX()`, `REPLACE()`
   - ❌ Avoid: PostgreSQL/MySQL-specific functions (`EXTRACT`, `TO_CHAR`, `NOW()`)

6. **Query Validation Checklist**:
   - [ ] Checked SAMPLE DATA for date column types?
   - [ ] Used `N'...'` prefix for all non-ASCII strings?
   - [ ] Used `TOP` instead of `LIMIT` for SQL Server?
   - [ ] Avoided date functions on string columns?
   - [ ] Used proper identifier quoting?
   - [ ] All table/column names from actual schema?

#### SQL Generation Prompt Requirements:

When generating SQL via LLM, prompts MUST include:
- Database type specification
- SQL Server compatibility rules
- Sample data context
- Date column type detection instructions
- Unicode string handling rules

**Example Prompt Pattern**:
```python
sql_server_instructions = """
SQL SERVER COMPATIBILITY REQUIREMENTS:
- Use TOP instead of LIMIT
- Use N'...' prefix for Unicode strings (non-ASCII)
- Check SAMPLE DATA to determine date column type (STRING vs DATE)
- For STRING dates: Use LIKE/SUBSTRING, not YEAR/MONTH/DAY
- Use square brackets [ ] for identifiers
- Use SQL Server functions: ISNULL, COALESCE, GETDATE(), etc.
"""
```

---

## 🔄 Queue System Architecture

### Queue Pattern (MANDATORY)

**Location**: `backend/services/ai_dictionary_generator.py` (reference implementation)

**Components**:
1. **Queue**: `asyncio.Queue()` for task distribution
2. **Workers**: 3 async worker tasks (`_process_queue_worker`)
3. **Job Management**: In-memory `_jobs` dict + database persistence
4. **Status Tracking**: Enum-based status (`WAITING`, `PROCESSING`, `DONE`, `FAILED`, `CANCELED`)

**Rules**:
- ✅ Use `asyncio.Queue()` for task queues
- ✅ Use worker tasks (3 workers default) for parallel processing
- ✅ Persist job state to database (`AIGenerationJob` model)
- ✅ Isolate errors per task (one failure doesn't crash queue)
- ✅ Use `asyncio.Event()` for graceful shutdown
- ❌ **NEVER** rewrite queue architecture, only improve reliability
- ❌ **NEVER** use blocking operations in workers
- ❌ **NEVER** process tasks synchronously

**Worker Pattern**:
```python
async def _process_queue_worker(self, worker_id: int) -> None:
    while not self._shutdown_event.is_set():
        try:
            job_id, task_key = await asyncio.wait_for(
                self._queue.get(), timeout=1.0
            )
            # Process task with error isolation
            await self._process_task(job_id, task_key)
            self._queue.task_done()
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}")
            # Continue processing, don't crash
```

---

## 🌐 WebSocket Architecture

### WebSocket Pattern (MANDATORY)

**Location**: `backend/api/dictionary_job_router.py`, `backend/api/use_case_job_router.py`

**Components**:
1. **ConnectionManager**: Manages WebSocket connections per job
2. **WebSocket Endpoint**: `/ws/{job-type}-status/{job_id}`
3. **Broadcast Updates**: Real-time status updates to connected clients

**Rules**:
- ✅ Use `ConnectionManager` pattern for managing connections
- ✅ WebSocket endpoints follow pattern: `/ws/{resource}-status/{id}`
- ✅ Send initial status on connection
- ✅ Broadcast updates on status changes
- ✅ Handle ping/pong for keepalive
- ✅ Use `asyncio.wait_for()` with timeout for message handling
- ❌ **NEVER** block WebSocket handlers
- ❌ **NEVER** send non-JSON messages

**ConnectionManager Pattern**:
```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)
    
    async def broadcast(self, job_id: str, message: dict):
        if job_id in self.active_connections:
            for ws in self.active_connections[job_id]:
                await ws.send_json(message)
```

**WebSocket Endpoint Pattern**:
```python
@router.websocket("/ws/{resource}-status/{job_id}")
async def websocket_status(websocket: WebSocket, job_id: str):
    await manager.connect(job_id, websocket)
    try:
        # Send initial status
        status = await service.get_job_status(job_id)
        await websocket.send_json({"type": "job_status_update", ...})
        
        # Keep connection alive
        while True:
            data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(job_id, websocket)
```

---

## 📦 Import Policy

### Import Rules (MANDATORY)

1. **Relative Imports**:
   - ✅ Use relative imports within same package: `from .module import Class`
   - ✅ Use explicit imports: `from db.connector import DatabaseConnector`
   - ❌ **NEVER** use `sys.path.append()` or `sys.path.insert()`
   - ❌ **NEVER** modify Python path at runtime

2. **Import Order**:
   ```python
   # Standard library
   import asyncio
   import logging
   from typing import Dict, List, Optional
   
   # Third-party
   from fastapi import APIRouter, Depends
   from sqlalchemy.ext.asyncio import AsyncSession
   
   # Local imports
   from db.connector import DatabaseConnector
   from services.llm_service import LLMService
   from api.database import get_db_session
   ```

3. **Circular Import Prevention**:
   - ✅ Import services locally inside functions when needed
   - ✅ Use dependency injection (`Depends()`) for FastAPI
   - ❌ **NEVER** create circular dependencies

**Example (Avoiding Circular Imports)**:
```python
# In router file
@router.post("/generate")
async def generate(request: Request, session: AsyncSession = Depends(get_db_session)):
    # Import service locally to avoid circular imports
    from services.ai_dictionary_generator import ai_dictionary_generator
    job_id = await ai_dictionary_generator.create_job(...)
```

---

## 🏷️ Naming Conventions

### File Naming

- ✅ Use `snake_case` for all Python files: `ai_dictionary.py`, `use_case_generator.py`
- ✅ Use `snake_case` for directories: `api/`, `services/`, `db/`
- ❌ Never use `camelCase` or `PascalCase` for files

### Class Naming

- ✅ Use `PascalCase` for classes: `DatabaseConnector`, `AIDictionaryGenerator`
- ✅ Use descriptive names: `ConnectionManager`, `SQLValidator`

### Variable/Function Naming

- ✅ Use `snake_case` for variables and functions: `job_id`, `get_job_status()`
- ✅ Use descriptive names: `table_tasks`, `process_queue_worker()`

### Constants

- ✅ Use `UPPER_SNAKE_CASE` for constants: `MAX_WORKERS`, `DEFAULT_LIMIT`

---

## 🚫 Anti-Duplication Rules

### Module Extension Policy

**Before creating a new file/module, verify**:

1. ✅ Does a similar module already exist?
   - Check `backend/services/` for business logic
   - Check `backend/api/` for endpoints
   - Check `backend/db/` for database access
   - Check `backend/llm/` for LLM access

2. ✅ Can existing module be extended?
   - Add new methods to existing classes
   - Add new endpoints to existing routers
   - Extend existing services with new functionality

3. ✅ Is the new file justified?
   - New file must serve a distinct purpose
   - Must not duplicate existing functionality
   - Must follow module placement rules

**Examples of Duplication to Avoid**:
- ❌ Creating `new_database_connector.py` when `db/connector.py` exists
- ❌ Creating `llm_wrapper.py` when `llm/connector.py` exists
- ❌ Creating `queue_manager.py` when queue logic exists in services
- ❌ Creating duplicate router files for similar endpoints

**Correct Approach**:
- ✅ Extend `DatabaseConnector` with new methods
- ✅ Add new endpoints to existing routers
- ✅ Extend `ModelConnector` with new capabilities
- ✅ Add new worker methods to existing services

---

## 🔧 Service Layer Rules

### Service Architecture

**Location**: `backend/services/`

**Pattern**:
- Services are singleton instances (or class-based with shared state)
- Services manage async queues, workers, and job state
- Services expose public methods for API routers
- Services handle database persistence

**Service Initialization**:
```python
# In service file
class AIDictionaryGenerator:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
    
    async def initialize(self) -> None:
        # Initialize workers, load from DB, etc.
        pass
    
    async def shutdown(self) -> None:
        # Graceful shutdown
        pass

# Singleton instance
ai_dictionary_generator = AIDictionaryGenerator()
```

**Service Usage in Routers**:
```python
from services.ai_dictionary_generator import ai_dictionary_generator

@router.post("/generate")
async def generate(...):
    job_id = await ai_dictionary_generator.create_job(...)
    background_tasks.add_task(ai_dictionary_generator.start_job, job_id)
```

**Rules**:
- ✅ Services are initialized in `core/app.py` lifespan
- ✅ Services are shut down gracefully on app shutdown
- ✅ Services persist state to database
- ✅ Services handle errors gracefully (don't crash workers)
- ❌ **NEVER** create services without initialization/shutdown
- ❌ **NEVER** use services without proper async handling

---

## 📝 API Router Rules

### Router Organization

**Location**: `backend/api/`

**Pattern**:
- Routers contain **only** endpoint definitions
- Business logic goes in `services/`
- Routers use dependency injection for database sessions
- Routers use background tasks for async jobs

**Router Structure**:
```python
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

router = APIRouter(tags=["resource-name"])

# Pydantic models
class RequestModel(BaseModel):
    field: str

# Endpoints
@router.post("/action")
async def action(
    request: RequestModel,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session)
):
    # Import service locally to avoid circular imports
    from services.service_name import service_instance
    
    # Validate, create job, start background task
    job_id = await service_instance.create_job(...)
    background_tasks.add_task(service_instance.start_job, job_id)
    
    return {"job_id": job_id}
```

**Rules**:
- ✅ Keep routers thin (endpoints only)
- ✅ Use Pydantic models for request/response validation
- ✅ Use `Depends(get_db_session)` for database sessions
- ✅ Use `BackgroundTasks` for async job processing
- ✅ Import services locally to avoid circular imports
- ❌ **NEVER** put business logic in routers
- ❌ **NEVER** create direct database connections in routers
- ❌ **NEVER** block endpoints with long-running operations

---

## 🗄️ Database Models

### Model Location

**Location**: `backend/api/db_models.py`

**Rules**:
- ✅ All SQLAlchemy models in single file (`db_models.py`)
- ✅ Use async SQLAlchemy (`AsyncSession`)
- ✅ Use proper relationships and foreign keys
- ✅ Include timestamps (`created_at`, `updated_at`)
- ❌ **NEVER** create duplicate model files
- ❌ **NEVER** use sync SQLAlchemy sessions

**Model Pattern**:
```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class ModelName(Base):
    __tablename__ = "table_name"
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

## 🎨 Use Case Generation Standards

### Use Case Quality Requirements

**Location**: `backend/services/use_case_generator.py`, `backend/services/ai_dictionary_generator.py`

**Rules**:
- ✅ Use sample data + dictionary + relations to generate **business-meaningful** use cases
- ✅ Use cases must be **practical** and **actionable**
- ✅ Use cases must reference actual tables/columns from schema
- ✅ Use cases must include realistic business scenarios
- ❌ **NEVER** generate generic or abstract use cases
- ❌ **NEVER** generate use cases without schema context

**Prompt Requirements**:
- Include minified schema
- Include data dictionary
- Include relationships
- Include sample data (3-5 rows per table)
- Include business domain context
- Specify SQL Server compatibility

---

## 🔐 Security Rules

### SQL Security

**Location**: `backend/db/security.py`

**Rules**:
- ✅ **ALWAYS** validate SQL queries via `validate_sql()` before execution
- ✅ Use `execute_readonly()` which enforces security validation
- ✅ Only allow SELECT queries (no INSERT, UPDATE, DELETE, DROP, etc.)
- ❌ **NEVER** execute raw SQL without validation
- ❌ **NEVER** allow user-provided SQL to execute directly

### Password Encryption

**Location**: `backend/db/security.py`

**Rules**:
- ✅ Use `encrypt_password()` and `decrypt_password()` for database passwords
- ✅ Store encrypted passwords in database
- ❌ **NEVER** store plaintext passwords
- ❌ **NEVER** log passwords

---

## 📋 LLM Response Validation

### JSON Response Requirements

**Rules**:
- ✅ **ALWAYS** ensure LLM responses are valid JSON
- ✅ Parse JSON with error handling
- ✅ Validate JSON structure before processing
- ✅ Use structured prompts that enforce JSON output
- ❌ **NEVER** assume LLM responses are valid JSON
- ❌ **NEVER** parse JSON without try/except

**JSON Parsing Pattern**:
```python
import json

try:
    response_text = await llm_service.generate(...)
    # Extract JSON from response (may have markdown code blocks)
    json_text = extract_json_from_response(response_text)
    data = json.loads(json_text)
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON response: {e}")
    # Retry or return error
except Exception as e:
    logger.error(f"LLM generation error: {e}")
    # Handle error
```

---

## 🧪 Testing Standards

### Test Organization

**Location**: `backend/tests/`

**Rules**:
- ✅ Tests should be in `backend/tests/` directory
- ✅ Use descriptive test names: `test_ai_dictionary_generation.py`
- ✅ Mock external dependencies (database, LLM)
- ✅ Test error cases, not just happy paths
- ❌ **NEVER** create test files in production code directories
- ❌ **NEVER** use real database connections in unit tests

---

## 🚀 Deployment Rules

### Startup Sequence

**Location**: `backend/core/app.py`

**Lifespan Pattern**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_tables()
    await service_instance.initialize()
    
    yield
    
    # Shutdown
    await service_instance.shutdown()
    await container.shutdown()
```

**Rules**:
- ✅ Initialize all services in lifespan startup
- ✅ Shutdown all services gracefully in lifespan shutdown
- ✅ Run database migrations in lifespan startup
- ✅ Handle initialization errors gracefully (log, don't crash)
- ❌ **NEVER** skip service initialization
- ❌ **NEVER** leave resources open on shutdown

---

## 📚 Documentation Requirements

### Code Documentation

**Rules**:
- ✅ Document all public methods with docstrings
- ✅ Document complex logic with inline comments
- ✅ Document SQL generation rules in prompts
- ✅ Document error handling strategies
- ❌ **NEVER** leave undocumented complex logic

**Docstring Pattern**:
```python
async def method_name(self, param: str) -> Dict[str, Any]:
    """
    Brief description of what the method does.
    
    Args:
        param: Description of parameter
    
    Returns:
        Description of return value
    
    Raises:
        ExceptionType: When this exception is raised
    """
```

---

## ✅ Success Criteria

A refactor is considered successful if:

- ✅ Project runs without crash
- ✅ No import errors exist
- ✅ No duplicated modules exist
- ✅ SQL generation accuracy improves
- ✅ Backend remains fully stable and modular
- ✅ All connectors (DB, LLM) are used correctly
- ✅ Queue system works reliably
- ✅ WebSocket updates stream properly
- ✅ All SQL queries are SQL Server compatible
- ✅ LLM responses are valid JSON

---

## 🔄 Before Implementing New Features

**Mandatory Checklist**:

1. ✅ Read `cursorrules.md` (this file)
2. ✅ Check if similar functionality exists
3. ✅ Verify module placement (api/, services/, db/, llm/)
4. ✅ Use existing connectors (DatabaseConnector, ModelConnector)
5. ✅ Follow naming conventions
6. ✅ Ensure SQL Server compatibility
7. ✅ Validate JSON responses
8. ✅ Test error handling
9. ✅ Document public methods
10. ✅ Update this file if new patterns emerge

---

## 📞 Reference Implementations

**Study these files as examples**:

- **Database Connector**: `backend/db/connector.py`
- **LLM Connector**: `backend/llm/connector.py`
- **Queue System**: `backend/services/ai_dictionary_generator.py`
- **WebSocket**: `backend/api/dictionary_job_router.py`
- **SQL Generation**: `backend/services/maturation_engine.py` (lines 788-1169)
- **Service Pattern**: `backend/services/use_case_generator.py`
- **Router Pattern**: `backend/api/use_case_job_router.py`
- **App Factory**: `backend/core/app.py`

---

## 🔄 Integration Between `backend/` and `src/` (Clean Architecture)

### Architecture Integration Rules

**Location**: `src/` directory implements Clean Architecture patterns

**Rules**:
- ✅ `src/domain/` - **ONLY** entity definitions and data models, **NO** DB or LLM logic
- ✅ `src/application/` - Use case orchestration that **MUST** call `backend/services/` for execution
- ✅ `src/infrastructure/connectors/` - Interface definitions only, actual implementation uses `backend/db/` and `backend/llm/`
- ✅ `src/presentation/` - API controllers that delegate to application layer
- ❌ **NEVER** implement DB or LLM logic in `src/domain/`
- ❌ **NEVER** duplicate connector implementations in `src/infrastructure/`
- ❌ **NEVER** bypass `backend/` services from `src/application/`

**Integration Pattern**:
```python
# src/application/handlers/generate_ai_dictionary_handler.py
class GenerateAIDictionaryHandler:
    async def handle(self, command):
        # Delegate to backend service
        from services.ai_dictionary_generator import ai_dictionary_generator
        job_id = await ai_dictionary_generator.create_job(...)
        return job_id
```

**Domain Layer Rules**:
- ✅ Entities in `src/domain/entities/` are pure data classes
- ✅ Value objects in `src/domain/value_objects/` contain validation logic only
- ❌ **NO** database queries in domain layer
- ❌ **NO** LLM calls in domain layer

**Application Layer Rules**:
- ✅ Use cases orchestrate business flow
- ✅ Must call `backend/services/` for actual execution
- ✅ Can compose multiple backend services
- ❌ **NO** direct database access
- ❌ **NO** direct LLM calls

**Infrastructure Layer Rules**:
- ✅ Define interfaces/contracts for connectors
- ✅ Implementation delegates to `backend/db/connector.py` and `backend/llm/connector.py`
- ❌ **NO** duplicate connector implementations

---

## 🎯 SQL Query Generation Optimization

### Enhanced Context Requirements

**For Chat Query Generator** (`backend/chat/engine/sql_pipeline.py`):

1. **Database Dialect Detection**:
   - ✅ Detect database type from `Snapshot` → `DatabaseConnection.db_type`
   - ✅ Use dialect-specific SQL generation (SQL Server: TOP, N'...', etc.)
   - ✅ Transform SQL functions based on database type

2. **Sample Data Integration**:
   - ✅ Include 3-5 unique, real sample rows per table in prompt
   - ✅ Use actual data values for WHERE clauses and filters
   - ✅ Base JOIN conditions on actual relationships from sample data
   - ❌ **NEVER** use generic `COUNT(*)` unless explicitly requested

3. **Business Context Analysis**:
   - ✅ Include data dictionary descriptions in prompt
   - ✅ Use relationship information for JOIN suggestions
   - ✅ Analyze business domain for query relevance

**Prompt Enhancement Pattern**:
```python
# In prompt_engine.py
def _build_sql_generation_prompt_v2(
    context, question, intent, tables_info, language
):
    # Include:
    # 1. Minified schema
    # 2. Data dictionary (minified)
    # 3. Relationships
    # 4. Sample data (3-5 rows per table)
    # 5. Database type and dialect rules
    # 6. Business context
```

---

## 🔗 Relationship Builder Optimization

### Enhanced Relationship Discovery

**For Relation Builder** (`backend/api/relationships.py`):

1. **Hidden Relationship Detection**:
   - ✅ Analyze schema similarity (field names, types, constraints)
   - ✅ Check value overlap from sampled DB rows
   - ✅ Use business descriptions from data dictionary
   - ✅ Identify semantic matches (e.g., "customer_id" matches "id" in customers)

2. **N:N Relationship Detection**:
   - ✅ Detect intermediary/bridge tables with 2+ foreign keys
   - ✅ Suggest N:N relationships only when intermediary table exists
   - ✅ Reference intermediary table in relationship definition

3. **Confidence Scoring**:
   - ✅ Calculate confidence (0.0-1.0) based on:
     * Schema match quality
     * Sample value correlation
     * Business context alignment
     * Dictionary description relevance
   - ✅ **DO NOT** assign high confidence without justification
   - ✅ If sample data shows no value overlap, confidence < 0.3

4. **Real Examples**:
   - ✅ Use actual values from sampled DB rows when available
   - ✅ Include matching values in relationship examples
   - ✅ Format: `{"matching_value": "...", "source_example": {...}, "target_example": {...}}`

---

## 📊 Use Case Generator Optimization

### Enhanced Business Context

**For Use Case Generator** (`backend/services/use_case_generator.py`):

1. **Business Goal Precision**:
   - ✅ Define exact business objective for each use case
   - ✅ Specify target audience and their needs
   - ✅ Include business context from domain knowledge

2. **SQL Requirements**:
   - ✅ Specify required SQL patterns (filtering, joining, aggregation)
   - ✅ Define expected output format
   - ✅ Include performance considerations

3. **Column Role Definition**:
   - ✅ Explain role of each column in business context
   - ✅ Provide real examples from sample data
   - ✅ Link columns to business metrics

4. **Sample Data Integration**:
   - ✅ Use 3-5 unique sample rows per table
   - ✅ Base use cases on actual data patterns
   - ✅ Include realistic business scenarios from sample data

**Prompt Enhancement**:
```python
# In build_use_case_generation_prompt()
# Include:
# 1. Minified schema
# 2. Minified data dictionary
# 3. Relationships (explicit + inferred)
# 4. Sample data (3-5 rows per table)
# 5. Business domain context
# 6. Database type and SQL dialect rules
# 7. Table row counts for context
```

---

## 🧹 Cleanup Rules

### File Cleanup Policy

**Files to Remove**:
- ❌ Test files in production directories: `*_test.py`, `*test*.py` (except in `backend/tests/`)
- ❌ Backup files: `*.backup`, `*_backup.*`, `*_old.*`
- ❌ Debug files: `*_debug.py`, `debug_*.py` (unless actively used)
- ❌ Temporary files: `*_temp.*`, `temp_*.py`

**Files to Keep**:
- ✅ All files in `backend/tests/` (test suite)
- ✅ All files in `backend/scripts/` (maintenance scripts)
- ✅ All production code files

**Cleanup Process**:
1. Identify files matching cleanup patterns
2. Verify file is not actively used
3. Remove file
4. Update imports if necessary

---

## 🔍 Circular Import Prevention

### Import Dependency Rules

**Circular Import Patterns to Avoid**:
- ❌ `api/` importing from `services/` at module level
- ❌ `services/` importing from `api/` at module level
- ❌ `core/` importing from `api/` or `services/` at module level

**Solution Pattern**:
```python
# ❌ BAD: Module-level import
from services.ai_dictionary_generator import ai_dictionary_generator

@router.post("/generate")
async def generate(...):
    job_id = await ai_dictionary_generator.create_job(...)

# ✅ GOOD: Local import inside function
@router.post("/generate")
async def generate(...):
    from services.ai_dictionary_generator import ai_dictionary_generator
    job_id = await ai_dictionary_generator.create_job(...)
```

**Dependency Flow** (allowed):
- `api/` → `services/` (via local imports)
- `services/` → `db/`, `llm/`, `core/`
- `core/` → `config/`
- `chat/` → `db/`, `llm/`, `core/`

**Dependency Flow** (forbidden):
- `api/` → `api/` (circular within same layer)
- `services/` → `api/` (reverse dependency)

---

## 📝 Sample Data Requirements

### Data Sampling Standards

**Rules**:
- ✅ Sample **3-5 unique rows** per table (not duplicates)
- ✅ Use `DatabaseConnector.execute_readonly()` for sampling
- ✅ Include all columns in sample (not just primary keys)
- ✅ Use actual data values (not placeholders)
- ✅ Compress/minify sample data before sending to LLM

**Sampling Pattern**:
```python
# Use DatabaseConnector
from services.db_connector_utils import create_db_connector_for_snapshot

connector = await create_db_connector_for_snapshot(session, snapshot_id)
sample_rows = await connector.sample_rows(table_name, limit=5)
```

**Minification**:
- Remove null columns from sample rows
- Truncate long text values (>100 chars)
- Keep only essential columns for context

---

## 🎨 Schema and Dictionary Minification

### Minification Requirements

**Before sending to LLM**:
- ✅ Minify schema: Remove unnecessary metadata, keep only table/column names, types, constraints
- ✅ Minify data dictionary: Keep only essential descriptions, remove verbose explanations
- ✅ Compress relationships: Keep only source/target tables and columns, remove verbose descriptions

**Minification Pattern**:
```python
def minify_schema(schema_data):
    return {
        table: {
            "columns": {col: {"type": type, "nullable": nullable}}
            for col, type, nullable in columns
        }
        for table, columns in schema_data.items()
    }
```

---

**Remember**: When in doubt, check existing implementations. Extend, don't duplicate.

