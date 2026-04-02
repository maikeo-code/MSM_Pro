import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  MessageCircle,
  Clock,
  CheckCircle,
  Send,
  AlertTriangle,
  RefreshCw,
  Search,
  Sparkles,
  Loader2,
} from "lucide-react";
import {
  listQuestions,
  answerQuestion,
  getSuggestion,
  getQuestionStats,
  syncQuestions,
  type QuestionDB,
} from "@/services/perguntasService";
import { useAccountStore } from "@/store/accountStore";
import { AccountSelector } from "@/components/AccountSelector";
import { cn } from "@/lib/utils";

// ─── Helpers ──────────────────────────────────────────────────────────────

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

// ─── Badge de Urgencia ────────────────────────────────────────────────────

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

// ─── Confianca Badge ──────────────────────────────────────────────────────

function ConfidenceBadge({ confidence }: { confidence: string | null }) {
  if (!confidence) return null;
  const colorMap = {
    high: "bg-green-100 text-green-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-orange-100 text-orange-700",
  };
  const color = colorMap[confidence as keyof typeof colorMap] || "bg-gray-100 text-gray-700";
  const labelMap = { high: "Alta", medium: "Média", low: "Baixa" };
  const label = labelMap[confidence as keyof typeof labelMap] || confidence;
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", color)}>
      {label}
    </span>
  );
}

// ─── KPI Card ─────────────────────────────────────────────────────────────

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

// ─── Question List (left panel) ────────────────────────────────────────────

interface QuestionListProps {
  questions: QuestionDB[];
  isLoading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  search: string;
  onSearchChange: (search: string) => void;
  tab: "pendentes" | "respondidas";
}

