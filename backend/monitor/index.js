/**
 * Monitor Module
 * Builds layout from execution using taskCache (extract -> stage -> enrich).
 */

const taskCache = require('../tasks/taskCache');
const { buildTaskLayout } = require('./timetable');

function groupByStage(treeData) {
  const stageMap = new Map();
  (treeData || []).forEach(t => {
    const idx = (t.stage || 1) - 1;
    if (!stageMap.has(idx)) stageMap.set(idx, []);
    stageMap.get(idx).push(t);
  });
  return [...stageMap.keys()].sort((a, b) => a - b).map(k => stageMap.get(k));
}

/**
 * Build layout from execution. Returns { grid, treeData, ... }.
 */
function buildLayoutFromExecution(execution) {
  let execData = execution;
  if (typeof execution === 'string') {
    try {
      execData = JSON.parse(execution);
    } catch (e) {
      throw new Error('Invalid execution format');
    }
  }

  const fullTasks = execData.tasks && Array.isArray(execData.tasks) ? execData.tasks : [];
  if (fullTasks.length === 0) return { treeData: [], grid: [], maxRows: 0, maxCols: 0, isolatedTasks: [] };

  const treeData = taskCache.buildTreeData(fullTasks);
  const staged = groupByStage(treeData);
  return buildTaskLayout(staged);
}

module.exports = {
  buildLayoutFromExecution,
  buildTaskLayout
};
