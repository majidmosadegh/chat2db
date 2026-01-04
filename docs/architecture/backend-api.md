# معماری ماژول Backend API

## نمای کلی (Overview)

ماژول **Backend API** لایه ارائه (Presentation Layer) پلتفرم SQL PT است که با استفاده از FastAPI پیاده‌سازی شده و مسئولیت ارائه REST APIهای یکپارچه برای کل سیستم را بر عهده دارد. این ماژول با پیروی از اصول Clean Architecture، کنترلرهای HTTP را از منطق کسب‌وکار جدا کرده و یک رابط یکپارچه برای Frontend و سرویس‌های خارجی فراهم می‌کند.

## معماری کلی (Architecture Overview)

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                Centralized Router Registry          │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │  Database   │   Schema    │    AI Services   │    │    │
│  │  │ Management  │ Management  │    (Dictionary, │    │    │
│  │  │             │             │     Chat, LLM)   │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────┘
                      │
           ┌──────────┴──────────┐
           │   Service Layer     │
           │ (Business Logic)    │
           └──────────┬──────────┘
                      │
           ┌──────────┴──────────┐
           │  Database Layer     │
           │ (Repositories)      │
           └─────────────────────┘
```

## اجزاء اصلی (Core Components)

### 1. Centralized Application Factory (`core/app.py`)

کلاس اصلی مدیریت چرخه حیات اپلیکیشن FastAPI:

#### ویژگی‌های کلیدی:
- **Centralized Router Registration**: ثبت یکپارچه همه Routerها
- **CORS Middleware**: مدیریت Cross-Origin Resource Sharing
- **Lifespan Management**: مدیریت شروع و پایان اپلیکیشن
- **Health Checks**: اندپوینت‌های مانیتورینگ سلامت سیستم

#### ساختار ثبت Routerها:
```python
api_routes = [
    (database.router, "/api/database", "database"),
    (schema.router, "/api/schema", "schema"),
    (ai_dictionary.router, "/api/ai/dictionary", "ai-dictionary"),
    (chat_router.router, "/api/chat", "chat"),
    # ... سایر routerها
]

for router, prefix, tags in api_routes:
    app.include_router(router, prefix=prefix, tags=[tags])
```

### 2. API Routerها (API Routers)

هر ماژول دارای Router جداگانه با مسئولیت‌های مشخص:

#### انواع Routerها:

##### **Database Management Router** (`database.py`)
- مدیریت اتصالات پایگاه داده
- تست اتصال به PostgreSQL, MySQL, SQL Server
- رمزگذاری امن پسوردها و API Keyها
- مدیریت وضعیت فعال بودن اتصالات

##### **Schema Management Router** (`schema.py`)
- مدیریت اسنپ‌شات‌های Schema پایگاه داده
- استخراج ساختار جداول و روابط
- ذخیره Metadata ساختار پایگاه داده

##### **AI Dictionary Router** (`ai_dictionary.py`)
- تولید فرهنگ داده با استفاده از AI
- مدیریت Jobهای پس‌زمینه برای پردازش سنگین
- مانیتورینگ پیشرفت تولید فرهنگ داده

##### **Chat Router** (`chat/router.py`)
- پردازش Text-to-SQL
- مدیریت مکالمات و زمینه چت
- اجرای کوئری‌های تولید شده

##### **LLM Management Router** (`llm.py`)
- مدیریت ارائه‌دهندگان مدل‌های زبانی
- تنظیمات API Key و Configuration
- تست اتصال به مدل‌ها

### 3. مدل‌های داده (Data Models)

استفاده از Pydantic برای مدل‌سازی داده‌ها:

#### انواع مدل‌ها:

##### **Request Models**
```python
class AIDictionaryGenerateRequest(BaseModel):
    snapshot_id: int
    business_domain: str
    database_description: str
    target_user: str
    language: Optional[str] = "persian"
    additional_notes: Optional[str] = None
```

##### **Response Models**
```python
class AIDictionaryGenerateResponse(BaseModel):
    success: bool
    message: str
    job_id: Optional[str] = None
