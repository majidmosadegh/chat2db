# فلو فنی کامل چت بات (Complete Chat Bot Technical Flow)

## 📋 نمای کلی

این مستند فلو فنی کامل چت بات را از ورودی کاربر تا خروجی نهایی شرح می‌دهد.

---

## 🔄 فلو اصلی (Main Flow)

```
┌─────────────────────────────────────────────────────────────────┐
│                    1. ورودی کاربر (User Input)                  │
│              POST /api/chat/execute                             │
│              ChatRequest: {question, snapshot_id, model_id, ...}│
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              2. Router (backend/chat/router.py)                 │
│              - دریافت request                                    │
│              - بررسی/ایجاد ChatSession                           │
│              - بارگذاری تنظیمات Bot                             │
│              - ذخیره پیام کاربر در دیتابیس                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│        3. ChatEngine (backend/chat/engine/chat_engine.py)        │
│        process_chat_request()                                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌──────────────────────┐          ┌──────────────────────┐
│  3.1. ContextLoader   │          │  3.2. Conversation   │
│  load_context()       │          │  History Loading      │
│                       │          │                      │
│  - Schema Info        │          │  - از دیتابیس        │
│  - Data Dictionary    │          │  - یا از Memory      │
│  - Relationships      │          │                      │
│  - Use Cases          │          │                      │
└───────────┬───────────┘          └───────────┬──────────┘
            │                                   │
            └───────────┬───────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│      4. SQLPipeline (backend/chat/engine/sql_pipeline.py)        │
│      process_sql_with_reasoning_pipeline()                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌──────────────────────┐          ┌──────────────────────┐
│  4.1. Reasoning       │          │  4.2. SQL Pipeline   │
│  Pipeline (3-Stage)   │          │                      │
│                       │          │                      │
│  Stage A: Intent      │          │  - Semantic Guard     │
│    Detection          │          │  - SQL Critic         │
│                       │          │  - SQL Validator     │
│  Stage B: Table       │          │  - SQL Executor       │
│    Selection          │          │                      │
│                       │          │                      │
│  Stage C: SQL         │          │                      │
│    Generation         │          │                      │
└───────────┬───────────┘          └───────────┬──────────┘
            │                                   │
            └───────────┬───────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              5. Response Generation                              │
│              - ساخت ChatResponse                                 │
│              - ذخیره پیام Assistant در دیتابیس                   │
│              - به‌روزرسانی آمار Session و Bot                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    6. خروجی (Response)                           │
│              ChatResponse: {sql, rows, metadata, ...}            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ جزئیات مراحل

### مرحله 1: Router (`backend/chat/router.py`)

**Endpoint:** `POST /api/chat/execute`

**وظایف:**
1. دریافت `ChatRequest` از کاربر
2. بررسی وجود `conversation_id` و بارگذاری `ChatSession`
3. بارگذاری تنظیمات `ChatBot` (snapshot_id, model_id, language)
4. ذخیره پیام کاربر در `ChatMessage`
5. ایجاد `DatabaseConnector` برای snapshot
6. فراخوانی `ChatEngine.process_chat_request()`
7. ذخیره پاسخ Assistant در دیتابیس
8. به‌روزرسانی آمار Session و Bot

**کد کلیدی:**
```python
# دریافت session
chat_session_db = await get_chat_session(conversation_id)

# بارگذاری bot settings
bot = await get_chat_bot(chat_session_db.bot_id)
effective_snapshot_id = bot.snapshot_id
effective_model_id = bot.model_id

# ایجاد connector و engine
connector = await get_database_connector(effective_snapshot_id, session)
chat_engine = ChatEngine(session, connector)

# پردازش request
response = await chat_engine.process_chat_request(chat_request)
```

---

### مرحله 2: ChatEngine (`backend/chat/engine/chat_engine.py`)

**کلاس اصلی:** `ChatEngine`

**اجزا:**
- `ContextLoader`: بارگذاری context از metadata
- `PromptEngine`: ساخت prompt‌ها برای LLM
- `LLMGateway`: رابط با مدل‌های LLM
- `SQLPipeline`: pipeline کامل SQL
- `ConversationStateManager`: مدیریت state مکالمه

**متد اصلی:** `process_chat_request()`

**جریان کار:**
1. بارگذاری Context (Schema, Dictionary, Relationships, Use Cases)
2. بارگذاری Conversation History از دیتابیس
3. فراخوانی SQLPipeline برای پردازش
4. مدیریت پاسخ‌های Conversational (CONVERSATIONAL intent)
5. به‌روزرسانی Conversation State
6. ساخت و برگرداندن ChatResponse

**کد کلیدی:**
```python
# بارگذاری context
context = await self.context_loader.load_context(request.snapshot_id)

