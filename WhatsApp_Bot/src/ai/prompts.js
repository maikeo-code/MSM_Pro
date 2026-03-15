// Prompt templates for Claude AI integration
// All prompts are in Brazilian Portuguese

export const SYSTEM_PROMPT = (myName) =>
  `Voce e o assistente pessoal de ${myName}. Responda de forma natural, educada e objetiva em portugues brasileiro. Adapte o tom: formal para fornecedores/trabalho, casual para amigos/familia. Nunca revele que e uma IA a menos que perguntado diretamente.`;

export const SUMMARY_PROMPT = (conversations) => {
  const lines = [];

  for (const [contact, messages] of Object.entries(conversations)) {
    if (!messages || messages.length === 0) continue;
    lines.push(`--- ${contact} ---`);
    for (const msg of messages) {
      const direction = msg.fromMe ? 'Eu' : contact;
      lines.push(`[${direction}]: ${msg.body}`);
    }
    lines.push('');
  }

  return `Voce e um assistente pessoal. Abaixo estao todas as conversas do dia no WhatsApp. Faca um resumo organizado e objetivo em portugues brasileiro.

Agrupe as conversas nas seguintes categorias:
- 💰 FINANCEIRO (bancos, cobranças, pagamentos, boletos, PIX, faturas)
- 🏢 TRABALHO/FORNECEDORES (clientes, fornecedores, negocios)
- 👤 PESSOAL (amigos, familia, conversas casuais)
- 👥 GRUPOS

Para cada conversa:
1. Resumo em 1-2 linhas do que se trata
2. Acoes pendentes (pagamentos, respostas necessarias, compromissos)
3. Urgencia: URGENTE / NORMAL / PODE ESPERAR
4. Se tem algo que precisa de resposta, sugira uma resposta curta

CONVERSAS DO DIA:
${lines.join('\n')}

Resumo:`;
};

export const CLASSIFY_PROMPT = (contactName, message) =>
  `Analise a seguinte mensagem do WhatsApp recebida de "${contactName}" e classifique-a.

Mensagem: "${message}"

Responda APENAS com um JSON valido no seguinte formato, sem nenhum texto adicional:
{
  "needsResponse": true ou false,
  "urgency": "high" ou "medium" ou "low",
  "category": "work" ou "personal" ou "spam" ou "notification"
}

Criterios:
- needsResponse: true se a mensagem e uma pergunta, pedido, convite ou requer qualquer acao; false para notificacoes, broadcasts, spam ou mensagens informativas sem necessidade de resposta
- urgency: high para situacoes urgentes ou importantes, medium para assuntos normais, low para conversas casuais ou irrelevantes
- category: work para trabalho/negocios/fornecedores, personal para amigos/familia, spam para propaganda/lixo, notification para avisos automaticos`;

export const SUGGEST_PROMPT = (contactName, context, message) => {
  const contextLines = context && context.length > 0
    ? context.map((m) => `[${m.fromMe ? 'Eu' : contactName}]: ${m.body}`).join('\n')
    : '(sem historico anterior)';

  return `Voce e um assistente pessoal ajudando a redigir respostas no WhatsApp.

Contato: ${contactName}
Historico recente:
${contextLines}

Nova mensagem recebida: "${message}"

Gere exatamente 3 opcoes de resposta em portugues brasileiro, variando o tamanho e o nivel de detalhe. Adapte o tom ao contexto (formal para trabalho, casual para amigos/familia).

Responda APENAS com um JSON valido no seguinte formato, sem nenhum texto adicional:
[
  { "label": "Curta", "text": "resposta curta e direta" },
  { "label": "Media", "text": "resposta com um pouco mais de detalhe" },
  { "label": "Detalhada", "text": "resposta completa e elaborada" }
]`;
};
