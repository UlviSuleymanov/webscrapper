import json
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class DatabaseConfig:
    """Database konfiqurasiyası"""

    enabled: bool = False
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "scraped_products"
    table_prefix: str = "wp_"


@dataclass
class ScraperConfig:
    """Scraper konfiqurasiyası"""

    base_url: str
    max_threads: int = 5
    timeout: int = 10
    headless: bool = True
    page_load_delay: int = 2
    output_dir: str = "output"
    images_dir: str = "images"
    download_images: bool = True

    # Scrape ediləcək field-lər
    fields: List[str] = None

    # CSS selektorlar
    selectors: Dict[str, str] = None

    # Database konfiqurasiyası
    database: DatabaseConfig = None

    def __post_init__(self):
        if self.fields is None:
            self.fields = [
                "title",
                "price",
                "description",
                "sku",
                "images",
                "categories",
                "url",
            ]

        if self.selectors is None:
            # Default WordPress WooCommerce selektorlar
            self.selectors = {
                "product_links": ".products .product a.woocommerce-LoopProduct-link",
                "title": "h1.product_title",
                "price": ".price .amount",
                "description": ".woocommerce-product-details__short-description",
                "sku": ".sku",
                "images": ".woocommerce-product-gallery__image img",
                "categories": ".posted_in a",
                "pagination_next": ".next.page-numbers",
            }

        if self.database is None:
            self.database = DatabaseConfig()

    @classmethod
    def from_json(cls, filepath: str) -> "ScraperConfig":
        """JSON faylından konfiqurasiya oxu"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Database config ayrıca parse et
        db_data = data.pop("database", {})
        db_config = DatabaseConfig(**db_data) if db_data else DatabaseConfig()

        config = cls(**data)
        config.database = db_config

        return config

    def to_json(self, filepath: str) -> None:
        """JSON faylına konfiqurasiya yaz"""
        data = {
            "base_url": self.base_url,
            "max_threads": self.max_threads,
            "timeout": self.timeout,
            "headless": self.headless,
            "page_load_delay": self.page_load_delay,
            "output_dir": self.output_dir,
            "images_dir": self.images_dir,
            "download_images": self.download_images,
            "fields": self.fields,
            "selectors": self.selectors,
            "database": {
                "enabled": self.database.enabled,
                "host": self.database.host,
                "port": self.database.port,
                "user": self.database.user,
                "password": self.database.password,
                "database": self.database.database,
                "table_prefix": self.database.table_prefix,
            },
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
