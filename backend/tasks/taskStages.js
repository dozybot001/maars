/**
 * Unified task stages module
 * Single source: clean dependencies + compute stages. Does not modify original data.
 */

const { cleanDependencies } = require('../monitor/timetable');

/**
 * 依赖下沉 (sinkDependencies)
 *
 * Plan 是动态的、不断向下延伸的（从 0 到 atomic tasks）。当父任务被分解为子任务后，
 * 指向该父任务的依赖应下沉到其子任务的叶子节点，父任务不再出现在依赖线中。
 *
 * 例如：1 已分解为 1_1, 1_2, 1_5 等，则：
 * - 4 依赖 1 → 下沉为 4 依赖 1 的叶子任务（1_5 等）
 * - 同理，若 1_1 再分解为 1_1_1, 1_1_2，则依赖 1_1 的会下沉到 1_1_1, 1_1_2
 *
 * Leaf = 该前缀下无其他同前缀任务依赖它的任务（即子树末端）。
 *
 * @param {Array} tasks - Flat tasks [{ task_id, dependencies?, ... }]
 * @returns {Array} Tasks with sunk dependencies (new array, original unchanged)
 */
function sinkDependencies(tasks) {
  if (!tasks || !Array.isArray(tasks) || tasks.length === 0) return tasks;

  const taskMap = new Map(tasks.map(t => [t.task_id, { ...t, dependencies: [...(t.dependencies || [])] }]));

  /**
   * 判断 taskId 是否在 parentId 的子树内。
   * 0 的子树为 1, 2, 3, 4；其余为 parentId_1, parentId_2...
   */
  function isInSubtree(taskId, parentId) {
    if (!taskId || !parentId) return false;
    if (parentId === '0') return /^[1-9]\d*$/.test(taskId);
    return taskId.startsWith(parentId + '_');
  }

  /**
   * 获取以 parentId 为前缀的子树的叶子任务。
   * 0 的子任务为 1, 2, 3, 4（顶层数字，不含 0）；其余为 parentId_1, parentId_2...
   */
  function getLeafTasksOfSubtree(parentId) {
    const subtasks = parentId === '0'
      ? tasks.filter(t => t.task_id && /^[1-9]\d*$/.test(t.task_id))
      : tasks.filter(t => t.task_id && t.task_id.startsWith(parentId + '_'));
    if (subtasks.length === 0) return [];

    const dependedOn = new Set();
    subtasks.forEach(t => {
      (t.dependencies || []).forEach(depId => {
        if (depId && (parentId === '0' ? /^[1-9]\d*$/.test(depId) : depId.startsWith(parentId + '_'))) {
          dependedOn.add(depId);
        }
      });
    });

    return subtasks
      .filter(t => !dependedOn.has(t.task_id))
      .map(t => t.task_id);
  }

  taskMap.forEach((task) => {
    const deps = task.dependencies || [];
    const sunk = [];
    for (const depId of deps) {
      if (!depId || typeof depId !== 'string') continue;
      // 若当前任务在 depId 的子树内（如 1 依赖 0、1_2 依赖 1），不下沉，保留原依赖
      if (isInSubtree(task.task_id, depId)) {
        sunk.push(depId);
        continue;
      }
      const leaves = getLeafTasksOfSubtree(depId);
      if (leaves.length > 0) {
        leaves.forEach(id => sunk.push(id));
      } else {
        sunk.push(depId);
      }
    }
    task.dependencies = sunk;
  });

  return Array.from(taskMap.values());
}

/**
 * Compute staged format from flat tasks: sink deps, topological sort, clean deps, add stage.
 * @param {Array} tasks - Flat tasks [{ task_id, dependencies?, ... }]
 * @returns {Array} Staged format [[stage0_tasks], [stage1_tasks], ...], each task has stage (1-based)
 */
function computeTaskStages(tasks) {
  if (!tasks || !Array.isArray(tasks) || tasks.length === 0) {
    return [];
  }

  const resolved = sinkDependencies(tasks);

  const taskList = resolved.map((t, idx) => ({
    ...t,
    task_id: t.task_id || String(idx + 1),
    dependencies: Array.isArray(t.dependencies) ? t.dependencies : []
  }));

  const taskMap = new Map(taskList.map(t => [t.task_id, t]));
  const stages = [];
  const completed = new Set();

  while (completed.size < taskList.length) {
    const ready = taskList.filter(t => {
      if (completed.has(t.task_id)) return false;
      return t.dependencies.length === 0 ||
        t.dependencies.every(dep => completed.has(dep));
    });

    if (ready.length === 0) {
      const remaining = taskList.filter(t => !completed.has(t.task_id));
      if (remaining.length > 0) {
        stages.push(remaining.map(t => ({ ...t })));
      }
      break;
    }

    stages.push(ready.map(t => ({ ...t })));
    ready.forEach(t => completed.add(t.task_id));
  }

  const cleanedStages = cleanDependencies(stages);
  return cleanedStages.map((stage, idx) =>
    stage.map(task => ({ ...task, stage: idx + 1 }))
  );
}

module.exports = {
  computeTaskStages,
  sinkDependencies
};
