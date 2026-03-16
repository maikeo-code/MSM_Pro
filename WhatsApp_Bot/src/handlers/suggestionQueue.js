/**
 * Persistent queue for pending suggestions backed by SQLite.
 * Survives process restarts — suggestions are not lost.
 */

import {
  savePendingSuggestion,
  getAllPendingSuggestions,
  deletePendingSuggestion,
  deleteAllPendingSuggestions,
  countPendingSuggestions,
} from './database.js';

/**
 * Add (or replace) suggestions for a contact.
 */
export function addSuggestion(chatId, contactName, incomingMsg, suggestions) {
  savePendingSuggestion(chatId, contactName, incomingMsg, suggestions);
}

/**
 * Return all pending suggestion entries (newest first).
 */
export function getPendingSuggestions() {
  return getAllPendingSuggestions();
}

/**
 * Remove a suggestion entry after the user has responded (or dismissed it).
 */
export function removeSuggestion(chatId) {
  deletePendingSuggestion(chatId);
}

/**
 * How many pending suggestions are waiting for action.
 */
export function pendingCount() {
  return countPendingSuggestions();
}

/**
 * Clear all entries (e.g. on mode change or daily reset).
 */
export function clearAll() {
  deleteAllPendingSuggestions();
}
