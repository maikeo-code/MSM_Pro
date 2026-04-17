"""
EKAS - Carga Inicial de Dados de Inteligencia Competitiva
Carrega dados reais sobre concorrentes, features, oportunidades.
Nao depende de API (dados estruturados manuais).
Fontes RAW ficam salvas para processar quando API tiver creditos.
"""
import os
import json
from pathlib import Path

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().strip().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from ekas_engine import EkasDB

db = EkasDB()

# === PROJETO ===
db.add_project("msm_pro", "MSM Pro", "Dashboard de vendas Mercado Livre",
               keywords=["mercado livre", "ecommerce", "vendas", "ERP"])

# === CONCORRENTES ===
db.add_competitor("Bling ERP", "msm_pro", "ERP", "bling.com.br",
    "R$30-200/mes", "PMEs e-commerce",
    strengths=["Melhor integracao com ML", "NF-e automatica confiavel",
               "Bom custo-beneficio", "Multi-deposito"],
    weaknesses=["Suporte lento 24-48h", "Interface datada",
                "Relatorios limitados", "Sem IA", "Devolucoes basico"])

db.add_competitor("Tiny ERP", "msm_pro", "ERP", "tiny.com.br",
    "R$20-120/mes", "Iniciantes e-commerce",
    strengths=["Mais barato", "Interface moderna", "Setup rapido",
               "App mobile", "Bom para iniciantes"],
    weaknesses=["Sem multi-deposito", "NF-e manual no basico",
                "Lento em picos", "Sem analytics", "Sem IA"])

db.add_competitor("Omie", "msm_pro", "ERP", "omie.com.br",
    "R$100-200+/mes", "Medias empresas",
    strengths=["Mais completo", "Analytics superior", "Suporte rapido",
               "API REST completa", "Multi-empresa", "Contabilidade integrada"],
    weaknesses=["Preco alto", "Curva aprendizado", "Complexo para MEIs",
                "Sem IA", "Marketplace basico"])

# === FEATURES DO MERCADO ===
features_data = [
    ("Emissao automatica de NF-e", "fiscal", "Gerar NF-e ao confirmar venda", "high", 0.95),
    ("Gestao estoque multi-deposito", "estoque", "Controle em multiplos depositos", "high", 0.85),
    ("Integracao com Mercado Livre", "integracoes", "Sincronizacao bidirecional ML", "medium", 0.90),
    ("Integracao com transportadoras", "logistica", "Calculo frete e etiquetas", "high", 0.80),
    ("Dashboard analytics avancado", "analytics", "Graficos vendas, margem, comparativos", "medium", 0.90),
    ("Gestao financeira completa", "financeiro", "DRE, fluxo caixa, conciliacao", "high", 0.75),
    ("CRM integrado", "atendimento", "Pipeline de vendas e gestao clientes", "medium", 0.60),
    ("Cadastro produtos com variacao", "estoque", "Cor, tamanho, modelo", "low", 0.70),
    ("App mobile", "outro", "Gestao pelo celular", "medium", 0.65),
    ("API REST para desenvolvedores", "integracoes", "API aberta para customizacoes", "medium", 0.55),
    ("Contabilidade integrada", "financeiro", "Dispensa contador para basico", "high", 0.50),
    ("IA para precificacao", "IA", "Ajuste automatico precos baseado em dados", "very_high", 0.95),
    ("Integracao PIX automatica", "financeiro", "Conciliacao PIX em tempo real", "medium", 0.85),
    ("Gestao devolucoes inteligente", "vendas", "Analise motivos e logistica reversa", "high", 0.80),
    ("Multi-canal unificado", "integracoes", "ML + Shopee + Amazon em 1 dashboard", "high", 0.88),
    ("Previsao de demanda com ML", "IA", "Machine learning para prever vendas", "very_high", 0.70),
]

feature_ids = {}
for name, cat, desc, complexity, importance in features_data:
    fid = db.add_feature(name, "msm_pro", cat, desc, complexity, importance)
    feature_ids[name] = fid

# === QUEM TEM O QUE ===
implementations = [
    ("Emissao automatica de NF-e", "Bling ERP", "Emite automaticamente ao confirmar venda no ML"),
    ("Emissao automatica de NF-e", "Omie", "Emissao automatica de NF-e, NFS-e, NFC-e"),
    ("Gestao estoque multi-deposito", "Bling ERP", "Multi-deposito com alertas de minimo"),
    ("Gestao estoque multi-deposito", "Omie", "Multi-deposito com lote, validade, FIFO/LIFO"),
    ("Integracao com Mercado Livre", "Bling ERP", "Sincronizacao bidirecional completa"),
    ("Integracao com Mercado Livre", "Tiny ERP", "Integracao basica com ML"),
    ("Integracao com Mercado Livre", "Omie", "Integracao com ML e outros marketplaces"),
    ("Integracao com transportadoras", "Bling ERP", "Correios, Jadlog, Loggi"),
    ("Integracao com transportadoras", "Omie", "Correios, Jadlog, Sequoia, Total Express"),
    ("Dashboard analytics avancado", "Omie", "Graficos avancados vendas, margem, comparativos"),
    ("Gestao financeira completa", "Bling ERP", "Contas pagar/receber, fluxo caixa, DRE"),
    ("Gestao financeira completa", "Omie", "DRE, balanco, conciliacao bancaria"),
    ("CRM integrado", "Omie", "Pipeline de vendas e gestao clientes"),
    ("Cadastro produtos com variacao", "Tiny ERP", "Suporte a cor, tamanho"),
    ("App mobile", "Tiny ERP", "App funcional para gestao mobile"),
    ("API REST para desenvolvedores", "Omie", "API REST completa e documentada"),
    ("Contabilidade integrada", "Omie", "Contabilidade integrada dispensa contador"),
]

