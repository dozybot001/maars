/**
 * Worker pool for executors and verifiers
 * Manages state: idle | busy | failed
 */
function createWorkerPool(maxWorkers, name = 'worker') {
  let workers = [];

  function init() {
    workers = [];
    for (let i = 0; i < maxWorkers; i++) {
      workers.push({ id: i + 1, status: 'idle', taskId: null });
    }
  }

  function getAll() {
    return workers.map(w => ({ ...w }));
  }

  function getById(id) {
    return workers.find(w => w.id === id) || null;
  }

  function getIdle() {
    return workers.find(w => w.status === 'idle') || null;
  }

  function assignTask(taskId) {
    const w = getIdle();
    if (w) {
      if (w.status !== 'idle') {
        w.status = 'idle';
        w.taskId = null;
      }
      w.status = 'busy';
      w.taskId = taskId;
      return w.id;
    }
    return null;
  }

  function releaseByTaskId(taskId) {
    const w = workers.find(x => x.taskId === taskId);
    if (w && (w.status === 'busy' || w.status === 'failed')) {
      w.status = 'idle';
      w.taskId = null;
      return w.id;
    }
    return w ? w.id : null;
  }

  function getStats() {
    workers.forEach(w => {
      if (!['idle', 'busy', 'failed'].includes(w.status)) {
        w.status = 'idle';
        w.taskId = null;
      }
    });
    const busy = workers.filter(w => w.status === 'busy').length;
    const idle = workers.filter(w => w.status === 'idle').length;
    const failed = workers.filter(w => w.status === 'failed').length;
    if (busy + idle + failed !== maxWorkers) {
      init();
      return { total: maxWorkers, busy: 0, idle: maxWorkers, failed: 0 };
    }
    return { total: maxWorkers, busy, idle, failed };
  }

  init();
  return {
    getAll,
    getById,
    getIdle,
    assignTask,
    releaseByTaskId,
    getStats,
    initialize: init
  };
}

const executorPool = createWorkerPool(7, 'executor');
const verifierPool = createWorkerPool(5, 'verifier');

module.exports = {
  executor: {
    getAllExecutors: executorPool.getAll,
    getExecutorById: executorPool.getById,
    getIdleExecutor: executorPool.getIdle,
    assignTask: executorPool.assignTask,
    releaseExecutorByTaskId: executorPool.releaseByTaskId,
    getExecutorStats: executorPool.getStats,
    initializeExecutors: executorPool.initialize
  },
  verifier: {
    getAllVerifiers: verifierPool.getAll,
    getVerifierById: verifierPool.getById,
    getIdleVerifier: verifierPool.getIdle,
    assignTask: verifierPool.assignTask,
    releaseVerifierByTaskId: verifierPool.releaseByTaskId,
    getVerifierStats: verifierPool.getStats,
    initializeVerifiers: verifierPool.initialize
  }
};
