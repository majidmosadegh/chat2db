# معماری چت بات (Chat Bot Architecture)

## 📋 نمای کلی (Overview)

چت بات یک سیستم **Text-to-SQL** پیشرفته است که:
- سوالات کاربر (فارسی/انگلیسی) را دریافت می‌کند
- به کوئری‌های SQL تبدیل می‌کند
- کوئری‌ها را روی دیتابیس اجرا می‌کند
- نتایج را به صورت جدول HTML نمایش می‌دهد

**محدودیت‌ها:**
- حداکثر 50 ردیف در هر کوئری
- فقط کوئری‌های SELECT (read-only)
- پشتیبانی از SQL Server، PostgreSQL، MySQL

---

## 🔄 جریان اصلی (Main Flow)

```
┌─────────────────┐
│  User Question  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Router (/execute)│
│  POST /api/chat/execute
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ChatEngine     │
│  process_chat_request()
└────────┬────────┘
         │
         ├──► 1. Load Context
         │    └─► ContextLoader
         │        ├─► Schema Info
         │        ├─► Data Dictionary
         │        ├─► Relationships
         │        └─► Use Cases
         │
         ├──► 2. Reasoning Pipeline (3-Stage)
         │    ├─► Stage A: Intent Detection
         │    ├─► Stage B: Table Selection
         │    └─► Stage C: SQL Generation
         │
         ├──► 3. SQL Pipeline
         │    ├─► Semantic Guard
         │    ├─► SQL Critic (Optional)
         │    ├─► SQL Validator
         │    └─► SQL Executor
         │
         ▼
┌─────────────────┐
│  ChatResponse   │
│  - SQL Query
│  - Results (max 50 rows)
│  - Metadata
└─────────────────┘
```

---

## 🏗️ اجزای اصلی (Main Components)

### 1. Router (`backend/chat/router.py`)
**وظیفه:** Entry point برای API

**Endpoint:**
```python
POST /api/chat/execute
```

**Request Schema:**
```python
ChatRequest:
  - user_question: str
  - snapshot_id: int
  - selected_model_id: int
  - language: "persian" | "english"
  - conversation_id: Optional[str]
```

**Response Schema:**
```python
ChatResponse:
  - success: bool
  - generated_sql: str
  - rows: List[Dict]  # حداکثر 50 ردیف
  - row_count: int
  - execution_status: str
  - execution_time_ms: int
  - metadata: {...}
```

---

### 2. ChatEngine (`backend/chat/engine/chat_engine.py`)
**وظیفه:** Orchestrator اصلی - هماهنگ‌کننده تمام مراحل

**اجزا:**
- `ContextLoader`: بارگذاری context از metadata
- `PromptEngine`: ساخت prompt‌ها برای LLM
- `LLMGateway`: رابط با مدل‌های LLM
- `SQLPipeline`: pipeline کامل SQL
- `ConversationStateManager`: مدیریت state مکالمه

**متد اصلی:**
```python
async def process_chat_request(request: ChatRequest) -> ChatResponse
```

**جریان کار:**
1. بارگذاری context
2. تشخیص intent (CONVERSATIONAL یا SQL)
3. اگر SQL: اجرای pipeline
4. اگر CONVERSATIONAL: پاسخ مکالمه‌ای
5. ساخت و برگرداندن response

---

### 3. ContextLoader (`backend/chat/engine/context_loader.py`)
**وظیفه:** بارگذاری context از دیتابیس metadata

**اطلاعات بارگذاری شده:**

#### Schema Info
```python
SchemaInfo:
  - table_name: str
  - schema_name: str
  - columns: List[ColumnInfo]
    - column_name: str
    - data_type: str
    - is_nullable: bool
    - is_primary_key: bool
```

#### Data Dictionary
```python
DataDictionaryInfo:
  - table_name: str
  - column_name: str
  - description: str
  - sample_data: List[str]  # نمونه داده‌ها
```

#### Relationships
```python
RelationshipInfo:
  - from_table: str
  - to_table: str
  - from_column: str
  - to_column: str
  - relationship_type: str
```

#### Use Cases
```python
UseCaseInfo:
  - name: str
  - business_goal: str
  - example_questions: List[str]
  - example_queries: List[str]
```

**متد اصلی:**
```python
async def load_context(snapshot_id: int) -> ChatContext
```

---

### 4. PromptEngine (`backend/chat/engine/prompt_engine.py`)
**وظیفه:** ساخت prompt‌های بهینه برای LLM

**انواع Prompt:**

#### 1. Intent Detection Prompt
- تشخیص نوع سوال (COUNT, AGGREGATION, LIST, DETAIL, TOP_N, COMPARISON, CONVERSATIONAL)
- ورودی: سوال کاربر + context
- خروجی: intent type