for feat_name, comp_name, how in implementations:
    fid = feature_ids.get(feat_name)
    comp = db.get_competitor(name=comp_name, project_id="msm_pro")
    if fid and comp:
        db.add_implementation(fid, comp["id"], how)

# === OPORTUNIDADES ===
opportunities = [
    ("gap", "IA para precificacao automatica",
     "Nenhum ERP brasileiro oferece precificacao baseada em IA", 0.95, 0.65),
    ("trend", "Integracao PIX automatica",
     "PIX = 40%+ transacoes, conciliacao tempo real e demanda crescente", 0.85, 0.30),
    ("gap", "Analytics preditivo com ML",
     "Nenhum ERP oferece previsao de demanda ou analytics preditivo", 0.80, 0.70),
    ("complaint", "Suporte lento nos ERPs tradicionais",
     "Usuarios reclamam de 24-48h para resposta", 0.60, 0.20),
    ("differentiator", "Dashboard realtime no celular",
     "Vendedores querem metricas instantaneas no celular", 0.75, 0.40),
    ("gap", "Gestao devolucoes com analise de motivos",
     "Nenhum ERP faz analise inteligente de motivos de devolucao", 0.80, 0.50),
    ("unserved_need", "Calculadora de margem por produto",
     "Vendedores nao sabem margem real com taxas ML", 0.85, 0.25),
    ("trend", "Multi-canal unificado ML+Shopee+Amazon",
     "Vendedores vendem em 3-4 canais, precisam visao unificada", 0.88, 0.55),
]

for type_, title, desc, impact, effort in opportunities:
    db.add_opportunity(type_, title, "msm_pro", desc,
                       impact_score=impact, effort_score=effort)

# === WATCHLIST ===
watches = [
    ("keyword", "ERP mercado livre 2026", 72),
    ("keyword", "bling erp novidades", 168),
    ("keyword", "tiny erp atualizacao", 168),
    ("keyword", "omie erp ecommerce", 168),
    ("keyword", "precificacao inteligente ecommerce", 168),
    ("competitor", "Bling ERP", 168),
    ("competitor", "Tiny ERP", 168),
    ("competitor", "Omie", 168),
]
for wtype, target, interval in watches:
    db.add_watch(wtype, target, "msm_pro", check_interval_hours=interval)

# === RESULTADOS ===
stats = db.get_stats()
print("=== EKAS - CARGA INICIAL COMPLETA ===")
for k, v in stats.items():
    if v > 0:
        print(f"  {k}: {v}")

print("\n=== ROADMAP SUGERIDO ===")
for i, s in enumerate(db.suggest_roadmap("msm_pro", 8), 1):
    print(f"  {i}. [{s['score']:.2f}] {s['feature']} ({s.get('category')}) "
          f"- {s.get('competitors_with_it', 0)} concorrentes")

print("\n=== COMPARATIVO BLING vs TINY vs OMIE ===")
comp = db.compare_competitors(["Bling ERP", "Tiny ERP", "Omie"], "msm_pro")
print(f"Features no mercado: {comp['total_features']}")
header = f"  {'Feature':<35} {'Bling':>5} {'Tiny':>5} {'Omie':>5}"
print(header)
print("  " + "-" * 55)
for feat, mapping in sorted(comp["feature_matrix"].items()):
    row = f"  {feat[:35]:<35}"
    for name in ["Bling ERP", "Tiny ERP", "Omie"]:
        has = mapping.get(name, False)
        row += f" {'SIM':>5}" if has else f" {'---':>5}"
    print(row)

print("\n=== TOP OPORTUNIDADES ===")
opps = db.get_opportunities("msm_pro")
for o in sorted(opps, key=lambda x: -x.get("priority_score", 0))[:8]:
    ps = o.get("priority_score", 0)
    print(f"  [{o['type']:<15}] Prio={ps:.3f} | {o['title']}")

print("\nDados carregados. Fontes RAW aguardam processamento com API quando houver creditos.")
print("Para processar: python cycle_bridge.py process --project msm_pro")
