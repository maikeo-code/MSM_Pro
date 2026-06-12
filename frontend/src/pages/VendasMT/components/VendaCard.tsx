// Card de venda — replica a anatomia + bloco financeiro do Mercado Turbo.
import { useState } from "react";
import type { Venda } from "../types";
import { brl, pct, corMargem } from "../calc";
import ModalCustoImposto from "./ModalCustoImposto";
import ModalEntrega from "./ModalEntrega";

function Linha({ label, valor, forte, cor }: { label: string; valor: string; forte?: boolean; cor?: string }) {
  return (
    <div className="flex items-center justify-between gap-6">
      <span className={`text-[11.5px] ${forte ? "font-semibold text-[#33313B]" : "text-[#33313B]/55"}`}>{label}</span>
      <span className={`tabular-nums ${forte ? "font-bold" : ""} ${cor ?? "text-[#33313B]"}`}>{valor}</span>
    </div>
  );
}

export default function VendaCard({ v }: { v: Venda }) {
  const [modal, setModal] = useState<null | "custo" | "entrega">(null);

  return (
    <div className="bg-white rounded-[10px] shadow-sm border border-[#33313B]/5 flex overflow-hidden">
      <div className="w-1 bg-[#614785]" />

      {/* coluna comprador / pedido */}
      <div className="w-52 shrink-0 px-4 py-3 border-r border-[#33313B]/10">
        <div className="text-[11px] text-[#33313B]/45">Venda</div>
        <div className="font-semibold text-[#614785]">#{v.venda}</div>
        <div className="mt-2 text-[11px] text-[#33313B]/45">Data</div>
        <div className="text-[12px]">{v.data ?? "—"}</div>
        <div className="mt-2 inline-block text-[10.5px] bg-[#614785]/10 text-[#614785] rounded px-1.5 py-0.5">
          {v.status ?? "—"}
        </div>
      </div>

      {/* coluna produto */}
      <div className="flex-1 px-4 py-3 border-r border-[#33313B]/10 min-w-0">
        <div className="text-[13px] font-medium text-[#33313B] leading-snug line-clamp-2">{v.titulo}</div>
        <div className="mt-2 flex items-center gap-2 flex-wrap text-[11px]">
          <span className="bg-[#33313B]/8 rounded px-1.5 py-0.5">SKU: {v.sku ?? "—"}</span>
          <span className="bg-[#329F69]/15 text-[#329F69] rounded px-1.5 py-0.5 font-medium">FULL</span>
          <span className="text-[#614785]">{v.mlb}</span>
        </div>
        <button
          onClick={() => setModal("entrega")}
          title="Clique para ver informações do frete"
          className="mt-2 text-[11px] text-[#614785] hover:underline inline-flex items-center gap-1"
        >
          🚚 Mercado Envios Grátis · Prioritário
        </button>
      </div>

      {/* coluna financeira — estrutura EXATA do Mercado Turbo */}
      <div className="w-60 shrink-0 px-4 py-3 bg-[#E4E2E9]/40">
        <Linha label="💳 Pago comprador" valor={brl(v.pago)} forte />
        <Linha label="🚚 Frete" valor={brl(v.frete)} cor="text-[#D43B4F]" />
        <Linha label="🤝 Tarifa de Venda ML" valor={brl(v.tarifaML)} cor="text-[#D43B4F]" />
        <div className="my-1 border-t border-[#0891b2]/30" />
        <Linha label="👛 Lucro Bruto" valor={brl(v.lucroBruto)} cor="text-[#0891b2]" forte />
        {v.temCusto ? (
          <>
            <Linha label="Custo do Produto" valor={brl(v.custoProduto)} cor="text-[#D43B4F]" />
            <Linha label="Imposto do Produto" valor={brl(v.imposto)} cor="text-[#D43B4F]" />
          </>
        ) : null}
        <button
          onClick={() => setModal("custo")}
          title="Clique aqui para alterar o Custo & Imposto"
          className={`mt-1 w-full text-[10.5px] rounded px-2 py-1 font-medium ${
            v.temCusto ? "bg-[#614785]/10 text-[#614785] hover:bg-[#614785]/20" : "bg-[#FFC107]/20 text-[#FFC107] hover:bg-[#FFC107]/30"
          }`}
        >
          {v.temCusto ? "✎ Editar Custo & Imposto" : "⚠ Custo & Imposto não informados — clique"}
        </button>
        <div className="my-1 border-t border-[#33313B]/10" />
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-semibold">Lucro</span>
          <span className={`font-bold text-[14px] tabular-nums ${corMargem(v.margem)}`}>
            {brl(v.lucro)} <span className="text-[11px]">({pct(v.margem)})</span>
          </span>
        </div>
      </div>

      {modal === "custo" && (
        <ModalCustoImposto
          venda={v}
          onFechar={() => setModal(null)}
          onSalvar={(sku, custo, impostoPct) => {
            // TODO: PATCH no cadastro de Produtos (SKU) quando ligado à edição.
            console.log("Salvar Custo & Imposto", { sku, custo, impostoPct });
            setModal(null);
          }}
        />
      )}
      {modal === "entrega" && <ModalEntrega venda={v} onFechar={() => setModal(null)} />}
    </div>
  );
}
