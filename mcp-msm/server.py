"""
MCP Server — MSM_Pro
Expõe ferramentas de acesso direto ao banco PostgreSQL para uso durante desenvolvimento.
Permite ao Claude consultar dados reais sem precisar rodar o servidor FastAPI.
"""

import asyncio
import json
import os
from typing import Any

try:
    import asyncpg
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    raise ImportError(
        "Instale as dependências: pip install mcp asyncpg"
    )

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://msm:msm@localhost:5432/msm_pro"
)

app = Server("msm-pro")


async def get_conn():
    return await asyncpg.connect(DATABASE_URL)


# ── Ferramentas disponíveis ───────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="query_snapshots",
            description="Busca histórico de snapshots de um anúncio MLB (preço, visitas, vendas, conversão)",
            inputSchema={
                "type": "object",
                "properties": {
                    "mlb_id": {"type": "string", "description": "ID do anúncio ML (ex: MLB-3456789012)"},
                    "dias":   {"type": "integer", "description": "Quantos dias de histórico (padrão: 30)", "default": 30}
                },
                "required": ["mlb_id"]
            }
        ),
        Tool(
            name="list_products",
            description="Lista todos os SKUs cadastrados com seus custos e anúncios vinculados",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="list_accounts",
            description="Lista as contas ML cadastradas e seu status de autenticação",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="check_competitors",
            description="Lista concorrentes vinculados a um anúncio MLB com últimos preços",
            inputSchema={
                "type": "object",
                "properties": {
                    "mlb_id": {"type": "string", "description": "ID do seu anúncio MLB"}
                },
                "required": ["mlb_id"]
            }
        ),
        Tool(
            name="get_alert_configs",
            description="Lista alertas configurados por anúncio ou SKU",
            inputSchema={
                "type": "object",
                "properties": {
                    "mlb_id": {"type": "string", "description": "Filtrar por MLB (opcional)"},
                    "sku":    {"type": "string", "description": "Filtrar por SKU (opcional)"}
                }
            }
        ),
        Tool(
            name="db_summary",
            description="Retorna resumo geral do banco: total de contas, anúncios, snapshots, alertas",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


# ── Handlers ─────────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        conn = await get_conn()
        result = await _dispatch(conn, name, arguments)
        await conn.close()
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=f"Erro: {str(e)}")]


async def _dispatch(conn, name: str, args: dict) -> Any:

    if name == "query_snapshots":
        mlb_id = args["mlb_id"]
        dias   = args.get("dias", 30)
        rows = await conn.fetch("""
            SELECT
                ls.data,
                ls.preco,
                ls.visitas,
                ls.vendas,
                ls.perguntas,
                ls.estoque,
                ROUND((ls.vendas::numeric / NULLIF(ls.visitas, 0)) * 100, 2) AS conversao_pct
            FROM listing_snapshots ls
            JOIN listings l ON l.id = ls.listing_id
            WHERE l.mlb_id = $1
              AND ls.data >= CURRENT_DATE - $2::int
            ORDER BY ls.data DESC
        """, mlb_id, dias)
        return [dict(r) for r in rows]

    elif name == "list_products":
        rows = await conn.fetch("""
            SELECT
                p.sku, p.nome, p.custo, p.unidade,
                COUNT(l.id) AS total_anuncios,
                ARRAY_AGG(l.mlb_id) AS anuncios
            FROM products p
            LEFT JOIN listings l ON l.product_id = p.id
            GROUP BY p.id, p.sku, p.nome, p.custo, p.unidade
            ORDER BY p.sku
        """)
        return [dict(r) for r in rows]

    elif name == "list_accounts":
        rows = await conn.fetch("""
            SELECT
                id, nickname, email, ativo,
                token_expires_at,
                (token_expires_at > NOW()) AS token_valido
            FROM ml_accounts
            ORDER BY nickname
        """)
        return [dict(r) for r in rows]

    elif name == "check_competitors":
        mlb_id = args["mlb_id"]
        rows = await conn.fetch("""
            SELECT
                c.mlb_id_concorrente,
                cs.preco AS ultimo_preco,
                cs.visitas AS ultimas_visitas,
                cs.vendas_delta AS vendas_estimadas_dia,
                cs.data AS data_snapshot
            FROM competitors c
            JOIN listings l ON l.id = c.listing_id
            LEFT JOIN competitor_snapshots cs ON cs.competitor_id = c.id
                AND cs.data = (SELECT MAX(data) FROM competitor_snapshots WHERE competitor_id = c.id)
            WHERE l.mlb_id = $1
            ORDER BY cs.preco ASC
        """, mlb_id)
        return [dict(r) for r in rows]

    elif name == "get_alert_configs":
        mlb_id = args.get("mlb_id")
        sku    = args.get("sku")
        query  = """
            SELECT
                a.id, a.tipo, a.threshold, a.canal,
                a.ativo, a.ultimo_disparo,
                l.mlb_id, p.sku
            FROM alert_configs a
            LEFT JOIN listings l ON l.id = a.listing_id
            LEFT JOIN products p ON p.id = a.product_id
            WHERE 1=1
        """
        params = []
        if mlb_id:
            params.append(mlb_id)
            query += f" AND l.mlb_id = ${len(params)}"
        if sku:
            params.append(sku)
            query += f" AND p.sku = ${len(params)}"
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]

    elif name == "db_summary":
        row = await conn.fetchrow("""
            SELECT
                (SELECT COUNT(*) FROM ml_accounts WHERE ativo = true)   AS contas_ativas,
                (SELECT COUNT(*) FROM products)                          AS total_skus,
                (SELECT COUNT(*) FROM listings WHERE status = 'active') AS anuncios_ativos,
                (SELECT COUNT(*) FROM listing_snapshots WHERE data = CURRENT_DATE) AS snapshots_hoje,
                (SELECT COUNT(*) FROM competitors)                       AS concorrentes_monitorados,
                (SELECT COUNT(*) FROM alert_configs WHERE ativo = true) AS alertas_ativos,
                (SELECT MAX(data) FROM listing_snapshots)               AS ultimo_snapshot
        """)
        return dict(row)

    else:
        return {"error": f"Ferramenta desconhecida: {name}"}


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
