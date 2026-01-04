# معماری ماژول Chat Engine

## نمای کلی (Overview)

ماژول **Chat Engine** قلب سیستم Text-to-SQL پلتفرم SQL PT است. این ماژول یک pipeline پیشرفته و production-ready برای تبدیل زبان طبیعی به کوئری‌های SQL ارائه می‌دهد که شامل بارگذاری زمینه، تولید Reasoning، ایجاد SQL، اعتبارسنجی و اجرای کوئری می‌شود.

## معماری کلی (Architecture Overview)

```
┌─────────────────────────────────────────────────────────────┐
│                      Chat Engine                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                Orchestration Layer                  │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │ContextLoader│PromptEngine │   LLMGateway    │    │    │
│  │  │             │             │                 │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 Processing Pipeline                 │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │   Reasoning │  SQL Gen   │   Validation    │    │    │
│  │  │   Pipeline  │             │                 │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────┘
                      │
           ┌──────────┴──────────┐
           │   SQL Execution     │
           │   & Results         │
           └─────────────────────┘
```

## اجزاء اصلی (Core Components)

### 1. ChatEngine (Orchestrator)

کلاس اصلی مدیریت چرخه حیات چت که همه کامپوننت‌ها را هماهنگ می‌کند:

#### ویژگی‌های کلیدی:
- **Pipeline Orchestration**: مدیریت کامل جریان Text-to-SQL
- **Traceability**: ثبت کامل همه مراحل با timestamp و hash
- **Error Handling**: مدیریت خطاها با fallback مناسب
- **Performance Monitoring**: اندازه‌گیری زمان هر مرحله

#### ساختار کامپوننت‌ها:
```python
class ChatEngine:
    def __init__(self, session: AsyncSession, connector: DatabaseConnector):
        self.context_loader = ContextLoader(session)
        self.prompt_engine = PromptEngine()
        self.llm_gateway = LLMGateway(session)
        self.sql_pipeline = SQLPipeline(...)
        self.conversation_manager = ConversationStateManager()
```

### 2. ContextLoader

مسئول بارگذاری و تجمیع زمینه مکالمه:

#### وظایف:
- بارگذاری Schema اطلاعات از snapshot
- تجمیع Data Dictionary و Relationships
- ایجاد Use Caseها و Business Context
- تولید Context Hash برای traceability

#### خروجی (ChatContext):
```python
class ChatContext(BaseModel):
    snapshot_id: int
    schema_info: List[SchemaInfo]
    data_dictionary: List[DataDictionaryInfo]
    relationships: List[RelationshipInfo]
    use_cases: List[UseCaseInfo]
    context_hash: str  # Auto-generated
```

### 3. PromptEngine

مدیریت templateهای prompt و تولید promptهای versioned:

#### ویژگی‌ها:
- **Versioned Templates**: هر prompt دارای version و تاریخچه
- **Multi-language Support**: پشتیبانی از زبان‌های مختلف
- **Dynamic Variables**: استفاده از متغیرهای پویا در promptها

#### ساختار Prompt Template:
```python
class PromptTemplate(BaseModel):
    version: str
    template_type: str
    language: ChatLanguage
    template: str
    variables: List[str]
```

### 4. LLMGateway

رابط abstracted برای ارتباط با مدل‌های زبانی مختلف:

#### ارائه‌دهندگان پشتیبانی شده:
- OpenAI (GPT-3.5, GPT-4)
- Anthropic Claude
- Local Models (Ollama, vLLM)
- Custom Providers

#### ویژگی‌ها:
- **Provider Agnostic**: یک interface یکسان برای همه providerها
- **Rate Limiting**: کنترل تعداد درخواست‌ها
- **Error Recovery**: retry logic برای خطاهای API
- **Cost Tracking**: مانیتورینگ هزینه‌های API

### 5. SQLPipeline

Pipeline سه مرحله‌ای پردازش SQL:

#### مراحل (Stages):

##### **Stage 1: Reasoning Generation**
```
User Question → Reasoning Prompt → LLM → Intent Analysis
                                              ↓
                                       Table Selection & Query Type
```

##### **Stage 2: SQL Generation**
```
Reasoning Output + Context → SQL Prompt → LLM → SQL Query
```

##### **Stage 3: Validation & Execution**
```
Generated SQL → Validation → Sanitization → Execution → Results
```

#### امنیت در هر مرحله:
- **Read-Only Enforcement**: جلوگیری از عملیات DML
- **Injection Prevention**: sanitization کوئری‌ها
- **Context Validation**: بررسی coherence با schema

### 6. ConversationStateManager (اختیاری)

مدیریت وضعیت مکالمات برای continuity:

#### قابلیت‌ها:
- ذخیره تاریخچه مکالمات
- Context sharing بین پیام‌ها
- Memory management برای cleanup

## جریان کاری (Workflow)

### پردازش کامل یک درخواست چت:

```
1. دریافت ChatRequest
   ↓
2. بارگذاری Context (ContextLoader)
   ├─ Schema Information
   ├─ Data Dictionary
   ├─ Relationships
   └─ Business Context
   ↓
3. تولید Reasoning (SQLPipeline)
   ├─ تحلیل Intent کاربر
   ├─ شناسایی جداول مرتبط
   └─ تعیین نوع کوئری
   ↓
4. تولید SQL (SQLPipeline)
   ├─ ساخت Prompt تخصصی
   ├─ ارسال به LLM
   └─ دریافت SQL Query
   ↓
5. اعتبارسنجی و اجرا (SQLPipeline)
   ├─ بررسی امنیتی SQL
   ├─ اجرای کوئری
   └─ بازگرداندن نتایج
   ↓
6. تولید ChatResponse با traceability کامل
```

