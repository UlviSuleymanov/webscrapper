import argparse
import sys
from pathlib import Path

from app.config import ScraperConfig
from app.dto import ProductData
from app.scraper import WordPressScraper


def custom_formatter_example(product: ProductData) -> dict:
    """Custom output format nümunəsi"""
    return {
        "ad": product.title,
        "qiymet": product.price,
        "kod": product.sku,
        "link": product.url,
        "sekil_sayi": len(product.images),
        "kateqoriyalar": ", ".join(product.categories),
    }


def main():
    parser = argparse.ArgumentParser(description="WordPress Product Scraper")
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Config faylının yolu (default: config.json)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "csv", "both"],
        default="both",
        help="Output formatı (default: both)",
    )
    parser.add_argument(
        "--custom-format", action="store_true", help="Custom formatter istifadə et"
    )

    args = parser.parse_args()

    # Config yoxla
    if not Path(args.config).exists():
        print(f"XƏTA: {args.config} faylı tapılmadı!")
        print("config.json.example faylını config.json olaraq kopyala və düzəlt.")
        sys.exit(1)

    # Config yüklə
    try:
        config = ScraperConfig.from_json(args.config)
    except Exception as e:
        print(f"XƏTA: Config faylı oxuna bilmədi: {str(e)}")
        sys.exit(1)

    # Scraper yarat və işə sal
    scraper = WordPressScraper(config)

    if args.custom_format:
        products = scraper.run(
            output_format=args.format, custom_formatter=custom_formatter_example
        )
    else:
        products = scraper.run(output_format=args.format)

    if products:
        print(f"\\n✓ Uğurla tamamlandı! {len(products)} məhsul scrape edildi.")
    else:
        print("\\n✗ Heç bir məhsul scrape edilmədi.")
        sys.exit(1)


if __name__ == "__main__":
    main()
