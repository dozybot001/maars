/**
 * Executor Manager Module
 * Manages the state of executors (busy/idle)
 */

const MAX_EXECUTORS = 7;

// Executor state: { id: number, status: 'idle' | 'busy' | 'failed', taskId: string | null }
let executors = [];

// Initialize executors
function initializeExecutors() {
  executors = [];
  for (let i = 0; i < MAX_EXECUTORS; i++) {
    executors.push({
      id: i,  // Executor IDs: 0-9
      status: 'idle',
      taskId: null
    });
  }
}

// Get all executor states
function getAllExecutors() {
  return executors.map(e => ({ ...e }));
}

// Get executor by ID
function getExecutorById(executorId) {
  return executors.find(e => e.id === executorId) || null;
}

// Get idle executor
function getIdleExecutor() {
  return executors.find(e => e.status === 'idle') || null;
}

// Assign task to executor
function assignTask(taskId) {
  const executor = getIdleExecutor();
  if (executor) {
    // Validate executor state before assignment
    if (executor.status !== 'idle') {
      console.error(`Attempting to assign task ${taskId} to executor ${executor.id} which is not idle (status: ${executor.status})`);
      // Reset to idle state
      executor.status = 'idle';
      executor.taskId = null;
    }
    executor.status = 'busy';
    executor.taskId = taskId;
    console.log(`Executor ${executor.id} assigned to task ${taskId}`);
    return executor.id;
  }
  console.log(`No idle executor available for task ${taskId}`);
  return null;
}

// Release executor (mark as idle)
function releaseExecutor(executorId) {
  const executor = executors.find(e => e.id === executorId);
  if (executor) {
    // Validate state before release
    if (executor.status !== 'busy' && executor.status !== 'idle' && executor.status !== 'failed') {
      console.warn(`Executor ${executorId} has invalid status "${executor.status}", resetting to idle`);
    }
    executor.status = 'idle';
    executor.taskId = null;
    console.log(`Executor ${executorId} released (by executor ID)`);
    return true;
  }
  console.warn(`Attempted to release executor ${executorId} which does not exist`);
  return false;
}

// Release executor by task ID
function releaseExecutorByTaskId(taskId) {
  const executor = executors.find(e => e.taskId === taskId);
  if (executor) {
    // Release if executor is busy or failed
    if (executor.status === 'busy' || executor.status === 'failed') {
      const executorId = executor.id;
      executor.status = 'idle';
      executor.taskId = null;
      console.log(`Executor ${executorId} released from task ${taskId}`);
      return executorId;
    } else {
      // Already idle - this is fine, just return the executor ID
      console.log(`Executor ${executor.id} was already idle for task ${taskId} (duplicate release attempt)`);
      return executor.id;
    }
  }
  // Log if taskId not found (might be already released or never assigned)
  // This is not necessarily an error - task might have been released already
  console.log(`No executor found for task ${taskId} (may already be released or never assigned)`);
  return null;
}

// Get executor statistics
function getExecutorStats() {
  // Ensure all executors have valid status
  executors.forEach(executor => {
    if (executor.status !== 'idle' && executor.status !== 'busy' && executor.status !== 'failed') {
      console.warn(`Invalid executor status detected: executor ${executor.id} has status "${executor.status}", resetting to idle`);
      executor.status = 'idle';
      executor.taskId = null;
    }
  });
  
  const busy = executors.filter(e => e.status === 'busy').length;
  const idle = executors.filter(e => e.status === 'idle').length;
  const failed = executors.filter(e => e.status === 'failed').length;
  
  // Validate that busy + idle + failed equals total
  if (busy + idle + failed !== MAX_EXECUTORS) {
    console.error(`Executor state inconsistency detected: busy=${busy}, idle=${idle}, failed=${failed}, total=${MAX_EXECUTORS}`);
    // Fix inconsistency by resetting all executors
    console.log('Resetting all executors to fix inconsistency...');
    initializeExecutors();
    return {
      total: MAX_EXECUTORS,
      busy: 0,
      idle: MAX_EXECUTORS,
      failed: 0
    };
  }
  
  return {
    total: MAX_EXECUTORS,
    busy,
    idle,
    failed
  };
}

// Initialize on module load
initializeExecutors();

module.exports = {
  getAllExecutors,
  getIdleExecutor,
  getExecutorById,
  assignTask,
  releaseExecutor,
  releaseExecutorByTaskId,
  getExecutorStats,
  initializeExecutors
};
