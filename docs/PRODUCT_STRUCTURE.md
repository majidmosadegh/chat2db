# ساختار کلی محصول SQL PT

**Product Name**: SQL PT (SQL Persian Text-to-SQL)  
**Version**: 2.0  
**Architecture**: Backend-First, Unified Prompt Building

---

## 🎯 نمای کلی محصول

SQL PT یک سیستم **Text-to-SQL** است که:
- سوالات طبیعی (فارسی/انگلیسی) را به SQL تبدیل می‌کند
- از AI برای تولید دیکشنری داده استفاده می‌کند
- روابط بین جداول را شناسایی می‌کند
- Use Caseهای کسب‌وکار تولید می‌کند
- با SQL Server و سایر دیتابیس‌ها کار می‌کند

---

## 📐 ساختار کامل پروژه

```
sql_pt/
│
├── 📁 backend/                          # ⭐ Backend (Python/FastAPI)
│   │
│   ├── 📁 api/                          # API Endpoints (20+ فایل)
│   │   ├── ai_dictionary.py             # تولید دیکشنری با AI
│   │   ├── dictionary_job_router.py     # مدیریت jobها + WebSocket
│   │   ├── use_case_job_router.py       # Use case jobs + WebSocket
│   │   ├── smart_use_case_builder.py   # ساخت use case هوشمند
│   │   ├── relationships.py             # مدیریت روابط جداول
│   │   ├── schema.py                    # عملیات schema
│   │   ├── data_dictionary.py           # CRUD دیکشنری
│   │   ├── database.py                  # عملیات دیتابیس
│   │   ├── database_connection.py       # اتصالات دیتابیس
│   │   ├── use_cases.py                 # مدیریت use caseها
│   │   ├── llm.py                       # مدیریت مدل‌های LLM
│   │   ├── models.py                    # مدل‌های Pydantic
│   │   ├── prompt_generator.py          # تولید prompt
│   │   ├── prompt.py                    # مدیریت promptها
│   │   ├── text_generation.py           # تولید متن
│   │   ├── fine_tuning.py               # Fine-tuning
│   │   ├── maturation.py                 # بلوغ use case
│   │   └── use_case_maturation.py       # بلوغ use case
│   │
│   ├── 📁 services/                     # Business Logic (12 فایل)
│   │   ├── ai_dictionary_generator.py   # ⭐ Generator با Queue (3 workers)
│   │   ├── use_case_generator.py        # Generator use case
│   │   ├── maturation_engine.py          # موتور بلوغ use case
│   │   ├── use_case_maturation.py       # سرویس بلوغ
│   │   ├── llm_service.py                # سرویس LLM یکپارچه
│   │   ├── db_connector.py              # DirectDatabaseConnector
│   │   ├── db_connector_utils.py        # Helper برای connector
│   │   ├── ai_dictionary_service.py     # Legacy service
│   │   ├── ai_dictionary_parser.py      # Parser برای dictionary
│   │   ├── ai_dictionary_prompt.py      # Prompt builder
│   │   └── ai_dictionary_types.py       # Type definitions
│   │
│   ├── 📁 chat/                         # ⭐ Chat Engine & SQL Pipeline
│   │   ├── 📁 engine/                   # Core Engine Components
│   │   │   ├── chat_engine.py           # Orchestrator اصلی
│   │   │   ├── prompt_engine.py         # ⭐ UNIFIED PROMPT BUILDING
│   │   │   ├── sql_pipeline.py          # Pipeline تولید SQL
│   │   │   ├── query_planner.py         # Query planning & entity extraction
│   │   │   ├── llm_gateway.py           # Gateway برای LLM
│   │   │   ├── context_loader.py         # بارگذاری context
│   │   │   └── conversation_state.py    # مدیریت conversation
│   │   │
│   │   ├── 📁 utils/                    # Utilities
│   │   │   └── json_safety.py           # Safe JSON parsing
│   │   │
│   │   ├── router.py                    # FastAPI router برای chat
│   │   ├── schemas.py                   # Pydantic models
│   │   ├── sql_guard.py                 # SQL security validation
│   │   └── executor.py                  # SQL executor
│   │
│   ├── 📁 db/                           # Database Layer
│   │   ├── connector.py                 # ⭐ DatabaseConnector (استاندارد)
│   │   ├── security.py                  # اعتبارسنجی SQL و رمزگذاری
│   │   ├── engine_factory.py            # ساخت engine برای دیتابیس‌ها
│   │   ├── models.py                    # مدل‌های دیتابیس
│   │   ├── repositories.py              # Repository pattern
│   │   └── dependencies.py              # Dependency injection
│   │
│   ├── 📁 llm/                          # LLM Layer
│   │   ├── connector.py                 # ⭐ ModelConnector (استاندارد)
│   │   ├── registry.py                  # ModelRegistry
│   │   ├── schemas.py                   # LLM schemas
│   │   ├── exceptions.py                # LLM exceptions
│   │   └── providers/                   # LLM Providers
│   │       ├── base.py                  # Base provider
│   │       ├── openai.py                # OpenAI provider
│   │       ├── ollama.py                # Ollama provider
│   │       ├── vllm.py                  # vLLM provider
│   │       └── custom_http.py           # Custom HTTP provider
│   │
│   ├── 📁 core/                         # Core Layer
│   │   ├── app.py                       # FastAPI app factory
│   │   ├── container.py                 # Dependency injection container
│   │   ├── config.py                    # Configuration
│   │   ├── db_utils.py                  # ابزارهای دیتابیس
│   │   ├── json_safety.py               # JSON safety utilities
│   │   ├── loguru_config.py            # Loguru configuration
│   │   └── prompts/                     # Prompt templates
│   │       └── dictionary_prompts.py    # Dictionary prompts
│   │
│   ├── 📁 config/                       # Configuration
│   │   ├── config.py                    # تنظیمات اصلی
│   │   ├── logging_config.py            # تنظیمات logging
│   │   └── logs/                        # فایل‌های لاگ
│   │
│   ├── 📁 tests/                        # Tests (68 فایل)
│   │   └── [68 test files]
│   │
│   ├── 📁 scripts/                      # اسکریپت‌های نگهداری
│   │   ├── migrate_ai_generation_jobs.py
│   │   ├── migrate_maturation_sessions.py
│   │   ├── cleanup_old_logs.py
│   │   └── maintenance/
│   │
│   ├── main.py                          # Entry point اصلی
│   ├── main_simple.py                   # Entry point ساده
│   └── requirements.txt                 # Dependencies
│
├── 📁 frontend/                         # ⭐ Frontend (Next.js/TypeScript)
│   ├── app/                             # Next.js App Router
│   │   ├── api/                         # API routes
│   │   ├── dashboard/                   # Dashboard pages
│   │   ├── chat/                        # Chat interface
│   │   ├── dictionary/                  # Dictionary management
│   │   ├── use-cases/                   # Use case management
│   │   └── relationships/               # Relationship management
│   │
│   ├── components/                      # React Components (52 فایل)
│   │   ├── ui/                          # UI components
│   │   ├── forms/                      # Form components
│   │   ├── tables/                     # Table components
│   │   └── charts/                     # Chart components
│   │
│   ├── lib/                             # Utility libraries
│   │   ├── api.ts                      # API client
│   │   ├── utils.ts                    # Utilities
│   │   └── hooks.ts                   # React hooks
│   │
│   ├── config/                          # Frontend configuration
│   │   └── api.ts                      # API configuration
│   │
│   └── package.json                     # Dependencies
│
├── 📁 src/                              # ⭐ Clean Architecture Layer
│   ├── domain/                          # Domain entities
│   │   ├── entities/                    # Entity classes
│   │   └── value_objects/               # Value objects
│   │
│   ├── application/                     # Use cases
│   │   ├── handlers/                    # Command handlers
│   │   ├── queries/                     # Query handlers
│   │   └── interfaces/                  # Service interfaces
│   │
│   ├── infrastructure/                  # External services
│   │   ├── config/                      # DI configuration
│   │   └── external/                    # External service implementations
│   │
│   └── presentation/                    # API controllers
│       └── api/                         # FastAPI controllers
│
├── 📁 docs/                             # مستندات
│   ├── architecture/                    # معماری
│   │   ├── ARCHITECTURE_STRUCTURE.md    # ساختار معماری
│   │   └── [8 markdown files]
│   ├── AI_Dictionary_Generation_Flow.md
│   └── design_summary_ai_dictionary_generation.md
│
├── 📄 cursorrules.md                    # ⭐ قوانین معماری (1077 خط)
├── 📄 README.md                         # مستندات اصلی
└── 📄 requirements.txt                  # Python dependencies
```