# بارگذاری history
conversation_history = await self.conversation_manager.get_conversation_history(
    conversation_id
)

# پردازش با pipeline
pipeline_result = await self.sql_pipeline.process_sql_with_reasoning_pipeline(
    context=context,
    question=request.user_question,
    language=request.language,
    model_id=request.selected_model_id,
    conversation_history=conversation_history
)
```

---

### مرحله 3: ContextLoader (`backend/chat/engine/context_loader.py`)

**کلاس:** `ContextLoader`

**وظیفه:** بارگذاری و تجمیع اطلاعات context از دیتابیس metadata

**اطلاعات بارگذاری شده:**

#### Schema Info
```python
SchemaInfo:
  - schema_name: str
  - table_name: str
  - column_name: str
  - column_type: str
  - is_primary_key: bool
  - is_foreign_key: bool
  - foreign_key_table: Optional[str]
  - foreign_key_column: Optional[str]
```

#### Data Dictionary
```python
DataDictionaryInfo:
  - schema_name: str
  - table_name: str
  - column_name: Optional[str]
  - description: Optional[str]
  - example_values: Optional[str]  # JSON array
  - synonyms: Optional[str]
  - is_sensitive: bool
```

#### Relationships
```python
RelationshipInfo:
  - source_table: str
  - source_column: str
  - target_table: str
  - target_column: str
  - relationship_type: str
  - join_type: str
  - cardinality: str
  - description: str
  - confidence_score: Optional[float]
```

#### Use Cases
```python
UseCaseInfo:
  - name: str
  - business_goal: str
  - example_questions: List[str]
  - example_queries: Optional[List[str]]
  - output_style: str
```

**خروجی:** `ChatContext` (immutable object با context_hash)

---

### مرحله 4: SQLPipeline (`backend/chat/engine/sql_pipeline.py`)

**کلاس:** `SQLPipeline`

**متد اصلی:** `process_sql_with_reasoning_pipeline()`

#### 4.1. Reasoning Pipeline (3-Stage)

**Stage A: Intent Detection**
- تشخیص قصد کاربر (CONVERSATIONAL, COUNT, AGGREGATION, LIST, TOP_N, DETAIL, COMPARISON)
- استفاده از `PromptEngine._execute_intent_detection()`
- خروجی: `{"intent": "...", "confidence": 0.8}`

**Stage B: Table Selection**
- انتخاب جداول مرتبط با سوال
- استفاده از `PromptEngine._execute_table_selection()`
- خروجی: `{"tables": [...], "required_columns": [...], "filters": [...]}`

**Stage C: SQL Generation**
- تولید SQL بر اساس intent و tables_info
- استفاده از `PromptEngine._execute_sql_generation()`
- استفاده از `QueryPlanner` برای ساخت query plan
- خروجی: `{"sql": "...", "query_plan": {...}, "confidence": 0.8, "business_value": "..."}`

**کد کلیدی:**
```python
# اجرای reasoning pipeline
reasoning_result = await self.prompt_engine.execute_reasoning_pipeline(
    llm_gateway, context, question, language, model_id, conversation_history
)

intent = reasoning_result.get("intent")
tables_info = reasoning_result.get("tables_info")
sql_from_reasoning = reasoning_result.get("sql")
```

#### 4.2. SQL Processing Pipeline

**Stage 1: Semantic Guard**
- اعمال قوانین معنایی بر اساس intent
- بررسی TOP/LIMIT برای COUNT/AGGREGATION
- بررسی WHERE برای DETAIL
- خروجی: `{"is_valid": bool, "violations": [...], "corrected_sql": "..."}`

**Stage 2: SQL Critic**
- نقد و بررسی SQL از نظر معنایی
- تلاش برای بهبود SQL در صورت نیاز (max 2 retry)
- خروجی: `{"sql": "...", "critique_result": "...", "attempts": [...]}`

**Stage 3: SQL Validator**
- اعتبارسنجی SQL از نظر امنیت و صحت
- تبدیل SQL برای سازگاری با نوع دیتابیس (SQL Server, PostgreSQL, MySQL)
- بررسی read-only بودن
- خروجی: `SQLValidationResult`

**Stage 4: SQL Executor**
- اجرای SQL روی snapshot database
- محدودیت: حداکثر 50 ردیف
- خروجی: `SQLExecutionResult`

**کد کلیدی:**
```python
# Semantic Guard
guard_result = self.semantic_guard.enforce_rules(sql_from_reasoning, intent, context)

# SQL Critic
critic_result = await self.critic.critique_and_improve_sql(
    sql_after_guard, context, question, intent, tables_info, language, model_id
)

