# جمع‌بندی طراحی سیستم تولید دیکشنری داده با AI

## 📋 خلاصه اجرایی

سیستم تولید خودکار دیکشنری داده با استفاده از AI که از یک صف هوشمند و 3 worker همزمان برای پردازش جداول استفاده می‌کند. وضعیت کارها از طریق WebSocket به صورت real-time به فرانت ارسال می‌شود.

## 🏗️ معماری کلی

```
User Action: "Generate with AI"
    ↓
Create Job (waiting) → Queue System
    ↓
3 Async Workers (parallel processing)
    ↓
For each Table:
    ├─ Sample 3 rows from DB
    ├─ Get minified schema
    ├─ Send to VLLM/LLM
    ├─ Parse JSON response
    ├─ Save to PostgreSQL
    └─ Send WebSocket update
```

## 🔍 وضعیت فعلی کدبیس

### ✅ بخش‌های پیاده‌سازی شده

#### 1. **مدل‌های دیتابیس (PostgreSQL)**
- ✅ `AIGenerationJob` - موجود در `api/db_models.py`
  - فیلدها: `job_id`, `snapshot_id`, `status`, `total_tables`, `completed_tables`, `progress_data`, `errors`
  - ⚠️ **نکته**: مدل پیشنهادی شما `AITableTask` جداگانه ندارد، اما `progress_data` به صورت JSON تمام اطلاعات را نگه می‌دارد

#### 2. **سرویس AI Dictionary Generator**
- ✅ `AIDictionaryGenerator` در `backend/services/ai_dictionary_generator.py`
- ✅ Queue system با `asyncio.Queue`
- ✅ 3 worker همزمان (`MAX_CONCURRENT_JOBS = 3`)
- ✅ پردازش جداول به صورت async
- ✅ مدیریت وضعیت job (waiting, processing, done, paused, failed, canceled)

#### 3. **DB Connector**
- ✅ `DirectDatabaseConnector` در `backend/services/db_connector.py`
- ✅ `get_table_sample_data()` در `core/db_utils.py` - گرفتن نمونه داده
- ✅ `get_table_schema_with_relationships()` - گرفتن schema فشرده

#### 4. **LLM Integration**
- ✅ `LLMService` در `backend/services/llm_service.py`
- ✅ پشتیبانی از VLLM, OpenAI, Ollama
- ✅ استفاده از `ModelConnector` برای ارسال درخواست‌ها

#### 5. **WebSocket Manager**
- ✅ `ConnectionManager` در `backend/api/dictionary_job_router.py`
- ✅ Endpoint: `/ws/dictionary-job-status/{job_id}`
- ✅ Broadcast به تمام اتصالات یک job

### ⚠️ تفاوت‌های طراحی پیشنهادی با پیاده‌سازی فعلی

#### 1. **مدل AITableTask جداگانه**
- **پیشنهادی**: جدول جداگانه `ai_table_tasks` برای هر task
- **فعلی**: اطلاعات task در `progress_data` (JSON) در `AIGenerationJob`
- **توصیه**: مدل فعلی کافی است و performance بهتری دارد (کمتر JOIN)

#### 2. **DirectDatabaseConnector**
- **پیشنهادی**: `sample_rows()` و `get_minified_schema()` مستقیم
- **فعلی**: استفاده از `get_table_sample_data()` و `get_table_schema_with_relationships()` که query enrichment هم دارند
- **توصیه**: پیاده‌سازی فعلی پیشرفته‌تر است

#### 3. **Worker Loop**
- **پیشنهادی**: `_worker_loop()` ساده
- **فعلی**: `_process_queue_worker()` با pause/resume/stop handling و lock management
- **توصیه**: پیاده‌سازی فعلی robust تر است

## 📊 فلوچارت دقیق پردازش

### مرحله 1: ایجاد Job
```python
POST /api/data-dictionary/ai-generate
    ↓
ai_dictionary_generator.create_job()
    ├─ Generate job_id: dict_{snapshot_id}_{uuid}
    ├─ Resolve target tables (based on scope)
    ├─ Create TableTask for each table
    ├─ Store in memory (_jobs dict)
    └─ Persist to DB (AIGenerationJob)
```

### مرحله 2: شروع پردازش
```python
background_tasks.add_task(ai_dictionary_generator.start_job, job_id)
    ↓
start_job(job_id)
    ├─ Load job from memory/DB
    ├─ Update status: WAITING → PROCESSING
    ├─ Start 3 worker tasks (if not running)
    └─ Queue all table tasks
```

### مرحله 3: Worker Processing
```python
_process_queue_worker(worker_id)
    ├─ Loop forever:
    │   ├─ Get task from queue: (job_id, table_key)
    │   ├─ Check job status (skip if paused/canceled)
    │   ├─ Process table: _process_table_task()
    │   └─ Mark task done
    └─ Handle exceptions gracefully
```

