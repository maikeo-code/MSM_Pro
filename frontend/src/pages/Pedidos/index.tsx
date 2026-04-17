import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ShoppingCart,
  DollarSign,
  Percent,
  Truck,
  Download,
  Search,
} from "lucide-react";
import { listOrders, type OrderOut } from "@/services/ordersService";
import { formatCurrency, formatDateTime, cn } from "@/lib/utils";
import { KpiCard } from "@/components/KpiCard";
import { useActiveAccount } from "@/hooks/useActiveAccount";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function exportOrdersCSV(orders: OrderOut[]): void {
  const headers = [
    "Data",
    "MLB ID",
    "Título",
    "Order ML",
    "Comprador",
    "Qtd",
    "Preco Unit.",
    "Total",
    "Taxa ML",
    "Frete",
    "Liquido",
    "Pagamento",
    "Envio",
  ];

  const rows = orders.map((o) => [
    new Date(o.order_date).toLocaleString("pt-BR"),
    o.mlb_id,
    `"${(o.item_title || "").replace(/"/g, '""')}"`,
    o.ml_order_id,
    `"${o.buyer_nickname.replace(/"/g, '""')}"`,
    o.quantity,
    Number(o.unit_price).toFixed(2),
    Number(o.total_amount).toFixed(2),
    Number(o.sale_fee).toFixed(2),
    Number(o.shipping_cost).toFixed(2),
    Number(o.net_amount).toFixed(2),
    o.payment_status,
    o.shipping_status,
  ].join(","));

  const csv = [headers.join(","), ...rows].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `pedidos_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Badge de status ──────────────────────────────────────────────────────────

const PAYMENT_STATUS_STYLES: Record<string, string> = {
  approved: "bg-green-100 text-green-700",
  pending: "bg-yellow-100 text-yellow-700",
  in_process: "bg-blue-100 text-blue-700",
  rejected: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-600",
};

const PAYMENT_STATUS_LABELS: Record<string, string> = {
  approved: "Aprovado",
  pending: "Pendente",
  in_process: "Em processo",
  rejected: "Recusado",
  cancelled: "Cancelado",
};

const SHIPPING_STATUS_STYLES: Record<string, string> = {
  delivered: "bg-green-100 text-green-700",
  shipped: "bg-blue-100 text-blue-700",
  pending: "bg-yellow-100 text-yellow-700",
  ready_to_ship: "bg-indigo-100 text-indigo-700",
  not_delivered: "bg-red-100 text-red-700",
  cancelled: "bg-gray-100 text-gray-600",
};

const SHIPPING_STATUS_LABELS: Record<string, string> = {
  delivered: "Entregue",
  shipped: "Enviado",
  pending: "Pendente",
  ready_to_ship: "Pronto p/ envio",
  not_delivered: "Nao entregue",
  cancelled: "Cancelado",
};

function StatusBadge({
  status,
  styles,
  labels,
}: {
  status: string;
  styles: Record<string, string>;
  labels: Record<string, string>;
}) {
  const styleClass = styles[status] ?? "bg-gray-100 text-gray-600";
  const label = labels[status] ?? status;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        styleClass,
      )}
    >
      {label}
    </span>
  );
}

// ─── Pagina Principal ─────────────────────────────────────────────────────────

const PERIOD_OPTIONS = [
  { value: "7", label: "Últimos 7 dias" },
  { value: "15", label: "Últimos 15 dias" },
  { value: "30", label: "Últimos 30 dias" },
  { value: "60", label: "Últimos 60 dias" },
];

export default function Pedidos() {
  const accountId = useActiveAccount();
  const [search, setSearch] = useState("");
  const [period, setPeriod] = useState("30"); // Default: 30 dias

  const { data: orders = [], isLoading, isError } = useQuery<OrderOut[]>({
    queryKey: ["orders", period, accountId],
    queryFn: () => listOrders(`${period}d`, accountId),
    staleTime: 5 * 60 * 1000,
  });

  // Ordenar por data mais recente primeiro
  const sorted = useMemo(
    () => [...orders].sort((a, b) => new Date(b.order_date).getTime() - new Date(a.order_date).getTime()),
    [orders],
  );

  // Filtrar por MLB ID ou comprador
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return sorted;
    return sorted.filter(
      (o) =>
        o.mlb_id.toLowerCase().includes(q) ||
        o.buyer_nickname.toLowerCase().includes(q) ||
        o.ml_order_id.toLowerCase().includes(q) ||
        (o.item_title && o.item_title.toLowerCase().includes(q)),
    );
  }, [sorted, search]);

  // KPIs agregados dos dados filtrados
  const totals = useMemo(() => {
    return filtered.reduce(
      (acc, o) => ({
        pedidos: acc.pedidos + 1,
        receita: acc.receita + Number(o.total_amount),
        taxaMl: acc.taxaMl + Number(o.sale_fee),
        liquido: acc.liquido + Number(o.net_amount),
      }),
      { pedidos: 0, receita: 0, taxaMl: 0, liquido: 0 },
    );
  }, [filtered]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Carregando pedidos...
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-64 text-red-500">
        Erro ao carregar pedidos. Verifique a conexao.
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pedidos</h1>
          <p className="text-sm text-gray-500 mt-1">
            Historico de pedidos sincronizados do Mercado Livre
          </p>
        </div>
        <button
          onClick={() => exportOrdersCSV(filtered)}
          className="inline-flex items-center gap-2 rounded-md bg-white border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition-colors"
        >
          <Download className="h-4 w-4" />
          Exportar CSV
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total de Pedidos"
          value={totals.pedidos.toLocaleString("pt-BR")}
          icon={<ShoppingCart className="h-4 w-4" />}
          iconBg="bg-blue-50 text-blue-600"
        />
        <KpiCard
          label="Receita Total"
          value={formatCurrency(totals.receita)}
          icon={<DollarSign className="h-4 w-4" />}
          iconBg="bg-green-50 text-green-600"
        />
        <KpiCard
          label="Taxa ML Total"
          value={formatCurrency(totals.taxaMl)}
          icon={<Percent className="h-4 w-4" />}
          iconBg="bg-orange-50 text-orange-600"
        />
        <KpiCard
          label="Liquido Total"
          value={formatCurrency(totals.liquido)}
          icon={<Truck className="h-4 w-4" />}
          iconBg="bg-purple-50 text-purple-600"
        />
      </div>

      {/* Filtros: período e busca */}
      <div className="flex items-center gap-4">
        {/* Seletor de período */}
        <div>
          <label className="block text-xs text-gray-600 font-medium mb-1">
            Período
          </label>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="rounded-md border border-gray-200 bg-white text-sm text-gray-900 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {PERIOD_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Busca */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar por MLB ID, título, comprador ou order ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-md border border-gray-200 bg-white text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      {/* Tabela */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-100 overflow-hidden">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400 space-y-2">
            <ShoppingCart className="h-10 w-10 opacity-30" />
            <p className="text-sm">
              {search ? "Nenhum pedido encontrado para a busca." : "Nenhum pedido sincronizado ainda."}
            </p>
            {!search && (
              <p className="text-xs text-gray-300">
                Os pedidos sao sincronizados automaticamente a cada 2 horas.
              </p>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Data
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    MLB ID
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Comprador
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Qtd
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Valor Unit.
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Total
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Taxa ML
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Frete
                  </th>
                  <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Liquido
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Pagamento
                  </th>
                  <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Envio
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map((order) => (
                  <tr
                    key={order.id}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                      {formatDateTime(order.order_date)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1 items-start">
                        <span className="font-mono text-xs bg-gray-100 text-gray-700 rounded px-1.5 py-0.5 w-fit">
                          {order.mlb_id}
                        </span>
                        {order.item_title && (
                          <span className="text-[10px] leading-tight text-gray-500 max-w-[150px] line-clamp-2" title={order.item_title}>
                            {order.item_title}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-900 max-w-[160px] truncate">
                      {order.buyer_nickname}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700 font-medium">
                      {order.quantity}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      {formatCurrency(Number(order.unit_price))}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-900 font-semibold">
                      {formatCurrency(Number(order.total_amount))}
                    </td>
                    <td className="px-4 py-3 text-right text-orange-600">
                      -{formatCurrency(Number(order.sale_fee))}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {Number(order.shipping_cost) > 0
                        ? `-${formatCurrency(Number(order.shipping_cost))}`
                        : <span className="text-green-600">Gratis</span>}
                    </td>
                    <td className="px-4 py-3 text-right font-bold text-green-700">
                      {formatCurrency(Number(order.net_amount))}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <StatusBadge
                        status={order.payment_status}
                        styles={PAYMENT_STATUS_STYLES}
                        labels={PAYMENT_STATUS_LABELS}
                      />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <StatusBadge
                        status={order.shipping_status}
                        styles={SHIPPING_STATUS_STYLES}
                        labels={SHIPPING_STATUS_LABELS}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Rodape com contagem */}
      {filtered.length > 0 && (
        <p className="text-xs text-gray-400 text-right">
          Exibindo {filtered.length} de {orders.length} pedidos
        </p>
      )}
    </div>
  );
}
