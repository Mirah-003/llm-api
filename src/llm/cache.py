import hashlib
from typing import Dict, Optional
from src.llm.schema import TriageResponse

class ResponseCache:
    """
    In-memory FIFO cache for LLM responses.
    Hashes (prompt_version + user_input) using SHA-256 to ensure 
    old cached answers are invalidated when prompt version changes.
    Evicts the oldest inserted entry when capacity is reached (FIFO policy).
    """
    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self._cache: Dict[str, TriageResponse] = {}
        self.hits = 0
        self.misses = 0

    def _generate_key(self, prompt_version: str, user_input: str) -> str:
        # Key MUST include prompt_version so prompt changes invalidate old cache!
        normalized_input = user_input.strip().lower()
        raw_key = f"{prompt_version}:{normalized_input}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get(self, prompt_version: str, user_input: str) -> Optional[TriageResponse]:
        key = self._generate_key(prompt_version, user_input)
        if key in self._cache:
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        return None

    def set(self, prompt_version: str, user_input: str, response: TriageResponse):
        key = self._generate_key(prompt_version, user_input)
        # Prevent unbounded RAM growth by evicting oldest entry if full and adding a new key
        if key not in self._cache and len(self._cache) >= self.max_size:
            first_key = next(iter(self._cache))
            del self._cache[first_key]
            
        self._cache[key] = response

    def get_stats(self) -> dict:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0.0
        return {
            "cached_entries": len(self._cache),
            "total_queries": total,
            "cache_hits": self.hits,
            "cache_misses": self.misses,
            "hit_rate_pct": round(hit_rate, 2)
        }

# Global singleton cache instance
global_cache = ResponseCache(max_size=500)