function QuestionList({
  questions,
  isLoading,
  selectedId,
  onSelect,
  search,
  onSearchChange,
  tab,
}: QuestionListProps) {
  const searchInputRef = useRef<HTMLInputElement>(null);

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    onSearchChange(value);
  }, [onSearchChange]);

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
        <input
          ref={searchInputRef}
          type="text"
          placeholder="Buscar perguntas..."
          value={search}
          onChange={handleSearchChange}
          className="w-full pl-9 pr-3 py-2 rounded-md border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Questions list */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {isLoading ? (
          <div className="text-center py-8 text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin mx-auto mb-2" />
            Carregando...
          </div>
        ) : questions.length === 0 ? (
          <div className="text-center py-8 text-gray-400 text-sm">
            {search ? "Nenhuma pergunta encontrada" : `Nenhuma pergunta ${tab === "pendentes" ? "pendente" : "respondida"}`}
          </div>
        ) : (
          questions.map((q) => (
            <button
              key={q.id}
              onClick={() => onSelect(q.id)}
              className={cn(
                "w-full text-left p-3 rounded-md border transition-all duration-200",
                selectedId === q.id
                  ? "border-blue-500 bg-blue-50/50 shadow-sm"
                  : "border-gray-100 bg-white hover:border-gray-300",
              )}
            >
              {/* Buyer + Urgencia */}
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-xs font-medium text-gray-600 truncate">
                  {q.buyer_nickname || `Comprador #${q.buyer_id}`}
                </span>
                {tab === "pendentes" && <UrgenciaBadge dateStr={q.date_created} />}
              </div>

              {/* Texto truncado */}
              <p className="text-sm text-gray-700 line-clamp-2 mb-1">{q.text}</p>

              {/* Tempo e MLB */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">{tempoRelativo(q.date_created)}</span>
                <span className="font-mono text-xs bg-gray-100 text-gray-600 rounded px-1.5 py-0.5">
                  {q.mlb_id}
                </span>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Question Detail (right panel) ─────────────────────────────────────────

interface QuestionDetailProps {
  question: QuestionDB | null;
  tab: "pendentes" | "respondidas";
  accountId: string | null;
}

function QuestionDetail({ question, tab, accountId }: QuestionDetailProps) {
  const queryClient = useQueryClient();
  const [resposta, setResposta] = useState("");
  const [editedSuggestion, setEditedSuggestion] = useState(false);

  // Suggestion mutation
  const suggestMutation = useMutation({
    mutationFn: (regenerate: boolean = false) =>
      question ? getSuggestion(question.id, regenerate) : Promise.reject(),
  });

  // Answer mutation
  const answerMutation = useMutation({
    mutationFn: (text: string) =>
      answerQuestion(
        question!.id,
        text,
        accountId || question!.ml_account_id,
        editedSuggestion ? "ai" : "manual",
        editedSuggestion,
      ),
    onSuccess: () => {
      setResposta("");
      setEditedSuggestion(false);
      queryClient.invalidateQueries({ queryKey: ["perguntas"] });
      queryClient.invalidateQueries({ queryKey: ["perguntas-stats"] });
    },
  });

  const handleUseAISuggestion = () => {
    if (suggestMutation.data?.suggestion) {
      setResposta(suggestMutation.data.suggestion);
      setEditedSuggestion(false);
    }
  };

  const handleGenerateSuggestion = () => {
    suggestMutation.mutate(false);
  };

  const handleAnswer = () => {
    if (!resposta.trim()) return;
    answerMutation.mutate(resposta);
  };

  const handleSkip = () => {
    setResposta("");
    setEditedSuggestion(false);
  };

  if (!question) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-400 space-y-3">
        <MessageCircle className="h-12 w-12 opacity-20" />
        <p className="text-sm">Selecione uma pergunta para respondê-la</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Cabeçalho */}
      <div className="border-b border-gray-200 pb-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide">MLB / Item</p>
            <p className="font-mono text-sm font-medium text-gray-900">{question.mlb_id}</p>
          </div>
          <span className="text-xs text-gray-400 whitespace-nowrap">{formatarData(question.date_created)}</span>
        </div>

        {question.item_title && (
          <p className="text-sm text-gray-700 font-medium line-clamp-2">{question.item_title}</p>
        )}

        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-600">
            De: <span className="font-medium">{question.buyer_nickname || `#${question.buyer_id}`}</span>
          </p>
          {tab === "pendentes" && <UrgenciaBadge dateStr={question.date_created} />}
        </div>
      </div>

      {/* Pergunta */}
      <div className="space-y-1">
        <p className="text-xs text-gray-400 uppercase tracking-wide font-medium">Pergunta</p>
        <div className="bg-gray-50 rounded-md p-3 border border-gray-200">
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{question.text}</p>
        </div>
      </div>

      {/* Se respondida, mostrar resposta existente */}
      {question.answer_text && (
        <div className="space-y-1">
          <p className="text-xs text-gray-400 uppercase tracking-wide font-medium">Resposta enviada</p>
          <div className="bg-green-50 rounded-md p-3 border border-green-200">
            <p className="text-xs text-green-600 mb-1 font-medium">{formatarData(question.answer_date!)}</p>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{question.answer_text}</p>
          </div>
        </div>
      )}

      {/* Se pendente e temos sugestao IA */}
      {tab === "pendentes" && question.ai_suggestion_text && !question.answer_text && (
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-400 uppercase tracking-wide font-medium">Sugestao IA</p>
            <ConfidenceBadge confidence={question.ai_suggestion_confidence} />
          </div>
          <div className="bg-violet-50 rounded-md p-3 border border-violet-200 space-y-2">
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {question.ai_suggestion_text}
            </p>
            <div className="flex items-center gap-2 pt-2">
              <button
                onClick={handleUseAISuggestion}
                className="inline-flex items-center gap-1 rounded-md bg-violet-600 text-white px-2 py-1 text-xs font-medium hover:bg-violet-700 transition-colors"
              >
                <Sparkles className="h-3 w-3" />
                Usar resposta
              </button>
              <button
                onClick={() => {
                  suggestMutation.mutate(true);
                }}
                disabled={suggestMutation.isPending}
                className="text-xs text-gray-500 hover:text-gray-700 transition-colors"
              >
                Regenerar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Se pendente e NAO temos sugestao, mostrar botao para gerar */}
      {tab === "pendentes" && !question.ai_suggestion_text && !question.answer_text && (
        <button
          onClick={handleGenerateSuggestion}
          disabled={suggestMutation.isPending}
          className={cn(
            "inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
            suggestMutation.isPending
              ? "bg-gray-100 text-gray-400 cursor-not-allowed"
              : "bg-violet-100 text-violet-700 hover:bg-violet-200",
          )}
        >
          {suggestMutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Gerando sugestao...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Gerar sugestao IA
            </>
          )}
        </button>
      )}

      {/* Formulario de resposta (apenas para pendentes) */}
      {tab === "pendentes" && !question.answer_text && (
        <div className="space-y-2 mt-auto pt-4 border-t border-gray-200">
          <div className="space-y-1">
            <p className="text-xs text-gray-400 uppercase tracking-wide font-medium">Sua resposta</p>
            <textarea
              value={resposta}
              onChange={(e) => {
                setResposta(e.target.value);
                if (suggestMutation.data?.suggestion === e.target.value) {
                  setEditedSuggestion(false);
                } else if (suggestMutation.data) {
                  setEditedSuggestion(true);
                }
              }}
              placeholder="Digite ou cole uma resposta..."
              rows={4}
              maxLength={2000}
              className="w-full rounded-md border border-gray-200 bg-white text-sm text-gray-900 placeholder:text-gray-400 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            />
            <div className="flex items-center justify-between">
              <p className="text-xs text-gray-400">{resposta.length} / 2000 caracteres</p>
              {editedSuggestion && <span className="text-xs text-orange-600 font-medium">Sugestao editada</span>}
            </div>
          </div>

          {/* Botoes de acao */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleAnswer}
              disabled={!resposta.trim() || answerMutation.isPending}
              className={cn(
                "flex-1 inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                "bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed",
              )}
            >
              <Send className="h-4 w-4" />
              {answerMutation.isPending ? "Enviando..." : "Enviar resposta"}
            </button>
            <button
              onClick={handleSkip}
              className="rounded-md px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition-colors"
            >
              Pular
            </button>
          </div>

          {answerMutation.isError && (
            <p className="text-xs text-red-600">Erro ao enviar resposta. Tente novamente.</p>
          )}
          {answerMutation.isSuccess && (
            <p className="text-xs text-green-600">Resposta enviada com sucesso!</p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────

type Tab = "pendentes" | "respondidas";

export default function Perguntas() {
  const [tab, setTab] = useState<Tab>("pendentes");
  const [search, setSearch] = useState("");
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const queryClient = useQueryClient();

  const { activeAccountId } = useAccountStore();

  const statusMap: Record<Tab, string> = {
    pendentes: "UNANSWERED",
    respondidas: "ANSWERED",
  };

  // Lista de perguntas
  const { data: questionsData, isLoading: listIsLoading } = useQuery({
    queryKey: ["perguntas", tab, search, activeAccountId, offset],
    queryFn: () =>
      listQuestions({
        status: statusMap[tab],
        ml_account_id: activeAccountId || undefined,
        search: search || undefined,
        limit: 20,
        offset,
      }),
    staleTime: 60_000,
  });

  // Stats
  const { data: stats } = useQuery({
    queryKey: ["perguntas-stats", activeAccountId],
    queryFn: () => getQuestionStats(activeAccountId || undefined),
    staleTime: 120_000,
  });

  // Sync manual
  const syncMutation = useMutation({
    mutationFn: syncQuestions,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["perguntas"] });
      queryClient.invalidateQueries({ queryKey: ["perguntas-stats"] });
    },
  });

  const questions = questionsData?.questions ?? [];
  const selectedQuestion = questions.find((q) => q.id === selectedQuestionId) || null;

  // KPIs
  const urgentes = useMemo(
    () => (tab === "pendentes" ? questions.filter((q) => horasDesde(q.date_created) >= 24).length : 0),
    [questions, tab],
  );

  const tempoMedioHoras = useMemo(() => {
    if (tab !== "pendentes" || questions.length === 0) return 0;
    const soma = questions.reduce((acc, q) => acc + horasDesde(q.date_created), 0);
    return Math.round(soma / questions.length);
  }, [questions, tab]);

  const taxaResposta = useMemo(() => {
    if (!stats || stats.total === 0) return 0;
    return Math.round((stats.answered / stats.total) * 100);
  }, [stats]);

  // Limpar selecao quando mudar tab
  useEffect(() => {
    setSelectedQuestionId(null);
    setOffset(0);
  }, [tab, activeAccountId]);

  return (
    <div className="p-6 space-y-6 h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Perguntas e Respostas</h1>
          <p className="text-sm text-gray-500 mt-1">
            Gerencie as perguntas dos compradores em todos os seus anuncios
          </p>
        </div>

        <div className="flex items-center gap-3">
          <AccountSelector />
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className={cn(
              "inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              syncMutation.isPending
                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700",
            )}
          >
            <RefreshCw className={cn("h-4 w-4", syncMutation.isPending && "animate-spin")} />
            {syncMutation.isPending ? "Sincronizando..." : "Sincronizar"}
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {tab === "pendentes" && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard
            label="Total Pendentes"
            value={String(stats?.unanswered ?? 0)}
            icon={<MessageCircle className="h-4 w-4" />}
            iconBg="bg-blue-50 text-blue-600"
          />
          <KpiCard
            label="Urgentes (+24h)"
            value={String(urgentes)}
            icon={<AlertTriangle className="h-4 w-4" />}
            iconBg={urgentes > 0 ? "bg-red-50 text-red-600" : "bg-gray-50 text-gray-400"}
          />
          <KpiCard
            label="Tempo Medio"
            value={tempoMedioHoras > 0 ? `${tempoMedioHoras}h` : "—"}
            icon={<Clock className="h-4 w-4" />}
            iconBg="bg-orange-50 text-orange-600"
          />
          <KpiCard
            label="Taxa Resposta"
            value={`${taxaResposta}%`}
            icon={<CheckCircle className="h-4 w-4" />}
            iconBg="bg-green-50 text-green-600"
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
              tab === t ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700",
            )}
          >
            {t === "pendentes" ? "Pendentes" : "Respondidas"}
          </button>
        ))}
      </div>

      {/* Master-Detail Layout */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 flex-1 min-h-0">
        {/* Left panel - Lista */}
        <div className="md:col-span-1 bg-white rounded-lg shadow-sm border border-gray-100 p-4 flex flex-col min-h-96 md:min-h-full">
          <QuestionList
            questions={questions}
            isLoading={listIsLoading}
            selectedId={selectedQuestionId}
            onSelect={setSelectedQuestionId}
            search={search}
            onSearchChange={setSearch}
            tab={tab}
          />
        </div>

        {/* Right panel - Detalhe */}
        <div className="md:col-span-2 bg-white rounded-lg shadow-sm border border-gray-100 p-4 flex flex-col min-h-96 md:min-h-full">
          <QuestionDetail
            question={selectedQuestion}
            tab={tab}
            accountId={activeAccountId || null}
          />
        </div>
      </div>

      {/* Rodape */}
      {questions.length > 0 && (
        <p className="text-xs text-gray-400 text-right">
          Exibindo {questions.length} de {questionsData?.total ?? 0} perguntas
        </p>
      )}
    </div>
  );
}
