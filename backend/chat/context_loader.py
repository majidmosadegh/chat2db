from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any
import json

from api.db_models import (
    SchemaMetadata, DataDictionary, Relationship, UseCase,
    SchemaSnapshot, UseCaseVersion
)
from .schemas import (
    SchemaInfo, DataDictionaryInfo, RelationshipInfo, UseCaseInfo
)


class ContextLoader:
    """Loads context information for a schema snapshot"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def load_schema(self, snapshot_id: int) -> List[SchemaInfo]:
        """Load schema metadata for a snapshot"""
        result = await self.session.execute(
            select(SchemaMetadata).where(SchemaMetadata.schema_snapshot_id == snapshot_id)
        )
        schema_records = result.scalars().all()

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

    async def load_data_dictionary(self, snapshot_id: int) -> List[DataDictionaryInfo]:
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

    async def load_relationships(self, snapshot_id: int) -> List[RelationshipInfo]:
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

    async def load_use_cases(self, snapshot_id: int) -> List[UseCaseInfo]:
        """Load active use cases for a snapshot"""
        # First get use cases directly linked to this snapshot
        result = await self.session.execute(
            select(UseCase).where(UseCase.schema_snapshot_id == snapshot_id)
        )
        use_case_records = result.scalars().all()

        use_cases = []

        for record in use_case_records:
            # Parse JSON fields
            try:
                example_questions = json.loads(record.example_questions) if record.example_questions else []
            except (json.JSONDecodeError, TypeError):
                example_questions = []

            try:
                example_queries = json.loads(record.example_queries) if record.example_queries else None
            except (json.JSONDecodeError, TypeError):
                example_queries = None

            use_cases.append(UseCaseInfo(
                name=record.name,
                business_goal=record.business_goal,
                example_questions=example_questions,
                example_queries=example_queries,
                output_style=record.output_style
            ))

        return use_cases

    async def load_all_context(self, snapshot_id: int) -> Dict[str, Any]:
        """Load all context information for a snapshot"""
        # Verify snapshot exists
        result = await self.session.execute(
            select(SchemaSnapshot).where(SchemaSnapshot.id == snapshot_id)
        )
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            raise ValueError(f"Schema snapshot {snapshot_id} not found")

        return {
            "schema": await self.load_schema(snapshot_id),
            "data_dictionary": await self.load_data_dictionary(snapshot_id),
            "relationships": await self.load_relationships(snapshot_id),
            "use_cases": await self.load_use_cases(snapshot_id),
            "snapshot_name": snapshot.name
        }
