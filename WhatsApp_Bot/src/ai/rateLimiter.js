/**
 * Token-bucket rate limiter for API calls.
 * - Respects max requests per second
 * - Limits concurrent calls
 * - Caps queue size to prevent OOM
 * - Timeout per call to prevent stuck slots
 */

const DEFAULT_CALL_TIMEOUT_MS = 30_000;
const DEFAULT_MAX_QUEUE_SIZE = 100;

export function createRateLimiter({
  maxPerSecond = 2,
  maxConcurrent = 3,
  maxQueueSize = DEFAULT_MAX_QUEUE_SIZE,
  callTimeoutMs = DEFAULT_CALL_TIMEOUT_MS,
} = {}) {
  const minInterval = 1000 / maxPerSecond;
  let lastCallTime = 0;
  let activeCount = 0;
  let scheduled = false;
  const waiting = [];

  function processQueue() {
    scheduled = false;

    while (waiting.length > 0 && activeCount < maxConcurrent) {
      const now = Date.now();
      const elapsed = now - lastCallTime;

      if (elapsed < minInterval) {
        if (!scheduled) {
          scheduled = true;
          setTimeout(() => { scheduled = false; processQueue(); }, minInterval - elapsed + 1);
        }
        return;
      }

      const { fn, resolve, reject, timer } = waiting.shift();
      activeCount++;
      lastCallTime = Date.now();

      fn()
        .then((result) => { clearTimeout(timer); resolve(result); })
        .catch((err) => { clearTimeout(timer); reject(err); })
        .finally(() => {
          activeCount--;
          processQueue();
        });
    }
  }

  return {
    /**
     * Execute a function respecting rate limits.
     * @template T
     * @param {() => Promise<T>} fn
     * @returns {Promise<T>}
     */
    execute(fn) {
      return new Promise((resolve, reject) => {
        if (waiting.length >= maxQueueSize) {
          return reject(new Error(`Rate limiter queue full (max ${maxQueueSize}). Try again later.`));
        }

        // Timeout: if call doesn't complete in time, reject and free the slot
        const timer = setTimeout(() => {
          const idx = waiting.findIndex(w => w.timer === timer);
          if (idx !== -1) {
            waiting.splice(idx, 1);
            reject(new Error(`Rate limiter call timed out after ${callTimeoutMs}ms`));
          }
        }, callTimeoutMs + (waiting.length * minInterval)); // account for queue wait

        waiting.push({ fn, resolve, reject, timer });
        processQueue();
      });
    },

    /** Current queue length */
    get queueLength() { return waiting.length; },

    /** Active concurrent calls */
    get activeCount() { return activeCount; },
  };
}
