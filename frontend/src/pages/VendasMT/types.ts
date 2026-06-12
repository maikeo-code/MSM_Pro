// Modelo de dados da aba Vendas (MT) — espelha a decomposição financeira do Mercado Turbo.
export interface Venda {
  venda: string;
  mlb: string | null;
  sku: string | null;
  titulo: string;
  data: string | null;
  status: string | null;
  margem: number | null;
  total: number;          // valor dos produtos (base de imposto e margem)
  pago: number;           // o que o comprador pagou (paid_amount) — "Pago comprador"
  produtos: number;       // compat (== total)
  tarifaML: number | null;
  frete: number | null;           // custo vendedor + frete pago pelo comprador
  lucroBruto: number | null;      // pago - frete - tarifa
  custoProduto: number | null;
  imposto: number | null;
  receitaLiquida: number | null;  // compat (== lucroBruto)
  lucro: number | null;
  temCusto: boolean;
  impostoPct?: number | null;
  entrega?: Entrega | null;
}

export interface Entrega {
  envioId: string;
  tipo: string;
  status: string;
  transportadora: string;
  rastreamento: string;
  manuseio: string;
  entregaPrevista: string;
  dimensoes: { altura: number; largura: number; comprimento: number };
  pesoG: number;
  valorDeclarado: number;
  comprador: string;
  cpf: string;
  enderecoDestinatario: string;
  cep: string;
}
