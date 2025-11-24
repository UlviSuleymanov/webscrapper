import argparse
import io
import sys
from pathlib import Path

from app.config import ScraperConfig
from app.dto import ProductData
from app.scraper import WordPressScraper


def custom_formatter_example(product: ProductData) -> dict:
    """Custom format nümunəsi - Senior dev yanaşması: DTO-dan istədiyini al"""
    return {
        "name": product.title,
        "sku_code": product.sku,
        "main_price": product.price,
        "source_url": product.url,
        # İstəyə görə custom logic
        "has_images": len(product.images) > 0,
    }


def main():
    parser = argparse.ArgumentParser(description="WordPress Product Scraper (Selenium)")

    # Config Path
    parser.add_argument(
        "--config", type=str, default="config.json", help="Config faylı"
    )

    # Operation Modes (Mutually Exclusive Group)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--db-only", action="store_true", help="Yalnız Database-ə yaz (Fayl yox)"
    )
    group.add_argument(
        "--no-db", action="store_true", help="Database-ə yazma (Yalnız Fayl)"
    )

    # Output Formats
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "csv", "both", "none"],
        default="both",
        help="Fayl formatı",
    )

    # Custom Logic
    parser.add_argument(
        "--custom-format", action="store_true", help="Custom output formatter işlət"
    )

    args = parser.parse_args()

    # 1. Load Configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"XƏTA: Config faylı tapılmadı: {config_path}")
        print("Example: cp config.json.example config.json")
        sys.exit(1)

    try:
        config = ScraperConfig.from_json(str(config_path))
    except Exception as e:
        print(f"CRITICAL: Config parse xətası: {e}")
        sys.exit(1)

    # 2. Determine Flags based on CLI Arguments
    save_db = config.database.enabled
    save_json = False
    save_csv = False

    # DB Logic override
    if args.db_only:
        save_db = True
        config.override_settings(db_enabled=True)
        # db-only seçilibsə format none olur avtomatik
        args.format = "none"
    elif args.no_db:
        save_db = False
        config.override_settings(db_enabled=False)

    # File Format Logic
    if args.format != "none" and not args.db_only:
        if args.format == "json":
            save_json = True
        elif args.format == "csv":
            save_csv = True
        elif args.format == "both":
            save_json = True
            save_csv = True

    # 3. Initialize & Run
    try:
        scraper = WordPressScraper(config)

        products = scraper.run(
            save_json=save_json,
            save_csv=save_csv,
            save_db=save_db,
            custom_formatter=custom_formatter_example if args.custom_format else None,
        )

        if not products:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nScraping dayandırıldı (User Interrupt).")
        sys.exit(0)
    except Exception as e:
        print(f"\n gözlənilməz xəta: {e}")
        # Log-a baxmaq lazımdır
        sys.exit(1)


if __name__ == "__main__":
    main()