```

##### **Data Transfer Objects (DTOs)**
- تبدیل داده‌های SQLAlchemy به فرمت API
- Validation ورودی‌ها
- Serialization پاسخ‌ها

### 4. Dependency Injection

استفاده از FastAPI Dependency Injection برای مدیریت وابستگی‌ها:

```python
async def get_db_session() -> AsyncSession:
    """Database session dependency"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# استفاده در endpoint
@router.get("/", response_model=List[DatabaseConnectionResponse])
async def get_connections(session: AsyncSession = Depends(get_db_session)):
    # منطق endpoint
```

## جریان کاری (Workflow)

### 1. درخواست‌های همزمان (Synchronous Requests)

```
HTTP Request → FastAPI Router → Input Validation → Service Layer
                                                       ↓
                                               Database Layer → Response
```

### 2. پردازش پس‌زمینه (Background Processing)

```
HTTP Request → FastAPI Router → Start Background Task
                                      ↓
                               BackgroundTasks.add_task()
                                      ↓
                            Service.process_job() → Complete
```

### 3. مدیریت خطا (Error Handling)

```
Exception Occurs → Custom Exception Handler → HTTP Exception
                                                      ↓
                                              Structured Error Response
```

## امنیت و اعتبارسنجی (Security & Validation)

### 1. **Encryption Management**
- رمزگذاری پسوردها و API Keyها با Fernet
- ذخیره امن در پایگاه داده
- رمزگشایی در زمان استفاده

### 2. **Input Validation**
- استفاده از Pydantic برای validation
- بررسی نوع داده‌ها و محدوده‌ها
- Sanitization ورودی‌ها

### 3. **Error Handling**
- تبدیل خطاهای داخلی به HTTP Exception
- لاگ‌گیری امن (بدون نمایش اطلاعات حساس)
- پاسخ‌های خطای ساختار یافته

## اندپوینت‌های اصلی (Main Endpoints)

### Database Management (`/api/database`)
```
GET    /                     # لیست اتصالات
POST   /                     # ایجاد اتصال جدید
GET    /{id}                 # دریافت اتصال خاص
PUT    /{id}                 # بروزرسانی اتصال
DELETE /{id}                 # حذف اتصال
POST   /test                 # تست اتصال
POST   /{id}/activate        # فعال کردن اتصال
```

### AI Dictionary (`/api/ai/dictionary`)
```
POST   /generate              # شروع تولید فرهنگ داده
GET    /jobs/{job_id}         # وضعیت Job
```

### Chat (`/api/chat`)
```
POST   /                      # ارسال پیام چت
GET    /history/{conv_id}     # تاریخچه مکالمه
```

### Schema Management (`/api/schema`)
```
POST   /snapshot              # ایجاد اسنپ‌شات Schema
GET    /snapshots             # لیست اسنپ‌شات‌ها
GET    /snapshot/{id}         # جزئیات اسنپ‌شات
```

## مدیریت Asynchronous Operations

### 1. **Background Tasks**
- استفاده از `BackgroundTasks` FastAPI
- پردازش سنگین بدون بلاک کردن API
- مدیریت وضعیت Jobها

### 2. **Database Sessions**
- استفاده از `AsyncSession` SQLAlchemy
- مدیریت Connection Pool
- Transaction Management

### 3. **Concurrent Operations**
- پشتیبانی از چندین Job همزمان
- Resource Management
- Rate Limiting

## مانیتورینگ و Observability

### 1. **Health Checks**
```python
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "server": "sql-pt-backend",
        "version": "2.0.0"
    }
```

### 2. **Logging**
- استفاده از Loguru برای لاگ‌گیری پیشرفته
- دسته‌بندی لاگ‌ها (errors.log, llm_calls.log, etc.)
- Structured Logging

### 3. **Metrics**
- زمان پاسخ APIها
- نرخ خطا
- استفاده از منابع

## تنظیمات و Configuration

### متغیرهای محیطی:
- `HOST`, `PORT`: تنظیمات سرور
- `CORS_ORIGINS`: دامنه‌های مجاز
- `DEBUG`: حالت Debug
- Database connection settings

### Centralized Configuration:
```python
# config/config.py
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
```

## مزایای معماری (Architecture Benefits)

### 1. **Scalability**
- Routerهای مستقل و ماژولار
- Asynchronous processing
- Centralized configuration

### 2. **Maintainability**
- Separation of concerns
- Type safety با Pydantic
- Centralized error handling

### 3. **Security**
- Input validation در همه لایه‌ها
- Encryption برای داده‌های حساس
- CORS و security middleware

### 4. **Developer Experience**
- Auto-generated API documentation
- Type hints در همه جا
- Dependency injection

## ملاحظات پیاده‌سازی (Implementation Considerations)

### 1. **Versioning**
- API versioning با URL prefix
- Backward compatibility
- Deprecation warnings

### 2. **Rate Limiting**
- Global rate limiting
- Per-endpoint limits
- User-based quotas

### 3. **Caching**
- Response caching
- Database query caching
- CDN integration

## آینده‌نگری (Future Enhancements)

### 1. **API Gateway**
- Load balancing
- Request routing
- Authentication middleware

### 2. **GraphQL Support**
- Flexible queries
- Schema stitching
- Real-time subscriptions

### 3. **Microservices Migration**
- Service decomposition
- Event-driven communication
- Service mesh integration

---

**این معماری پایه‌ای قوی برای توسعه پایدار و مقیاس‌پذیر فراهم می‌کند و امکان گسترش آسان سیستم را تضمین می‌کند.**









