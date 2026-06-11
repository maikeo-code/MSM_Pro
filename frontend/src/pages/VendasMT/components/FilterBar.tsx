// Barra de filtros + abas de status — como no Mercado Turbo.
const FILTROS = ["SKU Venda", "Data Venda", "Nº Venda", "ID Anúncio (MLB)", "Apelido Comprador", "CEP Comprador", "Nome Comprador", "E-mail Comprador", "Cód. Rastreio"];

export const ABAS_STATUS = [
  "Abertas", "Em Preparação", "Despachadas", "Pgto. Pendentes",
  "Envios Pendentes", "Flex", "Imprimir", "Aguarda Qualificar", "Mediação", "Entregues",
];

export default function FilterBar({ abaAtiva, setAba, total }: {
  abaAtiva: string; setAba: (a: string) => void; total: number;
}) {
  return (
    <div className="space-y-3">
      <div className="flex gap-4">
        <div className="bg-white rounded-[10px] shadow-sm px-4 py-3 flex items-center gap-2 flex-1">
          <select className="border border-[#614785]/30 rounded text-[#614785] px-2 py-1.5 text-[12.5px]">
            <option>Filtros</option>
            {FILTROS.map((f) => <option key={f}>{f}</option>)}
          </select>
          <input
            placeholder="Digite o Termo de Busca"
            className="flex-1 border border-[#33313B]/15 rounded px-3 py-1.5 text-[12.5px] outline-none focus:border-[#614785]"
          />
          <button className="border border-[#614785] text-[#614785] rounded px-4 py-1.5 hover:bg-[#614785] hover:text-white transition-colors">Buscar</button>
        </div>
        <div className="bg-white rounded-[10px] shadow-sm px-4 py-3 flex items-center">
          <button className="border border-[#614785] text-[#614785] rounded px-4 py-1.5 hover:bg-[#614785] hover:text-white transition-colors">↓ Baixar NF-es</button>
        </div>
      </div>

      <div className="flex items-center gap-1 overflow-x-auto bg-white rounded-t-[10px] shadow-sm px-2 pt-2">
        {ABAS_STATUS.map((aba) => (
          <button
            key={aba}
            onClick={() => setAba(aba)}
            className={`whitespace-nowrap px-3 py-2 text-[12.5px] border-b-2 transition-colors ${
              abaAtiva === aba ? "border-[#614785] text-[#614785] font-semibold" : "border-transparent text-[#33313B]/55 hover:text-[#33313B]"
            }`}
          >
            {aba}
            {aba === "Abertas" && (
              <span className="ml-1.5 bg-[#614785] text-white text-[10px] rounded-full px-1.5 py-0.5">{total}</span>
            )}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-b-[10px] shadow-sm px-4 py-3 flex items-center gap-4 -mt-3">
        <span className="text-[11px] text-[#33313B]/50 font-semibold uppercase">Período</span>
        <select className="border border-[#33313B]/15 rounded px-2 py-1.5 text-[12.5px]">
          <option>Todos</option><option>Últimos 3 dias</option><option>Últimos 7 dias</option>
        </select>
        <button className="bg-[#FFC107] text-[#33313B] rounded px-4 py-1.5 font-medium hover:brightness-95">🧹 Limpar Filtros</button>
        <label className="ml-auto flex items-center gap-2 text-[12px] text-[#33313B]/70">
          <input type="checkbox" /> Somente vendas com NF-e não emitidas
        </label>
      </div>
    </div>
  );
}