---

## 🔄 جریان‌های اصلی محصول

### 1. جریان Chat (Text-to-SQL)

```
User (Frontend)
    │
    │ سوال طبیعی (فارسی/انگلیسی)
    ↓
Frontend (Next.js)
    │
    │ POST /api/chat
    ↓
Backend API (FastAPI)
    │
    │ Chat Router
    ↓
Chat Engine
    │
    │ 1. Load Context
    │    - Schema
    │    - Data Dictionary
    │    - Relationships
    │    - Use Cases
    ↓
    │ 2. Intent Detection
    │    - CONVERSATIONAL
    │    - COUNT
    │    - AGGREGATION
    │    - etc.
    ↓
    │ 3. Table Selection
    │    - Select relevant tables
    │    - Filter by query content
    ↓
    │ 4. Query Planning
    │    - Entity extraction
    │    - Join path finding
    │    - Filter identification
    ↓
    │ 5. SQL Generation
    │    - Build prompt with sample data
    │    - Call LLM via ModelConnector
    │    - Generate SQL Server compatible SQL
    ↓
    │ 6. SQL Validation
    │    - Security validation
    │    - SQL Server transformation
    │    - Syntax checking
    ↓
    │ 7. Execution
    │    - Execute via DatabaseConnector
    │    - Return results
    ↓
Results → Frontend → User
```

