"""Documentation collector — fetches official docs from software products."""
from typing import Optional, Dict, Any
from .base import BaseCollector, RawContent, CollectionResult
from .web_collector import WebCollector


class DocsCollector(BaseCollector):
    """Collects official documentation pages. Extends WebCollector with doc-specific logic."""
    source_type = "docs"

    def __init__(self):
        self.web = WebCollector()

    def fetch(self, url: str) -> Optional[RawContent]:
        """Fetch a documentation page."""
        content = self.web.fetch(url)
        if content:
            content.source_type = "docs"
        return content

    def search(self, query: str, filters: Dict[str, Any] = None,
               max_results: int = 10) -> CollectionResult:
        result = CollectionResult()
        result.errors.append(
            "Docs collector: use fetch() with specific documentation URLs."
        )
        return result

    def fetch_sitemap(self, sitemap_url: str, max_pages: int = 50) -> CollectionResult:
        """Fetch multiple doc pages from a sitemap XML."""
        result = CollectionResult()
        try:
            import httpx
            resp = httpx.get(sitemap_url, timeout=15)
            if resp.status_code != 200:
                result.errors.append(f"Failed to fetch sitemap: {resp.status_code}")
                return result

            import re
            urls = re.findall(r'<loc>(.*?)</loc>', resp.text)[:max_pages]

            for url in urls:
                content = self.fetch(url)
                if content and self.validate_content(content):
                    result.items.append(content)

            result.total_found = len(result.items)
        except Exception as e:
            result.errors.append(str(e))
        return result
