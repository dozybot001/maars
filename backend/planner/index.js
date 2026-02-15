const fs = require('fs').promises;
const path = require('path');
const { mockChatCompletion } = require('../test/mock-stream');

const DECOMPOSE_PROMPT_FILE = path.join(__dirname, 'decompose-prompt.txt');
const VERIFY_PROMPT_FILE = path.join(__dirname, 'verify-prompt.txt');
const FORMAT_PROMPT_FILE = path.join(__dirname, 'format-prompt.txt');
const MOCK_AI_DIR = path.join(__dirname, '../db/test/mock-ai');

const MAX_DECOMPOSE_DEPTH = 5;

async function loadDecomposePrompt() {
  const data = await fs.readFile(DECOMPOSE_PROMPT_FILE, 'utf8');
  return data.trim();
}

async function loadVerifyPrompt() {
  const data = await fs.readFile(VERIFY_PROMPT_FILE, 'utf8');
  return data.trim();
}

async function loadFormatPrompt() {
  const data = await fs.readFile(FORMAT_PROMPT_FILE, 'utf8');
  return data.trim();
}

/** Load mock AI response from db/test/mock-ai. */
async function loadMockResponse(type, taskId) {
  const file = path.join(MOCK_AI_DIR, `${type}.json`);
  let data;
  try {
    data = JSON.parse(await fs.readFile(file, 'utf8'));
  } catch {
    return null;
  }
  const entry = data[taskId] || data._default;
  if (!entry) return null;
  const content = typeof entry.content === 'string' ? entry.content : JSON.stringify(entry.content);
  return { content, reasoning: entry.reasoning || '' };
}

/** Mock chat completion: loads from db/test/mock-ai, streams reasoning via onThinking. */
async function callChatCompletion(messages, onThinking, mockContext, signal) {
  const { type, taskId } = mockContext;
  const mock = await loadMockResponse(type, taskId);
  if (!mock) throw new Error(`No mock data for ${type}/${taskId}`);
  return mockChatCompletion(mock.content, mock.reasoning, onThinking, { signal });
}

// Parse JSON from AI response (handles markdown code blocks)
function parseJsonResponse(text) {
  let cleaned = (text || '').trim();
  const jsonMatch = cleaned.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (jsonMatch) {
    cleaned = jsonMatch[1].trim();
  }
  return JSON.parse(cleaned);
}

/** Decompose parent into phases (no atomicity, no I-O). */
async function decomposeTask(parentTask, onThinking, signal) {
  await loadDecomposePrompt(); // keep prompt loaded for future use
  const content = await callChatCompletion(
    [],
    onThinking,
    { type: 'decompose', taskId: parentTask.task_id },
    signal
  );
  const result = parseJsonResponse(content);
  return (result.tasks || []).filter(
    t => t.task_id && t.description && Array.isArray(t.dependencies)
  );
}

/** Verify if task is atomic. */
async function verifyTask(task, onThinking, signal) {
  await loadVerifyPrompt(); // keep prompt loaded for future use
  const content = await callChatCompletion(
    [],
    onThinking,
    { type: 'verify', taskId: task.task_id },
    signal
  );
  const result = parseJsonResponse(content);
  return { atomic: !!result.atomic, reason: result.reason || '' };
}

/** Format atomic task with input/output. */
async function formatTask(task, onThinking, signal) {
  await loadFormatPrompt(); // keep prompt loaded for future use
  const content = await callChatCompletion(
    [],
    onThinking,
    { type: 'format', taskId: task.task_id },
    signal
  );
  const result = parseJsonResponse(content);
  return result.input && result.output ? { input: result.input, output: result.output } : null;
}

/**
 * Unified flow: Verify first → if atomic: Format; else: Decompose → recurse for each child.
 * All tasks (including 0/idea) go through this.
 */
async function verifyAndDecomposeRecursive(task, allTasks, onTask, onThinking, depth, checkAborted, signal) {
  if (checkAborted?.()) {
    const e = new Error('Aborted');
    e.name = 'AbortError';
    throw e;
  }

  if (depth >= MAX_DECOMPOSE_DEPTH) {
    const io = await formatTask(task, onThinking, signal);
    if (!io) {
      throw new Error(`Format failed for task ${task.task_id} at max depth: missing input/output`);
    }
    const idx = allTasks.findIndex(t => t.task_id === task.task_id);
    if (idx >= 0) allTasks[idx] = { ...allTasks[idx], ...io };
    return;
  }

  const v = await verifyTask(task, onThinking, signal);
  const atomic = v.atomic;

  if (atomic) {
    const io = await formatTask(task, onThinking, signal);
    if (!io) {
      throw new Error(`Format failed for atomic task ${task.task_id}: missing input/output`);
    }
    const idx = allTasks.findIndex(t => t.task_id === task.task_id);
    if (idx >= 0) allTasks[idx] = { ...allTasks[idx], ...io };
    return;
  }

  const children = await decomposeTask(task, onThinking, signal);
  if (children.length === 0) {
    throw new Error(`Decompose returned no children for task ${task.task_id}`);
  }

  allTasks.push(...children);
  children.forEach(t => onTask && onTask(t));

  for (const child of children) {
    await verifyAndDecomposeRecursive(child, allTasks, onTask, onThinking, depth + 1, checkAborted, signal);
  }
}

function hasChildren(tasks, taskId) {
  return taskId === '0'
    ? tasks.some(t => t.task_id && /^[1-9]\d*$/.test(t.task_id))
    : tasks.some(t => t.task_id && t.task_id.startsWith(taskId + '_'));
}

/** Run verify→decompose→format on first task without children. Uses mock data from db/test/mock-ai. */
async function runPlan(plan, onTask, onThinking, options = {}) {
  const { signal } = options;
  const checkAborted = () => signal?.aborted;

  const tasks = plan?.tasks || [];
  const firstTask = tasks.find(t => t.task_id && !hasChildren(tasks, t.task_id));
  if (!firstTask) {
    throw new Error('No decomposable task found. Generate plan first.');
  }

  const allTasks = [...tasks];
  const originalIds = new Set(tasks.map(t => t.task_id));
  await verifyAndDecomposeRecursive(firstTask, allTasks, onTask, onThinking || (() => {}), 0, checkAborted, signal);

  return { tasks: allTasks };
}

module.exports = { runPlan };
