import Database from 'better-sqlite3';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { mkdirSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DB_PATH = join(__dirname, '../../data/learning.db');

mkdirSync(dirname(DB_PATH), { recursive: true });

let db;

/**
 * Return the active database connection, initialising it on first access.
 * @returns {Database}
 */
function getDb() {
  if (!db) {
    initLearningDb();
  }
  return db;
}

/**
 * Create all learning tables and enable WAL mode.
 * Safe to call multiple times (CREATE TABLE IF NOT EXISTS).
 */
export function initLearningDb() {
  db = new Database(DB_PATH);

  db.pragma('journal_mode = WAL');

  db.exec(`
    CREATE TABLE IF NOT EXISTS response_pairs (
      id                    INTEGER PRIMARY KEY AUTOINCREMENT,
      contact_name          TEXT    NOT NULL,
      contact_id            TEXT,
      category              TEXT,
      incoming_msg          TEXT    NOT NULL,
      user_response         TEXT    NOT NULL,
      response_time_seconds INTEGER,
      is_group              INTEGER DEFAULT 0,
      created_at            TEXT    DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_pairs_contact   ON response_pairs(contact_name);
    CREATE INDEX IF NOT EXISTS idx_pairs_timestamp ON response_pairs(created_at);

    CREATE TABLE IF NOT EXISTS contact_styles (
      id                   INTEGER PRIMARY KEY AUTOINCREMENT,
      contact_name         TEXT    UNIQUE NOT NULL,
      category             TEXT,
      tone                 TEXT,
      greeting_words       TEXT,
      farewell_words       TEXT,
      common_phrases       TEXT,
      emoji_usage          TEXT,
      avg_response_length  INTEGER,
      response_pattern     TEXT,
      total_interactions   INTEGER DEFAULT 0,
      last_updated         TEXT    DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_styles_contact ON contact_styles(contact_name);

    CREATE TABLE IF NOT EXISTS user_vocabulary (
      id             INTEGER PRIMARY KEY AUTOINCREMENT,
      word_or_phrase TEXT    UNIQUE NOT NULL,
      frequency      INTEGER DEFAULT 1,
      context        TEXT,
      last_used      TEXT    DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS learning_metrics (
      id                    INTEGER PRIMARY KEY AUTOINCREMENT,
      date                  TEXT    NOT NULL,
      suggestions_shown     INTEGER DEFAULT 0,
      suggestions_used      INTEGER DEFAULT 0,
      suggestions_modified  INTEGER DEFAULT 0,
      suggestions_ignored   INTEGER DEFAULT 0,
      accuracy_score        REAL    DEFAULT 0.0,
      UNIQUE(date)
    );

    CREATE TABLE IF NOT EXISTS suggestion_feedback (
      id                INTEGER PRIMARY KEY AUTOINCREMENT,
      contact_name      TEXT    NOT NULL,
      contact_id        TEXT,
      incoming_msg      TEXT    NOT NULL,
      suggested_texts   TEXT,
      user_response     TEXT,
      outcome           TEXT    NOT NULL,
      similarity_score  REAL    DEFAULT 0.0,
      created_at        TEXT    DEFAULT (datetime('now'))
    );
  `);

  return db;
}

/**
 * Persist a response pair (incoming message + user's reply).
 *
 * @param {object} params
 * @param {string}  params.contactName
 * @param {string}  [params.contactId]
 * @param {string}  [params.category]        - work, personal, financial, group
 * @param {string}  params.incomingMsg
 * @param {string}  params.userResponse
 * @param {number}  [params.responseTimeSeconds]
 * @param {boolean} [params.isGroup]
 * @returns {number} The row id of the inserted record
 */
export function saveResponsePair({
  contactName,
  contactId = null,
  category = null,
  incomingMsg,
  userResponse,
  responseTimeSeconds = null,
  isGroup = false,
}) {
  const stmt = getDb().prepare(`
    INSERT INTO response_pairs
      (contact_name, contact_id, category, incoming_msg, user_response,
       response_time_seconds, is_group)
    VALUES
      (@contactName, @contactId, @category, @incomingMsg, @userResponse,
       @responseTimeSeconds, @isGroup)
  `);

  const result = stmt.run({
    contactName,
    contactId,
    category,
    incomingMsg,
    userResponse,
    responseTimeSeconds,
    isGroup: isGroup ? 1 : 0,
  });

  return result.lastInsertRowid;
}

/**
 * Return recent response pairs for a specific contact.
 *
 * @param {string} contactName
 * @param {number} [limit=50]
 * @returns {object[]}
 */
export function getResponsePairs(contactName, limit = 50) {
  return getDb()
    .prepare(
      `SELECT * FROM response_pairs
       WHERE contact_name = ?
       ORDER BY created_at DESC
       LIMIT ?`
    )
    .all(contactName, limit);
}

/**
 * Return all recent response pairs across every contact.
 *
 * @param {number} [limit=500]
 * @returns {object[]}
 */
export function getAllResponsePairs(limit = 500) {
  return getDb()
    .prepare(
      `SELECT * FROM response_pairs
       ORDER BY created_at DESC
       LIMIT ?`
    )
    .all(limit);
}

/**
 * Upsert the learned style profile for a contact.
 *
 * @param {object} params
 * @param {string}   params.contactName
 * @param {string}   [params.category]
 * @param {string}   [params.tone]
 * @param {string[]} [params.greetingWords]
 * @param {string[]} [params.farewellWords]
 * @param {string[]} [params.commonPhrases]
 * @param {string}   [params.emojiUsage]       - none, low, medium, high
 * @param {number}   [params.avgResponseLength]
 * @param {string}   [params.responsePattern]  - quick, delayed, selective
 * @param {number}   [params.totalInteractions]
 * @returns {number} The row id of the upserted record
 */
export function saveContactStyle({
  contactName,
  category = null,
  tone = null,
  greetingWords = null,
  farewellWords = null,
  commonPhrases = null,
  emojiUsage = null,
  avgResponseLength = null,
  responsePattern = null,
  totalInteractions = 0,
}) {
  const stmt = getDb().prepare(`
    INSERT INTO contact_styles
      (contact_name, category, tone, greeting_words, farewell_words,
       common_phrases, emoji_usage, avg_response_length, response_pattern,
       total_interactions, last_updated)
    VALUES
      (@contactName, @category, @tone, @greetingWords, @farewellWords,
       @commonPhrases, @emojiUsage, @avgResponseLength, @responsePattern,
       @totalInteractions, datetime('now'))
    ON CONFLICT(contact_name) DO UPDATE SET
      category             = excluded.category,
      tone                 = excluded.tone,
      greeting_words       = excluded.greeting_words,
      farewell_words       = excluded.farewell_words,
      common_phrases       = excluded.common_phrases,
      emoji_usage          = excluded.emoji_usage,
      avg_response_length  = excluded.avg_response_length,
      response_pattern     = excluded.response_pattern,
      total_interactions   = excluded.total_interactions,
      last_updated         = excluded.last_updated
  `);

  const result = stmt.run({
    contactName,
    category,
    tone,
    greetingWords: greetingWords ? JSON.stringify(greetingWords) : null,
    farewellWords: farewellWords ? JSON.stringify(farewellWords) : null,
    commonPhrases: commonPhrases ? JSON.stringify(commonPhrases) : null,
    emojiUsage,
    avgResponseLength,
    responsePattern,
    totalInteractions,
  });

  return result.lastInsertRowid;
}

/**
 * Parse JSON array fields on a raw contact_styles row back to JS arrays.
 *
 * @param {object|null} row
 * @returns {object|null}
 */
function parseContactStyle(row) {
  if (!row) return null;

  return {
    ...row,
    greeting_words: row.greeting_words ? JSON.parse(row.greeting_words) : [],
    farewell_words: row.farewell_words ? JSON.parse(row.farewell_words) : [],
    common_phrases: row.common_phrases ? JSON.parse(row.common_phrases) : [],
  };
}

/**
 * Return the style profile for a contact, or null if none exists.
 * JSON fields (greeting_words, farewell_words, common_phrases) are
 * parsed back to arrays.
 *
 * @param {string} contactName
 * @returns {object|null}
 */
export function getContactStyle(contactName) {
  const row = getDb()
    .prepare(`SELECT * FROM contact_styles WHERE contact_name = ?`)
    .get(contactName) ?? null;

  return parseContactStyle(row);
}

/**
 * Return all contact style profiles with JSON fields parsed to arrays.
 *
 * @returns {object[]}
 */
export function getAllContactStyles() {
  const rows = getDb()
    .prepare(`SELECT * FROM contact_styles ORDER BY contact_name ASC`)
    .all();

  return rows.map(parseContactStyle);
}

/**
 * Insert a vocabulary entry or increment its frequency if it already exists.
 *
 * @param {string} wordOrPhrase
 * @param {string} [context] - greeting, farewell, filler, expression
 * @returns {number} The row id
 */
export function saveVocabulary(wordOrPhrase, context = null) {
  const stmt = getDb().prepare(`
    INSERT INTO user_vocabulary (word_or_phrase, context, last_used)
    VALUES (@wordOrPhrase, @context, datetime('now'))
    ON CONFLICT(word_or_phrase) DO UPDATE SET
      frequency = frequency + 1,
      last_used = excluded.last_used
  `);

  const result = stmt.run({ wordOrPhrase, context });
  return result.lastInsertRowid;
}

/**
 * Return the most frequently used words/phrases.
 *
 * @param {number} [limit=50]
 * @returns {object[]}
 */
export function getTopVocabulary(limit = 50) {
  return getDb()
    .prepare(
      `SELECT * FROM user_vocabulary
       ORDER BY frequency DESC
       LIMIT ?`
    )
    .all(limit);
}

/**
 * Increment a specific metric counter for the given date.
 * Creates the row for that date if it does not exist yet.
 *
 * @param {string} date  - YYYY-MM-DD
 * @param {string} field - suggestions_shown | suggestions_used |
 *                         suggestions_modified | suggestions_ignored
 */
export function updateMetrics(date, field) {
  // Pre-compiled statements per field — no string interpolation in SQL
  const stmts = {
    suggestions_shown: 'UPDATE learning_metrics SET suggestions_shown = suggestions_shown + 1 WHERE date = ?',
    suggestions_used: 'UPDATE learning_metrics SET suggestions_used = suggestions_used + 1 WHERE date = ?',
    suggestions_modified: 'UPDATE learning_metrics SET suggestions_modified = suggestions_modified + 1 WHERE date = ?',
    suggestions_ignored: 'UPDATE learning_metrics SET suggestions_ignored = suggestions_ignored + 1 WHERE date = ?',
  };

  if (!stmts[field]) {
    throw new Error(`updateMetrics: unknown field "${field}". Allowed: ${Object.keys(stmts).join(', ')}`);
  }

  // Ensure the row exists before incrementing
  getDb()
    .prepare(
      `INSERT INTO learning_metrics (date) VALUES (?)
       ON CONFLICT(date) DO NOTHING`
    )
    .run(date);

  getDb().prepare(stmts[field]).run(date);
}

/**
 * Return the total count of response pairs (efficient COUNT query).
 *
 * @returns {number}
 */
export function getResponsePairCount() {
  const row = getDb()
    .prepare(`SELECT COUNT(*) as count FROM response_pairs`)
    .get();
  return row?.count ?? 0;
}

/**
 * Return the metrics row for a specific date, or null if none.
 *
 * @param {string} date - YYYY-MM-DD
 * @returns {object|null}
 */
export function getMetrics(date) {
  return (
    getDb()
      .prepare(`SELECT * FROM learning_metrics WHERE date = ?`)
      .get(date) ?? null
  );
}

/**
 * Save feedback about a suggestion (was it used, modified, or ignored?).
 *
 * @param {object} params
 * @param {string}   params.contactName
 * @param {string}   [params.contactId]
 * @param {string}   params.incomingMsg
 * @param {string[]} [params.suggestedTexts] - The suggestions the bot offered
 * @param {string}   [params.userResponse]   - What the user actually sent
 * @param {string}   params.outcome          - 'used' | 'modified' | 'ignored' | 'own_response'
 * @param {number}   [params.similarityScore] - 0.0 to 1.0 (how close was the suggestion)
 */
export function saveSuggestionFeedback({
  contactName,
  contactId = null,
  incomingMsg,
  suggestedTexts = [],
  userResponse = null,
  outcome,
  similarityScore = 0.0,
}) {
  const stmt = getDb().prepare(`
    INSERT INTO suggestion_feedback
      (contact_name, contact_id, incoming_msg, suggested_texts,
       user_response, outcome, similarity_score)
    VALUES
      (@contactName, @contactId, @incomingMsg, @suggestedTexts,
       @userResponse, @outcome, @similarityScore)
  `);

  stmt.run({
    contactName,
    contactId,
    incomingMsg,
    suggestedTexts: JSON.stringify(suggestedTexts),
    userResponse,
    outcome,
    similarityScore,
  });
}

/**
 * Get feedback stats: how often suggestions are used vs ignored.
 *
 * @returns {{ total: number, used: number, modified: number, ignored: number, ownResponse: number, accuracy: number }}
 */
export function getFeedbackStats() {
  const rows = getDb()
    .prepare(`SELECT outcome, COUNT(*) as count FROM suggestion_feedback GROUP BY outcome`)
    .all();

  const stats = { total: 0, used: 0, modified: 0, ignored: 0, ownResponse: 0 };
  for (const row of rows) {
    stats.total += row.count;
    if (row.outcome === 'used') stats.used = row.count;
    if (row.outcome === 'modified') stats.modified = row.count;
    if (row.outcome === 'ignored') stats.ignored = row.count;
    if (row.outcome === 'own_response') stats.ownResponse = row.count;
  }

  stats.accuracy = stats.total > 0
    ? Math.round(((stats.used + stats.modified * 0.5) / stats.total) * 100)
    : 0;

  return stats;
}
