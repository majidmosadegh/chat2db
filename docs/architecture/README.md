# معماری پروژه SQL PT (SQL Professional Tuning)

## نمای کلی پروژه

پلتفرم **SQL PT** یک سیستم پیشرفته تولید و بهینه‌سازی کوئری‌های SQL است که با استفاده از معماری Clean Architecture و Domain-Driven Design پیاده‌سازی شده است. این سیستم از هوش مصنوعی برای تبدیل زبان طبیعی به SQL استفاده می‌کند و قابلیت‌های enterprise-grade مانند امنیت، مانیتورینگ و قابلیت توسعه‌پذیری ارائه می‌دهد.

## ساختار معماری کلی

```
sql_pt/
├── backend/                    # FastAPI Backend
│   ├── api/                   # REST API Endpoints
│   ├── chat/                  # Chat Engine (Text-to-SQL)
│   ├── core/                  # Application Core
│   ├── db/                    # Database Layer
│   ├── llm/                   # LLM Providers
│   ├── services/              # Business Logic Services
│   └── config/                # Configuration
├── frontend/                  # Next.js Frontend
├── src/                       # Clean Architecture Implementation
│   ├── domain/               # Business Domain
│   ├── application/          # Use Cases
│   ├── infrastructure/       # External Services
│   └── presentation/         # API Controllers
└── tests/                     # Integration Tests
```

## ماژول‌های اصلی و مستندات معماری

### Backend Modules

| ماژول | مسئولیت | فایل معماری |
|--------|----------|-------------|
| **Backend API** | REST API Endpoints و کنترلرها | [backend-api.md](backend-api.md) |
| **Chat Engine** | تبدیل Text-to-SQL و Pipeline پردازش | [chat-engine.md](chat-engine.md) |
| **Services** | منطق کسب‌وکار و سرویس‌های AI | [services.md](services.md) |
| **Database** | لایه دسترسی به داده و Repositoryها | [database.md](database.md) |
| **LLM** | ارائه‌دهندگان مدل‌های زبانی | [llm.md](llm.md) |

### Frontend Modules

| ماژول | مسئولیت | فایل معماری |
|--------|----------|-------------|
| **Frontend Core** | کامپوننت‌های React و UI | [frontend-core.md](frontend-core.md) |

### Clean Architecture (Domain-Driven Design)

| لایه | مسئولیت | فایل معماری |
|------|----------|-------------|
| **Clean Architecture** | پیاده‌سازی کامل DDD | [clean-architecture.md](clean-architecture.md) |

## اصول معماری

### 🏛️ Clean Architecture
- **Dependency Inversion**: لایه‌های داخلی وابسته به لایه‌های خارجی نیستند
- **Single Responsibility**: هر کلاس یک مسئولیت دارد
- **Open/Closed**: ماژول‌ها برای توسعه باز و برای تغییر بسته هستند

### 🎯 Domain-Driven Design (DDD)
- **Ubiquitous Language**: زبان مشترک بین توسعه‌دهندگان و متخصصان دامنه
- **Bounded Contexts**: مرزهای واضح بین زمینه‌های مختلف کسب‌وکار
- **Entities & Value Objects**: مدل‌سازی دقیق مفاهیم دامنه

### 🔄 CQRS Pattern
- **Commands**: عملیات تغییر وضعیت (Create, Update, Delete)
- **Queries**: عملیات خواندن داده‌ها
- **Separate Models**: مدل‌های جداگانه برای خواندن و نوشتن

### 🚀 Event-Driven Architecture
- **Domain Events**: انتشار رویدادها در لایه Domain
- **Event Handlers**: پردازش asynchronous رویدادها
- **Decoupling**: کاهش coupling بین ماژول‌ها

## فناوری‌های کلیدی

### Backend
- **Framework**: FastAPI (Python Async)
- **Architecture**: Clean Architecture + DDD
- **Database**: SQLAlchemy (Async) + Multiple DB Support
- **AI Integration**: OpenAI, Claude, Ollama, vLLM
- **Security**: Cryptography, API Key Management
- **Testing**: pytest (65+ test files)

### Frontend
- **Framework**: Next.js 14 (React + TypeScript)
- **Styling**: Tailwind CSS + Custom Design System
- **State Management**: Context API + Custom Hooks
- **UI Components**: Radix UI + Custom Library

### DevOps & Infrastructure
- **Containerization**: Docker (planned)
- **Orchestration**: Kubernetes (planned)
- **CI/CD**: GitHub Actions (planned)
- **Monitoring**: Prometheus + Grafana (planned)

## امنیت و کیفیت کد

### 🔒 Security Features
- **Database Security**: Encrypted connections, secure API keys
- **Input Validation**: SQL injection prevention, sanitization
- **Authentication**: API key management, rate limiting
- **Audit Trails**: Complete traceability for all operations

### 🧪 Quality Assurance
- **Unit Tests**: 65+ test files covering all backend functionality
- **Integration Tests**: End-to-end testing
- **Code Quality**: TypeScript, Pydantic, comprehensive logging
- **Error Handling**: Structured error responses, graceful degradation

## راهنمای استفاده از مستندات

1. **برای درک کلی**: از این فایل شروع کنید
2. **برای یک ماژول خاص**: فایل معماری مربوطه را مطالعه کنید
3. **برای توسعه**: معماری لایه Domain و Application را بررسی کنید
4. **برای دیباگ**: فایل معماری مربوط به ماژول مشکل‌دار را ببینید

## مشارکت در توسعه معماری

### 📝 Guidelines
- هر تغییر معماری باید مستند شود
- تست‌های واحد برای منطق پیچیده الزامی است
- Dependency injection در همه لایه‌ها رعایت شود
- Interface segregation principle رعایت شود

### 🔄 Process
1. تغییر را در فایل معماری مربوطه مستند کنید
2. تست‌های مرتبط را به‌روزرسانی کنید
3. Code review با تمرکز بر معماری
4. به‌روزرسانی این فایل README در صورت نیاز

---

**📚 برای اطلاعات بیشتر درباره هر ماژول، فایل معماری مربوطه را مطالعه کنید.**
