import { useState, useRef, useEffect } from "react";
import { X, Send, Sparkles, Loader2 } from "lucide-react";
import { consultorService, type ChatMessage } from "@/services/consultorService";
import { RenderAnalise } from "@/components/RenderAnalise";
import { cn } from "@/lib/utils";

interface ConsultorDrawerProps {
  aberto: boolean;
  onFechar: () => void;
}

const SUGESTOES = [
  "Como estão minhas vendas hoje?",
  "Quais anúncios estão com estoque crítico?",
  "Qual meu produto mais rentável nos últimos 30 dias?",
  "Resumo financeiro do mês",
];

interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export function ConsultorDrawer({ aberto, onFechar }: ConsultorDrawerProps) {
  const [messages, setMessages] = useState<DisplayMessage[]>([
    {
      role: 'assistant',
      content: 'Olá! Sou o **Consultor IA** do MSM Pro. Posso analisar seus dados de vendas, estoque, financeiro e concorrência. O que gostaria de saber?',
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Scroll automático
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus no input quando abre
  useEffect(() => {
    if (aberto) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [aberto]);

  const handleSend = async (text?: string) => {
    const messageText = (text || input).trim();
    if (!messageText || isLoading) return;

    const userMsg: DisplayMessage = { role: 'user', content: messageText, timestamp: new Date() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      // Montar histórico (excluindo a mensagem de boas-vindas)
      const history: ChatMessage[] = messages
        .slice(1) // pula boas-vindas
        .map(m => ({ role: m.role, content: m.content }));

      const response = await consultorService.chat(messageText, history);

      const assistantMsg: DisplayMessage = {
        role: 'assistant',
        content: response.reply,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: DisplayMessage = {
        role: 'assistant',
        content: 'Desculpe, ocorreu um erro ao processar sua pergunta. Tente novamente.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!aberto) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 bg-black/40 z-50 transition-opacity"
        onClick={onFechar}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-full max-w-lg bg-card border-l shadow-xl z-50 flex flex-col animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gradient-to-r from-blue-600 to-violet-600">
          <div className="flex items-center gap-2 text-white">
            <Sparkles className="h-5 w-5" />
            <h2 className="text-lg font-bold">Consultor IA</h2>
          </div>
          <button
            onClick={onFechar}
            className="p-1 rounded-md text-white/80 hover:text-white hover:bg-white/20 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Mensagens */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                "flex",
                msg.role === 'user' ? "justify-end" : "justify-start"
              )}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-lg px-4 py-3 text-sm",
                  msg.role === 'user'
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-foreground"
                )}
              >
                {msg.role === 'assistant' ? (
                  <RenderAnalise texto={msg.content} />
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                )}
              </div>
            </div>
          ))}

          {/* Loading indicator */}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-lg px-4 py-3 flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Analisando seus dados...
              </div>
            </div>
          )}

          {/* Sugestões (só quando não há conversa além da boas-vindas) */}
          {messages.length <= 1 && !isLoading && (
            <div className="space-y-2 pt-2">
              <p className="text-xs text-muted-foreground font-medium">Sugestões:</p>
              <div className="flex flex-wrap gap-2">
                {SUGESTOES.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(s)}
                    className="text-xs px-3 py-1.5 rounded-full border hover:bg-accent hover:text-accent-foreground transition-colors text-muted-foreground"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="border-t px-4 py-3">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Pergunte sobre seus dados..."
              rows={1}
              className="flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring max-h-24"
              disabled={isLoading}
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || isLoading}
              className="shrink-0 rounded-lg bg-primary p-2 text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
