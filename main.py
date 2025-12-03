import argparse
import signal
import sys
from pathlib import Path

from app.config import ScraperConfig
from app.dto import ProductData
from app.scraper import WordPressScraper

# Global scraper reference for signal handling
active_scraper = None


def signal_handler(sig, frame):
    """CTRL+C ilə dayandırma"""
    print("\n\n⚠️  Dayandırma sorğusu alındı (CTRL+C)...")
    print("Aktiv thread-lər tamamlanır, gözləyin...\n")

    if active_scraper:
        active_scraper.scraper_service.request_stop()
    else:
        sys.exit(0)


def custom_formatter_example(product: ProductData) -> dict:
    """Custom format nümunəsi - Senior dev yanaşması: DTO-dan istədiyini al"""
    return {
        "name": product.title,
        "sku_code": product.sku,
        "main_price": product.price,
        "source_url": product.url,
        "has_images": len(product.images) > 0,
    }


def main():
    global active_scraper

    # CTRL+C handler qur
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description="WordPress Product Scraper (Selenium)")

    # Config Path
    parser.add_argument(
        "--config", type=str, default="config.json", help="Config faylı"
    )

    # Test Mode
    parser.add_argument(
        "--test", action="store_true", help="Test rejimi (məhdud məhsul sayı)"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Test rejimində məhsul sayı (default: 10)"
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
        print(f"❌ XƏTA: Config faylı tapılmadı: {config_path}")
        print("Example: cp config.json.example config.json")
        sys.exit(1)

    try:
        config = ScraperConfig.from_json(str(config_path))
    except Exception as e:
        print(f"❌ CRITICAL: Config parse xətası: {e}")
        sys.exit(1)

    # 2. Determine Flags based on CLI Arguments
    save_db = config.database.enabled
    save_json = False
    save_csv = False

    # Test mode
    if args.test:
        config.override_settings(test_mode=True, test_limit=args.limit)
        print(f"\n🧪 TEST MODE: Yalnız {args.limit} məhsul scrape olunacaq\n")

    # DB Logic override
    if args.db_only:
        save_db = True
        config.override_settings(db_enabled=True)
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
        active_scraper = scraper

        print("\n" + "=" * 60)
        print("🚀 SCRAPER BAŞLADI")
        print("=" * 60)
        print(f"📌 Sayt: {config.base_url}")
        print(f"🧵 Thread sayı: {config.max_threads}")
        print(f"💾 Database: {'✅ Aktiv' if save_db else '❌ Deaktiv'}")
        print(f"📄 JSON: {'✅ Aktiv' if save_json else '❌ Deaktiv'}")
        print(f"📊 CSV: {'✅ Aktiv' if save_csv else '❌ Deaktiv'}")
        if config.test_mode:
            print(f"🧪 TEST MODE: {config.test_limit} məhsul limit")
        print("=" * 60)
        print("\n💡 Dayandırmaq üçün CTRL+C basın\n")

        products = scraper.run(
            save_json=save_json,
            save_csv=save_csv,
            save_db=save_db,
            custom_formatter=custom_formatter_example if args.custom_format else None,
        )

        if not products:
            print("\n⚠️  Heç bir məhsul scrape edilmədi.")
            sys.exit(1)

        print(f"\n✅ Uğurla tamamlandı: {len(products)} məhsul\n")

    except KeyboardInterrupt:
        print("\n\n⛔ Scraping dayandırıldı (User Interrupt).")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Gözlənilməz xəta: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
