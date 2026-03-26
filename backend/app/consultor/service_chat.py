"""
Chatbot Consultor IA com Claude tool_use.
Consulta dados do sistema via tools read-only.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)

BRT = timezone(timedelta(hours=-3))

# ─── Definição das tools para o Claude ───────────────────────────────────────
TOOLS = [
    {
        "name": "buscar_kpis",
        "description": "Busca KPIs consolidados de vendas: pedidos, unidades vendidas, receita, conversão. Aceita período: hoje, ontem, 7d, 30d.",
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": ["today", "yesterday", "7d", "15d", "30d"],
                    "description": "Período para buscar KPIs"
                }
            },
            "required": ["periodo"]
        }
    },
    {
        "name": "listar_anuncios",
        "description": "Lista todos os anúncios ativos com preço, estoque, visitas e vendas do dia. Retorna dados do período especificado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": ["today", "yesterday", "7d", "30d"],
                    "description": "Período dos dados"
                },
                "limite": {
                    "type": "integer",
                    "description": "Máximo de anúncios a retornar (default 20)",
                    "default": 20
                }
            },
            "required": []
        }
    },
    {
        "name": "buscar_financeiro",
        "description": "Busca resumo financeiro: vendas brutas, taxas ML, frete, receita líquida, margem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": ["7d", "15d", "30d", "60d"],
                    "description": "Período do resumo financeiro"
                }
            },
            "required": ["periodo"]
        }
    },
    {
        "name": "buscar_anuncio_detalhe",
        "description": "Busca detalhes de um anúncio específico pelo MLB ID ou título parcial.",
        "input_schema": {
            "type": "object",
            "properties": {
                "busca": {
                    "type": "string",
                    "description": "MLB ID (ex: MLB1234567890) ou parte do título do anúncio"
                }
            },
            "required": ["busca"]
        }
    },
    {
        "name": "buscar_estoque_critico",
        "description": "Lista anúncios com estoque baixo ou dias para zerar crítico.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limite_estoque": {
                    "type": "integer",
                    "description": "Considerar crítico abaixo de N unidades (default 10)",
                    "default": 10
                }
            },
            "required": []
        }
    },
    {
        "name": "buscar_concorrentes",
        "description": "Lista concorrentes monitorados com preços e comparação.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "buscar_alertas_recentes",
        "description": "Lista alertas configurados e eventos recentes disparados.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limite": {
                    "type": "integer",
                    "description": "Máximo de alertas a retornar",
                    "default": 10
                }
            },
            "required": []
        }
    },
]

SYSTEM_PROMPT = """Você é o Consultor IA do MSM Pro, um assistente especialista em vendas no Mercado Livre.

Regras:
- Responda SEMPRE em português brasileiro
- Use as ferramentas disponíveis para consultar dados REAIS antes de responder
- NUNCA invente ou estime dados — se não encontrar, diga isso claramente
- Você NÃO pode alterar nenhum dado, apenas consultar
- Seja direto e prático nas respostas
- Use formatação com **negrito** para destacar números importantes
- Quando mostrar valores monetários, use R$ com 2 casas decimais
- Sugira ações práticas baseadas nos dados

