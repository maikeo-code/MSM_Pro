import { Sparkles, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { RenderAnalise } from "@/components/RenderAnalise";
import type { ConsultorResponse } from "@/services/consultorService";

export interface ConsultorDrawerProps {
  aberto: boolean;
  onFechar: () => void;
  loading: boolean;
  resultado: ConsultorResponse | null;
  erro: string | null;
  titulo?: string;
  subtituloAnalise?: string;
  labelRodape?: (r: ConsultorResponse) => string;
}

export function ConsultorDrawer({
  aberto,
  onFechar,
  loading,
  resultado,
  erro,
  titulo = "Consultor IA",
  subtituloAnalise = "Analise gerada",
  labelRodape,
}: ConsultorDrawerProps) {
  return (
    <>
      {/* Overlay */}
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/30 backdrop-blur-sm transition-opacity duration-300",
          aberto
            ? "opacity-100 pointer-events-auto"
            : "opacity-0 pointer-events-none"
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
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 bg-gradient-to-r from-blue-600 to-blue-700">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-white" />
            <h2 className="text-base font-semibold text-white">{titulo}</h2>
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
                <div
                  className="absolute inset-0 rounded-full bg-blue-50"
                  style={{ zIndex: -1 }}
                />
              </div>
              <p className="text-sm text-gray-500 font-medium">
                Analisando seus anuncios...
              </p>
              <p className="text-xs text-gray-400 text-center max-w-xs">
                A IA esta processando seus dados de vendas, estoque e conversao
                para gerar insights personalizados.
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
                <p className="text-xs text-blue-600 font-medium uppercase tracking-wide">
                  {subtituloAnalise}
                </p>
              </div>
              <RenderAnalise texto={resultado.analise} />
            </div>
          )}

          {!loading && !erro && !resultado && (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
              <Sparkles className="h-10 w-10 text-blue-200" />
              <p className="text-sm text-gray-500">
                Clique em "Analisar" para gerar insights com IA
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        {resultado && !loading && (
          <div className="border-t border-gray-200 px-6 py-3 bg-gray-50">
            <p className="text-xs text-gray-500">
              {labelRodape
                ? labelRodape(resultado)
                : `${resultado.anuncios_analisados} anuncios analisados \u2022 ${new Date(
                    resultado.gerado_em
                  ).toLocaleString("pt-BR", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}`}
            </p>
          </div>
        )}
      </div>
    </>
  );
}
