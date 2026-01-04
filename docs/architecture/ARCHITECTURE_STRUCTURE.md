# ساختار معماری پروژه SQL PT

**Last Updated**: 2024  
**Version**: 2.0 (Unified Architecture)

---

## 📐 ساختار کلی پروژه

```
sql_pt/
│
├── 📁 backend/                          # ⭐ EXECUTION OWNER - همه عملیات واقعی
│   │
│   ├── 📁 api/                          # FastAPI Routers (20+ فایل)
│   │   ├── ai_dictionary.py             # Dictionary generation API
│   │   ├── dictionary_job_router.py     # Job management + WebSocket
│   │   ├── use_case_job_router.py       # Use case jobs + WebSocket
│   │   ├── smart_use_case_builder.py    # Use case generation
│   │   ├── relationships.py             # Relationship management
│   │   ├── schema.py                    # Schema operations
│   │   ├── data_dictionary.py           # Dictionary CRUD
│   │   └── ... (13+ فایل دیگر)
│   │
│   ├── 📁 services/                    # Business Logic Layer (12 فایل)
│   │   ├── ai_dictionary_generator.py   # ⭐ Queue System (3 workers)
│   │   ├── use_case_generator.py        # Use case generation
│   │   ├── maturation_engine.py         # Use case maturation
│   │   ├── llm_service.py              # Unified LLM service
│   │   └── ... (8 فایل دیگر)
│   │
│   ├── 📁 chat/                         # Chat Engine & SQL Pipeline
│   │   ├── 📁 engine/                   # Core Engine Components
│   │   │   ├── chat_engine.py           # Main orchestrator
│   │   │   ├── prompt_engine.py         # ⭐ UNIFIED PROMPT BUILDING
│   │   │   ├── sql_pipeline.py          # SQL generation pipeline
│   │   │   ├── query_planner.py         # Query planning & entity extraction
│   │   │   ├── llm_gateway.py           # LLM gateway
│   │   │   └── context_loader.py        # Context loading
│   │   │
│   │   ├── 📁 utils/                     # Utilities
│   │   │   └── json_safety.py           # Safe JSON parsing
│   │   │
│   │   ├── router.py                    # Chat API router
│   │   ├── schemas.py                   # Pydantic models
│   │   └── sql_guard.py                 # SQL security
│   │
│   ├── 📁 db/                           # Database Layer
│   │   ├── connector.py                # ⭐ DatabaseConnector (استاندارد)
│   │   ├── security.py                 # SQL validation & encryption
│   │   ├── models.py                    # Database models
│   │   └── repositories.py             # Repository pattern
│   │
│   ├── 📁 llm/                          # LLM Layer
│   │   ├── connector.py                # ⭐ ModelConnector (استاندارد)
│   │   ├── registry.py                  # Model registry
│   │   └── providers/                  # LLM Providers
│   │       ├── openai.py
│   │       ├── ollama.py
│   │       ├── vllm.py
│   │       └── custom_http.py
│   │
│   ├── 📁 core/                         # Core Layer
│   │   ├── app.py                       # FastAPI app factory
│   │   ├── db_utils.py                  # Database utilities
│   │   └── prompts/                     # Legacy prompts (deprecated)
│   │
│   ├── 📁 config/                       # Configuration
│   ├── 📁 tests/                        # Tests (68 فایل)
│   └── 📁 scripts/                      # Maintenance scripts
│
├── 📁 src/                              # ⭐ ORCHESTRATION LAYER ONLY
│   ├── domain/                          # Domain entities (no DB/LLM logic)
│   ├── application/                     # Use case definitions
│   │   └── usecases/                    # Delegates to backend/services
│   ├── infrastructure/                  # Interface definitions
│   │   └── connectors/                  # Uses backend/db & backend/llm
│   └── presentation/                    # API controllers
│       └── api/                         # Uses backend/api
│
├── 📁 frontend/                         # Next.js Frontend
│   ├── app/                             # Next.js App Router
│   ├── components/                      # React Components
│   └── lib/                             # Utilities
│
└── 📄 cursorrules.md                    # ⭐ قوانین معماری (1077 خط)
```

---

## 🔄 جریان داده‌ها (Data Flow)

### 1. SQL Query Generation Flow