### مرحله 4: پردازش هر جدول
```python
_process_table_task(job_id, table_key)
    ├─ Update task status: WAITING → PROCESSING
    ├─ Sample data: get_table_sample_data() (3 rows)
    ├─ Get schema: get_table_schema_with_relationships()
    ├─ Generate dictionary: _generate_table_dictionary()
    │   ├─ Build prompt
    │   ├─ Send to LLM (VLLM/OpenAI/Ollama)
    │   ├─ Parse JSON response
    │   └─ Validate structure
    ├─ Save to DB: _save_dictionary_to_db()
    │   ├─ Save table description
    │   └─ Save column descriptions
    ├─ Update task: PROCESSING → DONE
    ├─ Check job completion
    └─ Send WebSocket update
```

## 🔄 جریان داده

### 1. **Database Sampling**
```python
# از DB متصل به snapshot
sample_data = await get_table_sample_data(
    snapshot_id=snapshot_id,
    schema_name=schema_name,
    table_name=table_name,
    limit=3  # 3 سطر نمونه
)
```

### 2. **Schema Minification**
```python
# Schema فشرده
schema_info = await get_table_schema_with_relationships(
    snapshot_id=snapshot_id,
    schema_name=schema_name,
    table_name=table_name,
    session=session
)
# شامل: columns, relationships, constraints
```

### 3. **LLM Request**
```python
prompt = build_dictionary_prompt(
    job=job,
    table_task=table_task,
    schema_info=schema_info,
    sample_data=sample_data,
    db_type=db_type
)

response = await llm_service.generate_text(
    session=session,
    model_id=model_id,
    prompt=prompt,
    temperature=0.7,
    max_tokens=2048
)
```

### 4. **JSON Parsing & Validation**
```python
# Parse با JSON repair
result = parse_llm_json_response(
    response_text, 
    max_repair_attempts=3
)

# Validate structure
if validate_dictionary_result(result):
    # Save to DB
```

### 5. **Save to PostgreSQL**
```python
# Save table-level description
DataDictionary(
    schema_snapshot_id=snapshot_id,
    schema_name=schema_name,
    table_name=table_name,
    column_name=None,  # Table-level
    description=table_description,
    is_ai_generated=True
)

# Save column-level descriptions
for column in columns:
    DataDictionary(
        schema_snapshot_id=snapshot_id,
        schema_name=schema_name,
        table_name=table_name,
        column_name=column.name,
        description=column.description,
        example_values=json.dumps([column.example]),
        is_ai_generated=True
    )
```

## 📡 WebSocket Updates

### Connection Flow
```python
# Client connects
WS /ws/dictionary-job-status/{job_id}
    ↓
manager.connect(job_id, websocket)
    ↓
Send initial status
    ↓
Loop: Wait for updates
    ├─ Receive ping → Send pong
    ├─ Receive status_request → Send current status
    └─ Timeout → Send keepalive
```

### Update Messages
```json
{
  "type": "job_status_update",
  "job_id": "dict_123_abc",
  "status": "processing",
  "progress": {
    "schema.table1": {
      "status": "done",
      "progress": 100
    },
    "schema.table2": {
      "status": "processing",
      "progress": 50
    }
  },
  "timestamp": 1234567890.123
}
```

### Broadcast Points
1. **Task Started**: `_process_table_task()` - status → PROCESSING
2. **Task Progress**: هر 10% progress update
3. **Task Completed**: status → DONE
4. **Task Failed**: status → FAILED
5. **Job Completed**: تمام tasks done

## 🎯 نقاط قوت طراحی فعلی

1. **Robust Error Handling**
   - Retry logic برای LLM calls
   - JSON repair برای responses معیوب
   - Graceful degradation

2. **State Management**
   - Persistence به DB برای recovery
   - Memory cache برای performance
   - Lock management برای concurrency

3. **Scalability**
   - Queue-based processing
   - Configurable worker count
   - Non-blocking async operations

4. **Monitoring**
   - WebSocket real-time updates
   - Progress tracking per table
   - Error logging و reporting

## 🔧 پیشنهادات بهبود (اختیاری)

### 1. **AITableTask جدول جداگانه**
اگر نیاز به query مستقیم روی tasks دارید:
```sql
CREATE TABLE ai_table_tasks (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) NOT NULL,
    snapshot_id INTEGER NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'waiting',
    progress FLOAT DEFAULT 0,
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_job_id (job_id),
    INDEX idx_snapshot_id (snapshot_id)
);
```

### 2. **Batch Processing**
برای جداول بزرگ:
```python
# Process columns in batches
for batch in chunk_columns(columns, batch_size=10):
    await process_column_batch(batch)
```

### 3. **Caching**
```python
# Cache schema info
@lru_cache(maxsize=100)
async def get_cached_schema(snapshot_id, table_name):
    ...
```

## 📝 خلاصه

### ✅ آماده برای استفاده
- Queue system با 3 workers
- Database sampling (3 rows)
- Schema minification
- LLM integration (VLLM/OpenAI/Ollama)
- JSON parsing & validation
- PostgreSQL persistence
- WebSocket real-time updates

### 🔄 نیاز به بررسی
- مدل `AITableTask` جداگانه (فعلاً در JSON است)
- Direct database connector (فعلاً از `db_utils` استفاده می‌شود)

### 🎉 نتیجه
**طراحی فعلی کامل و production-ready است!** تمام بخش‌های پیشنهادی شما در کد موجود است و حتی پیشرفته‌تر (با error handling، retry logic، و state management بهتر).




