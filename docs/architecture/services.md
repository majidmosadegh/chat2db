# معماری ماژول Services

## نمای کلی (Overview)

ماژول **Services** لایه منطق کسب‌وکار (Business Logic Layer) پلتفرم SQL PT است که سرویس‌های اصلی سیستم را پیاده‌سازی می‌کند. این ماژول مسئولیت اجرای عملیات پیچیده مانند تولید فرهنگ داده با AI، مدیریت مدل‌های زبانی، و اتصال به پایگاه داده را بر عهده دارد.

## معماری کلی (Architecture Overview)

```
┌─────────────────────────────────────────────────────────────┐
│                    Services Layer                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Business Logic Services                │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │AI Dictionary│   LLM       │   Database      │    │    │
│  │  │  Service    │  Service    │   Connector     │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Supporting Services & Utilities          │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │AI Dictionary│   Prompt    │   Types &       │    │    │
│  │  │   Parser    │   Builder   │   Schemas       │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────┘
                      │
           ┌──────────┴──────────┐
           │   Database Layer    │
           │   (Persistence)     │
           └─────────────────────┘
```

## اجزاء اصلی (Core Components)

### 1. AIGenerationService (سرویس تولید فرهنگ داده)

سرویس اصلی تولید فرهنگ داده با استفاده از هوش مصنوعی:

#### معماری داخلی:
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
                    │   (Jobs, Models, │
                    │    Dictionary)   │
                    └──────────────────┘
```

#### ویژگی‌های کلیدی:
- **Singleton Pattern**: یک instance واحد برای کل اپلیکیشن
- **Asynchronous Processing**: استفاده از async/await برای عملیات غیرمستقیم
- **Background Job Management**: مدیریت jobهای طولانی‌مدت
- **Progress Tracking**: پیگیری پیشرفت تولید فرهنگ داده

#### متدهای اصلی:

##### `start_generation_job()`
```python
async def start_generation_job(
    self,
    session: AsyncSession,
    snapshot_id: int,
    business_domain: str,
    ...
) -> str
```
- ایجاد job جدید برای تولید AI
- تنظیم وضعیت اولیه به "pending"
- محاسبه تعداد کل جداول

##### `_process_generation_job()`
```python
async def _process_generation_job(self, job_id: str)
```
- اجرای job در پس‌زمینه
- پردازش جداول یکی یکی
- ذخیره نتایج در DataDictionary

##### `_generate_table_description()`
```python
async def _generate_table_description(
    self,
    connector: ModelConnector,
    session: AsyncSession,
    ...
) -> str
```
- تولید توصیف برای یک جدول خاص
- آماده‌سازی prompt و ارسال به LLM

### 2. LLMService (سرویس مدل‌های زبانی)

سرویس unified برای مدیریت همه عملیات LLM:

#### ویژگی‌ها:
- **Model Connector Management**: مدیریت اتصال به مدل‌های مختلف
- **Caching & Reuse**: استفاده مجدد از connectorها
- **Error Handling**: مدیریت خطاهای API
- **Cost Tracking**: مانیتورینگ هزینه‌ها

#### ارائه‌دهندگان پشتیبانی شده:
- **OpenAI**: GPT-3.5, GPT-4
- **Ollama**: مدل‌های local
- **vLLM**: مدل‌های optimized
- **Custom Providers**: امکان افزودن provider جدید

#### متدهای کلیدی:
```python
async def generate_text(
    self,
    session: AsyncSession,
    model_id: int,
    prompt: str,
    temperature: float = 0.7
) -> LLMResponse
```

### 3. Database Connector Service

سرویس اتصال به پایگاه داده‌های مختلف:

#### پشتیبانی از پایگاه داده‌ها:
- **PostgreSQL**: asyncpg driver
- **MySQL**: aiomysql driver
- **SQL Server**: pyodbc driver
- **SQLite**: برای development

#### قابلیت‌ها:
- **Connection Pooling**: مدیریت pool اتصالات
- **Transaction Management**: مدیریت تراکنش‌ها
- **Error Handling**: مدیریت خطاهای اتصال
- **Security**: رمزگذاری اطلاعات اتصال

## سرویس‌های کمکی (Supporting Services)

### 1. AI Dictionary Parser

پردازش و تجزیه پاسخ‌های LLM برای فرهنگ داده:

#### وظایف:
- **JSON Parsing**: تجزیه پاسخ‌های ساختار یافته
- **Fallback Handling**: مدیریت پاسخ‌های plain text
- **Data Validation**: اعتبارسنجی داده‌های استخراج شده
- **Error Recovery**: بازیابی از خطاهای parsing

### 2. AI Dictionary Prompt Builder

ساخت promptهای بهینه برای تولید فرهنگ داده:

#### قابلیت‌ها:
- **Dynamic Prompt Generation**: ساخت prompt بر اساس زمینه
- **Multi-language Support**: پشتیبانی از زبان‌های مختلف
- **Context Integration**: ادغام اطلاعات schema و business
- **Template Management**: مدیریت templateهای prompt

### 3. Types & Schemas

تعاریف نوع داده و schemaهای مشترک:

#### مدل‌های داده کلیدی:
```python
class TableDescription(BaseModel):
    table_name: str
    description: str
    column_descriptions: List[ColumnDescription]

class ColumnDescription(BaseModel):
    column_name: str
    data_type: str
    description: str
    is_nullable: bool
    constraints: List[str]
```

## جریان کاری (Workflow)

### تولید فرهنگ داده (AI Dictionary Generation):

```
1. دریافت درخواست تولید فرهنگ داده
   ↓
2. ایجاد AIGenerationJob در پایگاه داده
   ├─ تنظیم وضعیت به "pending"
   ├─ محاسبه تعداد جداول
   └─ تولید job_id منحصر به فرد
   ↓
