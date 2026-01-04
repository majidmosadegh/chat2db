# Universal LLM Model Connector

A clean, extensible, production-ready module for interacting with multiple LLM providers through a unified interface.

## Overview

This module provides a single entry point `ModelConnector.generate(request)` for all LLM operations across different providers including OpenAI, vLLM, Ollama, and custom HTTP endpoints.

## Architecture

```
backend/llm/
├── connector.py        # Main entry point - ModelConnector
├── registry.py         # Model registry and definitions
├── schemas.py          # Request/Response contracts
├── exceptions.py       # Custom exception classes
├── providers/
│   ├── base.py         # Provider interface
│   ├── openai.py       # OpenAI provider
│   ├── vllm.py         # vLLM provider
│   ├── ollama.py       # Ollama provider
│   └── custom_http.py  # Custom HTTP provider
```

## Quick Start

```python
from backend.llm import ModelConnector, LLMRequest, Message, MessageRole
from backend.llm.registry import initialize_registry, ConfigRegistryLoader

# Initialize registry with model definitions
config = {
    "models": [
        {
            "id": "gpt-4",
            "provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-4",
            "api_key": "your-api-key",
            "supports_chat": True,
            "supports_json": True,
            "max_tokens": 8192,
            "is_active": True,
        },
        {
            "id": "local-llama",
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "model_name": "llama2",
            "supports_chat": True,
            "supports_json": False,
            "max_tokens": 4096,
            "is_active": True,
        }
    ]
}

loader = ConfigRegistryLoader(config)
initialize_registry(loader)

# Create connector and initialize
connector = ModelConnector()
await connector.initialize()

# Generate text
request = LLMRequest(
    model_id="gpt-4",
    messages=[
        Message(role=MessageRole.USER, content="Hello, how are you?")
    ],
    temperature=0.7,
    max_tokens=100
)

response = await connector.generate(request)
print(response.text)
```

## Model Registry

Models are defined with the following properties:

- `id`: Unique identifier
- `provider`: Provider type (openai, vllm, ollama, custom)
- `base_url`: API endpoint URL
- `model_name`: Model name on the provider
- `api_key`: Optional API key
- `supports_chat`: Whether model supports chat format
- `supports_json`: Whether model supports JSON schema responses
- `max_tokens`: Maximum context length
- `is_active`: Whether model is available

## Supported Providers

### OpenAI
- Supports official OpenAI API and OpenAI-compatible endpoints
- Full feature support including function calling and JSON schemas

### vLLM
- Optimized for vLLM inference servers
- OpenAI-compatible API with vLLM-specific optimizations

### Ollama
- Local LLM server support
- Converts standard chat format to Ollama's conversation format

### Custom HTTP
- Flexible HTTP API support
- Configurable for any REST-based LLM API

## Request/Response Schema

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

## Error Handling

The module provides explicit exception types:

- `ModelNotFoundError`: Model ID not found in registry
- `ProviderNotSupportedError`: Unsupported provider type
- `InvalidRequestError`: Invalid request parameters
- `ModelGenerationError`: Generation failure

## Extensibility

The architecture supports future enhancements:

- **Streaming**: Add `stream=True` support to requests
- **Multi-modal**: Extend schemas for image/audio inputs
- **Tool calling**: Already supported in request schema
- **New providers**: Implement `BaseProvider` interface

## Production Features

- Async-first design
- Comprehensive error handling
- Request validation
- Provider caching
- Latency tracking
- Token usage reporting
- Type hints everywhere
- Clean separation of concerns
