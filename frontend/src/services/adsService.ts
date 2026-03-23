import api from "./api";

// ─── Tipos alinhados com o backend ────────────────────────────────────────────

// AdCampaignOut do backend
export interface AdCampaignOut {
  id: string;
  ml_account_id: string;
  campaign_id: string;
  name: string;
  status: string;
  daily_budget: number;
  roas_target: number | null;
  created_at: string;
  updated_at: string;
}

// AdSnapshotOut do backend
export interface AdSnapshotOut {
  id: string;
  campaign_id: string;
  date: string;
  impressions: number;
  clicks: number;
  spend: number;
  attributed_sales: number;
  attributed_revenue: number;
  organic_sales: number;
  roas: number | null;
  acos: number | null;
  cpc: number | null;
  ctr: number | null;
  captured_at: string;
}

// AdsDashboardOut do backend
export interface AdsDashboardOut {
  total_spend: number;
  total_revenue: number;
  total_clicks: number;
  total_impressions: number;
  roas_geral: number | null;
  acos_geral: number | null;
  campaigns: AdCampaignOut[];
}

// AdsCampaignDetailOut do backend
export interface AdsCampaignDetailOut {
  campaign: AdCampaignOut;
  snapshots: AdSnapshotOut[];
  summary: Record<string, unknown>;
}

// ─── Tipos derivados usados pelo frontend ─────────────────────────────────────

// Diagnóstico calculado no frontend a partir do ROAS
export type Diagnostico = "excellent" | "good" | "needs_improvement";

export function calcDiagnostico(roas: number | null): Diagnostico {
  if (roas == null) return "needs_improvement";
  if (roas > 5) return "excellent";
  if (roas > 2) return "good";
  return "needs_improvement";
}

// Campanha enriquecida com campos calculados para exibição na tabela
export interface AdsCampanha {
  id: string;
  campaign_id: string;
  name: string;
  status: string;
  // Direto do backend
  orcamento_diario: number;     // daily_budget
  roas_objetivo: number;        // roas_target ?? 0
  // Calculados a partir dos snapshots (via summary ou null quando sem dados)
  vendas_ads: number;           // attributed_sales agregado
  roas: number;                 // roas_geral da campanha (via summary)
  acos: number;                 // acos_geral da campanha (via summary)
  investimento: number;         // spend agregado
  cliques: number;              // clicks agregado
  impressoes: number;           // impressions agregado
  receita_ads: number;          // attributed_revenue agregado
  diagnostico: Diagnostico;     // calculado via calcDiagnostico(roas)
  delta_roas: null;             // não disponível no backend atual
  delta_vendas: null;           // não disponível no backend atual
}

// Ponto de timeline para o gráfico
export interface AdsCampanhaTimelinePoint {
  date: string;
  vendas_ads: number;          // attributed_sales
  vendas_organicas: number;    // organic_sales
  cliques: number;             // clicks
  investimento: number;        // spend
  receita_ads: number;         // attributed_revenue
}

// Detalhe de campanha com timeline normalizada para o frontend
export interface AdsCampanhaDetalhe extends Omit<AdsCampanha, "delta_roas" | "delta_vendas"> {
  delta_roas: null;
  delta_vendas: null;
  timeline: AdsCampanhaTimelinePoint[];
  name: string;
}

// Resumo agregado de todas as campanhas
export interface AdsResumo {
  total_investimento: number;   // total_spend
  receita_ads: number;          // total_revenue
  roas_geral: number;           // roas_geral ?? 0
  acos_geral: number;           // acos_geral ?? 0
  total_cliques: number;        // total_clicks
  vendas_por_ads: number;       // soma de attributed_sales (não disponível no dashboard — usar 0)
}

// ─── Funções de mapeamento ─────────────────────────────────────────────────────

function mapDashboardToResumo(raw: AdsDashboardOut): AdsResumo {
  return {
    total_investimento: Number(raw.total_spend),
    receita_ads: Number(raw.total_revenue),
    roas_geral: raw.roas_geral != null ? Number(raw.roas_geral) : 0,
    acos_geral: raw.acos_geral != null ? Number(raw.acos_geral) : 0,
    total_cliques: raw.total_clicks,
    vendas_por_ads: 0, // não disponível no endpoint /ads/ — calculado apenas no detalhe
  };
}

