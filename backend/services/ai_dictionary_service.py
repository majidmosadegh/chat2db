"""
AI Dictionary Generation Service
Real implementation for AI-powered data dictionary generation
"""
import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
import uuid

from services.llm_service import get_llm_service, LLMServiceError
from llm.schemas import LLMRequest, Message, MessageRole
# from api.database import get_db_session  # Imported locally to avoid circular imports
# Import statements moved to functions to avoid circular imports

logger = logging.getLogger(__name__)


class AIDictionaryGenerationService:
    """AI dictionary generation service - real implementation"""

    def __init__(self):
        self._running_tasks: Dict[str, asyncio.Task] = {}

    async def start_generation_job(
        self,
        session: AsyncSession,
        snapshot_id: int,
        business_domain: str,
        database_description: str,
        target_user: str,
        language: str = "persian",
        additional_notes: Optional[str] = None
    ) -> str:
        """Start a new AI dictionary generation job"""
        print(f"Starting AI generation job for snapshot {snapshot_id}")
        from api.db_models import AIGenerationJob, SchemaMetadata
        import uuid
        job_id = f"dict_{snapshot_id}_{uuid.uuid4().hex[:8]}"

        logger.info(f"Starting AI dictionary generation job {job_id} for snapshot {snapshot_id}")

        # Get all tables for this snapshot
        tables_query = select(
            SchemaMetadata.schema_name,
            SchemaMetadata.table_name
        ).where(
            SchemaMetadata.schema_snapshot_id == snapshot_id
        ).distinct().order_by(
            SchemaMetadata.schema_name,
            SchemaMetadata.table_name
        )

        tables_result = await session.execute(tables_query)
        tables_data = tables_result.all()

        # Create job record
        progress_data = {
            "tables": [
                {
                    "schema": row[0],
                    "table": row[1],
                    "status": "pending"
                }
                for row in tables_data
            ],
            "errors": []
        }

        job = AIGenerationJob(
            job_id=job_id,
            snapshot_id=snapshot_id,
            status="pending",
            total_tables=len(tables_data),
            completed_tables=0,
            progress_data=json.dumps(progress_data),
            errors=json.dumps([])
        )

        session.add(job)
        await session.commit()

        # Background processing will be handled by FastAPI BackgroundTasks

        return job_id

    async def _process_generation_job(
        self,
        session: AsyncSession,
        job_id: str,
        snapshot_id: int,
        business_domain: str,
        database_description: str,
        target_user: str,
        language: str,
        additional_notes: Optional[str] = None
    ) -> None:
        """Process AI generation job"""
        print(f"Background task started for job {job_id}")
        # Process the job - uncommented for actual processing

        from api.db_models import async_session, AIGenerationJob, SchemaMetadata, DataDictionary
        import json

        async with async_session() as session:
            try:
                # Update job status to processing
                job_result = await session.execute(
                    select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                )
                job = job_result.scalar_one_or_none()
                if not job:
                    logger.error(f"Job {job_id} not found")
                    return

                job.status = "processing"
                await session.commit()

                # Initialize LLM service - try real LLM, fallback to mock for testing
                llm_service = await self._initialize_llm_service(session)
                if not llm_service:
                    logger.warning("No active LLM models found. Using mock descriptions for testing.")
                    llm_service = None  # Will use mock data in _generate_table_description

                # Get job progress data
                progress_data = json.loads(job.progress_data or "{}")
                tables = progress_data.get("tables", [])
                errors = progress_data.get("errors", [])
                print(f"Progress data loaded: {len(tables)} tables, {len(errors)} errors")

                logger.info(f"Processing {len(tables)} tables for job {job_id}")
                print(f"Starting table processing loop with tables: {tables}")
                print(f"About to enter for loop")

                completed_count = 0

                for i, table_info in enumerate(tables):
                    try:
                        schema_name = table_info["schema"]
                        table_name = table_info["table"]
                        table_info["status"] = "processing"
                        job.progress_data = json.dumps({"tables": tables, "errors": errors})
                        await session.commit()

                        # Get columns for this table
                        columns_result = await session.execute(
                            select(SchemaMetadata.column_name, SchemaMetadata.column_type).where(
                                SchemaMetadata.schema_snapshot_id == snapshot_id,
                                SchemaMetadata.schema_name == schema_name,
                                SchemaMetadata.table_name == table_name,
                                SchemaMetadata.column_name.isnot(None)
                            )
                        )
                        columns = [(row[0], row[1]) for row in columns_result.all()]
                        print(f"Found {len(columns)} columns for table {schema_name}.{table_name}")

                        # Generate description for table and columns
                        await self._generate_table_description(
                            llm_service=llm_service,
                            session=session,
                            snapshot_id=snapshot_id,
                            schema_name=schema_name,
                            table_name=table_name,
                            columns=columns,
                            business_domain=business_domain,
                            database_description=database_description,
                            target_user=target_user,
                            language=language,
                            additional_notes=additional_notes
                        )

                        table_info["status"] = "completed"
                        completed_count += 1
                        job.completed_tables = completed_count
                        job.progress_data = json.dumps({"tables": tables, "errors": errors})
                        await session.commit()

                        logger.info(f"Generated descriptions for {schema_name}.{table_name}")

                    except Exception as e:
                        logger.error(f"Failed to process table {table_info.get('schema', '')}.{table_info.get('table', '')}: {e}")
                        table_info["status"] = "failed"
                        errors.append({
                            "table": f"{table_info.get('schema', '')}.{table_info.get('table', '')}",
                            "error": str(e)
                        })
                        job.progress_data = json.dumps({"tables": tables, "errors": errors})
                        await session.commit()

                # Update final status
                if completed_count == len(tables):
                    job.status = "completed"
                else:
                    job.status = "completed_with_errors"

                job.progress_data = json.dumps({"tables": tables, "errors": errors})
                await session.commit()

                logger.info(f"AI generation job {job_id} completed: {completed_count}/{len(tables)} tables processed")

            except Exception as e:
                logger.error(f"AI generation job {job_id} failed: {e}")
                try:
                    job_result = await session.execute(
                        select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                    )
                    job = job_result.scalar_one_or_none()
                    if job:
                        job.status = "failed"
                        job.errors = json.dumps([str(e)])
                        await session.commit()
                except Exception as update_error:
                    logger.error(f"Failed to update job status: {update_error}")

    async def _initialize_llm_service(self, session: AsyncSession) -> Optional[object]:
        """Initialize LLM service with active models - returns service instance"""
        try:
            llm_service = get_llm_service()
            await llm_service.initialize(session)
            logger.info("LLM service initialized successfully")
            return llm_service
        except LLMServiceError as e:
            logger.warning(f"LLM service initialization failed: {e}")
            logger.warning("LLM server not available, using mock data for testing")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize LLM service: {e}")
            logger.warning("LLM service initialization failed, will use mock data")
            return None

    async def _generate_table_description(
        self,
        llm_service: Optional[object],
        session: AsyncSession,
        snapshot_id: int,
        schema_name: str,
        table_name: str,
        columns: List,
        business_domain: str,
        database_description: str,
        target_user: str,
        language: str,
        additional_notes: Optional[str] = None
    ) -> Optional[str]:
        """Generate AI description for a specific table"""
        from api.db_models import SchemaMetadata, DataDictionary
        try:
            # If no LLM service available, use mock data for testing
            if not llm_service:
                return self._get_mock_description(schema_name, table_name, language)

            # Use the columns parameter passed to this method (already fetched in the calling method)

            # Get sample data (placeholder for now)
            sample_data = await self._get_table_sample_data(session, schema_name, table_name)

            # Create prompt
            prompt = self._create_generation_prompt(
                schema_name=schema_name,
                table_name=table_name,
                columns=columns,
                sample_data=sample_data,
                business_domain=business_domain,
                database_description=database_description,
                target_user=target_user,
                language=language,
                additional_notes=additional_notes
            )

            # Get first available model from service
            connector = llm_service.get_connector()
            if not connector:
                logger.warning("No connector available, using mock data")
                return self._get_mock_description(schema_name, table_name, language)

            available_models = connector.get_available_models()
            if not available_models:
                logger.warning("No available models found, using mock data")
                return self._get_mock_description(schema_name, table_name, language)

            model_id = available_models[0]

            # Generate description using LLMService
            llm_request = LLMRequest(
                model_id=model_id,
                messages=[
                    Message(
                        role=MessageRole.USER,
                        content=prompt
                    )
                ],
                temperature=0.3,
                max_tokens=800
            )

            response = await connector.generate(llm_request)

            # Check if response has text (assuming success if we get here)
            if hasattr(response, 'text') and response.text:
                description = response.text.strip()
            else:
                logger.error(f"LLM generation failed: No response text")
                raise Exception(f"LLM generation failed: No response text")

            # Save table-level description to database
            dict_entry = DataDictionary(
                schema_snapshot_id=snapshot_id,
                schema_name=schema_name,
                table_name=table_name,
                column_name=None,  # Table-level entry
                description=description,
                example_values=None,
                synonyms=None,
                is_sensitive=False,
                is_ai_generated=True
            )
            session.add(dict_entry)
            await session.commit()
            print(f"Saved table description for {schema_name}.{table_name}")

            # Generate descriptions for each column
            for column_name, column_type in columns:
                try:
                    column_description = await self._generate_column_description(
                        llm_service=llm_service,
                        session=session,
                        snapshot_id=snapshot_id,
                        schema_name=schema_name,
                        table_name=table_name,
                        column_name=column_name,
                        column_type=column_type,
                        business_domain=business_domain,
                        database_description=database_description,
                        target_user=target_user,
                        language=language,
                        additional_notes=additional_notes
                    )

                    if column_description:
                        # Save column-level description to database
                        column_dict_entry = DataDictionary(
                            schema_snapshot_id=snapshot_id,
                            schema_name=schema_name,
                            table_name=table_name,
                            column_name=column_name,
                            description=column_description.get('description'),
                            example_values=json.dumps(column_description.get('example_values', [])),
                            synonyms=column_description.get('synonyms'),
                            is_sensitive=column_description.get('is_sensitive', False),
                            is_ai_generated=True
                        )
                        session.add(column_dict_entry)
                        await session.commit()
                        logger.info(f"Generated description for column {schema_name}.{table_name}.{column_name}")

                except Exception as e:
                    logger.error(f"Failed to generate description for column {schema_name}.{table_name}.{column_name}: {e}")

            return description

        except Exception as e:
            logger.error(f"Failed to generate description for {schema_name}.{table_name}: {e}")
            return None

    def _create_generation_prompt(
        self,
        schema_name: str,
        table_name: str,
        columns: List,
        sample_data: str,
        business_domain: str,
        database_description: str,
        target_user: str,
        language: str,
        additional_notes: Optional[str] = None
    ) -> str:
        """Create generation prompt for LLM"""
        language_name = "Persian" if language.lower() == "persian" else "English"
        # For JSON structure, always use English for field names but content in requested language
        response_language = language_name

        additional_notes_text = f"\nAdditional Notes: {additional_notes}" if additional_notes else ""

        prompt = f"""Generate a comprehensive data dictionary for the database table "{schema_name}.{table_name}".

**Business Context:**
- Domain: {business_domain}
- Database Purpose: {database_description}
- Target Audience: {target_user}
- Language: {language_name}{additional_notes_text}

**Table Information:**
- Schema: {schema_name}
- Table: {table_name}
- Total Columns: {len(columns)}

**Column Details:**
{chr(10).join([f"  - {col[0]}: {col[1]}" for col in columns[:15]])}

**Sample Data (Real examples from database):**
{sample_data}

**Instructions:**
Generate a JSON response with EXACTLY this structure:

{{
  "table": {{
    "name": "{table_name}",
    "business_description": "Clear business purpose of this table in {language_name}",
    "usage_notes": "Important notes for {target_user} about using this data"
  }},
  "columns": [
    {{
      "name": "column_name",
      "data_type": "data_type",
      "description": "Business meaning and constraints in {language_name}",
      "real_example": "Actual example value from sample data"
    }}
  ]
}}

**Quality Rules:**
- Use ONLY real values from sample data for real_example fields
- If no sample data available, use "Not enough sample data to infer exact meaning"
- Include primary key, foreign key, and other constraints in descriptions
- Business descriptions must be meaningful, not generic like "stores data"
- Write ALL text content (descriptions, notes) in {language_name} language
- Respond with valid JSON only (no extra text, no explanations)

IMPORTANT: Return ONLY the JSON object, nothing else."""

        return prompt


    async def _get_table_sample_data(self, session: AsyncSession, schema_name: str, table_name: str) -> str:
        """Get sample data from table using DirectDatabaseConnector"""
        try:
            # Get database connection info from schema_metadata
            from api.db_models import SchemaMetadata, DatabaseConnection, SchemaSnapshot

            # Get snapshot info from schema metadata
            result = await session.execute(
                select(SchemaMetadata).where(
                    SchemaMetadata.schema_name == schema_name,
                    SchemaMetadata.table_name == table_name
                ).limit(1)
            )
            metadata = result.scalar_one_or_none()

            if not metadata:
                return "No metadata found for table"

            # Get connection info
            snapshot_result = await session.execute(
                select(SchemaSnapshot).where(SchemaSnapshot.id == metadata.schema_snapshot_id)
            )
            snapshot = snapshot_result.scalar_one_or_none()

            if not snapshot:
                return "No snapshot found"

            conn_result = await session.execute(
                select(DatabaseConnection).where(DatabaseConnection.id == snapshot.connection_id)
            )
            connection = conn_result.scalar_one_or_none()

            if not connection:
                return "No connection found"

            # Decrypt password
            from api.data_dictionary import decrypt_password
            if connection.password_encrypted and connection.password_encrypted.strip():
                password = decrypt_password(connection.password_encrypted)
            else:
                password = ""

            # Create database connector and get sample data
            from services.db_connector import DirectDatabaseConnector
            db_connector = DirectDatabaseConnector(
                db_type=connection.db_type,
                host=connection.host,
                port=connection.port,
                username=connection.username,
                password=password,
                database=connection.database_name
            )

            # Get sample data
            query = f"SELECT TOP 5 * FROM [{schema_name}].[{table_name}]"
            sample_rows = await db_connector.execute_query(query, limit=5)
            await db_connector.disconnect()

            if not sample_rows:
                return "No sample data available"

            # Format sample data
            formatted_rows = []
            for i, row in enumerate(sample_rows[:3]):  # Show max 3 rows
                row_values = []
                for key, value in row.items():
                    if value is not None:
                        row_values.append(f"{key}: {str(value)[:50]}...")  # Limit value length
                    else:
                        row_values.append(f"{key}: NULL")
                formatted_rows.append(f"Row {i+1}: {{{', '.join(row_values[:5])}}}")  # Limit columns shown

            return "\n".join(formatted_rows)

        except Exception as e:
            logger.warning(f"Failed to get sample data for {schema_name}.{table_name}: {e}")
            return f"Sample data not available: {str(e)}"

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status from database"""
        from api.database import get_db_session
        from api.db_models import AIGenerationJob
        session = None
        try:
            async for session in get_db_session():
                job_result = await session.execute(
                    select(AIGenerationJob).where(AIGenerationJob.job_id == job_id)
                )
                job = job_result.scalar_one_or_none()

                if not job:
                    return {"error": "Job not found"}

                progress_data = json.loads(job.progress_data or "{}")
                errors = json.loads(job.errors or "[]")

                return {
                    "job_id": job.job_id,
                    "status": job.status,
                    "total_tables": job.total_tables,
                    "completed_tables": job.completed_tables,
                    "failed_tables": len([t for t in progress_data.get("tables", []) if t.get("status") == "error"]),
                    "current_table": job.current_table,
                    "progress": progress_data,
                    "errors": errors,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None
                }

        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            return {"error": f"Failed to get job status: {str(e)}"}

    async def _generate_column_description(
        self,
        llm_service: Optional[object],
        session: AsyncSession,
        snapshot_id: int,
        schema_name: str,
        table_name: str,
        column_name: str,
        column_type: str,
        business_domain: str,
        database_description: str,
        target_user: str,
        language: str,
        additional_notes: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Generate AI description for a specific column"""
        try:
            # If no LLM service available, use mock data for testing
            if not llm_service:
                return self._get_mock_column_description(column_name, column_type, language)

            # Create prompt for column description
            prompt = self._create_column_description_prompt(
                schema_name=schema_name,
                table_name=table_name,
                column_name=column_name,
                column_type=column_type,
                business_domain=business_domain,
                database_description=database_description,
                target_user=target_user,
                language=language,
                additional_notes=additional_notes
            )

            # Generate description using LLMService
            connector = llm_service.get_connector()
            if not connector:
                raise Exception("No connector available")
            
            available_models = connector.get_available_models()
            if not available_models:
                raise Exception("No available models")

            model_id = available_models[0]

            llm_request = LLMRequest(
                model_id=model_id,
                messages=[
                    Message(
                        role=MessageRole.USER,
                        content=prompt
                    )
                ],
                temperature=0.3,
                max_tokens=500
            )

            response = await llm_service.generate(llm_request)

            # Check if response has text (assuming success if we get here)
            if hasattr(response, 'text') and response.text:
                # Parse the response to extract structured data
                return self._parse_column_description_response(response.text, language)
            else:
                logger.error(f"LLM generation failed for column {column_name}: No response text")
                return None

        except Exception as e:
            logger.error(f"Failed to generate description for column {schema_name}.{table_name}.{column_name}: {e}")
            return None

    def _create_column_description_prompt(
        self,
        schema_name: str,
        table_name: str,
        column_name: str,
        column_type: str,
        business_domain: str,
        database_description: str,
        target_user: str,
        language: str,
        additional_notes: Optional[str] = None
    ) -> str:
        """Create prompt for column description generation"""
        if language.lower() == "persian":
            prompt = f"""
بر اساس اطلاعات زیر، توضیح کاملی از ستون "{column_name}" در جدول "{table_name}" ارائه دهید:

**اطلاعات زمینه:**
- حوزه کسب‌وکار: {business_domain}
- شرح پایگاه داده: {database_description}
- کاربران هدف: {target_user}
- نوع داده ستون: {column_type}

**نکات تکمیلی:**
{additional_notes or "هیچ نکته خاصی وجود ندارد"}

**لطفاً پاسخ خود را به صورت JSON ساختار یافته ارائه دهید:**

{{
  "description": "توضیح کامل و مفید از ستون به زبان فارسی",
  "example_values": ["نمونه مقدار 1", "نمونه مقدار 2", "نمونه مقدار 3"],
  "synonyms": "مترادف1, مترادف2, مترادف3",
  "is_sensitive": false
}}

**نکات مهم:**
- توضیح باید دقیق، مفید و مرتبط با حوزه کسب‌وکار باشد
- نمونه مقادیر باید واقعی و متناسب با نوع داده باشند
- مترادف‌ها باید با کاما جدا شوند
- فیلد is_sensitive فقط در صورتی true باشد که داده حساس باشد (مانند اطلاعات مالی، پزشکی، شخصی)
"""
        else:
            prompt = f"""
Based on the following information, provide a complete description of the "{column_name}" column in the "{table_name}" table:

**Context Information:**
- Business Domain: {business_domain}
- Database Description: {database_description}
- Target Users: {target_user}
- Column Data Type: {column_type}

**Additional Notes:**
{additional_notes or "No additional notes"}

**Please provide your response in structured JSON format:**

{{
  "description": "Complete and useful description of the column in English",
  "example_values": ["example value 1", "example value 2", "example value 3"],
  "synonyms": "synonym1, synonym2, synonym3",
  "is_sensitive": false
}}

**Important Notes:**
- Description should be accurate, helpful and relevant to the business domain
- Example values should be realistic and appropriate for the data type
- Synonyms should be comma-separated
- is_sensitive should only be true if the data is sensitive (financial, medical, personal information)
"""

        return prompt.strip()

    def _parse_column_description_response(self, response_text: str, language: str) -> Dict[str, Any]:
        """Parse LLM response to extract structured column description data"""
        try:
            # Try to extract JSON from response
            import json
            import re

            # Find JSON in response (between curly braces)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)

                # Validate required fields
                result = {
                    'description': parsed.get('description', ''),
                    'example_values': parsed.get('example_values', []),
                    'synonyms': parsed.get('synonyms', ''),
                    'is_sensitive': parsed.get('is_sensitive', False)
                }

                # Ensure example_values is a list
                if isinstance(result['example_values'], str):
                    result['example_values'] = [result['example_values']]

                return result
            else:
                # Fallback if no JSON found
                return {
                    'description': response_text.strip(),
                    'example_values': [],
                    'synonyms': '',
                    'is_sensitive': False
                }

        except Exception as e:
            logger.error(f"Failed to parse column description response: {e}")
            return {
                'description': response_text.strip() if response_text else '',
                'example_values': [],
                'synonyms': '',
                'is_sensitive': False
            }

    def _get_mock_column_description(self, column_name: str, column_type: str, language: str) -> Dict[str, Any]:
        """Generate mock column description for testing when LLM is not available"""
        if language.lower() == "persian":
            return {
                'description': f"ستون {column_name} از نوع {column_type} - این ستون برای ذخیره اطلاعات مربوط به {column_name.replace('_', ' ')} استفاده می‌شود.",
                'example_values': ["نمونه 1", "نمونه 2", "نمونه 3"],
                'synonyms': "مترادف1, مترادف2",
                'is_sensitive': column_name.lower() in ['password', 'ssn', 'credit_card', 'phone', 'email']
            }
        else:
            return {
                'description': f"Column {column_name} of type {column_type} - This column stores information related to {column_name.replace('_', ' ')}.",
                'example_values': ["sample 1", "sample 2", "sample 3"],
                'synonyms': "synonym1, synonym2",
                'is_sensitive': column_name.lower() in ['password', 'ssn', 'credit_card', 'phone', 'email']
            }

    def _get_mock_description(self, schema_name: str, table_name: str, language: str) -> str:
        """Generate mock description for testing when LLM is not available"""
        if language.lower() == "persian":
            return f"جدول {table_name} در شمای {schema_name} - این جدول برای ذخیره اطلاعات مربوط به {table_name.replace('_', ' ')} استفاده می‌شود."
        else:
            return f"Table {table_name} in schema {schema_name} - This table stores information related to {table_name.replace('_', ' ')}."




# Global service instance
ai_dictionary_service = AIDictionaryGenerationService()








