# معماری ماژول LLM (Large Language Models)

## نمای کلی (Overview)

ماژول **LLM** یک سیستم unified و extensible برای ارتباط با ارائه‌دهندگان مختلف مدل‌های زبانی است. این ماژول یک interface یکپارچه برای عملیات LLM فراهم کرده و امکان پشتیبانی از providerهای مختلف مانند OpenAI، vLLM، Ollama و custom HTTP endpoints را دارد.

## معماری کلی (Architecture Overview)

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM Module                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Model Connector                         │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │Provider     │Registry     │   Schemas      │    │    │
│  │  │Dispatcher   │Management   │   & Contracts  │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               Provider Layer                        │    │
│  │  ┌─────────────┬─────────────┬─────────────────┐    │    │
│  │  │   OpenAI    │   vLLM      │     Ollama      │    │    │
│  │  │             │             │                 │    │    │
│  │  │   Custom    │   Base      │   Exceptions    │    │    │
│  │  │   HTTP      │   Provider  │                 │    │    │
│  │  └─────────────┴─────────────┴─────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────┬───────────────────────────────────────┘
                      │
           ┌──────────┴──────────┐
           │   External LLM      │
           │   Providers         │
           └─────────────────────┘
```

## اجزاء اصلی (Core Components)

### 1. ModelConnector (Facade Pattern)

کلاس اصلی و نقطه ورود unified برای همه عملیات LLM:

#### ویژگی‌های کلیدی:
- **Provider Agnostic**: یک interface یکسان برای همه providerها
- **Registry Management**: مدیریت مدل‌ها و تنظیمات آنها
- **Error Handling**: مدیریت خطاهای یکپارچه
- **Performance Monitoring**: اندازه‌گیری latency و usage

#### ساختار داخلی:
```python
class ModelConnector:
    def __init__(self, registry: Optional[ModelRegistry] = None):
        self.registry = registry or get_registry()
        self._providers: Dict[str, BaseProvider] = {}
        self._provider_classes: Dict[str, Type[BaseProvider]] = {
            "openai": OpenAIProvider,
            "vllm": VLLMProvider,
            "ollama": OllamaProvider,
            "custom": CustomHTTPProvider,
        }
```

#### متدهای اصلی:

##### `initialize()`
```python
async def initialize(self) -> None:
    """Initialize the connector by loading the model registry."""
    if not self.registry.is_loaded():
        await self.registry.load()
    self._initialized = True
```

##### `generate()`
```python
async def generate(self, request: LLMRequest) -> LLMResponse:
    """Generate text using the specified model."""
    self._ensure_initialized()

    # Get provider and generate
    provider = self._get_provider(request.model_id)
    start_time = time.time()

    try:
        response = await provider.generate(request)
        latency = int((time.time() - start_time) * 1000)
        response.latency_ms = latency
        return response
    except Exception as e:
        logger.error(f"Generation failed for model {request.model_id}: {e}")
        raise
```

### 2. Model Registry

سیستم مدیریت و تعریف مدل‌ها:

#### ویژگی‌ها:
- **Dynamic Configuration**: بارگذاری مدل‌ها از config
- **Provider Mapping**: mapping بین مدل‌ها و providerها
- **Validation**: اعتبارسنجی تنظیمات مدل‌ها
- **Caching**: cache مدل‌های فعال

#### ساختار مدل:
```python
@dataclass
class ModelDefinition:
    id: str
    provider: str
    base_url: str
    model_name: str
    api_key: Optional[str] = None
    supports_chat: bool = True
    supports_json: bool = False
    max_tokens: int = 4096
    is_active: bool = True
    timeout_seconds: float = 120.0
```

#### Registry Operations:
```python
class ModelRegistry:
    async def load(self) -> None:
        """Load model definitions from configuration"""

    def get_model(self, model_id: str) -> ModelDefinition:
        """Get model definition by ID"""

    def get_active_models(self) -> List[ModelDefinition]:
        """Get all active model definitions"""
