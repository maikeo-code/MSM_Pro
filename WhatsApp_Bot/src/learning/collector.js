import dayjs from 'dayjs';
import chalk from 'chalk';
import { saveResponsePair, updateMetrics, getResponsePairCount, saveSuggestionFeedback } from './learningDb.js';

/**
 * Track when we last saw a message from each contact,
 * so we can pair incoming messages with user responses.
 *
 * Map<contactId, { contactName, message, timestamp, category, isGroup }>
 */
const pendingMessages = new Map();

/**
 * Counter of new pairs since last auto-analysis.
 * When it reaches AUTO_ANALYZE_THRESHOLD, we trigger a background analysis.
 */
let newPairsSinceLastAnalysis = 0;
const AUTO_ANALYZE_THRESHOLD = 20;
let isAnalyzing = false;
let onAnalysisTrigger = null;

/**
 * Register a callback that will be invoked when enough new pairs
 * have been collected to warrant a style re-analysis.
 *
 * @param {() => Promise<void>} fn
 */
export function onAutoAnalysis(fn) {
  onAnalysisTrigger = fn;
}

/**
 * Register an incoming message as "waiting for response".
 * Call this whenever a new inbound message arrives.
 *
 * @param {string}  contactId
 * @param {string}  contactName
 * @param {string}  message
 * @param {string}  [category]  - work, personal, financial, group
 * @param {boolean} [isGroup]
 */
export function registerIncoming(contactId, contactName, message, category, isGroup) {
  pendingMessages.set(contactId, {
    contactName,
    message,
    timestamp: Date.now(),
    category: category || 'personal',
    isGroup: isGroup || false,
  });
}

/**
 * Called when the user sends a message (msg.fromMe === true).
 * Looks for a pending incoming message from this contact and, if found,
 * saves the (incoming, outgoing) pair for learning then removes it from
 * the pending map.
 *
 * @param {string} contactId
 * @param {string} contactName
 * @param {string} userResponse
 * @returns {{ contactName, contactId, category, incomingMsg, userResponse,
 *             responseTimeSeconds, isGroup } | null}
 *   The saved pair, or null when there was no pending message to pair with.
 */
export function registerOutgoing(contactId, contactName, userResponse) {
  const pending = pendingMessages.get(contactId);

  if (!pending) return null;

  const responseTimeSeconds = Math.floor((Date.now() - pending.timestamp) / 1000);

  const pair = {
    contactName: pending.contactName || contactName,
    contactId,
    category: pending.category,
    incomingMsg: pending.message,
    userResponse,
    responseTimeSeconds,
    isGroup: pending.isGroup,
  };

  saveResponsePair(pair);

  // Track daily activity — every saved pair counts as one shown suggestion
  const today = dayjs().format('YYYY-MM-DD');
  updateMetrics(today, 'suggestions_shown');

  pendingMessages.delete(contactId);

  // Log learning event in real-time
  const totalPairs = getResponsePairCount();
  console.log(
    chalk.gray(dayjs().format('HH:mm:ss')) + ' ' +
    chalk.magenta('[Aprendizado]') + ' ' +
    chalk.white(`Par salvo: ${pair.contactName}`) +
    chalk.gray(` (${pair.responseTimeSeconds}s) `) +
    chalk.cyan(`Total: ${totalPairs} pares`)
  );

  // Check if we should trigger auto-analysis
  newPairsSinceLastAnalysis++;
  if (newPairsSinceLastAnalysis >= AUTO_ANALYZE_THRESHOLD && !isAnalyzing && onAnalysisTrigger) {
    isAnalyzing = true;
    newPairsSinceLastAnalysis = 0;
    console.log(
      chalk.magenta('[Aprendizado]') + ' ' +
      chalk.yellow(`${AUTO_ANALYZE_THRESHOLD} novas respostas coletadas — iniciando analise automatica...`)
    );
    onAnalysisTrigger()
      .then(() => {
        console.log(
          chalk.magenta('[Aprendizado]') + ' ' +
          chalk.green('Analise automatica concluida!')
        );
      })
      .catch((err) => {
        console.error(chalk.magenta('[Aprendizado]') + ' Erro na analise:', err.message);
      })
      .finally(() => {
        isAnalyzing = false;
      });
  }

  return pair;
}

