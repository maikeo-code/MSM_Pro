import React from "react";

/**
 * Renderiza texto com bold (**texto**) de forma segura usando React elements.
 * React ja escapa automaticamente strings passadas como children — escapeHtml nao e necessario.
 */
function renderBoldText(text: string): React.ReactNode[] {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((part, idx) => {
    // Indices impares sao o conteudo entre **
    if (idx % 2 === 1) {
      return <strong key={idx}>{part}</strong>;
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

/**
 * Renderiza analise em markdown simples (paragrafos, listas com -, bold com **).
 * Substitui dangerouslySetInnerHTML por renderizacao segura com React elements.
 */
export function RenderAnalise({ texto }: { texto: string }) {
  const paragrafos = texto.split(/\n\n+/);
  return (
    <div className="space-y-3 text-sm leading-relaxed text-gray-700">
      {paragrafos.map((paragrafo, i) => {
        const linhas = paragrafo.split("\n");
        const ehLista = linhas.every(
          (l) => l.trim().startsWith("- ") || l.trim() === ""
        );
        if (ehLista && linhas.some((l) => l.trim().startsWith("- "))) {
          return (
            <ul key={i} className="list-none space-y-1 pl-0">
              {linhas
                .filter((l) => l.trim().startsWith("- "))
                .map((item, j) => {
                  const conteudo = item.replace(/^-\s+/, "");
                  return (
                    <li key={j} className="flex items-start gap-2">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
                      <span>{renderBoldText(conteudo)}</span>
                    </li>
                  );
                })}
            </ul>
          );
        }
        return <p key={i}>{renderBoldText(paragrafo)}</p>;
      })}
    </div>
  );
}
