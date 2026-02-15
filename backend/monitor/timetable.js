/**
 * Task Layout Module
 * Builds grid layout from staged tasks (already cleaned by computeTaskStages).
 */

/**
 * Deep clone an object to avoid modifying original data
 * @param {*} obj - Object to clone
 * @returns {*} Cloned object
 */
function deepClone(obj) {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }
  
  if (obj instanceof Date) {
    return new Date(obj.getTime());
  }
  
  if (obj instanceof Array) {
    return obj.map(item => deepClone(item));
  }
  
  if (typeof obj === 'object') {
    const cloned = {};
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        cloned[key] = deepClone(obj[key]);
      }
    }
    return cloned;
  }
  
  return obj;
}

/**
 * Clean dependencies: only keep dependencies from the previous stage
 * This function creates a deep copy of executionStages and cleans dependencies
 * Stage 0: keeps all dependencies (initial tasks)
 * Stage 1+: only keeps dependencies from the previous stage (stage - 1)
 * @param {Array} executionStages - Array of execution stages
 * @returns {Array} Cleaned execution stages (deep copy, original data not modified)
 */
function cleanDependencies(executionStages) {
  if (!executionStages || executionStages.length === 0) {
    return [];
  }

  // Deep clone executionStages to avoid modifying original data
  const cleanedStages = deepClone(executionStages);

  // Build task-to-stage mapping cache
  // Extract all task IDs and their stage indices into cache
  const taskStageCache = new Map(); // taskId -> stageIndex
  cleanedStages.forEach((stage, stageIndex) => {
    if (stage && Array.isArray(stage)) {
      stage.forEach(task => {
        if (task && task.task_id) {
          taskStageCache.set(task.task_id, stageIndex);
        }
      });
    }
  });

  // Clean dependencies starting from stage 1 (stage 0 keeps all dependencies)
  for (let stageIndex = 1; stageIndex < cleanedStages.length; stageIndex++) {
    const currentStage = cleanedStages[stageIndex];
    const previousStageIndex = stageIndex - 1;

    if (!currentStage || !Array.isArray(currentStage)) {
      continue;
    }

    // Get all task IDs from the previous stage
    const previousStageTaskIds = new Set();
    const previousStage = cleanedStages[previousStageIndex];
    if (previousStage && Array.isArray(previousStage)) {
      previousStage.forEach(task => {
        if (task && task.task_id) {
          previousStageTaskIds.add(task.task_id);
        }
      });
    }

    // Clean dependencies for each task in current stage
    currentStage.forEach(task => {
      if (!task || !task.dependencies || !Array.isArray(task.dependencies)) {
        return;
      }

      // Filter dependencies: only keep those from the previous stage
      task.dependencies = task.dependencies.filter(depId => {
        // Skip invalid dependency IDs
        if (!depId || typeof depId !== 'string' || depId.trim() === '' || depId === 'undefined' || depId === 'null') {
          return false;
        }

        const trimmedDepId = depId.trim();
        
        // Check if dependency is in the previous stage
        return previousStageTaskIds.has(trimmedDepId);
      });
    });
  }

  return cleanedStages;
}

/**
 * Build task layout (grid) from staged tasks. Expects tasks already cleaned by computeTaskStages.
 * @param {Array} taskStages - Staged format [[stage0], [stage1], ...], each task has stage
 * @returns {Object} { grid, maxRows, maxCols, isolatedTasks, treeData }
 */