/**
 * Track suggestions that were shown to the user, so we can compare
 * with what they actually sent.
 *
 * Map<contactId, { contactName, incomingMsg, suggestions: string[], timestamp }>
 */
const pendingSuggestions = new Map();

/**
 * Register suggestions that were shown to the user for a contact.
 * Call this after suggestResponse() returns results.
 *
 * @param {string} contactId
 * @param {string} contactName
 * @param {string} incomingMsg
 * @param {Array<{label: string, text: string}>} suggestions
 */
export function registerSuggestions(contactId, contactName, incomingMsg, suggestions) {
  pendingSuggestions.set(contactId, {
    contactName,
    incomingMsg,
    suggestions: suggestions.map(s => s.text),
    timestamp: Date.now(),
  });
}

/**
 * Compare the user's actual response with pending suggestions.
 * Returns feedback data and logs it.
 *
 * @param {string} contactId
 * @param {string} userResponse
 * @returns {string|null} outcome: 'used' | 'modified' | 'own_response' | null
 */
export function evaluateSuggestionFeedback(contactId, userResponse) {
  const pending = pendingSuggestions.get(contactId);
  if (!pending) return null;

  const { contactName, incomingMsg, suggestions } = pending;
  pendingSuggestions.delete(contactId);

  // Compare user response with each suggestion
  const normalizedResponse = userResponse.toLowerCase().trim();
  let bestSimilarity = 0;
  let outcome = 'own_response';

  for (const suggested of suggestions) {
    const normalizedSuggestion = suggested.toLowerCase().trim();

    // Exact match
    if (normalizedResponse === normalizedSuggestion) {
      bestSimilarity = 1.0;
      outcome = 'used';
      break;
    }

    // Similarity check (simple word overlap)
    const responseWords = new Set(normalizedResponse.split(/\s+/));
    const suggestionWords = new Set(normalizedSuggestion.split(/\s+/));
    const intersection = [...responseWords].filter(w => suggestionWords.has(w));
    const union = new Set([...responseWords, ...suggestionWords]);
    const similarity = union.size > 0 ? intersection.length / union.size : 0;

    if (similarity > bestSimilarity) {
      bestSimilarity = similarity;
    }
  }

  // Determine outcome based on similarity
  if (outcome !== 'used') {
    if (bestSimilarity >= 0.6) {
      outcome = 'modified';
    } else {
      outcome = 'own_response';
    }
  }

  // Save to database
  saveSuggestionFeedback({
    contactName,
    contactId,
    incomingMsg,
    suggestedTexts: suggestions,
    userResponse,
    outcome,
    similarityScore: bestSimilarity,
  });

  // Update daily metrics
  const today = dayjs().format('YYYY-MM-DD');
  if (outcome === 'used') {
    updateMetrics(today, 'suggestions_used');
    console.log(
      chalk.magenta('[Aprendizado]') + ' ' +
      chalk.green(`Sugestao USADA para ${contactName}! (similaridade: ${Math.round(bestSimilarity * 100)}%)`)
    );
  } else if (outcome === 'modified') {
    updateMetrics(today, 'suggestions_modified');
    console.log(
      chalk.magenta('[Aprendizado]') + ' ' +
      chalk.yellow(`Sugestao MODIFICADA para ${contactName} (similaridade: ${Math.round(bestSimilarity * 100)}%)`)
    );
  } else {
    updateMetrics(today, 'suggestions_ignored');
    console.log(
      chalk.magenta('[Aprendizado]') + ' ' +
      chalk.gray(`Resposta PROPRIA para ${contactName} (sem usar sugestao)`)
    );
  }

  return outcome;
}

/**
 * Return a snapshot of the current collection state.
 *
 * @returns {{ pendingResponses: number, pendingSuggestions: number }}
 */
export function getCollectionStats() {
  return {
    pendingResponses: pendingMessages.size,
    pendingSuggestions: pendingSuggestions.size,
  };
}