### 2. جریان Dictionary Generation

```
User (Frontend)
    │
    │ Request: Generate Dictionary
    │ - Select snapshot
    │ - Select tables
    │ - Set parameters
    ↓
Frontend (Next.js)
    │
    │ POST /api/ai/dictionary/generate
    ↓
Backend API (FastAPI)
    │
    │ AI Dictionary Router
    ↓
AI Dictionary Generator (Service)
    │
    │ 1. Create Job
    │    - Create AIGenerationJob
    │    - Create TableTasks
    │    - Add to queue
    ↓
    │ 2. Queue Processing
    │    - 3 Worker tasks
    │    - Process table tasks in parallel
    ↓
    │ 3. For Each Table:
    │    a. Get schema info
    │    b. Sample 3-5 rows via DatabaseConnector
    │    c. Build prompt via PromptEngine
    │    d. Call LLM via ModelConnector
    │    e. Parse JSON response
    │    f. Store in DataDictionary
    │    g. Broadcast WebSocket update
    ↓
    │ 4. Job Complete
    │    - Update job status
    │    - Send final WebSocket update
    ↓
Results → Database + WebSocket → Frontend → User
```

### 3. جریان Use Case Generation

```
User (Frontend)
    │
    │ Request: Generate Use Cases
    │ - Select snapshot
    │ - Select scope (all/table/column)
    │ - Set parameters
    ↓
Frontend (Next.js)
    │
    │ POST /api/smart-use-case-builder/generate
    ↓
Backend API (FastAPI)
    │
    │ Smart Use Case Builder Router
    ↓
Use Case Generator (Service)
    │
    │ 1. Load Context
    │    - Minified schema
    │    - Data dictionary
    │    - Relationships
    │    - Sample data (from dictionary)
    ↓
    │ 2. Build Prompt
    │    - Via PromptEngine.build_use_case_generation_prompt()
    │    - Include sample data
    │    - Include SQL Server rules
    ↓
    │ 3. Call LLM
    │    - Via ModelConnector
    │    - Generate use cases
    ↓
    │ 4. Parse & Store
    │    - Parse JSON response
    │    - Validate structure
    │    - Store in UseCase table
    ↓
Results → Database → Frontend → User
```

### 4. جریان Relationship Suggestion

```
User (Frontend)
    │
    │ Request: Suggest Relationships
    │ - Select snapshot
    ↓
Frontend (Next.js)
    │
    │ POST /api/relationships/ai-suggest
    ↓
Backend API (FastAPI)
    │
    │ Relationships Router
    ↓
Relationship Service
    │
    │ 1. Load Context
    │    - Schema data
    │    - Data dictionary
    │    - Sample data (from dictionary)
    │    - Detect intermediary tables
    ↓
    │ 2. Build Prompt
    │    - Via PromptEngine.build_relationship_suggestion_prompt()
    │    - Include sample data
    │    - Include N:N detection rules
    ↓
    │ 3. Call LLM
    │    - Via ModelConnector
    │    - Generate relationships
    ↓
    │ 4. Parse & Store
    │    - Parse JSON response
    │    - Calculate confidence scores
    │    - Store in Relationship table
    ↓
Results → Database → Frontend → User
```

---

