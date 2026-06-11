// Aba "Vendas (MT)" — réplica fiel da tela de Vendas do Mercado Turbo, dentro do MSM_Pro.
// Dados ao vivo pela MESMA cadeia de endpoints do Turbo (orders → tarifa → frete → fórmula),
// usando o OAuth do ML que o MSM_Pro já gerencia. Ver mercadoturbo_research/03-MECANISMO-ENDPOINTS.md.
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { listVendasMT, type VendasMTResponse } from "@/services/vendasMtService";
import { useActiveAccount } from "@/hooks/useActiveAccount";
import KpiCards from "./components/KpiCards";
import FilterBar from "./components/FilterBar";
import VendaCard from "./components/VendaCard";

export default function VendasMT() {
  const accountId = useActiveAccount();
  const [aba, setAba] = useState("Abertas");
  const [period] = useState("30d");

  const { data, isLoading, isError, error } = useQuery<VendasMTResponse>({
    queryKey: ["vendas-mt", period, accountId],
    queryFn: () => listVendasMT(period, accountId),
    staleTime: 5 * 60 * 1000,
  });

  const vendas = data?.vendas ?? [];

  const kpis = useMemo(() => {
    const qtd = vendas.length;
    const valor = vendas.reduce((s, v) => s + (v.total ?? 0), 0);
    return { qtd, valor };
  }, [vendas]);

  return (
    <div className="min-h-full bg-[#E4E2E9] text-[#33313B] p-4">
      <div className="max-w-[1280px] mx-auto space-y-4">
        {/* cabeçalho identidade MT */}
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-bold text-[#614785]">Vendas (MT)</span>
          <span className="text-[10px] bg-[#614785]/10 text-[#614785] rounded px-1.5 py-0.5">réplica Mercado Turbo</span>
          {data?.conta && <span className="ml-auto text-[11px] text-[#33313B]/50">Conta: {data.conta}</span>}
        </div>

        <KpiCards qtdMes={kpis.qtd} valorMes={kpis.valor} />
        <FilterBar abaAtiva={aba} setAba={setAba} total={vendas.length} />

        {isLoading && (
          <div className="text-center text-[12px] text-[#33313B]/50 py-10">⏳ Carregando vendas via cadeia ML…</div>
        )}
        {isError && (
          <div className="text-center text-[12px] text-[#D43B4F] bg-[#D43B4F]/10 rounded px-3 py-3">
            Falha ao carregar: {(error as Error)?.message ?? "erro"}. Verifique se há conta ML conectada.
          </div>
        )}
        {!isLoading && !isError && vendas.length === 0 && (
          <div className="text-center text-[12px] text-[#33313B]/50 py-10">
            Nenhuma venda no período. Conecte/atualize a conta ML em Configurações.
          </div>
        )}

        <div className="space-y-2">
          {vendas.map((v) => (
            <VendaCard key={v.venda} v={v} />
          ))}
        </div>

        {vendas.length > 0 && (
          <footer className="text-center text-[11px] text-[#33313B]/40 pb-6">
            Cadeia de endpoints do Mercado Turbo (ML ao vivo) · {vendas.length} vendas
          </footer>
        )}
      </div>
    </div>
  );
}