function buildTaskLayout(taskStages) {
  if (!taskStages || taskStages.length === 0) {
    return { grid: [], maxRows: 0, maxCols: 0, isolatedTasks: [], treeData: [] };
  }

  const cleanedStages = taskStages;

  // Build complete task map and dependency graph from cleaned stages
  const allTasks = new Map();
  const taskDependents = new Map(); // Map: taskId -> array of tasks that depend on it

  cleanedStages.forEach(stage => {
    stage.forEach(task => {
      allTasks.set(task.task_id, task);
      if (!taskDependents.has(task.task_id)) {
        taskDependents.set(task.task_id, []);
      }

      // Track which tasks depend on this task
      if (task.dependencies && task.dependencies.length > 0) {
        task.dependencies.forEach(depId => {
          if (!taskDependents.has(depId)) {
            taskDependents.set(depId, []);
          }
          taskDependents.get(depId).push(task.task_id);
        });
      }
    });
  });

  // Separate tasks into: dependency tasks (have dependencies or dependents) and isolated tasks
  const dependencyTasks = [];
  const isolatedTasks = [];

  allTasks.forEach((task, task_id) => {
    const hasDependencies = task.dependencies && task.dependencies.length > 0;
    const hasDependents = taskDependents.get(task_id) && taskDependents.get(task_id).length > 0;

    if (!hasDependencies && !hasDependents) {
      // Isolated task - no dependencies and no one depends on it
      isolatedTasks.push(task);
    } else {
      // Dependency task - has dependencies or dependents (or both)
      dependencyTasks.push(task);
    }
  });

  // Build columns for dependency tasks
  // Column 0: tasks with no dependencies (but have dependents)
  // Column 1+: tasks whose dependencies are all in previous columns
  const taskPositions = new Map(); // Map: taskId -> { col, row, task }
  const dependencyColumns = []; // Array of arrays: each array is a column of tasks

  // Track which tasks have been placed
  const placedTasks = new Set();

  // Build columns iteratively
  while (placedTasks.size < dependencyTasks.length) {
    const currentColumn = [];

    dependencyTasks.forEach(task => {
      if (placedTasks.has(task.task_id)) {
        return; // Already placed
      }

      const hasDependencies = task.dependencies && task.dependencies.length > 0;

      if (!hasDependencies) {
        // Task with no dependencies - can go in current column
        // Check if it has dependents (if not, it's isolated, but we already filtered those)
        currentColumn.push(task);
      } else {
        // Task has dependencies - check if all dependencies are in previous columns
        const allDepsPlaced = task.dependencies.every(depId => placedTasks.has(depId));
        if (allDepsPlaced) {
          currentColumn.push(task);
        }
      }
    });

    if (currentColumn.length === 0) {
      // No more tasks can be placed (circular dependency or missing dependencies)
      // Add remaining tasks to current column anyway
      dependencyTasks.forEach(task => {
        if (!placedTasks.has(task.task_id)) {
          currentColumn.push(task);
        }
      });
    }

    if (currentColumn.length > 0) {
      dependencyColumns.push(currentColumn);
      currentColumn.forEach(task => placedTasks.add(task.task_id));
    } else {
      break; // No more tasks to place
    }
  }

  // Assign row positions within each column
  // Tasks that depend on the same parent are placed vertically (consecutive rows)
  let maxRows = 0;

  dependencyColumns.forEach((column, colIndex) => {
    // Group tasks by their rightmost dependency (the dependency in the rightmost column)
    const tasksByRightmostDep = new Map();
    const tasksWithNoDeps = [];

    column.forEach(task => {
      if (!task.dependencies || task.dependencies.length === 0) {
        tasksWithNoDeps.push(task);
      } else {
        // Find the rightmost dependency
        let rightmostDepId = null;
        let rightmostDepCol = -1;

        task.dependencies.forEach(depId => {
          const depPos = taskPositions.get(depId);
          if (depPos && depPos.col > rightmostDepCol) {
            rightmostDepId = depId;
            rightmostDepCol = depPos.col;
          }
        });

        if (rightmostDepId) {
          if (!tasksByRightmostDep.has(rightmostDepId)) {
            tasksByRightmostDep.set(rightmostDepId, []);
          }
          tasksByRightmostDep.get(rightmostDepId).push(task);
        } else {
          // Dependencies not found (shouldn't happen, but handle gracefully)
          tasksWithNoDeps.push(task);
        }
      }
    });

    // Assign rows: first tasks with no dependencies, then tasks grouped by rightmost dependency
    let currentRow = 0;

    tasksWithNoDeps.forEach(task => {
      taskPositions.set(task.task_id, {
        col: colIndex,
        row: currentRow,
        task: task
      });
      currentRow++;
    });

    tasksByRightmostDep.forEach(tasks => {
      tasks.forEach(task => {
        taskPositions.set(task.task_id, {
          col: colIndex,
          row: currentRow,
          task: task
        });
        currentRow++;
      });
    });

    if (currentRow > maxRows) {
      maxRows = currentRow;
    }
  });

  // Ensure at least one row
  if (maxRows === 0) {
    maxRows = 1;
  }

  const regularCols = dependencyColumns.length;

  // Build 2D grid for dependency tasks: grid[row][col] = task or null
  const grid = [];
  for (let row = 0; row < maxRows; row++) {
    grid[row] = [];
    for (let col = 0; col < regularCols; col++) {
      grid[row][col] = null;
    }
  }

  taskPositions.forEach((pos, taskId) => {
    if (pos.col < regularCols) {
      grid[pos.row][pos.col] = pos.task;
    }
  });

  const treeData = cleanedStages.flat().map(task => ({ ...task, stage: task.stage || 1 }));

  return { 
    grid, 
    maxRows, 
    maxCols: regularCols, 
    isolatedTasks, 
    treeData
  };
}

module.exports = {
  buildTaskLayout,
  cleanDependencies,
  deepClone
};