## 🏗️ معماری کلی محصول

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Frontend (Next.js)                      │   │
│  │  - React Components                                  │   │
│  │  - API Client                                        │   │
│  │  - WebSocket Client                                  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                      API LAYER                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         FastAPI Routers (backend/api/)              │   │
│  │  - Chat Router                                       │   │
│  │  - Dictionary Router                                 │   │
│  │  - Use Case Router                                   │   │
│  │  - Relationship Router                               │   │
│  │  - WebSocket Endpoints                               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   BUSINESS LOGIC LAYER                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Services (backend/services/)                │   │
│  │  - AI Dictionary Generator (Queue System)          │   │
│  │  - Use Case Generator                               │   │
│  │  - Maturation Engine                                 │   │
│  │  - LLM Service                                       │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Chat Engine (backend/chat/)                 │   │
│  │  - Chat Engine                                       │   │
│  │  - Prompt Engine (Unified)                          │   │
│  │  - SQL Pipeline                                      │   │
│  │  - Query Planner                                     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  INFRASTRUCTURE LAYER                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Database    │  │     LLM      │  │    Queue     │      │
│  │  Connector   │  │  Connector   │  │   System     │      │
│  │  ⭐ Standard │  │ ⭐ Standard  │  │ (asyncio)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL SYSTEMS                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Database    │  │   LLM        │  │   WebSocket  │      │
│  │ (SQL Server)│  │ Providers    │  │   Clients    │      │
│  │             │  │ (OpenAI,     │  │              │      │
│  │             │  │  Ollama,     │  │              │      │
│  │             │  │  vLLM, etc.) │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 ویژگی‌های اصلی محصول

### 1. Text-to-SQL
- تبدیل سوالات طبیعی به SQL
- پشتیبانی از فارسی و انگلیسی
- تشخیص intent خودکار
- تولید SQL Server compatible
- استفاده از sample data برای دقت بیشتر

### 2. AI Dictionary Generation
- تولید خودکار دیکشنری داده
- نمونه‌گیری 3-5 ردیف از هر جدول
- ذخیره example_values در dictionary
- پردازش موازی با 3 worker
- به‌روزرسانی real-time از طریق WebSocket

### 3. Relationship Discovery
- شناسایی روابط صریح (Foreign Keys)
- شناسایی روابط ضمنی (Hidden Relations)
- پیشنهاد روابط N:N با intermediary tables
- محاسبه confidence score
- استفاده از sample data برای validation

### 4. Use Case Generation
- تولید use caseهای کسب‌وکار
- استفاده از schema و dictionary
- تولید سوالات و SQL queries واقعی
- پشتیبانی از scopeهای مختلف (all/table/column)

### 5. Use Case Maturation
- بهبود مداوم use caseها
- تولید سوالات جدید
- تست و validation خودکار
- یادگیری از خطاها

---

## 🔌 نقاط یکپارچه‌سازی

### 1. Prompt Building (Unified)
```
PromptEngine (backend/chat/engine/prompt_engine.py)
    │
    ├── build_use_case_generation_prompt()
    ├── build_relationship_suggestion_prompt()
    ├── build_sql_generation_prompt_with_sample_data()
    └── _enrich_sample_data_from_dictionary()
```

**استفاده در**:
- Chat Engine (SQL generation)
- Use Case Generator
- Relationship Builder
- Dictionary Generator (via legacy prompts)

### 2. Database Access (Standard)
```
DatabaseConnector (backend/db/connector.py)
    │
    ├── connect()
    ├── execute_readonly()
    ├── sample_rows()
    └── disconnect()
```

**استفاده در**:
- Chat Engine
- Dictionary Generator
- Use Case Generator
- Relationship Builder

### 3. LLM Access (Standard)
```
ModelConnector (backend/llm/connector.py)
    │
    ├── initialize()
    ├── generate()
    └── _get_provider()
```

**Providers**:
- OpenAI
- Ollama
- vLLM
- Custom HTTP

**استفاده در**:
- Chat Engine
- Dictionary Generator
- Use Case Generator
- Relationship Builder

### 4. Queue System (Standard)
```
AIDictionaryGenerator (backend/services/ai_dictionary_generator.py)
    │
    ├── asyncio.Queue()
    ├── 3 Worker Tasks
    ├── Job Management
    └── WebSocket Broadcast
```

**استفاده در**:
- Dictionary Generation
- Use Case Generation (future)

---

## 📊 API Endpoints

### Chat
- `POST /api/chat` - Chat with database
- `GET /api/chat/history` - Get chat history

