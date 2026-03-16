/**
 * Simple token-bucket rate limiter for API calls.
 * Ensures we don't exceed a configurable requests-per-second limit.
 *
 * Usage:
 *   const limiter = createRateLimiter({ maxPerSecond: 2, maxConcurrent: 3 });
 *   const result = await limiter.execute(() => apiCall());
 */

export function createRateLimiter({ maxPerSecond = 2, maxConcurrent = 3 } = {}) {
  const minInterval = 1000 / maxPerSecond;
  let lastCallTime = 0;
  let activeCount = 0;
  const waiting = [];

  function processQueue() {
    while (waiting.length > 0 && activeCount < maxConcurrent) {
      const now = Date.now();
      const elapsed = now - lastCallTime;

      if (elapsed < minInterval) {
        // Schedule next check after the interval
        setTimeout(processQueue, minInterval - elapsed + 1);
        return;
      }

      const { fn, resolve, reject } = waiting.shift();
      activeCount++;
      lastCallTime = Date.now();

      fn()
        .then(resolve)
        .catch(reject)
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
        waiting.push({ fn, resolve, reject });
        processQueue();
      });
    },

    /** Current queue length */
    get queueLength() { return waiting.length; },

    /** Active concurrent calls */
    get activeCount() { return activeCount; },
  };
}
