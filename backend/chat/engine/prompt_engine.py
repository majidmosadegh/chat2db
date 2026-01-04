from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import logging
import re

from ..schemas import (
    ChatContext, PromptTemplate, ChatLanguage,
    SchemaInfo, DataDictionaryInfo, RelationshipInfo, UseCaseInfo
)

logger = logging.getLogger(__name__)


class PromptEngine:
    """Engine for building deterministic, versioned, and serializable prompts"""

    # Current prompt versions
    PROMPT_VERSIONS = {
        "reasoning": "1.0.0",
        "sql": "1.1.0",
        "validation": "1.0.0"
    }

    def __init__(self):
        self.templates = self._initialize_templates()

    def _initialize_templates(self) -> Dict[str, PromptTemplate]:
        """Initialize all prompt templates"""
        templates = {}

        # Reasoning prompt - understands user intent and relevant tables
        templates["reasoning_en"] = PromptTemplate(
            version=self.PROMPT_VERSIONS["reasoning"],
            template_type="reasoning",
            language=ChatLanguage.ENGLISH,
            template=self._get_reasoning_template_en(),
            variables=["context", "question", "conversation_history"]
        )

        templates["reasoning_fa"] = PromptTemplate(
            version=self.PROMPT_VERSIONS["reasoning"],
            template_type="reasoning",
            language=ChatLanguage.PERSIAN,
            template=self._get_reasoning_template_fa(),
            variables=["context", "question", "conversation_history"]
        )

        # SQL generation prompts for different database types
        templates["sql_postgresql_en"] = PromptTemplate(
            version=self.PROMPT_VERSIONS["sql"],
            template_type="sql",
            language=ChatLanguage.ENGLISH,
            template=self._get_sql_template_postgresql_en(),
            variables=["reasoning_output", "context", "question"]
        )

        templates["sql_mysql_en"] = PromptTemplate(
            version=self.PROMPT_VERSIONS["sql"],
            template_type="sql",
            language=ChatLanguage.ENGLISH,
            template=self._get_sql_template_mysql_en(),
            variables=["reasoning_output", "context", "question"]
        )

        templates["sql_sqlserver_en"] = PromptTemplate(
            version=self.PROMPT_VERSIONS["sql"],
            template_type="sql",
            language=ChatLanguage.ENGLISH,
            template=self._get_sql_template_sqlserver_en(),
            variables=["reasoning_output", "context", "question"]
        )

        # Backward compatibility
        templates["sql_en"] = templates["sql_postgresql_en"]
        templates["sql_fa"] = PromptTemplate(
            version=self.PROMPT_VERSIONS["sql"],
            template_type="sql",
            language=ChatLanguage.PERSIAN,
            template=self._get_sql_template_fa(),
            variables=["reasoning_output", "context", "question"]
        )

        # Validation prompt (future use)
        templates["validation_en"] = PromptTemplate(
            version=self.PROMPT_VERSIONS["validation"],
            template_type="validation",
            language=ChatLanguage.ENGLISH,
            template=self._get_validation_template_en(),
            variables=["sql", "context"]
        )

        return templates

    def build_reasoning_prompt(
        self,
        context: ChatContext,
        question: str,
        language: ChatLanguage,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Build reasoning prompt to understand user intent and relevant tables"""
        template_key = f"reasoning_{language.value}"
        template = self.templates.get(template_key)

        if not template:
            raise ValueError(f"No reasoning template found for language {language}")

        context_str = self._build_context_string(context)

        variables = {
            "context": context_str,
            "question": question,
            "conversation_history": self._format_conversation_history(conversation_history)
        }

        return self._render_template(template, variables)

    def build_sql_prompt(
        self,
        context: ChatContext,
        question: str,
        reasoning_output: str,
        language: ChatLanguage
    ) -> str:
        """Build SQL generation prompt based on database type"""

        import logging
        logging.info(f"DEBUG: build_sql_prompt called with language={language}, question='{question}'")

        # Enhance reasoning with query-specific guidance
        enhanced_reasoning = reasoning_output
        if language == ChatLanguage.PERSIAN:
            if any(keyword in question for keyword in ["قیمت", "price"]):
                enhanced_reasoning += "\n\nGUIDANCE: This is a price-related query. Look for tables containing price information and product names."
            elif any(keyword in question for keyword in ["تعداد", "count"]):
                enhanced_reasoning += "\n\nGUIDANCE: This is a counting query. Consider using COUNT() or similar aggregation functions."
            elif any(keyword in question for keyword in ["نمایش", "لیست", "show", "list"]):
                enhanced_reasoning += "\n\nGUIDANCE: This is a listing query. Select appropriate columns to display the requested information."

        # Select template based on database type
        db_type = context.database_type.lower()
        if db_type in ['sqlserver', 'mssql']:
            template_key = f"sql_sqlserver_{language.value}"
        elif db_type == 'mysql':
            template_key = f"sql_mysql_{language.value}"
        elif db_type == 'postgresql':
            template_key = f"sql_postgresql_{language.value}"
        else:
            # Default to PostgreSQL for unknown types
            template_key = f"sql_postgresql_{language.value}"

        template = self.templates.get(template_key)

        # Fallback to generic template if specific one not found
        if not template:
            template_key = f"sql_{language.value}"
            template = self.templates.get(template_key)

        if not template:
            raise ValueError(f"No SQL template found for language {language} and database type {db_type}")

        context_str = self._build_context_string(context)

        # No hardcoded overrides - let the LLM decide based on the schema

        variables = {
            "reasoning_output": enhanced_reasoning,
            "context": context_str,
            "question": question
        }

        return self._render_template(template, variables)

    def build_validation_prompt(
        self,
        context: ChatContext,
        sql: str,
        language: ChatLanguage
    ) -> str:
        """Build SQL validation prompt (future use)"""
        template_key = f"validation_{language.value}"
        template = self.templates.get(template_key)

        if not template:
            raise ValueError(f"No validation template found for language {language}")

        context_str = self._build_context_string(context)

        variables = {
            "sql": sql,
            "context": context_str
        }

        return self._render_template(template, variables)

    # ===== NEW 3-STAGE REASONING PIPELINE =====

    async def execute_reasoning_pipeline(
        self,
        llm_gateway,
        context: ChatContext,
        question: str,
        language: ChatLanguage,
        model_id: int,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete 3-stage reasoning pipeline.

        Returns:
            Dict with keys: intent, tables_info, sql, stage_times, errors
        """
        import time
        pipeline_start = time.time()

        result = {
            "intent": None,
            "tables_info": None,
            "sql": None,
            "query_plan": {},
            "confidence": 0.5,
            "business_value": "",
            "stage_times": {},
            "errors": []
        }

        try:
            # Stage A: Intent Detection
            stage_start = time.time()
            logger.info(f"🎯 INTENT_DETECTION_START | Question: '{question[:50]}{'...' if len(question) > 50 else ''}' | Language: {language}")

            intent_result = await self._execute_intent_detection(
                llm_gateway, question, language, model_id, conversation_history
            )
            result["stage_times"]["intent_detection"] = int((time.time() - stage_start) * 1000)
            result["intent"] = intent_result.get("intent") if intent_result else "DETAIL"

            logger.info(f"✅ INTENT_DETECTED | Intent: {result['intent']} | Confidence: {intent_result.get('confidence', 'N/A') if intent_result else 'N/A'} | Time: {result['stage_times']['intent_detection']}ms")
            logger.debug(f"📝 INTENT_DETAILS | RawResult: {intent_result} | Reasoning: {intent_result.get('reasoning', 'N/A') if intent_result else 'N/A'}")

            # Skip table selection and SQL generation for conversational queries
            if result["intent"] == "CONVERSATIONAL":
                result["stage_times"]["table_selection"] = 0
                result["stage_times"]["sql_generation"] = 0
                result["tables_info"] = {"tables": [], "required_columns": [], "filters": []}
                result["sql"] = ""
                result["query_plan"] = {}
                result["confidence"] = 0.0
                result["business_value"] = "Conversational query - no SQL needed"
                logger.info("💬 CONVERSATIONAL_SKIP | SQL generation skipped for conversational intent")
            else:
                # Stage B: Table & Scope Selection
                # Count unique tables from schema_info list
                unique_tables = set()
                if context.schema_info:
                    for schema_item in context.schema_info:
                        table_key = f"{schema_item.schema_name}.{schema_item.table_name}"
                        unique_tables.add(table_key)
                logger.info(f"📊 TABLE_SELECTION_START | Intent: {result['intent']} | AvailableTables: {len(unique_tables)} | SchemaItems: {len(context.schema_info) if context.schema_info else 0}")

                stage_start = time.time()
                tables_result = await self._execute_table_selection(
                    llm_gateway, context, question, language, model_id
                )
                result["stage_times"]["table_selection"] = int((time.time() - stage_start) * 1000)
                result["tables_info"] = tables_result if tables_result else {"tables": [], "required_columns": [], "filters": []}

                selected_tables = [t.get("table", "unknown") for t in result["tables_info"].get("tables", [])]
                logger.info(f"✅ TABLES_SELECTED | Count: {len(selected_tables)} | Tables: {selected_tables} | Time: {result['stage_times']['table_selection']}ms")
                logger.debug(f"📋 TABLE_DETAILS | RequiredColumns: {result['tables_info'].get('required_columns', [])} | Filters: {result['tables_info'].get('filters', [])}")

                # Stage C: SQL Generation (only for non-conversational queries)
                logger.info(f"🔧 SQL_GENERATION_START | Intent: {result['intent']} | SelectedTables: {len(result['tables_info'].get('tables', []))} | Language: {language}")

                stage_start = time.time()
                sql_result = await self._execute_sql_generation(
                    llm_gateway, context, question, result["intent"], result["tables_info"], language, model_id
                )
                result["stage_times"]["sql_generation"] = int((time.time() - stage_start) * 1000)
                result["sql"] = sql_result.get("sql") if sql_result else ""
                
                # Include structured query plan, confidence, and business value
                result["query_plan"] = sql_result.get("query_plan", {}) if sql_result else {}
                result["confidence"] = sql_result.get("confidence", 0.5) if sql_result else 0.5
                result["business_value"] = sql_result.get("business_value", "") if sql_result else ""

                sql_length = len(result["sql"]) if result["sql"] else 0
                sql_preview = result["sql"][:100] + "..." if len(result["sql"] or "") > 100 else (result["sql"] or "None")
                logger.info(f"✅ SQL_GENERATED | Length: {sql_length} chars | Time: {result['stage_times']['sql_generation']}ms | SQL: '{sql_preview}' | Confidence: {result.get('confidence', 0.5):.2f}")
                logger.debug(f"🔍 SQL_DETAILS | FullSQL: {result['sql']} | GenerationResult: {sql_result}")

        except Exception as e:
            error_msg = f"Reasoning pipeline failed: {str(e)}"
            result["errors"].append(error_msg)
            result["stage_times"]["total_pipeline"] = int((time.time() - pipeline_start) * 1000)

            logger.error(f"❌ REASONING_PIPELINE_ERROR | Question: '{question[:50]}{'...' if len(question) > 50 else ''}' | Error: {error_msg} | TotalTime: {result['stage_times']['total_pipeline']}ms")
            logger.error(f"🔍 PIPELINE_ERROR_DETAILS | Exception: {type(e).__name__} | StageTimes: {result['stage_times']} | Errors: {result['errors']}", exc_info=True)

            # Set fallback values
            result["intent"] = "DETAIL"
            result["tables_info"] = {"tables": [], "required_columns": [], "filters": []}
            result["sql"] = ""
            result["query_plan"] = {}
            result["confidence"] = 0.3
            result["business_value"] = ""

        result["stage_times"]["total_pipeline"] = int((time.time() - pipeline_start) * 1000)
        logger.info(f"🏁 REASONING_PIPELINE_COMPLETE | TotalTime: {result['stage_times']['total_pipeline']}ms | Intent: {result['intent']} | SQL_Length: {len(result['sql'])} | Errors: {len(result['errors'])}")
        return result

    async def _execute_intent_detection(
        self,
        llm_gateway,
        question: str,
        language: ChatLanguage,
        model_id: int,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Stage A: Detect user intent from question"""
        logger.debug(f"🔍 INTENT_PROMPT_BUILD | Question: '{question[:30]}{'...' if len(question) > 30 else ''}' | Language: {language} | History: {len(conversation_history) if conversation_history else 0} messages")

        prompt = self._build_intent_detection_prompt(question, language, conversation_history)

        logger.debug(f"🤖 INTENT_LLM_CALL | Model: {model_id} | PromptLength: {len(prompt)} chars")

        llm_response = await llm_gateway.call_llm(
            model_id=model_id,
            prompt=prompt,
            temperature=0.1  # Low temperature for deterministic intent detection
        )

        if not llm_response.success:
            logger.error(f"❌ INTENT_LLM_FAILED | Model: {model_id} | Error: {llm_response.error_message}")
            raise Exception("Intent detection LLM call failed")

        logger.debug(f"📥 INTENT_LLM_RESPONSE | Success: {llm_response.success} | ResponseLength: {len(llm_response.raw_text)} | ModelUsed: {llm_response.model_used}")

        # Parse JSON response with safe parsing
        try:
            if not llm_response.raw_text:
                raise ValueError("Empty response from LLM")

            # Use safe JSON parsing
            from ..utils.json_safety import safe_json_parse
            intent_data = safe_json_parse(llm_response.raw_text)
            return intent_data
        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            logger.warning(f"Intent detection JSON parse failed: {str(e)}, raw response: {llm_response.raw_text}")
            # Fallback: extract intent from text
            text = str(llm_response.raw_text or "").lower().strip()
            original_question = question.lower().strip()  # Use original question for better detection

            # Prioritize conversational detection
            conversational_words = ["hi", "hello", "hey", "thanks", "thank you", "help", "please", "sorry", "bye", "goodbye", "سلام", "ممنون", "تشکر", "کمک", "لطفا", "ببخشید", "خداحافظ"]
            if (any(word in original_question for word in conversational_words) or
                len(original_question.split()) <= 3 or
                not any(char.isalnum() for char in original_question)):  # Very short or empty input
                return {"intent": "CONVERSATIONAL"}

            # Check for Persian SQL keywords
            persian_sql_keywords = ["قیمت", "تعداد", "نمایش", "لیست", "جستجو", "چقدر", "چند", "نمایش", "نشان", "قیر", "سیمان", "محصول"]
            if any(keyword in original_question for keyword in persian_sql_keywords):
                return {"intent": "DETAIL"}  # Default to DETAIL for Persian queries

            elif "count" in text or "how many" in text:
                return {"intent": "COUNT"}
            elif "list" in text or "show all" in text:
                return {"intent": "LIST"}
            elif "top" in text or "highest" in text or "best" in text:
                return {"intent": "TOP_N"}
            elif "average" in text or "avg" in text or "mean" in text:
                return {"intent": "AGGREGATION"}
            elif "compare" in text or "vs" in text:
                return {"intent": "COMPARISON"}
            else:
                return {"intent": "DETAIL"}

    async def _execute_table_selection(
        self,
        llm_gateway,
        context: ChatContext,
        question: str,
        language: ChatLanguage,
        model_id: int
    ) -> Dict[str, Any]:
        """Stage B: Select relevant tables and scope"""

        # Let the LLM analyze the schema and choose appropriate tables

        prompt = self._build_table_selection_prompt(context, question, language)

        llm_response = await llm_gateway.call_llm(
            model_id=model_id,
            prompt=prompt,
            temperature=0.1  # Low temperature for deterministic table selection
        )

        if not llm_response.success:
            raise Exception("Table selection LLM call failed")

        # Parse JSON response with safe parsing
        try:
            if not llm_response.raw_text:
                raise ValueError("Empty response from LLM")

            # Use safe JSON parsing
            from ..utils.json_safety import safe_json_parse
            tables_data = safe_json_parse(llm_response.raw_text)
            return tables_data
        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            # Fallback: return basic structure
            logger.warning(f"Table selection failed, using fallback: {str(e)}")
            return {
                "tables": [],
                "required_columns": [],
                "filters": []
            }

    async def _execute_sql_generation(
        self,
        llm_gateway,
        context: ChatContext,
        question: str,
        intent: str,
        tables_info: Dict[str, Any],
        language: ChatLanguage,
        model_id: int
    ) -> Dict[str, Any]:
        """Stage C: Generate SQL based on intent and selected tables with structured JSON output"""
        # Create query plan for better SQL generation
        from .query_planner import QueryPlanner
        query_planner = QueryPlanner(context)
        entities = query_planner.extract_entities(question)
        query_plan = query_planner.plan_query(question, intent, entities)
        
        # Extract sample values from data dictionary for filters
        sample_filters = self._extract_sample_filters_from_dictionary(
            context.data_dictionary, tables_info, query_plan
        )
        
        # Build enhanced prompt that requests JSON output
        prompt = self.build_sql_generation_prompt_with_json_output(
            context, question, intent, tables_info, language, query_plan, sample_filters
        )

        llm_response = await llm_gateway.call_llm(
            model_id=model_id,
            prompt=prompt,
            temperature=0.1  # Low temperature for SQL generation
        )

        if not llm_response.success:
            raise Exception("SQL generation LLM call failed")

        # Extract and parse JSON response
        if not llm_response.raw_text:
            raise ValueError("Empty response from LLM")
        
        # Try to parse JSON response
        try:
            from ..utils.json_safety import safe_json_parse
            result = safe_json_parse(llm_response.raw_text)
            
            # Validate and enhance the response
            if isinstance(result, dict):
                # Ensure all required fields exist
                if "sql" not in result:
                    # Fallback: extract SQL from text
                    result["sql"] = self._extract_sql_from_response(llm_response.raw_text)
                
                # Build query_plan if not present
                if "query_plan" not in result:
                    result["query_plan"] = self._build_query_plan_dict(
                        query_plan, tables_info, sample_filters
                    )
                
                # Calculate confidence if not present
                if "confidence" not in result:
                    result["confidence"] = self._calculate_query_confidence(
                        query_plan, tables_info, context, result.get("sql", "")
                    )
                
                # Generate business_value if not present
                if "business_value" not in result:
                    result["business_value"] = self._generate_business_explanation(
                        question, intent, query_plan, result.get("sql", "")
                    )
                
                return result
            else:
                # Fallback: extract SQL and build structure
                sql = self._extract_sql_from_response(llm_response.raw_text)
                return {
                    "query_plan": self._build_query_plan_dict(query_plan, tables_info, sample_filters),
                    "sql": sql,
                    "confidence": self._calculate_query_confidence(query_plan, tables_info, context, sql),
                    "business_value": self._generate_business_explanation(question, intent, query_plan, sql)
                }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse JSON response: {e}, falling back to SQL extraction")
            # Fallback: extract SQL and build structure
            sql = self._extract_sql_from_response(llm_response.raw_text)
            return {
                "query_plan": self._build_query_plan_dict(query_plan, tables_info, sample_filters),
                "sql": sql,
                "confidence": self._calculate_query_confidence(query_plan, tables_info, context, sql),
                "business_value": self._generate_business_explanation(question, intent, query_plan, sql)
            }

    def _extract_sql_from_response(self, raw_text: str) -> str:
        """Extract SQL query from LLM response"""
        if not raw_text:
            return ""

        # Remove markdown code blocks
        sql = re.sub(r'```\w*\n?', '', raw_text)
        sql = re.sub(r'```', '', sql)

        # Clean up whitespace
        sql = sql.strip()

        # If multiple statements, take the first one
        if ';' in sql:
            sql = sql.split(';')[0].strip()

        return sql
    
    def build_sql_generation_prompt_with_json_output(
        self,
        context: ChatContext,
        question: str,
        intent: str,
        tables_info: Dict[str, Any],
        language: ChatLanguage,
        query_plan: Optional[Any] = None,
        sample_filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build SQL generation prompt that requests JSON output with query plan"""
        # Build base prompt with sample data
        base_prompt = self.build_sql_generation_prompt_with_sample_data(
            context, question, intent, tables_info, language, query_plan
        )
        
        # Add JSON output format instructions
        json_instructions = """
        
═══════════════════════════════════════════════════════════════════════════════
CRITICAL OUTPUT FORMAT - YOU MUST RETURN VALID JSON (NO MARKDOWN, NO CODE BLOCKS)
═══════════════════════════════════════════════════════════════════════════════

Return ONLY a valid JSON object with this EXACT structure:

{
  "query_plan": {
    "tables": ["dbo.Table1", "dbo.Table2"],
    "filters": {"ColumnName": "actual_sample_value_from_dictionary"},
    "joins": ["INNER JOIN dbo.Table2 ON dbo.Table1.id = dbo.Table2.fk_id"],
    "aggregation": "COUNT | SUM | AVG | WINDOW | none"
  },
  "sql": "SELECT TOP 50 [Column1], [Column2] FROM [dbo].[Table1] WHERE [ColumnName] = N'value'",
  "confidence": 0.87,
  "business_value": "Short explanation of what this query answers"
}

═══════════════════════════════════════════════════════════════════════════════
DETAILED RULES FOR EACH FIELD:
═══════════════════════════════════════════════════════════════════════════════

1. query_plan.tables:
   - Array of actual table names from DATABASE SCHEMA section
   - Include schema prefix if exists (e.g., "dbo.TableName")
   - Use EXACT table names from schema, never invent names

2. query_plan.filters:
   - Object mapping column names to actual sample values
   - Extract values from SAMPLE DATA section above
   - Use real values that exist in the data, not placeholders
   - Example: {"ProductName": "قیر 6070", "Status": "Active"}

3. query_plan.joins:
   - Array of JOIN clauses if multiple tables needed
   - Empty array [] if single table query
   - Use actual relationship columns from RELATIONSHIPS section
   - Format: "INNER JOIN schema.Table2 ON schema.Table1.col = schema.Table2.col"

4. query_plan.aggregation:
   - "none" if no aggregation (simple SELECT)
   - "COUNT" for COUNT(*) queries
   - "SUM" for SUM() queries
   - "AVG" for AVG() queries
   - "WINDOW" for window functions (ROW_NUMBER, RANK, etc.)

5. sql:
   - Complete, executable SQL Server query
   - MUST use TOP n instead of LIMIT n
   - MUST use N'...' prefix for Unicode strings (Persian, Arabic, etc.)
   - MUST use SQL Server functions: GETDATE(), FORMAT(), DATEDIFF(), DATEPART(), etc.
   - NEVER use: strftime, LIMIT, NOW(), date(), UUID(), ILIKE, RETURNING
   - Use square brackets [ ] for identifiers if needed
   - For pagination: OFFSET n ROWS FETCH NEXT n ROWS ONLY
   - Example: SELECT TOP 50 [Name] FROM [dbo].[Products] WHERE [Name] = N'قیر 6070'

6. confidence:
   - Float between 0.0 and 1.0
   - Higher if: uses actual schema tables/columns, uses sample data values, has relationships
   - Lower if: uncertain about schema, missing relationships, generic values

7. business_value:
   - One sentence explaining what business question this query answers
   - Focus on the business intent, not technical details
   - Example: "Retrieves the price of specific product based on user's question"

═══════════════════════════════════════════════════════════════════════════════
SQL SERVER SYNTAX RULES (CRITICAL - MUST FOLLOW):
═══════════════════════════════════════════════════════════════════════════════

✅ CORRECT SYNTAX:
- SELECT TOP 50 * FROM [dbo].[Table]
- WHERE [Column] = N'UnicodeValue'  (N prefix for Persian/Arabic)
- GETDATE() for current date/time
- FORMAT(date_column, 'yyyy-MM-dd') for date formatting
- DATEDIFF(day, start_date, end_date) for date differences
- YEAR(), MONTH(), DAY() for date parts
- OFFSET 10 ROWS FETCH NEXT 20 ROWS ONLY for pagination

❌ NEVER USE:
- LIMIT (use TOP instead)
- NOW() (use GETDATE() instead)
- strftime() (use FORMAT() instead)
- date() (use GETDATE() or CAST/CONVERT)
- UUID() (use NEWID() instead)
- ILIKE (use LIKE with N prefix)
- RETURNING (not supported in SQL Server SELECT)

═══════════════════════════════════════════════════════════════════════════════
FINAL REMINDER:
═══════════════════════════════════════════════════════════════════════════════

- Return ONLY valid JSON - no markdown code blocks, no explanations
- Use actual table/column names from DATABASE SCHEMA section
- Use actual sample values from SAMPLE DATA section for filters
- Follow SQL Server syntax rules exactly
- Validate your JSON is parseable before returning
"""
        
        # Append JSON instructions to the prompt
        return base_prompt + json_instructions
    
    def _extract_sample_filters_from_dictionary(
        self,
        data_dictionary: List[DataDictionaryInfo],
        tables_info: Dict[str, Any],
        query_plan: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Extract sample filter values from data dictionary"""
        filters = {}
        
        if not data_dictionary or not query_plan:
            return filters
        
        # Get relevant tables
        relevant_tables = set()
        for table_info in tables_info.get("tables", []):
            table_name = table_info.get("table", "")
            if table_name:
                relevant_tables.add(table_name)
        
        # Get filter columns from query plan
        filter_columns = query_plan.filter_columns if query_plan else []
        
        # Extract sample values for filter columns
        for item in data_dictionary:
            table_key = f"{item.schema_name}.{item.table_name}"
            if table_key not in relevant_tables:
                continue
            
            if item.column_name and item.example_values:
                # Check if this column is in filter columns
                full_col_name = f"{table_key}.{item.column_name}"
                if any(full_col_name.endswith(col) or col.endswith(item.column_name) for col in filter_columns):
                    try:
                        examples = json.loads(item.example_values) if isinstance(
                            item.example_values, str
                        ) else item.example_values
                        if isinstance(examples, list) and examples:
                            # Use first example value as filter
                            filters[item.column_name] = examples[0]
                    except (json.JSONDecodeError, TypeError):
                        pass
        
        return filters
    
    def _build_query_plan_dict(
        self,
        query_plan: Optional[Any],
        tables_info: Dict[str, Any],
        sample_filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build query_plan dictionary structure"""
        # Get tables from tables_info or query_plan
        tables = []
        if tables_info.get("tables"):
            tables = [t.get("table", "") for t in tables_info.get("tables", []) if t.get("table")]
        elif query_plan and query_plan.primary_tables:
            tables = query_plan.primary_tables
        
        # Build joins array
        joins = []
        if query_plan and query_plan.join_path:
            for join_info in query_plan.join_path:
                from_table = join_info.get("from_table", "")
                to_table = join_info.get("to_table", "")
                from_col = join_info.get("from_column", "")
                to_col = join_info.get("to_column", "")
                join_type = join_info.get("join_type", "INNER")
                joins.append(f"{join_type} JOIN {to_table} ON {from_table}.{from_col} = {to_table}.{to_col}")
        
        # Determine aggregation type
        aggregation = "none"
        if query_plan:
            if query_plan.intent == "COUNT":
                aggregation = "COUNT"
            elif query_plan.intent == "AGGREGATION":
                aggregation = "SUM"  # Default, could be AVG, SUM, etc.
            elif query_plan.aggregation_columns:
                aggregation = "SUM"  # Default aggregation
        
        return {
            "tables": tables,
            "filters": sample_filters,
            "joins": joins,
            "aggregation": aggregation
        }
    
    def _calculate_query_confidence(
        self,
        query_plan: Optional[Any],
        tables_info: Dict[str, Any],
        context: ChatContext,
        sql: str
    ) -> float:
        """Calculate confidence score based on schema alignment and sample data"""
        confidence = 0.5  # Base confidence
        
        # Boost if we have tables selected
        if tables_info.get("tables"):
            confidence += 0.2
        
        # Boost if query plan has high confidence
        if query_plan and hasattr(query_plan, 'confidence'):
            confidence = max(confidence, query_plan.confidence)
        
        # Boost if SQL uses actual table names from schema
        if context.schema_info:
            schema_tables = {f"{s.schema_name}.{s.table_name}" for s in context.schema_info}
            sql_upper = sql.upper()
            for table in schema_tables:
                if table.upper() in sql_upper:
                    confidence += 0.1
                    break
        
        # Boost if sample filters are used
        if query_plan and query_plan.filter_columns:
            confidence += 0.1
        
        # Cap at 1.0
        return min(1.0, confidence)
    
    def _generate_business_explanation(
        self,
        question: str,
        intent: str,
        query_plan: Optional[Any],
        sql: str
    ) -> str:
        """Generate business explanation for the query"""
        intent_descriptions = {
            "COUNT": "Counts the number of records",
            "AGGREGATION": "Calculates aggregate statistics",
            "LIST": "Lists records",
            "TOP_N": "Finds top-ranked records",
            "DETAIL": "Retrieves detailed information",
            "COMPARISON": "Compares multiple entities"
        }
        
        base_explanation = intent_descriptions.get(intent, "Retrieves data")
        
        # Add context from question
        if "price" in question.lower() or "قیمت" in question:
            base_explanation += " related to pricing"
        elif "product" in question.lower() or "محصول" in question:
            base_explanation += " for products"
        elif "date" in question.lower() or "تاریخ" in question:
            base_explanation += " filtered by date"
        
        return base_explanation + " based on the user's question."

    def _build_intent_detection_prompt(
        self, question: str, language: ChatLanguage,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Build Stage A prompt for intent detection"""
        if language == ChatLanguage.ENGLISH:
            template = """You are an intent detection expert. Analyze the user question and return ONLY a JSON object.

QUESTION: {question}

{conversation_history}

TASK: Classify the intent into one of these categories:
- CONVERSATIONAL: Greetings, thanks, help requests, or general conversation (hi, hello, hey, thanks, thank you, help, please, sorry, bye, goodbye, etc.)
- COUNT: Questions asking for counts/numbers (how many, total, etc.)
- AGGREGATION: Questions asking for averages, sums, statistics
- LIST: Questions asking to list/show all items
- TOP_N: Questions asking for top/best/highest ranked items
- DETAIL: Questions asking for specific details about individual items
- COMPARISON: Questions comparing multiple items/things

IMPORTANT: If the input is just a greeting, single word, or conversational phrase, ALWAYS classify as CONVERSATIONAL.

OUTPUT: ONLY JSON, no explanations:
{{
  "intent": "COUNT | AGGREGATION | LIST | TOP_N | DETAIL | COMPARISON | CONVERSATIONAL"
}}"""
        else:
            template = """شما متخصص تشخیص قصد هستید. سوال کاربر را تحلیل کنید و فقط یک شیء JSON برگردانید.

سوال: {question}

{conversation_history}

وظیفه: قصد را در یکی از این دسته‌ها طبقه‌بندی کنید:
- CONVERSATIONAL: سلام، تشکر، درخواست کمک، یا گفتگو عمومی (سلام، hi، hello، hey، ممنون، تشکر، کمک، لطفا، ببخشید، خداحافظ، bye، goodbye، و غیره)
- COUNT: سوالاتی که تعداد/اعداد می‌پرسند (چند تا، مجموع، و غیره)
- AGGREGATION: سوالاتی که میانگین، مجموع، آمار می‌پرسند
- LIST: سوالاتی که می‌خواهند همه موارد را لیست کنند
- TOP_N: سوالاتی که بهترین/بالاترین رتبه را می‌پرسند
- DETAIL: سوالاتی که جزئیات خاص یک مورد را می‌پرسند
- COMPARISON: سوالاتی که چندین مورد را مقایسه می‌کنند

مهم: اگر ورودی فقط یک سلام، یک کلمه، یا عبارت گفتگویی است، همیشه به عنوان CONVERSATIONAL طبقه‌بندی کنید.

خروجی: فقط JSON، بدون توضیح:
{{
  "intent": "COUNT | AGGREGATION | LIST | TOP_N | DETAIL | COMPARISON | CONVERSATIONAL"
}}"""

        variables = {
            "question": question,
            "conversation_history": self._format_conversation_history(conversation_history)
        }

        return template.format(**variables)

    def _build_table_selection_prompt(
        self, context: ChatContext, question: str, language: ChatLanguage
    ) -> str:
        """Build Stage B prompt for table and scope selection"""
        context_str = self._build_context_string(context)

        if language == ChatLanguage.ENGLISH:
            template = """You are a database schema expert. Analyze the question and schema, then return ONLY a JSON object.

QUESTION: {question}

SCHEMA:
{context}

TASK: Identify relevant tables and columns for answering this question.

RULES:
- Only select tables that exist in the schema
- Analyze the query content and match it with table descriptions and column names
- For price-related queries, prioritize tables with price-related columns
- For energy/trading queries, prioritize tables with energy/trading-related columns
- Prefer fewer tables over more tables (ideally 1-2 tables)
- Include all columns that might be needed based on the query
- Identify potential filter columns (dates, categories, names, etc.)

OUTPUT: ONLY JSON, no explanations:
{{
  "tables": [
    {{
      "table": "table_name",
      "reason": "why this table is relevant"
    }}
  ],
  "required_columns": ["column1", "column2"],
  "filters": ["date_column", "category_column"]
}}"""
        else:
            template = """شما متخصص schema پایگاه داده هستید. سوال و schema را تحلیل کنید و فقط یک شیء JSON برگردانید.

سوال: {question}

Schema:
{context}

⚠️ وظیفه بسیار مهم: جداول و ستون‌های مرتبط برای پاسخ به این سوال را شناسایی کنید.

⚠️ قوانین الزامی:
- **الزامی**: فقط جداولی را انتخاب کنید که در بخش DATABASE SCHEMA بالا وجود دارند
- **الزامی**: نام جدول باید دقیقاً همان باشد که در Schema آمده (با schema prefix اگر وجود دارد)
- **ممنوع**: هرگز از نام‌های generic مثل Products، Orders استفاده نکنید مگر اینکه در Schema وجود داشته باشند
- **الزامی**: قبل از انتخاب، بخش DATABASE SCHEMA را بخوانید و نام‌های دقیق جداول را پیدا کنید
- جداول کمتر را ترجیح دهید (1-2 جدول)
- تمام ستون‌هایی که ممکن است نیاز باشد را شامل کنید
- ستون‌های فیلتر بالقوه را شناسایی کنید (تاریخ، دسته‌بندی، نام محصول، و غیره)
- برای سوالات قیمت، جداول با ستون‌های قیمت را اولویت دهید
- برای سوالات انرژی/معاملات، جداول با ستون‌های مرتبط را اولویت دهید

⚠️ اگر سوال شبیه به سوالات موجود در بخش BUSINESS USE CASES است، از جداول استفاده شده در آن use case‌ها به عنوان راهنما استفاده کنید.

خروجی: فقط JSON، بدون توضیح:
{{
  "tables": [
    {{
      "table": "schema.table_name (دقیقاً همان که در Schema آمده)",
      "reason": "چرا این جدول مرتبط است"
    }}
  ],
  "required_columns": ["column1", "column2 (نام‌های دقیق از Schema)"],
  "filters": ["date_column", "category_column (نام‌های دقیق از Schema)"]
}}"""

        variables = {
            "question": question,
            "context": context_str
        }

        return template.format(**variables)

    def _build_sql_generation_prompt_v2(
        self,
        context: ChatContext,
        question: str,
        intent: str,
        tables_info: Dict[str, Any],
        language: ChatLanguage,
        query_plan: Optional[Any] = None  # QueryPlan from query_planner
    ) -> str:
        """Build Stage C prompt for SQL generation with intent and table constraints"""
        # Build relationships context
        relationships_str = self._build_relationships_section(context.relationships) if context.relationships else ""

        # Format selected tables and columns
        allowed_tables = [t["table"] for t in tables_info.get("tables", [])]
        allowed_columns = tables_info.get("required_columns", [])
        
        # Get SQL Server specific instructions
        sql_server_rules = self._get_sql_server_rules(context.database_type, language)

        # Initialize plan_context for all languages
        plan_context = ""
        if query_plan:
            plan_context = f"""
QUERY PLAN:
- Primary Tables: {', '.join(query_plan.primary_tables) if query_plan.primary_tables else 'None'}
- Join Path: {len(query_plan.join_path)} joins needed
- Filter Columns: {', '.join(query_plan.filter_columns) if query_plan.filter_columns else 'None'}
- Date Filter: {'Yes' if query_plan.requires_date_filter else 'No'} {f"({query_plan.date_column})" if query_plan.date_column else ''}
- Limit: {query_plan.limit_count if query_plan.limit_count else 'None'}
"""

        if language == ChatLanguage.ENGLISH:
            template = """You are a Text-to-SQL expert for SQL Server. Generate exactly ONE SELECT SQL query.

QUESTION: {question}

INTENT: {intent}
{plan_context}
ALLOWED TABLES: {allowed_tables}
ALLOWED COLUMNS: {allowed_columns}

SCHEMA:
{context}

RELATIONSHIPS:
{relationships}

{sql_server_rules}

CRITICAL RULES:
- Use ONLY tables from ALLOWED TABLES
- Use ONLY columns from ALLOWED COLUMNS or table.* for LIST intent
- Use explicit JOINs only if relationships exist
- Use proper SQL Server syntax (see SQL SERVER RULES above)

INTENT-SPECIFIC RULES:
{intent_rules}

QUERY OPTIMIZATION:
- Avoid full table scans: use WHERE clauses with indexed columns when possible
- For "latest" queries: use TOP 1 ORDER BY date_column DESC
- For date filtering: use proper date functions (YEAR, MONTH, DAY, DATEDIFF)
- For text search: use LIKE with N'...' prefix for Unicode strings
- Prefer filtering over aggregation when user wants specific entities

IMPORTANT: For COUNT queries, always use: SELECT COUNT(*) as record_count FROM table_name
For AGGREGATION queries, always use proper column aliases like: SELECT AVG(price) as average_price, SUM(quantity) as total_quantity

TABLE USAGE: Use the selected tables from the ALLOWED TABLES list. If multiple tables are available, choose the most appropriate one based on the query content and table descriptions.

OUTPUT: Return ONLY the SQL query, no explanations or markdown."""

            # Intent-specific rules
            intent_rules = {
                "COUNT": "- Generate COUNT(*) as record_count queries\n- NEVER use TOP or LIMIT\n- Always use column alias: SELECT COUNT(*) as record_count FROM table\n- Use WHERE clauses to filter before counting",
                "AGGREGATION": "- Generate aggregation queries (SUM, AVG, etc.) with aliases\n- NEVER use TOP or LIMIT\n- Use aliases like: SELECT AVG(price) as average_price, SUM(quantity) as total_quantity\n- Group by appropriate columns\n- Use WHERE to filter before aggregation",
                "LIST": "- Generate SELECT queries with specific columns (avoid SELECT *)\n- Use TOP 50 to prevent large results\n- Include all relevant columns\n- Use WHERE clauses for filtering",
                "TOP_N": "- Generate TOP N queries (e.g., TOP 10)\n- Order by relevant metric DESC for highest, ASC for lowest\n- Include ranking criteria\n- Use WHERE to filter before ordering",
                "DETAIL": "- Generate detailed queries with WHERE clauses\n- Filter by specific entity identifiers (IDs, names, etc.)\n- Return all relevant columns for the entity\n- Use exact matches or LIKE for text search",
                "COMPARISON": "- Generate comparison queries\n- May require JOINs or UNIONs\n- Include comparison metrics\n- Use WHERE to filter entities being compared"
            }.get(intent, "- Generate appropriate query based on intent")

        else:
            template = """شما متخصص Text-to-SQL هستید. دقیقاً یک پرس‌وجوی SELECT SQL تولید کنید.

سوال: {question}

قصد: {intent}

جداول مجاز: {allowed_tables}
ستون‌های مجاز: {allowed_columns}

Schema:
{context}

روابط:
{relationships}

{sql_server_rules}

⚠️ قوانین بسیار مهم (باید رعایت شود):
- **الزامی**: فقط از جداول لیست جداول مجاز استفاده کنید - هیچ جدول دیگری مجاز نیست
- **الزامی**: فقط از ستون‌های لیست ستون‌های مجاز استفاده کنید - هیچ ستون دیگری مجاز نیست
- **الزامی**: از نام‌های دقیق جداول و ستون‌هایی که در بخش DATABASE SCHEMA بالا آمده استفاده کنید
- **ممنوع**: هرگز از نام‌های generic مثل Products، Orders، Customers استفاده نکنید مگر اینکه در Schema وجود داشته باشند
- **ممنوع**: هرگز از نام‌های ستون generic مثل price، name، id استفاده نکنید مگر اینکه در Schema وجود داشته باشند
- **الزامی**: قبل از تولید کوئری، بخش DATABASE SCHEMA را بخوانید و نام‌های دقیق جداول و ستون‌ها را پیدا کنید
- از JOINهای صریح فقط در صورت وجود رابطه استفاده کنید
- از نحو {db_type} مناسب استفاده کنید
- برای رشته‌های یونیکد (فارسی، عربی) از پیشوند N'...' استفاده کنید: WHERE [column_name] = N'value'

مهم: کوئری باید کامل باشد:
- حتماً شامل SELECT و FROM باشد
- اگر نیاز به فیلتر است، حتماً شامل WHERE باشد
- کوئری باید قابل اجرا باشد (نه ناقص)
- **الزامی**: باید از نام‌های دقیق جداول و ستون‌هایی که در بخش DATABASE SCHEMA بالا آمده استفاده کنید

قوانین خاص قصد:
{intent_rules}

⚠️ توجه بسیار مهم:
- **قبل از تولید کوئری**: بخش DATABASE SCHEMA را بخوانید و نام‌های دقیق جداول و ستون‌ها را پیدا کنید
- **الزامی**: کوئری باید کامل باشد - شامل SELECT، FROM، و در صورت نیاز WHERE
- **الزامی**: از نام‌های دقیق جداول و ستون‌هایی که در بخش DATABASE SCHEMA بالا آمده استفاده کنید
- **الزامی**: از Sample Data برای فهمیدن مقادیر واقعی استفاده کنید
- **الزامی**: کوئری باید بر اساس schema و context واقعی دیتابیس باشد
- **ممنوع**: هرگز از نام‌های generic یا فرضی استفاده نکنید

راهنمایی از Use Cases:
- اگر سوال کاربر شبیه به سوالات موجود در بخش BUSINESS USE CASES است، از کوئری‌های مثال آن use case به عنوان الگو استفاده کنید
- از business goal و example queries برای فهمیدن الگوی صحیح کوئری استفاده کنید
- اما همیشه از نام‌های دقیق جداول و ستون‌های Schema استفاده کنید (نه از مثال‌ها کپی کنید)

⚠️ چک‌لیست قبل از تولید کوئری:
1. آیا نام جدول در بخش DATABASE SCHEMA وجود دارد؟ ✓
2. آیا نام ستون‌ها در بخش DATABASE SCHEMA وجود دارد؟ ✓
3. آیا کوئری شامل SELECT، FROM، و در صورت نیاز WHERE است؟ ✓
4. آیا برای رشته‌های فارسی از N'...' استفاده شده است؟ ✓

⚠️ اگر جداول مجاز خالی است یا "any table" است:
- از بخش DATABASE SCHEMA بالا جداول مرتبط را پیدا کنید
- از جداول و ستون‌هایی که در Schema آمده استفاده کنید
- هرگز از نام‌های generic استفاده نکنید
- اگر سوال درباره قیمت است، جدولی با ستون قیمت پیدا کنید
- اگر سوال درباره محصول است، جدولی با ستون نام محصول پیدا کنید

⚠️ مثال: اگر سوال "قیمت قیر 6070" است:
- در بخش DATABASE SCHEMA جدولی با ستون قیمت و نام محصول پیدا کنید
- از نام‌های دقیق آن جدول و ستون‌ها استفاده کنید
- کوئری: SELECT [price_column] FROM [schema].[table_name] WHERE [product_name_column] = N'قیر 6070'

خروجی: فقط پرس‌وجوی SQL کامل و قابل اجرا را برگردانید، بدون توضیح یا markdown."""

            # Persian intent rules
            intent_rules = {
                "COUNT": "- پرس‌وجوهای COUNT(*) تولید کنید\n- هرگز از TOP یا LIMIT استفاده نکنید\n- روی شمارش رکوردها تمرکز کنید",
                "AGGREGATION": "- پرس‌وجوهای تجمیع تولید کنید (SUM, AVG, و غیره)\n- هرگز از TOP یا LIMIT استفاده نکنید\n- بر اساس ستون‌های مناسب گروه‌بندی کنید",
                "LIST": "- پرس‌وجوهای SELECT * یا لیست تولید کنید\n- از TOP 50 برای جلوگیری از نتایج بزرگ استفاده کنید (برای SQL Server)\n- تمام ستون‌های مرتبط را شامل کنید",
                "TOP_N": "- پرس‌وجوهای TOP N تولید کنید (برای SQL Server از TOP استفاده کنید، نه LIMIT)\n- بر اساس معیار مرتبط مرتب کنید\n- معیارهای رتبه‌بندی را شامل کنید",
                "DETAIL": "- پرس‌وجوهای جزئیات تولید کنید\n- بند WHERE برای رکوردهای خاص شامل کنید\n- برای رشته‌های فارسی از N'...' استفاده کنید: WHERE [column_name] = N'value'\n- جزئیات مورد خاص را برگردانید",
                "COMPARISON": "- پرس‌وجوهای مقایسه تولید کنید\n- ممکن است نیاز به JOIN یا UNION داشته باشد\n- معیارهای مقایسه را شامل کنید"
            }.get(intent, "- پرس‌وجوی مناسب بر اساس قصد تولید کنید")

        variables = {
            "question": question,
            "intent": intent,
            "plan_context": plan_context if query_plan else "",
            "allowed_tables": ", ".join(allowed_tables) if allowed_tables else "⚠️ هیچ جدولی انتخاب نشده - باید از جداول موجود در بخش DATABASE SCHEMA استفاده کنید",
            "allowed_columns": ", ".join(allowed_columns) if allowed_columns else "⚠️ هیچ ستونی انتخاب نشده - باید از ستون‌های موجود در بخش DATABASE SCHEMA استفاده کنید",
            "context": self._build_context_string(context),
            "relationships": relationships_str,
            "db_type": context.database_type,
            "sql_server_rules": sql_server_rules,
            "intent_rules": intent_rules
        }

        return template.format(**variables)
    
    def _get_sql_server_rules(self, db_type: str, language: Optional[ChatLanguage] = None) -> str:
        """Get SQL Server specific rules for prompt"""
        if db_type and db_type.lower() in ['sqlserver', 'mssql']:
            if language == ChatLanguage.PERSIAN:
                return """قوانین نحو SQL Server (بسیار مهم - باید رعایت شود):
- از TOP به جای LIMIT استفاده کنید (مثال: TOP 50، نه LIMIT 50)
- برای رشته‌های یونیکد (فارسی، عربی و غیره) از پیشوند N'...' استفاده کنید: WHERE [column_name] = N'value'
- از CONVERT یا CAST برای تبدیل تاریخ استفاده کنید: CONVERT(DATE, date_column)
- از GETDATE() به جای NOW() یا CURRENT_TIMESTAMP استفاده کنید
- از DATEDIFF برای تفاوت تاریخ استفاده کنید: DATEDIFF(day, start_date, end_date)
- از YEAR(), MONTH(), DAY() به جای EXTRACT() استفاده کنید
- از FORMAT() برای فرمت تاریخ استفاده کنید: FORMAT(date_column, 'yyyy-MM-dd')
- از STRING_AGG() برای الحاق رشته‌ها استفاده کنید (SQL Server 2017+)
- از JSON_QUERY() و JSON_VALUE() برای عملیات JSON استفاده کنید
- در صورت نیاز از براکت‌های مربع [ ] برای شناسه‌ها استفاده کنید: [table name]
- هرگز استفاده نکنید: strftime, date(), LIMIT, NOW(), UUID(), ILIKE, RETURNING
- برای صفحه‌بندی: OFFSET ... ROWS FETCH NEXT ... ROWS ONLY
- از ISNULL() یا COALESCE() برای مدیریت NULL استفاده کنید
- از LEN() به جای LENGTH() استفاده کنید
- از SUBSTRING() به جای SUBSTR() استفاده کنید
- مهم: کوئری باید کامل باشد - شامل SELECT، FROM، و WHERE (در صورت نیاز)"""
            else:
                return """SQL SERVER SYNTAX RULES (CRITICAL - MUST FOLLOW):
- Use TOP instead of LIMIT (e.g., TOP 50, not LIMIT 50)
- Use N'...' prefix for Unicode strings (Persian, Arabic, etc.): WHERE name = N'علی'
- Use CONVERT or CAST for date conversions: CONVERT(DATE, date_column)
- Use GETDATE() instead of NOW() or CURRENT_TIMESTAMP
- Use DATEDIFF for date differences: DATEDIFF(day, start_date, end_date)
- Use YEAR(), MONTH(), DAY() instead of EXTRACT()
- Use FORMAT() for date formatting: FORMAT(date_column, 'yyyy-MM-dd')
- Use STRING_AGG() for string concatenation (SQL Server 2017+)
- Use JSON_QUERY() and JSON_VALUE() for JSON operations
- Use square brackets [ ] for identifiers if needed: [table name]
- NEVER use: strftime, date(), LIMIT, NOW(), UUID(), ILIKE, RETURNING
- For pagination: OFFSET ... ROWS FETCH NEXT ... ROWS ONLY
- Use ISNULL() or COALESCE() for NULL handling
- Use LEN() instead of LENGTH()
- Use SUBSTRING() instead of SUBSTR()
- IMPORTANT: Query must be complete - include SELECT, FROM, and WHERE (if needed)"""
        else:
            return f"""DATABASE TYPE: {db_type.upper()}
- Use appropriate syntax for {db_type}
- Follow standard SQL conventions"""

    def get_prompt_metadata(self) -> Dict[str, Dict[str, str]]:
        """Get metadata about all available prompts for traceability"""
        return {
            template_key: {
                "version": template.version,
                "type": template.template_type,
                "language": template.language.value
            }
            for template_key, template in self.templates.items()
        }

    def _render_template(self, template: PromptTemplate, variables: Dict[str, Any]) -> str:
        """Render template with variables"""
        result = template.template

        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(var_value))

        return result

    def _build_context_string(self, context: ChatContext) -> str:
        """Build comprehensive context string from ChatContext"""
        parts = []

        # Schema information
        parts.append(self._build_schema_section(context.schema_info))

        # Data dictionary
        if context.data_dictionary:
            parts.append(self._build_data_dictionary_section(context.data_dictionary))

        # Relationships
        if context.relationships:
            parts.append(self._build_relationships_section(context.relationships))

        # Use cases
        if context.use_cases:
            parts.append(self._build_use_cases_section(context.use_cases))

        return "\n".join(parts)

    def _build_schema_section(self, schema_info: List[SchemaInfo]) -> str:
        """Build schema section string"""
        # Group by table
        tables = {}
        for col in schema_info:
            key = f"{col.schema_name}.{col.table_name}"
            if key not in tables:
                tables[key] = []
            tables[key].append(col)

        if not schema_info:
            return "DATABASE SCHEMA: (No schema information available)"
        
        lines = ["=" * 60]
        lines.append("DATABASE SCHEMA (استفاده از این نام‌های دقیق الزامی است):")
        lines.append("=" * 60)
        lines.append("⚠️ مهم: فقط از این جداول و ستون‌ها استفاده کنید. هیچ نام دیگری مجاز نیست.")
        lines.append("")
        
        for table_key, columns in tables.items():
            lines.append(f"\n📋 Table: {table_key}")
            lines.append(f"   ستون‌ها:")
            for col in columns:
                pk_marker = " (PRIMARY KEY)" if col.is_primary_key else ""
                fk_marker = f" (FOREIGN KEY -> {col.foreign_key_table}.{col.foreign_key_column})" if col.is_foreign_key else ""
                lines.append(f"     - {col.column_name} ({col.column_type}){pk_marker}{fk_marker}")
        
        lines.append("")
        lines.append("=" * 60)
        lines.append("⚠️ یادآوری: فقط از نام‌های بالا استفاده کنید. هیچ نام generic یا فرضی مجاز نیست.")
        lines.append("=" * 60)
        
        return "\n".join(lines)

    def _build_data_dictionary_section(self, data_dictionary: List[DataDictionaryInfo]) -> str:
        """Build data dictionary section string with sample data"""
        lines = ["DATA DICTIONARY:"]

        # Group by table for better organization
        table_dict = {}
        for item in data_dictionary:
            table_key = f"{item.schema_name}.{item.table_name}"
            if table_key not in table_dict:
                table_dict[table_key] = {"table_desc": None, "columns": []}
            
            if item.column_name:
                table_dict[table_key]["columns"].append(item)
            else:
                table_dict[table_key]["table_desc"] = item.description

        for table_key, table_data in table_dict.items():
            lines.append(f"\nTable: {table_key}")
            if table_data["table_desc"]:
                lines.append(f"Description: {table_data['table_desc']}")
            
            for item in table_data["columns"]:
                lines.append(f"  - {item.column_name}")
                if item.description:
                    lines.append(f"    Description: {item.description}")
                if item.example_values:
                    # Parse example values if JSON
                    try:
                        examples = json.loads(item.example_values) if isinstance(item.example_values, str) else item.example_values
                        if isinstance(examples, list) and examples:
                            lines.append(f"    Example values: {', '.join(str(v) for v in examples[:3])}")
                    except:
                        lines.append(f"    Example values: {item.example_values}")
                if item.synonyms:
                    lines.append(f"    Synonyms: {item.synonyms}")

        return "\n".join(lines)

    def _build_relationships_section(self, relationships: List[RelationshipInfo]) -> str:
        """Build relationships section string"""
        lines = ["RELATIONSHIPS:"]

        for rel in relationships:
            lines.append(f"\n{rel.source_table}.{rel.source_column} -> {rel.target_table}.{rel.target_column}")
            lines.append(f"  Type: {rel.relationship_type} ({rel.cardinality})")
            lines.append(f"  Join: {rel.join_type}")
            lines.append(f"  Description: {rel.description}")

        return "\n".join(lines)

    def _build_use_cases_section(self, use_cases: List[UseCaseInfo]) -> str:
        """Build use cases section string with examples"""
        if not use_cases:
            return ""
        
        lines = ["BUSINESS USE CASES (برای راهنمایی در تولید کوئری‌های مشابه):"]
        lines.append("=" * 60)

        for idx, use_case in enumerate(use_cases, 1):
            lines.append(f"\n[{idx}] Use Case: {use_case.name}")
            lines.append(f"Business Goal: {use_case.business_goal}")
            if use_case.output_style:
                lines.append(f"Output Style: {use_case.output_style}")

            # Add example questions and queries
            if use_case.example_questions and use_case.example_queries:
                lines.append("\nمثال‌های سوال و کوئری (برای راهنمایی):")
                example_pairs = list(zip(use_case.example_questions, use_case.example_queries))
                for q_idx, (question, query) in enumerate(example_pairs[:5], 1):  # Max 5 examples
                    lines.append(f"\n  مثال {q_idx}:")
                    lines.append(f"    سوال: {question}")
                    if query:
                        # Truncate long queries
                        query_preview = query[:200] + "..." if len(query) > 200 else query
                        lines.append(f"    کوئری: {query_preview}")
            elif use_case.example_questions:
                lines.append("\nمثال سوالات:")
                for q in use_case.example_questions[:5]:  # Max 5
                    lines.append(f"  - {q}")

            lines.append("-" * 60)

        lines.append("\nتوجه: از این use case‌ها به عنوان راهنما استفاده کنید تا کوئری‌های مشابه و صحیح تولید کنید.")
        return "\n".join(lines)
    
    # ===== UNIFIED PROMPT BUILDING METHODS =====
    # These methods centralize prompt building for use cases, relationships, and other modules
    
    def build_use_case_generation_prompt(
        self,
        request: Any,  # SmartUseCaseBuilderRequest
        minified_schema: Dict[str, Dict[str, Any]],
        data_dictionary: Dict[str, Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        sample_data: Dict[str, List[Dict[str, Any]]],
        language: str = "en",
        database_type: Optional[str] = None,
        table_row_counts: Optional[Dict[str, int]] = None
    ) -> str:
        """
        Unified method for building use case generation prompts.
        Centralizes prompt building logic to prevent duplication.
        
        This method is called by backend/api/smart_use_case_builder.py
        """
        # Import the existing function to maintain backward compatibility
        # But we'll improve it by ensuring it uses sample data from dictionary
        from api.smart_use_case_builder import build_use_case_generation_prompt as _legacy_build
        
        # Call legacy function but ensure sample data is enriched from dictionary
        enriched_sample_data = self._enrich_sample_data_from_dictionary(
            sample_data, data_dictionary
        )
        
        return _legacy_build(
            request, minified_schema, data_dictionary, relationships,
            enriched_sample_data, language, database_type, table_row_counts
        )
    
    def build_relationship_suggestion_prompt(
        self,
        schema_data: List[dict],
        data_dict: List[Any],  # List[DataDictionary]
        tables_with_samples: Dict[str, List[Dict[str, Any]]],
        intermediary_tables: Dict[str, Dict[str, Any]],
        business_context: Optional[str] = None
    ) -> str:
        """
        Unified method for building relationship suggestion prompts.
        Centralizes prompt building logic to prevent duplication.
        
        This method is called by backend/api/relationships.py
        """
        # Import the existing function to maintain backward compatibility
        from api.relationships import build_relationship_suggestion_prompt as _legacy_build
        
        # Enrich sample data from dictionary if available
        enriched_samples = self._enrich_sample_data_from_dictionary_dict(
            tables_with_samples, data_dict
        )
        
        return _legacy_build(
            schema_data, data_dict, enriched_samples,
            intermediary_tables, business_context
        )
    
    def _enrich_sample_data_from_dictionary(
        self,
        sample_data: Dict[str, List[Dict[str, Any]]],
        data_dictionary: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Enrich sample data with example values from data dictionary.
        Uses 3-5 unique sampled rows already stored in dictionary.
        Does NOT sample again - only uses existing dictionary data.
        """
        enriched = sample_data.copy()
        
        for table_key, dict_info in data_dictionary.items():
            if table_key not in enriched:
                enriched[table_key] = []
            
            # Extract example values from dictionary columns
            example_rows = []
            for col_key, col_info in dict_info.items():
                if col_key == "__table__":
                    continue
                
                if col_info.get("example_values"):
                    try:
                        examples = json.loads(col_info["example_values"]) if isinstance(
                            col_info["example_values"], str
                        ) else col_info["example_values"]
                        
                        if isinstance(examples, list) and examples:
                            # Create sample row from example values
                            for idx, example_val in enumerate(examples[:3]):
                                if len(example_rows) <= idx:
                                    example_rows.append({})
                                example_rows[idx][col_key] = example_val
                    except (json.JSONDecodeError, TypeError):
                        pass
            
            # Merge with existing sample data, prioritizing actual sampled rows
            if example_rows and not enriched[table_key]:
                enriched[table_key] = example_rows[:5]  # Max 5 rows
        
        return enriched
    
    def _enrich_sample_data_from_dictionary_dict(
        self,
        tables_with_samples: Dict[str, List[Dict[str, Any]]],
        data_dict: List[Any]  # List[DataDictionary]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Enrich sample data from DataDictionary model list.
        Uses example_values already stored in dictionary.
        """
        enriched = tables_with_samples.copy()
        
        # Group dictionary by table
        dict_by_table = {}
        for item in data_dict:
            table_key = f"{item.schema_name}.{item.table_name}"
            if table_key not in dict_by_table:
                dict_by_table[table_key] = {}
            
            if item.column_name:
                try:
                    example_values = json.loads(item.example_values) if item.example_values else []
                except:
                    example_values = []
                
                if example_values:
                    dict_by_table[table_key][item.column_name] = example_values
        
        # Build sample rows from dictionary examples
        for table_key, col_examples in dict_by_table.items():
            if table_key not in enriched or not enriched[table_key]:
                # Build sample rows from example values
                max_examples = max(len(vals) for vals in col_examples.values()) if col_examples else 0
                sample_rows = []
                
                for i in range(min(5, max_examples)):
                    row = {}
                    for col_name, examples in col_examples.items():
                        if i < len(examples):
                            row[col_name] = examples[i]
                    if row:
                        sample_rows.append(row)
                
                if sample_rows:
                    enriched[table_key] = sample_rows
        
        return enriched
    
    def build_sql_generation_prompt_with_sample_data(
        self,
        context: ChatContext,
        question: str,
        intent: str,
        tables_info: Dict[str, Any],
        language: ChatLanguage,
        query_plan: Optional[Any] = None
    ) -> str:
        """
        Build SQL generation prompt with sample data from dictionary.
        Uses 3-5 unique sampled rows already stored in data dictionary.
        Does NOT sample again - only uses existing dictionary data.
        """
        # Extract sample data from dictionary
        sample_data_section = self._build_sample_data_section_from_dictionary(
            context.data_dictionary, tables_info
        )
        
        # Build base prompt
        base_prompt = self._build_sql_generation_prompt_v2(
            context, question, intent, tables_info, language, query_plan
        )
        
        # Inject sample data section before SQL rules
        if sample_data_section:
            # Insert sample data section after relationships but before SQL rules
            # Try both English and Persian markers
            sample_marker_en = "SQL SERVER SYNTAX RULES"
            sample_marker_fa = "قوانین نحو SQL Server"
            if sample_marker_en in base_prompt:
                base_prompt = base_prompt.replace(
                    sample_marker_en,
                    f"{sample_data_section}\n\n{sample_marker_en}",
                    1
                )
            elif sample_marker_fa in base_prompt:
                base_prompt = base_prompt.replace(
                    sample_marker_fa,
                    f"{sample_data_section}\n\n{sample_marker_fa}",
                    1
                )
            else:
                # Append if marker not found
                base_prompt += f"\n\n{sample_data_section}"
        
        return base_prompt
    
    def _build_sample_data_section_from_dictionary(
        self,
        data_dictionary: List[DataDictionaryInfo],
        tables_info: Dict[str, Any]
    ) -> str:
        """
        Build sample data section from data dictionary example_values.
        Uses 3-5 unique sampled rows already stored in dictionary.
        """
        if not data_dictionary:
            return ""
        
        # Get relevant tables from tables_info
        relevant_tables = set()
        for table_info in tables_info.get("tables", []):
            table_name = table_info.get("table", "")
            if table_name:
                relevant_tables.add(table_name)
        
        # Group dictionary by table
        dict_by_table = {}
        for item in data_dictionary:
            table_key = f"{item.schema_name}.{item.table_name}"
            if table_key not in relevant_tables and relevant_tables:
                # Only include relevant tables if we have table selection
                continue
            
            if table_key not in dict_by_table:
                dict_by_table[table_key] = {}
            
            if item.column_name and item.example_values:
                try:
                    examples = json.loads(item.example_values) if isinstance(
                        item.example_values, str
                    ) else item.example_values
                    if isinstance(examples, list) and examples:
                        dict_by_table[table_key][item.column_name] = examples[:5]  # Max 5 examples
                except (json.JSONDecodeError, TypeError):
                    pass
        
        if not dict_by_table:
            return ""
        
        # Build sample data section
        lines = ["SAMPLE DATA (from dictionary - 3-5 unique rows per table):"]
        
        for table_key, col_examples in dict_by_table.items():
            if not col_examples:
                continue
            
            lines.append(f"\nTable: {table_key}")
            
            # Build sample rows from column examples
            max_rows = max(len(vals) for vals in col_examples.values()) if col_examples else 0
            sample_rows = []
            
            for i in range(min(5, max_rows)):
                row = {}
                for col_name, examples in col_examples.items():
                    if i < len(examples):
                        row[col_name] = examples[i]
                if row:
                    sample_rows.append(row)
            
            # Display up to 5 rows
            for idx, row in enumerate(sample_rows[:5], 1):
                row_str = json.dumps(row, ensure_ascii=False, default=str)
                # Truncate long values
                if len(row_str) > 200:
                    row_str = row_str[:200] + "..."
                lines.append(f"  Row {idx}: {row_str}")
        
        return "\n".join(lines)

    def _format_conversation_history(self, history: Optional[List[Dict[str, str]]]) -> str:
        """Format conversation history for prompt inclusion"""
        if not history:
            return "No previous conversation."

        formatted = []
        for entry in history[-5:]:  # Last 5 exchanges
            formatted.append(f"Q: {entry.get('question', '')}")
            formatted.append(f"A: {entry.get('sql', '')}")

        return "\n".join(formatted)

    def _get_reasoning_template_en(self) -> str:
        """English reasoning prompt template"""
        return """You are an expert at understanding user questions about databases.

CONTEXT:
{context}

CONVERSATION HISTORY:
{conversation_history}

QUESTION: {question}

TASK: Analyze the question and identify:
1. What the user wants to know
2. Which tables and columns are relevant
3. What type of analysis is needed
4. Any filtering or aggregation requirements

RESPONSE FORMAT:
Intent: [brief description]
Relevant Tables: [table1, table2, ...]
Key Columns: [col1, col2, ...]
Analysis Type: [aggregation/filtering/join/etc]
Additional Notes: [any special considerations]

Provide your analysis:"""

    def _get_reasoning_template_fa(self) -> str:
        """Persian reasoning prompt template"""
        return """شما یک متخصص درک پرسش‌های کاربران درباره پایگاه داده هستید.

پرسش: {question}

{conversation_history}

وظیفه: قصد پرسش را در یکی از دسته‌های زیر طبقه‌بندی کنید:
- CONVERSATIONAL: سلام، تشکر، درخواست کمک، یا گفتگو عمومی (سلام، ممنون، کمک، لطفا، ببخشید، خداحافظ و غیره)
- COUNT: پرسش‌هایی درباره شمارش/تعداد (چند تا، مجموع و غیره)
- AGGREGATION: پرسش‌هایی درباره میانگین، مجموع، آمار
- LIST: پرسش‌هایی درباره لیست کردن/نمایش همه موارد
- TOP_N: پرسش‌هایی درباره بهترین/بالاترین رتبه موارد
- DETAIL: پرسش‌هایی درباره جزئیات خاص یک مورد
- COMPARISON: پرسش‌هایی درباره مقایسه چندین مورد

مهم: اگر ورودی فقط یک سلام، یک کلمه، یا عبارت گفتگویی است، همیشه CONVERSATIONAL انتخاب کنید.

پاسخ فقط JSON بدهید، توضیح اضافه نکنید:
{{
  "intent": "COUNT | AGGREGATION | LIST | TOP_N | DETAIL | COMPARISON | CONVERSATIONAL"
}}"""

    def _get_sql_template_postgresql_en(self) -> str:
        """English SQL generation prompt template for PostgreSQL"""
        return """You are a Text-to-SQL expert. Generate exactly ONE SELECT SQL query for PostgreSQL.

REASONING ANALYSIS:
{reasoning_output}

CONTEXT:
{context}

QUESTION: {question}

CRITICAL RULES:
- Generate ONLY SELECT queries
- Use explicit JOINs, never implicit
- Use only tables/columns from the schema
- Include LIMIT 50 to prevent large results
- Use proper PostgreSQL syntax and aliases
- Handle NULL values appropriately

OUTPUT: Return ONLY the SQL query, no explanations:"""

    def _get_sql_template_mysql_en(self) -> str:
        """English SQL generation prompt template for MySQL"""
        return """You are a Text-to-SQL expert. Generate exactly ONE SELECT SQL query for MySQL.

REASONING ANALYSIS:
{reasoning_output}

CONTEXT:
{context}

QUESTION: {question}

CRITICAL RULES:
- Generate ONLY SELECT queries
- Use explicit JOINs, never implicit
- Use only tables/columns from the schema
- Include LIMIT 50 to prevent large results
- Use proper MySQL syntax and aliases
- Handle NULL values appropriately

OUTPUT: Return ONLY the SQL query, no explanations:"""

    def _get_sql_template_sqlserver_en(self) -> str:
        """English SQL generation prompt template for SQL Server"""
        return """You are a Text-to-SQL expert. Generate exactly ONE SELECT SQL query for SQL Server.

REASONING ANALYSIS:
{reasoning_output}

CONTEXT:
{context}

QUESTION: {question}

CRITICAL RULES:
- Generate ONLY SELECT queries
- Use explicit JOINs, never implicit
- Use only tables/columns from the schema
- Analyze query content and select appropriate tables dynamically
- For price-related queries, use tables with price columns
- For energy-related queries, use tables with energy columns
- Include TOP 50 to prevent large results
- Use proper SQL Server syntax (T-SQL) and aliases
- Handle NULL values appropriately
- Use square brackets [ ] for identifiers if needed

OUTPUT: Return ONLY the SQL query, no explanations:"""

    def _get_sql_template_en(self) -> str:
        """Legacy English SQL generation prompt template (defaults to PostgreSQL)"""
        return self._get_sql_template_postgresql_en()

    def _get_sql_template_fa(self) -> str:
        """Persian SQL generation prompt template"""
        return """شما یک متخصص Text-to-SQL هستید. دقیقاً یک پرس‌وجوی SELECT SQL تولید کنید.

تحلیل استدلال:
{reasoning_output}

زمینه:
{context}

پرسش: {question}

قوانین بسیار مهم:
- فقط پرس‌وجوی SELECT تولید کنید
- از JOINهای صریح استفاده کنید، نه ضمنی
- فقط از جداول/ستون‌های موجود در schema استفاده کنید
- بر اساس محتوای پرسش، مناسب‌ترین جداول را انتخاب کنید
- برای پرسش‌های قیمت، جداول با ستون‌های قیمت را اولویت دهید
- برای پرسش‌های انرژی، جداول با ستون‌های انرژی را اولویت دهید
- TOP 50 را برای جلوگیری از نتایج بزرگ اضافه کنید
- از نحو SQL مناسب و نام‌های مستعار استفاده کنید
- با مقادیر NULL به طور مناسب برخورد کنید

خروجی: فقط پرس‌وجوی SQL را برگردانید، بدون توضیح:"""

    def _get_validation_template_en(self) -> str:
        """English SQL validation prompt template"""
        return """You are a SQL security validator.

CONTEXT:
{context}

SQL TO VALIDATE:
{sql}

TASK: Check if this SQL query is safe and correct.

VALIDATION CRITERIA:
- Read-only (SELECT only)
- Uses existing tables/columns
- Proper JOIN syntax
- No dangerous functions
- Reasonable complexity

RESPONSE: "SAFE" or "UNSAFE: [reason]"""
