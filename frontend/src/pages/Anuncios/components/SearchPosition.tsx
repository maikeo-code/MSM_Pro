import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, AlertCircle, CheckCircle, TrendingDown } from "lucide-react";
import listingsService from "@/services/listingsService";
import { cn } from "@/lib/utils";

interface SearchPositionProps {
  mlbId: string;
}

export function SearchPosition({ mlbId }: SearchPositionProps) {
  const [keyword, setKeyword] = React.useState("");
  const [searchTriggered, setSearchTriggered] = React.useState(false);

  const { data: result, isLoading, error } = useQuery({
    queryKey: ["search-position", mlbId, keyword],
    queryFn: () => listingsService.getSearchPosition(mlbId, keyword),
    enabled: searchTriggered && keyword.trim().length >= 2,
    retry: 1,
  });

  function handleSearch() {
    if (keyword.trim().length >= 2) {
      setSearchTriggered(true);
    }
  }

  function handleKeyPress(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      handleSearch();
    }
  }

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center gap-2 mb-4">
        <Search className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">Posicao na Busca</h2>
      </div>

      <div className="space-y-4">
        <div className="flex items-end gap-3">
          <div className="flex flex-col gap-1 flex-1 max-w-md">
            <label className="text-xs font-medium text-muted-foreground">
              Palavra-chave para buscar
            </label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => {
                setKeyword(e.target.value);
                setSearchTriggered(false);
              }}
              onKeyPress={handleKeyPress}
              placeholder="Ex: iPhone 13 branco"
              className="h-10 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              minLength={2}
              maxLength={200}
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={isLoading || keyword.trim().length < 2}
            className="inline-flex items-center gap-1.5 h-10 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            <Search className="h-4 w-4" />
            Buscar
          </button>
        </div>

        {error && (
          <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive flex items-start gap-3">
            <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
            <div>
              <p className="font-semibold">Erro ao buscar posicao</p>
              <p className="text-xs mt-1">Verifique a conexao e tente novamente.</p>
            </div>
          </div>
        )}

        {isLoading && (
          <div className="rounded-md bg-blue-50 border border-blue-200 px-4 py-4 text-sm text-blue-900">
            Buscando sua posicao nos resultados... Isso pode levar alguns segundos.
          </div>
        )}

        {searchTriggered && !isLoading && result && (
          <div className="space-y-3">
            {result.found ? (
              <div className="rounded-md bg-green-50 border border-green-200 px-4 py-4">
                <div className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <p className="font-semibold text-green-900">
                      Encontrado em posicao {result.position}
                    </p>
                    <p className="text-sm text-green-800 mt-1">
                      Sua listagem aparece na pagina {result.page} dos resultados de busca.
                      Total de {result.total_results} resultados para "{result.keyword}".
                    </p>
                    <div className="mt-3 flex items-center gap-4 text-xs text-green-700 font-medium">
                      <div>
                        <span className="block text-green-900 font-bold text-base">
                          {result.position}
                        </span>
                        Posicao
                      </div>
                      <div>
                        <span className="block text-green-900 font-bold text-base">
                          {result.page}
                        </span>
                        Pagina
                      </div>
                      <div>
                        <span className="block text-green-900 font-bold text-base">
                          {result.total_results}
                        </span>
                        Total
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-md bg-yellow-50 border border-yellow-200 px-4 py-4">
                <div className="flex items-start gap-3">
                  <TrendingDown className="h-5 w-5 text-yellow-600 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-semibold text-yellow-900">
                      Nao encontrado nos primeiros 200 resultados
                    </p>
                    <p className="text-sm text-yellow-800 mt-1">
                      Seu anuncio nao aparece nas primeiras 4 paginas de resultados para "{result.keyword}".
                      Total de {result.total_results} resultados.
                    </p>
                    <p className="text-xs text-yellow-700 mt-2">
                      Dica: Verifique se sua palavra-chave esta no titulo e descricao do anuncio.
                      Considere ajustar o preco para melhor competitividade.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {!searchTriggered && !isLoading && !error && (
          <div className="rounded-md bg-muted px-4 py-3 text-sm text-muted-foreground">
            Digite uma palavra-chave e clique em "Buscar" para ver em que posicao seu anuncio aparece nos resultados do Mercado Livre.
          </div>
        )}
      </div>
    </div>
  );
}
