"""
EKAS Cycle Bridge v1.0
Integra o modulo EKAS ao ciclo de aprendizado do Swarm Genesis v6.
Adiciona fases de coleta e processamento externo ao loop existente.

Fases adicionadas ao ciclo:
  - Fase 2: COLLECTION  — agente scout coleta de fontes externas
  - Fase 3: PROCESSING  — agente analyst-external processa conteudo bruto via IA
  - Fase 6+: STRATEGY   — agente strategist gera roadmap e alimenta o learning.db

Integracao:
  - Le learning.db (SwarmDB) para entender estado do ciclo atual
  - Executa coleta EKAS (watchlist, buscas)
  - Processa fontes brutas pelo pipeline de IA
  - Salva resultados em ekas.db (features, concorrentes, tutoriais, oportunidades)
  - Alimenta insights-chave de volta ao learning.db como conhecimento semantico
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Bootstrap: carrega .env antes de qualquer import do ecossistema
# ---------------------------------------------------------------------------
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").strip().splitlines():
        _line = _line.strip()
        if _line and "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------------------
# Path setup — permite imports de engine.py (Genesis) e ekas_engine.py (EKAS)
# ---------------------------------------------------------------------------
EKAS_DIR = Path(__file__).parent
GENESIS_DIR = EKAS_DIR.parent

if str(GENESIS_DIR) not in sys.path:
    sys.path.insert(0, str(GENESIS_DIR))
if str(EKAS_DIR) not in sys.path:
    sys.path.insert(0, str(EKAS_DIR))

# ---------------------------------------------------------------------------
# Imports do ecossistema — com mensagens de erro claras se ausentes
# ---------------------------------------------------------------------------
try:
    from engine import SwarmDB
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        f"Nao foi possivel importar SwarmDB de '{GENESIS_DIR}/engine.py'. "
        f"Verifique se o arquivo existe e se o Genesis esta instalado. Erro: {exc}"
    ) from exc

try:
    from ekas_engine import EkasDB
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        f"Nao foi possivel importar EkasDB de '{EKAS_DIR}/ekas_engine.py'. "
        f"Erro: {exc}"
    ) from exc

try:
    from processors.pipeline import ProcessingPipeline
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        f"Nao foi possivel importar ProcessingPipeline de "
        f"'{EKAS_DIR}/processors/pipeline.py'. Erro: {exc}"
    ) from exc

try:
    from collectors.youtube_collector import YouTubeCollector
    from collectors.web_collector import WebCollector
    from collectors.docs_collector import DocsCollector
    from collectors.manual_collector import ManualCollector
    from collectors.github_collector import GitHubCollector
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        f"Nao foi possivel importar um ou mais collectors de "
        f"'{EKAS_DIR}/collectors/'. Erro: {exc}"
    ) from exc

# ---------------------------------------------------------------------------
# Logger centralizado
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ekas.cycle_bridge")

# ---------------------------------------------------------------------------
# Mapeamento de tipos de watch para collectors
# ---------------------------------------------------------------------------
_WATCH_TYPE_TO_COLLECTOR: Dict[str, str] = {
    "keyword": "youtube",
    "channel": "youtube",
    "competitor": "youtube",
    "feature": "youtube",
    "author": "youtube",
    # Tipos adicionais mapeados para web como fallback
    "rss": "web",
    "url": "web",
    "github": "github",
    "docs": "docs",
}


# ===========================================================================
# EkasCycleBridge
# ===========================================================================
class EkasCycleBridge:
    """Bridge entre o ciclo de aprendizado do Swarm Genesis e o modulo EKAS.

    Responsabilidades:
    - Fase 2 (COLLECTION): verifica watchlist e coleta conteudo externo.
    - Fase 3 (PROCESSING): processa fontes brutas via pipeline de IA.
    - Fase 6+ (STRATEGY): gera roadmap e alimenta insights no learning.db.

    Ambas as DBs (SwarmDB e EkasDB) sao gerenciadas pelo bridge, garantindo
    rastreabilidade cruzada entre os dois sistemas de armazenamento.

    Args:
        project_id: Identificador do projeto EKAS ativo (ex: "msm_pro").
        project_context: Descricao textual usada pelo pipeline para pontuar
            relevancia. Ex: "MSM Pro — Dashboard de vendas Mercado Livre".
        swarm_db_path: Caminho customizado para o learning.db (opcional).
        ekas_db_path: Caminho customizado para o ekas.db (opcional).
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        project_context: str = "",
        swarm_db_path: Optional[Path] = None,
        ekas_db_path: Optional[Path] = None,
    ) -> None:
        self.project_id: Optional[str] = project_id
        self.project_context: str = project_context

        # Inicializa as DBs
        self.swarm_db: SwarmDB = (
            SwarmDB(swarm_db_path) if swarm_db_path else SwarmDB()
        )
        self.ekas_db: EkasDB = (
            EkasDB(ekas_db_path) if ekas_db_path else EkasDB()
        )

        # Pipeline de IA — lazy-initializado na primeira chamada a process()
        self.pipeline: ProcessingPipeline = ProcessingPipeline(
            project_context=project_context
        )

        # Collectors — instanciados uma unica vez e reutilizados
        self.collectors: Dict[str, Any] = {
            "youtube": YouTubeCollector(),
            "web": WebCollector(),
            "docs": DocsCollector(),
            "manual": ManualCollector(),
            "github": GitHubCollector(),
        }

        logger.info(
            "EkasCycleBridge inicializado | project_id=%s | context=%s",
            project_id,
            project_context[:60] + "..." if len(project_context) > 60 else project_context,
        )

    # =======================================================================
    # FASE 2: COLLECTION
    # =======================================================================
    def run_collection_phase(self, cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Fase 2: COLLECTION — agente scout coleta de fontes externas.

        Etapas internas:
        1. Busca watches vencidos na watchlist EKAS.
        2. Para cada watch, executa o collector adequado.
        3. Persiste itens novos em ekas.db (duplicatas ignoradas por constraint).
        4. Registra inicio/fim da fase em action_log (learning.db).
        5. Fecha cada collection_run com estatisticas.

        Args:
            cycle_id: ID do ciclo corrente em learning.db. Pode ser None se
                chamado fora de um ciclo formal.

        Returns:
            Dict com chaves: watches_checked, items_found, items_new, errors.
        """
        stats: Dict[str, Any] = {
            "watches_checked": 0,
            "items_found": 0,
            "items_new": 0,
            "errors": [],
        }

        self._log_action(
            cycle_id=cycle_id,
            agent="scout",
            action="collection_phase_start",
            target="ekas_watchlist",
        )

        due_watches: List[Dict[str, Any]] = []
        try:
            due_watches = self.ekas_db.get_due_watches()
        except Exception as exc:
            msg = f"Erro ao obter due_watches: {exc}"
            logger.error(msg)
            stats["errors"].append(msg)
            self._log_action(
                cycle_id=cycle_id,
                agent="scout",
                action="collection_phase_end",
                target="ekas_watchlist",
                result="error",
                details=json.dumps(stats, ensure_ascii=False),
            )
            return stats

        logger.info("Watches vencidos encontrados: %d", len(due_watches))

        for watch in due_watches:
            watch_id: int = watch.get("id", 0)
            watch_type: str = watch.get("watch_type", "").lower()
            target: str = watch.get("target", "")

            run_id: int = 0
            try:
                run_id = self.ekas_db.start_collection_run(
                    run_type="watchlist",
                    source_type=watch_type,
                    query=target,
                    project_id=watch.get("project_id"),
                )

                collector_key = self._map_watch_to_collector(watch_type)
                collector = self.collectors.get(collector_key)

                if collector is None:
                    msg = f"Nenhum collector disponivel para watch_type='{watch_type}' (watch_id={watch_id})"
                    logger.warning(msg)
                    stats["errors"].append(msg)
                    self.ekas_db.end_collection_run(
                        run_id,
                        status="FAILED",
                        error=msg,
                    )
                    continue

                phase_found = 0
                phase_new = 0
                t_start = time.time()

                if watch_type == "channel":
                    # Coleta os ultimos videos de um canal YouTube
                    yt = self.collectors.get("youtube")
                    if yt and hasattr(yt, "fetch_channel"):
                        result = yt.fetch_channel(target, max_videos=20)
                        found, new = self._persist_collection_result(
                            result, project_id=watch.get("project_id")
                        )
                        phase_found += found
                        phase_new += new
                    else:
                        # Fallback: busca pelo nome do canal
                        result = collector.search(target, max_results=10)
                        found, new = self._persist_collection_result(
                            result, project_id=watch.get("project_id")
                        )
                        phase_found += found
                        phase_new += new

                elif watch_type == "keyword":
                    # Busca no YouTube (collector padrao para keywords)
                    result = collector.search(
                        target,
                        filters=watch.get("filters", {}),
                        max_results=10,
                    )
                    found, new = self._persist_collection_result(
                        result, project_id=watch.get("project_id")
                    )
                    phase_found += found
                    phase_new += new

                elif watch_type in ("competitor", "feature", "author"):
                    # Busca no YouTube pelo nome do alvo
                    yt = self.collectors.get("youtube")
                    if yt:
                        result = yt.search(target, max_results=5)
                        found, new = self._persist_collection_result(
                            result, project_id=watch.get("project_id")
                        )
                        phase_found += found
                        phase_new += new

                elif watch_type == "github":
                    gh = self.collectors.get("github")
                    if gh:
                        result = gh.search(target, max_results=10)
                        found, new = self._persist_collection_result(
                            result, project_id=watch.get("project_id")
                        )
                        phase_found += found
                        phase_new += new

                elif watch_type == "docs":
                    docs = self.collectors.get("docs")
                    if docs:
                        result = docs.search(target, max_results=5)
                        found, new = self._persist_collection_result(
                            result, project_id=watch.get("project_id")
                        )
                        phase_found += found
                        phase_new += new

                else:
                    # Fallback generico via web
                    web = self.collectors.get("web")
                    if web:
                        result = web.search(target, max_results=5)
                        found, new = self._persist_collection_result(
                            result, project_id=watch.get("project_id")
                        )
                        phase_found += found
                        phase_new += new

                duration_ms = int((time.time() - t_start) * 1000)
                stats["items_found"] += phase_found
                stats["items_new"] += phase_new
                stats["watches_checked"] += 1

                self.ekas_db.end_collection_run(
                    run_id,
                    items_found=phase_found,
                    items_new=phase_new,
                    duration_ms=duration_ms,
                    status="COMPLETED",
                )
                self.ekas_db.mark_watch_checked(watch_id, new_items=phase_new)

                logger.info(
                    "Watch %d (%s='%s') | encontrados=%d | novos=%d | %dms",
                    watch_id,
                    watch_type,
                    target[:40],
                    phase_found,
                    phase_new,
                    duration_ms,
                )

            except Exception as exc:
                msg = f"Watch {watch_id} ('{target}'): {exc}"
                logger.exception("Erro ao processar watch %d", watch_id)
                stats["errors"].append(msg)
                if run_id:
                    try:
                        self.ekas_db.end_collection_run(
                            run_id,
                            status="FAILED",
                            error=str(exc),
                        )
                    except Exception:
                        pass  # nao propaga falha de cleanup

        self._log_action(
            cycle_id=cycle_id,
            agent="scout",
            action="collection_phase_end",
            target="ekas_watchlist",
            details=json.dumps(stats, ensure_ascii=False),
        )

        logger.info(
            "Coleta finalizada | watches=%d | novos=%d | erros=%d",
            stats["watches_checked"],
            stats["items_new"],
            len(stats["errors"]),
        )
        return stats

    # =======================================================================
    # FASE 3: PROCESSING
    # =======================================================================
    def run_processing_phase(
        self, cycle_id: Optional[int] = None, limit: int = 20
    ) -> Dict[str, Any]:
        """Fase 3: PROCESSING — agente analyst-external processa fontes brutas via IA.

        Etapas internas:
        1. Busca fontes com status RAW em ekas.db.
        2. Para cada fonte, executa o pipeline de 6 estagios do Claude.
        3. Persiste resumos, features, concorrentes, tutoriais, oportunidades.
        4. Atualiza o status da fonte para PROCESSED (ou FAILED se erro).
        5. Insights relevantes (score >= 0.5) sao salvos no learning.db.
        6. Registra a fase no action_log com contagem de tokens.

        Args:
            cycle_id: ID do ciclo corrente em learning.db.
            limit: Maximo de fontes a processar por chamada.

        Returns:
            Dict com: processed, failed, features_found, competitors_found,
            tutorials_found, opportunities_found, tokens_used, errors.
        """
        stats: Dict[str, Any] = {
            "processed": 0,
            "failed": 0,
            "features_found": 0,
            "competitors_found": 0,
            "tutorials_found": 0,
            "opportunities_found": 0,
            "tokens_used": 0,
            "errors": [],
        }

        self._log_action(
            cycle_id=cycle_id,
            agent="analyst-external",
            action="processing_phase_start",
            target="ekas_sources",
        )

        raw_sources: List[Dict[str, Any]] = []
        try:
            raw_sources = self.ekas_db.get_sources_by_status("RAW", limit=limit)
        except Exception as exc:
            msg = f"Erro ao obter fontes RAW: {exc}"
            logger.error(msg)
            stats["errors"].append(msg)
            self._log_action(
                cycle_id=cycle_id,
                agent="analyst-external",
                action="processing_phase_end",
                target="ekas_sources",
                result="error",
                details=json.dumps(stats, ensure_ascii=False),
            )
            return stats

        logger.info("Fontes RAW a processar: %d (limit=%d)", len(raw_sources), limit)

        for source in raw_sources:
            source_id: int = source.get("id", 0)
            source_title: str = source.get("title", f"source_{source_id}")
            source_type: str = source.get("source_type", "unknown")

            try:
                # Marca como PROCESSING para evitar duplo processamento em
                # execucoes paralelas
                self.ekas_db.update_source_status(source_id, "PROCESSING")

                raw_text: str = source.get("raw_text") or ""
                metadata: Dict[str, Any] = source.get("metadata") or {}
                pid: Optional[str] = source.get("project_id") or self.project_id

                # Se nao ha texto e nao ha titulo util, falha rapidamente
                if not raw_text.strip() and not source_title.strip():
                    reason = f"Fonte {source_id} sem texto e sem titulo — ignorada"
                    logger.warning(reason)
                    self.ekas_db.update_source_status(source_id, "FAILED")
                    stats["failed"] += 1
                    stats["errors"].append(reason)
                    continue

                result = self.pipeline.process(
                    title=source_title,
                    raw_text=raw_text,
                    source_type=source_type,
                    metadata=metadata,
                    source_id=source_id,
                )

                # Se o pipeline falhou em todos os estagios criticos e nao
                # gerou nem um resumo curto, marca como FAILED
                if result.errors and not result.summary_short:
                    reason = f"Pipeline falhou completamente para fonte {source_id}: {result.errors}"
                    logger.warning(reason)
                    self.ekas_db.update_source_status(source_id, "FAILED")
                    stats["failed"] += 1
                    stats["errors"].extend(result.errors)
                    continue

                # ----- Resumos -----
                self.ekas_db.update_source_summaries(
                    source_id,
                    summary_short=result.summary_short,
                    summary_medium=result.summary_medium,
                    summary_full=result.summary_full,
                    relevance_score=result.relevance_score,
                    tags=result.tags_generated,
                )

                # ----- Features -----
                for feat in result.features_detected:
                    feat_name = (feat.get("name") or "").strip()
                    if not feat_name:
                        continue
                    fid = self.ekas_db.add_feature(
                        name=feat_name,
                        project_id=pid,
                        category=feat.get("category"),
                        description=feat.get("description"),
                    )
                    if fid:
                        stats["features_found"] += 1

                # ----- Concorrentes -----
                for comp in result.competitors_mentioned:
                    comp_name = (comp.get("name") or "").strip()
                    if not comp_name:
                        continue
                    cid = self.ekas_db.add_competitor(
                        name=comp_name,
                        project_id=pid,
                        category=comp.get("category"),
                        strengths=comp.get("strengths") or [],
                        weaknesses=comp.get("weaknesses") or [],
                    )
                    if cid:
                        try:
                            self.ekas_db.link_source_to_competitor(cid, source_id)
                        except Exception:
                            pass  # link pode ja existir; nao e critico
                        stats["competitors_found"] += 1

                # ----- Tutoriais -----
                for tut in result.tutorials_extracted:
                    tut_title = (tut.get("title") or source_title).strip()
                    tut_steps = tut.get("steps") or []
                    if not tut_steps:
                        continue  # tutorial vazio nao tem valor
                    tid = self.ekas_db.add_tutorial(
                        title=tut_title,
                        steps=tut_steps,
                        source_id=source_id,
                        project_id=pid,
                        prerequisites=tut.get("prerequisites"),
                        difficulty=tut.get("difficulty"),
                        estimated_time=tut.get("estimated_time"),
                    )
                    if tid:
                        stats["tutorials_found"] += 1

                # ----- Oportunidades -----
                for opp in result.opportunities:
                    opp_title = (opp.get("title") or "").strip()
                    if not opp_title:
                        continue
                    oid = self.ekas_db.add_opportunity(
                        type=opp.get("type") or "gap",
                        title=opp_title,
                        project_id=pid,
                        description=opp.get("description"),
                        evidence=[{"source_id": source_id, "title": source_title}],
                        impact_score=float(opp.get("impact_score") or 0),
                        effort_score=float(opp.get("effort_score") or 0),
                    )
                    if oid:
                        stats["opportunities_found"] += 1

                # Marca como processado
                self.ekas_db.update_source_status(source_id, "PROCESSED")
                stats["processed"] += 1
                stats["tokens_used"] += result.tokens_used

                # ----- Alimenta learning.db com insight -----
                # Apenas fontes com relevancia >= 0.5 sao promovidas ao
                # conhecimento semantico do Swarm Genesis.
                if result.relevance_score >= 0.5:
                    knowledge_key = (
                        f"source_{source_id}_{source_title[:50].replace(' ', '_')}"
                    )
                    knowledge_value = result.summary_medium or result.summary_short
                    if knowledge_value:
                        try:
                            self.swarm_db.save_knowledge(
                                category="inteligencia_externa",
                                key=knowledge_key,
                                value=knowledge_value,
                                confidence=result.relevance_score,
                            )
                        except Exception as exc:
                            logger.warning(
                                "Nao foi possivel salvar knowledge para fonte %d: %s",
                                source_id,
                                exc,
                            )

                logger.info(
                    "Fonte %d processada | relevancia=%.2f | features=%d | "
                    "competidores=%d | tutoriais=%d | oportunidades=%d | tokens=%d",
                    source_id,
                    result.relevance_score,
                    len(result.features_detected),
                    len(result.competitors_mentioned),
                    len(result.tutorials_extracted),
                    len(result.opportunities),
                    result.tokens_used,
                )

            except Exception as exc:
                msg = f"Fonte {source_id} ('{source_title[:40]}'): {exc}"
                logger.exception("Erro ao processar fonte %d", source_id)
                stats["failed"] += 1
                stats["errors"].append(msg)
                try:
                    self.ekas_db.update_source_status(source_id, "FAILED")
                except Exception:
                    pass

        self._log_action(
            cycle_id=cycle_id,
            agent="analyst-external",
            action="processing_phase_end",
            target="ekas_sources",
            details=json.dumps(stats, ensure_ascii=False),
            tokens_used=stats["tokens_used"],
        )

        logger.info(
            "Processamento finalizado | ok=%d | falhas=%d | tokens=%d",
            stats["processed"],
            stats["failed"],
            stats["tokens_used"],
        )
        return stats

    # =======================================================================
    # FASE 6+: STRATEGY
    # =======================================================================
    def run_strategy_phase(self, cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Fase 6+: STRATEGY — agente strategist gera roadmap e insights.

        Etapas internas:
        1. Gera sugestoes de roadmap baseadas em features e concorrentes.
        2. Busca oportunidades detectadas.
        3. Alimenta os top 5 itens de roadmap e oportunidades no learning.db.

        Args:
            cycle_id: ID do ciclo corrente em learning.db.

        Returns:
            Dict com: roadmap_items, opportunities_analyzed, errors.
        """
        stats: Dict[str, Any] = {
            "roadmap_items": 0,
            "opportunities_analyzed": 0,
            "errors": [],
        }

        self._log_action(
            cycle_id=cycle_id,
            agent="strategist",
            action="strategy_phase_start",
            target="ekas_intelligence",
        )

        # --- Roadmap ---
        roadmap: List[Dict[str, Any]] = []
        try:
            roadmap = self.ekas_db.suggest_roadmap(
                project_id=self.project_id, limit=10
            )
            stats["roadmap_items"] = len(roadmap)
        except Exception as exc:
            msg = f"Erro ao gerar roadmap: {exc}"
            logger.error(msg)
            stats["errors"].append(msg)

        for item in roadmap[:5]:
            feature_name = item.get("feature") or ""
            if not feature_name:
                continue
            knowledge_value = json.dumps(
                {
                    "score": item.get("score", 0),
                    "category": item.get("category"),
                    "complexity": item.get("complexity"),
                    "competitors_with_it": item.get("competitors_with_it", 0),
                    "reason": item.get("reason", ""),
                },
                ensure_ascii=False,
            )
            confidence = min(float(item.get("score") or 0), 1.0)
            try:
                self.swarm_db.save_knowledge(
                    category="roadmap_sugerido",
                    key=feature_name,
                    value=knowledge_value,
                    confidence=confidence,
                )
            except Exception as exc:
                logger.warning("Nao foi possivel salvar roadmap item '%s': %s", feature_name, exc)

        # --- Oportunidades ---
        opportunities: List[Dict[str, Any]] = []
        try:
            opportunities = self.ekas_db.get_opportunities(
                project_id=self.project_id, status="DETECTED"
            )
            stats["opportunities_analyzed"] = len(opportunities)
        except Exception as exc:
            msg = f"Erro ao obter oportunidades: {exc}"
            logger.error(msg)
            stats["errors"].append(msg)

        for opp in opportunities[:5]:
            opp_title = (opp.get("title") or "").strip()
            if not opp_title:
                continue
            priority_score = float(opp.get("priority_score") or 0)
            knowledge_value = json.dumps(
                {
                    "type": opp.get("type"),
                    "priority": priority_score,
                    "impact": opp.get("impact_score", 0),
                    "effort": opp.get("effort_score", 0),
                },
                ensure_ascii=False,
            )
            try:
                self.swarm_db.save_knowledge(
                    category="oportunidades_mercado",
                    key=opp_title,
                    value=knowledge_value,
                    confidence=min(priority_score, 1.0),
                )
            except Exception as exc:
                logger.warning(
                    "Nao foi possivel salvar oportunidade '%s': %s", opp_title, exc
                )

        self._log_action(
            cycle_id=cycle_id,
            agent="strategist",
            action="strategy_phase_end",
            target="ekas_intelligence",
            details=json.dumps(stats, ensure_ascii=False),
        )

        logger.info(
            "Estrategia finalizada | roadmap=%d | oportunidades=%d",
            stats["roadmap_items"],
            stats["opportunities_analyzed"],
        )
        return stats

    # =======================================================================
    # CICLO COMPLETO EKAS
    # =======================================================================
    def run_full_ekas_cycle(self, cycle_id: Optional[int] = None) -> Dict[str, Any]:
        """Executa um ciclo EKAS completo: coleta → processamento → estrategia.

        Sequencia:
        1. run_collection_phase  (Fase 2)
        2. run_processing_phase  (Fase 3)
        3. run_strategy_phase    (Fase 6+)

        Erros em cada fase sao capturados e registrados sem interromper as
        demais fases, garantindo maximo de dados processados mesmo em falhas
        parciais.

        Args:
            cycle_id: ID do ciclo corrente no Swarm Genesis. Se None, cria um
                novo ciclo automaticamente para fins de rastreamento.

        Returns:
            Dict com chave 'cycle_id' e sub-dict 'phases' contendo os stats
            de cada fase.
        """
        # Se nao foi fornecido um cycle_id, cria um ciclo temporario para
        # fins de rastreabilidade no action_log.
        own_cycle = False
        if cycle_id is None:
            try:
                cycle_id = self.swarm_db.start_cycle()
                own_cycle = True
                logger.info("Ciclo EKAS autonomo iniciado (id=%d)", cycle_id)
            except Exception as exc:
                logger.warning("Nao foi possivel criar ciclo no SwarmDB: %s", exc)

        results: Dict[str, Any] = {"cycle_id": cycle_id, "phases": {}}

        # --- Fase 2: Coleta ---
        print("[EKAS] Fase 2: COLETA EXTERNA...")
        try:
            col_stats = self.run_collection_phase(cycle_id)
        except Exception as exc:
            logger.exception("Falha critica na fase de coleta")
            col_stats = {"watches_checked": 0, "items_found": 0, "items_new": 0, "errors": [str(exc)]}
        results["phases"]["collection"] = col_stats
        print(f"  Watches verificados : {col_stats['watches_checked']}")
        print(f"  Itens encontrados   : {col_stats['items_found']}")
        print(f"  Itens novos         : {col_stats['items_new']}")
        if col_stats.get("errors"):
            print(f"  Erros               : {len(col_stats['errors'])}")

        # --- Fase 3: Processamento ---
        print("[EKAS] Fase 3: PROCESSAMENTO IA...")
        try:
            proc_stats = self.run_processing_phase(cycle_id)
        except Exception as exc:
            logger.exception("Falha critica na fase de processamento")
            proc_stats = {
                "processed": 0, "failed": 0, "features_found": 0,
                "competitors_found": 0, "tutorials_found": 0,
                "opportunities_found": 0, "tokens_used": 0,
                "errors": [str(exc)],
            }
        results["phases"]["processing"] = proc_stats
        print(f"  Processados         : {proc_stats['processed']}")
        print(f"  Falhas              : {proc_stats['failed']}")
        print(f"  Features            : {proc_stats['features_found']}")
        print(f"  Concorrentes        : {proc_stats['competitors_found']}")
        print(f"  Tutoriais           : {proc_stats['tutorials_found']}")
        print(f"  Oportunidades       : {proc_stats['opportunities_found']}")
        print(f"  Tokens utilizados   : {proc_stats['tokens_used']}")

        # --- Fase 6+: Estrategia ---
        print("[EKAS] Fase 6+: ESTRATEGIA...")
        try:
            strat_stats = self.run_strategy_phase(cycle_id)
        except Exception as exc:
            logger.exception("Falha critica na fase de estrategia")
            strat_stats = {"roadmap_items": 0, "opportunities_analyzed": 0, "errors": [str(exc)]}
        results["phases"]["strategy"] = strat_stats
        print(f"  Sugestoes de roadmap: {strat_stats['roadmap_items']}")
        print(f"  Oportunidades analis: {strat_stats['opportunities_analyzed']}")

        # Fecha o ciclo autonomo se foi criado por este metodo
        if own_cycle and cycle_id is not None:
            try:
                total_tokens = proc_stats.get("tokens_used", 0)
                summary = (
                    f"EKAS cycle | col={col_stats['items_new']} novos | "
                    f"proc={proc_stats['processed']} | tokens={total_tokens}"
                )
                self.swarm_db.end_cycle(cycle_id, summary=summary)
                logger.info("Ciclo EKAS autonomo finalizado (id=%d)", cycle_id)
            except Exception as exc:
                logger.warning("Nao foi possivel fechar ciclo %d: %s", cycle_id, exc)

        return results

    # =======================================================================
    # CONVENIENCIA: fetch + process imediato
    # =======================================================================
    def add_source_and_process(
        self,
        source_type: str,
        url: str,
        title: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Busca uma URL, persiste no ekas.db e processa imediatamente via IA.

        Util para adicionar fontes pontuais sem esperar pelo ciclo completo.

        Args:
            source_type: Tipo da fonte — "youtube", "web", "docs", "github",
                "manual". Deve corresponder a um collector registrado.
            url: URL ou ID da fonte a buscar.
            title: Titulo opcional. Se None, usa o titulo extraido pelo collector.
            project_id: Projeto ao qual associar a fonte. Usa self.project_id
                se nao informado.

        Returns:
            Dict com: source_id, title, relevance, features, competitors,
            tutorials, opportunities, tokens. Em caso de erro, retorna
            {'error': <mensagem>}.
        """
        collector = self.collectors.get(source_type.lower())
        if collector is None:
            return {
                "error": f"Tipo de fonte desconhecido: '{source_type}'. "
                         f"Disponiveis: {list(self.collectors.keys())}"
            }

        # ----- Coleta -----
        content = None
        try:
            content = collector.fetch(url)
        except Exception as exc:
            return {"error": f"Erro ao buscar '{url}': {exc}"}

        if content is None:
            return {"error": f"Collector nao retornou conteudo para: '{url}'"}

        pid = project_id or self.project_id
        effective_title = title or content.title or url

        # ----- Persiste fonte -----
        try:
            sid = self.ekas_db.add_source(
                source_type=content.source_type,
                source_url=content.source_url,
                title=effective_title,
                project_id=pid,
                source_id=content.source_id,
                author=content.author,
                author_channel=content.author_channel,
                published_at=content.published_at,
                raw_text=content.raw_text,
                metadata=content.metadata,
                tags=content.tags,
            )
        except Exception as exc:
            return {"error": f"Erro ao salvar fonte no ekas.db: {exc}"}

        if sid <= 0:
            return {
                "error": "Fonte ja existe ou nao foi possivel salvar (sid <= 0)",
                "source_id": sid,
            }

        # ----- Processa via pipeline -----
        try:
            self.ekas_db.update_source_status(sid, "PROCESSING")
            result = self.pipeline.process(
                title=effective_title,
                raw_text=content.raw_text,
                source_type=content.source_type,
                metadata=content.metadata,
                source_id=sid,
            )
        except Exception as exc:
            self.ekas_db.update_source_status(sid, "FAILED")
            return {"error": f"Erro no pipeline de IA: {exc}", "source_id": sid}

        # ----- Persiste resultados -----
        try:
            self.ekas_db.update_source_summaries(
                sid,
                summary_short=result.summary_short,
                summary_medium=result.summary_medium,
                summary_full=result.summary_full,
                relevance_score=result.relevance_score,
                tags=result.tags_generated,
            )

            for comp in result.competitors_mentioned:
                comp_name = (comp.get("name") or "").strip()
                if not comp_name:
                    continue
                cid = self.ekas_db.add_competitor(
                    name=comp_name,
                    project_id=pid,
                    category=comp.get("category"),
                    strengths=comp.get("strengths") or [],
                    weaknesses=comp.get("weaknesses") or [],
                )
                if cid:
                    try:
                        self.ekas_db.link_source_to_competitor(cid, sid)
                    except Exception:
                        pass

            for feat in result.features_detected:
                feat_name = (feat.get("name") or "").strip()
                if not feat_name:
                    continue
                self.ekas_db.add_feature(
                    name=feat_name,
                    project_id=pid,
                    category=feat.get("category"),
                    description=feat.get("description"),
                )

            for tut in result.tutorials_extracted:
                tut_steps = tut.get("steps") or []
                if not tut_steps:
                    continue
                self.ekas_db.add_tutorial(
                    title=tut.get("title") or effective_title,
                    steps=tut_steps,
                    source_id=sid,
                    project_id=pid,
                    prerequisites=tut.get("prerequisites"),
                    difficulty=tut.get("difficulty"),
                    estimated_time=tut.get("estimated_time"),
                )

            for opp in result.opportunities:
                opp_title = (opp.get("title") or "").strip()
                if not opp_title:
                    continue
                self.ekas_db.add_opportunity(
                    type=opp.get("type") or "gap",
                    title=opp_title,
                    project_id=pid,
                    description=opp.get("description"),
                    impact_score=float(opp.get("impact_score") or 0),
                    effort_score=float(opp.get("effort_score") or 0),
                    evidence=[{"source_id": sid, "title": effective_title}],
                )

            self.ekas_db.update_source_status(sid, "PROCESSED")

        except Exception as exc:
            logger.exception("Erro ao persistir resultados do pipeline para fonte %d", sid)
            # Fonte foi processada mas pode ter dados parciais — nao marca FAILED
            # pois o resumo ja foi salvo.
            return {
                "source_id": sid,
                "title": effective_title,
                "warning": f"Dados parcialmente salvos: {exc}",
                "relevance": result.relevance_score,
                "features": len(result.features_detected),
                "competitors": len(result.competitors_mentioned),
                "tutorials": len(result.tutorials_extracted),
                "opportunities": len(result.opportunities),
                "tokens": result.tokens_used,
            }

        logger.info(
            "Fonte adicionada e processada | id=%d | relevancia=%.2f | tokens=%d",
            sid,
            result.relevance_score,
            result.tokens_used,
        )

        return {
            "source_id": sid,
            "title": effective_title,
            "relevance": result.relevance_score,
            "features": len(result.features_detected),
            "competitors": len(result.competitors_mentioned),
            "tutorials": len(result.tutorials_extracted),
            "opportunities": len(result.opportunities),
            "tokens": result.tokens_used,
        }

    # =======================================================================
    # HELPERS INTERNOS
    # =======================================================================
    def _map_watch_to_collector(self, watch_type: str) -> str:
        """Mapeia um watch_type para o nome do collector correspondente.

        Args:
            watch_type: String do tipo de watch (ex: 'keyword', 'channel').

        Returns:
            Nome da chave em self.collectors. Retorna 'web' como fallback.
        """
        return _WATCH_TYPE_TO_COLLECTOR.get(watch_type.lower(), "web")

    def _persist_collection_result(
        self,
        result: Any,
        project_id: Optional[str] = None,
    ) -> tuple[int, int]:
        """Persiste os items de um CollectionResult no ekas.db.

        Itens duplicados (mesma source_url) sao ignorados silenciosamente pela
        constraint UNIQUE do schema — add_source retorna <= 0 nesses casos.

        Args:
            result: Objeto CollectionResult retornado por um collector.
            project_id: Projeto ao qual associar os itens.

        Returns:
            Tupla (total_encontrado, total_novo).
        """
        if result is None:
            return 0, 0

        total_found: int = getattr(result, "total_found", 0) or len(
            getattr(result, "items", [])
        )
        new_count = 0

        for item in getattr(result, "items", []):
            try:
                sid = self.ekas_db.add_source(
                    source_type=getattr(item, "source_type", "unknown"),
                    source_url=getattr(item, "source_url", ""),
                    title=getattr(item, "title", ""),
                    project_id=project_id,
                    source_id=getattr(item, "source_id", ""),
                    author=getattr(item, "author", ""),
                    author_channel=getattr(item, "author_channel", ""),
                    published_at=getattr(item, "published_at", ""),
                    raw_text=getattr(item, "raw_text", ""),
                    metadata=getattr(item, "metadata", {}),
                    tags=getattr(item, "tags", []),
                )
                if sid and sid > 0:
                    new_count += 1
            except Exception as exc:
                logger.warning("Erro ao persistir item '%s': %s", getattr(item, "source_url", "?"), exc)

        return total_found, new_count

    def _log_action(
        self,
        *,
        cycle_id: Optional[int],
        agent: str,
        action: str,
        target: str = "",
        result: str = "success",
        details: str = "",
        tokens_used: int = 0,
        duration_ms: int = 0,
    ) -> None:
        """Registra uma acao no action_log do SwarmDB de forma silenciosa.

        Erros de log nao interrompem o fluxo principal. Se cycle_id for None,
        a acao ainda e registrada com cycle_id=0 para rastreabilidade.

        Args:
            cycle_id: ID do ciclo Genesis (pode ser None).
            agent: Nome do agente executor.
            action: Tipo de acao (ex: 'collection_phase_start').
            target: Alvo da acao (ex: 'ekas_watchlist').
            result: Resultado ('success', 'error', etc.).
            details: Detalhes serializados (tipicamente JSON).
            tokens_used: Tokens LLM consumidos nesta acao.
            duration_ms: Duracao em milissegundos.
        """
        try:
            self.swarm_db.log_action(
                cycle_id=cycle_id or 0,
                agent_name=agent,
                action_type=action,
                target=target,
                result=result,
                details=details,
                duration_ms=duration_ms,
                tokens_used=tokens_used,
            )
        except Exception as exc:
            logger.warning(
                "Nao foi possivel registrar action_log [%s/%s]: %s", agent, action, exc
            )


# ===========================================================================
# CLI
# ===========================================================================
def _build_parser():
    """Constroi o ArgumentParser do CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="EKAS Cycle Bridge — Integra EKAS ao Swarm Genesis v6",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Coleta todos os watches vencidos
  python cycle_bridge.py collect --project msm_pro

  # Processa até 30 fontes brutas
  python cycle_bridge.py process --project msm_pro --limit 30

  # Gera roadmap estratégico
  python cycle_bridge.py strategy --project msm_pro

  # Ciclo completo (coleta + processamento + estratégia)
  python cycle_bridge.py full-cycle --project msm_pro

  # Busca e processa um video YouTube imediatamente
  python cycle_bridge.py fetch-and-process \\
    --project msm_pro \\
    --source-type youtube \\
    --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

  # Exibe estatísticas do ekas.db
  python cycle_bridge.py status
        """,
    )

    parser.add_argument(
        "command",
        choices=["collect", "process", "strategy", "full-cycle", "fetch-and-process", "status"],
        help="Comando a executar",
    )
    parser.add_argument(
        "--project",
        default="msm_pro",
        help="ID do projeto EKAS (default: msm_pro)",
    )
    parser.add_argument(
        "--context",
        default="",
        help="Contexto textual do projeto para pontuar relevancia na IA",
    )
    parser.add_argument(
        "--cycle-id",
        type=int,
        default=None,
        help="ID de ciclo existente no Swarm Genesis (opcional)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="URL ou ID da fonte (necessario para fetch-and-process)",
    )
    parser.add_argument(
        "--source-type",
        default="youtube",
        choices=["youtube", "web", "docs", "manual", "github"],
        help="Tipo de collector (default: youtube)",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Titulo opcional para a fonte (fetch-and-process)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximo de fontes a processar por chamada (default: 20)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Habilita logging DEBUG",
    )

    return parser


def main() -> None:
    """Ponto de entrada do CLI do EKAS Cycle Bridge."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ----- Resolve contexto do projeto -----
    context = args.context
    if not context:
        try:
            tmp_db = EkasDB()
            project = tmp_db.get_project(args.project)
            if project:
                context = f"{project['name']} - {project.get('description', '')}".strip(" -")
        except Exception:
            pass

    bridge = EkasCycleBridge(
        project_id=args.project,
        project_context=context,
    )

    # ----- Dispatch de comandos -----
    if args.command == "collect":
        result = bridge.run_collection_phase(args.cycle_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "process":
        result = bridge.run_processing_phase(args.cycle_id, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "strategy":
        result = bridge.run_strategy_phase(args.cycle_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "full-cycle":
        result = bridge.run_full_ekas_cycle(args.cycle_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "fetch-and-process":
        if not args.url:
            print(json.dumps(
                {"error": "Argumento --url e obrigatorio para fetch-and-process"},
                ensure_ascii=False,
            ))
            sys.exit(1)
        result = bridge.add_source_and_process(
            source_type=args.source_type,
            url=args.url,
            title=args.title,
            project_id=args.project,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "status":
        try:
            ekas_stats = bridge.ekas_db.get_stats()
            swarm_ctx = bridge.swarm_db.get_current_cycle()
            output = {
                "ekas": ekas_stats,
                "swarm_current_cycle": swarm_ctx,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            output = {"error": str(exc)}
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
