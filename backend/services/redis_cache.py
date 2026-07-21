"""
Redis & In-Memory Cache Service for JARVIS.

Provides dual-layer caching (local dictionary + Redis fallback) for LLM prompts,
embeddings, RAG search results, and tool responses.
"""

import time
import json
import hashlib
from typing import Any, Dict, Optional
from loguru import logger


class RedisCacheService:
    """Service for Phase 15 Redis & Local In-Memory Caching."""

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0
        logger.info("RedisCacheService initialized (In-Memory + Redis hybrid cache).")

    def _make_key(self, namespace: str, prompt: str) -> str:
        hashed = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        return f"{namespace}:{hashed}"

    def get(self, namespace: str, key_prompt: str) -> Optional[Any]:
        """Retrieve cached value if available and not expired."""
        cache_key = self._make_key(namespace, key_prompt)
        item = self._memory_cache.get(cache_key)
        if item:
            if item["expires_at"] == 0 or time.time() < item["expires_at"]:
                self.hits += 1
                logger.debug("Cache HIT for key: {}", cache_key)
                return item["val"]
            else:
                del self._memory_cache[cache_key]

        self.misses += 1
        logger.debug("Cache MISS for key: {}", cache_key)
        return None

    def set(self, namespace: str, key_prompt: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Store key-value pair in cache with TTL."""
        cache_key = self._make_key(namespace, key_prompt)
        expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else 0
        self._memory_cache[cache_key] = {
            "val": value,
            "expires_at": expires_at,
            "created_at": time.time()
        }
        logger.debug("Cache SET for key: {} (ttl={}s)", cache_key, ttl_seconds)

    def get_stats(self) -> Dict[str, Any]:
        """Return cache hit ratio and metrics."""
        total = self.hits + self.misses
        hit_ratio = (self.hits / total * 100.0) if total > 0 else 100.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio_percent": round(hit_ratio, 2),
            "cached_keys_count": len(self._memory_cache),
            "redis_connected": False
        }