## مدل‌های داده (Data Models)

### ChatRequest
```python
class ChatRequest(BaseModel):
    snapshot_id: int
    selected_model_id: int
    language: ChatLanguage
    user_question: str
    conversation_id: Optional[str] = None
```

### ChatResponse
```python
class ChatResponse(BaseModel):
    success: bool
    user_question: str
    generated_sql: str
    rows: List[Dict[str, Any]]
    row_count: int
    # Traceability fields
    context_hash: str
    sql_validation_status: str
    execution_time_ms: int
    conversation_id: Optional[str] = None
```

## امنیت و ایمنی (Security & Safety)

### 1. **SQL Injection Prevention**
- استفاده از parameterized queries
- Validation همه ورودی‌ها
- Sanitization SQL قبل از اجرا

### 2. **Read-Only Operations**
- بررسی syntax برای جلوگیری از DML operations
- Whitelist allowed SQL keywords
- Context-aware validation

### 3. **Rate Limiting**
- محدودیت تعداد درخواست‌ها per user
- Queue management برای concurrent requests
- Resource protection

### 4. **Error Handling**
- Safe error messages (بدون leak اطلاعات حساس)
- Fallback به plain text در صورت خطا
- Structured error logging

## Traceability و Auditing

### اطلاعات traceable:
- **Context Hash**: fingerprint منحصر به فرد context
- **Prompt Versions**: version promptهای استفاده شده
- **Execution Metrics**: زمان هر مرحله
- **Model Usage**: مدل استفاده شده و هزینه
- **Validation Status**: نتیجه اعتبارسنجی

### کاربردها:
- **Debugging**: پیگیری مشکلات
- **Auditing**: ثبت فعالیت‌ها برای compliance
- **Performance Analysis**: تحلیل bottlenecks
- **Cost Tracking**: مانیتورینگ هزینه‌ها

## قابلیت توسعه (Extensibility)

### افزودن LLM Provider جدید:
```python
class NewProvider(LLMProvider):
    def prepare_request(self, prompt: str) -> Dict:
        # Custom API format
        return {"input": prompt}

    def parse_response(self, response: Dict) -> str:
        # Custom response parsing
        return response["generated_text"]
```

### افزودن مرحله pipeline جدید:
```python
class SQLOptimizer:
    async def optimize_sql(self, sql: str, context: ChatContext) -> str:
        # Optimization logic
        pass
```

### افزودن prompt template جدید:
```python
templates["optimization_en"] = PromptTemplate(
    version="1.0.0",
    template_type="optimization",
    language=ChatLanguage.ENGLISH,
    template=optimization_template,
    variables=["sql", "performance_metrics"]
)
```

## مانیتورینگ و Observability

### Metrics قابل اندازه‌گیری:
- **Context Loading Time**: زمان بارگذاری context
- **Prompt Building Time**: زمان ساخت prompt
- **LLM Call Latency**: تأخیر پاسخ مدل
- **SQL Generation Time**: زمان تولید SQL
- **Validation Time**: زمان اعتبارسنجی
- **Execution Time**: زمان اجرای کوئری
- **Total Processing Time**: زمان کل پردازش

### Logging Levels:
- **INFO**: lifecycle events و نتایج اصلی
- **WARNING**: validation failures و خطاهای recoverable
- **ERROR**: critical failures و API errors
- **DEBUG**: detailed tracing برای development

## تنظیمات و Configuration

### Environment Variables:
```
LLM_MODEL_TIMEOUT=30
SQL_EXECUTION_TIMEOUT=60
MAX_ROWS_LIMIT=1000
CONTEXT_CACHE_TTL=3600
```

### Database Configuration:
- Model provider settings
- Prompt templates
- Conversation cleanup policies

## مزایای معماری (Architecture Benefits)

### 1. **Production Ready**
- Comprehensive error handling
- Full traceability
- Performance monitoring
- Security-first approach

### 2. **Highly Extensible**
- Clean separation of concerns
- Modular pipeline stages
- Provider-agnostic design
- Plugin-like architecture

### 3. **Maintainable**
- Type safety با Pydantic
- Comprehensive documentation
- Clear component boundaries
- Async/await throughout

### 4. **Scalable**
- Stateless design
- Resource-efficient
- Concurrent request handling
- Background processing support

## چالش‌ها و محدودیت‌ها (Challenges & Limitations)

### 1. **Context Size Limits**
- محدودیت اندازه context در LLMها
- نیاز به intelligent context selection
- Trade-off بین completeness و performance

### 2. **Complex Schema Understanding**
- Schemaهای پیچیده با روابط زیاد
- Business logic در stored procedures
- Legacy database structures

### 3. **Multi-turn Conversations**
- حفظ context در مکالمات طولانی
- Memory management
- Conversation state consistency

## بهبودهای آینده (Future Enhancements)

### 1. **Performance Optimizations**
- Context caching و reuse
- Parallel processing در pipeline stages
- Batch processing برای multiple queries

### 2. **Advanced Features**
- Multi-agent reasoning
- Query optimization pipeline
- User feedback learning
- Advanced conversation state

### 3. **Integration Features**
- Vector database برای semantic search
- External knowledge base integration
- Real-time collaboration

### 4. **Monitoring Enhancements**
- Real-time dashboards
- Alerting system
- Performance profiling
- Cost optimization

---

**Chat Engine یک معماری robust و extensible برای Text-to-SQL فراهم می‌کند که هم production-ready است و هم امکان توسعه آسان را دارد.**









