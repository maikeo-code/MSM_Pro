import dayjs from 'dayjs';
import { saveResponsePair, updateMetrics } from './learningDb.js';
import { getMessagesToday } from '../handlers/database.js';

/**
 * Track when we last saw a message from each contact,
 * so we can pair incoming messages with user responses.
 *
 * Map<contactId, { contactName, message, timestamp, category, isGroup }>
 */
const pendingMessages = new Map();

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

  return pair;
}

/**
 * Return a snapshot of the current collection state.
 *
 * @returns {{ pendingResponses: number }}
 */
export function getCollectionStats() {
  const pending = pendingMessages.size;
  return { pendingResponses: pending };
}