```
User Question
    ↓
┌─────────────────────────────────────┐
│ Chat API Router                     │
│ (backend/chat/router.py)            │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Chat Engine                         │
│ (backend/chat/engine/chat_engine.py)│
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Context Loader                      │
│ - Load schema                       │
│ - Load data dictionary              │
│ - Load relationships                 │
│ - Load use cases                    │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Prompt Engine                       │
│ (backend/chat/engine/prompt_engine.py)│
│ ⭐ UNIFIED PROMPT BUILDING          │
│ - Extract sample data from dict     │
│ - Build SQL generation prompt      │
│ - Include query plan                │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ LLM Gateway                         │
│ (backend/chat/engine/llm_gateway.py)│
│ → ModelConnector                    │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ SQL Pipeline                        │
│ - Validate SQL                      │
│ - Transform for SQL Server           │
│ - Execute via DatabaseConnector     │
└─────────────────────────────────────┘
    ↓
Results → User
```

### 2. Use Case Generation Flow

```
User Request
    ↓
┌─────────────────────────────────────┐
│ Smart Use Case Builder API          │
│ (backend/api/smart_use_case_builder.py)│
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Prompt Engine                       │
│ build_use_case_generation_prompt()   │
│ ⭐ UNIFIED PROMPT BUILDING           │
│ - Enrich sample data from dict       │
│ - Build use case prompt              │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ ModelConnector                      │
│ (backend/llm/connector.py)         │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Use Case Generator                 │
│ (backend/services/use_case_generator.py)│
│ - Parse LLM response                │
│ - Store use cases                   │
└─────────────────────────────────────┘
    ↓
Results → Database
```

### 3. Relationship Suggestion Flow

```
User Request
    ↓
┌─────────────────────────────────────┐
│ Relationships API                   │
│ (backend/api/relationships.py)      │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Prompt Engine                       │
│ build_relationship_suggestion_prompt()│
│ ⭐ UNIFIED PROMPT BUILDING           │
│ - Enrich sample data from dict       │
│ - Build relationship prompt          │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ ModelConnector                      │
│ (backend/llm/connector.py)         │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Relationship Parser                 │
│ - Parse JSON response               │
│ - Store relationships                │
└─────────────────────────────────────┘
    ↓
Results → Database
```

### 4. Dictionary Generation Flow (Queue System)

```
User Request
    ↓
┌─────────────────────────────────────┐
│ AI Dictionary API                   │
│ (backend/api/ai_dictionary.py)       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ AI Dictionary Generator             │
│ (backend/services/ai_dictionary_generator.py)│
│ ⭐ QUEUE SYSTEM (3 workers)         │
│ - Create job                        │
│ - Add tasks to queue                │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Worker 1, 2, 3                      │
│ (async workers)                     │
│ - Process table tasks               │
│ - Generate dictionary               │
│ - Broadcast WebSocket updates       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ DatabaseConnector                   │
│ (backend/db/connector.py)           │
│ - Sample rows (3-5 per table)       │
│ - Store in dictionary               │
└─────────────────────────────────────┘
    ↓
Results → Database + WebSocket
```

---

## 🏗️ معماری لایه‌ای (Layered Architecture)

```
┌─────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Frontend   │  │  API Routes  │  │  WebSocket   │   │
│  │   (Next.js)  │  │  (FastAPI)   │  │  (Real-time) │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Services   │  │ Chat Engine  │  │  Queue Sys   │   │
│  │  (Business)  │  │  (SQL Gen)   │  │  (Workers)   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE LAYER                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Database   │  │     LLM     │  │   Prompt     │   │
│  │  Connector   │  │  Connector  │  │   Engine     │   │
│  │  ⭐ Standard │  │ ⭐ Standard │  │ ⭐ Unified   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                      DOMAIN LAYER                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Entities   │  │  Value      │  │   Domain     │   │
│  │   (Models)   │  │  Objects    │  │   Logic      │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 🔗 ارتباطات ماژول‌ها (Module Dependencies)

### Dependency Graph

```
┌─────────────┐
│   Frontend  │
└──────┬──────┘
       │ HTTP/WebSocket
       ↓
┌──────────────────────────────────────────────────┐
│              API Layer (backend/api/)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   Chat   │  │  Dict    │  │  UseCase │       │
│  │  Router  │  │  Router   │  │  Router  │       │
│  └────┬─────┘  └────┬──────┘  └────┬─────┘       │
└───────┼─────────────┼──────────────┼─────────────┘
        │             │              │
        │             │              │
        ↓             ↓              ↓
