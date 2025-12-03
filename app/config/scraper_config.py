import json
from dataclasses import dataclass, field
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
class LoginConfig:
    """Login Konfiqurasiyası"""

    enabled: bool = False
    url: str = ""
    username: str = ""
    password: str = ""
    selectors: Dict[str, str] = field(
        default_factory=lambda: {
            "username": "#username",
            "password": "#password",
            "submit": "button[name='login']",
        }
    )


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

    # Test üçün limit
    test_mode: bool = False
    test_limit: int = 10

    # Scrape ediləcək field-lər
    fields: List[str] = None

    # CSS selektorlar
    selectors: Dict[str, str] = None

    # Database konfiqurasiyası
    database: DatabaseConfig = None

    # Login konfiqurasiyası
    login: LoginConfig = None

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

        if self.login is None:
            self.login = LoginConfig()

    @classmethod
    def from_json(cls, filepath: str) -> "ScraperConfig":
        """JSON faylından konfiqurasiya oxu"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Database config ayrıca parse et
        db_data = data.pop("database", {})
        db_config = DatabaseConfig(**db_data) if db_data else DatabaseConfig()

        # Login config ayrıca parse et
        login_data = data.pop("login", {})
        login_config = LoginConfig(**login_data) if login_data else LoginConfig()

        config = cls(**data)
        config.database = db_config
        config.login = login_config

        return config

    def override_settings(
        self,
        db_enabled: Optional[bool] = None,
        output_format: str = "both",
        test_mode: Optional[bool] = None,
        test_limit: Optional[int] = None,
    ):
        """CLI arqumentlərinə əsasən ayarları yenilə"""
        if db_enabled is not None:
            self.database.enabled = db_enabled

        if test_mode is not None:
            self.test_mode = test_mode

        if test_limit is not None:
            self.test_limit = test_limit