#### 2. Table Selection Prompt
- انتخاب جداول مرتبط
- ورودی: intent + entities + schema
- خروجی: لیست جداول و ستون‌های مرتبط

#### 3. SQL Generation Prompt
- تولید SQL بر اساس intent و context
- **پشتیبانی از انواع DB:**
  - SQL Server: `TOP 50`, `N'...'` برای Unicode
  - PostgreSQL: `LIMIT 50`
  - MySQL: `LIMIT 50`
- **قوانین مهم:**
  - فقط از جداول و ستون‌های موجود در schema استفاده کند
  - برای SQL Server از `TOP 50` استفاده کند (نه `LIMIT`)
  - برای رشته‌های فارسی از `N'...'` استفاده کند
  - کوئری باید کامل باشد (SELECT, FROM, WHERE در صورت نیاز)

#### 4. SQL Validation Prompt
- بررسی صحت SQL از نظر معنایی

**متدهای کلیدی:**
```python
def build_intent_detection_prompt(...)
def build_table_selection_prompt(...)
def build_sql_generation_prompt(...)
def _get_sql_server_rules(...)  # قوانین خاص SQL Server
```

---

### 5. SQLPipeline (`backend/chat/engine/sql_pipeline.py`)
**وظیفه:** Pipeline کامل تولید و اجرای SQL

**مراحل:**

#### Stage 1: Reasoning Pipeline (3-Stage)

##### Stage A: Intent Detection
```python
ReasoningPipeline.detect_intent(question, context)
```
- تشخیص نوع سوال
- انواع intent: COUNT, AGGREGATION, LIST, DETAIL, TOP_N, COMPARISON, CONVERSATIONAL

##### Stage B: Table Selection
```python
ReasoningPipeline.select_tables(intent, question, context)
```
- انتخاب جداول مرتبط
- فیلتر بر اساس entities موجود در سوال

##### Stage C: SQL Generation
```python
ReasoningPipeline.generate_sql(intent, tables, question, context)
```
- تولید SQL اولیه
- استفاده از PromptEngine برای ساخت prompt

#### Stage 2: Semantic Guard
```python
SemanticGuard.enforce_rules(sql, intent, context)
```
**قوانین:**
- COUNT queries نباید TOP/LIMIT داشته باشند
- DETAIL queries باید WHERE داشته باشند
- فقط SELECT queries مجاز هستند
- باید SELECT و FROM داشته باشند

#### Stage 3: SQL Critic (Optional)
```python
SQLCritic.critique_and_improve_sql(sql, context, question)
```
- نقد SQL از نظر معنایی
- در صورت نیاز retry با feedback
- حداکثر 2 بار retry

#### Stage 4: SQL Validator
```python
SQLValidator.validate_sql(sql, context)
```
**بررسی‌ها:**
- Syntax validation
- Safety checks (read-only)
- Context validation (جداول و ستون‌های موجود)
- تبدیل syntax برای انواع مختلف DB

#### Stage 5: SQL Executor
```python
SQLExecutor.execute_sql(sql, max_rows=50)
```
- اجرای SQL روی دیتابیس snapshot
- استفاده از `DatabaseConnector`
- برگرداندن حداکثر 50 ردیف

**متد اصلی:**
```python
async def process_sql(
    context: ChatContext,
    question: str,
    reasoning_output: str,
    language: ChatLanguage,
    model_id: int,
    max_rows: int = 50  # محدودیت 50 ردیف
) -> dict
```

---

### 6. LLMGateway (`backend/chat/engine/llm_gateway.py`)
**وظیفه:** رابط یکپارچه با مدل‌های LLM

**پشتیبانی از:**
- OpenAI (GPT-3.5, GPT-4)
- Anthropic (Claude)
- Ollama (مدل‌های محلی)

**متد اصلی:**
```python
async def call_llm(
    prompt: str,
    model_id: int,
    temperature: float = 0.1
) -> str
```

---

### 7. DatabaseConnector (`backend/db/connector.py`)
**وظیفه:** اتصال و اجرای کوئری‌ها روی دیتابیس

**پشتیبانی از:**
- SQL Server (با pymssql)
- PostgreSQL (با asyncpg)
- MySQL (با aiomysql)

**متد اصلی:**
```python
async def execute_readonly(
    sql: str,
    limit: int = 50  # محدودیت پیش‌فرض
) -> List[Dict[str, Any]]
```

**ویژگی‌ها:**
- اعمال خودکار `TOP 50` برای SQL Server
- اعمال خودکار `LIMIT 50` برای PostgreSQL/MySQL
- Security validation (فقط SELECT)
- Comprehensive logging

---

### 8. Frontend Components

#### Chat Page (`frontend/app/chat/page.tsx`)
**وظیفه:** صفحه اصلی چت

**عملکرد:**
- دریافت سوال از کاربر
- ارسال درخواست به API
- نمایش SQL query
- نمایش نتایج به صورت جدول HTML