3. شروع پردازش پس‌زمینه
   ├─ بروزرسانی وضعیت به "processing"
   └─ شروع پردازش جداول
   ↓
4. پردازش هر جدول
   ├─ بارگذاری اطلاعات ستون‌ها
   ├─ ساخت prompt تخصصی
   ├─ ارسال به LLM
   ├─ تجزیه پاسخ
   └─ ذخیره در DataDictionary
   ↓
5. بروزرسانی پیشرفت و تکمیل job
   ├─ محاسبه درصد پیشرفت
   ├─ مدیریت خطاها
   └─ تنظیم وضعیت نهایی
```

### عملیات LLM:

```
1. دریافت درخواست تولید متن
   ↓
2. بررسی initialization سرویس
   ├─ بارگذاری مدل‌های فعال از DB
   ├─ تنظیم registry
   └─ ایجاد connector
   ↓
3. ساخت LLMRequest
   ├─ تنظیم پارامترها (temperature, max_tokens)
   ├─ اضافه کردن system prompt
   └─ تنظیم user message
   ↓
4. ارسال به ModelConnector
   ├─ انتخاب provider مناسب
   ├─ مدیریت rate limiting
   ├─ error handling و retry
   ↓
5. بازگرداندن پاسخ
   ├─ استخراج متن تولید شده
   ├─ محاسبه metadata (tokens, cost)
   └─ لاگ‌گیری عملیات
```

## مدیریت خطا (Error Handling)

### انواع خطا:
1. **Model Initialization Errors**: عدم وجود مدل‌های فعال
2. **API Errors**: مشکلات اتصال به LLM providers
3. **Parsing Errors**: مشکل در تجزیه پاسخ JSON
4. **Database Errors**: مشکلات ذخیره‌سازی
5. **Validation Errors**: داده‌های نامعتبر

### استراتژی مدیریت:
- **Logging جامع**: ثبت همه خطاها با context
- **Fallback Mechanisms**: استفاده از fallback در صورت خطا
- **Atomic Operations**: استفاده از تراکنش‌ها برای consistency
- **Graceful Degradation**: ادامه کار با قابلیت‌های محدود

## امنیت و رمزگذاری (Security & Encryption)

### 1. **API Key Management**
- رمزگذاری کلیدهای API با Fernet
- ذخیره امن در پایگاه داده
- رمزگشایی runtime-only

### 2. **Database Connection Security**
- رمزگذاری پسوردها و connection strings
- استفاده از secure protocols
- Audit logging برای دسترسی‌ها

### 3. **Input Validation**
- Sanitization همه ورودی‌ها
- SQL injection prevention
- Schema validation برای داده‌ها

## مانیتورینگ و Logging

### انواع لاگ:
- **Job Lifecycle**: شروع، پیشرفت، تکمیل jobها
- **API Calls**: تمام ارتباطات با LLM providers
- **Errors**: خطاها با جزئیات کامل
- **Performance**: زمان اجرای عملیات

### Metrics:
- تعداد jobهای فعال
- نرخ موفقیت تولید فرهنگ داده
- هزینه‌های API
- زمان پاسخگویی سرویس‌ها

## قابلیت توسعه (Extensibility)

### افزودن LLM Provider جدید:
```python
class NewProvider(LLMProvider):
    def prepare_request(self, prompt: str) -> Dict:
        return {"input": prompt, "parameters": {...}}

    def parse_response(self, response: Dict) -> str:
        return response["generated_text"]
```

### افزودن سرویس جدید:
```python
class NewBusinessService:
    def __init__(self, db_session: AsyncSession):
        self.session = db_session

    async def perform_business_operation(self, data: Dict) -> Result:
        # Business logic implementation
        pass
```

## تنظیمات و Configuration

### متغیرهای محیطی:
```
LLM_MODEL_TIMEOUT=1200
AI_DICTIONARY_BATCH_SIZE=5
MAX_CONCURRENT_JOBS=3
ENCRYPTION_KEY_FILE=encryption_key.txt
```

### Database Configuration:
- Model provider settings
- Job queue limits
- Cache TTL values
- Error retry policies

## مزایای معماری (Architecture Benefits)

### 1. **Separation of Concerns**
- هر سرویس مسئولیت مشخصی دارد
- قابلیت تست مستقل کامپوننت‌ها
- نگهداری و توسعه آسان

### 2. **Scalability**
- Asynchronous operations
- Background job processing
- Resource-efficient design

### 3. **Reliability**
- Comprehensive error handling
- Transaction management
- Fallback mechanisms

### 4. **Extensibility**
- Clean interfaces
- Plugin-like architecture
- Easy addition of new services

## چالش‌ها و محدودیت‌ها (Challenges & Limitations)

### 1. **Resource Management**
- مدیریت memory در پردازش jobهای سنگین
- Connection pool limits
- Rate limiting برای API calls

### 2. **Error Recovery**
- Handling intermittent API failures
- Partial job completion
- State consistency در failures

### 3. **Performance Optimization**
- Caching strategies
- Batch processing
- Parallel execution limits

## بهبودهای آینده (Future Enhancements)

### 1. **Performance**
- Job queue system (Redis/RabbitMQ)
- Result caching
- Parallel processing improvements

### 2. **Features**
- Custom prompt templates per domain
- Multi-language support enhancement
- Advanced error recovery

### 3. **Monitoring**
- Real-time dashboards
- Alerting system
- Cost optimization features

---

**ماژول Services یک لایه business logic قوی و extensible فراهم می‌کند که عملیات پیچیده سیستم را مدیریت کرده و امکان توسعه آسان را تضمین می‌کند.**









