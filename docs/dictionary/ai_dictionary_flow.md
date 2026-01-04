# AI Dictionary Generation Flow - Complete Documentation

## 📋 Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Complete Flow Diagram](#complete-flow-diagram)
4. [Frontend Flow](#frontend-flow)
5. [Backend Flow](#backend-flow)
6. [Database Operations](#database-operations)
7. [Error Handling](#error-handling)
8. [Status Management](#status-management)

---

## Overview

The AI Dictionary Generation system is a comprehensive solution for automatically generating data dictionary entries using Large Language Models (LLMs). The system processes database tables, samples data, generates descriptions, and stores them in a structured format.

### Key Components
- **Frontend**: React/Next.js UI for job management and monitoring
- **Backend**: FastAPI service with queue-based processing
- **LLM Service**: Integration with VLLM provider for text generation
- **Database**: PostgreSQL for storing jobs, dictionaries, and metadata

---

## Architecture

```
┌─────────────────┐
│   Frontend      │
│  (Next.js)      │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────┐
│   Backend API   │
│   (FastAPI)     │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────────┐
│ Queue  │ │ LLM Service  │
│ System │ │ (VLLM)       │
└───┬────┘ └──────┬───────┘
    │             │
    ▼             ▼
┌─────────────────────┐
│  Database           │
│  (PostgreSQL)       │
└─────────────────────┘
```

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND FLOW                                 │
└─────────────────────────────────────────────────────────────────┘

1. User Opens Data Dictionary Page
   └─> Fetch snapshots
   └─> Display available snapshots

2. User Clicks "Generate with AI"
   └─> Open dialog form
   └─> Fill in:
       - Business Domain
       - Database Description
       - Target User
       - Language (default: Persian)

3. User Submits Form
   └─> POST /api/data-dictionary/ai-generate
   └─> Receive job_id
   └─> Start polling for status

4. Polling Loop (Every 2 seconds)
   └─> GET /api/data-dictionary/ai-generate/status/{job_id}
   └─> Update job card UI
   └─> Check if completed
   └─> Refresh dictionary data if completed

┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND FLOW                                  │
└─────────────────────────────────────────────────────────────────┘

1. API Endpoint: POST /api/data-dictionary/ai-generate
   ├─> Validate request
   ├─> Create job via ai_dictionary_generator.create_job()
   │   ├─> Generate job_id: dict_{snapshot_id}_{uuid}
   │   ├─> Resolve target tables based on scope
   │   ├─> Create TableTask for each table
   │   ├─> Store job in memory (_jobs dict)
   │   └─> Persist to database (AIGenerationJob table)
   │
   └─> Start job in background
       └─> background_tasks.add_task(ai_dictionary_generator.start_job, job_id)

2. start_job(job_id)
   ├─> Load job from memory or database
   ├─> Check job status (allow WAITING or stuck PROCESSING)
   ├─> Update job status to PROCESSING
   ├─> Start worker tasks if not running
   │   └─> Create 3 worker tasks (_process_queue_worker)
   ├─> Queue all table tasks
   │   └─> For each table: await _queue.put((job_id, table_key))
   └─> Persist job status

3. Worker Task: _process_queue_worker(worker_id)
   ├─> Loop forever:
   │   ├─> Get task from queue: (job_id, table_key) = await _queue.get()
   │   ├─> Check if job exists and is active
   │   ├─> Process table task: await _process_table_task(job_id, table_key)
   │   └─> Mark task done: _queue.task_done()
   │
   └─> Handle exceptions gracefully

4. _process_table_task(job_id, table_key)
   ├─> Load job and table task
   ├─> Check task status (skip if DONE/FAILED/CANCELED)
   ├─> Update task status to PROCESSING
   ├─> Update progress: 10%
   ├─> Sample table data (5 rows)
   │   └─> DirectDatabaseConnector.query()
   ├─> Get table schema
   │   └─> Fetch columns, data types, foreign keys
   ├─> Update progress: 30%
   ├─> Generate dictionary via LLM
   │   └─> await _generate_table_dictionary(...)
   ├─> Update progress: 90%
   ├─> Save dictionary to database
   │   └─> await _save_dictionary_to_db(...)
   ├─> Update task status to DONE
   ├─> Update progress: 100%
   ├─> Check job completion
   │   └─> await _check_job_completion(job)
   └─> Persist job status

5. _generate_table_dictionary(job, table_task, schema_info, sample_data)
   ├─> Initialize result = None
   ├─> Retry loop (max 3 attempts):
   │   ├─> Get database session
   │   ├─> Initialize LLM service (once)
   │   ├─> Get active model
   │   ├─> Create prompt
   │   │   └─> _create_dictionary_prompt()
   │   │       ├─> Include table schema
   │   │       ├─> Include sample data
   │   │       ├─> Include business context
   │   │       └─> Request JSON format
   │   ├─> Call LLM: await _llm_service.generate_text(...)
   │   ├─> Parse JSON response
   │   │   ├─> Remove markdown code blocks
   │   │   ├─> Extract JSON from response
   │   │   ├─> Clean JSON (remove trailing commas, fix missing commas)
   │   │   ├─> Try json.loads()
   │   │   ├─> If fails, try repair_json_text()
   │   │   ├─> If fails, try recursive column extraction
   │   │   ├─> If fails, try regex fallback
   │   │   └─> If all fail, retry or raise error
   │   ├─> Set result = parsed_json
   │   └─> Return result
   │
   └─> Return result (or raise exception)

6. _save_dictionary_to_db(snapshot_id, dictionary_result, schema_name)
   ├─> Get database session
   ├─> Extract table_info and columns_info from result
   ├─> Check if table description exists
   │   ├─> If exists: Update
   │   └─> If not: Insert
   ├─> For each column:
   │   ├─> Check if column description exists
   │   ├─> If exists: Update
   │   └─> If not: Insert
   ├─> Commit transaction
   └─> Log success

7. _check_job_completion(job)
   ├─> Count completed tasks (DONE status)
   ├─> Count failed tasks (FAILED status)
   ├─> Check if all tasks are done
   │   ├─> If all DONE: Set job status to DONE
   │   ├─> If any FAILED: Set job status to FAILED
   │   └─> Otherwise: Keep PROCESSING
   └─> Persist job status

┌─────────────────────────────────────────────────────────────────┐
│                    STATUS POLLING                                │
└─────────────────────────────────────────────────────────────────┘

Frontend polls every 2 seconds:
  GET /api/data-dictionary/ai-generate/status/{job_id}
    └─> Returns:
        - job_id
        - status (waiting/processing/completed/failed/paused/canceled)
        - total_tables
        - completed_tables
        - current_table
        - progress (percentage)
        - created_at
        - updated_at

When status = "completed":
  └─> Stop polling
  └─> Refresh dictionary data
  └─> Show success notification

```

---

## Frontend Flow

### 1. Page Load
```typescript
// frontend/app/data-dictionary/page.tsx

useEffect(() => {
  fetchSnapshots()
  if (selectedSnapshot) {
    fetchDataDictionary(selectedSnapshot.id)
    fetchAiJobs(selectedSnapshot.id)
  }
}, [selectedSnapshot])
```

### 2. Create AI Job
```typescript
const handleGenerateAI = async () => {
  const response = await fetch('/api/data-dictionary/ai-generate', {
    method: 'POST',
    body: JSON.stringify({
      snapshot_id: selectedSnapshot.id,
      business_domain: formData.businessDomain,
      database_description: formData.databaseDescription,
      target_user: formData.targetUser,
      language: formData.language || 'persian'
    })
  })
  
  const data = await response.json()
  setNewJobId(data.job_id)
  startJobPolling(data.job_id)
}
```

### 3. Polling
```typescript
const startJobPolling = (jobId: string) => {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/data-dictionary/ai-generate/status/${jobId}`)
    const statusData = await response.json()
    
    // Update job in state
    setAiJobs(prev => prev.map(job => 
      job.job_id === jobId ? { ...job, ...statusData } : job
    ))
    
    // Check if completed
    if (statusData.status === 'completed') {
      clearInterval(interval)
      fetchDataDictionary(selectedSnapshot.id) // Refresh data
    }
  }, 2000) // Poll every 2 seconds
}
```

---

## Backend Flow

### 1. Job Creation
```python
# backend/api/data_dictionary.py

@router.post("/ai-generate")
async def generate_ai_dictionary(request, background_tasks, session):
    # Create job
    job_id = await ai_dictionary_generator.create_job(
        session=session,
        snapshot_id=request.snapshot_id,
        business_domain=request.business_domain,
        language=request.language or "persian",
        audience=request.target_user,
        tone="professional",
        scope=GenerationScope.FULL_SNAPSHOT,
        target_names=[],
        row_sample_limit=5
    )
    
    # Start in background
    background_tasks.add_task(ai_dictionary_generator.start_job, job_id)
    
    return {"success": True, "job_id": job_id}
```

### 2. Job Processing
```python
# backend/services/ai_dictionary_generator.py

async def start_job(self, job_id: str):
    # Load job
    job = self._jobs[job_id]
    
    # Start workers if needed
    if not self._workers:
        for i in range(3):  # 3 concurrent workers
            worker = asyncio.create_task(self._process_queue_worker(i))
            self._workers.append(worker)
    
    # Queue all table tasks
    for table_key, task in job.table_tasks.items():
        if task.status == JobStatus.WAITING:
            await self._queue.put((job_id, table_key))
```

### 3. Worker Processing
```python
async def _process_queue_worker(self, worker_id: int):
    while True:
        job_id, table_key = await self._queue.get()
        try:
            await self._process_table_task(job_id, table_key)
        except Exception as e:
            logger.error(f"Error processing {table_key}: {e}")
        finally:
            self._queue.task_done()
```

### 4. Table Task Processing
```python
async def _process_table_task(self, job_id: str, table_key: str):
    # 1. Sample data (5 rows)
    sample_data = await self._sample_table_data(...)
    
    # 2. Get schema
    schema_info = await self._get_table_schema(...)
    
    # 3. Generate dictionary
    dictionary_result = await self._generate_table_dictionary(
        job, table_task, schema_info, sample_data
    )
    
    # 4. Save to database
    await self._save_dictionary_to_db(
        snapshot_id=job.snapshot_id,
        dictionary_result=dictionary_result,
        schema_name=table_task.schema_name
    )
    
    # 5. Mark task as done
    table_task.status = JobStatus.DONE
    table_task.progress = 100.0
    
    # 6. Check job completion
    await self._check_job_completion(job)
```

### 5. LLM Generation
```python
async def _generate_table_dictionary(...):
    result = None
    max_retries = 2
    
    while retry_count <= max_retries:
        # Create prompt
        prompt = self._create_dictionary_prompt(...)
        
        # Call LLM
        response = await self._llm_service.generate_text(
            session=session,
            model_id=model_id,
            prompt=prompt,
            temperature=0.3,
            max_tokens=2000
        )
        
        # Parse JSON
        try:
            # Clean response
            json_text = extract_json_from_response(response.text)
            
            # Try parsing
            result = json.loads(json_text)
            break  # Success
            
        except json.JSONDecodeError:
            # Try repair
            try:
                repaired = repair_json_text(json_text)
                result = json.loads(repaired)
                break
            except:
                # Try recursive extraction
                result = extract_columns_recursively(json_text)
                break
    
    return result
```

---

## Database Operations

### Tables Used

1. **AIGenerationJob**
   - Stores job metadata
   - Fields: job_id, snapshot_id, status, total_tables, completed_tables, progress_data

2. **DataDictionary**
   - Stores table and column descriptions
   - Fields: schema_name, table_name, column_name, description, example_values

3. **SchemaMetadata**
   - Stores table/column schema information
   - Used for sampling and schema retrieval

### Operations

```python
# Create Job
job = AIGenerationJob(
    job_id=job_id,
    snapshot_id=snapshot_id,
    status="waiting",
    total_tables=len(tables),
    completed_tables=0
)
session.add(job)
await session.commit()

# Update Job Status
await session.execute(
    update(AIGenerationJob)
    .where(AIGenerationJob.job_id == job_id)
    .values(status="processing", updated_at=datetime.now())
)
await session.commit()

# Save Dictionary
table_dict = DataDictionary(
    schema_snapshot_id=snapshot_id,
    schema_name=schema_name,
    table_name=table_name,
    description=table_info["business_description"],
    is_ai_generated=True
)
session.add(table_dict)

for column in columns_info:
    column_dict = DataDictionary(
        schema_snapshot_id=snapshot_id,
        schema_name=schema_name,
        table_name=table_name,
        column_name=column["name"],
        description=column["description"],
        example_values=json.dumps([column.get("real_example")]),
        is_ai_generated=True
    )
    session.add(column_dict)

await session.commit()
```

---

## Error Handling

### 1. JSON Parsing Errors
```python
try:
    result = json.loads(json_text)
except json.JSONDecodeError:
    # Try repair
    repaired = repair_json_text(json_text)
    result = json.loads(repaired)
except:
    # Try recursive extraction
    result = extract_columns_recursively(json_text)
```

### 2. Task Failures
```python
try:
    await self._process_table_task(job_id, table_key)
except Exception as e:
    table_task.status = JobStatus.FAILED
    table_task.error_message = str(e)[:1000]
    await self._persist_job_async(job)
```

### 3. Stuck Tasks
```python
# Detect tasks stuck in PROCESSING for >10 minutes
if table_task.status == JobStatus.PROCESSING:
    if (datetime.now() - table_task.started_at).total_seconds() > 600:
        table_task.status = JobStatus.FAILED
        table_task.error_message = "Task timeout after 10 minutes"
```

---

## Status Management

### Job Statuses
- **WAITING**: Job created, not started
- **PROCESSING**: Job is being processed
- **DONE**: All tasks completed successfully
- **FAILED**: One or more tasks failed
- **PAUSED**: Job paused by user
- **CANCELED**: Job canceled by user

### Task Statuses
- **WAITING**: Task queued, not started
- **PROCESSING**: Task being processed
- **DONE**: Task completed successfully
- **FAILED**: Task failed with error
- **CANCELED**: Task canceled

### Progress Calculation
```python
completed_tables = sum(
    1 for task in job.table_tasks.values()
    if task.status == JobStatus.DONE
)

progress = (completed_tables / len(job.table_tasks)) * 100
```

---

## Key Functions Reference

### Backend Functions

1. **create_job()**: Creates a new dictionary generation job
2. **start_job()**: Starts processing a job
3. **pause_job()**: Pauses a running job
4. **resume_job()**: Resumes a paused job
5. **cancel_job()**: Cancels a job
6. **_process_queue_worker()**: Worker task that processes queue
7. **_process_table_task()**: Processes a single table task
8. **_generate_table_dictionary()**: Generates dictionary via LLM
9. **_save_dictionary_to_db()**: Saves dictionary to database
10. **_check_job_completion()**: Checks if job is complete

### Frontend Functions

1. **fetchSnapshots()**: Fetches available snapshots
2. **fetchDataDictionary()**: Fetches dictionary data
3. **fetchAiJobs()**: Fetches AI generation jobs
4. **handleGenerateAI()**: Creates new AI job
5. **startJobPolling()**: Starts polling for job status
6. **handleAiJobAction()**: Handles pause/resume/cancel actions

---

## API Endpoints

### POST /api/data-dictionary/ai-generate
Creates a new AI dictionary generation job.

**Request:**
```json
{
  "snapshot_id": 1,
  "business_domain": "Financial Services",
  "database_description": "Trading database",
  "target_user": "Data Analysts",
  "language": "persian"
}
```

**Response:**
```json
{
  "success": true,
  "message": "AI dictionary generation started successfully",
  "job_id": "dict_1_abc123"
}
```

### GET /api/data-dictionary/ai-generate/status/{job_id}
Gets the status of an AI generation job.

**Response:**
```json
{
  "job_id": "dict_1_abc123",
  "status": "processing",
  "total_tables": 3,
  "completed_tables": 1,
  "current_table": "dbo.EnergyExchange",
  "progress": 33.33,
  "created_at": "2025-12-27T10:00:00Z",
  "updated_at": "2025-12-27T10:05:00Z"
}
```

### POST /api/data-dictionary/ai-generate/{job_id}/pause
Pauses a running job.

### POST /api/data-dictionary/ai-generate/{job_id}/resume
Resumes a paused job.

### POST /api/data-dictionary/ai-generate/{job_id}/cancel
Cancels a job.

---

## Configuration

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `LLM_API_URL`: VLLM API endpoint
- `MAX_CONCURRENT_JOBS`: Maximum parallel LLM calls (default: 3)

### Settings
- `row_sample_limit`: Number of sample rows (default: 5)
- `max_retries`: Maximum retry attempts for LLM calls (default: 2)
- `polling_interval`: Frontend polling interval (default: 2000ms)
- `task_timeout`: Task timeout in seconds (default: 600)

---

## Troubleshooting

### Common Issues

1. **JSON Parsing Errors**
   - **Cause**: LLM returns malformed JSON
   - **Solution**: Multiple fallback mechanisms (repair, recursive extraction)

2. **Stuck Tasks**
   - **Cause**: Task stuck in PROCESSING state
   - **Solution**: Timeout detection (10 minutes) marks task as FAILED

3. **Unicode Errors**
   - **Cause**: Persian text in logs
   - **Solution**: ASCII-safe encoding for log messages

4. **Progress Not Updating**
   - **Cause**: Database not flushed
   - **Solution**: session.flush() after progress updates

---

## Performance Considerations

1. **Concurrent Processing**: 3 workers process tasks in parallel
2. **Queue System**: Asyncio queue for task distribution
3. **Database Sampling**: Only 5 rows sampled per table
4. **LLM Caching**: LLM service initialized once per job
5. **Polling Optimization**: Frontend polls every 2 seconds, full refresh every 10 seconds

---

## Future Improvements

1. WebSocket support for real-time updates
2. Batch processing for large databases
3. Incremental updates (only changed tables)
4. Custom prompt templates
5. Multi-language support
6. Export functionality (PDF, Excel)

---

## Version History

- **v2.0.0** (2025-12-27): Complete rewrite with queue system
- **v1.0.0** (2025-12-20): Initial implementation

---

## Contact & Support

For issues or questions, please refer to the main project documentation or contact the development team.




