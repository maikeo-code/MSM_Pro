// KPIs do topo — "Vendas Aprovadas (Qtd)" e "(R$)" com sparkline, como no Mercado Turbo.
import { useState } from "react";

function Sparkline({ seed }: { seed: number }) {
  const bars = Array.from({ length: 24 }, (_, i) => 20 + (Math.sin(i * seed) + 1) * 35);
  return (
    <div className="flex items-end gap-[2px] h-16 opacity-30">
      {bars.map((h, i) => (
        <div key={i} className="w-[6px] bg-[#614785] rounded-sm" style={{ height: `${h}%` }} />
      ))}
    </div>
  );
}

function Card({ titulo, mesPassado, mesAtual, children }: {
  titulo: string; mesPassado: string; mesAtual: string; children?: React.ReactNode;
}) {
  return (
    <div className="relative bg-white rounded-[10px] shadow-sm px-5 py-4 flex-1 overflow-hidden">
      <div className="flex items-start justify-between">
        <h3 className="text-[#614785] font-semibold text-[13px]">{titulo}</h3>
        {children}
      </div>
      <div className="flex items-end gap-10 mt-3">
        <div>
          <div className="text-[#33313B]/50 text-[11px]">Mês Passado</div>
          <div className="font-bold text-[18px]">{mesPassado}</div>
        </div>
        <div>
          <div className="text-[#33313B]/50 text-[11px]">Mês Atual</div>
          <div className="font-bold text-[18px]">{mesAtual}</div>
        </div>
        <div className="ml-auto"><Sparkline seed={titulo.length} /></div>
      </div>
    </div>
  );
}

export default function KpiCards({ qtdMes, valorMes }: { qtdMes?: number; valorMes?: number }) {
  const [incluirFrete, setIncluirFrete] = useState(false);
  const brl = (n: number) => "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (
    <div className="flex gap-4">
      <Card titulo="Vendas Aprovadas (Qtd)" mesPassado="—" mesAtual={qtdMes != null ? String(qtdMes) : "—"} />
      <Card
        titulo={incluirFrete ? "Vendas aprovadas + Frete comprador" : "Vendas Aprovadas (R$)"}
        mesPassado="—"
        mesAtual={valorMes != null ? brl(valorMes) : "—"}
      >
        <label className="flex items-center gap-1.5 text-[11px] text-[#33313B]/70 cursor-pointer">
          <input type="checkbox" checked={incluirFrete} onChange={(e) => setIncluirFrete(e.target.checked)} />
          Incluir frete comprador
        </label>
      </Card>
    </div>
  );
}
