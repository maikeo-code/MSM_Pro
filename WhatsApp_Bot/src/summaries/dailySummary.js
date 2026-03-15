import { getMessagesByDate, getMessagesToday, saveSummary } from '../handlers/database.js';
import { generateSummary } from '../ai/claude.js';

/**
 * Format today's date (or any Date) as a YYYY-MM-DD string in UTC.
 *
 * @param {Date} [date]
 * @returns {string}
 */
function toDateString(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

/**
 * Group an array of message rows by their contact_name.
 *
 * @param {object[]} messages
 * @returns {Record<string, object[]>}
 */
function groupByContact(messages) {
  return messages.reduce((acc, msg) => {
    const key = msg.contact_name;
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(msg);
    return acc;
  }, {});
}

/**
 * Generate and persist a daily summary.
 *
 * @param {object}  [options]
 * @param {string}  [options.date]      - YYYY-MM-DD (defaults to today)
 * @param {any}     [options.aiClient]  - AI client instance (optional override)
 * @returns {Promise<string>} The generated summary text
 */
export async function generateDailySummary({ date } = {}) {
  const targetDate = date ?? toDateString();

  // Fetch messages for the target date
  const messages =
    date ? getMessagesByDate(date) : getMessagesToday();

  if (messages.length === 0) {
    const empty = `No messages found for ${targetDate}.`;
    saveSummary(targetDate, empty);
    return empty;
  }

  // Group messages by contact for a more structured summary prompt
  const grouped = groupByContact(messages);

  // Ask the AI to produce the summary
  const summaryText = await generateSummary(grouped);

  // Persist and return
  saveSummary(targetDate, summaryText);

  return summaryText;
}

/**
 * Set up a lightweight scheduler that generates and prints a daily summary
 * at the specified wall-clock time.
 *
 * @param {string} time - "HH:MM" in local time (e.g. "22:00")
 * @returns {() => void} A cancel function that stops the interval
 *
 * @example
 * const cancel = scheduleSummary('22:00');
 * // Later, to stop:
 * cancel();
 */
export function scheduleSummary(time) {
  const [targetHour, targetMinute] = time.split(':').map(Number);

  let lastRunDate = null; // Track the date we last ran to avoid duplicate runs

  const intervalId = setInterval(async () => {
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();
    const todayStr = toDateString(now);

    // Fire only once per day at the target time
    if (
      currentHour === targetHour &&
      currentMinute === targetMinute &&
      lastRunDate !== todayStr
    ) {
      lastRunDate = todayStr;

      console.log(`\n[DailySummary] Generating summary for ${todayStr}...`);

      try {
        const summary = await generateDailySummary({ date: todayStr });
        console.log('\n════════════════════════════════════════');
        console.log(`  Daily Summary — ${todayStr}`);
        console.log('════════════════════════════════════════');
        console.log(summary);
        console.log('════════════════════════════════════════\n');
      } catch (err) {
        console.error('[DailySummary] Error generating summary:', err.message);
      }
    }
  }, 60_000); // check every minute

  // Return a cancel function
  return () => clearInterval(intervalId);
}
