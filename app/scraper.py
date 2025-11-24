import logging
import sys
import time
from datetime import datetime
from typing import Callable, List, Optional

from app.config import ScraperConfig
from app.dto import ProductData
from app.formatters import OutputFormatter
from app.repositories import DatabaseRepository, FileRepository
from app.services import ScraperService, WebDriverService


class WordPressScraper:
    """Ana scraper class - Orchestrator"""

    def __init__(self, config: ScraperConfig):
        self.config = config
        self._setup_logging()

        # Dependencies (Traditional injection)
        self.file_repository = FileRepository(config.output_dir)

        # Database repository-ni yalnız aktivdirsə initialize edirik
        self.database_repository = None
        if self.config.database.enabled:
            self.database_repository = DatabaseRepository(config.database)

        self.webdriver_service = WebDriverService(config)
        self.scraper_service = ScraperService(
            config, self.webdriver_service, self.file_repository
        )
        self.output_formatter = OutputFormatter()

    def _setup_logging(self):
        # Fayla yazarkən mütləq utf-8 istifadə edirik
        file_handler = logging.FileHandler("scraper.log", encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )

        # Ekrana yazarkən standart stdout axınını istifadə edirik
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )

        logging.basicConfig(
            level=logging.INFO,
            handlers=[file_handler, stream_handler],
        )

    def run(
        self,
        save_json: bool = True,
        save_csv: bool = True,
        save_db: bool = True,
        custom_formatter: Optional[Callable] = None,
    ) -> List[ProductData]:
        """
        Scraper-i işə sal.
        Nəyin harada saxlanacağına arqumentlər qərar verir.
        """
        start_time = time.time()
        self._log_start(save_json, save_csv, save_db)

        # 1. Scrape Execution
        products = self.scraper_service.scrape_all()

        if not products:
            logging.warning("Heç bir məhsul tapılmadı.")
            return []

        # 2. Database Saving
        if save_db and self.config.database.enabled and self.database_repository:
            logging.info("Database-ə yazılır...")
            saved_count = self.database_repository.save_products_batch(products)
            logging.info(f"Database nəticəsi: {saved_count}/{len(products)} sətir.")
        elif save_db and not self.config.database.enabled:
            logging.warning("DB yaddaşı istənildi, amma config-də DB deaktivdir.")

        # 3. File Saving
        if save_json or save_csv:
            self._save_files(products, save_json, save_csv, custom_formatter)

        self._log_end(len(products), start_time)
        return products

    def _save_files(
        self,
        products: List[ProductData],
        json_flag: bool,
        csv_flag: bool,
        formatter: Optional[Callable],
    ):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Format Data
        if formatter:
            data_to_save = self.output_formatter.apply_custom_format(
                products, formatter
            )
        else:
            data_to_save = self.output_formatter.to_dict_list(products)

        # Write JSON
        if json_flag:
            filename = f"products_{timestamp}.json"
            self.file_repository.save_json(data_to_save, filename)

        # Write CSV
        if csv_flag:
            filename = f"products_{timestamp}.csv"
            self.file_repository.save_csv(data_to_save, filename)

    def _log_start(self, json_f, csv_f, db_f):
        logging.info("=" * 60)
        logging.info("WordPress Product Scraper Başladı")
        logging.info(f"Targets -> DB: {db_f} | JSON: {json_f} | CSV: {csv_f}")
        logging.info("=" * 60)

    def _log_end(self, count, start_time):
        elapsed = time.time() - start_time
        logging.info("-" * 60)
        logging.info(f"Proses bitdi. Cəmi: {count} məhsul.")
        logging.info(f"Vaxt: {elapsed:.2f} saniyə")
        logging.info("=" * 60)
