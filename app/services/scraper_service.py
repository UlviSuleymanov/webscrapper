import logging
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from app.dto import ProductData


class ScraperService:
    def __init__(self, config, webdriver_service, file_repository):
        self.config = config
        self.webdriver_service = webdriver_service
        self.file_repository = file_repository

        # Locks for thread safety
        self.products_lock = Lock()
        self.counter_lock = Lock()

        self.scraped_products: List[ProductData] = []
        self.session_cookies: List[Dict] = []
        self.global_counter = 0

    def _get_next_number(self) -> int:
        """Thread-safe counter for folder numbering (1, 2, 3...)"""
        with self.counter_lock:
            self.global_counter += 1
            return self.global_counter

    def _sanitize_filename(self, name: str) -> str:
        """Clean string for folder naming"""
        if not name:
            return "product"
        # Azerbaijani char map
        name = (
            name.replace("Ə", "E").replace("ə", "e").replace("İ", "I").replace("ı", "i")
        )
        name = (
            name.replace("Ö", "O").replace("ö", "o").replace("Ü", "U").replace("ü", "u")
        )
        name = (
            name.replace("Ş", "S").replace("ş", "s").replace("Ç", "C").replace("ç", "c")
        )
        name = name.replace("Ğ", "G").replace("ğ", "g")
        # Remove special chars
        name = re.sub(r"[^a-zA-Z0-9\s_-]", "", name)
        # Underscores instead of spaces
        return re.sub(r"\s+", "_", name).strip().upper()

    def _perform_login(self, driver: webdriver.Chrome) -> bool:
        if not self.config.login.enabled:
            return True
        try:
            driver.get(self.config.login.url)
            wait = WebDriverWait(driver, 15)
            wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, self.config.login.selectors["username"])
                )
            ).send_keys(self.config.login.username)
            driver.find_element(
                By.CSS_SELECTOR, self.config.login.selectors["password"]
            ).send_keys(self.config.login.password)
            driver.execute_script(
                "arguments[0].click();",
                driver.find_element(
                    By.CSS_SELECTOR, self.config.login.selectors["submit"]
                ),
            )
            time.sleep(5)
            self.session_cookies = driver.get_cookies()
            return True
        except Exception as e:
            logging.error(f"Login Error: {e}")
            return False

    def _inject_cookies(self, driver: webdriver.Chrome):
        if not self.session_cookies:
            return
        try:
            driver.get(self.config.base_url)
            for cookie in self.session_cookies:
                driver.add_cookie(cookie)
            driver.refresh()
        except:
            pass

    def _parse_spec_table(self, driver: webdriver.Chrome, product: ProductData):
        """
        Scrapes table.pn-spec-list for ALL attributes.
        Fills: oem, sku (if missing), and attributes dict.
        """
        try:
            # Look for table rows
            rows = driver.find_elements(By.CSS_SELECTOR, "table.pn-spec-list tr")

            # If empty, try clicking 'Description' tab
            if not rows:
                try:
                    desc_tab = driver.find_element(
                        By.CSS_SELECTOR, "li.description_tab a"
                    )
                    driver.execute_script("arguments[0].click();", desc_tab)
                    time.sleep(0.5)
                    rows = driver.find_elements(
                        By.CSS_SELECTOR, "table.pn-spec-list tr"
                    )
                except:
                    pass

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) == 2:
                    raw_key = cols[0].text.strip().replace(":", "")
                    value = cols[1].text.strip()

                    if not value or not raw_key:
                        continue

                    key_lower = raw_key.lower()

                    if "oem" in key_lower:
                        product.oem = value
                    elif "sku" in key_lower and not product.sku:
                        product.sku = value
                    else:
                        # Capture "Ölçüləri", "Digər adı", etc.
                        product.attributes[raw_key] = value
        except Exception:
            pass

    def scrape_product(
        self, url: str, driver: webdriver.Chrome
    ) -> Optional[ProductData]:
        try:
            driver.get(url)
            # Reduced sleep to 1s to save time, increase if internet is slow
            time.sleep(1)
            wait = WebDriverWait(driver, self.config.timeout)

            product = ProductData(url=url)
            product.scraped_at = datetime.now().isoformat()

            # --- WP ID (For DB) ---
            try:
                product.wp_id = (
                    driver.find_element(By.CSS_SELECTOR, "div.product.type-product")
                    .get_attribute("id")
                    .replace("product-", "")
                )
            except:
                product.wp_id = str(self._get_next_number())

            # --- Basic Fields ---
            try:
                product.title = wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, self.config.selectors["title"])
                    )
                ).text.strip()
            except:
                pass

            try:
                product.price = driver.find_element(
                    By.CSS_SELECTOR, self.config.selectors["price"]
                ).text.strip()
            except:
                pass

            try:
                product.description = driver.find_element(
                    By.CSS_SELECTOR, self.config.selectors["description"]
                ).text.strip()
            except:
                pass

            # --- SKU ---
            try:
                sku_text = driver.find_element(
                    By.CSS_SELECTOR, ".sku_wrapper .sku"
                ).text.strip()
                if sku_text:
                    product.sku = sku_text
            except:
                pass

            # --- CRITICAL: Table Parser ---
            self._parse_spec_table(driver, product)

            # --- Categories & Tags ---
            try:
                product.categories = [
                    e.text.strip()
                    for e in driver.find_elements(By.CSS_SELECTOR, ".posted_in a")
                ]
            except:
                pass
            try:
                product.tags = [
                    e.text.strip()
                    for e in driver.find_elements(By.CSS_SELECTOR, ".tagged_as a")
                ]
            except:
                pass

            # --- Images (Strict: Main Gallery Only) ---
            try:
                # Strictly select the gallery div
                gallery = driver.find_element(
                    By.CSS_SELECTOR, ".woocommerce-product-gallery"
                )
                img_elems = gallery.find_elements(By.TAG_NAME, "img")

                image_urls = []
                seen = set()
                for img in img_elems:
                    src = img.get_attribute("data-large_image") or img.get_attribute(
                        "src"
                    )
                    # Filter out tiny icons or unrelated images
                    if src and src not in seen and "http" in src:
                        image_urls.append(src)
                        seen.add(src)

                # --- FOLDER NAMING: NUMBER + TITLE ---
                counter = self._get_next_number()
                safe_title = self._sanitize_filename(product.title)
                folder_name = f"{counter}_{safe_title}"

                if self.config.download_images and image_urls:
                    local_paths = []
                    base_path = f"images/{folder_name}"
                    for i, u in enumerate(image_urls):
                        ext = u.split("?")[0].split(".")[-1]
                        if len(ext) > 4:
                            ext = "jpg"

                        fname = f"{i + 1}.{ext}"
                        path = self.file_repository.download_image(u, fname, base_path)
                        if path:
                            local_paths.append(path)
                    product.images = local_paths
                else:
                    product.images = image_urls
            except:
                pass

            logging.info(f"Scraped: {product.title} | ID: {product.wp_id}")
            return product

        except Exception as e:
            logging.error(f"Error {url}: {e}")
            return None

    def scrape_product_worker(self, url: str):
        """Worker with strict resource cleanup"""
        driver = None
        try:
            # Create driver
            driver = self.webdriver_service.create_driver()

            if self.config.login.enabled:
                self._inject_cookies(driver)

            p = self.scrape_product(url, driver)

            if p:
                with self.products_lock:
                    self.scraped_products.append(p)
            return p

        except WebDriverException as e:
            logging.error(
                f"WebDriver crashed for {url}. System might be overloaded. Error: {e}"
            )
            # If driver failed to create, wait a bit before letting thread continue
            time.sleep(5)
            return None
        except Exception as e:
            logging.error(f"Unexpected error in worker: {e}")
            return None
        finally:
            # CRITICAL CLEANUP: Ensure process dies
            if driver:
                try:
                    driver.close()  # Close tab
                except:
                    pass
                try:
                    driver.quit()  # Kill process
                except:
                    pass

            # Small pause to let OS reclaim RAM/CPU
            time.sleep(1)

    def get_product_links(self, driver):
        links = []
        curr = self.config.base_url
        while curr:
            try:
                driver.get(curr)
                time.sleep(self.config.page_load_delay)
                els = driver.find_elements(
                    By.CSS_SELECTOR, self.config.selectors["product_links"]
                )
                links.extend([e.get_attribute("href") for e in els])

                logging.info(f"Links found so far: {len(links)}")

                try:
                    curr = driver.find_element(
                        By.CSS_SELECTOR, self.config.selectors["pagination_next"]
                    ).get_attribute("href")
                except:
                    break
            except Exception as e:
                logging.error(f"Crawling stopped/error: {e}")
                break
        return list(set(links))

    def scrape_all(self):
        logging.info("Starting Scraper...")

        # 1. Get Links (Single Driver)
        driver = self.webdriver_service.create_driver()
        try:
            if self.config.login.enabled:
                self._perform_login(driver)
            links = self.get_product_links(driver)
        finally:
            driver.quit()

        if not links:
            logging.warning("No links found.")
            return []

        logging.info(f"Found {len(links)} products. Starting threads...")

        # 2. Process with Limit
        # ThreadPoolExecutor ensures we never have more than max_threads active
        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            futures = {executor.submit(self.scrape_product_worker, u): u for u in links}

            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 10 == 0:
                    logging.info(f"Progress: {completed}/{len(links)}")

        return self.scraped_products
