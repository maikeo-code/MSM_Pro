import Anthropic from '@anthropic-ai/sdk';
import { settings } from '../config/settings.js';
import {
  SYSTEM_PROMPT,
  SUMMARY_PROMPT,
  CLASSIFY_PROMPT,
  SUGGEST_PROMPT,
} from './prompts.js';

const client = new Anthropic({ apiKey: settings.anthropicApiKey });

// Haiku model used for cheap classification calls
const HAIKU_MODEL = 'claude-haiku-4-5-20251001';

/**
 * Builds a messages array from conversation context and the new incoming message.
 * @param {Array<{fromMe: boolean, body: string}>} context - Previous messages in the conversation
 * @param {string} message - The new message to respond to
 * @param {string} contactName - Name of the contact
 * @returns {Array} Messages array formatted for the Anthropic API
 */
function buildMessages(context, message, contactName) {
  const messages = [];

  if (context && context.length > 0) {
    for (const msg of context) {
      messages.push({
        role: msg.fromMe ? 'assistant' : 'user',
        content: msg.body,
      });
    }
  }

  // Ensure the last message is from the user (the contact)
  const lastRole = messages.length > 0 ? messages[messages.length - 1].role : null;
  if (lastRole === 'user') {
    // Merge to avoid two consecutive user messages
    messages[messages.length - 1].content += `\n${message}`;
  } else {
    messages.push({ role: 'user', content: message });
  }

  return messages;
}

/**
 * Generates a natural reply to a WhatsApp message using the configured Claude model.
 * @param {Array<{fromMe: boolean, body: string}>} context - Previous messages
 * @param {string} message - The incoming message to reply to
 * @param {string} contactName - Name of the sender
 * @returns {Promise<string|null>} The reply text, or null on error
 */
export async function generateResponse(context, message, contactName, styleContext = '') {
  try {
    let systemPrompt = SYSTEM_PROMPT(settings.myName);
    if (styleContext) {
      systemPrompt += `\n\nIMPORTANTE - Use o estilo aprendido do usuario:\n${styleContext}`;
    }
    const messages = buildMessages(context, message, contactName);

    const response = await client.messages.create({
      model: settings.aiModel,
      max_tokens: settings.maxTokens,
      system: systemPrompt,
      messages,
    });

    return response.content[0]?.text ?? null;
  } catch (error) {
    console.error('[claude] generateResponse error:', error?.message ?? error);
    return null;
  }
}

/**
 * Generates a daily summary of all conversations, grouped by category.
 * @param {Object.<string, Array<{fromMe: boolean, body: string}>>} conversations
 *   Object mapping contact name to their message list
 * @returns {Promise<string|null>} Formatted summary text, or null on error
 */
export async function generateSummary(conversations) {
  try {
    const prompt = SUMMARY_PROMPT(conversations);

    const response = await client.messages.create({
      model: settings.aiModel,
      max_tokens: 2000,
      messages: [{ role: 'user', content: prompt }],
    });

    return response.content[0]?.text ?? null;
  } catch (error) {
    console.error('[claude] generateSummary error:', error?.message ?? error);
    return null;
  }
}

/**
 * Classifies an incoming message to determine whether it needs a response,
 * its urgency level, and its category.
 * Always uses the Haiku model to keep costs low.
 * @param {string} message - The message text to classify
 * @param {string} contactName - Name of the sender
 * @returns {Promise<{needsResponse: boolean, urgency: 'high'|'medium'|'low', category: 'work'|'personal'|'spam'|'notification'}|null>}
 */
export async function classifyMessage(message, contactName) {
  try {
    const prompt = CLASSIFY_PROMPT(contactName, message);

    const response = await client.messages.create({
      model: HAIKU_MODEL,
      max_tokens: 150,
      messages: [{ role: 'user', content: prompt }],
    });

    const raw = response.content[0]?.text?.trim();
    if (!raw) return null;

    const result = JSON.parse(raw);
    return {
      needsResponse: Boolean(result.needsResponse),
      urgency: result.urgency ?? 'low',
      category: result.category ?? 'notification',
    };
  } catch (error) {
    console.error('[claude] classifyMessage error:', error?.message ?? error);
    return null;
  }
}

/**
 * Generates 2-3 suggested reply options with varying levels of detail.
 * Used when the bot is running in "suggest" mode.
 * @param {Array<{fromMe: boolean, body: string}>} context - Previous messages
 * @param {string} message - The incoming message to suggest replies for
 * @param {string} contactName - Name of the sender
 * @returns {Promise<Array<{label: string, text: string}>|null>} Suggestion array, or null on error
 */
export async function suggestResponse(context, message, contactName, styleContext = '') {
  try {
    let prompt = SUGGEST_PROMPT(contactName, context, message);
    if (styleContext) {
      prompt += `\n\nIMPORTANTE - Baseie as sugestoes no estilo real do usuario:\n${styleContext}`;
    }

    const response = await client.messages.create({
      model: settings.aiModel,
      max_tokens: 600,
      messages: [{ role: 'user', content: prompt }],
    });

    const raw = response.content[0]?.text?.trim();
    if (!raw) return null;

    const suggestions = JSON.parse(raw);

    if (!Array.isArray(suggestions) || suggestions.length === 0) return null;

    return suggestions.map((s) => ({
      label: s.label ?? 'Opcao',
      text: s.text ?? '',
    }));
  } catch (error) {
    console.error('[claude] suggestResponse error:', error?.message ?? error);
    return null;
  }
}
