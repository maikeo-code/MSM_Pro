"""EKAS Collectors — Módulos de coleta de conteúdo externo."""
from .base import BaseCollector, RawContent, CollectionResult
from .youtube_collector import YouTubeCollector
from .web_collector import WebCollector
from .docs_collector import DocsCollector
from .manual_collector import ManualCollector
from .github_collector import GitHubCollector
