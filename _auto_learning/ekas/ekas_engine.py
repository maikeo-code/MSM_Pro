"""
EKAS v1.0 — External Knowledge Acquisition System Engine
Database abstraction layer for multi-project external intelligence.

Method groups:
  - Connection      : __init__, _ensure_db, _conn
  - Projects        : register_project, get_project, get_all_projects, update_project
  - Sources         : add_source, get_source, search_sources, update_source_status,
                      update_source_summaries, get_sources_by_status, get_sources_by_author
  - Competitors     : add_competitor, get_competitor, get_all_competitors, update_competitor,
                      link_source_to_competitor, get_competitor_sources
  - Features        : add_feature, get_feature, get_features_by_category,
                      update_feature_status, update_feature_importance
  - Implementations : add_implementation, get_implementations_for_feature,
                      get_implementations_by_competitor
  - Tutorials       : add_tutorial, get_tutorials, get_tutorials_for_feature
  - Opportunities   : add_opportunity, get_opportunities, validate_opportunity,
                      dismiss_opportunity, update_opportunity_status
  - Watchlist       : add_watch, get_active_watches, deactivate_watch,
                      mark_watch_checked, get_due_watches
  - Collection Runs : start_collection_run, end_collection_run, get_recent_runs
  - Queries         : search_all, get_competitor_profile, compare_competitors,
                      get_feature_landscape, suggest_roadmap
  - Stats           : get_stats, get_project_stats
  - Export          : export_all
"""

import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

EKAS_DIR = Path(__file__).parent
EKAS_DB_PATH = EKAS_DIR / "db" / "ekas.db"


