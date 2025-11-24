import logging
import os
from threading import Lock

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class WebDriverService:
    """WebDriver yaratma və idarəetmə"""

    def __init__(self, config):
        self.config = config
        self.driver_lock = Lock()

    def create_driver(self) -> webdriver.Chrome:
        """Yeni Chrome driver yarat"""
        options = Options()

        if self.config.headless:
            options.add_argument("--headless")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Səssiz rejim (logları azaltmaq üçün)
        options.add_argument("--log-level=3")

        try:
            # Driveri install et
            driver_path = ChromeDriverManager().install()

            # YENİ HİSSƏ: Əgər qaytarılan yol .exe deyilsə, düzəlt
            if not driver_path.endswith(".exe"):
                # Bəzən folder yolunu qaytarır, exe-ni tapmalıyıq
                directory = os.path.dirname(driver_path)
                potential_exe = os.path.join(directory, "chromedriver.exe")
                if os.path.exists(potential_exe):
                    driver_path = potential_exe

            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=options)
            return driver

        except Exception as e:
            logging.error(f"WebDriver yaradıla bilmədi: {str(e)}")
            raise e
