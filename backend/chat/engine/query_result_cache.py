"""
Query Result Cache - Cache for SQL query results with TTL
Reduces database load for repeated queries
"""
from typing import Dict, Optional, List, Any
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class QueryResultCache:
    """Cache for SQL query results with TTL and normalization"""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default
        """
        Initialize query result cache.
        
        Args:
            ttl_seconds: Time-to-live for cached results in seconds (default: 5 minutes)
        """
        self.cache: Dict[str, Tuple[Dict[str, Any], datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        logger.info(f"📦 QUERY_CACHE_INIT | TTL: {ttl_seconds}s")
    
    def _normalize_sql(self, sql: str) -> str:
        """
        Normalize SQL for consistent caching.
        Removes whitespace, normalizes case, and removes comments.
        
        Args:
            sql: Original SQL query
            
        Returns:
            Normalized SQL string
        """
        # Remove comments
        sql = re.sub(r'--.*?$', '', sql, flags=re.MULTILINE)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        
        # Normalize whitespace
        sql = ' '.join(sql.split())
        
        # Convert to uppercase for consistency (but preserve string literals)
        # This is a simple approach - for production, consider a SQL parser
        return sql.upper()
    
    def _get_cache_key(self, sql: str, snapshot_id: int) -> str:
        """
        Generate cache key from normalized SQL and snapshot_id.
        
        Args:
            sql: SQL query (will be normalized)
            snapshot_id: Schema snapshot ID
            
        Returns:
            Cache key as hex string
        """
        normalized_sql = self._normalize_sql(sql)
        key_data = {
            "sql": normalized_sql,
            "snapshot_id": snapshot_id
        }
        return hashlib.sha256(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()
    
    def get_result(
        self, 
        sql: str, 
        snapshot_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached result if available and not expired.
        
        Args:
            sql: SQL query
            snapshot_id: Schema snapshot ID
            
        Returns:
            Cached result dict or None if not found/expired
        """
        cache_key = self._get_cache_key(sql, snapshot_id)
        
        if cache_key in self.cache:
            result, cached_at = self.cache[cache_key]
            age = datetime.utcnow() - cached_at
            
            if age < self.ttl:
                logger.info(
                    f"📦 QUERY_CACHE_HIT | SQL: {sql[:50]}... | "
                    f"Key: {cache_key[:8]} | Age: {age.total_seconds():.1f}s | "
                    f"Rows: {result.get('row_count', 0)}"
                )
                return result
            else:
                # Expired, remove from cache
                del self.cache[cache_key]
                logger.info(
                    f"⏰ QUERY_CACHE_EXPIRED | SQL: {sql[:50]}... | "
                    f"Key: {cache_key[:8]} | Age: {age.total_seconds():.1f}s"
                )
        
        return None
    
    def store_result(
        self, 
        sql: str, 
        snapshot_id: int, 
        result: Dict[str, Any]
    ):
        """
        Store query result in cache.
        
        Args:
            sql: SQL query
            snapshot_id: Schema snapshot ID
            result: Result dictionary to cache
        """
        cache_key = self._get_cache_key(sql, snapshot_id)
        
        # Only cache successful results
        if result.get("success", False):
            self.cache[cache_key] = (result, datetime.utcnow())
            logger.info(
                f"💾 QUERY_CACHE_STORED | SQL: {sql[:50]}... | "
                f"Key: {cache_key[:8]} | Rows: {result.get('row_count', 0)}"
            )
        else:
            logger.debug(
                f"⏭️ QUERY_CACHE_SKIPPED | SQL: {sql[:50]}... | "
                f"Reason: Unsuccessful result"
            )
    
    def invalidate_snapshot(self, snapshot_id: int):
        """
        Invalidate all cached results for a specific snapshot.
        
        Args:
            snapshot_id: Schema snapshot ID to invalidate
        """
        keys_to_remove = [
            key for key, (result, _) in self.cache.items()
            if result.get("snapshot_id") == snapshot_id
        ]
        
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            logger.info(
                f"🗑️ QUERY_CACHE_INVALIDATED | SnapshotID: {snapshot_id} | "
                f"Removed: {len(keys_to_remove)} entries"
            )
        else:
            logger.debug(
                f"🔍 QUERY_CACHE_NOT_FOUND | SnapshotID: {snapshot_id} | No entries to remove"
            )
    
    def invalidate_all(self):
        """Invalidate all cached results"""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"🧹 QUERY_CACHE_CLEARED | Removed: {count} entries")
    
    def cleanup_expired(self):
        """Remove all expired entries from cache"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, (result, cached_at) in self.cache.items()
            if now - cached_at >= self.ttl
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(
                f"🧹 QUERY_CACHE_CLEANUP | Removed: {len(expired_keys)} expired entries"
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
        
        total_rows = sum(
            result.get("row_count", 0)
            for _, (result, _) in self.cache.items()
        )
        
        return {
            "total_entries": total_entries,
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "total_cached_rows": total_rows,
            "ttl_seconds": self.ttl.total_seconds()
        }