```

### 3. Provider Layer

لایه abstraction برای ارائه‌دهندگان مختلف:

#### Base Provider Interface:
```python
class BaseProvider(ABC):
    def __init__(self, model_def: ModelDefinition):
        self.model_def = model_def

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text using this provider"""
        pass

    @abstractmethod
    def prepare_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Prepare request for this provider's API"""
        pass

    @abstractmethod
    def parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse response from this provider's API"""
        pass
```

#### ارائه‌دهندگان پشتیبانی شده:

##### **OpenAI Provider**
```python
class OpenAIProvider(BaseProvider):
    async def generate(self, request: LLMRequest) -> LLMResponse:
        # OpenAI API integration
        # Supports GPT-3.5, GPT-4, GPT-4-turbo
        # Full feature support: function calling, JSON schemas
```

##### **vLLM Provider**
```python
class VLLMProvider(BaseProvider):
    async def generate(self, request: LLMRequest) -> LLMResponse:
        # Optimized for vLLM inference servers
        # OpenAI-compatible API
        # High-performance batch processing
```

##### **Ollama Provider**
```python
class OllamaProvider(BaseProvider):
    async def generate(self, request: LLMRequest) -> LLMResponse:
        # Local LLM server support
        # Converts chat format to Ollama format
        # Supports local models (Llama, Mistral, etc.)
```

##### **Custom HTTP Provider**
```python
class CustomHTTPProvider(BaseProvider):
    async def generate(self, request: LLMRequest) -> LLMResponse:
        # Flexible HTTP API support
        # Configurable for any REST-based LLM API
        # Custom request/response mapping
