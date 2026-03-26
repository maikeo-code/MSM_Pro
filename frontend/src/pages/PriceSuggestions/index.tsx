import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Sparkles,
  RefreshCw,
  Package,
  Eye,
  ShoppingCart,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Check,
  X,
  Target,
  BarChart3,
  Loader2,
  Tag,
} from "lucide-react";
import {
  getRecommendations,
  applyRecommendation,
  dismissRecommendation,
  generateRecommendations,
  type PriceRecommendation,
  type ConversionIndex,
} from "@/services/pricingService";
import { formatCurrency, cn } from "@/lib/utils";
import { useActiveAccount } from "@/hooks/useActiveAccount";

// ─── Confidence Badge ──────────────────────────────────────────────────────────
function ConfidenceBadge({ confidence }: { confidence: "high" | "medium" | "low" }) {
  const styles = {
    high: "bg-green-100 text-green-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-gray-100 text-gray-600",
  };
  const labels = { high: "Alta", medium: "Media", low: "Baixa" };
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", styles[confidence])}>
      {labels[confidence]}
    </span>
  );
}

// ─── Risk Badge ────────────────────────────────────────────────────────────────
function RiskBadge({ risk }: { risk: "low" | "medium" | "high" }) {
  const styles = {
    low: "bg-green-100 text-green-700",
    medium: "bg-orange-100 text-orange-700",
    high: "bg-red-100 text-red-700",
  };
  const labels = { low: "Baixo", medium: "Medio", high: "Alto" };
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", styles[risk])}>
      <AlertTriangle className="h-3 w-3 mr-1" />
      {labels[risk]}
    </span>
  );
}

// ─── Urgency Badge ─────────────────────────────────────────────────────────────
function UrgencyBadge({ urgency }: { urgency: "immediate" | "next_48h" | "monitor" }) {
  const styles = {
    immediate: "bg-red-100 text-red-700 border-red-200",
    next_48h: "bg-yellow-100 text-yellow-700 border-yellow-200",
    monitor: "bg-blue-100 text-blue-700 border-blue-200",
  };
  const labels = { immediate: "Imediato", next_48h: "48h", monitor: "Monitorar" };
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium border", styles[urgency])}>
      {labels[urgency]}
    </span>
  );
}

