/**
 * Verifier Manager Module
 * Manages the state of verifiers (busy/idle)
 */

const MAX_VERIFIERS = 5;

// Verifier state: { id: number, status: 'idle' | 'busy' | 'failed', taskId: string | null }
let verifiers = [];

// Initialize verifiers
function initializeVerifiers() {
  verifiers = [];
  for (let i = 0; i < MAX_VERIFIERS; i++) {
    verifiers.push({
      id: i,  // Verifier IDs: 0-9
      status: 'idle',
      taskId: null
    });
  }
}

// Get all verifier states
function getAllVerifiers() {
  return verifiers.map(v => ({ ...v }));
}

// Get verifier by ID
function getVerifierById(verifierId) {
  return verifiers.find(v => v.id === verifierId) || null;
}

// Get idle verifier
function getIdleVerifier() {
  return verifiers.find(v => v.status === 'idle') || null;
}

// Assign task to verifier
function assignTask(taskId) {
  const verifier = getIdleVerifier();
  if (verifier) {
    // Validate verifier state before assignment
    if (verifier.status !== 'idle') {
      console.error(`Attempting to assign task ${taskId} to verifier ${verifier.id} which is not idle (status: ${verifier.status})`);
      // Reset to idle state
      verifier.status = 'idle';
      verifier.taskId = null;
    }
    verifier.status = 'busy';
    verifier.taskId = taskId;
    console.log(`Verifier ${verifier.id} assigned to task ${taskId}`);
    return verifier.id;
  }
  console.log(`No idle verifier available for task ${taskId}`);
  return null;
}

// Release verifier (mark as idle)
function releaseVerifier(verifierId) {
  const verifier = verifiers.find(v => v.id === verifierId);
  if (verifier) {
    // Validate state before release
    if (verifier.status !== 'busy' && verifier.status !== 'idle' && verifier.status !== 'failed') {
      console.warn(`Verifier ${verifierId} has invalid status "${verifier.status}", resetting to idle`);
    }
    verifier.status = 'idle';
    verifier.taskId = null;
    console.log(`Verifier ${verifierId} released (by verifier ID)`);
    return true;
  }
  console.warn(`Attempted to release verifier ${verifierId} which does not exist`);
  return false;
}

// Release verifier by task ID
function releaseVerifierByTaskId(taskId) {
  const verifier = verifiers.find(v => v.taskId === taskId);
  if (verifier) {
    // Release if verifier is busy or failed
    if (verifier.status === 'busy' || verifier.status === 'failed') {
      const verifierId = verifier.id;
      verifier.status = 'idle';
      verifier.taskId = null;
      console.log(`Verifier ${verifierId} released from task ${taskId}`);
      return verifierId;
    } else {
      // Already idle - this is fine, just return the verifier ID
      console.log(`Verifier ${verifier.id} was already idle for task ${taskId} (duplicate release attempt)`);
      return verifier.id;
    }
  }
  // Log if taskId not found (might be already released or never assigned)
  console.log(`No verifier found for task ${taskId} (may already be released or never assigned)`);
  return null;
}

// Get verifier statistics
function getVerifierStats() {
  // Ensure all verifiers have valid status
  verifiers.forEach(verifier => {
    if (verifier.status !== 'idle' && verifier.status !== 'busy' && verifier.status !== 'failed') {
      console.warn(`Invalid verifier status detected: verifier ${verifier.id} has status "${verifier.status}", resetting to idle`);
      verifier.status = 'idle';
      verifier.taskId = null;
    }
  });
  
  const busy = verifiers.filter(v => v.status === 'busy').length;
  const idle = verifiers.filter(v => v.status === 'idle').length;
  const failed = verifiers.filter(v => v.status === 'failed').length;
  
  // Validate that busy + idle + failed equals total
  if (busy + idle + failed !== MAX_VERIFIERS) {
    console.error(`Verifier state inconsistency detected: busy=${busy}, idle=${idle}, failed=${failed}, total=${MAX_VERIFIERS}`);
    // Fix inconsistency by resetting all verifiers
    console.log('Resetting all verifiers to fix inconsistency...');
    initializeVerifiers();
    return {
      total: MAX_VERIFIERS,
      busy: 0,
      idle: MAX_VERIFIERS,
      failed: 0
    };
  }
  
  return {
    total: MAX_VERIFIERS,
    busy,
    idle,
    failed
  };
}

// Initialize on module load
initializeVerifiers();

module.exports = {
  getAllVerifiers,
  getIdleVerifier,
  getVerifierById,
  assignTask,
  releaseVerifier,
  releaseVerifierByTaskId,
  getVerifierStats,
  initializeVerifiers
};