┌──────────────────────────────────────────────────┐
│          Services Layer (backend/services/)        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   Chat   │  │  Dict    │  │  UseCase │       │
│  │  Engine  │  │ Generator │  │ Generator│       │
│  └────┬─────┘  └────┬──────┘  └────┬─────┘       │
└───────┼─────────────┼──────────────┼─────────────┘
        │             │              │
        │             │              │
        ↓             ↓              ↓
┌──────────────────────────────────────────────────┐
│      Infrastructure Layer (backend/db, llm/)      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │Database  │  │   LLM     │  │  Prompt  │       │
│  │Connector │  │ Connector │  │  Engine  │       │
│  │ ⭐ Std   │  │ ⭐ Std    │  │ ⭐ Unified│       │
│  └────┬─────┘  └────┬──────┘  └────┬─────┘       │
└───────┼─────────────┼──────────────┼─────────────┘
        │             │              │
        ↓             ↓              ↓
┌──────────────────────────────────────────────────┐
│              External Systems                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │Database  │  │   LLM     │  │  Queue   │       │
│  │(SQL Svr) │  │ Providers │  │ (asyncio)│       │
│  └──────────┘  └──────────┘  └──────────┘       │
└──────────────────────────────────────────────────┘
```

### Dependency Rules

```
✅ ALLOWED:
- api/ → services/ (via local imports)
- services/ → db/, llm/, core/
- chat/ → db/, llm/, core/
- core/ → config/

❌ FORBIDDEN:
- api/ → api/ (circular within same layer)
- services/ → api/ (reverse dependency)
- Module-level imports between api/ and services/
```

---

## 🎯 نقاط یکپارچه‌سازی (Unification Points)

### 1. Prompt Building (⭐ Unified)

```
┌──────────────────────────────────────────────────┐
│         PromptEngine (UNIFIED)                   │
│  (backend/chat/engine/prompt_engine.py)         │
│                                                  │
│  Methods:                                       │
│  ├── build_use_case_generation_prompt()         │
│  ├── build_relationship_suggestion_prompt()     │
│  ├── build_sql_generation_prompt_with_sample_data()│
│  └── _enrich_sample_data_from_dictionary()      │
└──────────────────────────────────────────────────┘
         ↑                    ↑                    ↑
         │                    │                    │
    ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
    │ UseCase │         │Relation │         │   SQL  │
    │ Builder │         │ Builder │         │  Gen   │
    └─────────┘         └─────────┘         └─────────┘
```

### 2. Database Access (⭐ Standard)

```
┌──────────────────────────────────────────────────┐
│      DatabaseConnector (STANDARD)                 │
│      (backend/db/connector.py)                   │
│                                                   │
│  Methods:                                         │
│  ├── connect()                                   │
│  ├── execute_readonly()                          │
│  ├── sample_rows()                               │
│  └── disconnect()                                │
└──────────────────────────────────────────────────┘
         ↑                    ↑                    ↑
         │                    │                    │
    ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
    │  Chat   │         │  Dict   │         │ UseCase │
    │  Engine │         │ Generator│         │ Generator│
    └─────────┘         └─────────┘         └─────────┘
```

### 3. LLM Access (⭐ Standard)

```
┌──────────────────────────────────────────────────┐
│      ModelConnector (STANDARD)                   │
│      (backend/llm/connector.py)                 │
│                                                   │
│  Methods:                                         │
│  ├── initialize()                                │
│  ├── generate()                                  │
│  └── _get_provider()                             │
└──────────────────────────────────────────────────┘
         ↑                    ↑                    ↑
         │                    │                    │
    ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
    │  Chat   │         │  Dict   │         │ UseCase │
    │  Engine │         │ Generator│         │ Generator│
    └─────────┘         └─────────┘         └─────────┘
```

### 4. Queue System (⭐ Standard)

```
┌──────────────────────────────────────────────────┐
│   AIDictionaryGenerator (QUEUE SYSTEM)          │
│   (backend/services/ai_dictionary_generator.py)  │
│                                                   │
│  Components:                                      │
│  ├── asyncio.Queue()                             │
│  ├── 3 Worker Tasks                              │
│  ├── Job Management                              │
│  └── WebSocket Broadcast                        │
└──────────────────────────────────────────────────┘
         ↑
         │
    ┌────┴────┐
    │  API    │
    │  Router │
    └─────────┘
