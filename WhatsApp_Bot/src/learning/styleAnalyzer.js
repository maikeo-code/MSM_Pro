import { settings } from '../config/settings.js';
import { getClient } from '../ai/claude.js';
import {
  getResponsePairs,
  getAllResponsePairs,
  saveContactStyle,
  getContactStyle,
  saveVocabulary,
  getTopVocabulary,
} from './learningDb.js';

const HAIKU_MODEL = 'claude-haiku-4-5-20251001';

/**
 * Analyze all responses for a specific contact and build their style profile.
 * Uses AI to understand tone, common phrases, greeting patterns, etc.
 *
 * @param {string} contactName
 * @returns {Promise<object|null>} The style profile
 */
export async function analyzeContactStyle(contactName) {
  const pairs = getResponsePairs(contactName, 100);

  if (pairs.length < 3) {
    // Need at least 3 interactions to build a profile
    return null;
  }

  // Format conversation pairs for AI analysis
  const conversationSample = pairs.map(p =>
    `Recebido: "${p.incoming_msg}"\nMinha resposta: "${p.user_response}"\nTempo: ${p.response_time_seconds}s`
  ).join('\n---\n');

  try {
    const response = await getClient().messages.create({
      model: HAIKU_MODEL,
      max_tokens: 800,
      messages: [{
        role: 'user',
        content: `Analise as minhas respostas no WhatsApp para o contato "${contactName}" e extraia meu estilo de comunicacao.

Conversas:
${conversationSample}

Responda APENAS com JSON valido:
{
  "tone": "formal" ou "informal" ou "casual" ou "professional",
  "greeting_words": ["palavras que uso pra cumprimentar"],
  "farewell_words": ["palavras que uso pra despedir"],
  "common_phrases": ["frases que repito frequentemente"],
  "emoji_usage": "none" ou "low" ou "medium" ou "high",
  "avg_response_length": numero medio de caracteres,
  "response_pattern": "quick" ou "delayed" ou "selective",
  "category": "work" ou "personal" ou "financial"
}`,
      }],
    });

    const raw = response.content[0]?.text?.trim();
    if (!raw) return null;

    const style = JSON.parse(raw);

    // Save to database
    saveContactStyle({
      contactName,
      category: style.category || 'personal',
      tone: style.tone || 'informal',
      greetingWords: style.greeting_words || [],
      farewellWords: style.farewell_words || [],
      commonPhrases: style.common_phrases || [],
      emojiUsage: style.emoji_usage || 'low',
      avgResponseLength: style.avg_response_length || 50,
      responsePattern: style.response_pattern || 'quick',
      totalInteractions: pairs.length,
    });

    return style;
  } catch (error) {
    console.error('[styleAnalyzer] Error analyzing contact style:', error.message);
    return null;
  }
}

/**
 * Analyze all responses globally to extract the user's vocabulary.
 * Finds words and phrases the user uses most often.
 *
 * @returns {Promise<void>}
 */
export async function analyzeGlobalVocabulary() {
  const allPairs = getAllResponsePairs(200);

  if (allPairs.length < 5) return;

  // Extract just user responses
  const responses = allPairs.map(p => p.user_response).join('\n');

  try {
    const response = await getClient().messages.create({
      model: HAIKU_MODEL,
      max_tokens: 600,
      messages: [{
        role: 'user',
        content: `Analise estas respostas do WhatsApp e extraia o vocabulario mais usado.

Respostas:
${responses}

Responda APENAS com JSON valido:
{
  "greetings": ["cumprimentos mais usados"],
  "farewells": ["despedidas mais usadas"],
  "fillers": ["palavras de preenchimento tipo 'tipo', 'ne', 'entao'"],
  "expressions": ["expressoes caracteristicas como 'show', 'beleza', 'tranquilo'"]
}`,
      }],
    });

    const raw = response.content[0]?.text?.trim();
    if (!raw) return;

    const vocab = JSON.parse(raw);

    // Save each category
    for (const word of (vocab.greetings || [])) {
      saveVocabulary(word, 'greeting');
    }
    for (const word of (vocab.farewells || [])) {
      saveVocabulary(word, 'farewell');
    }
    for (const word of (vocab.fillers || [])) {
      saveVocabulary(word, 'filler');
    }
    for (const word of (vocab.expressions || [])) {
      saveVocabulary(word, 'expression');
    }
  } catch (error) {
    console.error('[styleAnalyzer] Error analyzing vocabulary:', error.message);
  }
}

/**
 * Run full analysis: all contacts + global vocabulary.
 * Should be called periodically (e.g., once a day or after N new responses).
 *
 * @returns {Promise<{contactsAnalyzed: number, vocabularyUpdated: boolean}>}
 */
export async function runFullAnalysis() {
  const allPairs = getAllResponsePairs(500);

  // Get unique contacts
  const contacts = [...new Set(allPairs.map(p => p.contact_name))];

  let contactsAnalyzed = 0;

  for (const contact of contacts) {
    const existing = getContactStyle(contact);
    const contactPairs = allPairs.filter(p => p.contact_name === contact);

    // Re-analyze if we have 5+ new interactions since last analysis
    const needsUpdate = !existing || contactPairs.length > (existing.total_interactions + 5);

    if (needsUpdate) {
      const result = await analyzeContactStyle(contact);
      if (result) contactsAnalyzed++;
    }
  }

  // Update global vocabulary
  await analyzeGlobalVocabulary();

  return { contactsAnalyzed, vocabularyUpdated: true };
}

/**
 * Build a style context string for the AI when generating responses.
 * This is injected into the prompt so responses match the user's style.
 *
 * @param {string} contactName
 * @returns {Promise<string>} Context string for AI prompt
 */
export async function getStyleContext(contactName) {
  const style = getContactStyle(contactName);
  const vocab = getTopVocabulary(30);

  let context = '';

  if (style) {
    const greetings = Array.isArray(style.greeting_words) ? style.greeting_words : [];
    const farewells = Array.isArray(style.farewell_words) ? style.farewell_words : [];
    const phrases = Array.isArray(style.common_phrases) ? style.common_phrases : [];

    context += `\nEstilo com ${contactName}:`;
    context += `\n- Tom: ${style.tone}`;
    context += `\n- Categoria: ${style.category}`;
    if (greetings.length) context += `\n- Cumprimentos: ${greetings.join(', ')}`;
    if (farewells.length) context += `\n- Despedidas: ${farewells.join(', ')}`;
    if (phrases.length) context += `\n- Frases comuns: ${phrases.join(', ')}`;
    context += `\n- Uso de emoji: ${style.emoji_usage}`;
    context += `\n- Tamanho medio: ${style.avg_response_length} caracteres`;
  }

  if (vocab.length > 0) {
    const words = vocab.map(v => v.word_or_phrase);
    context += `\n\nVocabulario frequente do usuario: ${words.join(', ')}`;
  }

  // Get recent response pairs for this contact as examples
  const recentPairs = getResponsePairs(contactName, 5);
  if (recentPairs.length > 0) {
    context += '\n\nExemplos de como o usuario respondeu antes:';
    for (const pair of recentPairs) {
      context += `\n  Recebido: "${pair.incoming_msg}"`;
      context += `\n  Resposta: "${pair.user_response}"`;
    }
  }

  return context;
}
