import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, TrendingUp } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import listingsService from "@/services/listingsService";
import { formatCurrency, formatDate, formatPercent } from "@/lib/utils";

export default function AnuncioDetalhe() {
  const { mlbId } = useParams<{ mlbId: string }>();

  const { data: snapshots, isLoading } = useQuery({
    queryKey: ["snapshots", mlbId],
    queryFn: () => listingsService.getSnapshots(mlbId!, 30),
    enabled: !!mlbId,
  });

  const chartData = snapshots?.map((s) => ({
    data: formatDate(s.captured_at),
    preco: parseFloat(s.price),
    conversao: s.conversion_rate ? parseFloat(s.conversion_rate) : 0,
    visitas: s.visits,
    vendas: s.sales_today,
  }));

  return (
    <div className="p-8">
      <div className="mb-6">
        <Link
          to="/anuncios"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar para Anuncios
        </Link>
        <h1 className="text-3xl font-bold text-foreground">{mlbId}</h1>
        <p className="text-muted-foreground mt-1">Historico dos ultimos 30 dias</p>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">Carregando...</div>
      ) : !snapshots || snapshots.length === 0 ? (
        <div className="rounded-lg border bg-card p-12 text-center">
          <TrendingUp className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
          <p className="font-medium text-foreground">Sem historico de snapshots</p>
          <p className="text-sm text-muted-foreground mt-1">
            Os snapshots sao capturados diariamente as 06:00 BRT.
          </p>
        </div>
      ) : (
        <>
          {/* Grafico de Preco x Conversao */}
          <div className="rounded-lg border bg-card p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Preco x Conversao</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="data" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="preco" orientation="left" tickFormatter={(v) => `R$${v}`} />
                <YAxis yAxisId="conversao" orientation="right" tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  formatter={(value, name) => {
                    if (name === "preco") return [formatCurrency(Number(value)), "Preco"];
                    if (name === "conversao") return [formatPercent(Number(value)), "Conversao"];
                    return [value, name];
                  }}
                />
                <Legend />
                <Line
                  yAxisId="preco"
                  type="monotone"
                  dataKey="preco"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  name="preco"
                />
                <Line
                  yAxisId="conversao"
                  type="monotone"
                  dataKey="conversao"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={false}
                  name="conversao"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Tabela de snapshots */}
          <div className="rounded-lg border bg-card">
            <div className="px-6 py-4 border-b">
              <h2 className="text-lg font-semibold">Historico Detalhado</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-6 py-3 text-left font-medium text-muted-foreground">Data</th>
                    <th className="px-6 py-3 text-right font-medium text-muted-foreground">Preco</th>
                    <th className="px-6 py-3 text-right font-medium text-muted-foreground">Visitas</th>
                    <th className="px-6 py-3 text-right font-medium text-muted-foreground">Vendas</th>
                    <th className="px-6 py-3 text-right font-medium text-muted-foreground">Conversao</th>
                    <th className="px-6 py-3 text-right font-medium text-muted-foreground">Estoque</th>
                  </tr>
                </thead>
                <tbody>
                  {[...snapshots].reverse().map((s) => (
                    <tr key={s.id} className="border-b hover:bg-muted/50">
                      <td className="px-6 py-3">{formatDate(s.captured_at)}</td>
                      <td className="px-6 py-3 text-right">{formatCurrency(parseFloat(s.price))}</td>
                      <td className="px-6 py-3 text-right">{s.visits.toLocaleString("pt-BR")}</td>
                      <td className="px-6 py-3 text-right">{s.sales_today}</td>
                      <td className="px-6 py-3 text-right">
                        {s.conversion_rate ? formatPercent(parseFloat(s.conversion_rate)) : "-"}
                      </td>
                      <td className="px-6 py-3 text-right">{s.stock}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
