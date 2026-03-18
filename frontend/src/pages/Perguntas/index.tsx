import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MessageCircle,
  Clock,
  CheckCircle,
  Send,
  AlertTriangle,
} from "lucide-react";
import {
  listQuestions,
  answerQuestion,
  type MLQuestion,
} from "@/services/perguntasService";
import { cn } from "@/lib/utils";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function horasDesde(dateStr: string): number {
  const diff = Date.now() - new Date(dateStr).getTime();
  return diff / (1000 * 60 * 60);
}

function formatarData(dateStr: string): string {
  return new Date(dateStr).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function tempoRelativo(dateStr: string): string {
  const horas = horasDesde(dateStr);
  if (horas < 1) return `${Math.floor(horas * 60)}min atras`;
  if (horas < 24) return `${Math.floor(horas)}h atras`;
  return `${Math.floor(horas / 24)}d atras`;
}

// ─── Badge de Urgencia ────────────────────────────────────────────────────────

function UrgenciaBadge({ dateStr }: { dateStr: string }) {
  const horas = horasDesde(dateStr);
  if (horas >= 24) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700">
        <AlertTriangle className="h-3 w-3" />
        Urgente
      </span>
    );
  }
  if (horas >= 12) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-700">
        <Clock className="h-3 w-3" />
        Atencao
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700">
      <CheckCircle className="h-3 w-3" />
      Recente
    </span>
  );
}

// ─── KPI Card ─────────────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  iconBg?: string;
}

function KpiCard({
  label,
  value,
  icon,
  iconBg = "bg-blue-50 text-blue-600",
}: KpiCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm p-5 flex flex-col gap-2 border border-gray-100">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500 font-medium">{label}</p>
        <span className={cn("p-2 rounded-lg", iconBg)}>{icon}</span>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}

// ─── Card de Pergunta ─────────────────────────────────────────────────────────

