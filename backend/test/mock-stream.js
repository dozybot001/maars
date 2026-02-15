/**
 * Mock AI streaming simulation
 * Simulates SSE-style reasoning chunks for frontend planner thinking display.
 * Used by planner (mock-only mode).
 */

/**
 * Simulate streaming reasoning content to onThinking callback.
 * Splits text into chunks and emits with small delays to mimic AI streaming.
 * @param {string} reasoning - Full reasoning text to stream
 * @param {function(string): void} onThinking - Callback for each chunk
 * @param {number} chunkSize - Approximate chars per chunk (default 8)
 * @param {number} delayMs - Delay between chunks in ms (default 30)
 * @param {AbortSignal} signal - Optional abort signal to stop streaming
 * @returns {Promise<void>}
 */
async function simulateReasoningStream(reasoning, onThinking, chunkSize = 8, delayMs = 30, signal) {
  if (!reasoning || typeof reasoning !== 'string') return;
  if (typeof onThinking !== 'function') return;

  const delay = (ms) => new Promise((r) => setTimeout(r, ms));

  for (let i = 0; i < reasoning.length; i += chunkSize) {
    if (signal?.aborted) {
      const e = new Error('Aborted');
      e.name = 'AbortError';
      throw e;
    }
    const chunk = reasoning.slice(i, i + chunkSize);
    if (chunk) onThinking(chunk);
    await delay(delayMs);
  }
}

/**
 * Run mock chat completion: stream reasoning, then return content.
 * @param {string} content - JSON string to return as "content"
 * @param {string} reasoning - Text to stream via onThinking
 * @param {function(string): void} onThinking - Callback for streaming
 * @param {Object} options - { chunkSize, delayMs, signal }
 * @returns {Promise<string>} The content string
 */
async function mockChatCompletion(content, reasoning, onThinking, options = {}) {
  const { chunkSize = 8, delayMs = 30, signal } = options;
  await simulateReasoningStream(reasoning || '', onThinking, chunkSize, delayMs, signal);
  return content || '';
}

module.exports = {
  simulateReasoningStream,
  mockChatCompletion
};