class EkasDB:
    """Motor de banco de dados EKAS v1.0 — Inteligencia externa multi-projeto."""

    def __init__(self, db_path: Path = EKAS_DB_PATH):
        self.db_path = Path(db_path) if not isinstance(db_path, Path) else db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Carrega o schema SQL e aplica ao banco se o arquivo existir."""
        schema_path = EKAS_DIR / "db" / "schema.sql"
        if not schema_path.exists():
            return
        with self._conn() as conn:
            conn.executescript(schema_path.read_text(encoding="utf-8"))

    @contextmanager
    def _conn(self):
        """Gerenciador de contexto de conexao com WAL e foreign keys ativados."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ================================================================
    # PROJECTS
    # ================================================================

    def register_project(
        self,
        project_id: str,
        name: str,
        description: str = "",
        base_path: str = "",
        keywords: Optional[List[str]] = None,
    ) -> str:
        """Registers a project in EKAS. Ignores duplicates by primary key.

        Args:
            project_id: Unique identifier for the project.
            name: Human-readable project name.
            description: Optional description of the project.
            base_path: Filesystem path to the project root.
            keywords: List of keywords for this project's domain.

        Returns:
            The project_id passed in.
        """
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO projects (id, name, description, base_path, keywords)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    name,
                    description,
                    base_path,
                    json.dumps(keywords or [], ensure_ascii=False),
                ),
            )
            return project_id

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a project by its ID.

        Args:
            project_id: The unique project identifier.

        Returns:
            Dict with project data, or None if not found.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if row:
                d = dict(row)
                d["keywords"] = json.loads(d.get("keywords") or "[]")
                return d
            return None

    def get_all_projects(self) -> List[Dict[str, Any]]:
        """Returns all active projects.

        Returns:
            List of project dicts with keywords deserialized.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM projects WHERE is_active=1"
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["keywords"] = json.loads(d.get("keywords") or "[]")
                result.append(d)
            return result

    def update_project(self, project_id: str, **kwargs: Any) -> None:
        """Updates allowed fields on a project record.

        Args:
            project_id: The project to update.
            **kwargs: Fields to update. Allowed: name, description, base_path,
                      keywords, is_active.
        """
        allowed = {"name", "description", "base_path", "keywords", "is_active"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        if "keywords" in fields:
            fields["keywords"] = json.dumps(fields["keywords"], ensure_ascii=False)
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [project_id]
        with self._conn() as conn:
            conn.execute(
                f"UPDATE projects SET {set_clause} WHERE id=?", values
            )

    # ================================================================
    # SOURCES
    # ================================================================

    def add_source(
        self,
        source_type: str,
        source_url: str,
        title: str,
        project_id: Optional[str] = None,
        source_id: Optional[str] = None,
        author: Optional[str] = None,
        author_channel: Optional[str] = None,
        published_at: Optional[str] = None,
        language: str = "pt-BR",
        raw_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        relevance_score: float = 0.0,
    ) -> int:
        """Adds a new source. Ignores duplicates by (source_type, source_url).

        Args:
            source_type: Type of source (e.g. 'youtube', 'article', 'reddit').
            source_url: URL of the source.
            title: Title of the source.
            project_id: Optional project this source belongs to.
            source_id: External platform ID (e.g. YouTube video ID).
            author: Author name.
            author_channel: Author channel or handle.
            published_at: ISO8601 publication date string.
            language: BCP-47 language tag. Defaults to 'pt-BR'.
            raw_text: Full raw text content.
            metadata: Arbitrary metadata dict.
            tags: List of tag strings.

        Returns:
            The row ID of the inserted or existing source.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO sources
                    (project_id, source_type, source_url, source_id, title, author,
                     author_channel, published_at, language, raw_text, metadata, tags,
                     relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    source_type,
                    source_url,
                    source_id,
                    title,
                    author,
                    author_channel,
                    published_at,
                    language,
                    raw_text,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    json.dumps(tags or [], ensure_ascii=False),
                    relevance_score,
                ),
            )
            if cur.lastrowid == 0:
                row = conn.execute(
                    "SELECT id FROM sources WHERE source_type=? AND source_url=?",
                    (source_type, source_url),
                ).fetchone()
                return row["id"] if row else 0
            return cur.lastrowid

    def get_source(self, source_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a source by its row ID.

        Args:
            source_id: The integer primary key of the source.

        Returns:
            Dict with source data, or None if not found.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE id=?", (source_id,)
            ).fetchone()
            if row:
                return self._parse_source(row)
            return None

    def search_sources(
        self,
        query: Optional[str] = None,
        source_type: Optional[str] = None,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        min_relevance: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Full-text search across sources with optional filters.

        Args:
            query: Search string matched against title, raw_text, and author.
            source_type: Filter by source type.
            project_id: Filter to a specific project (includes global sources).
            status: Filter by processing status (RAW, PROCESSED, FAILED, etc.).
            min_relevance: Minimum relevance_score threshold.
            limit: Maximum number of results to return.

        Returns:
            List of source dicts ordered by relevance_score DESC, collected_at DESC.
        """
        conditions: List[str] = []
        params: List[Any] = []

        if query:
            conditions.append("(title LIKE ? OR raw_text LIKE ? OR author LIKE ?)")
            params.extend([f"%{query}%"] * 3)
        if source_type:
            conditions.append("source_type=?")
            params.append(source_type)
        if project_id:
            conditions.append("(project_id=? OR project_id IS NULL)")
            params.append(project_id)
        if status:
            conditions.append("status=?")
            params.append(status)
        if min_relevance is not None:
            conditions.append("relevance_score>=?")
            params.append(min_relevance)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM sources {where}
                ORDER BY relevance_score DESC, collected_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [self._parse_source(r) for r in rows]

    def _parse_source(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Deserializes JSON fields on a source row.

        Args:
            row: A sqlite3.Row from the sources table.

        Returns:
            Dict with metadata and tags deserialized from JSON.
        """
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata") or "{}")
        d["tags"] = json.loads(d.get("tags") or "[]")
        return d

    def update_source_status(self, source_id: int, status: str,
                             processed_at: str = None, error: str = None) -> None:
        """Updates the processing status of a source.

        Sets processed_at timestamp automatically when status is 'PROCESSED'.

        Args:
            source_id: The source's primary key.
            status: New status string (RAW, PROCESSED, FAILED, SKIPPED).
            processed_at: Optional explicit processed_at timestamp.
            error: Optional error message for FAILED status.
        """
        with self._conn() as conn:
            extra = ", processed_at=datetime('now')" if status == "PROCESSED" else ""
            if processed_at:
                extra = f", processed_at=?"
            params = [status]
            if processed_at:
                params.append(processed_at)
            params.append(source_id)
            conn.execute(
                f"UPDATE sources SET status=?{extra} WHERE id=?",
                params,
            )

    def update_source_summaries(
        self,
        source_id: int,
        summary_short: Optional[str] = None,
        summary_medium: Optional[str] = None,
        summary_full: Optional[str] = None,
        relevance_score: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Updates summarization fields on a source.

        Only updates fields that are explicitly provided (not None).

        Args:
            source_id: The source's primary key.
            summary_short: Short summary (1-2 sentences).
            summary_medium: Medium summary (paragraph).
            summary_full: Full structured summary.
            relevance_score: Float score between 0.0 and 1.0.
            tags: Replacement list of tag strings.
        """
        fields: Dict[str, Any] = {}
        if summary_short is not None:
            fields["summary_short"] = summary_short
        if summary_medium is not None:
            fields["summary_medium"] = summary_medium
        if summary_full is not None:
            fields["summary_full"] = summary_full
        if relevance_score is not None:
            fields["relevance_score"] = relevance_score
        if tags is not None:
            fields["tags"] = json.dumps(tags, ensure_ascii=False)
        if not fields:
            return
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [source_id]
        with self._conn() as conn:
            conn.execute(
                f"UPDATE sources SET {set_clause} WHERE id=?", values
            )

    def get_sources_by_status(
        self, status: str, limit: int = 100, project_id: str = None
    ) -> List[Dict[str, Any]]:
        """Returns sources matching a given processing status, oldest first.

        Args:
            status: Status to filter by (RAW, PROCESSED, FAILED, SKIPPED).
            limit: Maximum number of records to return.
            project_id: Optional project filter.

        Returns:
            List of source dicts ordered by collected_at ASC.
        """
        with self._conn() as conn:
            query = "SELECT * FROM sources WHERE status=?"
            params = [status]
            if project_id is not None:
                query += " AND (project_id=? OR project_id IS NULL)"
                params.append(project_id)
            query += " ORDER BY collected_at ASC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            return [self._parse_source(r) for r in rows]

    def get_sources_by_author(
        self, author_channel: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Returns sources from a given author channel, newest first.

        Args:
            author_channel: Partial or full channel identifier (LIKE match).
            limit: Maximum number of records to return.

        Returns:
            List of source dicts ordered by published_at DESC.
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sources
                WHERE author_channel LIKE ?
                ORDER BY published_at DESC LIMIT ?
                """,
                (f"%{author_channel}%", limit),
            ).fetchall()
            return [self._parse_source(r) for r in rows]

    # ================================================================
    # COMPETITORS
    # ================================================================

    def add_competitor(
        self,
        name: str,
        project_id: Optional[str] = None,
        category: Optional[str] = None,
        website: Optional[str] = None,
        pricing_info: Optional[str] = None,
        target_audience: Optional[str] = None,
        integrations: Optional[List] = None,
        strengths: Optional[List] = None,
        weaknesses: Optional[List] = None,
        overall_sentiment: float = 0.0,
    ) -> int:
        """Adds a competitor. Ignores duplicates by (project_id, name)."""
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO competitors
                    (project_id, name, category, website, pricing_info, target_audience,
                     integrations, strengths, weaknesses, overall_sentiment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, name, category, website, pricing_info, target_audience,
                 json.dumps(integrations or [], ensure_ascii=False),
                 json.dumps(strengths or [], ensure_ascii=False),
                 json.dumps(weaknesses or [], ensure_ascii=False),
                 overall_sentiment),
            )
            if cur.lastrowid == 0:
                row = conn.execute(
                    "SELECT id FROM competitors WHERE project_id IS ? AND name=?",
                    (project_id, name),
                ).fetchone()
                return row["id"] if row else 0
            return cur.lastrowid

    def get_competitor(
        self,
        competitor_id: Optional[int] = None,
        name: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a competitor by ID or name.

        Args:
            competitor_id: Primary key lookup (takes priority over name).
            name: Competitor name lookup.
            project_id: Scopes the name lookup to a specific project.

        Returns:
            Dict with competitor data (JSON list fields deserialized), or None.
        """
        with self._conn() as conn:
            if competitor_id:
                row = conn.execute(
                    "SELECT * FROM competitors WHERE id=?", (competitor_id,)
                ).fetchone()
            elif name:
                if project_id:
                    row = conn.execute(
                        "SELECT * FROM competitors WHERE name=? AND project_id=?",
                        (name, project_id),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT * FROM competitors WHERE name=?", (name,)
                    ).fetchone()
            else:
                return None

            if row:
                d = dict(row)
                for field in ("integrations", "strengths", "weaknesses"):
                    d[field] = json.loads(d.get(field) or "[]")
                return d
            return None

    def get_all_competitors(
        self, project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns all competitors, optionally scoped to a project.

        Args:
            project_id: If provided, includes competitors for this project and
                        global competitors (project_id IS NULL).

        Returns:
            List of competitor dicts ordered by source_count DESC.
        """
        with self._conn() as conn:
            if project_id:
                rows = conn.execute(
                    """
                    SELECT * FROM competitors
                    WHERE project_id=? OR project_id IS NULL
                    ORDER BY source_count DESC
                    """,
                    (project_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM competitors ORDER BY source_count DESC"
                ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for field in ("integrations", "strengths", "weaknesses"):
                    d[field] = json.loads(d.get(field) or "[]")
                result.append(d)
            return result

    def update_competitor(self, competitor_id: int, **kwargs: Any) -> None:
        """Updates allowed fields on a competitor record.

        List fields (integrations, strengths, weaknesses) are automatically
        serialized to JSON. Always sets last_updated to current timestamp.

        Args:
            competitor_id: Primary key of the competitor to update.
            **kwargs: Fields to update. Allowed: name, category, website,
                      pricing_info, target_audience, integrations, strengths,
                      weaknesses, overall_sentiment, source_count.
        """
        allowed = {
            "name",
            "category",
            "website",
            "pricing_info",
            "target_audience",
            "integrations",
            "strengths",
            "weaknesses",
            "overall_sentiment",
            "source_count",
        }
        fields: Dict[str, Any] = {}
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k in ("integrations", "strengths", "weaknesses"):
                fields[k] = json.dumps(v, ensure_ascii=False)
            else:
                fields[k] = v
        if not fields:
            return
        fields["last_updated"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [competitor_id]
        with self._conn() as conn:
            conn.execute(
                f"UPDATE competitors SET {set_clause} WHERE id=?", values
            )

    def link_source_to_competitor(
        self, competitor_id: int, source_id: int
    ) -> None:
        """Links a source to a competitor and recalculates source_count.

        Args:
            competitor_id: The competitor's primary key.
            source_id: The source's primary key.
        """
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO competitor_sources (competitor_id, source_id)
                VALUES (?, ?)
                """,
                (competitor_id, source_id),
            )
            conn.execute(
                """
                UPDATE competitors SET source_count = (
                    SELECT COUNT(*) FROM competitor_sources WHERE competitor_id=?
                ), last_updated=datetime('now') WHERE id=?
                """,
                (competitor_id, competitor_id),
            )

    def get_competitor_sources(
        self, competitor_id: int
    ) -> List[Dict[str, Any]]:
        """Returns all sources linked to a competitor, by relevance.

        Args:
            competitor_id: The competitor's primary key.

        Returns:
            List of source dicts ordered by relevance_score DESC.
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT s.* FROM sources s
                JOIN competitor_sources cs ON s.id = cs.source_id
                WHERE cs.competitor_id=?
                ORDER BY s.relevance_score DESC
                """,
                (competitor_id,),
            ).fetchall()
            return [self._parse_source(r) for r in rows]

    # ================================================================
    # FEATURES
    # ================================================================

    def add_feature(
        self,
        name: str,
        project_id: Optional[str] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        implementation_complexity: Optional[str] = None,
        importance_score: float = 0.0,
        project_status: str = "NOT_PLANNED",
    ) -> int:
        """Adds a product feature. Ignores duplicates by (project_id, name)."""
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO features
                    (project_id, name, category, description, implementation_complexity,
                     importance_score, project_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, name, category, description, implementation_complexity,
                 importance_score, project_status),
            )
            if cur.lastrowid == 0:
                row = conn.execute(
                    "SELECT id FROM features WHERE project_id IS ? AND name=?",
                    (project_id, name),
                ).fetchone()
                return row["id"] if row else 0
            return cur.lastrowid

    def get_feature(self, feature_id: int = None, name: str = None,
                    project_id: str = None) -> Optional[Dict[str, Any]]:
        """Retrieves a feature by ID or name."""
        with self._conn() as conn:
            if feature_id:
                row = conn.execute(
                    "SELECT * FROM features WHERE id=?", (feature_id,)
                ).fetchone()
            elif name:
                if project_id:
                    row = conn.execute(
                        "SELECT * FROM features WHERE name=? AND (project_id=? OR project_id IS NULL)",
                        (name, project_id)).fetchone()
                else:
                    row = conn.execute(
                        "SELECT * FROM features WHERE name=?", (name,)
                    ).fetchone()
            else:
                return None
            return dict(row) if row else None

    def get_features_by_category(
        self,
        category: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns features filtered by category and/or project.

        Args:
            category: Category to filter by.
            project_id: Project scope (includes global features).

        Returns:
            List of feature dicts ordered by importance_score DESC.
        """
        conditions: List[str] = []
        params: List[Any] = []

        if category:
            conditions.append("category=?")
            params.append(category)
        if project_id:
            conditions.append("(project_id=? OR project_id IS NULL)")
            params.append(project_id)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM features {where} ORDER BY importance_score DESC",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def update_feature_status(self, feature_id: int, status: str,
                              importance_score: float = None,
                              implementation_complexity: str = None) -> None:
        """Updates the project implementation status of a feature.

        Args:
            feature_id: The feature's primary key.
            status: New status (e.g. PLANNED, IN_PROGRESS, IMPLEMENTED, REJECTED).
            importance_score: Optional importance score update.
            implementation_complexity: Optional complexity update.
        """
        with self._conn() as conn:
            sets = ["project_status=?"]
            params = [status]
            if importance_score is not None:
                sets.append("importance_score=?")
                params.append(importance_score)
            if implementation_complexity is not None:
                sets.append("implementation_complexity=?")
                params.append(implementation_complexity)
            params.append(feature_id)
            conn.execute(
                f"UPDATE features SET {', '.join(sets)} WHERE id=?",
                params,
            )

    def update_feature_importance(
        self, feature_id: int, importance_score: float
    ) -> None:
        """Sets the importance score for a feature.

        Args:
            feature_id: The feature's primary key.
            importance_score: Float score (typically 0.0 to 10.0).
        """
        with self._conn() as conn:
            conn.execute(
                "UPDATE features SET importance_score=? WHERE id=?",
                (importance_score, feature_id),
            )

    # ================================================================
    # IMPLEMENTATIONS
    # ================================================================

    def add_implementation(
        self,
        feature_id: int,
        competitor_id: int,
        how_it_works: Optional[str] = None,
        steps: Optional[List[str]] = None,
        pros: Optional[List[str]] = None,
        cons: Optional[List[str]] = None,
        source_id: Optional[int] = None,
    ) -> int:
        """Records how a competitor implements a specific feature.

        Args:
            feature_id: The feature's primary key.
            competitor_id: The competitor's primary key.
            how_it_works: Free-text description of the implementation approach.
            steps: Ordered list of implementation steps.
            pros: List of advantages of this implementation.
            cons: List of disadvantages of this implementation.
            source_id: Source that documents this implementation.

        Returns:
            The row ID of the new implementation record.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO feature_implementations
                    (feature_id, competitor_id, how_it_works, steps, pros, cons, source_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feature_id,
                    competitor_id,
                    how_it_works,
                    json.dumps(steps or [], ensure_ascii=False),
                    json.dumps(pros or [], ensure_ascii=False),
                    json.dumps(cons or [], ensure_ascii=False),
                    source_id,
                ),
            )
            return cur.lastrowid

    def get_implementations_for_feature(
        self, feature_id: int
    ) -> List[Dict[str, Any]]:
        """Returns all competitor implementations for a given feature.

        Args:
            feature_id: The feature's primary key.

        Returns:
            List of implementation dicts with competitor_name joined in and
            steps/pros/cons deserialized from JSON.
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT fi.*, c.name as competitor_name
                FROM feature_implementations fi
                JOIN competitors c ON fi.competitor_id = c.id
                WHERE fi.feature_id=?
                """,
                (feature_id,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for field in ("steps", "pros", "cons"):
                    d[field] = json.loads(d.get(field) or "[]")
                result.append(d)
            return result

    def get_implementations_by_competitor(
        self, competitor_id: int
    ) -> List[Dict[str, Any]]:
        """Returns all feature implementations from a given competitor.

        Args:
            competitor_id: The competitor's primary key.

        Returns:
            List of implementation dicts with feature_name and feature_category
            joined in and steps/pros/cons deserialized from JSON.
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT fi.*, f.name as feature_name, f.category as feature_category
                FROM feature_implementations fi
                JOIN features f ON fi.feature_id = f.id
                WHERE fi.competitor_id=?
                """,
                (competitor_id,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for field in ("steps", "pros", "cons"):
                    d[field] = json.loads(d.get(field) or "[]")
                result.append(d)
            return result

    # ================================================================
    # TUTORIALS
    # ================================================================

    def add_tutorial(
        self,
        title: str,
        steps: List[str],
        source_id: Optional[int] = None,
        competitor_id: Optional[int] = None,
        feature_id: Optional[int] = None,
        project_id: Optional[str] = None,
        prerequisites: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
        estimated_time: Optional[str] = None,
    ) -> int:
        """Records a how-to tutorial extracted from a source.

        Args:
            title: Tutorial title.
            steps: Ordered list of steps (required, must be non-empty).
            source_id: Source this tutorial was extracted from.
            competitor_id: Competitor this tutorial is about.
            feature_id: Feature this tutorial demonstrates.
            project_id: Optional project scope.
            prerequisites: List of prerequisite conditions or tools.
            difficulty: Difficulty level (beginner, intermediate, advanced).
            estimated_time: Human-readable time estimate (e.g. '30 minutes').

        Returns:
            The row ID of the new tutorial record.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO tutorials
                    (title, source_id, competitor_id, feature_id, project_id,
                     steps, prerequisites, difficulty, estimated_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    source_id,
                    competitor_id,
                    feature_id,
                    project_id,
                    json.dumps(steps, ensure_ascii=False),
                    json.dumps(prerequisites or [], ensure_ascii=False),
                    difficulty,
                    estimated_time,
                ),
            )
            return cur.lastrowid

    def get_tutorials(
        self,
        project_id: Optional[str] = None,
        competitor_id: Optional[int] = None,
        feature_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Returns tutorials with optional filters.

        Args:
            project_id: Filter to project scope (includes global tutorials).
            competitor_id: Filter to a specific competitor.
            feature_id: Filter to a specific feature.
            limit: Maximum number of results.

        Returns:
            List of tutorial dicts with steps/prerequisites deserialized and
            competitor_name/feature_name joined in.
        """
        conditions: List[str] = []
        params: List[Any] = []

        if project_id:
            conditions.append("(t.project_id=? OR t.project_id IS NULL)")
            params.append(project_id)
        if competitor_id:
            conditions.append("t.competitor_id=?")
            params.append(competitor_id)
        if feature_id:
            conditions.append("t.feature_id=?")
            params.append(feature_id)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT t.*, c.name as competitor_name, f.name as feature_name
                FROM tutorials t
                LEFT JOIN competitors c ON t.competitor_id = c.id
                LEFT JOIN features f ON t.feature_id = f.id
                {where}
                ORDER BY t.created_at DESC LIMIT ?
                """,
                params,
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["steps"] = json.loads(d.get("steps") or "[]")
                d["prerequisites"] = json.loads(d.get("prerequisites") or "[]")
                result.append(d)
            return result

    def get_tutorials_for_feature(
        self, feature_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Convenience wrapper returning tutorials for a specific feature.

        Args:
            feature_id: The feature's primary key.
            limit: Maximum number of results.

        Returns:
            List of tutorial dicts as returned by get_tutorials.
        """
        return self.get_tutorials(feature_id=feature_id, limit=limit)

    # ================================================================
    # OPPORTUNITIES
    # ================================================================

    def add_opportunity(
        self,
        type: str,
        title: str,
        project_id: Optional[str] = None,
        description: Optional[str] = None,
        evidence: Optional[List[Any]] = None,
        impact_score: float = 0,
        effort_score: float = 0,
        project_ticket: str = "",
    ) -> int:
        """Records a detected product opportunity."""
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO opportunities
                    (project_id, type, title, description, evidence,
                     impact_score, effort_score, project_ticket)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    type,
                    title,
                    description,
                    json.dumps(evidence or [], ensure_ascii=False),
                    impact_score,
                    effort_score,
                    project_ticket,
                ),
            )
            return cur.lastrowid

    def get_opportunities(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Returns opportunities with optional filters.

        Args:
            project_id: Filter to project scope (includes global opportunities).
            status: Filter by status (DETECTED, VALIDATED, DISMISSED, IN_PROGRESS, DONE).
            type: Filter by opportunity type.
            limit: Maximum number of results.

        Returns:
            List of opportunity dicts ordered by priority_score DESC.
        """
        conditions: List[str] = []
        params: List[Any] = []

        if project_id:
            conditions.append("(project_id=? OR project_id IS NULL)")
            params.append(project_id)
        if status:
            conditions.append("status=?")
            params.append(status)
        if type:
            conditions.append("type=?")
            params.append(type)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM opportunities {where}
                ORDER BY priority_score DESC LIMIT ?
                """,
                params,
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["evidence"] = json.loads(d.get("evidence") or "[]")
                result.append(d)
            return result

    def validate_opportunity(self, opportunity_id: int) -> None:
        """Marks an opportunity as VALIDATED for follow-up.

        Args:
            opportunity_id: The opportunity's primary key.
        """
        with self._conn() as conn:
            conn.execute(
                "UPDATE opportunities SET status='VALIDATED' WHERE id=?",
                (opportunity_id,),
            )

    def dismiss_opportunity(
        self, opportunity_id: int, reason: str = ""
    ) -> None:
        """Marks an opportunity as DISMISSED with an optional reason.

        Args:
            opportunity_id: The opportunity's primary key.
            reason: Explanation of why this opportunity was dismissed.
        """
        with self._conn() as conn:
            conn.execute(
                "UPDATE opportunities SET status='DISMISSED', dismiss_reason=? WHERE id=?",
                (reason, opportunity_id),
            )

    def update_opportunity_status(
        self,
        opportunity_id: int,
        status: str,
        ticket: Optional[str] = None,
    ) -> None:
        """Updates opportunity status and optionally links a project ticket.

        Args:
            opportunity_id: The opportunity's primary key.
            status: New status string.
            ticket: Optional project ticket ID or URL to link.
        """
        with self._conn() as conn:
            if ticket:
                conn.execute(
                    "UPDATE opportunities SET status=?, project_ticket=? WHERE id=?",
                    (status, ticket, opportunity_id),
                )
            else:
                conn.execute(
                    "UPDATE opportunities SET status=? WHERE id=?",
                    (status, opportunity_id),
                )

    # ================================================================
    # WATCHLIST
    # ================================================================

    def add_watch(
        self,
        watch_type: str,
        target: str,
        project_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        check_interval_hours: int = 168,
    ) -> int:
        """Adds a recurring watch target.

        Args:
            watch_type: Type of watch (e.g. 'YOUTUBE_CHANNEL', 'REDDIT_KEYWORD').
            target: The target identifier (URL, channel handle, keyword, etc.).
            project_id: Optional project scope.
            filters: Dict of additional filter parameters for the collector.
            check_interval_hours: How often to re-check (default 168 = weekly).

        Returns:
            The row ID of the new watch record.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO watchlist
                    (project_id, watch_type, target, filters, check_interval_hours)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    watch_type,
                    target,
                    json.dumps(filters or {}, ensure_ascii=False),
                    check_interval_hours,
                ),
            )
            return cur.lastrowid

    def get_active_watches(
        self, project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns all active watches, optionally scoped to a project.

        Args:
            project_id: Filter to project scope (includes global watches).

        Returns:
            List of watch dicts with filters deserialized.
        """
        with self._conn() as conn:
            if project_id:
                rows = conn.execute(
                    """
                    SELECT * FROM watchlist
                    WHERE is_active=1
                      AND (project_id=? OR project_id IS NULL)
                    """,
                    (project_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM watchlist WHERE is_active=1"
                ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["filters"] = json.loads(d.get("filters") or "{}")
                result.append(d)
            return result

    def deactivate_watch(self, watch_id: int) -> None:
        """Deactivates a watch so it will no longer be collected.

        Args:
            watch_id: The watch's primary key.
        """
        with self._conn() as conn:
            conn.execute(
                "UPDATE watchlist SET is_active=0 WHERE id=?", (watch_id,)
            )

    def mark_watch_checked(self, watch_id: int, new_items: int = 0) -> None:
        """Records that a watch was just checked and how many new items were found.

        Args:
            watch_id: The watch's primary key.
            new_items: Number of new items collected in this check.
        """
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE watchlist
                SET last_checked=datetime('now'), new_items_count=?
                WHERE id=?
                """,
                (new_items, watch_id),
            )

    def get_due_watches(self, project_id: str = None) -> List[Dict[str, Any]]:
        """Returns active watches that are due for checking based on their interval.

        A watch is due if it has never been checked or if
        last_checked + check_interval_hours <= now.

        Args:
            project_id: Optional project filter.

        Returns:
            List of watch dicts ordered by last_checked ASC (oldest first),
            with NULL last_checked sorted first.
        """
        with self._conn() as conn:
            query = """
                SELECT * FROM watchlist
                WHERE is_active=1
                  AND (
                    last_checked IS NULL
                    OR datetime(last_checked, '+' || check_interval_hours || ' hours')
                       <= datetime('now')
                  )
                """
            params = []
            if project_id is not None:
                query += " AND project_id=?"
                params.append(project_id)
            query += " ORDER BY last_checked ASC"
            rows = conn.execute(query, params).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["filters"] = json.loads(d.get("filters") or "{}")
                result.append(d)
            return result

    # ================================================================
    # COLLECTION RUNS
    # ================================================================

    def start_collection_run(
        self,
        run_type: str,
        source_type: Optional[str] = None,
        query: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> int:
        """Opens a new collection run record.

        Args:
            run_type: Type of collection run (e.g. 'SCHEDULED', 'MANUAL', 'WATCH').
            source_type: The source type being collected (e.g. 'youtube', 'reddit').
            query: Search query used in this run.
            project_id: Optional project scope.

        Returns:
            The row ID of the new collection run (used to close it later).
        """
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO collection_runs (project_id, run_type, source_type, query)
                VALUES (?, ?, ?, ?)
                """,
                (project_id, run_type, source_type, query),
            )
            return cur.lastrowid

    def end_collection_run(
        self,
        run_id: int,
        items_found: int = 0,
        items_new: int = 0,
        items_processed: int = 0,
        tokens_used: int = 0,
        duration_ms: int = 0,
        status: str = "COMPLETED",
        error: Optional[str] = None,
    ) -> None:
        """Closes an existing collection run with results.

        Args:
            run_id: The run's primary key (from start_collection_run).
            items_found: Total items found in this run.
            items_new: Number of items that were new (not duplicates).
            items_processed: Number of items processed/summarized by AI.
            tokens_used: Total LLM tokens consumed.
            duration_ms: Total wall-clock duration in milliseconds.
            status: Final status (COMPLETED, FAILED, PARTIAL).
            error: Error message if status is FAILED.
        """
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE collection_runs SET
                    items_found=?, items_new=?, items_processed=?,
                    tokens_used=?, duration_ms=?, status=?, error=?,
                    finished_at=datetime('now')
                WHERE id=?
                """,
                (
                    items_found,
                    items_new,
                    items_processed,
                    tokens_used,
                    duration_ms,
                    status,
                    error,
                    run_id,
                ),
            )

    def get_recent_runs(
        self, limit: int = 20, project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns recent collection runs, newest first.

        Args:
            limit: Maximum number of runs to return.
            project_id: Filter to project scope (includes global runs).

        Returns:
            List of collection run dicts.
        """
        with self._conn() as conn:
            if project_id:
                rows = conn.execute(
                    """
                    SELECT * FROM collection_runs
                    WHERE project_id=? OR project_id IS NULL
                    ORDER BY started_at DESC LIMIT ?
                    """,
                    (project_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM collection_runs ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # ADVANCED QUERIES
    # ================================================================

    def search_all(
        self,
        query: str,
        project_id: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Cross-entity search across sources, competitors, features, and opportunities.

        Args:
            query: Search string to match against all entities.
            project_id: Optional project scope.
            limit: Maximum results per entity type.

        Returns:
            Dict with keys 'sources', 'competitors', 'features', 'opportunities',
            each containing a list of matching records.
        """
        sources = self.search_sources(query=query, project_id=project_id, limit=limit)

        with self._conn() as conn:
            if project_id:
                cond_proj = " AND (project_id=? OR project_id IS NULL)"
                proj_params = (project_id,)
            else:
                cond_proj = ""
                proj_params = ()

            comp_rows = conn.execute(
                f"""
                SELECT * FROM competitors
                WHERE (name LIKE ? OR category LIKE ? OR target_audience LIKE ?){cond_proj}
                ORDER BY source_count DESC LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", f"%{query}%") + proj_params + (limit,),
            ).fetchall()
            competitors = []
            for r in comp_rows:
                d = dict(r)
                for field in ("integrations", "strengths", "weaknesses"):
                    d[field] = json.loads(d.get(field) or "[]")
                competitors.append(d)

            feat_rows = conn.execute(
                f"""
                SELECT * FROM features
                WHERE (name LIKE ? OR description LIKE ? OR category LIKE ?){cond_proj}
                ORDER BY importance_score DESC LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", f"%{query}%") + proj_params + (limit,),
            ).fetchall()
            features = [dict(r) for r in feat_rows]

            opp_rows = conn.execute(
                f"""
                SELECT * FROM opportunities
                WHERE (title LIKE ? OR description LIKE ? OR type LIKE ?){cond_proj}
                ORDER BY priority_score DESC LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", f"%{query}%") + proj_params + (limit,),
            ).fetchall()
            opportunities = []
            for r in opp_rows:
                d = dict(r)
                d["evidence"] = json.loads(d.get("evidence") or "[]")
                opportunities.append(d)

        return {
            "query": query,
            "sources": sources,
            "competitors": competitors,
            "features": features,
            "opportunities": opportunities,
        }

    def get_competitor_profile(
        self,
        competitor_id: Optional[int] = None,
        name: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Returns a full competitor profile with features, sources, and sentiment.

        Args:
            competitor_id: Primary key lookup (takes priority over name).
            name: Competitor name lookup.
            project_id: Scopes the name lookup to a specific project.

        Returns:
            Competitor dict enriched with 'sources', 'implementations', and
            'features_count', or None if competitor not found.
        """
        comp = self.get_competitor(
            competitor_id=competitor_id, name=name, project_id=project_id
        )
        if not comp:
            return None
        cid = comp["id"]
        comp["sources"] = self.get_competitor_sources(cid)
        comp["implementations"] = self.get_implementations_by_competitor(cid)
        comp["features_count"] = len(comp["implementations"])
        return comp

    def compare_competitors(
        self, names: List[str], project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compares multiple competitors side by side via a feature matrix.

        Args:
            names: List of competitor names to compare.
            project_id: Optional project scope for competitor lookups.

        Returns:
            Dict with keys:
              - 'competitors': List of summary dicts (name, category, source_count, sentiment).
              - 'feature_matrix': Dict mapping feature_name -> {competitor_name: bool}.
              - 'total_features': Total unique features across all competitors.
        """
        profiles = []
        all_features: set = set()

        for name in names:
            profile = self.get_competitor_profile(name=name, project_id=project_id)
            if profile:
                profiles.append(profile)
                for impl in profile.get("implementations", []):
                    all_features.add(impl.get("feature_name", ""))

        matrix: Dict[str, Dict[str, bool]] = {}
        for feature in sorted(all_features):
            matrix[feature] = {}
            for p in profiles:
                has_it = any(
                    impl.get("feature_name") == feature
                    for impl in p.get("implementations", [])
                )
                matrix[feature][p["name"]] = has_it

        return {
            "competitors": [
                {
                    "name": p["name"],
                    "category": p.get("category"),
                    "source_count": p.get("source_count", 0),
                    "sentiment": p.get("overall_sentiment", 0),
                }
                for p in profiles
            ],
            "feature_matrix": matrix,
            "total_features": len(all_features),
        }

    def get_feature_landscape(
        self, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Returns an overview of all features, who has them, and project status.

        Args:
            project_id: Optional project scope.

        Returns:
            Dict with 'total_features' count and 'features' list sorted by
            importance DESC. Each feature entry includes competitor coverage.
        """
        features = self.get_features_by_category(project_id=project_id)
        landscape = []
        for f in features:
            impls = self.get_implementations_for_feature(f["id"])
            landscape.append(
                {
                    "feature": f["name"],
                    "category": f.get("category"),
                    "importance": f.get("importance_score", 0),
                    "complexity": f.get("implementation_complexity"),
                    "project_status": f.get("project_status"),
                    "competitors_with_it": [i["competitor_name"] for i in impls],
                    "implementations_count": len(impls),
                }
            )
        return {
            "total_features": len(landscape),
            "features": sorted(landscape, key=lambda x: -x["importance"]),
        }

    def suggest_roadmap(
        self, project_id: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Suggests features to implement based on importance, market coverage, and effort.

        Scoring logic:
          - Base score = feature importance_score.
          - 1.5x multiplier if 3+ competitors have the feature (market standard).
          - Complexity multiplier: low=1.3, medium=1.0, high=0.7, very_high=0.5.

        Excludes features already IMPLEMENTED or IN_PROGRESS.

        Args:
            project_id: Optional project scope.
            limit: Maximum number of suggestions to return.

        Returns:
            List of suggestion dicts sorted by score DESC, each containing
            feature name, category, computed score, importance, complexity,
            competitor count, and a human-readable reason.
        """
        features = self.get_features_by_category(project_id=project_id)
        suggestions = []

        complexity_boost: Dict[str, float] = {
            "low": 1.3,
            "medium": 1.0,
            "high": 0.7,
            "very_high": 0.5,
        }

        for f in features:
            if f.get("project_status") in ("IMPLEMENTED", "IN_PROGRESS"):
                continue
            impls = self.get_implementations_for_feature(f["id"])

            score = float(f.get("importance_score", 0))
            if len(impls) >= 3:
                score *= 1.5
            score *= complexity_boost.get(
                f.get("implementation_complexity", "medium"), 1.0
            )

            suggestions.append(
                {
                    "feature": f["name"],
                    "category": f.get("category"),
                    "score": round(score, 3),
                    "importance": f.get("importance_score", 0),
                    "complexity": f.get("implementation_complexity"),
                    "competitors_with_it": len(impls),
                    "reason": (
                        f"{'Padrao de mercado' if len(impls) >= 3 else 'Diferencial'} — "
                        f"importancia {f.get('importance_score', 0):.1f}, "
                        f"complexidade {f.get('implementation_complexity', '?')}"
                    ),
                }
            )

        return sorted(suggestions, key=lambda x: -x["score"])[:limit]

    # ================================================================
    # STATS
    # ================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Returns aggregate counts across all EKAS entities.

        Returns:
            Dict with counts for projects, sources (by status), competitors,
            features (by status), tutorials, opportunities (by status),
            watchlist active entries, and total collection runs.
        """
        with self._conn() as conn:

            def count(table: str, condition: str = "1=1") -> int:
                return conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {condition}"
                ).fetchone()[0]

            return {
                "projects": count("projects", "is_active=1"),
                "sources_total": count("sources"),
                "sources_raw": count("sources", "status='RAW'"),
                "sources_processed": count("sources", "status='PROCESSED'"),
                "sources_failed": count("sources", "status='FAILED'"),
                "competitors": count("competitors"),
                "features": count("features"),
                "features_implemented": count(
                    "features", "project_status='IMPLEMENTED'"
                ),
                "features_planned": count("features", "project_status='PLANNED'"),
                "tutorials": count("tutorials"),
                "opportunities_total": count("opportunities"),
                "opportunities_detected": count(
                    "opportunities", "status='DETECTED'"
                ),
                "opportunities_validated": count(
                    "opportunities", "status='VALIDATED'"
                ),
                "watchlist_active": count("watchlist", "is_active=1"),
                "collection_runs": count("collection_runs"),
            }

    def get_project_stats(self, project_id: str) -> Dict[str, Any]:
        """Returns aggregate counts scoped to a specific project.

        Counts include both project-specific records and global records
        (project_id IS NULL) for sources, competitors, features, tutorials,
        opportunities, and active watches.

        Args:
            project_id: The project to report stats for.

        Returns:
            Dict with project_id and entity counts.
        """
        with self._conn() as conn:

            _STAT_TABLES = {"sources", "competitors", "features", "tutorials",
                            "opportunities", "watchlist"}

            def count(table: str, extra: str = "") -> int:
                if table not in _STAT_TABLES:
                    raise ValueError(f"Invalid table: {table}")
                cond = "(project_id=? OR project_id IS NULL)"
                params = [project_id]
                if extra:
                    cond += f" AND {extra}"
                return conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {cond}",
                    params,
                ).fetchone()[0]

            return {
                "project_id": project_id,
                "sources": count("sources"),
                "competitors": count("competitors"),
                "features": count("features"),
                "tutorials": count("tutorials"),
                "opportunities": count("opportunities"),
                "watches": count("watchlist", "is_active=1"),
            }

    # ================================================================
    # EXPORT
    # ================================================================

    def export_all(self) -> str:
        """Exports the entire EKAS database to a timestamped JSON file.

        The export includes stats, projects, competitors, features,
        opportunities, active watches, and the 50 most recent collection runs.

        Returns:
            Absolute path to the generated JSON export file.
        """
        export_dir = EKAS_DIR / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = export_dir / f"ekas_export_{ts}.json"

        data = {
            "exported_at": datetime.now().isoformat(),
            "version": "EKAS v1.0",
            "stats": self.get_stats(),
            "projects": self.get_all_projects(),
            "competitors": self.get_all_competitors(),
            "features": self.get_features_by_category(),
            "opportunities": self.get_opportunities(),
            "watches": self.get_active_watches(),
            "recent_runs": self.get_recent_runs(50),
        }

        export_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(export_path)

    # ================================================================
    # ALIASES — compatibilidade entre engine e runner
    # ================================================================
    def add_project(self, *a, **kw):
        return self.register_project(*a, **kw)

    def list_projects(self, **kw):
        return self.get_all_projects(**kw)

    def list_competitors(self, project_id=None, **kw):
        return self.get_all_competitors(project_id=project_id, **kw)

    def link_competitor_source(self, competitor_id, source_id):
        return self.link_source_to_competitor(competitor_id, source_id)

    def get_competitor_full_profile(self, **kw):
        return self.get_competitor_profile(**kw)

    def add_feature_implementation(self, *a, **kw):
        return self.add_implementation(*a, **kw)

    def get_feature_implementations(self, feature_id):
        return self.get_implementations_for_feature(feature_id)

    def get_competitor_implementations(self, competitor_id):
        return self.get_implementations_by_competitor(competitor_id)

    def list_tutorials(self, **kw):
        return self.get_tutorials(**kw)

    def list_opportunities(self, **kw):
        return self.get_opportunities(**kw)

    def add_watchlist(self, *a, **kw):
        return self.add_watch(*a, **kw)

    def list_watchlist(self, project_id=None, active_only=True, **kw):
        if active_only:
            return self.get_active_watches(project_id=project_id)
        with self._conn() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM watchlist WHERE project_id=? OR project_id IS NULL",
                    (project_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM watchlist").fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["filters"] = json.loads(d.get("filters") or "{}")
                result.append(d)
            return result
