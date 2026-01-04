"""
Context Cache - In-memory cache for ChatContext with TTL
Reduces database load and improves response time for repeated requests
"""
from typing import Dict, Optional, Tuple
import hashlib
import json
import logging
from datetime import datetime, timedelta

from ..schemas import ChatContext
from .context_loader import ContextLoader

logger = logging.getLogger(__name__)


class ContextCache:
    """In-memory cache for ChatContext with TTL and invalidation support"""
    
    def __init__(self, ttl_seconds: int = 3600):  # 1 hour default
        """
        Initialize context cache.
        
        Args:
            ttl_seconds: Time-to-live for cached contexts in seconds (default: 1 hour)
        """
        self.cache: Dict[str, Tuple[ChatContext, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        logger.info(f"📦 CONTEXT_CACHE_INIT | TTL: {ttl_seconds}s")
    
    def _get_cache_key(self, snapshot_id: int, context_version: Optional[str] = None) -> str:
        """
        Generate cache key from snapshot_id and optional version.
        
        Args:
            snapshot_id: Schema snapshot ID
            context_version: Optional version string for cache invalidation
            
        Returns:
            Cache key as hex string
        """
        key_data = {"snapshot_id": snapshot_id}
        if context_version:
            key_data["version"] = context_version
        return hashlib.md5(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()
    
    async def get_context(
        self, 
        snapshot_id: int, 
        loader: ContextLoader,
        context_version: Optional[str] = None
    ) -> ChatContext:
        """
        Get context from cache or load if not cached.
        
        Args:
            snapshot_id: Schema snapshot ID
            loader: ContextLoader instance to use if cache miss
            context_version: Optional version string for cache invalidation
            
        Returns:
            ChatContext: Cached or freshly loaded context
        """
        cache_key = self._get_cache_key(snapshot_id, context_version)
        
        # Check cache
        if cache_key in self.cache:
            context, cached_at = self.cache[cache_key]
            age = datetime.utcnow() - cached_at
            
            if age < self.ttl:
                logger.info(
                    f"📦 CONTEXT_CACHE_HIT | SnapshotID: {snapshot_id} | "
                    f"Key: {cache_key[:8]} | Age: {age.total_seconds():.1f}s"
                )
                return context
            else:
                # Expired, remove from cache
                del self.cache[cache_key]
                logger.info(
                    f"⏰ CONTEXT_CACHE_EXPIRED | SnapshotID: {snapshot_id} | "
                    f"Key: {cache_key[:8]} | Age: {age.total_seconds():.1f}s"
                )
        
        # Cache miss, load from database
        logger.info(
            f"📥 CONTEXT_CACHE_MISS | SnapshotID: {snapshot_id} | Loading from DB"
        )
        context = await loader.load_context(snapshot_id)
        
        # Store in cache
        self.cache[cache_key] = (context, datetime.utcnow())
        logger.info(
            f"💾 CONTEXT_CACHE_STORED | SnapshotID: {snapshot_id} | "
            f"Key: {cache_key[:8]} | Tables: {len(set(f'{s.schema_name}.{s.table_name}' for s in context.schema_info))}"
        )
        
        return context
    
    def invalidate(self, snapshot_id: int, context_version: Optional[str] = None):
        """
        Invalidate cache for a specific snapshot.
        
        Args:
            snapshot_id: Schema snapshot ID to invalidate
            context_version: Optional version string
        """
        cache_key = self._get_cache_key(snapshot_id, context_version)
        if cache_key in self.cache:
            del self.cache[cache_key]
            logger.info(
                f"🗑️ CONTEXT_CACHE_INVALIDATED | SnapshotID: {snapshot_id} | "
                f"Key: {cache_key[:8]}"
            )
        else:
            logger.debug(
                f"🔍 CONTEXT_CACHE_NOT_FOUND | SnapshotID: {snapshot_id} | "
                f"Key: {cache_key[:8]}"
            )
    
    def invalidate_all(self):
        """Invalidate all cached contexts"""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"🧹 CONTEXT_CACHE_CLEARED | Removed: {count} entries")
    
    def cleanup_expired(self):
        """Remove all expired entries from cache"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, (context, cached_at) in self.cache.items()
            if now - cached_at >= self.ttl
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(
                f"🧹 CONTEXT_CACHE_CLEANUP | Removed: {len(expired_keys)} expired entries"
            )
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, any]:
        """Get cache statistics"""
        now = datetime.utcnow()
        total_entries = len(self.cache)
        expired_entries = sum(
            1 for _, (_, cached_at) in self.cache.items()
            if now - cached_at >= self.ttl
        )
        active_entries = total_entries - expired_entries
        
        return {
            "total_entries": total_entries,
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "ttl_seconds": self.ttl.total_seconds()
        }

