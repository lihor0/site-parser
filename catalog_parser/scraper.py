import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from catalog_parser.fetcher import FetchError, Fetcher
from catalog_parser.models import Product
from catalog_parser.pages import ParseError, parse_categories, parse_listing, parse_product

log = logging.getLogger(__name__)

DEFAULT_START_URL = "https://books.toscrape.com/index.html"


@dataclass
class ScrapeResult:
    products: list[Product] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


async def collect_product_urls(fetcher: Fetcher, category_url: str, limit: int | None) -> list[str]:
    """Проходит все страницы категории по ссылке «next»."""
    urls: list[str] = []
    page: str | None = category_url
    while page and (limit is None or len(urls) < limit):
        found, page = parse_listing(await fetcher.get(page), page)
        urls.extend(found)
    return urls[:limit] if limit else urls


async def scrape(
    fetcher: Fetcher,
    start_url: str = DEFAULT_START_URL,
    categories: list[str] | None = None,
    limit_per_category: int | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> ScrapeResult:
    all_categories = parse_categories(await fetcher.get(start_url), start_url)
    if categories:
        wanted = {c.casefold() for c in categories}
        selected = {name: url for name, url in all_categories.items() if name.casefold() in wanted}
        missing = wanted - {n.casefold() for n in selected}
        if missing:
            log.warning("Категории не найдены: %s", ", ".join(sorted(missing)))
    else:
        selected = all_categories
    log.info("Категорий к обработке: %d", len(selected))

    url_lists = await asyncio.gather(
        *(collect_product_urls(fetcher, url, limit_per_category) for url in selected.values())
    )
    # Один товар может быть в нескольких местах — убираем дубли, сохраняя порядок
    product_urls = list(dict.fromkeys(u for urls in url_lists for u in urls))
    log.info("Найдено товаров: %d", len(product_urls))

    result = ScrapeResult()
    done = 0

    async def load(url: str) -> None:
        nonlocal done
        try:
            result.products.append(parse_product(await fetcher.get(url), url))
        except (FetchError, ParseError) as e:
            log.error("Пропущен товар: %s", e)
            result.failed.append(url)
        done += 1
        if on_progress:
            on_progress(done, len(product_urls))

    await asyncio.gather(*(load(u) for u in product_urls))
    # gather завершается в произвольном порядке — возвращаем порядок каталога
    order = {u: i for i, u in enumerate(product_urls)}
    result.products.sort(key=lambda p: order[p.url])
    return result
