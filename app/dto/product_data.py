from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class ProductData:
    """Məhsul datası"""

    title: Optional[str] = None
    price: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    images: List[str] = None
    categories: List[str] = None
    url: Optional[str] = None
    scraped_at: Optional[str] = None

    def __post_init__(self):
        if self.images is None:
            self.images = []
        if self.categories is None:
            self.categories = []
        if self.scraped_at is None:
            self.scraped_at = datetime.now().isoformat()