```

## مدل‌های داده (Data Models)

### LLMRequest
```python
@dataclass
class LLMRequest:
    model_id: str
    messages: List[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stop: Optional[List[str]] = None
    stream: bool = False  # Future streaming support
    json_schema: Optional[Dict] = None  # Structured outputs
    tools: Optional[List[Dict]] = None  # Function calling
```

### LLMResponse
```python
@dataclass
class LLMResponse:
    text: str
    raw_response: Dict[str, Any]
    model_id: str
    usage: Optional[Usage] = None
    latency_ms: Optional[int] = None
    finish_reason: Optional[str] = None
```

### Message Schema
```python
@dataclass
class Message:
    role: MessageRole  # USER, ASSISTANT, SYSTEM
    content: str
    name: Optional[str] = None  # For function calls

class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"
```

## مدیریت خطا (Error Handling)

### انواع خطا:
```python
class ModelNotFoundError(Exception):
    """Raised when model ID is not found in registry"""

class ProviderNotSupportedError(Exception):
    """Raised when provider type is not supported"""

class InvalidRequestError(Exception):
    """Raised when request parameters are invalid"""

class ModelGenerationError(Exception):
    """Raised when model generation fails"""
```

### استراتژی مدیریت خطا:
- **Validation**: بررسی پارامترها در ورودی
- **Retry Logic**: retry خودکار برای خطاهای transient
- **Fallback**: استفاده از provider جایگزین در صورت failure
- **Logging**: لاگ کامل خطاها با context

## قابلیت توسعه (Extensibility)

### افزودن Provider جدید:
```python
class NewProvider(BaseProvider):
    async def generate(self, request: LLMRequest) -> LLMResponse:
        # Custom implementation
        pass

    def prepare_request(self, request: LLMRequest) -> Dict[str, Any]:
        # Convert to provider's API format
        return {
            "input": request.messages[0].content,
            "parameters": {
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            }
        }

    def parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        # Parse provider's response format
        return LLMResponse(
            text=response_data["generated_text"],
            raw_response=response_data,
            model_id=self.model_def.id
        )
```

### تنظیمات در Registry:
```python
# Add to provider classes mapping
self._provider_classes["new_provider"] = NewProvider

# Model configuration
{
    "id": "custom-model",
    "provider": "new_provider",
    "base_url": "https://custom-api.example.com",
    "model_name": "custom-model-v1",
    "supports_chat": True,
    "max_tokens": 4096
}
```

## امنیت و Rate Limiting

### 1. **API Key Management**
- رمزگذاری کلیدها در database
- Runtime decryption
- Secure transmission (HTTPS)

### 2. **Rate Limiting**
```python
class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = []

    async def acquire(self) -> None:
        """Wait if rate limit exceeded"""
        now = time.time()
        # Remove old requests
        self.requests = [r for r in self.requests if now - r < 60]
        if len(self.requests) >= self.requests_per_minute:
            sleep_time = 60 - (now - self.requests[0])
            await asyncio.sleep(sleep_time)
        self.requests.append(now)
```

### 3. **Request Validation**
- Sanitization ورودی‌ها
- Size limits برای promptها
- Model capability validation

## مانیتورینگ و Observability

### Metrics قابل اندازه‌گیری:
- **Latency**: زمان پاسخ هر provider
- **Token Usage**: مصرف tokens و هزینه‌ها
- **Success Rate**: نرخ موفقیت درخواست‌ها
- **Error Rates**: نرخ خطا per provider

### Logging:
```python
logger.info(f"LLM_REQUEST | Model: {model_id} | Provider: {provider} | Tokens: {usage.prompt_tokens}")
logger.warning(f"LLM_ERROR | Model: {model_id} | Error: {error} | Latency: {latency}ms")
logger.debug(f"LLM_RESPONSE | Model: {model_id} | FinishReason: {finish_reason}")
```

## تنظیمات و Configuration

### Environment Variables:
```
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://localhost:11434
VLLM_BASE_URL=http://localhost:8000
CUSTOM_API_KEY=...
```

### Registry Configuration:
```python
config = {
    "models": [
        {
            "id": "gpt-4",
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-4",
            "api_key": "${OPENAI_API_KEY}",
            "supports_chat": True,
            "supports_json": True,
            "max_tokens": 8192,
            "is_active": True,
            "timeout_seconds": 120.0
        },
        {
            "id": "local-llama",
            "provider": "ollama",
            "base_url": "${OLLAMA_BASE_URL}",
            "model_name": "llama2:13b",
            "supports_chat": True,
            "supports_json": False,
            "max_tokens": 4096,
            "is_active": True
        }
    ]
}
```

## مزایای معماری (Architecture Benefits)

### 1. **Unified Interface**
- یک API ساده برای همه providerها
- کاهش complexity در business logic
- قابلیت testing آسان

### 2. **Extensibility**
- افزودن provider جدید بدون تغییر کد موجود
- Plugin-like architecture
- Configuration-driven setup

### 3. **Reliability**
- Error handling جامع
- Retry logic و fallback mechanisms
- Rate limiting و resource protection

### 4. **Performance**
- Provider caching و reuse
- Async operations throughout
- Latency tracking و optimization

## چالش‌ها و محدودیت‌ها (Challenges & Limitations)

### 1. **Provider Differences**
- API differences بین providerها
- Capability variations (JSON support, function calling)
- Rate limit differences

### 2. **Cost Management**
- Tracking usage across providers
- Cost optimization strategies
- Budget limits و alerting

### 3. **Model Management**
- Model versioning و updates
- Compatibility testing
- Performance benchmarking

## بهبودهای آینده (Future Enhancements)

### 1. **Advanced Features**
- Streaming responses
- Multi-modal inputs (images, audio)
- Advanced function calling
- Model fine-tuning integration

### 2. **Performance Optimizations**
- Response caching
- Batch processing
- Load balancing across providers
- Auto-scaling based on demand

### 3. **Monitoring Enhancements**
- Real-time dashboards
- Cost analytics
- Performance comparisons
- Automated model selection

### 4. **New Providers**
- Google Gemini
- Anthropic Claude (enhanced)
- Local model optimizations
- Custom enterprise providers

---

**ماژول LLM یک معماری clean و extensible برای مدیریت مدل‌های زبانی فراهم می‌کند که امکان توسعه آسان و یکپارچه‌سازی با providerهای مختلف را دارد.**









