import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import List, Optional

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from app.dto import ProductData


class ScraperService:
    """Scraping əməliyyatları"""

    def __init__(self, config, webdriver_service, file_repository):
        self.config = config
        self.webdriver_service = webdriver_service
        self.file_repository = file_repository
        self.products_lock = Lock()
        self.scraped_products: List[ProductData] = []

    def get_product_links(self, driver: webdriver.Chrome) -> List[str]:
        """Bütün məhsul linklərini topla"""
        all_links = []
        current_url = self.config.base_url

        while current_url:
            try:
                driver.get(current_url)
                time.sleep(self.config.page_load_delay)

                # Məhsul linklərini tap
                elements = driver.find_elements(
                    By.CSS_SELECTOR, self.config.selectors["product_links"]
                )

                page_links = [elem.get_attribute("href") for elem in elements]
                all_links.extend(page_links)

                logging.info(
                    f"Səhifədə {len(page_links)} məhsul tapıldı. Cəmi: {len(all_links)}"
                )

                # Növbəti səhifəyə keç
                try:
                    next_button = driver.find_element(
                        By.CSS_SELECTOR, self.config.selectors["pagination_next"]
                    )
                    current_url = next_button.get_attribute("href")
                except NoSuchElementException:
                    break

            except Exception as e:
                logging.error(f"Link toplama xətası: {str(e)}")
                break

        return list(set(all_links))

    def scrape_product(
        self, url: str, driver: webdriver.Chrome
    ) -> Optional[ProductData]:
        """Tək məhsulu scrape et"""
        try:
            driver.get(url)
            time.sleep(self.config.page_load_delay)

            product = ProductData(url=url)
            wait = WebDriverWait(driver, self.config.timeout)

            # Title
            if "title" in self.config.fields:
                try:
                    elem = wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, self.config.selectors["title"])
                        )
                    )
                    product.title = elem.text.strip()
                except TimeoutException:
                    pass

            # Price
            if "price" in self.config.fields:
                try:
                    elem = driver.find_element(
                        By.CSS_SELECTOR, self.config.selectors["price"]
                    )
                    product.price = elem.text.strip()
                except NoSuchElementException:
                    pass

            # Description
            if "description" in self.config.fields:
                try:
                    elem = driver.find_element(
                        By.CSS_SELECTOR, self.config.selectors["description"]
                    )
                    product.description = elem.text.strip()
                except NoSuchElementException:
                    pass

            # SKU
            if "sku" in self.config.fields:
                try:
                    elem = driver.find_element(
                        By.CSS_SELECTOR, self.config.selectors["sku"]
                    )
                    sku_text = elem.text.strip()
                    # "SKU: 03128" formatından yalnız nömrəni çıxart
                    if "SKU:" in sku_text:
                        product.sku = sku_text.replace("SKU:", "").strip()
                    else:
                        product.sku = sku_text
                except NoSuchElementException:
                    pass

            # OEM Nömrə
            if "oem" in self.config.fields and "oem" in self.config.selectors:
                try:
                    elem = driver.find_element(
                        By.CSS_SELECTOR, self.config.selectors["oem"]
                    )
                    oem_text = elem.text.strip()
                    # "OEM Nömrə: 55250-2B000" formatından nömrəni çıxart
                    if "OEM" in oem_text or "Nömrə" in oem_text:
                        product.oem = oem_text.split(":")[-1].strip()
                    else:
                        product.oem = oem_text
                except NoSuchElementException:
                    pass

            # Images
            if "images" in self.config.fields:
                try:
                    elems = driver.find_elements(
                        By.CSS_SELECTOR, self.config.selectors["images"]
                    )
                    product.images = [
                        elem.get_attribute("src")
                        for elem in elems
                        if elem.get_attribute("src")
                    ]
                    # Dublikatları sil
                    product.images = list(dict.fromkeys(product.images))

                    # Şəkilləri yüklə
                    if self.config.download_images and product.images:
                        for idx, img_url in enumerate(product.images):
                            # Fayl adını təmizlə
                            safe_sku = (
                                (product.sku or "product")
                                .replace("/", "-")
                                .replace("\\", "-")
                            )
                            filename = f"{safe_sku}_{idx}.jpg"
                            self.file_repository.download_image(
                                img_url, filename, self.config.images_dir
                            )
                except NoSuchElementException:
                    pass

            # Categories
            if "categories" in self.config.fields:
                try:
                    elems = driver.find_elements(
                        By.CSS_SELECTOR, self.config.selectors["categories"]
                    )
                    product.categories = [elem.text.strip() for elem in elems]
                except NoSuchElementException:
                    pass

            logging.info(f"Scrape edildi: {product.title or url}")
            return product

        except Exception as e:
            logging.error(f"Məhsul scrape xətası {url}: {str(e)}")
            return None

    def scrape_product_worker(self, url: str) -> Optional[ProductData]:
        """Worker thread üçün məhsul scrape et"""
        driver = self.webdriver_service.create_driver()

        try:
            product = self.scrape_product(url, driver)

            if product:
                with self.products_lock:
                    self.scraped_products.append(product)

            return product
        finally:
            driver.quit()

    def scrape_all(self) -> List[ProductData]:
        """Bütün məhsulları scrape et (multithread)"""
        # Əvvəlcə bütün linkləri topla
        logging.info("Məhsul linkləri toplanır...")
        main_driver = self.webdriver_service.create_driver()

        try:
            product_links = self.get_product_links(main_driver)
            logging.info(f"Cəmi {len(product_links)} məhsul tapıldı")
        finally:
            main_driver.quit()

        if not product_links:
            logging.warning("Heç bir məhsul linki tapılmadı!")
            return []

        # Multithread scraping
        logging.info(f"Scraping başladılır ({self.config.max_threads} thread)...")

        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            futures = {
                executor.submit(self.scrape_product_worker, url): url
                for url in product_links
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1
                logging.info(f"Tamamlandı: {completed}/{len(product_links)}")

        return self.scraped_products
