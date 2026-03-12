import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RefreshCw, WifiOff, TrendingUp, TrendingDown, ShoppingCart, Package, DollarSign, Target, BarChart2, Sparkles, X, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import listingsService from "@/services/listingsService";
import { consultorService, type ConsultorResponse } from "@/services/consultorService";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";

// ─── Render simples de markdown: **bold**, listas (- item), paragrafos ────────
function RenderAnalise({ texto }: { texto: string }) {
  const paragrafos = texto.split(/\n\n+/);
  return (
    <div className="space-y-3 text-sm leading-relaxed text-gray-700">
      {paragrafos.map((paragrafo, i) => {
        const linhas = paragrafo.split("\n");
        const ehLista = linhas.every((l) => l.trim().startsWith("- ") || l.trim() === "");
        if (ehLista && linhas.some((l) => l.trim().startsWith("- "))) {
          return (
            <ul key={i} className="list-none space-y-1 pl-0">
              {linhas.filter((l) => l.trim().startsWith("- ")).map((item, j) => {
                const conteudo = item.replace(/^-\s+/, "");
                return (
                  <li key={j} className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
                    <span dangerouslySetInnerHTML={{ __html: conteudo.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>") }} />
                  </li>
                );
              })}
            </ul>
          );
        }
        const html = paragrafo.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        return (
          <p key={i} dangerouslySetInnerHTML={{ __html: html }} />
        );
      })}
    </div>
  );
}

// ─── Drawer do Consultor IA ───────────────────────────────────────────────────
interface ConsultorDrawerProps {
  aberto: boolean;
  onFechar: () => void;
  loading: boolean;
  resultado: ConsultorResponse | null;
  erro: string | null;
}

function ConsultorDrawer({ aberto, onFechar, loading, resultado, erro }: ConsultorDrawerProps) {
  return (
    <>
      {/* Overlay */}
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/30 backdrop-blur-sm transition-opacity duration-300",
          aberto ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        )}
        onClick={onFechar}
      />

      {/* Drawer */}
      <div
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex flex-col bg-white shadow-2xl transition-transform duration-300 ease-in-out",
          "w-full sm:w-[480px]",
          aberto ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header do drawer */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 bg-gradient-to-r from-blue-600 to-blue-700">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-white" />
            <h2 className="text-base font-semibold text-white">Consultor IA</h2>
          </div>
          <button
            onClick={onFechar}
            className="rounded-md p-1.5 text-white/70 hover:text-white hover:bg-white/20 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Corpo */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading && (
            <div className="flex flex-col items-center justify-center py-16 gap-4">
              <div className="relative">
                <Loader2 className="h-10 w-10 text-blue-600 animate-spin" />
                <div className="absolute inset-0 rounded-full bg-blue-50" style={{ zIndex: -1 }} />
              </div>
              <p className="text-sm text-gray-500 font-medium">Analisando seus anuncios...</p>
              <p className="text-xs text-gray-400 text-center max-w-xs">
                A IA esta processando seus dados de vendas, estoque e conversao para gerar insights personalizados.
              </p>
            </div>
          )}

          {erro && !loading && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <p className="font-semibold mb-1">Erro ao gerar analise</p>
              <p>{erro}</p>
            </div>
          )}

          {resultado && !loading && (
            <div className="space-y-4">
              <div className="rounded-lg bg-blue-50 border border-blue-100 px-4 py-3">
                <p className="text-xs text-blue-600 font-medium uppercase tracking-wide">Analise gerada</p>
              </div>
              <RenderAnalise texto={resultado.analise} />
            </div>
          )}

          {!loading && !erro && !resultado && (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
              <Sparkles className="h-10 w-10 text-blue-200" />
              <p className="text-sm text-gray-500">Clique em "Analisar" para gerar insights com IA</p>
            </div>
          )}
        </div>

        {/* Footer */}
        {resultado && !loading && (
          <div className="border-t border-gray-200 px-6 py-3 bg-gray-50">
            <p className="text-xs text-gray-500">
              {resultado.anuncios_analisados} anuncios analisados &bull;{" "}
              {new Date(resultado.gerado_em).toLocaleString("pt-BR", {
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          </div>
        )}
      </div>
    </>
  );
}

// ─── Componente de variacao (seta verde/vermelha) ───────────────────────────
function Variacao({ value, unit = "%" }: { value?: number | null; unit?: string }) {
  if (value == null) return null;
  const isPositive = value >= 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  const color = isPositive ? "text-green-600" : "text-red-500";
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${color}`}>
      <Icon className="h-3 w-3" />
      {Math.abs(value).toFixed(1)}{unit}
    </span>
  );
}

// ─── KPI Card com variacao ────────────────────────────────────────────────────
interface KpiCardProps {
  label: string;
  value: string;
  variacao?: number | null;
  icon: React.ReactNode;
  varUnit?: string;
}

function KpiCard({ label, value, variacao, icon, varUnit = "%" }: KpiCardProps) {
  return (
    <div className="rounded-lg border bg-card p-5 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground font-medium">{label}</p>
        <span className="text-muted-foreground/40">{icon}</span>
      </div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
      <Variacao value={variacao} unit={varUnit} />
    </div>
  );
}

// ─── Badge de dias para zerar estoque ────────────────────────────────────────
function DiasBadge({ dias }: { dias?: number | null }) {
  if (dias == null) {
    return <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs bg-gray-100 text-gray-500">—</span>;
  }
  if (dias > 30) {
    return <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800">{dias}d</span>;
  }
  if (dias >= 7) {
    return <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800">{dias}d</span>;
  }
  return <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800">{dias}d</span>;
}

export default function Dashboard() {
  const queryClient = useQueryClient();
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  // ─── Consultor IA ────────────────────────────────────────────────────────────
  const [consultorAberto, setConsultorAberto] = useState(false);
  const [consultorLoading, setConsultorLoading] = useState(false);
  const [consultorResultado, setConsultorResultado] = useState<ConsultorResponse | null>(null);
  const [consultorErro, setConsultorErro] = useState<string | null>(null);

  const handleConsultor = async () => {
    setConsultorAberto(true);
    if (consultorResultado) return; // ja tem resultado, so abre
    setConsultorLoading(true);
    setConsultorErro(null);
    try {
      const res = await consultorService.analisar();
      setConsultorResultado(res);
    } catch {
      setConsultorErro("Nao foi possivel gerar a analise. Verifique se o backend esta online.");
    } finally {
      setConsultorLoading(false);
    }
  };

  const { data: listings, isLoading, isError, error } = useQuery({
    queryKey: ["listings"],
    queryFn: () => listingsService.list(),
    retry: 2,
  });

  const { data: kpi } = useQuery({
    queryKey: ["kpi-summary"],
    queryFn: () => listingsService.getKpiSummary(),
    retry: 2,
  });

  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const result = await listingsService.sync();
      setSyncMsg(result.message);
      queryClient.invalidateQueries({ queryKey: ["listings"] });
      queryClient.invalidateQueries({ queryKey: ["kpi-summary"] });
    } catch {
      setSyncMsg("Erro ao sincronizar. Verifique se a conta ML está conectada.");
    } finally {
      setSyncing(false);
    }
  };

  const displayListings = listings ?? [];

  // Ordenar por vendas do dia (unidades vendidas) — maior primeiro
  const sortedListings = [...displayListings].sort((a, b) => {
    const salesA = a.last_snapshot?.sales_today ?? 0;
    const salesB = b.last_snapshot?.sales_today ?? 0;
    return salesB - salesA;
  });

  // Totais calculados da tabela
  const totalPedidos = displayListings.reduce((sum, l) => sum + (l.last_snapshot?.orders_count ?? l.last_snapshot?.sales_today ?? 0), 0);
  const totalUnidades = displayListings.reduce((sum, l) => sum + (l.last_snapshot?.sales_today ?? 0), 0);
  const totalReceita = displayListings.reduce((sum, l) => sum + (l.last_snapshot?.revenue ?? 0), 0);
  const totalEstoque = displayListings.reduce((sum, l) => sum + (l.last_snapshot?.stock ?? 0), 0);
  const totalEstoqueValor = displayListings.reduce((sum, l) => {
    const preco = l.sale_price ?? l.price;
    const estoque = l.last_snapshot?.stock ?? 0;
    return sum + preco * estoque;
  }, 0);

  const totalVisitas = sortedListings.reduce((sum, l) => sum + (l.last_snapshot?.visits ?? 0), 0);
  const avgConversao = totalVisitas > 0 ? (totalUnidades / totalVisitas) * 100 : 0;
  const avgPrecoMedio = totalUnidades > 0 ? totalReceita / totalUnidades : 0;
  // Preço médio por venda (receita / pedidos — diferente de receita / unidades)
  const avgPrecoMedioPorVenda = totalPedidos > 0 ? totalReceita / totalPedidos : 0;

  // Dados KPI para cards (usa periodo "hoje" ou soma dos listings)
  const kpiHoje = kpi?.hoje;

  return (
    <div className="p-8">
      {/* Drawer do Consultor IA */}
      <ConsultorDrawer
        aberto={consultorAberto}
        onFechar={() => setConsultorAberto(false)}
        loading={consultorLoading}
        resultado={consultorResultado}
        erro={consultorErro}
      />

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Visao geral dos seus anuncios no Mercado Livre
        </p>
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "Sincronizando..." : "Sincronizar ML"}
          </button>

          <button
            onClick={handleConsultor}
            className="inline-flex items-center gap-2 rounded-md bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:from-blue-700 hover:to-violet-700 transition-all"
          >
            <Sparkles className="h-4 w-4" />
            Consultor IA
          </button>

          {consultorResultado && (
            <button
              onClick={() => { setConsultorResultado(null); setConsultorErro(null); handleConsultor(); }}
              className="text-xs text-muted-foreground hover:text-foreground underline transition-colors"
            >
              Atualizar analise
            </button>
          )}

          {syncMsg && (
            <span className="text-sm text-muted-foreground">{syncMsg}</span>
          )}
        </div>
      </div>

      {/* Erro da API */}
      {isError && (
        <div className="mb-8 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <WifiOff className="h-5 w-5 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Erro ao carregar anuncios</p>
            <p className="mt-1">
              {(error as Error)?.message ?? "Nao foi possivel conectar a API."}
              {" "}Verifique se a conta ML esta conectada em{" "}
              <a href="/configuracoes" className="underline font-medium">Configuracoes</a>.
            </p>
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ["listings"] })}
              className="mt-2 inline-flex items-center gap-1 text-red-800 underline text-xs font-medium"
            >
              <RefreshCw className="h-3 w-3" /> Tentar novamente
            </button>
          </div>
        </div>
      )}

      {/* Nenhum anuncio */}
      {!isLoading && !isError && displayListings.length === 0 && (
        <div className="mb-8 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Nenhum anuncio encontrado</p>
            <p className="mt-1">
              Clique em <strong>"Sincronizar ML"</strong> acima para importar seus anuncios do Mercado Livre,
              ou conecte uma conta ML em{" "}
              <a href="/configuracoes" className="underline font-medium">Configuracoes</a>.
            </p>
          </div>
        </div>
      )}

      {/* ─── KPI Cards com variacao (estilo UpSeller) ─────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <KpiCard
          label="Pedidos Validos"
          value={String(kpiHoje?.pedidos ?? totalPedidos)}
          variacao={kpiHoje?.vendas_variacao}
          icon={<ShoppingCart className="h-5 w-5" />}
        />
        <KpiCard
          label="Unidades Vendidas"
          value={String(kpiHoje?.vendas ?? totalUnidades)}
          variacao={kpiHoje?.vendas_variacao}
          icon={<Package className="h-5 w-5" />}
        />
        <KpiCard
          label="Receita Total"
          value={formatCurrency(kpiHoje?.receita_total ?? kpiHoje?.receita ?? totalReceita)}
          variacao={kpiHoje?.receita_variacao}
          icon={<DollarSign className="h-5 w-5" />}
        />
        <KpiCard
          label="Preco Medio"
          value={formatCurrency(kpiHoje?.preco_medio ?? avgPrecoMedio)}
          variacao={null}
          icon={<BarChart2 className="h-5 w-5" />}
        />
        <KpiCard
          label="Conversao"
          value={formatPercent(kpiHoje?.conversao ?? avgConversao)}
          variacao={kpiHoje?.conversao_variacao}
          icon={<Target className="h-5 w-5" />}
        />
      </div>

      {/* ─── Tabela KPI por periodo ───────────────────────────────────────────── */}
      <div className="rounded-lg border bg-card shadow-sm mb-6">
        <div className="px-4 py-2 border-b">
          <h2 className="text-sm font-semibold text-foreground">Resumo por Periodo</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Periodo</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Anuncios</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Vendas</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Visitas</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Conversao</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Receita</th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Valor Estoque</th>
              </tr>
            </thead>
            <tbody>
              {[
                { label: "Hoje", data: kpi?.hoje },
                { label: "Ontem", data: kpi?.ontem },
                { label: "Anteontem", data: kpi?.anteontem },
                { label: "7 dias", data: kpi?.["7dias"] },
                { label: "30 dias", data: kpi?.["30dias"] },
              ].map(({ label, data }) => (
                <tr key={label} className="border-b hover:bg-muted/50">
                  <td className="px-4 py-2 font-medium text-foreground">{label}</td>
                  <td className="px-4 py-2 text-right text-foreground">{data?.anuncios ?? "-"}</td>
                  <td className="px-4 py-2 text-right font-medium text-foreground">{data?.vendas ?? "-"}</td>
                  <td className="px-4 py-2 text-right text-foreground">{data?.visitas?.toLocaleString("pt-BR") ?? "-"}</td>
                  <td className="px-4 py-2 text-right text-foreground">
                    {data?.conversao != null ? `${data.conversao.toFixed(2)}%` : "-"}
                  </td>
                  <td className="px-4 py-2 text-right font-medium text-green-600">
                    {data?.receita != null && data.receita > 0 ? formatCurrency(data.receita) : "-"}
                  </td>
                  <td className="px-4 py-2 text-right font-medium text-foreground">
                    {data?.valor_estoque != null ? formatCurrency(data.valor_estoque) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Card total estoque atual */}
      {displayListings.length > 0 && (
        <div className="rounded-lg border bg-card shadow-sm mb-6 px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Valor Total em Estoque (atual)</p>
            <p className="text-xs text-muted-foreground mt-0.5">Soma de todos os anuncios ativos × estoque × preco com desconto</p>
          </div>
          <p className="text-2xl font-bold text-green-600">{formatCurrency(totalEstoqueValor)}</p>
        </div>
      )}

      {/* ─── Tabela de anuncios estilo UpSeller ──────────────────────────────── */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-foreground">Anuncios Ativos</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Produto</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Pedidos</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Unidades</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Receita (R$)</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Você Recebe</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Preco/Unidade</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Preco/Venda</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Participacao</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Conversao</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Estoque</th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Dias p/ Zerar</th>
                <th className="px-4 py-3 text-center font-medium text-muted-foreground">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={12} className="px-6 py-8 text-center text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : displayListings.length === 0 ? (
                <tr>
                  <td colSpan={12} className="px-6 py-8 text-center text-muted-foreground">
                    Nenhum anuncio encontrado. Sincronize para importar do Mercado Livre.
                  </td>
                </tr>
              ) : (
                <>
                  {sortedListings.map((listing) => {
                    const effectivePrice = listing.sale_price ?? listing.price;
                    const snap = listing.last_snapshot;
                    const pedidos = snap?.orders_count ?? snap?.sales_today ?? 0;
                    const unidades = snap?.sales_today ?? 0;
                    const receita = snap?.revenue ?? (unidades * effectivePrice);
                    const precoMedio = snap?.avg_selling_price ?? (unidades > 0 ? receita / unidades : effectivePrice);
                    // Preço médio por VENDA (receita / pedidos — 1 pedido pode ter N unidades)
                    const precoMedioPorVenda = listing.avg_price_per_sale ?? (pedidos > 0 ? receita / pedidos : null);
                    const participacao = listing.participacao_pct;
                    const conversao = snap?.conversion_rate;
                    const estoque = snap?.stock;
                    const diasParaZerar = listing.dias_para_zerar;

                    return (
                      <tr
                        key={listing.id}
                        className="border-b hover:bg-muted/50 transition-colors"
                      >
                        {/* Produto: thumbnail + titulo + MLB ID + SKU */}
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            {listing.thumbnail ? (
                              <img
                                src={listing.thumbnail}
                                alt={listing.title}
                                className="h-10 w-10 rounded object-cover shrink-0 border"
                              />
                            ) : (
                              <div className="h-10 w-10 rounded bg-muted flex items-center justify-center shrink-0">
                                <Package className="h-4 w-4 text-muted-foreground/50" />
                              </div>
                            )}
                            <div className="min-w-0">
                              <p className="font-medium text-foreground line-clamp-1 text-xs leading-tight">
                                {listing.title}
                              </p>
                              <p className="text-xs text-muted-foreground mt-0.5 font-mono">
                                {listing.mlb_id}
                                {listing.seller_sku && ` · SKU: ${listing.seller_sku}`}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right font-medium">
                          {pedidos > 0 ? pedidos : "-"}
                        </td>
                        <td className="px-4 py-3 text-right font-medium">
                          {unidades > 0 ? unidades : "-"}
                        </td>
                        <td className="px-4 py-3 text-right font-medium text-green-600">
                          {receita > 0 ? formatCurrency(receita) : "-"}
                        </td>
                        {/* Você Recebe */}
                        <td className="px-4 py-3 text-right font-semibold text-green-600">
                          {listing.voce_recebe != null ? formatCurrency(listing.voce_recebe) : "-"}
                        </td>
                        {/* Preco/Unidade */}
                        <td className="px-4 py-3 text-right">
                          {formatCurrency(precoMedio)}
                        </td>
                        {/* ITEM 1: Preco/Venda */}
                        <td className="px-4 py-3 text-right">
                          {precoMedioPorVenda != null ? (
                            <span className="text-blue-700 font-medium">{formatCurrency(precoMedioPorVenda)}</span>
                          ) : "-"}
                        </td>
                        {/* ITEM 2: Participacao % */}
                        <td className="px-4 py-3 text-right">
                          {participacao != null ? (
                            <div className="flex flex-col items-end gap-0.5">
                              <span className={cn(
                                "text-xs font-semibold",
                                participacao >= 30 ? "text-green-700" : participacao >= 10 ? "text-yellow-700" : "text-muted-foreground"
                              )}>
                                {participacao.toFixed(1)}%
                              </span>
                              <div className="w-12 h-1 rounded-full bg-muted overflow-hidden">
                                <div
                                  className={cn(
                                    "h-full rounded-full",
                                    participacao >= 30 ? "bg-green-500" : participacao >= 10 ? "bg-yellow-500" : "bg-gray-400"
                                  )}
                                  style={{ width: `${Math.min(100, participacao)}%` }}
                                />
                              </div>
                            </div>
                          ) : "-"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {conversao != null ? (
                            <span className={cn(
                              "font-medium",
                              Number(conversao) >= 3 ? "text-green-600" : Number(conversao) >= 1 ? "text-yellow-600" : "text-red-500"
                            )}>
                              {formatPercent(Number(conversao))}
                            </span>
                          ) : "-"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span className={cn(
                            (estoque ?? 0) < 10 ? "text-red-600 font-medium" : "text-foreground"
                          )}>
                            {estoque ?? "-"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <DiasBadge dias={diasParaZerar} />
                        </td>
                        <td className="px-4 py-3 text-center">
                          <Link
                            to={`/anuncios/${listing.mlb_id}`}
                            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
                          >
                            Detalhes
                          </Link>
                        </td>
                      </tr>
                    );
                  })}

                  {/* ── Linha de totais ── */}
                  <tr className="bg-muted/30 font-bold border-t-2">
                    <td className="px-4 py-3 text-xs text-muted-foreground font-bold uppercase tracking-wide">
                      TOTAL ({displayListings.length} anuncios)
                    </td>
                    <td className="px-4 py-3 text-right">{totalPedidos > 0 ? totalPedidos : "-"}</td>
                    <td className="px-4 py-3 text-right">{totalUnidades > 0 ? totalUnidades : "-"}</td>
                    <td className="px-4 py-3 text-right text-green-600">{totalReceita > 0 ? formatCurrency(totalReceita) : "-"}</td>
                    <td className="px-4 py-3 text-right text-green-600">—</td>
                    <td className="px-4 py-3 text-right">{formatCurrency(avgPrecoMedio > 0 ? avgPrecoMedio : 0)}</td>
                    <td className="px-4 py-3 text-right text-blue-700">{avgPrecoMedioPorVenda > 0 ? formatCurrency(avgPrecoMedioPorVenda) : "-"}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">100%</td>
                    <td className="px-4 py-3 text-right">{formatPercent(avgConversao)}</td>
                    <td className="px-4 py-3 text-right">{totalEstoque > 0 ? totalEstoque : "-"}</td>
                    <td className="px-4 py-3 text-right text-muted-foreground">—</td>
                    <td className="px-4 py-3"></td>
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
