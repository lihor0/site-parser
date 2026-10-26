import asyncio
import logging
import random

import httpx

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


class FetchError(Exception):
    pass


class Fetcher:
    """HTTP-клиент для парсинга: ограничение параллельности, пауза между запросами, повторы с backoff."""

    def __init__(
        self,
        concurrency: int = 10,
        delay: float = 0.0,
        retries: int = 3,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._semaphore = asyncio.Semaphore(concurrency)
        self._delay = delay
        self._retries = retries
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ru,en;q=0.9"},
            transport=transport,
        )
        self.requests = 0
        self.failures = 0

    async def __aenter__(self) -> "Fetcher":
        return self

    async def __aexit__(self, *exc) -> None:
        await self._client.aclose()

    async def get(self, url: str) -> str:
        for attempt in range(1, self._retries + 1):
            async with self._semaphore:
                try:
                    self.requests += 1
                    response = await self._client.get(url)
                    if response.status_code not in RETRY_STATUSES:
                        response.raise_for_status()
                        # Сайты не всегда указывают кодировку — читаем как UTF-8, а не latin-1 по умолчанию
                        return response.content.decode("utf-8", errors="replace")
                    reason = f"HTTP {response.status_code}"
                except httpx.HTTPStatusError as e:
                    raise FetchError(f"{url}: HTTP {e.response.status_code}") from e
                except httpx.TransportError as e:
                    reason = type(e).__name__
                finally:
                    if self._delay:
                        await asyncio.sleep(self._delay)

            if attempt < self._retries:
                pause = 2 ** (attempt - 1) + random.random()
                log.warning("%s: %s, повтор через %.1f с (%d/%d)", url, reason, pause, attempt, self._retries)
                await asyncio.sleep(pause)

        self.failures += 1
        raise FetchError(f"{url}: {reason} после {self._retries} попыток")
