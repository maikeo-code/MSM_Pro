"""GitHub collector — extracts README, docs, and metadata from public repos."""
import re
from typing import Optional, Dict, Any, List
from .base import BaseCollector, RawContent, CollectionResult

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class GitHubCollector(BaseCollector):
    source_type = "github"

    def __init__(self, token: str = None):
        self.token = token  # GitHub personal access token (optional, for rate limits)
        self.base_url = "https://api.github.com"

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github.v3+json",
                    "User-Agent": "EKAS/1.0"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _parse_repo_url(self, url: str) -> tuple:
        """Extract owner/repo from GitHub URL."""
        match = re.search(r'github\.com/([^/]+)/([^/\s?#]+)', url)
        if match:
            return match.group(1), match.group(2).rstrip('.git')
        return None, None

    def fetch(self, url_or_slug: str) -> Optional[RawContent]:
        """Fetch a GitHub repository's README and metadata."""
        if not HAS_HTTPX:
            return None

        if "/" in url_or_slug and "github.com" in url_or_slug:
            owner, repo = self._parse_repo_url(url_or_slug)
        elif "/" in url_or_slug:
            parts = url_or_slug.split("/")
            owner, repo = parts[0], parts[1]
        else:
            return None

        if not owner or not repo:
            return None

        try:
            # Get repo metadata
            resp = httpx.get(f"{self.base_url}/repos/{owner}/{repo}",
                           headers=self._headers(), timeout=15)
            if resp.status_code != 200:
                return None
            repo_data = resp.json()

            # Get README
            readme_text = ""
            readme_resp = httpx.get(f"{self.base_url}/repos/{owner}/{repo}/readme",
                                   headers={**self._headers(), "Accept": "application/vnd.github.raw"},
                                   timeout=15)
            if readme_resp.status_code == 200:
                readme_text = readme_resp.text

            return RawContent(
                source_type="github",
                source_url=repo_data.get("html_url", url_or_slug),
                source_id=f"{owner}/{repo}",
                title=repo_data.get("full_name", ""),
                author=owner,
                author_channel=f"https://github.com/{owner}",
                published_at=repo_data.get("created_at", ""),
                raw_text=readme_text,
                metadata={
                    "stars": repo_data.get("stargazers_count", 0),
                    "forks": repo_data.get("forks_count", 0),
                    "open_issues": repo_data.get("open_issues_count", 0),
                    "language": repo_data.get("language", ""),
                    "license": (repo_data.get("license") or {}).get("spdx_id", ""),
                    "description": repo_data.get("description", ""),
                    "topics": repo_data.get("topics", []),
                    "updated_at": repo_data.get("updated_at", ""),
                    "size_kb": repo_data.get("size", 0),
                    "default_branch": repo_data.get("default_branch", "main"),
                },
                tags=repo_data.get("topics", []),
            )
        except Exception:
            return None

    def search(self, query: str, filters: Dict[str, Any] = None,
               max_results: int = 10) -> CollectionResult:
        """Search GitHub repositories."""
        if not HAS_HTTPX:
            return CollectionResult(errors=["httpx not installed"])

        result = CollectionResult()
        filters = filters or {}

        import time
        start = time.time()

        # Build search query
        q = query
        if filters.get("language"):
            q += f" language:{filters['language']}"
        if filters.get("min_stars"):
            q += f" stars:>={filters['min_stars']}"

        sort = filters.get("sort", "stars")

        try:
            resp = httpx.get(f"{self.base_url}/search/repositories",
                           params={"q": q, "sort": sort, "per_page": min(max_results, 30)},
                           headers=self._headers(), timeout=15)

            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items:
                    slug = item.get("full_name", "")
                    content = self.fetch(slug)
                    if content:
                        result.items.append(content)
            else:
                result.errors.append(f"GitHub API error: {resp.status_code}")
        except Exception as e:
            result.errors.append(str(e))

        result.total_found = len(result.items)
        result.duration_ms = int((time.time() - start) * 1000)
        return result