#### Chat Message (`frontend/components/chat/chat-message.tsx`)
**وظیفه:** نمایش پیام‌های چت

**ویژگی‌ها:**
- نمایش SQL query با syntax highlighting
- نمایش نتایج به صورت جدول HTML با اسکرول
- نمایش metadata (execution time, row count)
- پشتیبانی از dark mode

**ساختار جدول:**
```tsx
<div className="overflow-auto max-h-96">
  <table>
    <thead className="sticky top-0">
      {/* Headers */}
    </thead>
    <tbody>
      {/* All 50 rows */}
    </tbody>
  </table>
</div>
```

---

## 📊 مراحل پردازش (Processing Stages)

### Stage 1: Context Loading
```
ContextLoader.load_context(snapshot_id)
    ↓
├─► Schema Info (جداول و ستون‌ها)
├─► Data Dictionary (توضیحات + sample data)
├─► Relationships (روابط بین جداول)
└─► Use Cases (مثال‌های کوئری)
```

### Stage 2: Reasoning Pipeline (3-Stage)

#### Stage A: Intent Detection
```
LLM Call → Intent Type
Types: COUNT, AGGREGATION, LIST, DETAIL, TOP_N, COMPARISON, CONVERSATIONAL
```

#### Stage B: Table Selection
```
LLM Call → Selected Tables + Columns
Based on: Intent + Entities + Schema
```

#### Stage C: SQL Generation
```
LLM Call → SQL Query
Based on: Intent + Tables + Context + Database Type
```

### Stage 3: Semantic Guards
```
SemanticGuard.enforce_rules()
    ↓
├─► COUNT queries: No TOP/LIMIT
├─► DETAIL queries: Must have WHERE
├─► Must have SELECT and FROM
└─► Only SELECT queries allowed
```

### Stage 4: SQL Critic (Optional)
```
SQLCritic.critique_and_improve_sql()
    ↓
If issues found → Retry with feedback (max 2 times)
```

### Stage 5: SQL Validation
```
SQLValidator.validate_sql()
    ↓
├─► Syntax validation
├─► Safety checks
├─► Context validation
└─► Database-specific transformations
```

### Stage 6: SQL Execution
```
SQLExecutor.execute_sql(sql, max_rows=50)
    ↓
DatabaseConnector.execute_readonly(sql, limit=50)
    ↓
Results (max 50 rows)
```

---

## 🗂️ Schema و Context

### ChatContext
```python
ChatContext:
  - snapshot_id: int
  - snapshot_name: str
  - database_type: str  # "sqlserver" | "postgresql" | "mysql"
  - schema_info: List[SchemaInfo]
  - data_dictionary: List[DataDictionaryInfo]
  - relationships: List[RelationshipInfo]
  - use_cases: List[UseCaseInfo]
  - context_hash: str  # برای caching
```

### Context String Format
برای استفاده در prompt، context به string تبدیل می‌شود:

```
DATABASE SCHEMA:
===============
[dbo].[GoodsExchange_Export]
  - GoodsName (nvarchar)
  - Price (decimal)
  - ...

DATA DICTIONARY:
================
GoodsExchange_Export.GoodsName
  Description: نام کالا
  Sample Data: ['قیر 6070 - صادراتی', ...]

RELATIONSHIPS:
==============
dbo.GoodsExchange_Export → dbo.OtherTable
  ON GoodsExchange_Export.ID = OtherTable.ExportID

BUSINESS USE CASES:
===================
[1] Use Case: Price Query
  Business Goal: دریافت قیمت کالاها
  Example Questions: ['قیمت قیر چقدر است؟']
  Example Queries: ['SELECT Price FROM ...']
```

---

## 🔒 امنیت و اعتبارسنجی

### SQL Security
- فقط کوئری‌های SELECT مجاز هستند
- بررسی در `SQLGuard.validate_sql()`
- بررسی در `DatabaseConnector.execute_readonly()`

### Context Validation
- بررسی وجود جداول و ستون‌ها در schema
- بررسی روابط بین جداول
- استفاده از allowed_tables و allowed_columns

### Limit Enforcement
- حداکثر 50 ردیف در هر کوئری
- اعمال خودکار `TOP 50` یا `LIMIT 50`
- بررسی در `SQLExecutor` و `DatabaseConnector`

---

## 📝 نکات مهم

### 1. Context-based Generation
- تمام کوئری‌ها بر اساس schema واقعی دیتابیس تولید می‌شوند
- استفاده از sample data برای فهمیدن مقادیر واقعی
- استفاده از use cases برای راهنمایی

### 2. Multi-stage Reasoning
- استفاده از 3-stage pipeline برای دقت بیشتر
- هر stage به stage قبلی وابسته است
- امکان retry در صورت خطا

