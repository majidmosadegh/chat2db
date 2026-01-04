from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..schemas import ConversationState


class ConversationStateManager:
    """Manages optional conversation state for continuity"""

    def __init__(self, session: Optional[AsyncSession] = None, max_history_entries: int = 10, ttl_hours: int = 24):
        """
        Initialize conversation state manager.

        Args:
            session: Optional database session for loading history from database
            max_history_entries: Maximum number of conversation entries to keep
            ttl_hours: Time-to-live for conversation state in hours
        """
        self.session = session
        self.max_history_entries = max_history_entries
        self.ttl_hours = ttl_hours
        self._states: Dict[str, ConversationState] = {}

    def get_conversation_state(self, conversation_id: str) -> Optional[ConversationState]:
        """
        Get conversation state by ID, checking TTL.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            ConversationState or None if not found or expired
        """
        if conversation_id not in self._states:
            return None

        state = self._states[conversation_id]

        # Check if state has expired
        if datetime.utcnow() - state.updated_at > timedelta(hours=self.ttl_hours):
            # Remove expired state
            del self._states[conversation_id]
            return None

        return state

    def create_conversation_state(self, conversation_id: str) -> ConversationState:
        """
        Create new conversation state.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            ConversationState: New empty conversation state
        """
        state = ConversationState(
            conversation_id=conversation_id,
            last_intent=None,
            last_tables=[],
            last_sql=None,
            last_result_summary=None,
            updated_at=datetime.utcnow()
        )

        self._states[conversation_id] = state
        return state

    def update_conversation_state(
        self,
        conversation_id: str,
        intent: Optional[str] = None,
        tables: Optional[List[str]] = None,
        sql: Optional[str] = None,
        result_summary: Optional[str] = None
    ) -> ConversationState:
        """
        Update conversation state with new information.

        Args:
            conversation_id: Unique conversation identifier
            intent: User's intent from reasoning
            tables: Tables used in the query
            sql: Generated SQL query
            result_summary: Summary of results

        Returns:
            ConversationState: Updated conversation state
        """
        state = self.get_conversation_state(conversation_id)

        if not state:
            state = self.create_conversation_state(conversation_id)

        # Update fields if provided
        if intent is not None:
            state.last_intent = intent

        if tables is not None:
            state.last_tables = tables[-5:]  # Keep only last 5 tables

        if sql is not None:
            state.last_sql = sql

        if result_summary is not None:
            state.last_result_summary = result_summary

        state.updated_at = datetime.utcnow()
        self._states[conversation_id] = state

        return state

    async def get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """
        Get conversation history for prompt inclusion.
        Loads from database if session is available, otherwise uses in-memory state.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            List of conversation entries with question and SQL
        """
        history = []

        # Try to load from database first if session is available
        if self.session:
            try:
                from api.db_models import ChatMessage
                
                # Load last N messages from database
                stmt = (
                    select(ChatMessage)
                    .where(ChatMessage.conversation_id == conversation_id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(self.max_history_entries * 2)  # Get more to filter user/assistant pairs
                )
                result = await self.session.execute(stmt)
                messages = result.scalars().all()

                # Build history from message pairs (user -> assistant)
                messages_sorted = sorted(messages, key=lambda m: m.created_at)
                for i in range(len(messages_sorted) - 1):
                    if (messages_sorted[i].role == "user" and
                        messages_sorted[i + 1].role == "assistant"):
                        sql = messages_sorted[i + 1].generated_sql or ""
                        # Only include pairs that have actual SQL queries (not empty or conversational responses)
                        if sql.strip():
                            history.append({
                                "question": messages_sorted[i].content,
                                "sql": sql
                            })

                # Keep only last N entries
                history = history[-self.max_history_entries:]
                
                if history:
                    return history
            except Exception as e:
                # Fall back to in-memory state if database load fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to load conversation history from database: {e}")

        # Fallback to in-memory state
        state = self.get_conversation_state(conversation_id)

        if not state or not state.last_sql:
            return []

        if state.last_intent and state.last_sql:
            history.append({
                "question": f"Previous query intent: {state.last_intent}",
                "sql": state.last_sql
            })

        return history[-self.max_history_entries:]

    def clear_conversation_state(self, conversation_id: str):
        """
        Clear conversation state.

        Args:
            conversation_id: Unique conversation identifier
        """
        if conversation_id in self._states:
            del self._states[conversation_id]

    def cleanup_expired_states(self):
        """Remove all expired conversation states"""
        current_time = datetime.utcnow()
        expired_ids = []

        for conv_id, state in self._states.items():
            if current_time - state.updated_at > timedelta(hours=self.ttl_hours):
                expired_ids.append(conv_id)

        for conv_id in expired_ids:
            del self._states[conv_id]

    def get_active_conversations_count(self) -> int:
        """Get count of active (non-expired) conversations"""
        self.cleanup_expired_states()
        return len(self._states)
