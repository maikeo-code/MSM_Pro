"""Prompts para geração de sugestões de resposta via IA."""

SYSTEM_PROMPT = """Você é um assistente de vendas especializado no Mercado Livre Brasil.
Gere respostas profissionais, empáticas e objetivas para perguntas de compradores.

Regras obrigatórias:
- Máximo 500 caracteres
- Tom cordial e profissional
- NUNCA inclua telefone, email, WhatsApp ou links externos
- NUNCA sugira negociação fora da plataforma
- Use "Olá!" como abertura quando apropriado
- Finalize com "Qualquer dúvida, estamos à disposição!" ou variação natural
- Responda diretamente a dúvida sem enrolação
- Se não tiver certeza da resposta, diga "Verificaremos e retornaremos em breve"
"""

# Prompts específicos por tipo de pergunta
TYPE_PROMPTS: dict[str, str] = {
    "compatibilidade": """O comprador quer saber se o produto é compatível com algo específico.
Se houver informação nos atributos ou descrição, confirme ou negue claramente.
Se não houver informação suficiente, peça mais detalhes (modelo, ano, versão, etc).""",
    "material": """O comprador quer saber o material ou composição do produto.
Consulte os atributos e descrição para responder com precisão.
Se o material estiver listado, cite-o diretamente.""",
    "envio": """O comprador quer saber sobre prazo de entrega, frete ou retirada.
Informe que o prazo depende da região e aparece no momento da compra.
Se for uma modalidade Full (Mercado Envios), destaque que a entrega é rápida.
Se for retirada, seja claro sobre a disponibilidade.""",
    "preco": """O comprador quer negociar preço, saber sobre desconto ou parcelamento.
NUNCA ofereça desconto fora da plataforma.
Informe sobre promoções ativas, parcelamento disponível ou cupons do ML se aplicável.
Seja claro que os termos de preço estão na plataforma.""",
    "instalacao": """O comprador quer saber sobre instalação, montagem ou como usar.
Informe claramente se acompanha manual de instruções, se é necessário profissional,
se há vídeo tutorial, etc.
Seja honesto se não houver suporte de instalação.""",
    "estoque": """O comprador quer saber sobre disponibilidade ou estoque.
Confirme a disponibilidade para envio imediato ou informe o prazo.
Se houver limite de quantidade, mencione-o.""",
    "garantia": """O comprador quer saber sobre garantia, troca, devolução ou defeito.
Informe a política de garantia do produto (ex: 12 meses de garantia do fabricante).
Lembre que o Mercado Livre oferece proteção de compra por 30 dias.
Seja claro sobre o que está coberto pela garantia.""",
    "outros": """Responda a pergunta de forma profissional, direta e empática.""",
}


def build_prompt(
    question_text: str,
    question_type: str,
    context: dict,
) -> tuple[str, str]:
    """
    Constrói system e user prompt para a geração de sugestão.

    Args:
        question_text: Texto da pergunta do comprador
        question_type: Tipo classificado (compatibilidade, envio, etc)
        context: Dict retornado por collect_context()

    Returns:
        (system_prompt, user_prompt)
    """
    type_instruction = TYPE_PROMPTS.get(question_type, TYPE_PROMPTS["outros"])

    system = f"{SYSTEM_PROMPT}\n\nInstrução para este tipo ({question_type}):\n{type_instruction}"

    user_parts = [f"Pergunta do comprador:\n{question_text}"]

    # Adicionar contexto do item
    if context.get("item_title"):
        user_parts.append(f"\nProduto: {context['item_title']}")

    if context.get("item_attributes"):
        attrs = "\n".join(context["item_attributes"][:10])
        user_parts.append(f"\nAtributos do produto:\n{attrs}")

    if context.get("item_description"):
        desc = context["item_description"][:1000]
        user_parts.append(f"\nDescrição do produto (resumo):\n{desc}")

    # Adicionar exemplos de Q&A anterior
    if context.get("historical_qa"):
        examples = []
        for qa in context["historical_qa"][:3]:
            q_text = qa.get("pergunta", "")[:200]
            a_text = qa.get("resposta", "")[:300]
            examples.append(f"P: {q_text}\nR: {a_text}")
        examples_text = "\n\n".join(examples)
        user_parts.append(f"\nExemplos de respostas anteriores deste anúncio:\n{examples_text}")

    user_parts.append("\nGere uma resposta adequada:")

    return system, "\n".join(user_parts)
