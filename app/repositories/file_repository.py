import csv
import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import requests


class FileRepository:
    """File əməliyyatları üçün repository"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.file_lock = Lock()

    def save_json(self, data: List[Dict[str, Any]], filename: str) -> None:
        """JSON formatda saxla"""
        filepath = self.output_dir / filename

        with self.file_lock:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        logging.info(f"JSON saxlanıldı: {filepath}")

    def save_csv(self, data: List[Dict[str, Any]], filename: str) -> None:
        """CSV formatda saxla"""
        if not data:
            logging.warning("CSV üçün data yoxdur")
            return

        filepath = self.output_dir / filename

        with self.file_lock:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)

        logging.info(f"CSV saxlanıldı: {filepath}")

    def download_image(
        self, url: str, filename: str, sub_folder: str = ""
    ) -> Optional[str]:
        """
        Şəkil yüklə və tam lokal yolu qaytar (Absolute Path).
        Məsələn: D:/projects/web/images/sku_123/img.jpg
        """
        try:
            # Əsas şəkil qovluğu + Məhsul qovluğu
            target_dir = self.output_dir / sub_folder
            target_dir.mkdir(parents=True, exist_ok=True)

            response = requests.get(url, timeout=10, stream=True)
            response.raise_for_status()

            filepath = target_dir / filename

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Absolute path qaytarırıq (OS-dan asılı olaraq tam yol)
            return str(filepath.resolve())

        except Exception as e:
            logging.error(f"Şəkil yüklənərkən xəta: {url} - {str(e)}")
            return None
