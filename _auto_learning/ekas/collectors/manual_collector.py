"""Manual/PDF collector — extracts text from uploaded documents."""
import os
from typing import Optional, Dict, Any
from .base import BaseCollector, RawContent, CollectionResult

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    try:
        import PyPDF2 as pypdf
        HAS_PYPDF = True
    except ImportError:
        HAS_PYPDF = False


class ManualCollector(BaseCollector):
    """Collects content from local PDF/text files (manuals, guides, etc)."""
    source_type = "manual"

    def fetch(self, file_path: str) -> Optional[RawContent]:
        """Extract text from a local file (PDF or text)."""
        if not os.path.exists(file_path):
            return None

        ext = os.path.splitext(file_path)[1].lower()
        text = ""
        metadata = {"file_size": os.path.getsize(file_path), "extension": ext}

        if ext == ".pdf":
            text = self._extract_pdf(file_path)
            metadata["extractor"] = "pypdf" if HAS_PYPDF else "none"
        elif ext in (".txt", ".md", ".rst", ".html", ".htm"):
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                return None
        else:
            return None

        if not text.strip():
            return None

        filename = os.path.basename(file_path)
        metadata["pages"] = text.count("\f") + 1 if ext == ".pdf" else 1
        metadata["word_count"] = len(text.split())

        return RawContent(
            source_type="manual",
            source_url=f"file://{os.path.abspath(file_path)}",
            source_id=filename,
            title=filename,
            raw_text=text,
            metadata=metadata,
        )

    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF."""
        if not HAS_PYPDF:
            return ""
        try:
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n\n".join(pages)
        except Exception:
            return ""

    def search(self, query: str, filters: Dict[str, Any] = None,
               max_results: int = 10) -> CollectionResult:
        result = CollectionResult()
        result.errors.append("Manual collector: use fetch() with file paths.")
        return result

    def import_directory(self, dir_path: str, extensions: list = None) -> CollectionResult:
        """Import all matching files from a directory."""
        if extensions is None:
            extensions = [".pdf", ".txt", ".md"]

        result = CollectionResult()
        if not os.path.isdir(dir_path):
            result.errors.append(f"Directory not found: {dir_path}")
            return result

        for root, dirs, files in os.walk(dir_path):
            for f in files:
                if any(f.lower().endswith(ext) for ext in extensions):
                    fpath = os.path.join(root, f)
                    content = self.fetch(fpath)
                    if content and self.validate_content(content):
                        result.items.append(content)

        result.total_found = len(result.items)
        return result