### Dictionary
- `POST /api/ai/dictionary/generate` - Generate dictionary
- `GET /api/ai/dictionary/status/{job_id}` - Get job status
- `WS /ws/dictionary-job-status/{job_id}` - WebSocket updates
- `GET /api/data-dictionary` - Get dictionary
- `PUT /api/data-dictionary/{id}` - Update dictionary

### Use Cases
- `POST /api/smart-use-case-builder/generate` - Generate use cases
- `GET /api/use-case-job/status/{job_id}` - Get job status
- `WS /ws/use-case-job-status/{job_id}` - WebSocket updates
- `GET /api/use-cases` - Get use cases
- `PUT /api/use-cases/{id}` - Update use case

### Relationships
- `POST /api/relationships/ai-suggest` - Suggest relationships
- `GET /api/relationships` - Get relationships
- `POST /api/relationships` - Create relationship
- `PUT /api/relationships/{id}` - Update relationship

### Schema
- `POST /api/schema/introspect` - Introspect schema
- `GET /api/schema/{snapshot_id}` - Get schema

### Database
- `POST /api/database-connection` - Create connection
- `GET /api/database-connection` - Get connections
- `POST /api/database/test` - Test connection

---

## 🔐 Security

### SQL Security
- Validation قبل از execution
- فقط SELECT queries مجاز
- Block کردن DROP, DELETE, UPDATE, etc.
- SQL injection prevention

### Password Encryption
- رمزگذاری passwordهای دیتابیس
- ذخیره encrypted در database
- Decrypt فقط هنگام استفاده

### Authentication (Future)
- JWT tokens
- Role-based access control

---

## 📈 Performance

### Queue System
- 3 worker tasks برای پردازش موازی
- Isolated errors (یک failure کل queue را crash نمی‌کند)
- Real-time updates via WebSocket

### Caching (Future)
- Cache schema metadata
- Cache dictionary data
- Cache relationships

### Optimization
- Minified schema/dictionary در prompts
- Sample data محدود (3-5 rows)
- Efficient SQL generation

---

## 🧪 Testing

### Test Structure
- `backend/tests/` - 68 test files
- Unit tests
- Integration tests
- API tests

### Test Coverage
- Database connector tests
- LLM connector tests
- Chat engine tests
- Dictionary generator tests

---

## 📚 مستندات

### Architecture
- `cursorrules.md` - قوانین معماری (1077 خط)
- `docs/architecture/ARCHITECTURE_STRUCTURE.md` - ساختار معماری
- `docs/architecture/` - 8 فایل معماری دیگر

### Design
- `docs/AI_Dictionary_Generation_Flow.md` - جریان تولید dictionary
- `docs/design_summary_ai_dictionary_generation.md` - خلاصه design

### Product
- `README.md` - مستندات اصلی
- `docs/PRODUCT_STRUCTURE.md` - این فایل

---

## 🚀 Deployment

### Backend
- FastAPI application
- Uvicorn server
- Environment variables for config
- Logging to files

### Frontend
- Next.js application
- Static generation
- API routes
- WebSocket client

### Database
- SQL Server (primary)
- PostgreSQL (supported)
- MySQL (supported)

---

## 🔄 جریان داده کلی

```
User Input (Frontend)
    ↓
API Request (HTTP/WebSocket)
    ↓
Backend Processing
    ├── Chat Engine (Text-to-SQL)
    ├── Dictionary Generator (AI Dictionary)
    ├── Use Case Generator (Use Cases)
    └── Relationship Builder (Relationships)
    ↓
Infrastructure
    ├── DatabaseConnector (Database)
    ├── ModelConnector (LLM)
    └── Queue System (Background Jobs)
    ↓
External Systems
    ├── Database (SQL Server)
    └── LLM Providers (OpenAI, Ollama, etc.)
    ↓
Results → Backend → Frontend → User
```

---

## 📝 قوانین کلیدی

1. **Backend-First**: همه عملیات واقعی در `backend/`
2. **Unified Prompt Building**: همه prompts از `PromptEngine`
3. **Standard Connectors**: استفاده از `DatabaseConnector` و `ModelConnector`
4. **Sample Data from Dictionary**: استفاده از `example_values` موجود
5. **No Duplication**: جلوگیری از تکرار با استفاده از ماژول‌های یکپارچه
6. **SQL Server Compatibility**: همه SQL queries باید SQL Server compatible باشند

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

**نکته**: این ساختار برای جلوگیری از structural entropy طراحی شده است. همه قوانین در `cursorrules.md` مستند شده‌اند.


