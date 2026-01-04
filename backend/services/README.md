# AI Generation Service Architecture

## نمای کلی (Overview)

ماژول `AIGenerationService` یک سرویس asynchronous برای تولید فرهنگ داده (Data Dictionary) با استفاده از هوش مصنوعی است. این سرویس امکان تولید توصیفات هوشمند برای جداول و ستون‌های پایگاه داده را فراهم می‌کند.

## معماری کلی (Architecture Overview)

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI       │────│ AIGeneration    │────│  ModelConnector │
│   Endpoint      │    │   Service       │    │   (LLM)         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌──────────────────┐
                    │   Database       │
                    │   (Jobs, Models,│
                    │    Dictionary)   │
                    └──────────────────┘
```

## اجزاء اصلی (Core Components)

### 1. کلاس AIGenerationService

کلاس اصلی سرویس که مسئولیت مدیریت چرخه حیات jobهای AI را بر عهده دارد.

#### ویژگی‌های کلیدی:
- **Singleton Pattern**: یک instance واحد برای کل اپلیکیشن
- **Asynchronous Processing**: استفاده از async/await برای عملیات غیرمستقیم
- **Error Handling**: مدیریت خطاها با logging مناسب
- **State Management**: پیگیری وضعیت jobها

### 2. متدهای اصلی (Main Methods)

#### `initialize_connector()`
```python
async def initialize_connector(self) -> ModelConnector
```
- **وظیفه**: راه‌اندازی اتصال به مدل‌های LLM
- **ورودی**: هیچ
- **خروجی**: شی ModelConnector آماده
- **جزئیات**:
  - بارگذاری مدل‌های فعال از پایگاه داده
  - تنظیم registry مدل‌ها
  - ایجاد اتصال به providerهای مختلف (OpenAI, Ollama, vLLM)

#### `start_generation_job()`
```python
async def start_generation_job(
    self,
    session: AsyncSession,
    snapshot_id: int,
    business_domain: str,
    database_description: str,
    target_user: str,
    language: str,
    optional_notes: str
) -> str
```
- **وظیفه**: ایجاد job جدید برای تولید AI
- **ورودی**: اطلاعات زمینه و تنظیمات
- **خروجی**: شناسه منحصر به فرد job
- **جزئیات**:
  - ایجاد رکورد AIGenerationJob در پایگاه داده
  - تنظیم وضعیت اولیه به "pending"
  - محاسبه تعداد کل جداول

#### `_process_generation_job()`
```python
async def _process_generation_job(self, job_id: str)
```
- **وظیفه**: اجرای job در پس‌زمینه
- **جزئیات**:
  - بروزرسانی وضعیت به "processing"
  - پردازش جداول یکی یکی
  - ذخیره نتایج در DataDictionary
  - مدیریت خطاها و بروزرسانی پیشرفت

#### `_generate_table_description()`
```python
async def _generate_table_description(
    self,
    connector: ModelConnector,
    session: AsyncSession,
    job_id: str,
    snapshot_id: int,
    schema_name: str,
    table_name: str,
    column_count: int,
    business_domain: str,
    ...
) -> str
```
- **وظیفه**: تولید توصیف برای یک جدول خاص
- **جزئیات**:
  - آماده‌سازی prompt
  - ارسال درخواست به LLM
  - پردازش پاسخ و ذخیره

#### `_create_generation_prompt()`
```python
def _create_generation_prompt(
    self,
    schema_name: str,
    table_name: str,
    columns: list,
    business_domain: str,
    ...
) -> str
```
- **وظیفه**: ایجاد prompt بهینه برای LLM
- **ویژگی‌ها**:
  - ساختاردهی اطلاعات زمینه
  - تنظیم زبان خروجی
  - فرمت‌دهی ستون‌ها

#### `get_job_status()`
```python
async def get_job_status(self, job_id: str) -> Dict[str, Any]
```
- **وظیفه**: دریافت وضعیت فعلی job
- **خروجی**: اطلاعات پیشرفت و خطاها

## جریان کاری (Workflow)

### 1. شروع Job (Job Initiation)
```
User Request → FastAPI Endpoint → start_generation_job()
                                      ↓
                               Create AIGenerationJob Record
                                      ↓
                               Background Task Created
