/**
 * Timetable Layout Module
 * Calculates timetable layout for dependency tasks visualization
 */

/**
 * Build timetable layout: assign row positions to tasks for visual continuity
 * Logic: Column 0 = dependency tasks with no dependencies (but have dependents)
 *        Column 1+ = dependency tasks whose dependencies are all in previous columns
 *        Rightmost columns = isolated tasks (no dependencies AND no dependents)
 * Tasks that depend on the same parent are placed vertically (same column, different rows)
 * @param {Array} executionStages - Array of execution stages, each stage is an array of tasks
 * @returns {Object} Layout object with grid, maxRows, maxCols, and isolatedTasks
 */
function buildTimetableLayout(executionStages) {
  if (!executionStages || executionStages.length === 0) {
    return { grid: [], maxRows: 0, maxCols: 0, isolatedTasks: [] };
  }

  // Build complete task map and dependency graph from all stages
  const allTasks = new Map();
  const taskDependents = new Map(); // Map: taskId -> array of tasks that depend on it

  executionStages.forEach(stage => {
    stage.forEach(task => {
      allTasks.set(task.id, task);
      if (!taskDependents.has(task.id)) {
        taskDependents.set(task.id, []);
      }

      // Track which tasks depend on this task
      if (task.dependencies && task.dependencies.length > 0) {
        task.dependencies.forEach(depId => {
          if (!taskDependents.has(depId)) {
            taskDependents.set(depId, []);
          }
          taskDependents.get(depId).push(task.id);
        });
      }
    });
  });

  // Separate tasks into: dependency tasks (have dependencies or dependents) and isolated tasks
  const dependencyTasks = [];
  const isolatedTasks = [];

  allTasks.forEach((task, taskId) => {
    const hasDependencies = task.dependencies && task.dependencies.length > 0;
    const hasDependents = taskDependents.get(taskId) && taskDependents.get(taskId).length > 0;

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
      if (placedTasks.has(task.id)) {
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
        if (!placedTasks.has(task.id)) {
          currentColumn.push(task);
        }
      });
    }

    if (currentColumn.length > 0) {
      dependencyColumns.push(currentColumn);
      currentColumn.forEach(task => placedTasks.add(task.id));
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
      taskPositions.set(task.id, {
        col: colIndex,
        row: currentRow,
        task: task
      });
      currentRow++;
    });

    tasksByRightmostDep.forEach(tasks => {
      tasks.forEach(task => {
        taskPositions.set(task.id, {
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

  // Fill grid with dependency tasks
  taskPositions.forEach((pos, taskId) => {
    if (pos.col < regularCols) {
      grid[pos.row][pos.col] = pos.task;
    }
  });

  // Return grid, dimensions, and isolated tasks separately
  return { grid, maxRows, maxCols: regularCols, isolatedTasks };
}

module.exports = {
  buildTimetableLayout
};
