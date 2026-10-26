import argparse
import asyncio
import logging
import time
from pathlib import Path

from catalog_parser.export import to_csv, to_excel
from catalog_parser.fetcher import Fetcher
from catalog_parser.scraper import DEFAULT_START_URL, scrape


def build_args() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m catalog_parser",
        description="Парсер каталога интернет-магазина с выгрузкой в Excel",
    )
    ap.add_argument("-c", "--categories", help="Категории через запятую (по умолчанию все)")
    ap.add_argument("-l", "--limit", type=int, help="Максимум товаров из каждой категории")
    ap.add_argument("-o", "--out", default="products.xlsx", help="Файл результата (по умолчанию products.xlsx)")
    ap.add_argument("--csv", action="store_true", help="Дополнительно сохранить CSV рядом с Excel")
    ap.add_argument("--concurrency", type=int, default=10, help="Одновременных запросов (по умолчанию 10)")
    ap.add_argument("--delay", type=float, default=0.0, help="Пауза после каждого запроса, секунд")
    ap.add_argument("--url", default=DEFAULT_START_URL, help="Стартовая страница каталога")
    return ap


async def run(args: argparse.Namespace) -> int:
    started = time.monotonic()
    categories = [c.strip() for c in args.categories.split(",")] if args.categories else None
    out = Path(args.out)
    # Создаём папку до парсинга, а не после — чтобы не потерять результат долгой работы
    out.parent.mkdir(parents=True, exist_ok=True)

    def progress(done: int, total: int) -> None:
        if done == total or done % 50 == 0:
            print(f"\r  товаров: {done}/{total}", end="" if done < total else "\n", flush=True)

    async with Fetcher(concurrency=args.concurrency, delay=args.delay) as fetcher:
        result = await scrape(fetcher, args.url, categories, args.limit, on_progress=progress)

    seconds = time.monotonic() - started
    to_excel(result.products, out, source=args.url, failed=len(result.failed), seconds=seconds)
    print(f"Готово: {len(result.products)} товаров за {seconds:.1f} с → {out.resolve()}")
    if args.csv:
        to_csv(result.products, out.with_suffix(".csv"))
        print(f"CSV: {out.with_suffix('.csv').resolve()}")
    if result.failed:
        print(f"Не удалось загрузить: {len(result.failed)} (подробности в логе выше)")
    return 1 if result.failed and not result.products else 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    raise SystemExit(asyncio.run(run(build_args().parse_args())))


if __name__ == "__main__":
    main()