function QuestionCard({
  question,
  isPendente,
}: {
  question: MLQuestion;
  isPendente: boolean;
}) {
  const queryClient = useQueryClient();
  const [resposta, setResposta] = useState("");
  const [expandido, setExpandido] = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      answerQuestion(question.id, resposta, question._account_id),
    onSuccess: () => {
      setResposta("");
      setExpandido(false);
      queryClient.invalidateQueries({ queryKey: ["perguntas"] });
    },
  });

  const handleResponder = () => {
    if (!resposta.trim()) return;
    mutation.mutate();
  };

  return (
    <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-4 space-y-3">
      {/* Cabecalho */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs bg-gray-100 text-gray-700 rounded px-1.5 py-0.5">
              {question.item_id}
            </span>
            <span className="text-xs text-gray-400">
              {question._account_nickname}
            </span>
            {isPendente && <UrgenciaBadge dateStr={question.date_created} />}
          </div>
          <p className="mt-2 text-sm text-gray-900 font-medium">
            {question.from?.nickname ?? `Comprador #${question.from?.id}`}
            <span className="text-gray-400 font-normal ml-2">
              perguntou {tempoRelativo(question.date_created)}
            </span>
          </p>
        </div>
        <p className="text-xs text-gray-400 whitespace-nowrap">
          {formatarData(question.date_created)}
        </p>
      </div>

      {/* Texto da pergunta */}
      <p className="text-sm text-gray-700 leading-relaxed bg-gray-50 rounded-md px-3 py-2">
        {question.text}
      </p>

      {/* Resposta existente (para aba Respondidas) */}
      {question.answer && (
        <div className="border-l-2 border-blue-300 pl-3">
          <p className="text-xs text-blue-600 font-medium mb-1">
            Resposta — {formatarData(question.answer.date_created)}
          </p>
          <p className="text-sm text-gray-700">{question.answer.text}</p>
        </div>
      )}

      {/* Formulario de resposta (apenas para pendentes) */}
      {isPendente && (
        <div className="space-y-2">
          {!expandido ? (
            <button
              onClick={() => setExpandido(true)}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 text-white px-3 py-1.5 text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              <MessageCircle className="h-4 w-4" />
              Responder
            </button>
          ) : (
            <div className="space-y-2">
              <textarea
                value={resposta}
                onChange={(e) => setResposta(e.target.value)}
                placeholder="Digite sua resposta..."
                rows={3}
                className="w-full rounded-md border border-gray-200 bg-white text-sm text-gray-900 placeholder:text-gray-400 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={handleResponder}
                  disabled={!resposta.trim() || mutation.isPending}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    "bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed",
                  )}
                >
                  <Send className="h-3.5 w-3.5" />
                  {mutation.isPending ? "Enviando..." : "Enviar resposta"}
                </button>
                <button
                  onClick={() => {
                    setExpandido(false);
                    setResposta("");
                  }}
                  className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
                >
                  Cancelar
                </button>
              </div>
              {mutation.isError && (
                <p className="text-xs text-red-600">
                  Erro ao enviar. Tente novamente.
                </p>
              )}
              {mutation.isSuccess && (
                <p className="text-xs text-green-600">
                  Resposta enviada com sucesso.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Pagina Principal ─────────────────────────────────────────────────────────

type Tab = "pendentes" | "respondidas";

export default function Perguntas() {
  const [tab, setTab] = useState<Tab>("pendentes");

  const statusMap: Record<Tab, string> = {
    pendentes: "UNANSWERED",
    respondidas: "ANSWERED",
  };

  const { data, isLoading, isError } = useQuery({
    queryKey: ["perguntas", tab],
    queryFn: () => listQuestions(statusMap[tab], 50),
    staleTime: 2 * 60 * 1000,
  });

  const questions = data?.questions ?? [];

  // KPIs para aba pendentes
  const urgentes = useMemo(
    () =>
      tab === "pendentes"
        ? questions.filter((q) => horasDesde(q.date_created) >= 24).length
        : 0,
    [questions, tab],
  );

  const tempoMedioHoras = useMemo(() => {
    if (tab !== "pendentes" || questions.length === 0) return 0;
    const soma = questions.reduce(
      (acc, q) => acc + horasDesde(q.date_created),
      0,
    );
    return Math.round(soma / questions.length);
  }, [questions, tab]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Perguntas e Respostas
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Gerencie as perguntas dos compradores em todos os seus anuncios
        </p>
      </div>

      {/* KPI Cards (apenas na aba pendentes) */}
      {tab === "pendentes" && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <KpiCard
            label="Total Pendentes"
            value={String(data?.total ?? 0)}
            icon={<MessageCircle className="h-4 w-4" />}
            iconBg="bg-blue-50 text-blue-600"
          />
          <KpiCard
            label="Aguardando +24h"
            value={String(urgentes)}
            icon={<AlertTriangle className="h-4 w-4" />}
            iconBg={
              urgentes > 0
                ? "bg-red-50 text-red-600"
                : "bg-gray-50 text-gray-400"
            }
          />
          <KpiCard
            label="Espera Media"
            value={
              tempoMedioHoras > 0 ? `${tempoMedioHoras}h` : "—"
            }
            icon={<Clock className="h-4 w-4" />}
            iconBg="bg-orange-50 text-orange-600"
          />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {(["pendentes", "respondidas"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "px-4 py-1.5 rounded-md text-sm font-medium transition-colors capitalize",
              tab === t
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700",
            )}
          >
            {t === "pendentes" ? "Pendentes" : "Respondidas"}
          </button>
        ))}
      </div>

      {/* Conteudo */}
      {isLoading ? (
        <div className="flex items-center justify-center h-48 text-gray-400">
          Carregando perguntas...
        </div>
      ) : isError ? (
        <div className="flex items-center justify-center h-48 text-red-500">
          Erro ao carregar perguntas. Verifique a conexao.
        </div>
      ) : questions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400 space-y-2">
          <MessageCircle className="h-12 w-12 opacity-20" />
          <p className="text-sm">
            {tab === "pendentes"
              ? "Nenhuma pergunta pendente. Tudo em dia!"
              : "Nenhuma pergunta respondida encontrada."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {questions.map((q) => (
            <QuestionCard
              key={`${q._account_id}-${q.id}`}
              question={q}
              isPendente={tab === "pendentes"}
            />
          ))}
        </div>
      )}

      {/* Rodape */}
      {questions.length > 0 && (
        <p className="text-xs text-gray-400 text-right">
          Exibindo {questions.length} perguntas
        </p>
      )}
    </div>
  );
}
