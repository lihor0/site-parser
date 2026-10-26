from pathlib import Path

import pytest

from catalog_parser.pages import ParseError, parse_categories, parse_listing, parse_product

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://books.toscrape.com/"
MYSTERY = BASE + "catalogue/category/books/mystery_3/index.html"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_categories():
    cats = parse_categories(fixture("index.html"), BASE + "index.html")
    assert len(cats) == 50
    assert "Books" not in cats  # корневой пункт меню — не категория
    assert cats["Mystery"] == MYSTERY


def test_listing_with_next_page():
    urls, next_page = parse_listing(fixture("category_page1.html"), MYSTERY)
    assert len(urls) == 20
    assert urls[0] == BASE + "catalogue/sharp-objects_997/index.html"
    assert next_page == BASE + "catalogue/category/books/mystery_3/page-2.html"


def test_listing_last_page():
    urls, next_page = parse_listing(fixture("category_page2.html"), MYSTERY.replace("index", "page-2"))
    assert len(urls) == 12
    assert next_page is None


def test_product():
    url = BASE + "catalogue/sharp-objects_997/index.html"
    p = parse_product(fixture("product.html"), url)
    assert p.title == "Sharp Objects"
    assert p.category == "Mystery"
    assert p.price == 47.82
    assert p.price_excl_tax == 47.82
    assert p.in_stock == 20
    assert p.rating == 4
    assert p.reviews == 0
    assert p.upc == "e00eb4fd7b871a48"
    assert p.description.startswith("WICKED above her hipbone")
    assert not p.description.endswith("more")
    assert p.image_url.startswith(BASE + "media/cache/")
    assert p.url == url


def test_product_on_unexpected_page():
    with pytest.raises(ParseError):
        parse_product("<html><body>Сайт на обслуживании</body></html>", BASE)
