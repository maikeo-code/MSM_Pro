// Réplica do modal "Custo e Imposto da Venda" do Mercado Turbo (dialog dialog-atributo-produto-venda).
// Custo (R$) e Imposto (%) são POR SKU. Ver mercadoturbo_research/02-MODAIS-VENDAS.md.
import { useState } from "react";
import type { Venda } from "../types";
import { brl } from "../calc";

interface Props {
  venda: Venda;
  onFechar: () => void;
  onSalvar: (sku: string, custo: number, impostoPct: number, opts: { aplicarCadastro: boolean; aplicarMulticontas: boolean }) => void;
}

export default function ModalCustoImposto({ venda, onFechar, onSalvar }: Props) {
  const [custo, setCusto] = useState(venda.custoProduto ? Math.abs(venda.custoProduto) : 0);
  const [impostoPct, setImpostoPct] = useState(venda.impostoPct ?? 0);
  const [aplicarCadastro, setAplicarCadastro] = useState(true);
  const [aplicarMulticontas, setAplicarMulticontas] = useState(false);

  const impostoValor = (venda.produtos * impostoPct) / 100;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-24" onClick={onFechar}>
      <div className="bg-white rounded-[10px] shadow-lg w-[440px] max-w-[92vw]" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#33313B]/10 bg-[#614785] text-white rounded-t-[10px]">
          <span className="font-semibold text-[13px]">Custo e Imposto da Venda</span>
          <button onClick={onFechar} className="text-white/80 hover:text-white text-lg leading-none">×</button>
        </div>

        <div className="px-4 py-4 space-y-3 text-[12.5px]">
          <div className="text-[11px] text-[#33313B]/50">Venda #{venda.venda} · {venda.titulo.slice(0, 48)}…</div>

          <label className="block">
            <span className="text-[#33313B]/60">SKU</span>
            <input value={venda.sku ?? ""} readOnly
              className="mt-1 w-full border border-[#33313B]/15 rounded px-2 py-1.5 bg-[#E4E2E9]/40" />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-[#33313B]/60">Custo (R$)</span>
              <input type="number" step="0.01" value={custo} onChange={(e) => setCusto(+e.target.value)}
                className="mt-1 w-full border border-[#33313B]/15 rounded px-2 py-1.5 tabular-nums" />
            </label>
            <label className="block">
              <span className="text-[#33313B]/60">Imposto (%)</span>
              <input type="number" step="0.01" value={impostoPct} onChange={(e) => setImpostoPct(+e.target.value)}
                className="mt-1 w-full border border-[#33313B]/15 rounded px-2 py-1.5 tabular-nums" />
            </label>
          </div>

          <div className="text-[11px] text-[#33313B]/55 bg-[#E4E2E9]/50 rounded px-2 py-1.5">
            Imposto sobre {brl(venda.produtos)} = <b className="text-[#D43B4F]">{brl(impostoValor)}</b>
          </div>

          <label className="flex items-start gap-2 text-[11.5px] cursor-pointer">
            <input type="checkbox" checked={aplicarCadastro} onChange={(e) => setAplicarCadastro(e.target.checked)} className="mt-0.5" />
            <span>Quero atualizar o Custo &amp; Imposto deste SKU no cadastro de produtos</span>
          </label>
          <label className="flex items-start gap-2 text-[11.5px] cursor-pointer">
            <input type="checkbox" checked={aplicarMulticontas} onChange={(e) => setAplicarMulticontas(e.target.checked)} className="mt-0.5" />
            <span>Quero cadastrar/atualizar este SKU nas outras contas do multicontas</span>
          </label>
        </div>

        <div className="flex justify-end gap-2 px-4 py-3 border-t border-[#33313B]/10">
          <button onClick={onFechar} className="px-4 py-1.5 rounded border border-[#33313B]/20 text-[12.5px] hover:bg-[#E4E2E9]">Fechar</button>
          <button
            onClick={() => onSalvar(venda.sku ?? "", custo, impostoPct, { aplicarCadastro, aplicarMulticontas })}
            className="px-4 py-1.5 rounded bg-[#329F69] text-white text-[12.5px] font-medium hover:brightness-95">
            Salvar
          </button>
        </div>
      </div>
    </div>
  );
}
