import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class ProductData:
    """Məhsul datası - Genişləndirilmiş versiya"""

    wp_id: Optional[str] = None  # WordPress unikal ID (Məs: 3785)
    title: Optional[str] = None
    price: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    oem: Optional[str] = None

    # Yeni sahələr
    tags: List[str] = field(default_factory=list)
    attributes: Dict[str, str] = field(
        default_factory=dict
    )  # Cədvəl məlumatları üçün (Ölçü, Model və s.)

    images: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    url: Optional[str] = None
    scraped_at: Optional[str] = None

    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now().isoformat()

    @property
    def attributes_json(self) -> str:
        """Verilənlər bazası üçün atributları JSON stringə çevirir"""
        return json.dumps(self.attributes, ensure_ascii=False)

    @property
    def tags_json(self) -> str:
        """Verilənlər bazası üçün teqləri JSON stringə çevirir"""
        return json.dumps(self.tags, ensure_ascii=False)
