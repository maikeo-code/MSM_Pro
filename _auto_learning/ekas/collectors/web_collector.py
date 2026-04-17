"""Web collector — extracts content from web articles, blogs, tutorials."""
import re
import time
from typing import Optional, Dict, Any, List
from .base import BaseCollector, RawContent, CollectionResult

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


class WebCollector(BaseCollector):
    source_type = "web"

    def __init__(self, user_agent: str = None):
        self.user_agent = user_agent or "EKAS/1.0 (Knowledge Acquisition Bot)"

    def _clean_html(self, html: str) -> str:
        """Extract readable text from HTML."""
        if not HAS_BS4:
            # Basic fallback: strip tags
            return re.sub(r'<[^>]+>', ' ', html).strip()

        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, nav, header, footer
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
            tag.decompose()

        # Try to find main content
        main = soup.find("main") or soup.find("article") or soup.find(class_=re.compile(r"content|post|article|entry"))
        if main:
            text = main.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def _extract_metadata(self, html: str, url: str) -> Dict[str, Any]:
        """Extract metadata from HTML meta tags."""
        if not HAS_BS4:
            return {}

        soup = BeautifulSoup(html, "html.parser")
        meta = {}

        # Open Graph
        for tag in soup.find_all("meta", attrs={"property": re.compile(r"^og:")}):
            key = tag.get("property", "").replace("og:", "")
            meta[f"og_{key}"] = tag.get("content", "")

        # Standard meta
        for name in ["description", "author", "keywords"]:
            tag = soup.find("meta", attrs={"name": name})
            if tag:
                meta[name] = tag.get("content", "")

        # Title
        title_tag = soup.find("title")
        if title_tag:
            meta["page_title"] = title_tag.string or ""

        # Published date
        for attr in ["article:published_time", "datePublished", "date"]:
            tag = soup.find("meta", attrs={"property": attr}) or soup.find("meta", attrs={"name": attr})
            if tag:
                meta["published_at"] = tag.get("content", "")
                break

        # Word count
        text = self._clean_html(html)
        meta["word_count"] = len(text.split())

        return meta

    def fetch(self, url: str) -> Optional[RawContent]:
        """Fetch and extract content from a web URL."""
        if not HAS_HTTPX:
            return None

        try:
            resp = httpx.get(url, headers={"User-Agent": self.user_agent},
                           follow_redirects=True, timeout=15)
            if resp.status_code != 200:
                return None

            html = resp.text
            text = self._clean_html(html)
            meta = self._extract_metadata(html, url)

            if len(text.strip()) < 100:
                return None

            title = meta.get("og_title") or meta.get("page_title") or url
            author = meta.get("author") or meta.get("og_site_name") or ""
            published = meta.get("published_at") or meta.get("og_article:published_time") or ""

            return RawContent(
                source_type="web",
                source_url=url,
                title=title,
                author=author,
                published_at=published,
                raw_text=text,
                metadata=meta,
                tags=[k for k in (meta.get("keywords") or "").split(",") if k.strip()],
            )
        except Exception:
            return None

    def search(self, query: str, filters: Dict[str, Any] = None,
               max_results: int = 10) -> CollectionResult:
        """Search is not directly supported for web — use specific URLs or a search engine API."""
        result = CollectionResult()
        result.errors.append(
            "Web collector does not support search directly. "
            "Use fetch() with specific URLs or integrate a search API."
        )
        return result
