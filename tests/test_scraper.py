"""Парсинг целиком на поддельном сайте: сеть подменена httpx.MockTransport."""
from collections import Counter
from pathlib import Path

import httpx
import pytest

from catalog_parser.fetcher import FetchError, Fetcher
from catalog_parser.scraper import scrape

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://books.toscrape.com/"
PAGES = {
    BASE + "index.html": "index.html",
    BASE + "catalogue/category/books/mystery_3/index.html": "category_page1.html",
    BASE + "catalogue/category/books/mystery_3/page-2.html": "category_page2.html",
}


def fake_site(fail_first: int = 0, broken: set[str] = frozenset()):
    """Отдаёт фикстуры; на любую карточку товара — product.html. fail_first — сколько первых запросов вернуть 503."""
    hits: Counter[str] = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        hits[url] += 1
        if sum(hits.values()) <= fail_first:
            return httpx.Response(503)
        if url in broken:
            return httpx.Response(404)
        name = PAGES.get(url) or ("product.html" if url.startswith(BASE + "catalogue/") else None)
        if name is None:
            return httpx.Response(404)
        return httpx.Response(200, content=(FIXTURES / name).read_bytes())

    return httpx.MockTransport(handler), hits


async def test_scrape_category_all_pages():
    transport, hits = fake_site()
    async with Fetcher(transport=transport) as fetcher:
        result = await scrape(fetcher, BASE + "index.html", categories=["mystery"])
    assert len(result.products) == 32  # 20 + 12 со второй страницы
    assert result.failed == []
    assert hits[BASE + "catalogue/category/books/mystery_3/page-2.html"] == 1
    # Порядок как в каталоге, а не как завершились запросы
    assert result.products[0].url.endswith("sharp-objects_997/index.html")


async def test_limit_stops_pagination():
    transport, hits = fake_site()
    async with Fetcher(transport=transport) as fetcher:
        result = await scrape(fetcher, BASE + "index.html", categories=["Mystery"], limit_per_category=5)
    assert len(result.products) == 5
    assert hits[BASE + "catalogue/category/books/mystery_3/page-2.html"] == 0


async def test_retries_on_server_errors(monkeypatch):
    monkeypatch.setattr("catalog_parser.fetcher.asyncio.sleep", _no_sleep)
    transport, _ = fake_site(fail_first=2)
    async with Fetcher(transport=transport, retries=3) as fetcher:
        html = await fetcher.get(BASE + "index.html")
    assert "side_categories" in html


async def test_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr("catalog_parser.fetcher.asyncio.sleep", _no_sleep)
    transport, _ = fake_site(fail_first=100)
    async with Fetcher(transport=transport, retries=3) as fetcher:
        with pytest.raises(FetchError):
            await fetcher.get(BASE + "index.html")
        assert fetcher.requests == 3


async def test_broken_product_is_skipped_not_fatal():
    broken = BASE + "catalogue/in-a-dark-dark-wood_963/index.html"
    transport, _ = fake_site(broken={broken})
    async with Fetcher(transport=transport) as fetcher:
        result = await scrape(fetcher, BASE + "index.html", categories=["Mystery"])
    assert result.failed == [broken]
    assert len(result.products) == 31


async def _no_sleep(_seconds: float) -> None:
    pass
