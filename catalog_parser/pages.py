"""Разбор HTML-страниц каталога. Чистые функции: HTML на входе, данные на выходе — без сети."""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from catalog_parser.models import Product

RATINGS = {"Zero": 0, "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


class ParseError(Exception):
    """Страница не похожа на ожидаемую — сайт мог поменять вёрстку."""


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _money(text: str) -> float:
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    if not match:
        raise ParseError(f"Не удалось разобрать цену: {text!r}")
    return float(match.group().replace(",", "."))


def parse_categories(html: str, page_url: str) -> dict[str, str]:
    """Категории из бокового меню: {название: абсолютная ссылка}."""
    links = _soup(html).select(".side_categories ul ul a")
    if not links:
        raise ParseError("Меню категорий не найдено")
    return {a.get_text(strip=True): urljoin(page_url, a["href"]) for a in links}


def parse_listing(html: str, page_url: str) -> tuple[list[str], str | None]:
    """Ссылки на товары со страницы категории и ссылка на следующую страницу (или None)."""
    soup = _soup(html)
    products = [urljoin(page_url, a["href"]) for a in soup.select("article.product_pod h3 a")]
    next_link = soup.select_one("li.next a")
    return products, urljoin(page_url, next_link["href"]) if next_link else None


def parse_product(html: str, url: str) -> Product:
    soup = _soup(html)
    main = soup.select_one(".product_main")
    if main is None:
        raise ParseError(f"Карточка товара не найдена: {url}")

    table = {th.get_text(strip=True): td.get_text(strip=True) for th, td in
             ((row.th, row.td) for row in soup.select("table.table-striped tr")) if th and td}
    stock = re.search(r"\d+", table.get("Availability", ""))

    rating_tag = main.select_one("p.star-rating")
    rating_class = next((c for c in rating_tag["class"] if c in RATINGS), "Zero") if rating_tag else "Zero"

    # Хлебные крошки: Home / Books / <Категория> / <Товар>
    crumbs = soup.select("ul.breadcrumb li a")
    description_tag = soup.select_one("#product_description + p")
    image = soup.select_one("#product_gallery img, .item.active img")

    return Product(
        title=main.h1.get_text(strip=True),
        category=crumbs[-1].get_text(strip=True) if len(crumbs) >= 3 else "",
        price=_money(main.select_one("p.price_color").get_text()),
        price_excl_tax=_money(table.get("Price (excl. tax)", "0")),
        in_stock=int(stock.group()) if stock else 0,
        rating=RATINGS[rating_class],
        reviews=int(table.get("Number of reviews", "0") or 0),
        upc=table.get("UPC", ""),
        description=description_tag.get_text(strip=True).removesuffix("...more").strip() if description_tag else "",
        url=url,
        image_url=urljoin(url, image["src"]) if image else "",
    )
