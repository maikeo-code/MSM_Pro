import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Package, Search, TrendingUp, ArrowUpDown } from "lucide-react";
import analysisService, { type AnuncioAnalise } from "@/services/analysisService";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";

type SortKey = keyof AnuncioAnalise | null;
type SortDirection = "asc" | "desc";

export default function AnaliseAnuncios() {
  const [searchTerm, setSearchTerm] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const { data: response, isLoading, error } = useQuery({
    queryKey: ["analysis-listings"],
    queryFn: () => analysisService.getListingsAnalysis(),
  });

  const anuncios = response?.anuncios ?? [];

  // Filtrar por busca
  const filteredAnuncios = useMemo(() => {
    if (!searchTerm.trim()) return anuncios;

    const term = searchTerm.toLowerCase();
    return anuncios.filter(
      (a) =>
        a.titulo?.toLowerCase().includes(term) ||
        a.mlb_id?.toLowerCase().includes(term)
    );
  }, [anuncios, searchTerm]);

  // Ordenar
  const sortedAnuncios = useMemo(() => {
    if (!sortKey) return filteredAnuncios;

    return [...filteredAnuncios].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];

      // Null/undefined handling
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      // Number comparison
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
      }

      // String comparison
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDirection === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }

      return 0;
    });
  }, [filteredAnuncios, sortKey, sortDirection]);

  // Handle sort column click
  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      // Toggle direction if same column
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      // New column, default to desc
      setSortKey(key);
      setSortDirection("desc");
    }
  };

  // Calcular totais (baseado em filteredAnuncios)
  const totals = useMemo(() => {
    return {
      vendas_7d: filteredAnuncios.reduce((sum, a) => sum + (a.vendas_7d ?? 0), 0),
      estoque: filteredAnuncios.reduce((sum, a) => sum + (a.estoque ?? 0), 0),
      visitas_hoje: filteredAnuncios.reduce((sum, a) => sum + (a.visitas_hoje ?? 0), 0),
      visitas_ontem: filteredAnuncios.reduce((sum, a) => sum + (a.visitas_ontem ?? 0), 0),
      vendas_hoje: filteredAnuncios.reduce((sum, a) => sum + (a.vendas_hoje ?? 0), 0),
      vendas_ontem: filteredAnuncios.reduce((sum, a) => sum + (a.vendas_ontem ?? 0), 0),
      vendas_anteontem: filteredAnuncios.reduce((sum, a) => sum + (a.vendas_anteontem ?? 0), 0),
    };
  }, [filteredAnuncios]);

  // Média de conversão
  const avgConversao = useMemo(() => {
    const vals = filteredAnuncios
      .filter((a) => a.conversao_7d != null)
      .map((a) => a.conversao_7d!);
    return vals.length > 0 ? vals.reduce((sum, v) => sum + v, 0) / vals.length : 0;
  }, [filteredAnuncios]);

  const colSpan = 20; // Total de colunas

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground">Análise de Anúncios</h1>
        <p className="text-muted-foreground mt-1">
          Visão completa de desempenho, conversão e oportunidades
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          Erro ao carregar dados. Verifique sua conexão.
        </div>
      )}

      {/* Card de resumo rápido */}
      {anuncios.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="rounded-lg border bg-card shadow-sm p-4">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Anúncios</p>
            <p className="text-2xl font-bold mt-2 text-foreground">{anuncios.length}</p>
          </div>
          <div className="rounded-lg border bg-card shadow-sm p-4">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Vendas 7d</p>
            <p className="text-2xl font-bold mt-2 text-green-600">{totals.vendas_7d}</p>
          </div>
          <div className="rounded-lg border bg-card shadow-sm p-4">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Estoque</p>
            <p className="text-2xl font-bold mt-2 text-foreground">{totals.estoque}</p>
          </div>
          <div className="rounded-lg border bg-card shadow-sm p-4">
            <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Conv. 7d</p>
            <p className="text-2xl font-bold mt-2 text-blue-600">{formatPercent(avgConversao)}</p>
          </div>
        </div>
      )}

      {/* Search bar */}
      <div className="rounded-lg border bg-card shadow-sm mb-6">
        <div className="px-6 py-4 border-b flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-foreground">
            Todos os Anúncios ({filteredAnuncios.length})
          </h2>
          <div className="flex items-center gap-3 flex-1 justify-end">
            <div className="relative max-w-xs w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Buscar por título ou MLB..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full rounded-md border border-input bg-background pl-9 pr-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
              />
            </div>
          </div>
        </div>

        {/* Tabela */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th
                  className="px-4 py-3 text-left font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("titulo")}
                >
                  <div className="flex items-center gap-2">
                    Anúncio
                    {sortKey === "titulo" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-left font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("mlb_id")}
                >
                  <div className="flex items-center gap-2">
                    MLB
                    {sortKey === "mlb_id" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-left font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("tipo")}
                >
                  <div className="flex items-center gap-2">
                    Tipo
                    {sortKey === "tipo" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("preco")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Preço
                    {sortKey === "preco" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("visitas_hoje")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Vis. Hoje
                    {sortKey === "visitas_hoje" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("visitas_ontem")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Vis. Ontem
                    {sortKey === "visitas_ontem" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("conversao_7d")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Conv. 7d
                    {sortKey === "conversao_7d" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("conversao_15d")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Conv. 15d
                    {sortKey === "conversao_15d" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("conversao_30d")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Conv. 30d
                    {sortKey === "conversao_30d" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("vendas_hoje")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Vend. Hoje
                    {sortKey === "vendas_hoje" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("vendas_ontem")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Vend. Ontem
                    {sortKey === "vendas_ontem" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("vendas_anteontem")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Vend. Ant.
                    {sortKey === "vendas_anteontem" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("vendas_7d")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Vend. 7d
                    {sortKey === "vendas_7d" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("estoque")}
                >
                  <div className="flex items-center justify-end gap-2">
                    Estoque
                    {sortKey === "estoque" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("roas_7d")}
                >
                  <div className="flex items-center justify-end gap-2">
                    ROAS 7d
                    {sortKey === "roas_7d" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("roas_15d")}
                >
                  <div className="flex items-center justify-end gap-2">
                    ROAS 15d
                    {sortKey === "roas_15d" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th
                  className="px-4 py-3 text-right font-medium text-muted-foreground cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => handleSort("roas_30d")}
                >
                  <div className="flex items-center justify-end gap-2">
                    ROAS 30d
                    {sortKey === "roas_30d" && (
                      <ArrowUpDown className={`h-3 w-3 ${sortDirection === "asc" ? "rotate-180" : ""}`} />
                    )}
                  </div>
                </th>
                <th className="px-4 py-3 text-right font-medium text-muted-foreground">Score</th>
                <th className="px-4 py-3 text-center font-medium text-muted-foreground">Link</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={colSpan} className="px-6 py-8 text-center text-muted-foreground">
                    Carregando...
                  </td>
                </tr>
              ) : sortedAnuncios.length === 0 ? (
                <tr>
                  <td colSpan={colSpan} className="px-6 py-12 text-center">
                    <TrendingUp className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
                    <p className="font-medium text-foreground">
                      {searchTerm ? `Nenhum anúncio encontrado para "${searchTerm}"` : "Nenhum anúncio encontrado"}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {searchTerm ? "Tente outro termo de busca." : "Sincronize seus anúncios para ver dados."}
                    </p>
                  </td>
                </tr>
              ) : (
                <>
                  {sortedAnuncios.map((anuncio) => {
                    const temDesconto = anuncio.preco_original &&
                      Number(anuncio.preco_original) > Number(anuncio.preco);
                    const descPct = temDesconto
                      ? (((Number(anuncio.preco_original) - Number(anuncio.preco)) /
                        Number(anuncio.preco_original)) *
                        100)
                      : 0;

                    return (
                      <tr
                        key={anuncio.mlb_id}
                        className="border-b hover:bg-muted/50 transition-colors"
                      >
                        {/* Thumb + Título */}
                        <td className="px-4 py-3 max-w-xs">
                          <div className="flex items-center gap-3">
                            {anuncio.thumbnail ? (
                              <img
                                src={anuncio.thumbnail}
                                alt={anuncio.titulo}
                                className="h-10 w-10 rounded object-cover shrink-0 border"
                              />
                            ) : (
                              <div className="h-10 w-10 rounded bg-muted flex items-center justify-center shrink-0">
                                <Package className="h-4 w-4 text-muted-foreground/50" />
                              </div>
                            )}
                            <div className="min-w-0">
                              <p
                                className="text-xs font-medium text-foreground truncate"
                                title={anuncio.titulo}
                              >
                                {anuncio.titulo.length > 40
                                  ? anuncio.titulo.substring(0, 40) + "..."
                                  : anuncio.titulo}
                              </p>
                              {temDesconto && (
                                <p className="text-xs text-green-600 font-medium">
                                  -{descPct.toFixed(0)}%
                                </p>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* MLB ID */}
                        <td className="px-4 py-3 text-left">
                          <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground">
                            {anuncio.mlb_id}
                          </span>
                        </td>

                        {/* Tipo */}
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                              anuncio.tipo === "full"
                                ? "bg-purple-100 text-purple-700"
                                : anuncio.tipo === "premium"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-gray-100 text-gray-700"
                            )}
                          >
                            {anuncio.tipo}
                          </span>
                        </td>

                        {/* Preço */}
                        <td className="px-4 py-3 text-right">
                          <div className="flex flex-col items-end gap-0.5">
                            {temDesconto && (
                              <span className="text-xs text-muted-foreground line-through">
                                {formatCurrency(anuncio.preco_original!)}
                              </span>
                            )}
                            <span className={cn(
                              "font-semibold",
                              temDesconto ? "text-green-600" : ""
                            )}>
                              {formatCurrency(anuncio.preco)}
                            </span>
                          </div>
                        </td>

                        {/* Visitas Hoje */}
                        <td className="px-4 py-3 text-right text-foreground font-medium">
                          {anuncio.visitas_hoje}
                        </td>

                        {/* Visitas Ontem */}
                        <td className="px-4 py-3 text-right text-foreground font-medium">
                          {anuncio.visitas_ontem}
                        </td>

                        {/* Conversão 7d */}
                        <td className="px-4 py-3 text-right">
                          {anuncio.conversao_7d != null ? (
                            <span
                              className={cn(
                                "font-medium",
                                Number(anuncio.conversao_7d) >= 5
                                  ? "text-green-600"
                                  : Number(anuncio.conversao_7d) >= 2
                                  ? "text-yellow-600"
                                  : "text-red-500"
                              )}
                            >
                              {formatPercent(anuncio.conversao_7d, 1)}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>

                        {/* Conversão 15d */}
                        <td className="px-4 py-3 text-right">
                          {anuncio.conversao_15d != null ? (
                            <span
                              className={cn(
                                "font-medium",
                                Number(anuncio.conversao_15d) >= 5
                                  ? "text-green-600"
                                  : Number(anuncio.conversao_15d) >= 2
                                  ? "text-yellow-600"
                                  : "text-red-500"
                              )}
                            >
                              {formatPercent(anuncio.conversao_15d, 1)}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>

                        {/* Conversão 30d */}
                        <td className="px-4 py-3 text-right">
                          {anuncio.conversao_30d != null ? (
                            <span
                              className={cn(
                                "font-medium",
                                Number(anuncio.conversao_30d) >= 5
                                  ? "text-green-600"
                                  : Number(anuncio.conversao_30d) >= 2
                                  ? "text-yellow-600"
                                  : "text-red-500"
                              )}
                            >
                              {formatPercent(anuncio.conversao_30d, 1)}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>

                        {/* Vendas Hoje */}
                        <td className="px-4 py-3 text-right text-green-600 font-medium">
                          {anuncio.vendas_hoje}
                        </td>

                        {/* Vendas Ontem */}
                        <td className="px-4 py-3 text-right text-foreground font-medium">
                          {anuncio.vendas_ontem}
                        </td>

                        {/* Vendas Anteontem */}
                        <td className="px-4 py-3 text-right text-foreground font-medium">
                          {anuncio.vendas_anteontem}
                        </td>

                        {/* Vendas 7d */}
                        <td className="px-4 py-3 text-right text-blue-600 font-medium">
                          {anuncio.vendas_7d}
                        </td>

                        {/* Estoque */}
                        <td
                          className={cn(
                            "px-4 py-3 text-right font-medium",
                            (anuncio.estoque ?? 0) < 10
                              ? "text-red-600"
                              : (anuncio.estoque ?? 0) < 30
                              ? "text-yellow-600"
                              : "text-foreground"
                          )}
                        >
                          {anuncio.estoque}
                        </td>

                        {/* ROAS 7d */}
                        <td className="px-4 py-3 text-right">
                          {anuncio.roas_7d != null ? (
                            <span
                              className={cn(
                                "font-medium",
                                Number(anuncio.roas_7d) > 3
                                  ? "text-green-600"
                                  : Number(anuncio.roas_7d) >= 1
                                  ? "text-yellow-600"
                                  : "text-red-500"
                              )}
                            >
                              {Number(anuncio.roas_7d).toFixed(2)}x
                            </span>
                          ) : (
                            "N/D"
                          )}
                        </td>

                        {/* ROAS 15d */}
                        <td className="px-4 py-3 text-right">
                          {anuncio.roas_15d != null ? (
                            <span
                              className={cn(
                                "font-medium",
                                Number(anuncio.roas_15d) > 3
                                  ? "text-green-600"
                                  : Number(anuncio.roas_15d) >= 1
                                  ? "text-yellow-600"
                                  : "text-red-500"
                              )}
                            >
                              {Number(anuncio.roas_15d).toFixed(2)}x
                            </span>
                          ) : (
                            "N/D"
                          )}
                        </td>

                        {/* ROAS 30d */}
                        <td className="px-4 py-3 text-right">
                          {anuncio.roas_30d != null ? (
                            <span
                              className={cn(
                                "font-medium",
                                Number(anuncio.roas_30d) > 3
                                  ? "text-green-600"
                                  : Number(anuncio.roas_30d) >= 1
                                  ? "text-yellow-600"
                                  : "text-red-500"
                              )}
                            >
                              {Number(anuncio.roas_30d).toFixed(2)}x
                            </span>
                          ) : (
                            "N/D"
                          )}
                        </td>

                        {/* Quality Score */}
                        <td className="px-4 py-3 text-right">
                          {anuncio.quality_score != null ? (
                            <span
                              className={cn(
                                "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                                anuncio.quality_score >= 80
                                  ? "bg-green-100 text-green-700"
                                  : anuncio.quality_score >= 60
                                  ? "bg-yellow-100 text-yellow-700"
                                  : "bg-red-100 text-red-700"
                              )}
                            >
                              {anuncio.quality_score}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>

                        {/* Link externo */}
                        <td className="px-4 py-3 text-center">
                          {anuncio.permalink && (
                            <a
                              href={anuncio.permalink}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 rounded-md border px-2 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
                              title="Abrir no Mercado Livre"
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </td>
                      </tr>
                    );
                  })}

                  {/* Linha de totais */}
                  <tr className="bg-muted/30 font-bold border-t-2">
                    <td className="px-4 py-3 text-xs text-muted-foreground uppercase tracking-wide">
                      TOTAL ({filteredAnuncios.length})
                    </td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td className="px-4 py-3 text-right">{totals.visitas_hoje}</td>
                    <td className="px-4 py-3 text-right">{totals.visitas_ontem}</td>
                    <td className="px-4 py-3 text-right text-blue-600">{formatPercent(avgConversao)}</td>
                    <td></td>
                    <td></td>
                    <td className="px-4 py-3 text-right text-green-600">{totals.vendas_hoje}</td>
                    <td className="px-4 py-3 text-right">{totals.vendas_ontem}</td>
                    <td className="px-4 py-3 text-right">{totals.vendas_anteontem}</td>
                    <td className="px-4 py-3 text-right text-blue-600">{totals.vendas_7d}</td>
                    <td className="px-4 py-3 text-right">{totals.estoque}</td>
                    <td colSpan={4}></td>
                    <td></td>
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
