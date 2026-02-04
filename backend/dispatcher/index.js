/**
 * Dispatcher Module
 * Generates execution stages from a plan. Execution order is derived from task dependencies.
 */

/**
 * Generate execution stages from plan
 * @param {Object} plan - The plan object (from planner or database)
 * @returns {Array} Execution stages - array of arrays; each inner array is a stage of tasks
 */
function generateExecutionSequence(plan) {
  let planData = plan;
  if (typeof plan === 'string') {
    try {
      planData = JSON.parse(plan);
    } catch (e) {
      throw new Error('Invalid plan format: not valid JSON');
    }
  }

  const taskList = planData.task_list || planData.workflow?.task_list || [];
  if (!Array.isArray(taskList) || taskList.length === 0) {
    return [];
  }

  const allTasks = [];
  const taskMap = new Map();

  taskList.forEach((task, idx) => {
    const taskId = task.id || String(idx + 1);
    const taskObj = {
      id: taskId,
      action: task.action,
      context: task.context,
      dependencies: Array.isArray(task.dependencies) ? task.dependencies : [],
      status: task.status || 'undone'
    };
    allTasks.push(taskObj);
    taskMap.set(taskId, taskObj);
  });

  const executionStages = [];
  const completedTasks = new Set();

  while (completedTasks.size < allTasks.length) {
    const readyTasks = allTasks.filter(task => {
      if (completedTasks.has(task.id)) return false;
      return task.dependencies.length === 0 ||
             task.dependencies.every(dep => completedTasks.has(dep));
    });

    if (readyTasks.length === 0) {
      const remaining = allTasks.filter(t => !completedTasks.has(t.id));
      if (remaining.length > 0) {
        executionStages.push(remaining.map(t => ({
          id: t.id,
          action: t.action,
          context: t.context,
          dependencies: t.dependencies,
          status: t.status
        })));
      }
      break;
    }

    executionStages.push(readyTasks.map(t => ({
      id: t.id,
      action: t.action,
      context: t.context,
      dependencies: t.dependencies,
      status: t.status
    })));

    readyTasks.forEach(t => completedTasks.add(t.id));
  }

  return Array.isArray(executionStages) ? executionStages : [];
}

const timetable = require('./timetable');

module.exports = {
  generateExecutionSequence,
  buildTimetableLayout: timetable.buildTimetableLayout
};
