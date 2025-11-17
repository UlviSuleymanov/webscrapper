import logging
import time
from datetime import datetime
from typing import Callable, List, Optional

from app.config import ScraperConfig
from app.dto import ProductData
from app.formatters import OutputFormatter
from app.repositories import DatabaseRepository, FileRepository
from app.services import ScraperService, WebDriverService


class WordPressScraper:
    """Ana scraper class"""

    def __init__(self, config: ScraperConfig):
        self.config = config

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()],
        )

        # Initialize services və repositories
        self.file_repository = FileRepository(config.output_dir)
        self.database_repository = DatabaseRepository(config.database)
        self.webdriver_service = WebDriverService(config)
        self.scraper_service = ScraperService(
            config, self.webdriver_service, self.file_repository
        )
        self.output_formatter = OutputFormatter()

    def run(
        self,
        output_format: str = "json",
        save_to_db: bool = True,
        custom_formatter: Optional[Callable] = None,
    ) -> List[ProductData]:
        """Scraper-i işə sal"""
        start_time = time.time()

        logging.info("=" * 60)
        logging.info("WordPress Product Scraper başladı")
        logging.info(f"Base URL: {self.config.base_url}")
        logging.info(f"Max threads: {self.config.max_threads}")
        logging.info(
            f"Database: {'Aktiv' if self.config.database.enabled and save_to_db else 'Deaktiv'}"
        )
        logging.info("=" * 60)

        products = self.scraper_service.scrape_all()

        if not products:
            logging.warning("Heç bir məhsul scrape edilmədi!")
            return []

        # Database-ə saxla
        if self.config.database.enabled and save_to_db:
            logging.info("Database-ə saxlanır...")
            saved_count = self.database_repository.save_products_batch(products)
            logging.info(f"Database-ə {saved_count} məhsul saxlanıldı")

        # File-a saxla
        if output_format != "none":
            # Format və saxla
            if custom_formatter:
                formatted_data = self.output_formatter.apply_custom_format(
                    products, custom_formatter
                )
            else:
                formatted_data = self.output_formatter.to_dict_list(products)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if output_format == "json":
                self.file_repository.save_json(
                    formatted_data, f"products_{timestamp}.json"
                )
            elif output_format == "csv":
                self.file_repository.save_csv(
                    formatted_data, f"products_{timestamp}.csv"
                )
            elif output_format == "both":
                self.file_repository.save_json(
                    formatted_data, f"products_{timestamp}.json"
                )
                self.file_repository.save_csv(
                    formatted_data, f"products_{timestamp}.csv"
                )

        elapsed_time = time.time() - start_time

        logging.info("=" * 60)
        logging.info(f"Scraping tamamlandı!")
        logging.info(f"Cəmi məhsul: {len(products)}")
        logging.info(f"Vaxt: {elapsed_time:.2f} saniyə")
        logging.info("=" * 60)

        return products
