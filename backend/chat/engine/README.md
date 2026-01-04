# Chat Engine - Production-Grade Text-to-SQL System

## Overview

The Chat Engine is a production-grade module that orchestrates the complete Text-to-SQL lifecycle. It provides a clean, extensible architecture with full traceability and separation of concerns.

## Architecture

### Core Components

1. **ChatEngine** - Main orchestrator
2. **ContextLoader** - Loads and aggregates context into immutable ChatContext
3. **PromptEngine** - Builds deterministic, versioned prompts
4. **LLMGateway** - Abstracts model provider APIs
5. **SQLPipeline** - Three-stage SQL processing (Generate → Validate → Execute)
6. **ConversationStateManager** - Optional state management for continuity

### Data Flow

```
ChatRequest → ChatEngine → ContextLoader → ChatContext
                              ↓
                        PromptEngine → Reasoning Prompt → LLM → Reasoning Output
                              ↓
                        SQLPipeline → SQL Generation → SQL Validation → SQL Execution
                              ↓
                        ChatResponse ← Results + Full Traceability
```

## Key Features

### 🔒 Security & Safety
- Read-only SQL enforcement
- Injection prevention
- Context validation
- SQL sanitization

### 📊 Traceability
- Context hash for audit trails
- Prompt versioning
- Execution timing
- Model usage tracking
- Validation status

### 🔧 Extensibility
- Clean separation of concerns
- Modular pipeline stages
- Provider-agnostic LLM abstraction
- Optional conversation state
- Versioned prompts

### 🚀 Production Ready
- Async/await throughout
- Proper error handling
- Resource cleanup
- Type safety with Pydantic
- Comprehensive logging points

## Usage

### Basic Usage

```python
from sqlalchemy.ext.asyncio import AsyncSession
from db import DatabaseConnector
from chat import ChatEngine

# Initialize
session = get_db_session()
connector = DatabaseConnector(snapshot_id)
engine = ChatEngine(session, connector)

# Process request
request = ChatRequest(
    snapshot_id=123,
    selected_model_id=1,
    language="en",
    user_question="Show me all users from New York",
    conversation_id="conv_123"  # optional
)

response = await engine.process_chat_request(request)

# Response includes full traceability
print(f"SQL: {response.generated_sql}")
print(f"Rows: {response.row_count}")
print(f"Model: {response.model_used}")
print(f"Context Hash: {response.context_hash}")
```

### Advanced Usage with Conversation State

```python
# Conversation continuity
request1 = ChatRequest(
    snapshot_id=123,
    selected_model_id=1,
    language="en",
    user_question="What tables do you have?",
    conversation_id="conv_123"
)

response1 = await engine.process_chat_request(request1)

# Follow-up question uses conversation context
request2 = ChatRequest(
    snapshot_id=123,
    selected_model_id=1,
    language="en",
    user_question="Show me the first 10 records from that table",
    conversation_id="conv_123"  # Same conversation ID
)

response2 = await engine.process_chat_request(request2)
```

## API Reference

### ChatEngine

Main orchestrator class.

**Methods:**
- `process_chat_request(request: ChatRequest) -> ChatResponse`
- `get_engine_metadata() -> dict`
- `cleanup_expired_conversations()`
- `close()`

### ChatRequest

Request model with enhanced fields:

```python
class ChatRequest(BaseModel):
    snapshot_id: int
    selected_model_id: int  # Renamed from model_id
    language: ChatLanguage
    user_question: str     # Renamed from question
    conversation_id: Optional[str] = None
```

### ChatResponse

Enhanced response with full traceability:

```python
class ChatResponse(BaseModel):
    success: bool
    user_question: str
    generated_sql: str
    rows: List[Dict[str, Any]]
    row_count: int
    snapshot_id: int
    model_used: str
    execution_status: str
    error_message: Optional[str] = None

    # Traceability fields
    context_hash: str
    sql_validation_status: str  # 'passed', 'failed', 'skipped'
    execution_time_ms: int
    processing_timestamp: datetime
    conversation_id: Optional[str] = None
```

### ChatContext

Immutable context object:

```python
class ChatContext(BaseModel):
    snapshot_id: int
    snapshot_name: str
    schema_info: List[SchemaInfo]
    data_dictionary: List[DataDictionaryInfo]
    relationships: List[RelationshipInfo]
    use_cases: List[UseCaseInfo]
    context_hash: str  # Auto-generated
```

## Pipeline Stages

### 1. Context Loading
- Aggregates schema, dictionary, relationships, use cases
- Creates immutable ChatContext
- Generates context hash for traceability

### 2. Reasoning Generation
- Builds intent understanding prompt
- Calls LLM to analyze user question
- Identifies relevant tables and analysis type

### 3. SQL Generation
- Uses reasoning output + context
- Generates SQL via LLM
- Low temperature for consistency

### 4. SQL Validation
- Read-only enforcement
- Injection prevention
- Context validation
- SQL sanitization

### 5. SQL Execution
- Executes against snapshot database
- Applies row limits
- Captures execution metrics

## Configuration

### Environment Variables
- None required (uses existing database config)

### Dependencies
- SQLAlchemy (async)
- httpx (for LLM calls)
- pydantic (for schemas)
- Existing db and api modules

## Extensibility Points

### Adding New LLM Providers
Extend `LLMGateway` with new provider methods:

```python
def _prepare_custom_provider_request(self, ...):
    # Custom API format
    pass

def _parse_custom_provider_response(self, ...):
    # Custom response parsing
    pass
```

### Adding New Prompt Types
Add to `PromptEngine._initialize_templates()`:

```python
templates["optimization_en"] = PromptTemplate(
    version="1.0.0",
    template_type="optimization",
    language=ChatLanguage.ENGLISH,
    template=self._get_optimization_template_en(),
    variables=["sql", "context", "performance_metrics"]
)
```

### Adding Pipeline Stages
Extend `SQLPipeline` with new stages:

```python
class SQLOptimizer:
    """Stage 2.5: Optimize SQL performance"""

    async def optimize_sql(self, sql: str, context: ChatContext) -> str:
        # Optimization logic
        pass
```

## Migration from Legacy

The legacy `ChatOrchestrator` is maintained for compatibility. To migrate:

1. Replace `ChatOrchestrator` with `ChatEngine`
2. Update request field names (`model_id` → `selected_model_id`, `question` → `user_question`)
3. Handle new response fields (traceability, conversation_id)
4. Use async session management

## Monitoring & Observability

### Metrics Available
- Context loading time
- Prompt building time
- LLM call latency
- SQL generation time
- Validation time
- Execution time
- Total processing time

### Tracing
- Context hash for audit trails
- Prompt versions for reproducibility
- Model usage tracking
- Conversation continuity

## Error Handling

### Structured Error Responses
- Validation failures
- LLM API errors
- Database connection issues
- SQL execution errors
- Context loading failures

### Error Propagation
- Errors bubble up with context
- Partial results preserved where possible
- Safe fallbacks for optional features

## Testing

### Unit Tests
- Mock LLM responses
- Test each pipeline stage
- Validate error handling

### Integration Tests
- Full pipeline testing
- Database snapshot testing
- Multi-conversation flows

## Future Enhancements

### Planned Features
- Memory system for query learning
- Multi-agent reasoning
- Query optimization pipeline
- User feedback loop
- Advanced conversation state
- Query result caching

### Extension Points
- Plugin architecture for custom stages
- Custom prompt templates
- Alternative validation strategies
- Result post-processing hooks
