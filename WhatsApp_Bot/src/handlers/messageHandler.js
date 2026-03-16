import chalk from 'chalk';
import { settings } from '../config/settings.js';
import { generateResponse, classifyMessage, suggestResponse } from '../ai/claude.js';
import { saveMessage, getMessagesByContact } from './database.js';
import { registerIncoming, registerOutgoing, registerSuggestions, evaluateSuggestionFeedback } from '../learning/collector.js';
import { getStyleContext } from '../learning/styleAnalyzer.js';
import { addSuggestion } from './suggestionQueue.js';

// Auto-mode rate limiter: max 5 auto-replies per contact per minute
const autoReplyTimestamps = new Map();
const AUTO_REPLY_MAX = 5;
const AUTO_REPLY_WINDOW_MS = 60_000;

function canAutoReply(contactId) {
  const now = Date.now();
  const timestamps = autoReplyTimestamps.get(contactId) || [];
  const recent = timestamps.filter(t => now - t < AUTO_REPLY_WINDOW_MS);
  if (recent.length >= AUTO_REPLY_MAX) return false;
  recent.push(now);
  autoReplyTimestamps.set(contactId, recent);
  return true;
}

/**
 * Handle a single incoming WhatsApp message.
 *
 * @param {import('whatsapp-web.js').Message} msg
 * @param {{ mode: string, whatsappClient: any }} options
 * @returns {Promise<{ handled: boolean, mode: string, contact: string }>}
 */
export async function handleIncomingMessage(msg, { mode, whatsappClient } = {}) {
  // ------------------------------------------------------------------
  // 1. Extract message metadata
  // ------------------------------------------------------------------
  const from = msg.from;
  const body = msg.body?.trim() ?? '';
  const isGroup = msg.isGroupMsg ?? false;

  // Resolve a human-readable contact name
  let contactName = msg.notifyName ?? from;
  try {
    const contact = await msg.getContact();
    contactName = contact.pushname || contact.name || contact.number || from;
  } catch {
    // getContact() can fail for some message types — keep the fallback value
  }

  // Group name (only meaningful when isGroup is true)
  let groupName = null;
  if (isGroup) {
    try {
      const chat = await msg.getChat();
      groupName = chat.name ?? null;
    } catch {
      // ignore
    }
  }

  // ------------------------------------------------------------------
  // 2. Early-exit guards
  // ------------------------------------------------------------------

  const activeMode = mode || settings.botMode;

  // Capture outgoing messages for learning (user's own responses)
  if (msg.fromMe === true) {
    if (body) {
      registerOutgoing(from, contactName, body);
      // Evaluate if user used/modified/ignored our suggestions
      evaluateSuggestionFeedback(from, body);
      saveMessage({ chatId: from, contactName, body, fromMe: true, timestamp: msg.timestamp ?? Math.floor(Date.now() / 1000), category: null, isGroup, groupName });
    }
    return { handled: false, mode: activeMode, contact: contactName };
  }

  // Skip media-only messages (no text body)
  if (!body) {
    return { handled: false, mode: activeMode, contact: contactName };
  }

  // Skip blacklisted contacts
  if (
    settings.blacklistContacts.length > 0 &&
    settings.blacklistContacts.some(
      (blocked) =>
        blocked.trim().toLowerCase() === contactName.toLowerCase() ||
        blocked.trim() === from
    )
  ) {
    console.log(`[MessageHandler] Skipping blacklisted contact: ${contactName}`);
    return { handled: false, mode: activeMode, contact: contactName };
  }

  // ------------------------------------------------------------------
  // 3. Classify the message with AI
  // ------------------------------------------------------------------
  const timestamp = msg.timestamp ?? Math.floor(Date.now() / 1000);

  let category = 'unknown';
  try {
    const classification = await classifyMessage(body, contactName);
    if (classification) {
      category = classification.category;
    }
  } catch (err) {
    console.error('[MessageHandler] Classification error:', err.message);
  }

  // ------------------------------------------------------------------
  // 4. Persist the message (once, with category already set)
  // ------------------------------------------------------------------
  saveMessage({
    chatId: from,
    contactName,
    body,
    fromMe: false,
    timestamp,
    category,
    isGroup,
    groupName,
  });

  // Register for learning (pairs incoming with future outgoing)
  registerIncoming(from, contactName, body, category, isGroup);

  // ------------------------------------------------------------------
  // 5. Act according to botMode
  // ------------------------------------------------------------------

  // Get conversation context for AI
  const contextMsgs = getMessagesByContact(contactName, 20).map(m => ({
    fromMe: Boolean(m.from_me),
    body: m.body,
  }));

  // Get learned style context (how the user usually responds to this contact)
  let styleContext = '';
  try {
    styleContext = await getStyleContext(contactName);
  } catch {
    // Learning data may not exist yet
  }

  if (activeMode === 'auto') {
    // Safe-guard: never auto-reply in groups — fall through to suggest mode
    if (isGroup) {
      console.log(chalk.yellow(`[SafeGuard] Grupo detectado — modo auto desabilitado para "${groupName}". Usando suggest.`));
    } else if (!canAutoReply(from)) {
      console.log(chalk.yellow(`[SafeGuard] Rate-limit: muitas respostas automaticas para ${contactName}. Usando suggest.`));
    } else {
      try {
        const response = await generateResponse(contextMsgs, body, contactName, styleContext);
        if (response) {
          await msg.reply(response);
          console.log(
            `[MessageHandler] AUTO reply to ${contactName}: ${response.slice(0, 60)}...`
          );
        }
      } catch (err) {
        console.error('[MessageHandler] Auto-response error:', err.message);
      }
      return { handled: true, mode: activeMode, contact: contactName };
    }
  }

  // Suggest mode, or auto mode that fell through (group/rate-limited)
  if (activeMode !== 'summary') {
    try {
      const suggestions = await suggestResponse(contextMsgs, body, contactName, styleContext);

      if (suggestions && suggestions.length > 0) {
        // Register suggestions for feedback tracking
        registerSuggestions(from, contactName, body, suggestions);

        // Store in the queue so user can send from the menu
        addSuggestion(from, contactName, body, suggestions);

        console.log('\n─────────────────────────────────────────');
        console.log(`Nova msg de ${contactName}${isGroup ? ` (${groupName})` : ''}:`);
        console.log(`  "${body}"`);
        console.log('\nSugestoes de resposta:');

        suggestions.forEach((s, i) => {
          console.log(`  ${i + 1}. [${s.label}] ${s.text}`);
        });

        console.log(chalk.yellow('  Use o menu "Responder sugestao" para enviar.'));
        console.log('─────────────────────────────────────────\n');
      }
    } catch (err) {
      console.error('[MessageHandler] Suggest error:', err.message);
    }
  } else {
    console.log(
      `[MessageHandler] SUMMARY mode — saved msg from ${contactName} (${category})`
    );
  }

  return { handled: true, mode: activeMode, contact: contactName };
}
