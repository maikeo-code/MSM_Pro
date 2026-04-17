"""YouTube collector — extracts video metadata and transcripts."""
import json
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from .base import BaseCollector, RawContent, CollectionResult

# Optional imports — graceful degradation
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    HAS_TRANSCRIPT_API = True
except ImportError:
    HAS_TRANSCRIPT_API = False

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class YouTubeCollector(BaseCollector):
    source_type = "youtube"

    def __init__(self, api_key: str = None):
        self.api_key = api_key  # YouTube Data API v3 key (optional)

    def _extract_video_id(self, url_or_id: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
            return url_or_id
        patterns = [
            r'(?:v=|/v/|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})',
            r'(?:shorts/)([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
        return None

    def _extract_channel_id(self, url: str) -> Optional[str]:
        """Extract channel ID or handle from YouTube channel URL."""
        patterns = [
            r'youtube\.com/channel/([a-zA-Z0-9_-]+)',
            r'youtube\.com/@([a-zA-Z0-9_.-]+)',
            r'youtube\.com/c/([a-zA-Z0-9_.-]+)',
            r'youtube\.com/user/([a-zA-Z0-9_.-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _get_transcript(self, video_id: str, languages: List[str] = None) -> str:
        """Get video transcript using youtube-transcript-api v1.2+."""
        if not HAS_TRANSCRIPT_API:
            return ""
        if languages is None:
            languages = ["pt", "pt-BR", "en", "es"]
        api = YouTubeTranscriptApi()
        # Try each preferred language
        for lang in languages:
            try:
                snippets = api.fetch(video_id, languages=[lang])
                texts = [s.text for s in snippets if hasattr(s, 'text') and s.text]
                if texts:
                    return " ".join(texts)
            except Exception:
                continue
        # Fallback: try default (any language)
        try:
            snippets = api.fetch(video_id)
            texts = [s.text for s in snippets if hasattr(s, 'text') and s.text]
            return " ".join(texts)
        except Exception:
            pass
        return ""

    def _get_oembed_info(self, video_id: str) -> Dict[str, Any]:
        """Get basic video info via oEmbed (no API key needed)."""
        if not HAS_HTTPX:
            return {}
        try:
            url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            resp = httpx.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {}

    def _search_with_api(self, query: str, max_results: int = 10,
                          filters: Dict[str, Any] = None) -> List[Dict]:
        """Search YouTube via Data API v3."""
        if not self.api_key or not HAS_HTTPX:
            return []

        filters = filters or {}
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 50),
            "key": self.api_key,
            "order": filters.get("order", "relevance"),
            "relevanceLanguage": filters.get("language", "pt"),
        }

        if filters.get("published_after"):
            params["publishedAfter"] = filters["published_after"]
        if filters.get("published_before"):
            params["publishedBefore"] = filters["published_before"]

        try:
            resp = httpx.get("https://www.googleapis.com/youtube/v3/search",
                           params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("items", [])
        except Exception:
            pass
        return []

    def _get_video_details(self, video_ids: List[str]) -> Dict[str, Dict]:
        """Get detailed video statistics via Data API v3."""
        if not self.api_key or not HAS_HTTPX or not video_ids:
            return {}

        try:
            resp = httpx.get("https://www.googleapis.com/youtube/v3/videos",
                           params={
                               "part": "snippet,statistics,contentDetails",
                               "id": ",".join(video_ids),
                               "key": self.api_key,
                           }, timeout=15)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                return {item["id"]: item for item in items}
        except Exception:
            pass
        return {}

    def _get_channel_videos(self, channel_identifier: str,
                             max_videos: int = 50) -> List[str]:
        """Get video IDs from a channel."""
        if not self.api_key or not HAS_HTTPX:
            return []

        # First resolve channel ID if it's a handle
        channel_id = channel_identifier
        if not channel_identifier.startswith("UC"):
            try:
                # Try search for channel
                resp = httpx.get("https://www.googleapis.com/youtube/v3/search",
                               params={
                                   "part": "snippet",
                                   "q": channel_identifier,
                                   "type": "channel",
                                   "maxResults": 1,
                                   "key": self.api_key,
                               }, timeout=15)
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    if items:
                        channel_id = items[0]["snippet"]["channelId"]
            except Exception:
                return []

        # Get uploads playlist
        try:
            resp = httpx.get("https://www.googleapis.com/youtube/v3/channels",
                           params={
                               "part": "contentDetails",
                               "id": channel_id,
                               "key": self.api_key,
                           }, timeout=15)
            if resp.status_code != 200:
                return []

            channels = resp.json().get("items", [])
            if not channels:
                return []

            uploads_id = channels[0]["contentDetails"]["relatedPlaylists"]["uploads"]

            video_ids = []
            page_token = None
            while len(video_ids) < max_videos:
                params = {
                    "part": "snippet",
                    "playlistId": uploads_id,
                    "maxResults": min(50, max_videos - len(video_ids)),
                    "key": self.api_key,
                }
                if page_token:
                    params["pageToken"] = page_token

                resp = httpx.get("https://www.googleapis.com/youtube/v3/playlistItems",
                               params=params, timeout=15)
                if resp.status_code != 200:
                    break

                data = resp.json()
                for item in data.get("items", []):
                    vid = item["snippet"]["resourceId"]["videoId"]
                    video_ids.append(vid)

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

            return video_ids
        except Exception:
            return []

    def search(self, query: str, filters: Dict[str, Any] = None,
               max_results: int = 10) -> CollectionResult:
        """Search YouTube for videos matching query."""
        result = CollectionResult()
        filters = filters or {}

        import time
        start = time.time()

        # Search via API
        items = self._search_with_api(query, max_results, filters)
        if not items:
            result.errors.append("YouTube Data API not available or returned no results")
            result.duration_ms = int((time.time() - start) * 1000)
            return result

        video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
        details = self._get_video_details(video_ids)

        min_views = filters.get("min_views", 0)
        min_likes = filters.get("min_likes", 0)
        max_age_days = filters.get("max_age_days")

        for vid_id in video_ids:
            detail = details.get(vid_id, {})
            snippet = detail.get("snippet", {})
            stats = detail.get("statistics", {})

            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))

            # Apply filters
            if views < min_views:
                continue
            if likes < min_likes:
                continue

            published = snippet.get("publishedAt", "")
            if max_age_days and published:
                try:
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    from datetime import timezone
                    age = (datetime.now(timezone.utc) - pub_dt).days
                    if age > max_age_days:
                        continue
                except Exception:
                    pass

            # Get transcript
            transcript = self._get_transcript(vid_id)

            duration = detail.get("contentDetails", {}).get("duration", "")

            content = RawContent(
                source_type="youtube",
                source_url=f"https://www.youtube.com/watch?v={vid_id}",
                source_id=vid_id,
                title=snippet.get("title", ""),
                author=snippet.get("channelTitle", ""),
                author_channel=snippet.get("channelId", ""),
                published_at=published,
                raw_text=transcript,
                language=snippet.get("defaultLanguage", "pt"),
                metadata={
                    "views": views,
                    "likes": likes,
                    "comments": int(stats.get("commentCount", 0)),
                    "duration": duration,
                    "description": snippet.get("description", ""),
                    "thumbnails": snippet.get("thumbnails", {}),
                    "category_id": snippet.get("categoryId", ""),
                    "like_ratio": round(likes / max(views, 1), 4),
                },
                tags=snippet.get("tags", []),
            )
            result.items.append(content)

        result.total_found = len(result.items)
        result.duration_ms = int((time.time() - start) * 1000)
        return result

    def fetch(self, url_or_id: str) -> Optional[RawContent]:
        """Fetch a single YouTube video."""
        video_id = self._extract_video_id(url_or_id)
        if not video_id:
            return None

        # Get transcript
        transcript = self._get_transcript(video_id)

        # Get metadata
        details = self._get_video_details([video_id])
        detail = details.get(video_id)

        if detail:
            snippet = detail.get("snippet", {})
            stats = detail.get("statistics", {})
            return RawContent(
                source_type="youtube",
                source_url=f"https://www.youtube.com/watch?v={video_id}",
                source_id=video_id,
                title=snippet.get("title", ""),
                author=snippet.get("channelTitle", ""),
                author_channel=snippet.get("channelId", ""),
                published_at=snippet.get("publishedAt", ""),
                raw_text=transcript,
                metadata={
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                    "duration": detail.get("contentDetails", {}).get("duration", ""),
                    "description": snippet.get("description", ""),
                },
                tags=snippet.get("tags", []),
            )

        # Fallback: oEmbed
        oembed = self._get_oembed_info(video_id)
        if oembed:
            return RawContent(
                source_type="youtube",
                source_url=f"https://www.youtube.com/watch?v={video_id}",
                source_id=video_id,
                title=oembed.get("title", ""),
                author=oembed.get("author_name", ""),
                author_channel=oembed.get("author_url", ""),
                raw_text=transcript,
                metadata={"oembed": True},
            )

        # Minimal: just transcript
        if transcript:
            return RawContent(
                source_type="youtube",
                source_url=f"https://www.youtube.com/watch?v={video_id}",
                source_id=video_id,
                title=f"Video {video_id}",
                raw_text=transcript,
            )

        return None

    def fetch_channel(self, channel_url: str, max_videos: int = 50,
                      filters: Dict[str, Any] = None) -> CollectionResult:
        """Fetch all videos from a YouTube channel."""
        result = CollectionResult()
        import time
        start = time.time()

        channel_id = self._extract_channel_id(channel_url)
        if not channel_id:
            result.errors.append(f"Could not extract channel ID from: {channel_url}")
            return result

        video_ids = self._get_channel_videos(channel_id, max_videos)
        if not video_ids:
            result.errors.append("No videos found or API not available")
            result.duration_ms = int((time.time() - start) * 1000)
            return result

        filters = filters or {}
        min_views = filters.get("min_views", 0)

        # Process in batches of 50 (API limit)
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            details = self._get_video_details(batch)

            for vid_id in batch:
                detail = details.get(vid_id)
                if not detail:
                    continue

                stats = detail.get("statistics", {})
                views = int(stats.get("viewCount", 0))
                if views < min_views:
                    continue

                snippet = detail.get("snippet", {})
                transcript = self._get_transcript(vid_id)

                content = RawContent(
                    source_type="youtube",
                    source_url=f"https://www.youtube.com/watch?v={vid_id}",
                    source_id=vid_id,
                    title=snippet.get("title", ""),
                    author=snippet.get("channelTitle", ""),
                    author_channel=channel_url,
                    published_at=snippet.get("publishedAt", ""),
                    raw_text=transcript,
                    metadata={
                        "views": views,
                        "likes": int(stats.get("likeCount", 0)),
                        "comments": int(stats.get("commentCount", 0)),
                        "duration": detail.get("contentDetails", {}).get("duration", ""),
                        "description": snippet.get("description", ""),
                    },
                    tags=snippet.get("tags", []),
                )
                result.items.append(content)

        result.total_found = len(result.items)
        result.duration_ms = int((time.time() - start) * 1000)
        return result