```

### 2. پردازش پس‌زمینه (Background Processing)
```
Background Task → _process_generation_job()
                     ↓
              Update Status: "processing"
                     ↓
            Process Tables One by One
                     ↓
         _generate_table_description() for each table
                     ↓
            Save Results to DataDictionary
                     ↓
         Update Progress & Status
```

### 3. تولید توصیف (Description Generation)
```
Table Info → _create_generation_prompt()
                ↓
          Send to LLM via ModelConnector
                ↓
        Parse Response (JSON/Text)
                ↓
      Save Table & Column Descriptions
```

## مدل‌های داده (Data Models)

### AIGenerationJob
```python
class AIGenerationJob(Base):
    job_id: str (unique)
    snapshot_id: int
    status: str ("pending", "processing", "completed", "error")
    total_tables: int
    completed_tables: int
    current_table: str (nullable)
    progress_data: Text (JSON)
    errors: Text (JSON)
    created_at: DateTime
    updated_at: DateTime
```

### DataDictionary
```python
class DataDictionary(Base):
    snapshot_id: int
    schema_name: str
    table_name: str
    column_name: str (nullable)  # null برای توصیف جدول
    description: Text
    is_ai_generated: bool
    created_at: DateTime
```

## مدیریت خطا (Error Handling)

### انواع خطا:
1. **Model Initialization Errors**: عدم وجود مدل‌های فعال
2. **LLM API Errors**: مشکلات اتصال یا پاسخ API
3. **Parsing Errors**: مشکل در parse پاسخ JSON
4. **Database Errors**: مشکلات ذخیره‌سازی

### استراتژی مدیریت:
- Logging جامع در همه سطوح
- Fallback به plain text در صورت parse failure
- Atomic transactions برای database operations
- Graceful degradation برای partial failures

## تنظیمات و Configuration

### متغیرهای محیطی:
- `LLM_MODEL_TIMEOUT`: تایم‌اوت اتصال به مدل‌ها
- Database connection settings

### تنظیمات مدل:
- `is_active`: فعال بودن مدل
- `max_tokens`: حداکثر توکن خروجی
- Provider-specific settings

## مزایای معماری (Architecture Benefits)

### 1. **Scalability**
- Asynchronous processing
- Background task management
- Resource-efficient job queuing

### 2. **Reliability**
- Error recovery mechanisms
- Progress tracking
- Atomic operations

### 3. **Maintainability**
- Clean separation of concerns
- Modular design
- Comprehensive logging

### 4. **Extensibility**
- Easy addition of new LLM providers
- Configurable prompt templates
- Plugin-like model registry

## ملاحظات امنیتی (Security Considerations)

### 1. **API Key Management**
- Encrypted storage in database
- Runtime decryption only
- No logging of sensitive data

### 2. **Input Validation**
- Sanitization of table/schema names
- SQL injection prevention
- Safe JSON parsing

### 3. **Rate Limiting**
- Controlled API calls to LLM services
- Queue management for concurrent jobs

## مانیتورینگ و Debugging

### 1. **Logging Levels**
- `INFO`: Job lifecycle events
- `WARNING`: Parse failures, recoverable errors
- `ERROR`: Critical failures, API errors

### 2. **Metrics**
- Job completion rates
- Processing times per table
- Error rates by model/provider

### 3. **Debugging Tools**
- Job status API endpoint
- Progress tracking in database
- Structured error reporting

## بهبودهای آینده (Future Improvements)

### 1. **Performance**
- Batch processing for multiple tables
- Caching of model connections
- Parallel processing within jobs

### 2. **Features**
- Custom prompt templates per domain
- Multi-language support beyond Persian
- Integration with vector databases for context

### 3. **Monitoring**
- Real-time dashboards
- Alerting system for failures
- Performance metrics collection

## نتیجه‌گیری (Conclusion)

معماری `AIGenerationService` یک راه‌حل robust و scalable برای تولید فرهنگ داده با استفاده از LLMها ارائه می‌دهد. طراحی asynchronous، error handling جامع، و separation of concerns باعث می‌شود این ماژول قابل اعتماد و نگهداری باشد.









