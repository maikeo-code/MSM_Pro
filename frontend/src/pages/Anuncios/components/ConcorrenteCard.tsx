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
import { BarChart2 } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

interface CompetitorInfo {
  mlb_id: string;
  price: number;
  last_updated: string;
}

interface ListingInfo {
  price: number;
}

interface HistoryItem {
  date: string | Date;
  price: number | string;
}

interface CompetitorHistoryData {
  mlb_id: string;
  history: HistoryItem[];
}

interface SnapshotItem {
  captured_at: string;
  price: number | string;
}

interface ConcorrenteCardProps {
  competitor: CompetitorInfo;
  listing: ListingInfo;
  competitorId: string | null;
  competitorHistory: CompetitorHistoryData | undefined;
  mySnapshots: SnapshotItem[];
}

export function ConcorrenteCard({
  competitor,
  listing,
  competitorId,
  competitorHistory,
  mySnapshots,
}: ConcorrenteCardProps) {
  return (
    <div className="rounded-lg border bg-card p-6 space-y-6">
      {/* Resumo estático do concorrente */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold mb-1">Concorrente Vinculado</h2>
          <p className="font-medium text-muted-foreground">{competitor.mlb_id}</p>
          <p className="text-sm text-muted-foreground">
            Preco atual: <span className="font-semibold text-foreground">{formatCurrency(competitor.price)}</span>
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Atualizado em:{" "}
            {new Date(competitor.last_updated).toLocaleDateString("pt-BR")}
          </p>
        </div>
        <div className="text-right">
          {listing.price === competitor.price ? (
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">
                Mesmo preco
              </p>
              <p className="text-xs text-muted-foreground">que o concorrente</p>
            </div>
          ) : listing.price > competitor.price ? (
            <div className="space-y-1">
              <p className="text-sm font-medium text-red-600">
                {(
                  ((listing.price - competitor.price) /
                    competitor.price) *
                  100
                ).toFixed(1)}
                % mais caro
              </p>
              <p className="text-xs text-muted-foreground">que o concorrente</p>
            </div>
          ) : listing.price > 0 && competitor.price > 0 ? (
            <div className="space-y-1">
              <p className="text-sm font-medium text-green-600">
                {(
                  ((competitor.price - listing.price) /
                    competitor.price) *
                  100
                ).toFixed(1)}
                % mais barato
              </p>
              <p className="text-xs text-muted-foreground">que o concorrente</p>
            </div>
          ) : (
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">
                Preco indisponivel
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Grafico historico de preco: meu vs concorrente */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <BarChart2 className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">Historico de Preco — Meu vs Concorrente</h3>
        </div>

        {!competitorId ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            Carregando dados do concorrente...
          </p>
        ) : !competitorHistory || competitorHistory.history.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            Sem historico de preco disponivel para este concorrente. Os dados sao coletados diariamente pelo Celery.
          </p>
        ) : (() => {
            // Merge: combina historico do concorrente com snapshots do meu listing por data
            const myPriceByDate: Record<string, number> = {};
            mySnapshots.forEach((snap) => {
              const dateKey = snap.captured_at.slice(0, 10);
              myPriceByDate[dateKey] = Number(snap.price);
            });

            const mergedData = competitorHistory.history.map((item) => {
              const dateKey = (item.date as string).slice(0, 10);
              return {
                date: dateKey,
                competitor_price: Number(item.price),
                my_price: myPriceByDate[dateKey] ?? null,
              };
            });

            const fmtCurrency = (v: number) =>
              new Intl.NumberFormat("pt-BR", {
                style: "currency",
                currency: "BRL",
              }).format(v);

            const fmtDate = (v: string) => {
              const d = new Date(v + "T00:00:00");
              return isNaN(d.getTime())
                ? v
                : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
            };

            return (
              <>
                <div className="flex items-center gap-6 text-xs text-muted-foreground mb-3">
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-4 h-0.5 bg-blue-500" />
                    Meu Preco
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-4 h-0.5 bg-red-500" />
                    Concorrente ({competitorHistory.mlb_id})
                  </span>
                </div>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart
                    data={mergedData}
                    margin={{ top: 10, right: 20, left: 0, bottom: 60 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" className="opacity-40" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11 }}
                      angle={-45}
                      height={80}
                      tickFormatter={fmtDate}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v: number) =>
                        new Intl.NumberFormat("pt-BR", {
                          style: "currency",
                          currency: "BRL",
                          maximumFractionDigits: 0,
                        }).format(v)
                      }
                    />
                    <Tooltip
                      formatter={(value: unknown, name: string) => [
                        value != null ? fmtCurrency(Number(value)) : "—",
                        name,
                      ]}
                      labelFormatter={(label: string) => {
                        const d = new Date(label + "T00:00:00");
                        return isNaN(d.getTime())
                          ? label
                          : d.toLocaleDateString("pt-BR", {
                              day: "2-digit",
                              month: "2-digit",
                              year: "numeric",
                            });
                      }}
                    />
                    <Legend />
                    <Line
                      type="stepAfter"
                      dataKey="my_price"
                      stroke="#3B82F6"
                      strokeWidth={2}
                      dot={false}
                      name="Meu Preco"
                      connectNulls={false}
                    />
                    <Line
                      type="stepAfter"
                      dataKey="competitor_price"
                      stroke="#EF4444"
                      strokeWidth={2}
                      dot={false}
                      name="Concorrente"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </>
            );
          })()
        }
      </div>
    </div>
  );
}
