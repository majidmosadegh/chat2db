"""
Query Planning and Entity Extraction Module
Enriches user questions into high-quality database query plans
"""
import re
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass

from ..schemas import ChatContext, SchemaInfo, RelationshipInfo, DataDictionaryInfo

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """Extracted entity from user question"""
    name: str
    entity_type: str  # 'company', 'product', 'date', 'number', 'domain_term'
    confidence: float
    suggested_tables: List[str]
    suggested_columns: List[str]


@dataclass
class QueryPlan:
    """Structured query plan for SQL generation"""
    intent: str
    entities: List[ExtractedEntity]
    primary_tables: List[str]
    join_path: List[Dict[str, str]]  # List of {from_table, to_table, via_column}
    filter_columns: List[str]
    aggregation_columns: List[str]
    order_by_columns: List[str]
    limit_count: Optional[int]
    requires_date_filter: bool
    date_column: Optional[str]
    confidence: float


class QueryPlanner:
    """Plans queries by extracting entities and analyzing context"""

    def __init__(self, context: ChatContext):
        self.context = context
        self.schema_map = self._build_schema_map()
        self.dictionary_map = self._build_dictionary_map()
        self.relationship_graph = self._build_relationship_graph()

    def _build_schema_map(self) -> Dict[str, List[SchemaInfo]]:
        """Build map of table -> columns"""
        schema_map = {}
        for schema_item in self.context.schema_info:
            table_key = f"{schema_item.schema_name}.{schema_item.table_name}"
            if table_key not in schema_map:
                schema_map[table_key] = []
            schema_map[table_key].append(schema_item)
        return schema_map

    def _build_dictionary_map(self) -> Dict[str, Dict[str, DataDictionaryInfo]]:
        """Build map of table -> column -> dictionary info"""
        dict_map = {}
        for dict_item in self.context.data_dictionary:
            table_key = f"{dict_item.schema_name}.{dict_item.table_name}"
            if table_key not in dict_map:
                dict_map[table_key] = {}
            if dict_item.column_name:
                dict_map[table_key][dict_item.column_name] = dict_item
        return dict_map

    def _build_relationship_graph(self) -> Dict[str, List[Dict[str, str]]]:
        """Build graph of table relationships"""
        graph = {}
        for rel in self.context.relationships:
            source = rel.source_table
            target = rel.target_table
            
            if source not in graph:
                graph[source] = []
            graph[source].append({
                "target": target,
                "source_column": rel.source_column,
                "target_column": rel.target_column,
                "join_type": rel.join_type,
                "cardinality": rel.cardinality
            })
            
            # Bidirectional
            if target not in graph:
                graph[target] = []
            graph[target].append({
                "target": source,
                "source_column": rel.target_column,
                "target_column": rel.source_column,
                "join_type": rel.join_type,
                "cardinality": rel.cardinality
            })
        return graph

    def extract_entities(self, question: str) -> List[ExtractedEntity]:
        """
        Extract entities (company names, products, dates, etc.) from question
        
        Args:
            question: User question
            
        Returns:
            List of extracted entities with suggested tables/columns
        """
        entities = []
        question_lower = question.lower()
        
        # Extract dates
        date_patterns = [
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # YYYY-MM-DD
            r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',  # DD-MM-YYYY
            r'(today|yesterday|tomorrow|last week|last month|this year)',
            r'(\d+)\s*(days?|weeks?|months?|years?)\s*(ago|before)'
        ]
        
        for pattern in date_patterns:
            matches = re.finditer(pattern, question_lower, re.IGNORECASE)
            for match in matches:
                entities.append(ExtractedEntity(
                    name=match.group(),
                    entity_type="date",
                    confidence=0.8,
                    suggested_tables=self._find_tables_with_date_columns(),
                    suggested_columns=self._find_date_columns()
                ))
        
        # Extract numbers (quantities, prices, IDs)
        number_patterns = [
            r'\b\d+\b',  # Simple numbers
            r'\$\d+',    # Prices
            r'\d+\s*(million|thousand|k|m)\b'  # Large numbers
        ]
        
        for pattern in number_patterns:
            matches = re.finditer(pattern, question_lower, re.IGNORECASE)
            for match in matches:
                entities.append(ExtractedEntity(
                    name=match.group(),
                    entity_type="number",
                    confidence=0.6,
                    suggested_tables=list(self.schema_map.keys()),
                    suggested_columns=self._find_numeric_columns()
                ))
        
        # Extract domain terms from dictionary
        for table_key, columns in self.dictionary_map.items():
            for col_name, dict_info in columns.items():
                if dict_info.description:
                    # Check if question contains words from description
                    desc_words = set(re.findall(r'\w+', dict_info.description.lower()))
                    question_words = set(re.findall(r'\w+', question_lower))
                    overlap = desc_words & question_words
                    
                    if len(overlap) >= 2:  # At least 2 matching words
                        entities.append(ExtractedEntity(
                            name=" ".join(overlap),
                            entity_type="domain_term",
                            confidence=0.7,
                            suggested_tables=[table_key],
                            suggested_columns=[col_name]
                        ))
        
        # Extract table/column names mentioned in question
        for table_key, columns in self.schema_map.items():
            table_name = table_key.split('.')[-1].lower()
            if table_name in question_lower:
                entities.append(ExtractedEntity(
                    name=table_name,
                    entity_type="table_reference",
                    confidence=0.9,
                    suggested_tables=[table_key],
                    suggested_columns=[col.column_name for col in columns]
                ))
            
            for col in columns:
                if col.column_name.lower() in question_lower:
                    entities.append(ExtractedEntity(
                        name=col.column_name,
                        entity_type="column_reference",
                        confidence=0.9,
                        suggested_tables=[table_key],
                        suggested_columns=[col.column_name]
                    ))
        
        # Remove duplicates
        seen = set()
        unique_entities = []
        for entity in entities:
            key = (entity.name.lower(), entity.entity_type)
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)
        
        return unique_entities

    def _find_tables_with_date_columns(self) -> List[str]:
        """Find tables that have date/datetime columns"""
        tables = set()
        date_types = ['date', 'datetime', 'timestamp', 'datetime2', 'smalldatetime']
        
        for table_key, columns in self.schema_map.items():
            for col in columns:
                if any(dt in col.column_type.lower() for dt in date_types):
                    tables.add(table_key)
        
        return list(tables)

    def _find_date_columns(self) -> List[str]:
        """Find all date/datetime columns"""
        columns = []
        date_types = ['date', 'datetime', 'timestamp', 'datetime2', 'smalldatetime']
        
        for table_key, cols in self.schema_map.items():
            for col in cols:
                if any(dt in col.column_type.lower() for dt in date_types):
                    columns.append(f"{table_key}.{col.column_name}")
        
        return columns

    def _find_numeric_columns(self) -> List[str]:
        """Find all numeric columns"""
        columns = []
        numeric_types = ['int', 'bigint', 'decimal', 'float', 'money', 'numeric', 'smallint', 'tinyint']
        
        for table_key, cols in self.schema_map.items():
            for col in cols:
                if any(nt in col.column_type.lower() for nt in numeric_types):
                    columns.append(f"{table_key}.{col.column_name}")
        
        return columns

    def plan_query(
        self,
        question: str,
        intent: str,
        entities: Optional[List[ExtractedEntity]] = None
    ) -> QueryPlan:
        """
        Create a structured query plan from question and intent
        
        Args:
            question: User question
            intent: Detected intent (COUNT, AGGREGATION, LIST, etc.)
            entities: Extracted entities (if None, will extract)
            
        Returns:
            QueryPlan with tables, joins, filters, etc.
        """
        if entities is None:
            entities = self.extract_entities(question)
        
        # Determine primary tables from entities
        primary_tables = self._determine_primary_tables(entities, intent)
        
        # Find join path between tables
        join_path = self._find_join_path(primary_tables)
        
        # Determine filter columns
        filter_columns = self._determine_filter_columns(entities, question)
        
        # Determine aggregation columns
        aggregation_columns = self._determine_aggregation_columns(intent, entities)
        
        # Determine order by columns
        order_by_columns = self._determine_order_by_columns(intent, entities)
        
        # Check for date filtering needs
        requires_date_filter, date_column = self._check_date_filtering(entities, question)
        
        # Determine limit
        limit_count = self._determine_limit(intent)
        
        # Calculate confidence
        confidence = self._calculate_confidence(entities, primary_tables, join_path)
        
        return QueryPlan(
            intent=intent,
            entities=entities,
            primary_tables=primary_tables,
            join_path=join_path,
            filter_columns=filter_columns,
            aggregation_columns=aggregation_columns,
            order_by_columns=order_by_columns,
            limit_count=limit_count,
            requires_date_filter=requires_date_filter,
            date_column=date_column,
            confidence=confidence
        )

    def _determine_primary_tables(
        self,
        entities: List[ExtractedEntity],
        intent: str
    ) -> List[str]:
        """Determine which tables are most relevant"""
        table_scores = {}
        
        # Score tables based on entities
        for entity in entities:
            for table in entity.suggested_tables:
                if table not in table_scores:
                    table_scores[table] = 0
                table_scores[table] += entity.confidence
        
        # Boost tables with relevant columns for intent
        if intent in ["COUNT", "AGGREGATION"]:
            for table_key, columns in self.schema_map.items():
                numeric_cols = [c for c in columns if any(nt in c.column_type.lower() 
                    for nt in ['int', 'decimal', 'float', 'money', 'numeric'])]
                if numeric_cols:
                    if table_key not in table_scores:
                        table_scores[table_key] = 0
                    table_scores[table_key] += 0.3
        
        # Sort by score and return top tables
        sorted_tables = sorted(table_scores.items(), key=lambda x: x[1], reverse=True)
        return [table for table, score in sorted_tables[:3]]  # Top 3 tables

    def _find_join_path(self, tables: List[str]) -> List[Dict[str, str]]:
        """Find join path between tables using relationship graph"""
        if len(tables) < 2:
            return []
        
        join_path = []
        visited = set()
        
        for i in range(len(tables) - 1):
            from_table = tables[i]
            to_table = tables[i + 1]
            
            if from_table in self.relationship_graph:
                for rel in self.relationship_graph[from_table]:
                    if rel["target"] == to_table:
                        join_path.append({
                            "from_table": from_table,
                            "to_table": to_table,
                            "from_column": rel["source_column"],
                            "to_column": rel["target_column"],
                            "join_type": rel["join_type"]
                        })
                        break
        
        return join_path

    def _determine_filter_columns(
        self,
        entities: List[ExtractedEntity],
        question: str
    ) -> List[str]:
        """Determine which columns should be used for filtering"""
        filter_cols = []
        question_lower = question.lower()
        
        # Look for filter keywords
        filter_keywords = ['where', 'filter', 'with', 'having', 'contains', 'equals', '=', '>', '<']
        
        for entity in entities:
            if entity.entity_type in ["date", "number", "domain_term"]:
                for col in entity.suggested_columns:
                    if col not in filter_cols:
                        filter_cols.append(col)
        
        # Add columns mentioned with filter keywords
        for table_key, columns in self.schema_map.items():
            for col in columns:
                col_lower = col.column_name.lower()
                if col_lower in question_lower:
                    # Check if there's a filter keyword nearby
                    col_pos = question_lower.find(col_lower)
                    nearby_text = question_lower[max(0, col_pos-20):col_pos+20]
                    if any(kw in nearby_text for kw in filter_keywords):
                        full_col = f"{table_key}.{col.column_name}"
                        if full_col not in filter_cols:
                            filter_cols.append(full_col)
        
        return filter_cols

    def _determine_aggregation_columns(
        self,
        intent: str,
        entities: List[ExtractedEntity]
    ) -> List[str]:
        """Determine columns for aggregation"""
        if intent not in ["AGGREGATION", "COUNT"]:
            return []
        
        agg_cols = []
        for table_key, columns in self.schema_map.items():
            for col in columns:
                numeric_types = ['int', 'bigint', 'decimal', 'float', 'money', 'numeric']
                if any(nt in col.column_type.lower() for nt in numeric_types):
                    agg_cols.append(f"{table_key}.{col.column_name}")
        
        return agg_cols[:5]  # Limit to top 5

    def _determine_order_by_columns(
        self,
        intent: str,
        entities: List[ExtractedEntity]
    ) -> List[str]:
        """Determine columns for ordering"""
        if intent not in ["TOP_N", "LIST"]:
            return []
        
        order_cols = []
        
        # Prefer date columns for "latest" queries
        date_cols = self._find_date_columns()
        if date_cols:
            order_cols.extend(date_cols[:2])
        
        # Add numeric columns for ranking
        numeric_cols = self._find_numeric_columns()
        if numeric_cols:
            order_cols.extend(numeric_cols[:2])
        
        return order_cols

    def _check_date_filtering(
        self,
        entities: List[ExtractedEntity],
        question: str
    ) -> tuple[bool, Optional[str]]:
        """Check if date filtering is needed"""
        question_lower = question.lower()
        date_keywords = ['latest', 'recent', 'today', 'yesterday', 'last', 'this week', 'this month', 'this year']
        
        has_date_entity = any(e.entity_type == "date" for e in entities)
        has_date_keyword = any(kw in question_lower for kw in date_keywords)
        
        if has_date_entity or has_date_keyword:
            date_cols = self._find_date_columns()
            if date_cols:
                return True, date_cols[0]
        
        return False, None

    def _determine_limit(self, intent: str) -> Optional[int]:
        """Determine result limit based on intent"""
        if intent == "COUNT":
            return None  # No limit for counts
        elif intent == "AGGREGATION":
            return None  # No limit for aggregations
        elif intent == "TOP_N":
            return 10  # Default top 10
        else:
            return 100  # Default limit for lists/details

    def _calculate_confidence(
        self,
        entities: List[ExtractedEntity],
        primary_tables: List[str],
        join_path: List[Dict[str, str]]
    ) -> float:
        """Calculate confidence score for query plan"""
        if not entities:
            return 0.3
        
        if not primary_tables:
            return 0.2
        
        # Base confidence from entities
        entity_confidence = sum(e.confidence for e in entities) / len(entities) if entities else 0
        
        # Boost if we have join path
        join_boost = 0.2 if join_path else 0
        
        # Boost if tables are found
        table_boost = 0.3 if primary_tables else 0
        
        confidence = min(1.0, entity_confidence + join_boost + table_boost)
        return confidence

