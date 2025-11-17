from dataclasses import asdict
from typing import Any, Callable, Dict, List

from app.dto import ProductData


class OutputFormatter:
    """Output formatlaşdırma"""

    @staticmethod
    def to_dict_list(products: List[ProductData]) -> List[Dict[str, Any]]:
        """ProductData-nı dict list-ə çevir"""
        return [asdict(product) for product in products]

    @staticmethod
    def apply_custom_format(
        products: List[ProductData], formatter: Callable[[ProductData], Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Custom formatter tətbiq et"""
        return [formatter(product) for product in products]
