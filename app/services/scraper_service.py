import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from app.dto import ProductData


class ScraperService:
    def __init__(self, config, webdriver_service, file_repository):
        self.config = config
        self.webdriver_service = webdriver_service
        self.file_repository = file_repository
        self.products_lock = Lock()
        self.scraped_products: List[ProductData] = []

        # Store cookies here to share with workers
        self.session_cookies: List[Dict] = []

    def _sanitize_filename(self, name: str) -> str:
        """Qovluq və fayl adlarını OS üçün təhlükəsiz hala gətir"""
        if not name:
            return "unknown"
        # Yalnız hərf, rəqəm, tire və alt-xətt saxla
        name = re.sub(r'[\\/*?:"<>|]', "", name)
        return name.strip().replace(" ", "_")

    def _perform_login(self, driver: webdriver.Chrome) -> bool:
        """Log in and save cookies (With JS Force Click)"""
        if not self.config.login.enabled:
            return True

        logging.info(f"Login cəhdi: {self.config.login.url}")
        try:
            driver.get(self.config.login.url)
            wait = WebDriverWait(driver, 15)

            # 1. Username
            user_input = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, self.config.login.selectors["username"])
                )
            )
            user_input.clear()
            user_input.send_keys(self.config.login.username)
            time.sleep(1)

            # 2. Password
            pass_input = driver.find_element(
                By.CSS_SELECTOR, self.config.login.selectors["password"]
            )
            pass_input.clear()
            pass_input.send_keys(self.config.login.password)
            time.sleep(1)

            # 3. Submit Button (JS Force Click)
            submit_btn = driver.find_element(
                By.CSS_SELECTOR, self.config.login.selectors["submit"]
            )
            driver.execute_script("arguments[0].click();", submit_btn)

            # 4. Wait & Verify
            time.sleep(5)
            logging.info("Login sorğusu göndərildi. Cookie-lər götürülür...")
            self.session_cookies = driver.get_cookies()
            return True

        except Exception as e:
            logging.error(f"Login prosesində xəta: {str(e)}")
            return False

    def _inject_cookies(self, driver: webdriver.Chrome):
        """Inject saved cookies into a new driver instance"""
        if not self.session_cookies:
            return

        driver.get(self.config.base_url)
        for cookie in self.session_cookies:
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        driver.refresh()

    def scrape_product_worker(self, url: str) -> Optional[ProductData]:
        """Worker thread - Modified to support Login"""
        driver = self.webdriver_service.create_driver()
        try:
            if self.config.login.enabled:
                self._inject_cookies(driver)

            product = self.scrape_product(url, driver)

            if product:
                with self.products_lock:
                    self.scraped_products.append(product)
            return product
        finally:
            driver.quit()

    def scrape_all(self) -> List[ProductData]:
        logging.info("Driver başladılır...")
        main_driver = self.webdriver_service.create_driver()

        try:
            # 1. Login (Main Thread)
            if self.config.login.enabled:
                if not self._perform_login(main_driver):
                    logging.error("Login uğursuz oldu. Proses dayandırılır.")
                    return []

            # 2. Get Links (Authenticated)
            logging.info("Məhsul linkləri toplanır...")
            product_links = self.get_product_links(main_driver)
            logging.info(f"Cəmi {len(product_links)} məhsul tapıldı")

        finally:
            main_driver.quit()

        if not product_links:
            logging.warning("Heç bir məhsul linki tapılmadı!")
            return []

        # 3. Multithread Scraping
        logging.info(f"Scraping başladılır ({self.config.max_threads} thread)...")

        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            futures = {
                executor.submit(self.scrape_product_worker, url): url
                for url in product_links
            }

            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 5 == 0:
                    logging.info(f"Tamamlandı: {completed}/{len(product_links)}")

        return self.scraped_products

    def get_product_links(self, driver: webdriver.Chrome) -> List[str]:
        all_links = []
        current_url = self.config.base_url

        while current_url:
            try:
                driver.get(current_url)
                time.sleep(self.config.page_load_delay)

                elements = driver.find_elements(
                    By.CSS_SELECTOR, self.config.selectors["product_links"]
                )

                page_links = [elem.get_attribute("href") for elem in elements]
                all_links.extend(page_links)

                logging.info(
                    f"Səhifədə {len(page_links)} məhsul tapıldı. Cəmi: {len(all_links)}"
                )

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
                    if "OEM" in oem_text or "Nömrə" in oem_text:
                        product.oem = oem_text.split(":")[-1].strip()
                    else:
                        product.oem = oem_text
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

            # Images Logic (UPDATED)
            if "images" in self.config.fields:
                try:
                    elems = driver.find_elements(
                        By.CSS_SELECTOR, self.config.selectors["images"]
                    )
                    image_urls = [
                        elem.get_attribute("src")
                        for elem in elems
                        if elem.get_attribute("src")
                    ]
                    # URL Dublikatlarını sil
                    image_urls = list(dict.fromkeys(image_urls))

                    # Məhsul üçün unikal qovluq adı yarat (SKU və ya Title əsasında)
                    folder_identifier = (
                        product.sku
                        if product.sku
                        else (product.title or "unknown_product")
                    )
                    product_folder_name = self._sanitize_filename(folder_identifier)

                    # Şəkilləri yüklə və Lokal yolları yadda saxla
                    local_image_paths = []

                    if self.config.download_images and image_urls:
                        base_images_folder = "images"  # Standart ad
                        full_relative_path = (
                            f"{base_images_folder}/{product_folder_name}"
                        )

                        for idx, img_url in enumerate(image_urls):
                            ext = img_url.split(".")[-1].split("?")[
                                0
                            ]  # sadə extension almaq
                            if len(ext) > 4 or not ext:
                                ext = "jpg"

                            filename = f"{idx + 1}.{ext}"

                            absolute_path = self.file_repository.download_image(
                                img_url, filename, full_relative_path
                            )

                            if absolute_path:
                                local_image_paths.append(absolute_path)

                    product.images = (
                        local_image_paths if self.config.download_images else image_urls
                    )

                except NoSuchElementException:
                    pass

            logging.info(f"Scrape edildi: {product.title or url}")
            return product

        except Exception as e:
            logging.error(f"Məhsul scrape xətası {url}: {str(e)}")
            return None