# SQL Validator
validation_result = self.validator.validate_sql(final_sql, context)

# SQL Executor
execution_result = await self.executor.execute_sql(sql_to_execute, max_rows=50)
```

---

### مرحله 5: PromptEngine (`backend/chat/engine/prompt_engine.py`)

**کلاس:** `PromptEngine`

**وظایف:**
1. ساخت prompt‌های versioned و deterministic
2. اجرای 3-stage reasoning pipeline
3. ساخت prompt‌های SQL generation با sample data
4. مدیریت template‌های مختلف (انگلیسی/فارسی)

**متدهای کلیدی:**
- `execute_reasoning_pipeline()`: اجرای کامل pipeline
- `build_sql_generation_prompt_with_json_output()`: ساخت prompt با JSON output
- `build_sql_generation_prompt_with_sample_data()`: ساخت prompt با sample data

**ویژگی‌ها:**
- پشتیبانی از چندین نوع دیتابیس (SQL Server, PostgreSQL, MySQL)
- استفاده از sample data از data dictionary
- ساخت query plan با QueryPlanner
- محاسبه confidence و business_value

---

### مرحله 6: LLMGateway (`backend/chat/engine/llm_gateway.py`)

**کلاس:** `LLMGateway`

**وظیفه:** رابط انتزاعی با مدل‌های LLM

**متد اصلی:** `call_llm()`

**ویژگی‌ها:**
- استفاده از `LLMService` برای ارتباط با مدل‌ها
- مدیریت error handling
- logging کامل
- خروجی: `LLMResponse`

---

### مرحله 7: ConversationStateManager (`backend/chat/engine/conversation_state.py`)

**کلاس:** `ConversationStateManager`

**وظایف:**
1. مدیریت state مکالمه (in-memory)
2. بارگذاری history از دیتابیس
3. به‌روزرسانی state بعد از هر query

**متدهای کلیدی:**
- `get_conversation_history()`: بارگذاری history از دیتابیس یا memory
- `update_conversation_state()`: به‌روزرسانی state
- `cleanup_expired_states()`: پاک‌سازی state‌های منقضی شده

**ویژگی‌ها:**
- TTL برای state‌ها (24 ساعت پیش‌فرض)
- بارگذاری از دیتابیس با fallback به memory
- مدیریت حداکثر تعداد entries

---

## 🔄 فلو کامل با جزئیات

### 1. دریافت Request
```
User → POST /api/chat/execute
     → ChatRequest {
         user_question: "قیمت قیر 6070 چقدر است؟",
         snapshot_id: 1,
         selected_model_id: 1,
         language: "persian",
         conversation_id: "uuid-123"
       }
```

### 2. Router Processing
```
Router:
  ├─ دریافت ChatRequest
  ├─ بارگذاری ChatSession از دیتابیس
  ├─ بارگذاری ChatBot settings
  ├─ ذخیره پیام کاربر در ChatMessage
  └─ ایجاد ChatEngine
```

### 3. ChatEngine Processing
```
ChatEngine.process_chat_request():
  ├─ ContextLoader.load_context()
  │   ├─ بارگذاری SchemaMetadata
  │   ├─ بارگذاری DataDictionary
  │   ├─ بارگذاری Relationships
  │   └─ بارگذاری UseCases
  │
  ├─ ConversationStateManager.get_conversation_history()
  │   ├─ تلاش برای بارگذاری از دیتابیس
  │   └─ Fallback به memory state
  │
  └─ SQLPipeline.process_sql_with_reasoning_pipeline()
```

### 4. Reasoning Pipeline
```
Stage A: Intent Detection
  ├─ ساخت intent detection prompt
  ├─ فراخوانی LLM
  └─ خروجی: {"intent": "DETAIL", "confidence": 0.9}

Stage B: Table Selection
  ├─ ساخت table selection prompt
  ├─ فراخوانی LLM
  └─ خروجی: {
       "tables": [{"table": "dbo.Products", "reason": "..."}],
       "required_columns": ["Price", "ProductName"],
       "filters": ["ProductName"]
     }

Stage C: SQL Generation
  ├─ ساخت QueryPlan با QueryPlanner
  ├─ استخراج sample filters از dictionary
  ├─ ساخت SQL generation prompt با JSON output
  ├─ فراخوانی LLM
  └─ خروجی: {
       "sql": "SELECT TOP 50 [Price] FROM [dbo].[Products] WHERE [ProductName] = N'قیر 6070'",
       "query_plan": {...},
       "confidence": 0.85,
       "business_value": "..."
     }
```

### 5. SQL Processing Pipeline
```
Semantic Guard:
  ├─ بررسی قوانین معنایی
  └─ خروجی: {"is_valid": true, "violations": [], "corrected_sql": "..."}

