/**
 * Global queue for pending suggestions that the user can act on.
 *
 * Each entry maps a chatId to its suggestion data so the user can
 * select and send a suggested reply from the interactive menu.
 */

/** @type {Map<string, { chatId: string, contactName: string, incomingMsg: string, suggestions: Array<{label: string, text: string}>, timestamp: number }>} */
const queue = new Map();

/**
 * Add (or replace) suggestions for a contact.
 *
 * @param {string} chatId
 * @param {string} contactName
 * @param {string} incomingMsg
 * @param {Array<{label: string, text: string}>} suggestions
 */
export function addSuggestion(chatId, contactName, incomingMsg, suggestions) {
  queue.set(chatId, {
    chatId,
    contactName,
    incomingMsg,
    suggestions,
    timestamp: Date.now(),
  });
}

/**
 * Return all pending suggestion entries (newest first).
 * @returns {Array<{ chatId: string, contactName: string, incomingMsg: string, suggestions: Array<{label: string, text: string}>, timestamp: number }>}
 */
export function getPendingSuggestions() {
  return [...queue.values()].sort((a, b) => b.timestamp - a.timestamp);
}

/**
 * Remove a suggestion entry after the user has responded (or dismissed it).
 * @param {string} chatId
 */
export function removeSuggestion(chatId) {
  queue.delete(chatId);
}

/**
 * How many pending suggestions are waiting for action.
 * @returns {number}
 */
export function pendingCount() {
  return queue.size;
}

/**
 * Clear all entries (e.g. on mode change or daily reset).
 */
export function clearAll() {
  queue.clear();
}
