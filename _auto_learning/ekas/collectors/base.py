"""Base classes for all EKAS collectors."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod


@dataclass
class RawContent:
    """Universal structure for collected content from any source."""
    source_type: str               # youtube, docs, manual, github, web
    source_url: str
    title: str
    source_id: str = ""            # platform-specific ID
    author: str = ""
    author_channel: str = ""
    published_at: str = ""
    raw_text: str = ""
    language: str = "pt-BR"
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CollectionResult:
    """Result of a collection operation."""
    items: List[RawContent] = field(default_factory=list)
    total_found: int = 0
    errors: List[str] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def success(self) -> bool:
        return len(self.items) > 0 or (self.total_found == 0 and not self.errors)


class BaseCollector(ABC):
    """Abstract base for all collectors."""
    source_type: str = "unknown"

    @abstractmethod
    def search(self, query: str, filters: Dict[str, Any] = None,
               max_results: int = 10) -> CollectionResult:
        """Search for content matching query and filters."""
        ...

    @abstractmethod
    def fetch(self, url_or_id: str) -> Optional[RawContent]:
        """Fetch a single piece of content by URL or ID."""
        ...

    def fetch_batch(self, urls: List[str]) -> CollectionResult:
        """Fetch multiple items. Default: iterate fetch()."""
        result = CollectionResult()
        for url in urls:
            try:
                item = self.fetch(url)
                if item:
                    result.items.append(item)
            except Exception as e:
                result.errors.append(f"{url}: {e}")
        result.total_found = len(result.items)
        return result

    def validate_content(self, content: RawContent) -> bool:
        """Check if content is valid and worth processing."""
        if not content.title or not content.raw_text:
            return False
        if len(content.raw_text.strip()) < 50:
            return False
        return True