SQL Critic:
  ├─ نقد SQL از نظر معنایی
  ├─ تلاش برای بهبود (max 2 retry)
  └─ خروجی: {"sql": "...", "critique_result": "passed", "attempts": [...]}

SQL Validator:
  ├─ تبدیل SQL برای سازگاری با دیتابیس
  ├─ بررسی read-only بودن
  ├─ اعتبارسنجی schema
  └─ خروجی: SQLValidationResult

SQL Executor:
  ├─ اجرای SQL روی snapshot database
  ├─ محدودیت: max 50 rows
  └─ خروجی: SQLExecutionResult {
       rows: [...],
       row_count: 1,
       truncated: false,
       success: true
     }
```

### 6. Response Generation
```
ChatResponse:
  ├─ success: true
  ├─ generated_sql: "SELECT TOP 50 [Price] FROM [dbo].[Products] WHERE [ProductName] = N'قیر 6070'"
  ├─ rows: [{"Price": 1500000}]
  ├─ row_count: 1
  ├─ execution_status: "success"
  ├─ context_hash: "abc123..."
  ├─ sql_validation_status: "passed"
  ├─ execution_time_ms: 250
  └─ conversation_id: "uuid-123"
```

### 7. Database Persistence
```
Router:
  ├─ ذخیره ChatMessage (assistant) در دیتابیس
  ├─ به‌روزرسانی ChatSession.message_count
  ├─ به‌روزرسانی ChatSession.last_activity_at
  ├─ به‌روزرسانی ChatBot.total_message_count
  └─ به‌روزرسانی ChatBot.last_activity_at
```

---

## 🔒 امنیت و اعتبارسنجی

### SQL Guard
- فقط SELECT queries مجاز
- جلوگیری از DROP, DELETE, UPDATE, INSERT
- بررسی read-only بودن

### SQL Validator
- تبدیل SQL برای سازگاری با نوع دیتابیس
- بررسی استفاده از جداول/ستون‌های موجود در schema
- اعتبارسنجی syntax

### Semantic Guard
- اعمال قوانین معنایی بر اساس intent
- تصحیح خودکار SQL (مثلاً حذف TOP از COUNT queries)

---

## 📊 Logging و Observability

### Log Points
- `🔄 CHAT_REQUEST_START`: شروع request
- `📚 CONTEXT_LOADED`: بارگذاری context
- `🧠 REASONING_START`: شروع reasoning pipeline
- `✅ STAGE_1_COMPLETE`: تکمیل reasoning
- `🛡️ STAGE_2_START`: شروع semantic guard
- `🔍 STAGE_3_START`: شروع SQL critic
- `✅ STAGE_4_START`: شروع validation
- `⚡ STAGE_5_START`: شروع execution
- `🎉 PIPELINE_COMPLETE`: تکمیل pipeline

### Metrics
- زمان هر stage
- تعداد errors
- confidence scores
- تعداد rows برگشتی

---

## 🎯 مدیریت خطا

### Error Handling Strategy
1. **Context Loading Errors**: برگرداندن error response با context خالی
2. **LLM Errors**: Fallback به default responses
3. **SQL Validation Errors**: برگرداندن error با جزئیات validation
4. **SQL Execution Errors**: برگرداندن error با message پاک شده (بدون اطلاعات حساس)

### Error Response Format
```python
ChatResponse(
    success=False,
    error_message="...",
    execution_status="error",
    sql_validation_status="failed"
)
```

---

## 🔄 مدیریت مکالمه (Conversation Management)

### Conversation History Loading
1. تلاش برای بارگذاری از دیتابیس (`ChatMessage`)
2. Fallback به in-memory state
3. محدودیت: آخرین N پیام (پیش‌فرض: 10)

### Conversation State
- `last_intent`: آخرین intent تشخیص داده شده
- `last_tables`: آخرین جداول استفاده شده
- `last_sql`: آخرین SQL تولید شده
- `last_result_summary`: خلاصه نتایج

---

## 📝 خلاصه

فلو فنی چت بات شامل مراحل زیر است:

1. **Router**: دریافت request و مدیریت session
2. **ChatEngine**: هماهنگی کلی فرآیند
3. **ContextLoader**: بارگذاری context از metadata
4. **Reasoning Pipeline**: تشخیص intent، انتخاب جداول، تولید SQL
5. **SQL Pipeline**: اعتبارسنجی، نقد، و اجرای SQL
6. **Response**: ساخت و برگرداندن پاسخ
7. **Persistence**: ذخیره در دیتابیس

همه مراحل با logging کامل، error handling، و observability پیاده‌سازی شده‌اند.

