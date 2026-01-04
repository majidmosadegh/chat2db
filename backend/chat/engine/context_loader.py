from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any
import json
import hashlib
import logging
import time
from datetime import datetime

from api.db_models import (
    SchemaMetadata, DataDictionary, Relationship, UseCase,
    SchemaSnapshot, UseCaseVersion, DatabaseConnection
)
from ..schemas import (
    SchemaInfo, DataDictionaryInfo, RelationshipInfo, UseCaseInfo, ChatContext
)

logger = logging.getLogger(__name__)


class ContextLoader:
    """Loads and aggregates context information into immutable ChatContext"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def load_context(self, snapshot_id: int) -> ChatContext:
        """
        Load all context information and aggregate into immutable ChatContext.

        Args:
            snapshot_id: The schema snapshot ID to load context for

        Returns:
            ChatContext: Immutable context object with all aggregated data

        Raises:
            ValueError: If snapshot doesn't exist
        """
        request_id = f"CTX_{snapshot_id}_{int(time.time()*1000)}"
        start_time = time.time()

        logger.info(f"📚 CONTEXT_LOAD_START | ID: {request_id} | SnapshotID: {snapshot_id}")

        # Verify snapshot exists and get name and database connection
        logger.debug(f"🔍 CONTEXT_SNAPSHOT_LOOKUP | ID: {request_id} | SnapshotID: {snapshot_id}")

        result = await self.session.execute(
            select(SchemaSnapshot.name, SchemaSnapshot.connection_id)
            .where(SchemaSnapshot.id == snapshot_id)
        )
        snapshot_data = result.first()
        if not snapshot_data:
            logger.error(f"❌ CONTEXT_SNAPSHOT_NOT_FOUND | ID: {request_id} | SnapshotID: {snapshot_id}")
            raise ValueError(f"Schema snapshot {snapshot_id} not found")

        snapshot_name = snapshot_data.name
        connection_id = snapshot_data.connection_id

        logger.info(f"✅ CONTEXT_SNAPSHOT_FOUND | ID: {request_id} | Name: '{snapshot_name}' | ConnectionID: {connection_id}")

        # Get database type from connection
        logger.debug(f"🔍 CONTEXT_DB_TYPE_LOOKUP | ID: {request_id} | ConnectionID: {connection_id}")

        result = await self.session.execute(
            select(DatabaseConnection.db_type).where(DatabaseConnection.id == connection_id)
        )
        db_type = result.scalar_one_or_none()
        database_type = db_type if db_type else "unknown"

        logger.info(f"ℹ️ CONTEXT_DB_TYPE | ID: {request_id} | Type: {database_type}")

        # Load all context components in parallel
        logger.info(f"📥 CONTEXT_LOADING_COMPONENTS | ID: {request_id} | Loading schema, dictionary, relationships, use cases")

        load_start = time.time()
        schema_info = await self._load_schema(snapshot_id)
        data_dictionary = await self._load_data_dictionary(snapshot_id)
        relationships = await self._load_relationships(snapshot_id)
        use_cases = await self._load_use_cases(snapshot_id)
        load_time = int((time.time() - load_start) * 1000)

        # Group schema by tables
        tables = {}
        for schema_item in schema_info:
            table_key = f"{schema_item.schema_name}.{schema_item.table_name}"
            if table_key not in tables:
                tables[table_key] = []
            tables[table_key].append(schema_item.column_name)

        logger.info(f"✅ CONTEXT_COMPONENTS_LOADED | ID: {request_id} | Tables: {len(tables)} | Columns: {sum(len(cols) for cols in tables.values())} | Dictionary: {len(data_dictionary)} | Relationships: {len(relationships)} | UseCases: {len(use_cases)} | Time: {load_time}ms")
        logger.debug(f"📋 CONTEXT_TABLES | ID: {request_id} | Tables: {list(tables.keys())}")

        # Create immutable ChatContext
        context_hash = hashlib.md5(json.dumps({
            "snapshot_id": snapshot_id,
            "tables": sorted(tables.keys()),
            "table_count": len(tables),
            "column_count": sum(len(cols) for cols in tables.values())
        }).encode()).hexdigest()[:16]

        total_time = int((time.time() - start_time) * 1000)
        logger.info(f"🎯 CONTEXT_LOAD_COMPLETE | ID: {request_id} | Hash: {context_hash} | TotalTime: {total_time}ms")

        return ChatContext(
            snapshot_id=snapshot_id,
            snapshot_name=snapshot_name,
            database_type=database_type,
            schema_info=schema_info,
            data_dictionary=data_dictionary,
            relationships=relationships,
            use_cases=use_cases,
            context_hash=context_hash
        )

    async def _load_schema(self, snapshot_id: int) -> List[SchemaInfo]:
        """Load schema metadata for a snapshot"""
        logger.debug(f"📊 LOADING_SCHEMA | SnapshotID: {snapshot_id}")

        result = await self.session.execute(
            select(SchemaMetadata).where(SchemaMetadata.schema_snapshot_id == snapshot_id)
        )
        schema_records = result.scalars().all()

        logger.debug(f"📊 SCHEMA_RECORDS_LOADED | SnapshotID: {snapshot_id} | Records: {len(schema_records)}")

        return [
            SchemaInfo(
                schema_name=record.schema_name,
                table_name=record.table_name,
                column_name=record.column_name,
                column_type=record.column_type,
                is_primary_key=record.is_primary_key,
                is_foreign_key=record.is_foreign_key,
                foreign_key_table=record.foreign_key_table,
                foreign_key_column=record.foreign_key_column
            )
            for record in schema_records
        ]

    async def _load_data_dictionary(self, snapshot_id: int) -> List[DataDictionaryInfo]:
        """Load data dictionary entries for a snapshot"""
        result = await self.session.execute(
            select(DataDictionary).where(DataDictionary.schema_snapshot_id == snapshot_id)
        )
        dictionary_records = result.scalars().all()

        return [
            DataDictionaryInfo(
                schema_name=record.schema_name,
                table_name=record.table_name,
                column_name=record.column_name,
                description=record.description,
                example_values=record.example_values,
                synonyms=record.synonyms,
                is_sensitive=record.is_sensitive
            )
            for record in dictionary_records
        ]

    async def _load_relationships(self, snapshot_id: int) -> List[RelationshipInfo]:
        """Load relationships for a snapshot"""
        result = await self.session.execute(
            select(Relationship).where(Relationship.schema_snapshot_id == snapshot_id)
        )
        relationship_records = result.scalars().all()

        return [
            RelationshipInfo(
                source_table=record.source_table,
                source_column=record.source_column,
                target_table=record.target_table,
                target_column=record.target_column,
                relationship_type=record.relationship_type,
                join_type=record.join_type,
                cardinality=record.cardinality,
                description=record.description,
                confidence_score=record.confidence_score
            )
            for record in relationship_records
        ]

    async def _load_use_cases(self, snapshot_id: int) -> List[UseCaseInfo]:
        """Load active use cases for a snapshot with comprehensive logging"""
        logger.debug(f"📋 LOADING_USE_CASES | SnapshotID: {snapshot_id}")
        
        result = await self.session.execute(
            select(UseCase).where(UseCase.schema_snapshot_id == snapshot_id)
        )
        use_case_records = result.scalars().all()

        logger.info(f"📋 USE_CASES_FOUND | SnapshotID: {snapshot_id} | Count: {len(use_case_records)}")

        use_cases = []

        for record in use_case_records:
            # Parse JSON fields
            try:
                example_questions = json.loads(record.example_questions) if record.example_questions else []
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"⚠️ USE_CASE_PARSE_ERROR | UseCaseID: {record.id} | Field: example_questions | Error: {e}")
                example_questions = []

            try:
                example_queries = json.loads(record.example_queries) if record.example_queries else None
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"⚠️ USE_CASE_PARSE_ERROR | UseCaseID: {record.id} | Field: example_queries | Error: {e}")
                example_queries = None

            # Log use case details
            logger.debug(f"📋 USE_CASE_LOADED | Name: {record.name} | Questions: {len(example_questions)} | Queries: {len(example_queries) if example_queries else 0}")

            use_cases.append(UseCaseInfo(
                name=record.name,
                business_goal=record.business_goal,
                example_questions=example_questions,
                example_queries=example_queries,
                output_style=record.output_style
            ))

        logger.info(f"✅ USE_CASES_LOADED | SnapshotID: {snapshot_id} | Total: {len(use_cases)} | WithExamples: {sum(1 for uc in use_cases if uc.example_questions and uc.example_queries)}")
        return use_cases
