// Réplica do modal "Informações da Entrega" (DialogModificarEntrega) do Mercado Turbo. Somente leitura.
// Ver mercadoturbo_research/02-MODAIS-VENDAS.md.
import type { Venda } from "../types";
import { brl } from "../calc";

interface Props {
  venda: Venda;
  onFechar: () => void;
}

function Item({ label, valor }: { label: string; valor: string }) {
  return (
    <div className="flex justify-between gap-4 py-0.5">
      <span className="text-[#33313B]/55">{label}</span>
      <span className="text-right font-medium">{valor}</span>
    </div>
  );
}

export default function ModalEntrega({ venda, onFechar }: Props) {
  const e = venda.entrega;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-20" onClick={onFechar}>
      <div className="bg-white rounded-[10px] shadow-lg w-[460px] max-w-[92vw]" onClick={(ev) => ev.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#33313B]/10 bg-[#614785] text-white rounded-t-[10px]">
          <span className="font-semibold text-[13px]">Informações da Entrega</span>
          <button onClick={onFechar} className="text-white/80 hover:text-white text-lg leading-none">×</button>
        </div>

        {!e ? (
          <div className="px-4 py-8 text-center text-[12px] text-[#33313B]/50">
            Dados de entrega não disponíveis para esta venda.
          </div>
        ) : (
          <div className="px-4 py-4 text-[12px] space-y-3">
            <div className="space-y-0.5">
              <Item label="ID" valor={`#${e.envioId}`} />
              <Item label="Tipo" valor={e.tipo} />
              <Item label="Status" valor={e.status} />
              <Item label="Transportadora" valor={e.transportadora} />
              <Item label="Código de Rastreamento" valor={e.rastreamento} />
              <Item label="Manuseio" valor={e.manuseio} />
              <Item label="Entrega Prevista" valor={e.entregaPrevista} />
            </div>

            <div className="border-t border-[#33313B]/10 pt-2">
              <div className="font-semibold text-[12.5px] mb-1">Dados do Pacote</div>
              <Item label="Dimensões" valor={`${e.dimensoes.altura} × ${e.dimensoes.largura} × ${e.dimensoes.comprimento} cm`} />
              <Item label="Peso" valor={`${e.pesoG} g`} />
              <Item label="Valor Declarado" valor={brl(e.valorDeclarado)} />
            </div>

            <div className="border-t border-[#33313B]/10 pt-2">
              <div className="font-semibold text-[12.5px] mb-1">Comprador / Destinatário</div>
              <Item label="Comprador" valor={e.comprador} />
              <Item label="CPF" valor={e.cpf} />
              <div className="text-[#33313B]/55 mt-1">Endereço</div>
              <div className="text-[11.5px]">{e.enderecoDestinatario}</div>
              <Item label="CEP" valor={e.cep} />
            </div>
          </div>
        )}

        <div className="flex justify-end px-4 py-3 border-t border-[#33313B]/10">
          <button onClick={onFechar} className="px-4 py-1.5 rounded border border-[#33313B]/20 text-[12.5px] hover:bg-[#E4E2E9]">Fechar</button>
        </div>
      </div>
    </div>
  );
}
