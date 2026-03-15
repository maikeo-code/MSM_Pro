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
 * Return all messages for a given date string (YYYY-MM-DD, UTC).
 *
 * @param {string} date - e.g. "2026-03-15"
 * @returns {object[]}
 */
export function getMessagesByDate(date) {
  const start = new Date(`${date}T00:00:00.000Z`);
  const end = new Date(`${date}T23:59:59.999Z`);

  return getDb()
    .prepare(
      `SELECT * FROM messages
       WHERE timestamp >= ? AND timestamp <= ?
       ORDER BY timestamp ASC`
    )
    .all(
      Math.floor(start.getTime() / 1000),
      Math.floor(end.getTime() / 1000)
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
