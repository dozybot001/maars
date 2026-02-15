/**
 * Task cache module
 * Cache: task_id, dependencies (status for execution). Stage from backend. Db unchanged.
 */

const { computeTaskStages } = require('./taskStages');

const planCache = new Map(); // planId -> [{ task_id, dependencies }]

function extractCacheFromTask(task) {
  if (!task || !task.task_id) return null;
  return {
    task_id: task.task_id,
    dependencies: Array.isArray(task.dependencies) ? task.dependencies : []
  };
}

function extractCacheFromTasks(tasks) {
  if (!tasks || !Array.isArray(tasks)) return [];
  return tasks.map(t => ({
    task_id: t.task_id || '',
    dependencies: Array.isArray(t.dependencies) ? t.dependencies : [],
    status: t.status || 'undone'
  })).filter(c => c.task_id);
}

function getPlanCache(planId) {
  return planCache.get(planId) || [];
}

function appendPlanCache(planId, task) {
  const entry = extractCacheFromTask(task);
  if (!entry) return;
  const cache = getPlanCache(planId);
  const idx = cache.findIndex(c => c.task_id === entry.task_id);
  if (idx >= 0) cache[idx] = entry;
  else cache.push(entry);
  planCache.set(planId, cache);
}

function clearPlanCache(planId) {
  planCache.delete(planId);
}

function computeStaged(cacheEntries) {
  if (!cacheEntries || cacheEntries.length === 0) return [];
  return computeTaskStages(cacheEntries);
}

function enrichTreeData(staged, fullTasks) {
  const byId = new Map();
  (fullTasks || []).forEach(t => { if (t?.task_id) byId.set(t.task_id, t); });
  return staged.flat().map(c => {
    const full = byId.get(c.task_id) || {};
    return { ...full, ...c };  // 使用 c 的清洗后依赖，避免跨阶段连线
  });
}

/** Build flat treeData from tasks: extract cache -> compute stage -> enrich with full data. */
function buildTreeData(tasks) {
  if (!tasks || tasks.length === 0) return [];
  const cache = extractCacheFromTasks(tasks);
  const staged = computeStaged(cache);
  return enrichTreeData(staged, tasks);
}

module.exports = {
  extractCacheFromTask,
  extractCacheFromTasks,
  getPlanCache,
  appendPlanCache,
  clearPlanCache,
  computeStaged,
  enrichTreeData,
  buildTreeData
};