Você tem acesso aos dados de:
- KPIs de vendas (pedidos, unidades, receita, conversão)
- Lista de anúncios (preço, estoque, visitas, vendas)
- Dados financeiros (receita líquida, taxas, margem)
- Detalhes por anúncio (histórico, performance)
- Estoque crítico (itens com risco de zerar)
- Concorrentes monitorados
- Alertas configurados
"""


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


async def _execute_tool(
    tool_name: str,
    tool_input: dict,
    db: AsyncSession,
    user_id: UUID,
) -> str:
    """Executa uma tool e retorna o resultado como string JSON."""
    try:
        if tool_name == "buscar_kpis":
            from app.vendas.service_kpi import get_kpi_by_period
            result = await get_kpi_by_period(db, user_id)
            periodo = tool_input.get("periodo", "today")
            # Mapear período para chave do resultado
            key_map = {"today": "hoje", "yesterday": "ontem", "7d": "7dias", "15d": "15dias", "30d": "30dias"}
            key = key_map.get(periodo, "hoje")
            data = result.get(key, {})
            return json.dumps({"periodo": periodo, "dados": data}, cls=DecimalEncoder, ensure_ascii=False)

        elif tool_name == "listar_anuncios":
            from app.vendas.service_kpi import list_listings
            periodo = tool_input.get("periodo", "today")
            limite = tool_input.get("limite", 20)
            listings = await list_listings(db, user_id, period=periodo, per_page=limite)
            # Simplificar output para economizar tokens
            simplified = []
            for l in listings[:limite]:
                snap = l.get("last_snapshot")
                snap_data = {}
                if snap:
                    if hasattr(snap, '__dict__'):
                        snap_data = {
                            "vendas": getattr(snap, "sales_today", 0),
                            "visitas": getattr(snap, "visits", 0),
                            "estoque": getattr(snap, "stock", 0),
                            "receita": float(getattr(snap, "revenue", 0) or 0),
                        }
                    elif isinstance(snap, dict):
                        snap_data = {
                            "vendas": snap.get("sales_today", 0),
                            "visitas": snap.get("visits", 0),
                            "estoque": snap.get("stock", 0),
                            "receita": float(snap.get("revenue", 0) or 0),
                        }
                simplified.append({
                    "titulo": l.get("title", ""),
                    "mlb_id": l.get("mlb_id", ""),
                    "preco": float(l.get("price", 0)),
                    "voce_recebe": l.get("voce_recebe"),
                    "dias_para_zerar": l.get("dias_para_zerar"),
                    **snap_data,
                })
            return json.dumps({"total": len(listings), "anuncios": simplified}, cls=DecimalEncoder, ensure_ascii=False)

        elif tool_name == "buscar_financeiro":
            from app.financeiro.service import get_financeiro_resumo
            periodo = tool_input.get("periodo", "30d")
            result = await get_financeiro_resumo(db, user_id, periodo)
            return json.dumps(result, cls=DecimalEncoder, ensure_ascii=False)

        elif tool_name == "buscar_anuncio_detalhe":
            from app.vendas.service_kpi import list_listings
            busca = tool_input.get("busca", "").strip()
            listings = await list_listings(db, user_id, period="today")
            # Filtrar por MLB ID ou título
            matches = [
                l for l in listings
                if busca.upper() in (l.get("mlb_id", "") or "").upper()
                or busca.lower() in (l.get("title", "") or "").lower()
            ]
            if not matches:
                return json.dumps({"erro": f"Nenhum anúncio encontrado para '{busca}'"}, ensure_ascii=False)
            # Retornar detalhes do primeiro match
            l = matches[0]
            snap = l.get("last_snapshot")
            snap_data = {}
            if snap:
                if hasattr(snap, '__dict__'):
                    for field in ["sales_today", "visits", "stock", "revenue", "conversion_rate", "orders_count"]:
                        snap_data[field] = getattr(snap, field, None)
                elif isinstance(snap, dict):
                    snap_data = {k: snap.get(k) for k in ["sales_today", "visits", "stock", "revenue", "conversion_rate", "orders_count"]}
            return json.dumps({
                "titulo": l.get("title"),
                "mlb_id": l.get("mlb_id"),
                "preco": float(l.get("price", 0)),
                "preco_original": float(l.get("original_price", 0)) if l.get("original_price") else None,
                "sku": l.get("seller_sku"),
                "voce_recebe": l.get("voce_recebe"),
                "dias_para_zerar": l.get("dias_para_zerar"),
                "quality_score": l.get("quality_score"),
                "permalink": l.get("permalink"),
                **snap_data,
            }, cls=DecimalEncoder, ensure_ascii=False)

        elif tool_name == "buscar_estoque_critico":
            from app.vendas.service_kpi import list_listings
            limite = tool_input.get("limite_estoque", 10)
            listings = await list_listings(db, user_id, period="today")
            criticos = []
            for l in listings:
                snap = l.get("last_snapshot")
                estoque = None
                if snap:
                    estoque = getattr(snap, "stock", None) if hasattr(snap, '__dict__') else snap.get("stock")
                dias = l.get("dias_para_zerar")
                if (estoque is not None and estoque < limite) or (dias is not None and dias < 7):
                    criticos.append({
                        "titulo": l.get("title"),
                        "mlb_id": l.get("mlb_id"),
                        "estoque": estoque,
                        "dias_para_zerar": dias,
                        "preco": float(l.get("price", 0)),
                    })
            criticos.sort(key=lambda x: x.get("estoque") or 999)
            return json.dumps({"total_criticos": len(criticos), "anuncios": criticos[:20]}, cls=DecimalEncoder, ensure_ascii=False)

        elif tool_name == "buscar_concorrentes":
            from app.concorrencia.service import get_all_competitors
            result = await get_all_competitors(db, user_id)
            simplified = []
            for c in result[:15]:
                # ORM objects: acessar atributos diretamente
                simplified.append({
                    "titulo": getattr(c, "title", ""),
                    "mlb_id": getattr(c, "mlb_id", ""),
                    "preco_atual": float(getattr(c, "current_price", 0) or 0),
                })
            return json.dumps({"total": len(result), "concorrentes": simplified}, cls=DecimalEncoder, ensure_ascii=False)

        elif tool_name == "buscar_alertas_recentes":
            from app.alertas.service import list_alert_events
            limite = tool_input.get("limite", 10)
            events = await list_alert_events(db, user_id, days=limite)
            # ORM objects: converter para dicts
            simplified_events = []
            for e in events[:limite]:
                simplified_events.append({
                    "message": getattr(e, "message", ""),
                    "alert_type": getattr(e, "alert_type", ""),
                    "triggered_at": str(getattr(e, "triggered_at", "")),
                    "mlb_id": getattr(e, "mlb_id", ""),
                })
            return json.dumps({"total": len(events), "alertas": simplified_events}, cls=DecimalEncoder, ensure_ascii=False)

        else:
            return json.dumps({"erro": f"Tool '{tool_name}' não reconhecida"}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Erro ao executar tool {tool_name}: {e}")
        return json.dumps({"erro": f"Erro ao buscar dados: {str(e)}"}, ensure_ascii=False)


async def chat_with_tools(
    db: AsyncSession,
    user_id: UUID,
    message: str,
    history: list[dict],
) -> tuple[str, int]:
    """
    Processa uma mensagem do usuário com loop de tool_use.
    Retorna (resposta, tokens_usados).
    """
    api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
    if not api_key:
        import os
        api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return "Chave da API Anthropic não configurada. Configure ANTHROPIC_API_KEY nas variáveis de ambiente.", 0

    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Montar mensagens: histórico + mensagem atual
    messages = []
    for msg in history[-18:]:  # Últimas 18 mensagens do histórico (para caber no contexto)
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

    total_tokens = 0
    max_iterations = 5

    for _ in range(max_iterations):
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        total_tokens += response.usage.input_tokens + response.usage.output_tokens

        # Verificar se precisa executar tools
        if response.stop_reason == "tool_use":
            # Adicionar resposta do assistente às mensagens
            messages.append({"role": "assistant", "content": response.content})

            # Executar cada tool chamada
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await _execute_tool(block.name, block.input, db, user_id)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            # Extrair texto da resposta final
            reply_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    reply_text += block.text
            return reply_text or "Não consegui gerar uma resposta.", total_tokens

    return "Desculpe, não consegui processar sua pergunta. Tente reformular.", total_tokens