// ─── Health Score Bar ──────────────────────────────────────────────────────────
function HealthScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-muted-foreground">--</span>;
  const color = score >= 67 ? "bg-green-500" : score >= 34 ? "bg-yellow-500" : "bg-red-500";
  const textColor = score >= 67 ? "text-green-700" : score >= 34 ? "text-yellow-700" : "text-red-700";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${Math.min(100, score)}%` }} />
      </div>
      <span className={cn("text-xs font-medium", textColor)}>{score}</span>
    </div>
  );
}

// ─── Conversion Trend Badge ────────────────────────────────────────────────────
function ConversionTrendBadge({
  convIndex,
  convYesterday,
  conv7d,
}: {
  convIndex: ConversionIndex | null;
  convYesterday: number;
  conv7d: number;
}) {
  if (!convIndex && conv7d === 0) return null;

  // Determinar direcao: ontem vs 7d
  const diff = conv7d > 0 ? ((convYesterday - conv7d) / conv7d) * 100 : 0;
  const isUp = diff > 2;
  const isDown = diff < -2;

  const bgColor = isUp
    ? "bg-green-100 border-green-300"
    : isDown
      ? "bg-red-100 border-red-300"
      : "bg-gray-100 border-gray-300";
  const textColor = isUp ? "text-green-700" : isDown ? "text-red-700" : "text-gray-600";
  const arrow = isUp ? "^" : isDown ? "v" : "=";
  const label = isUp ? "SUBINDO" : isDown ? "CAINDO" : "ESTAVEL";

  return (
    <div className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold", bgColor, textColor)}>
      <span className="text-sm">{arrow === "^" ? "\u2191" : arrow === "v" ? "\u2193" : "\u2194"}</span>
      <span>CONVERSAO: {label}</span>
      {diff !== 0 && (
        <span className="font-semibold">
          ({diff > 0 ? "+" : ""}{diff.toFixed(0)}%)
        </span>
      )}
    </div>
  );
}

// ─── Price Change Display ──────────────────────────────────────────────────────
function PriceChange({
  current,
  suggested,
  pct,
  action,
}: {
  current: number;
  suggested: number;
  pct: number;
  action: "increase" | "decrease" | "hold";
}) {
  const arrowColor =
    action === "increase" ? "text-green-600" : action === "decrease" ? "text-red-600" : "text-gray-500";
  const pctColor =
    action === "increase" ? "text-green-600" : action === "decrease" ? "text-red-600" : "text-gray-500";

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm font-medium text-muted-foreground">{formatCurrency(current)}</span>
      {action !== "hold" ? (
        <>
          <span className={arrowColor}>
            {action === "increase" ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
          </span>
          <span className="text-sm font-bold text-foreground">{formatCurrency(suggested)}</span>
          <span className={cn("text-xs font-semibold", pctColor)}>
            ({pct > 0 ? "+" : ""}
            {pct.toFixed(1)}%)
          </span>
        </>
      ) : (
        <span className="text-xs text-gray-500 font-medium">Manter</span>
      )}
    </div>
  );
}

// ─── Skeleton Card ─────────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div className="rounded-lg border bg-card shadow-sm p-5 animate-pulse">
      <div className="flex items-start gap-4">
        <div className="h-12 w-12 rounded bg-muted" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-3/4 rounded bg-muted" />
          <div className="h-3 w-1/2 rounded bg-muted" />
          <div className="h-3 w-1/3 rounded bg-muted" />
        </div>
      </div>
      <div className="mt-4 grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-10 rounded bg-muted" />
        ))}
      </div>
    </div>
  );
}

// ─── Apply Confirmation Modal ──────────────────────────────────────────────────
function ApplyModal({
  rec,
  onConfirm,
  onCancel,
  isLoading,
}: {
  rec: PriceRecommendation;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-card rounded-lg border shadow-lg max-w-md w-full mx-4 p-6">
        <h3 className="text-lg font-bold text-foreground mb-4">Confirmar Alteracao de Preco</h3>

        <div className="space-y-3 mb-6">
          <div className="flex items-center gap-3">
            {rec.thumbnail ? (
              <img src={rec.thumbnail} alt={rec.title} className="h-12 w-12 rounded object-cover border" />
            ) : (
              <div className="h-12 w-12 rounded bg-muted flex items-center justify-center">
                <Package className="h-5 w-5 text-muted-foreground/50" />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground line-clamp-2">{rec.title}</p>
              <p className="text-xs text-muted-foreground font-mono">{rec.mlb_id}</p>
            </div>
          </div>

          <div className="rounded-md bg-muted/50 p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Preco atual:</span>
              <span className="font-medium">{formatCurrency(rec.current_price)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Preco sugerido:</span>
              <span className="font-bold text-foreground">{formatCurrency(rec.suggested_price)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Variacao:</span>
              <span
                className={cn(
                  "font-medium",
                  rec.action === "increase" ? "text-green-600" : rec.action === "decrease" ? "text-red-600" : "",
                )}
              >
                {rec.price_change_pct > 0 ? "+" : ""}
                {rec.price_change_pct.toFixed(1)}%
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Confianca:</span>
              <ConfidenceBadge confidence={rec.confidence} />
            </div>
          </div>

          <p className="text-xs text-muted-foreground italic">{rec.reasoning}</p>

          {/* Promotion warning */}
          {rec.has_active_promotion && (
            <div className="flex items-start gap-2 rounded-md bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800">
              <Tag className="h-4 w-4 shrink-0 mt-0.5 text-amber-600" />
              <span>
                <strong>Promocao ativa</strong> — alterar o preco pode desativar a promocao vigente neste anuncio.
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent transition-colors disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-60"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Aplicando...
              </>
            ) : (
              <>
                <Check className="h-4 w-4" />
                Confirmar
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Recommendation Card ───────────────────────────────────────────────────────
function RecommendationCard({
  rec,
  onApply,
  onDismiss,
}: {
  rec: PriceRecommendation;
  onApply: (rec: PriceRecommendation) => void;
  onDismiss: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const borderColor =
    rec.action === "increase"
      ? "border-l-4 border-l-green-500 bg-green-50/50"
      : rec.action === "decrease"
        ? "border-l-4 border-l-red-500 bg-red-50/50"
        : "border-l-4 border-l-gray-400 bg-gray-50/50";

  return (
    <div className={cn("rounded-lg border bg-card shadow-sm hover:shadow-md transition-shadow p-5", borderColor)}>
      {/* Header: Thumbnail + Info + Price */}
      <div className="flex items-start gap-4">
        {/* Thumbnail */}
        {rec.thumbnail ? (
          <img src={rec.thumbnail} alt={rec.title} className="h-12 w-12 rounded object-cover shrink-0 border" />
        ) : (
          <div className="h-12 w-12 rounded bg-muted flex items-center justify-center shrink-0">
            <Package className="h-5 w-5 text-muted-foreground/50" />
          </div>
        )}

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {rec.sku && (
              <span className="inline-flex items-center rounded-full bg-blue-100 text-blue-700 px-2 py-0.5 text-xs font-medium">
                SKU: {rec.sku}
              </span>
            )}
            <span className="text-xs text-muted-foreground font-mono">{rec.mlb_id}</span>
          </div>
          <p className="text-sm font-medium text-foreground line-clamp-2 leading-tight">{rec.title}</p>

          {/* Price change */}
          <div className="mt-2">
            <PriceChange
              current={rec.current_price}
              suggested={rec.suggested_price}
              pct={rec.price_change_pct}
              action={rec.action}
            />
          </div>
        </div>

        {/* Badges column */}
        <div className="flex flex-col gap-1.5 items-end shrink-0">
          <ConfidenceBadge confidence={rec.confidence} />
          <RiskBadge risk={rec.risk_level} />
          <UrgencyBadge urgency={rec.urgency} />
          {rec.has_active_promotion && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-700 border border-amber-200 px-2 py-0.5 text-xs font-medium">
              <Tag className="h-3 w-3" />
              Promo ativa
            </span>
          )}
        </div>
      </div>

      {/* Mini Metrics — Conversion Badge + Periods Table */}
      <div className="mt-4 space-y-3">
        {/* Conversion Trend Badge — principal indice */}
        {rec.periods_data && (
          <ConversionTrendBadge
            convIndex={rec.conversion_index}
            convYesterday={rec.periods_data.yesterday?.conversion ?? 0}
            conv7d={rec.periods_data.last_7d?.conversion ?? 0}
          />
        )}

        {/* Periods comparison table — "Hoje" NAO aparece como coluna de comparacao */}
        {rec.periods_data && (
          <div className="rounded-md border overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-muted/60">
                  <th className="text-left px-3 py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground font-medium">Metrica</th>
                  <th className="text-center px-2 py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground font-medium">Ontem</th>
                  <th className="text-center px-2 py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground font-medium">Anteontem</th>
                  <th className="text-center px-2 py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground font-medium">7 dias</th>
                  <th className="text-center px-2 py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground font-medium">15 dias</th>
                  <th className="text-center px-2 py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground font-medium">30 dias</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t bg-blue-50/30">
                  <td className="px-3 py-1.5 text-muted-foreground font-bold">Conversao</td>
                  <td className="text-center px-2 py-1.5 font-bold">{rec.periods_data.yesterday?.conversion != null ? `${rec.periods_data.yesterday.conversion.toFixed(1)}%` : "--"}</td>
                  <td className="text-center px-2 py-1.5 font-semibold">{rec.periods_data.day_before?.conversion != null ? `${rec.periods_data.day_before.conversion.toFixed(1)}%` : "--"}</td>
                  <td className="text-center px-2 py-1.5 font-semibold">{rec.periods_data.last_7d?.conversion != null ? `${rec.periods_data.last_7d.conversion.toFixed(1)}%` : "--"}</td>
                  <td className="text-center px-2 py-1.5 font-semibold">{rec.periods_data.last_15d?.conversion != null ? `${rec.periods_data.last_15d.conversion.toFixed(1)}%` : "--"}</td>
                  <td className="text-center px-2 py-1.5 font-semibold">{rec.periods_data.last_30d?.conversion != null ? `${rec.periods_data.last_30d.conversion.toFixed(1)}%` : "--"}</td>
                </tr>
                <tr className="border-t">
                  <td className="px-3 py-1.5 text-muted-foreground font-medium flex items-center gap-1"><Eye className="h-3 w-3" />Visitas</td>
                  <td className="text-center px-2 py-1.5 font-semibold">{rec.periods_data.yesterday?.visits != null ? rec.periods_data.yesterday.visits.toLocaleString("pt-BR") : "--"}</td>
                  <td className="text-center px-2 py-1.5 font-semibold">{rec.periods_data.day_before?.visits != null ? rec.periods_data.day_before.visits.toLocaleString("pt-BR") : "--"}</td>
                  <td className="text-center px-2 py-1.5 font-semibold">
                    {rec.periods_data.last_7d?.visits != null ? (
                      <>{rec.periods_data.last_7d.visits.toLocaleString("pt-BR")} <span className="text-[10px] text-muted-foreground font-normal">(~{(rec.periods_data.last_7d.visits / 7).toFixed(1)}/d)</span></>
                    ) : "--"}
                  </td>
                  <td className="text-center px-2 py-1.5 font-semibold">
                    {rec.periods_data.last_15d?.visits != null ? (
                      <>{rec.periods_data.last_15d.visits.toLocaleString("pt-BR")} <span className="text-[10px] text-muted-foreground font-normal">(~{(rec.periods_data.last_15d.visits / 15).toFixed(1)}/d)</span></>
                    ) : "--"}
                  </td>
                  <td className="text-center px-2 py-1.5 font-semibold">
                    {rec.periods_data.last_30d?.visits != null ? (
                      <>{rec.periods_data.last_30d.visits.toLocaleString("pt-BR")} <span className="text-[10px] text-muted-foreground font-normal">(~{(rec.periods_data.last_30d.visits / 30).toFixed(1)}/d)</span></>
                    ) : "--"}
                  </td>
                </tr>
                <tr className="border-t">
                  <td className="px-3 py-1.5 text-muted-foreground font-medium flex items-center gap-1"><ShoppingCart className="h-3 w-3" />Vendas</td>
                  <td className="text-center px-2 py-1.5 font-semibold">{rec.periods_data.yesterday?.sales ?? "--"}</td>
                  <td className="text-center px-2 py-1.5 font-semibold">{rec.periods_data.day_before?.sales ?? "--"}</td>
                  <td className="text-center px-2 py-1.5 font-semibold">
                    {rec.periods_data.last_7d?.sales != null ? (
                      <>{rec.periods_data.last_7d.sales} <span className="text-[10px] text-muted-foreground font-normal">(~{(rec.periods_data.last_7d.sales / 7).toFixed(1)}/d)</span></>
                    ) : "--"}
                  </td>
                  <td className="text-center px-2 py-1.5 font-semibold">
                    {rec.periods_data.last_15d?.sales != null ? (
                      <>{rec.periods_data.last_15d.sales} <span className="text-[10px] text-muted-foreground font-normal">(~{(rec.periods_data.last_15d.sales / 15).toFixed(1)}/d)</span></>
                    ) : "--"}
                  </td>
                  <td className="text-center px-2 py-1.5 font-semibold">
                    {rec.periods_data.last_30d?.sales != null ? (
                      <>{rec.periods_data.last_30d.sales} <span className="text-[10px] text-muted-foreground font-normal">(~{(rec.periods_data.last_30d.sales / 30).toFixed(1)}/d)</span></>
                    ) : "--"}
                  </td>
                </tr>
              </tbody>
            </table>
            {/* Tempo real (hoje) — separado, nao comparacao */}
            {rec.periods_data.today && (rec.periods_data.today.visits > 0 || rec.periods_data.today.sales > 0) && (
              <div className="px-3 py-1.5 bg-muted/30 border-t text-[10px] text-muted-foreground">
                Tempo real (hoje): {rec.periods_data.today.visits} visitas, {rec.periods_data.today.sales} vendas
                {rec.periods_data.today.conversion > 0 && ` (${rec.periods_data.today.conversion.toFixed(1)}% conv.)`}
              </div>
            )}
          </div>
        )}

        {/* Fallback: old-style metrics when periods_data not available */}
        {!rec.periods_data && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div className="rounded-md bg-muted/50 px-3 py-2">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium">Conversao 7d</p>
              <p className="text-sm font-semibold text-foreground">
                {rec.conversion_7d != null ? `${rec.conversion_7d.toFixed(1)}%` : "--"}
              </p>
            </div>
            <div className="rounded-md bg-muted/50 px-3 py-2">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium">Visitas 7d</p>
              <p className="text-sm font-semibold text-foreground flex items-center gap-1">
                <Eye className="h-3 w-3 text-muted-foreground/50" />
                {rec.visits_7d != null ? rec.visits_7d.toLocaleString("pt-BR") : "--"}
              </p>
            </div>
            <div className="rounded-md bg-muted/50 px-3 py-2">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium">Vendas 7d</p>
              <p className="text-sm font-semibold text-foreground flex items-center gap-1">
                <ShoppingCart className="h-3 w-3 text-muted-foreground/50" />
                {rec.sales_7d != null ? rec.sales_7d : "--"}
              </p>
            </div>
          </div>
        )}

        {/* Stock + Health row */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-md bg-muted/50 px-3 py-2">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium">Estoque</p>
            <p
              className={cn(
                "text-sm font-semibold",
                rec.stock != null && rec.stock < 10 ? "text-red-600" : "text-foreground",
              )}
            >
              {rec.stock != null ? rec.stock : "--"}
              {rec.stock_days_projection != null && (
                <span className="text-[10px] text-muted-foreground ml-1">({rec.stock_days_projection}d)</span>
              )}
            </p>
          </div>
          <div className="rounded-md bg-muted/50 px-3 py-2">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium">Health Score</p>
            <HealthScoreBar score={rec.health_score} />
          </div>
        </div>
      </div>

      {/* Competitor prices (if available) */}
      {(rec.competitor_avg_price != null || rec.competitor_min_price != null) && (
        <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
          {rec.competitor_avg_price != null && (
            <span>
              Concorrencia (media): <span className="font-medium text-foreground">{formatCurrency(rec.competitor_avg_price)}</span>
            </span>
          )}
          {rec.competitor_min_price != null && (
            <span>
              Menor preco: <span className="font-medium text-foreground">{formatCurrency(rec.competitor_min_price)}</span>
            </span>
          )}
        </div>
      )}

      {/* Reasoning (collapsible) */}
      <div className="mt-3">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          Analise da IA
        </button>
        {expanded && (
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed bg-muted/30 rounded-md p-3 border">
            {rec.reasoning}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="mt-4 flex items-center gap-2 border-t pt-3">
        {rec.status === "pending" && rec.action !== "hold" && (
          <button
            onClick={() => onApply(rec)}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Check className="h-3.5 w-3.5" />
            Aplicar
          </button>
        )}
        <Link
          to={`/anuncios/${rec.mlb_id}?simPreco=${rec.suggested_price}`}
          className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
        >
          <BarChart3 className="h-3.5 w-3.5" />
          Simular
        </Link>
        {rec.status === "pending" && (
          <button
            onClick={() => onDismiss(rec.id)}
            className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            <X className="h-3.5 w-3.5" />
            Ignorar
          </button>
        )}
        {rec.status === "applied" && (
          <span className="inline-flex items-center gap-1 rounded-full bg-green-100 text-green-700 px-2 py-0.5 text-xs font-medium">
            <Check className="h-3 w-3" />
            Aplicado
          </span>
        )}
        {rec.status === "dismissed" && (
          <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 text-gray-500 px-2 py-0.5 text-xs font-medium">
            Ignorado
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Summary Card ──────────────────────────────────────────────────────────────
function SummaryCard({
  label,
  count,
  icon,
  bgClass,
  textClass,
}: {
  label: string;
  count: number;
  icon: React.ReactNode;
  bgClass: string;
  textClass: string;
}) {
  return (
    <div className={cn("rounded-lg border p-5 flex items-center gap-4", bgClass)}>
      <div className={cn("rounded-full p-2.5", textClass, "bg-white/80")}>{icon}</div>
      <div>
        <p className={cn("text-2xl font-bold", textClass)}>{count}</p>
        <p className="text-sm text-muted-foreground font-medium">{label}</p>
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────
export default function PriceSuggestions() {
  const accountId = useActiveAccount();
  const queryClient = useQueryClient();
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [confidenceFilter, setConfidenceFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<string>("confidence");
  const [applyTarget, setApplyTarget] = useState<PriceRecommendation | null>(null);

  // ─── Queries ───────────────────────────────────────────────────────────────
  const {
    data: response,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["pricing-recommendations", actionFilter, confidenceFilter, sortBy, accountId],
    queryFn: () =>
      getRecommendations(
        {
          action: actionFilter !== "all" ? actionFilter : undefined,
          confidence: confidenceFilter !== "all" ? confidenceFilter : undefined,
          sort: sortBy,
        },
        accountId,
      ),
    retry: 2,
  });

  // ─── Mutations ─────────────────────────────────────────────────────────────
  const generateMutation = useMutation({
    mutationFn: () => generateRecommendations(accountId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pricing-recommendations"] });
    },
    onError: () => {
      alert("Erro ao gerar recomendacoes. Verifique se o backend esta online.");
    },
  });

  const applyMutation = useMutation({
    mutationFn: (id: string) => applyRecommendation(id),
    onSuccess: (data) => {
      setApplyTarget(null);
      queryClient.invalidateQueries({ queryKey: ["pricing-recommendations"] });
      const baseMsg = data.ml_api_success
        ? `Preco alterado com sucesso para ${data.mlb_id}!`
        : data.message;
      const promoMsg = data.promo_warning ? `\n\n${data.promo_warning}` : "";
      alert(baseMsg + promoMsg);
    },
    onError: () => {
      setApplyTarget(null);
      alert("Erro ao aplicar a recomendacao.");
    },
  });

  const dismissMutation = useMutation({
    mutationFn: (id: string) => dismissRecommendation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pricing-recommendations"] });
    },
  });

  const items = response?.items ?? [];
  const summary = response?.summary;
  const reportDate = response?.date;

  return (
    <div className="p-8">
      {/* ─── Apply Confirmation Modal ──────────────────────────────────────── */}
      {applyTarget && (
        <ApplyModal
          rec={applyTarget}
          onConfirm={() => applyMutation.mutate(applyTarget.id)}
          onCancel={() => setApplyTarget(null)}
          isLoading={applyMutation.isPending}
        />
      )}

      {/* ─── Header ────────────────────────────────────────────────────────── */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-foreground">Sugestao de Precos</h1>
        <p className="text-muted-foreground mt-1">
          Recomendacoes baseadas em IA
          {reportDate && (
            <span className="ml-2 text-xs text-muted-foreground/70">
              Atualizado: {new Date(reportDate).toLocaleDateString("pt-BR")}
            </span>
          )}
        </p>
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:from-blue-700 hover:to-violet-700 transition-all disabled:opacity-60"
          >
            {generateMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Gerando...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Gerar Agora
              </>
            )}
          </button>
          {generateMutation.isSuccess && generateMutation.data && (
            <span className="text-sm text-green-600 font-medium">
              {generateMutation.data.recommendations_count} recomendacoes geradas em{" "}
              {(generateMutation.data.processing_time_ms / 1000).toFixed(1)}s
            </span>
          )}
        </div>
      </div>

      {/* ─── Error Banner ──────────────────────────────────────────────────── */}
      {isError && (
        <div className="mb-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertTriangle className="h-5 w-5 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Erro ao carregar recomendacoes</p>
            <p className="mt-1">
              {(error as Error)?.message ?? "Nao foi possivel conectar a API."}
            </p>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ["pricing-recommendations"] })}
              className="mt-2 inline-flex items-center gap-1 text-red-800 underline text-xs font-medium"
            >
              <RefreshCw className="h-3 w-3" /> Tentar novamente
            </button>
          </div>
        </div>
      )}

      {/* ─── Summary Cards ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <SummaryCard
          label="Aumentar"
          count={summary?.increase_count ?? 0}
          icon={<TrendingUp className="h-5 w-5" />}
          bgClass="bg-green-50/50 border-green-200"
          textClass="text-green-600"
        />
        <SummaryCard
          label="Diminuir"
          count={summary?.decrease_count ?? 0}
          icon={<TrendingDown className="h-5 w-5" />}
          bgClass="bg-red-50/50 border-red-200"
          textClass="text-red-600"
        />
        <SummaryCard
          label="Manter"
          count={summary?.hold_count ?? 0}
          icon={<Minus className="h-5 w-5" />}
          bgClass="bg-gray-50/50 border-gray-200"
          textClass="text-gray-600"
        />
      </div>

      {/* ─── Filters ───────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-muted-foreground">Acao:</label>
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="all">Todos</option>
            <option value="increase">Aumentar</option>
            <option value="decrease">Diminuir</option>
            <option value="hold">Manter</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-muted-foreground">Confianca:</label>
          <select
            value={confidenceFilter}
            onChange={(e) => setConfidenceFilter(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="all">Todas</option>
            <option value="high">Alta</option>
            <option value="medium">Media</option>
            <option value="low">Baixa</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-muted-foreground">Ordenar:</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="confidence">Confianca</option>
            <option value="sku">SKU</option>
            <option value="price_change_pct">Variacao %</option>
          </select>
        </div>

        {(actionFilter !== "all" || confidenceFilter !== "all") && (
          <button
            onClick={() => {
              setActionFilter("all");
              setConfidenceFilter("all");
            }}
            className="text-xs text-muted-foreground hover:text-foreground underline transition-colors"
          >
            Limpar filtros
          </button>
        )}
      </div>

      {/* ─── Recommendation Cards ──────────────────────────────────────────── */}
      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border bg-card shadow-sm p-12 text-center">
          <Target className="h-16 w-16 text-muted-foreground/30 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">Nenhuma recomendacao disponivel</h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Clique em "Gerar Agora" para criar recomendacoes de preco baseadas nos seus dados de vendas,
            visitas e concorrencia.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((rec) => (
            <RecommendationCard
              key={rec.id}
              rec={rec}
              onApply={setApplyTarget}
              onDismiss={(id) => dismissMutation.mutate(id)}
            />
          ))}
        </div>
      )}

      {/* ─── Footer summary ────────────────────────────────────────────────── */}
      {items.length > 0 && summary && (
        <div className="mt-6 text-center text-xs text-muted-foreground">
          {summary.total} recomendacoes no total | Confianca media: {summary.avg_confidence}
        </div>
      )}
    </div>
  );
}