```

---

## 📊 Sample Data Flow

```
┌──────────────────────────────────────────────────┐
│         Data Dictionary (Database)                │
│                                                   │
│  Table: schema.table_name                        │
│  Column: column_name                             │
│  example_values: ["val1", "val2", "val3", ...]  │
└──────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────┐
│      PromptEngine._enrich_sample_data()          │
│      - Extract example_values                    │
│      - Build 3-5 sample rows                     │
│      - Format as JSON                            │
└──────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────┐
│           Prompt Building                        │
│      - Include sample data section               │
│      - Add to SQL/UseCase/Relation prompts       │
└──────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────┐
│              LLM Processing                      │
│      - LLM uses sample data for context          │
│      - Generates accurate SQL/queries            │
└──────────────────────────────────────────────────┘
```

**Rules**:
- ✅ Use `example_values` from `DataDictionary` model
- ✅ Extract 3-5 unique rows from dictionary
- ❌ Do NOT sample again if dictionary has data
- ❌ Do NOT use `COUNT(*)` or metadata-only queries

---

## 🔐 Security & Validation Flow

```
User Input
    ↓
┌──────────────────────────────────────────────────┐
│         SQL Validation                          │
│      (backend/db/security.py)                   │
│      - validate_sql()                            │
│      - Only SELECT queries                       │
│      - No DROP, DELETE, UPDATE, etc.            │
└──────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────┐
│      DatabaseConnector.execute_readonly()        │
│      - Enforces security validation              │
│      - Returns results safely                    │
└──────────────────────────────────────────────────┘
         ↓
Results → User
```

---

## 🌐 WebSocket Flow

```
Client
    ↓
┌──────────────────────────────────────────────────┐
│      WebSocket Connection                       │
│      /ws/dictionary-job-status/{job_id}         │
│      /ws/use-case-job-status/{job_id}            │
└──────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────┐
│      ConnectionManager                           │
│      - Manage connections per job                │
│      - Send initial status                       │
└──────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────┐
│      Worker Task                                 │
│      - Process table task                        │
│      - Broadcast update via WebSocket            │
└──────────────────────────────────────────────────┘
         ↓
Real-time Updates → Client
```

---

## 📝 قوانین کلیدی

### Ownership Rules

1. **`backend/` is EXECUTION OWNER**
   - All real operations happen in `backend/`
   - DB, LLM, Queue, WebSocket all in `backend/`

2. **`src/` is ORCHESTRATION ONLY**
   - Defines use case flows
   - Delegates to `backend/` for execution
   - No DB/LLM logic in `src/`

### Connector Rules

1. **Database**: Always use `DatabaseConnector` (backend/db/connector.py)
2. **LLM**: Always use `ModelConnector` (backend/llm/connector.py)
3. **Queue**: Use existing queue in `ai_dictionary_generator.py` (3 workers)

### Prompt Building Rules

1. **Unified**: All prompts go through `PromptEngine`
2. **Sample Data**: Use dictionary `example_values` (3-5 rows)
3. **No Duplication**: Don't create new prompt functions

### SQL Generation Rules

1. **Dialect Detection**: Detect from Snapshot metadata
2. **SQL Server**: Apply transformations if dialect is MSSQL
3. **Sample Data**: Use 3-5 rows from dictionary
4. **Relations**: Use relationships for JOIN paths

---

## 🎨 بهبودهای معماری

### قبل از یکپارچه‌سازی:
- ❌ Prompt building در 5+ مکان مختلف
- ❌ Sample data دوباره sample می‌شد
- ❌ Duplication در prompt logic

### بعد از یکپارچه‌سازی:
- ✅ Prompt building در یک مکان (`PromptEngine`)
- ✅ Sample data از dictionary استفاده می‌شود
- ✅ No duplication - همه از `PromptEngine` استفاده می‌کنند
- ✅ Architecture stability via `cursorrules.md`

---

## 📚 فایل‌های مرجع

- **Architecture Rules**: `cursorrules.md` (1077 خط)
- **Prompt Engine**: `backend/chat/engine/prompt_engine.py`
- **Database Connector**: `backend/db/connector.py`
- **LLM Connector**: `backend/llm/connector.py`
- **Queue System**: `backend/services/ai_dictionary_generator.py`

---

**نکته**: این ساختار برای جلوگیری از structural entropy طراحی شده است. همه قوانین در `cursorrules.md` مستند شده‌اند.


