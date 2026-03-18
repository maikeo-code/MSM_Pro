import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MessageCircle,
  AlertTriangle,
  Mail,
  RotateCcw,
  Headphones,
  Sparkles,
  Send,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  atendimentoService,
  type AtendimentoItem,
  type AtendimentoStats,
} from "@/services/atendimentoService";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function tempoRelativo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}min atras`;
  const horas = Math.floor(mins / 60);
  if (horas < 24) return `${horas}h atras`;
  const dias = Math.floor(horas / 24);
  return `${dias}d atras`;
}

// ─── Tipo → configuração visual ───────────────────────────────────────────────

type ItemType = "pergunta" | "reclamacao" | "mensagem" | "devolucao";

const TYPE_CONFIG: Record<
  ItemType,
  {
    label: string;
    icon: React.FC<{ className?: string }>;
    badgeClass: string;
    emptyMsg: string;
  }
> = {
  pergunta: {
    label: "Pergunta",
    icon: MessageCircle,
    badgeClass: "bg-blue-100 text-blue-700",
    emptyMsg: "Nenhuma pergunta pendente. Tudo em dia!",
  },
  reclamacao: {
    label: "Reclamacao",
    icon: AlertTriangle,
    badgeClass: "bg-red-100 text-red-700",
    emptyMsg: "Nenhuma reclamacao aberta.",
  },
  mensagem: {
    label: "Mensagem",
    icon: Mail,
    badgeClass: "bg-purple-100 text-purple-700",
    emptyMsg: "Nenhuma mensagem nao lida.",
  },
  devolucao: {
    label: "Devolucao",
    icon: RotateCcw,
    badgeClass: "bg-orange-100 text-orange-700",
    emptyMsg: "Nenhuma devolucao pendente.",
  },
};

function getTypeConfig(type: string) {
  return TYPE_CONFIG[type as ItemType] ?? TYPE_CONFIG["pergunta"];
}

// ─── KPI Card ─────────────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  icon: Icon,
  hasAlert,
}: {
  label: string;
  value: number;
  icon: React.FC<{ className?: string }>;
  hasAlert: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-4 flex items-center gap-4",
        hasAlert && value > 0
          ? "bg-red-50 border-red-200"
          : "bg-white border-gray-100",
      )}
    >
      <span
        className={cn(
          "p-2 rounded-lg",
          hasAlert && value > 0
            ? "bg-red-100 text-red-600"
            : "bg-gray-100 text-gray-500",
        )}
      >
        <Icon className="h-5 w-5" />
      </span>
      <div>
        <p className="text-xs text-gray-500 font-medium">{label}</p>
        <p
          className={cn(
            "text-2xl font-bold",
            hasAlert && value > 0 ? "text-red-700" : "text-gray-900",
          )}
        >
          {value}
        </p>
      </div>
    </div>
  );
}

// ─── Modal de Resposta ────────────────────────────────────────────────────────

function RespostaModal({
  item,
  onClose,
}: {
  item: AtendimentoItem;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [texto, setTexto] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const config = getTypeConfig(item.type);
  const Icon = config.icon;

  const mutation = useMutation({
    mutationFn: () =>
      atendimentoService.respond(item.type, item.id, {
        text: texto,
        account_id: item.account_id ?? "",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["atendimento"] });
      queryClient.invalidateQueries({ queryKey: ["atendimento-stats"] });
      onClose();
    },
  });

  const handleAiSuggestion = async () => {
    setAiLoading(true);
    try {
      const result = await atendimentoService.getAiSuggestion(
        item.type,
        item.id,
        item.account_id,
      );
      setTexto(result.suggestion);
    } catch {
      // silenciar erro de IA — usuario pode digitar manualmente
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-gray-600" />
            <h2 className="font-semibold text-gray-900">
              Responder {config.label}
            </h2>
            <span
              className={cn(
                "text-xs font-medium rounded-full px-2 py-0.5",
                config.badgeClass,
              )}
            >
              #{item.id}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Corpo */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {/* Texto original */}
          <div>
            <p className="text-xs text-gray-500 mb-1 font-medium">
              Mensagem original
            </p>
            <div className="bg-gray-50 rounded-lg px-4 py-3 text-sm text-gray-800 leading-relaxed">
              {item.text}
            </div>
          </div>

          {/* Metadados */}
          <div className="flex flex-wrap gap-3 text-xs text-gray-500">
            {item.from_user && (
              <span>
                De:{" "}
                <strong className="text-gray-700">
                  {item.from_user.nickname}
                </strong>
              </span>
            )}
            {item.item_id && (
              <span>
                Anuncio:{" "}
                <strong className="text-gray-700">{item.item_id}</strong>
              </span>
            )}
            {item.account_nickname && (
              <span>
                Conta:{" "}
                <strong className="text-gray-700">{item.account_nickname}</strong>
              </span>
            )}
            <span>{tempoRelativo(item.date_created)}</span>
          </div>

          {/* Resposta */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <p className="text-xs text-gray-500 font-medium">Sua resposta</p>
              <button
                onClick={handleAiSuggestion}
                disabled={aiLoading}
                className="inline-flex items-center gap-1.5 text-xs text-violet-600 hover:text-violet-800 font-medium disabled:opacity-50 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5" />
                {aiLoading ? "Gerando..." : "Sugerir com IA"}
              </button>
            </div>
            <textarea
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder="Digite sua resposta..."
              rows={5}
              className="w-full rounded-lg border border-gray-200 bg-white text-sm text-gray-900 placeholder:text-gray-400 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            />
          </div>

          {mutation.isError && (
            <p className="text-xs text-red-600">
              Erro ao enviar resposta. Tente novamente.
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!texto.trim() || mutation.isPending}
            className={cn(
              "inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              "bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            <Send className="h-4 w-4" />
            {mutation.isPending ? "Enviando..." : "Enviar resposta"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Card de item de atendimento ──────────────────────────────────────────────

function AtendimentoCard({
  item,
  onResponder,
}: {
  item: AtendimentoItem;
  onResponder: (item: AtendimentoItem) => void;
}) {
  const config = getTypeConfig(item.type);
  const Icon = config.icon;

  return (
    <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-4 space-y-3">
      {/* Cabecalho */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap flex-1 min-w-0">
          <span
            className={cn(
              "inline-flex items-center gap-1 text-xs font-medium rounded-full px-2 py-0.5",
              config.badgeClass,
            )}
          >
            <Icon className="h-3 w-3" />
            {config.label}
          </span>
          {item.requires_action && (
            <span className="inline-flex items-center gap-1 text-xs font-medium rounded-full px-2 py-0.5 bg-amber-100 text-amber-700">
              <AlertTriangle className="h-3 w-3" />
              Acao Necessaria
            </span>
          )}
          {item.from_user && (
            <span className="text-xs text-gray-500">
              {item.from_user.nickname}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-400 whitespace-nowrap shrink-0">
          {tempoRelativo(item.date_created)}
        </span>
      </div>

      {/* Texto */}
      <p className="text-sm text-gray-800 leading-relaxed line-clamp-3 bg-gray-50 rounded px-3 py-2">
        {item.text.length > 200 ? item.text.slice(0, 200) + "..." : item.text}
      </p>

      {/* Metadados */}
      {(item.item_id || item.item_title) && (
        <div className="flex items-center gap-2 text-xs text-gray-500">
          {item.item_id && (
            <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">
              {item.item_id}
            </span>
          )}
          {item.item_title && (
            <span className="truncate">{item.item_title}</span>
          )}
        </div>
      )}

      {/* Ultima mensagem (para mensagens/reclamacoes) */}
      {item.last_message && (
        <p className="text-xs text-gray-500 italic truncate">
          Ultima: {item.last_message}
        </p>
      )}

      {/* Acao */}
      {item.requires_action && (
        <div>
          <button
            onClick={() => onResponder(item)}
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 text-white px-3 py-1.5 text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            <MessageCircle className="h-4 w-4" />
            Responder
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────

type TypeFilter = "todos" | ItemType;
type StatusFilter = "pendentes" | "fechados" | "todos";

const TYPE_TABS: { key: TypeFilter; label: string }[] = [
  { key: "todos", label: "Todos" },
  { key: "pergunta", label: "Perguntas" },
  { key: "reclamacao", label: "Reclamacoes" },
  { key: "mensagem", label: "Mensagens" },
  { key: "devolucao", label: "Devolucoes" },
];

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: "pendentes", label: "Pendentes" },
  { key: "fechados", label: "Respondidos / Fechados" },
  { key: "todos", label: "Todos" },
];

// Mapeamento de status: quais statuses são "pendentes"
const PENDING_STATUSES = new Set([
  "unanswered",
  "open",
  "UNANSWERED",
  "OPEN",
  "pending",
  "waiting_for_seller_response",
  "new",
]);

// ─── Pagina Principal ─────────────────────────────────────────────────────────

export default function Atendimento() {
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("todos");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("pendentes");
  const [modalItem, setModalItem] = useState<AtendimentoItem | null>(null);

  // Stats query
  const { data: stats } = useQuery<AtendimentoStats>({
    queryKey: ["atendimento-stats"],
    queryFn: () => atendimentoService.getStats(),
    staleTime: 2 * 60 * 1000,
  });

  // Lista query — busca todos, filtramos client-side
  const { data, isLoading, isError } = useQuery({
    queryKey: ["atendimento"],
    queryFn: () => atendimentoService.getAll({ limit: 100 }),
    staleTime: 2 * 60 * 1000,
  });

  const allItems = data?.items ?? [];
  const byType = data?.by_type ?? {};

  // Filtros client-side
  const filtered = useMemo(() => {
    let items = allItems;

    if (typeFilter !== "todos") {
      items = items.filter((i) => i.type === typeFilter);
    }

    if (statusFilter === "pendentes") {
      items = items.filter(
        (i) => i.requires_action || PENDING_STATUSES.has(i.status),
      );
    } else if (statusFilter === "fechados") {
      items = items.filter(
        (i) => !i.requires_action && !PENDING_STATUSES.has(i.status),
      );
    }

    return items;
  }, [allItems, typeFilter, statusFilter]);

  const pendingCount = useMemo(
    () =>
      allItems.filter(
        (i) => i.requires_action || PENDING_STATUSES.has(i.status),
      ).length,
    [allItems],
  );

  const emptyMsg =
    typeFilter !== "todos"
      ? getTypeConfig(typeFilter).emptyMsg
      : statusFilter === "pendentes"
        ? "Nenhum item pendente. Tudo em dia!"
        : "Nenhum item encontrado.";

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Headphones className="h-7 w-7 text-blue-600" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Atendimento</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Perguntas, reclamacoes, mensagens e devolucoes em um unico lugar
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <KpiCard
          label="Perguntas Pendentes"
          value={stats?.perguntas_pendentes ?? 0}
          icon={MessageCircle}
          hasAlert={true}
        />
        <KpiCard
          label="Reclamacoes Abertas"
          value={stats?.reclamacoes_abertas ?? 0}
          icon={AlertTriangle}
          hasAlert={true}
        />
        <KpiCard
          label="Mensagens"
          value={stats?.mensagens_nao_lidas ?? 0}
          icon={Mail}
          hasAlert={false}
        />
        <KpiCard
          label="Devolucoes Pendentes"
          value={stats?.devolucoes_pendentes ?? 0}
          icon={RotateCcw}
          hasAlert={true}
        />
        <div
          className={cn(
            "rounded-lg border p-4 flex items-center gap-4",
            (stats?.total_pendentes ?? 0) > 0
              ? "bg-amber-50 border-amber-200"
              : "bg-green-50 border-green-200",
          )}
        >
          <span
            className={cn(
              "p-2 rounded-lg",
              (stats?.total_pendentes ?? 0) > 0
                ? "bg-amber-100 text-amber-600"
                : "bg-green-100 text-green-600",
            )}
          >
            <Headphones className="h-5 w-5" />
          </span>
          <div>
            <p className="text-xs text-gray-500 font-medium">Total Pendentes</p>
            <p
              className={cn(
                "text-2xl font-bold",
                (stats?.total_pendentes ?? pendingCount) > 0
                  ? "text-amber-700"
                  : "text-green-700",
              )}
            >
              {stats?.total_pendentes ?? pendingCount}
            </p>
          </div>
        </div>
      </div>

      {/* Tabs de tipo */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit overflow-x-auto">
        {TYPE_TABS.map((tab) => {
          const count =
            tab.key === "todos"
              ? allItems.length
              : (byType[tab.key + "s"] ?? byType[tab.key] ?? 0);
          return (
            <button
              key={tab.key}
              onClick={() => setTypeFilter(tab.key)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors whitespace-nowrap flex items-center gap-1.5",
                typeFilter === tab.key
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700",
              )}
            >
              {tab.label}
              {count > 0 && (
                <span
                  className={cn(
                    "text-xs rounded-full px-1.5 py-0.5 font-semibold",
                    typeFilter === tab.key
                      ? "bg-blue-100 text-blue-700"
                      : "bg-gray-200 text-gray-600",
                  )}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Sub-tabs de status */}
      <div className="flex gap-1 bg-gray-50 border border-gray-200 rounded-lg p-1 w-fit">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setStatusFilter(tab.key)}
            className={cn(
              "px-3 py-1 rounded-md text-sm font-medium transition-colors",
              statusFilter === tab.key
                ? "bg-white text-gray-900 shadow-sm border border-gray-200"
                : "text-gray-400 hover:text-gray-600",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Lista */}
      {isLoading ? (
        <div className="flex items-center justify-center h-48 text-gray-400">
          Carregando atendimentos...
        </div>
      ) : isError ? (
        <div className="flex items-center justify-center h-48 text-red-500">
          Erro ao carregar. Verifique a conexao.
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400 space-y-2">
          <Headphones className="h-12 w-12 opacity-20" />
          <p className="text-sm">{emptyMsg}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((item) => (
            <AtendimentoCard
              key={`${item.type}-${item.id}`}
              item={item}
              onResponder={setModalItem}
            />
          ))}
        </div>
      )}

      {filtered.length > 0 && (
        <p className="text-xs text-gray-400 text-right">
          Exibindo {filtered.length}{" "}
          {filtered.length === 1 ? "item" : "itens"}
        </p>
      )}

      {/* Modal */}
      {modalItem && (
        <RespostaModal item={modalItem} onClose={() => setModalItem(null)} />
      )}
    </div>
  );
}