### 3. Database Type Awareness
- SQL Server: `TOP 50`, `N'...'` برای Unicode
- PostgreSQL: `LIMIT 50`
- MySQL: `LIMIT 50`
- تبدیل خودکار syntax در `SQLValidator`

### 4. Language Support
- پشتیبانی از فارسی و انگلیسی
- Prompt‌های جداگانه برای هر زبان
- پشتیبانی از کاراکترهای Unicode در SQL

### 5. Result Display
- نمایش SQL query با syntax highlighting
- نمایش نتایج به صورت جدول HTML
- اسکرول برای نتایج بزرگ (max 50 rows)
- نمایش metadata (execution time, row count)

### 6. Traceability
- تمام مراحل لاگ می‌شوند
- Request ID برای tracking
- Execution time برای هر stage
- Error logging با stack trace

---

## 📁 ساختار فایل‌ها

```
backend/chat/
├── router.py                    # API endpoint
├── schemas.py                   # Data models (ChatRequest, ChatResponse, ...)
├── sql_guard.py                # SQL safety checks
├── executor.py                  # Legacy SQL executor
├── ARCHITECTURE.md              # این فایل
│
├── engine/
│   ├── __init__.py
│   ├── chat_engine.py          # Main orchestrator
│   ├── context_loader.py       # Context loading
│   ├── prompt_engine.py        # Prompt building
│   ├── llm_gateway.py          # LLM interface
│   ├── sql_pipeline.py         # SQL pipeline (Reasoning, Guard, Critic, Validator, Executor)
│   ├── query_planner.py        # Query planning (optional)
│   ├── conversation_state.py   # Conversation management
│   └── README.md
│
└── utils/
    ├── __init__.py
    └── json_safety.py           # JSON parsing utilities

backend/db/
├── connector.py                # Database connector
├── engine_factory.py           # SQLAlchemy engine factory
├── models.py                   # Database models
└── security.py                 # SQL security validation

frontend/
├── app/chat/
│   └── page.tsx                # Chat page
└── components/chat/
    └── chat-message.tsx        # Message display component
```

---

## 🔄 جریان داده (Data Flow)

```
1. User Input
   ↓
2. ChatRequest (JSON)
   ↓
3. ChatEngine.process_chat_request()
   ↓
4. ContextLoader.load_context()
   ↓
5. SQLPipeline.process_sql()
   ├─► ReasoningPipeline (3-stage)
   ├─► SemanticGuard
   ├─► SQLCritic (optional)
   ├─► SQLValidator
   └─► SQLExecutor
   ↓
6. DatabaseConnector.execute_readonly()
   ↓
7. Results (List[Dict])
   ↓
8. ChatResponse (JSON)
   ↓
9. Frontend Display
   ├─► SQL Query (syntax highlighted)
   └─► Results Table (HTML, scrollable)
```

---

## 🎯 ویژگی‌های کلیدی

✅ **Context-aware**: استفاده از schema واقعی دیتابیس  
✅ **Multi-stage reasoning**: 3-stage pipeline برای دقت بیشتر  
✅ **Database type aware**: پشتیبانی از SQL Server, PostgreSQL, MySQL  
✅ **Language support**: فارسی و انگلیسی  
✅ **Safety**: فقط SELECT queries، validation کامل  
✅ **Limit enforcement**: حداکثر 50 ردیف  
✅ **Result display**: جدول HTML با اسکرول  
✅ **Traceability**: لاگ کامل تمام مراحل  
✅ **Error handling**: مدیریت خطا در تمام مراحل  
✅ **Retry mechanism**: امکان retry در SQL Critic  

---

## 📈 Performance

- **Context Loading**: ~100-500ms (بسته به حجم schema)
- **Reasoning Pipeline**: ~2-5s (بسته به مدل LLM)
- **SQL Execution**: ~100-1000ms (بسته به کوئری و دیتابیس)
- **Total**: ~3-7s برای یک درخواست کامل

---

## 🔧 Configuration

### Limit Configuration
```python
# backend/chat/engine/sql_pipeline.py
max_rows: int = 50  # حداکثر ردیف‌ها

# backend/db/connector.py
limit: int = 50  # محدودیت پیش‌فرض
```

### Prompt Configuration
```python
# backend/chat/engine/prompt_engine.py
PROMPT_VERSIONS = {
    "reasoning": "1.0.0",
    "sql": "1.1.0",
    "validation": "1.0.0"
}
```

---

## 📚 منابع

- [SQL Server Syntax Rules](backend/chat/engine/prompt_engine.py#L776)
- [Semantic Guard Rules](backend/chat/engine/sql_pipeline.py#L615)
- [Frontend Table Display](frontend/components/chat/chat-message.tsx#L299)

---

**آخرین به‌روزرسانی:** 2024
**نسخه:** 2.0.0
