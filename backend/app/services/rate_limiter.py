import time
import asyncio
from typing import Optional

class GeminiRateLimiter:
    """
    Thread-safe and Async-friendly Rate Limiter for Google Gemini API.
    Enforces a strict requests-per-minute (RPM) ceiling (default 14 RPM on free/tier-1 quotas)
    to prevent HTTP 429 ResourceExhausted errors during concurrent agent & vision tasks.
    """
    def __init__(self, max_rpm: int = 14):
        self.max_rpm = max_rpm
        self.min_interval = 60.0 / max(max_rpm, 1)
        self.last_call_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Asynchronously waits until the required interval has elapsed since the last API call."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_call_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                await asyncio.sleep(wait_time)
            self.last_call_time = time.time()

    def acquire_sync(self):
        """Synchronous version for thread-based workers."""
        now = time.time()
        elapsed = now - self.last_call_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call_time = time.time()

gemini_rate_limiter = GeminiRateLimiter(max_rpm=14)