function mapCampaignToAdsCampanha(c: AdCampaignOut): AdsCampanha {
  // Sem snapshots no dashboard — métricas ficam zeradas até o usuário abrir o detalhe
  return {
    id: c.id,
    campaign_id: c.campaign_id,
    name: c.name,
    status: c.status,
    orcamento_diario: Number(c.daily_budget),
    roas_objetivo: c.roas_target != null ? Number(c.roas_target) : 0,
    vendas_ads: 0,
    roas: 0,
    acos: 0,
    investimento: 0,
    cliques: 0,
    impressoes: 0,
    receita_ads: 0,
    diagnostico: calcDiagnostico(null),
    delta_roas: null,
    delta_vendas: null,
  };
}

function mapSnapshotToTimelinePoint(s: AdSnapshotOut): AdsCampanhaTimelinePoint {
  return {
    date: s.date,
    vendas_ads: s.attributed_sales,
    vendas_organicas: s.organic_sales,
    cliques: s.clicks,
    investimento: Number(s.spend),
    receita_ads: Number(s.attributed_revenue),
  };
}

function mapDetailToDetalhe(raw: AdsCampaignDetailOut): AdsCampanhaDetalhe {
  const summary = raw.summary as Record<string, number>;
  // Backend retorna roas_geral e acos_geral, não roas e acos
  const roas = summary.roas_geral != null ? Number(summary.roas_geral) : null;

  // Agrega métricas dos snapshots para exibir na linha da tabela quando o detalhe carrega
  const totalVendas = raw.snapshots.reduce((s, snap) => s + snap.attributed_sales, 0);
  const totalInvestimento = raw.snapshots.reduce((s, snap) => s + Number(snap.spend), 0);
  const totalReceita = raw.snapshots.reduce((s, snap) => s + Number(snap.attributed_revenue), 0);
  const totalCliques = raw.snapshots.reduce((s, snap) => s + snap.clicks, 0);
  const totalImpressoes = raw.snapshots.reduce((s, snap) => s + snap.impressions, 0);

  return {
    id: raw.campaign.id,
    campaign_id: raw.campaign.campaign_id,
    name: raw.campaign.name,
    status: raw.campaign.status,
    orcamento_diario: Number(raw.campaign.daily_budget),
    roas_objetivo: raw.campaign.roas_target != null ? Number(raw.campaign.roas_target) : 0,
    vendas_ads: totalVendas,
    roas: roas ?? 0,
    acos: summary.acos_geral != null ? Number(summary.acos_geral) : 0,
    investimento: totalInvestimento,
    cliques: totalCliques,
    impressoes: totalImpressoes,
    receita_ads: totalReceita,
    diagnostico: calcDiagnostico(roas),
    delta_roas: null,
    delta_vendas: null,
    timeline: raw.snapshots
      .slice()
      .sort((a, b) => a.date.localeCompare(b.date))
      .map(mapSnapshotToTimelinePoint),
  };
}

// ─── Service ──────────────────────────────────────────────────────────────────

const adsService = {
  // Backend: GET /ads/ → AdsDashboardOut
  // Retorna { resumo, campanhas } para o componente
  async list(mlAccountId?: string | null): Promise<{ resumo: AdsResumo; campanhas: AdsCampanha[] }> {
    const params: any = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.get<AdsDashboardOut>("/ads/", {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return {
      resumo: mapDashboardToResumo(data),
      campanhas: data.campaigns.map(mapCampaignToAdsCampanha),
    };
  },

  // Backend: GET /ads/{campaignId}?days=30 → AdsCampaignDetailOut
  // Retorna AdsCampanhaDetalhe com timeline normalizada
  async getCampanha(campaignId: string, period: string = "30d", mlAccountId?: string | null): Promise<AdsCampanhaDetalhe> {
    // Converter período em formato string (ex: "30d") para dias (int)
    const daysMap: Record<string, number> = {
      "7d": 7,
      "15d": 15,
      "30d": 30,
      "60d": 60,
      "90d": 90,
    };
    const days = daysMap[period] ?? 30;

    const params: any = { days };
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }

    const { data } = await api.get<AdsCampaignDetailOut>(`/ads/${campaignId}`, {
      params,
    });
    return mapDetailToDetalhe(data);
  },

  // Backend: POST /ads/sync → { results: [...], accounts_synced: number }
  async sync(mlAccountId?: string | null): Promise<{ message: string; synced: number }> {
    const params: any = {};
    if (mlAccountId) {
      params.ml_account_id = mlAccountId;
    }
    const { data } = await api.post<{ results: unknown[]; accounts_synced: number }>("/ads/sync", {}, {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return {
      message: `Sincronizacao concluida`,
      synced: data.accounts_synced ?? 0,
    };
  },
};

export default adsService;
