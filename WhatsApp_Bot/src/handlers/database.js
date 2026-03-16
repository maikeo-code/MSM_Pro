import Database from 'better-sqlite3';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { mkdirSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DB_PATH = join(__dirname, '../../data/messages.db');

// Ensure the data directory exists before opening the database
mkdirSync(dirname(DB_PATH), { recursive: true });

let db;

/**
 * Initialise the SQLite database and create tables if they do not exist.
 * Must be called once before any other function is used.
 */
export function initDb() {
  db = new Database(DB_PATH);

  // Enable WAL mode for better concurrent read performance
  db.pragma('journal_mode = WAL');

  db.exec(`
    CREATE TABLE IF NOT EXISTS messages (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      chat_id      TEXT    NOT NULL,
      contact_name TEXT    NOT NULL,
      body         TEXT    NOT NULL,
      from_me      INTEGER NOT NULL DEFAULT 0,
      timestamp    INTEGER NOT NULL,
      category     TEXT,
      is_group     INTEGER NOT NULL DEFAULT 0,
      group_name   TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
    CREATE INDEX IF NOT EXISTS idx_messages_contact   ON messages(contact_name);
    CREATE INDEX IF NOT EXISTS idx_messages_chat      ON messages(chat_id);

    CREATE TABLE IF NOT EXISTS summaries (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      date       TEXT    NOT NULL UNIQUE,
      content    TEXT    NOT NULL,
      created_at INTEGER NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_summaries_date ON summaries(date);

    CREATE TABLE IF NOT EXISTS pending_suggestions (
      chat_id      TEXT    PRIMARY KEY,
      contact_name TEXT    NOT NULL,
      incoming_msg TEXT    NOT NULL,
      suggestions  TEXT    NOT NULL,
      created_at   INTEGER NOT NULL
    );
  `);

  return db;
}

/**
 * Return the active database connection, initialising it on first access.
 * @returns {Database}
 */
function getDb() {
  if (!db) {
    initDb();
  }
  return db;
}

/**
 * Persist a single incoming or outgoing message.
 *
 * @param {object} params
 * @param {string}  params.chatId
 * @param {string}  params.contactName
 * @param {string}  params.body
 * @param {boolean} params.fromMe
 * @param {number}  params.timestamp   - Unix seconds
 * @param {string}  [params.category]
 * @param {boolean} params.isGroup
 * @param {string}  [params.groupName]
 * @returns {number} The row id of the inserted message
 */
export function saveMessage({
  chatId,
  contactName,
  body,
  fromMe,
  timestamp,
  category = null,
  isGroup,
  groupName = null,
}) {
  const stmt = getDb().prepare(`
    INSERT INTO messages
      (chat_id, contact_name, body, from_me, timestamp, category, is_group, group_name)
    VALUES
      (@chatId, @contactName, @body, @fromMe, @timestamp, @category, @isGroup, @groupName)
  `);

  const result = stmt.run({
    chatId,
    contactName,
    body,
    fromMe: fromMe ? 1 : 0,
    timestamp,
    category,
    isGroup: isGroup ? 1 : 0,
    groupName,
  });

  return result.lastInsertRowid;
}

/**
 * Return every message whose timestamp falls within the current calendar day
 * (UTC midnight → now).
 *
 * @returns {object[]}
 */
export function getMessagesToday() {
  // Calculate start of day in BRT (UTC-3) so messages between 00:00-02:59 BRT
  // are not misclassified as belonging to the previous UTC day.
  const now = new Date();
  const brtOffset = -3 * 60; // BRT = UTC-3, in minutes
  const brtNow = new Date(now.getTime() + (brtOffset + now.getTimezoneOffset()) * 60000);
  brtNow.setHours(0, 0, 0, 0);
  const startOfDayBRT = new Date(brtNow.getTime() - (brtOffset + now.getTimezoneOffset()) * 60000);
  const startTs = Math.floor(startOfDayBRT.getTime() / 1000);

  return getDb()
    .prepare(
      `SELECT * FROM messages WHERE timestamp >= ? ORDER BY timestamp ASC`
    )
    .all(startTs);
}

/**
 * Return the most recent messages exchanged with a given contact.
 *
 * @param {string} contactName
 * @param {number} [limit=50]
 * @returns {object[]}
 */
export function getMessagesByContact(contactName, limit = 50) {
  return getDb()
    .prepare(
      `SELECT * FROM messages
       WHERE contact_name = ?
       ORDER BY timestamp DESC
       LIMIT ?`
    )
    .all(contactName, limit)
    .reverse(); // return in chronological order
}

/**
 * Return all messages for a given date string (YYYY-MM-DD) in BRT timezone.
 *
 * @param {string} date - e.g. "2026-03-15"
 * @returns {object[]}
 */
export function getMessagesByDate(date) {
  // BRT = UTC-3: midnight in BRT = 03:00 UTC
  const startBRT = new Date(`${date}T03:00:00.000Z`);
  const endBRT = new Date(startBRT.getTime() + 24 * 60 * 60 * 1000 - 1);

  return getDb()
    .prepare(
      `SELECT * FROM messages
       WHERE timestamp >= ? AND timestamp <= ?
       ORDER BY timestamp ASC`
    )
    .all(
      Math.floor(startBRT.getTime() / 1000),
      Math.floor(endBRT.getTime() / 1000)
    );
}

/**
 * Persist (or replace) the daily summary for a specific date.
 *
 * @param {string} date    - YYYY-MM-DD
 * @param {string} content - The summary text
 * @returns {number} Row id
 */
export function saveSummary(date, content) {
  const stmt = getDb().prepare(`
    INSERT INTO summaries (date, content, created_at)
    VALUES (@date, @content, @createdAt)
    ON CONFLICT(date) DO UPDATE SET
      content    = excluded.content,
      created_at = excluded.created_at
  `);

  const result = stmt.run({
    date,
    content,
    createdAt: Math.floor(Date.now() / 1000),
  });

  return result.lastInsertRowid;
}

/**
 * Retrieve the summary for a given date, or null if not yet generated.
 *
 * @param {string} date - YYYY-MM-DD
 * @returns {object|null}
 */
export function getSummary(date) {
  return (
    getDb()
      .prepare(`SELECT * FROM summaries WHERE date = ?`)
      .get(date) ?? null
  );
}

// ── Pending Suggestions (persistent queue) ──────────────────────────

export function savePendingSuggestion(chatId, contactName, incomingMsg, suggestions) {
  getDb().prepare(`
    INSERT OR REPLACE INTO pending_suggestions (chat_id, contact_name, incoming_msg, suggestions, created_at)
    VALUES (?, ?, ?, ?, ?)
  `).run(chatId, contactName, incomingMsg, JSON.stringify(suggestions), Math.floor(Date.now() / 1000));
}

export function getAllPendingSuggestions() {
  return getDb()
    .prepare(`SELECT * FROM pending_suggestions ORDER BY created_at DESC`)
    .all()
    .map(row => ({
      chatId: row.chat_id,
      contactName: row.contact_name,
      incomingMsg: row.incoming_msg,
      suggestions: JSON.parse(row.suggestions),
      timestamp: row.created_at * 1000,
    }));
}

export function deletePendingSuggestion(chatId) {
  getDb().prepare(`DELETE FROM pending_suggestions WHERE chat_id = ?`).run(chatId);
}

export function deleteAllPendingSuggestions() {
  getDb().prepare(`DELETE FROM pending_suggestions`).run();
}

export function countPendingSuggestions() {
  return getDb().prepare(`SELECT COUNT(*) as count FROM pending_suggestions`).get().count;
}

// ── Message search / history ────────────────────────────────────────

export function searchMessages(query, limit = 50) {
  return getDb()
    .prepare(`SELECT * FROM messages WHERE body LIKE ? ORDER BY timestamp DESC LIMIT ?`)
    .all(`%${query}%`, limit);
}

export function getMessageHistory(contactName, limit = 100) {
  return getDb()
    .prepare(`SELECT * FROM messages WHERE contact_name = ? ORDER BY timestamp DESC LIMIT ?`)
    .all(contactName, limit)
    .reverse();
}

export function getDistinctContacts() {
  return getDb()
    .prepare(`SELECT contact_name, COUNT(*) as msg_count, MAX(timestamp) as last_msg FROM messages GROUP BY contact_name ORDER BY last_msg DESC`)
    .all();
}

export function getAllSummaries(limit = 30) {
  return getDb()
    .prepare(`SELECT * FROM summaries ORDER BY date DESC LIMIT ?`)
    .all(limit);
}
